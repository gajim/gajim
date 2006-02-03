##	common/nslookup.py
##
## Contributors for this file:
##	- Dimitur Kirov <dkirov@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2006 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import sys, os, sre

from xmpp.idlequeue import IdleObject, IdleQueue
if os.name == 'nt':
	from subprocess import *
elif os.name == 'posix':
	import fcntl
# it is good to check validity of arguments, when calling system commands
ns_type_pattern = sre.compile('^[a-z]+$')

# match srv host_name
host_pattern = sre.compile('^[a-z0-9\-._]*[a-z0-9]\.[a-z]{2,}$')

class Resolver:
	def __init__(self, idlequeue):
		self.idlequeue = idlequeue
		# dict {host : list of srv records}
		self.resolved_hosts = {} 
		# dict {host : list of callbacks}
		self.handlers = {} 
	
	def parse_srv_result(self, fqdn, result):
		''' parse the output of nslookup command and return list of 
		properties: 'host', 'port','weight', 'priority'	corresponding to the found
		srv hosts '''
		if os.name == 'nt':
			return self._parse_srv_result_nt(fqdn, result)
		elif os.name == 'posix':
			return self._parse_srv_result_posix(fqdn, result)
	
	def _parse_srv_result_nt(self, fqdn, result):
		# output from win32 nslookup command
		if not result: 
			return []
		hosts = []
		lines = result.replace('\r','').split('\n')
		current_host = None
		for line in lines:
			line = line.lstrip()
			if line == '':
				continue
			if line.startswith(fqdn):
				rest = line[len(fqdn):]
				if rest.find('service') > -1:
					current_host = {}
			elif isinstance(current_host, dict):
				res = line.strip().split('=')
				if len(res) != 2:
					if len(current_host) == 4:
						hosts.append(current_host)
					current_host = None
					continue
				prop_type = res[0].strip() 
				prop_value = res[1].strip()
				if prop_type.find('prio') > -1:
					try:
						current_host['prio'] = int(prop_value)
					except ValueError:
						continue
				elif prop_type.find('weight') > -1:
					try:
						current_host['weight'] = int(prop_value)
					except ValueError:
						continue
				elif prop_type.find('port') > -1:
					try:
						current_host['port'] = int(prop_value)
					except ValueError:
						continue
				elif prop_type.find('host') > -1:
					current_host['host'] = prop_value
				if len(current_host) == 4:
					hosts.append(current_host)
					current_host = None
		return hosts
	
	def _parse_srv_result_posix(self, fqdn, result):
		# typical output of bind-tools nslookup command
		if not result: 
			return []
		hosts = []
		lines = result.split('\n')
		for line in lines:
			if line == '':
				continue
			if line.startswith(fqdn):
				rest = line[len(fqdn):].split('=')
				if len(rest) != 2:
					continue
				answer_type, props_str = rest
				if answer_type.strip() != 'service':
					continue
				props = props_str.strip().split(' ')
				if len(props) < 4:
					continue
				prio, weight, port, host  = props[-4:]
				if host[-1] == '.':
					host = host[:-1]
				try:
					prio = int(prio)
					weight = int(weight)
					port = int(port)
				except ValueError:
					continue
				hosts.append({'host': host, 'port': port,'weight': weight,
						'prio': prio})
		return hosts
	
	def _on_ready(self, host, result):
		# nslookup finished, parse the result and call the handlers
		result_list = self.parse_srv_result(host, result)
		
		# practically it is impossible to be the opposite, but who knows :)
		if not self.resolved_hosts.has_key(host):
			self.resolved_hosts[host] = result_list
		if self.handlers.has_key(host):
			for callback in self.handlers[host]:
				callback(host, result_list)
			del(self.handlers[host])
	
	def start_resolve(self, host):
		''' spawn new nslookup process and start waiting for results '''
		ns = NsLookup(self._on_ready, host)
		ns.set_idlequeue(self.idlequeue)
		ns.commandtimeout = 10
		ns.start()
	
	def resolve(self, host, on_ready):
		if not host:
			# empty host, return empty list of srv records
			on_ready([])
			return
		if self.resolved_hosts.has_key(host):
			# host is already resolved, return cached values
			on_ready(host, self.resolved_hosts[host])
			return
		if self.handlers.has_key(host):
			# host is about to be resolved by another connection,
			# attach our callback 
			self.handlers[host].append(on_ready)
		else:
			# host has never been resolved, start now
			self.handlers[host] = [on_ready]
			self.start_resolve(host)

class IdleCommand(IdleObject):
	def __init__(self, on_result):
		# how long (sec.) to wait for result ( 0 - forever )
		# it is a class var, instead of a constant and we can override it.
		self.commandtimeout = 0 
		# when we have some kind of result (valid, ot not) we call this handler
		self.result_handler = on_result
		# if it is True, we can safetely execute the command
		self.canexecute = True
		self.idlequeue = None
		self.result =''
	
	def set_idlequeue(self, idlequeue):
		self.idlequeue = idlequeue
	
	def _return_result(self):
		if self.result_handler:
			self.result_handler(self.result)
		self.result_handler = None
	
	def _compose_command_args(self):
		return ['echo', 'da']
	
	def _compose_command_line(self):
		''' return one line representation of command and its arguments '''
		return  reduce(lambda left, right: left + ' ' + right,  self._compose_command_args())
	
	def wait_child(self):
		if self.pipe.poll() is None:
			# result timeout
			if self.endtime < self.idlequeue.current_time():
				self._return_result()
				self.pipe.stdout.close()
			else:
				# child is still active, continue to wait
				self.idlequeue.set_alarm(self.wait_child, 0.1)
		else:
			# child has quit
			self.result = self.pipe.stdout.read()
			self._return_result()
			self.pipe.stdout.close()
		
	def start(self):
		if os.name == 'nt':
			self._start_nt()
		elif os.name == 'posix':
			self._start_posix()
	
	def _start_nt(self):
		if not self.canexecute:
			self.result = ''
			self._return_result()
			return
		self.pipe = Popen(self._compose_command_args(), stdout=PIPE, 
			bufsize = 1024, shell = True, stderr = STDOUT, stdin = None)
		if self.commandtimeout >= 0:
			self.endtime = self.idlequeue.current_time()
			self.idlequeue.set_alarm(self.wait_child, 0.1)
	
	def _start_posix(self):
		self.pipe = os.popen(self._compose_command_line())
		self.fd = self.pipe.fileno()
		fcntl.fcntl(self.pipe, fcntl.F_SETFL, os.O_NONBLOCK)
		self.idlequeue.plug_idle(self, False, True)
		if self.commandtimeout >= 0:
			self.idlequeue.set_read_timeout(self.fd, self.commandtimeout)
		
	def end(self):
		self.idlequeue.unplug_idle(self.fd)
		try:
			self.pipe.close()
		except:
			pass
	
	def pollend(self):
		self.idlequeue.remove_timeout(self.fd)
		self.end()
		self._return_result()
	
	def pollin(self):
		try:
			res = self.pipe.read()
		except Exception, e:
			res = ''
		if res == '':
			return self.pollend()
		else:
			self.result += res
	
	def read_timeout(self):
		self.end()
		self._return_result()
	
class NsLookup(IdleCommand):
	def __init__(self, on_result, host='_xmpp-client', type = 'srv'):
		IdleCommand.__init__(self, on_result)
		self.commandtimeout = 30 
		self.host = host.lower()
		self.type = type.lower()
		if not host_pattern.match(self.host):
			# invalid host name
			# TODO: notify user about this. Maybe message to stderr will be enough
			self.host = None
			self.canexecute = False
			return
		if not ns_type_pattern.match(self.type):
			self.type = None
			self.host = None
			self.canexecute = False
			return
	
	def _compose_command_args(self):
		return ['nslookup', '-type=' + self.type , self.host]
	
	def _return_result(self):
		if self.result_handler:
			self.result_handler(self.host, self.result)
		self.result_handler = None
	
if __name__ == '__main__':
	if os.name != 'posix':
		sys.exit()
	# testing Resolver class
	import gobject
	import gtk
	idlequeue = IdleQueue()
	resolver = Resolver(idlequeue)
	
	def clicked(widget):
		global resolver
		host = text_view.get_text()
		def on_result(host, result_array):
			print 'Result:\n' + repr(result_array)
		resolver.resolve(host, on_result)
	win = gtk.Window()
	win.set_border_width(6)
	text_view = gtk.Entry()
	text_view.set_text('_xmpp-client._tcp.jabber.org')
	hbox = gtk.HBox()
	hbox.set_spacing(3)
	but = gtk.Button(' Lookup SRV ')
	hbox.pack_start(text_view, 5)
	hbox.pack_start(but, 0)
	but.connect('clicked', clicked)
	win.add(hbox)
	win.show_all()
	gobject.timeout_add(200, idlequeue.process)
	gtk.main()
