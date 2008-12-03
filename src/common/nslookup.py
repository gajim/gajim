# -*- coding:utf-8 -*-
## src/common/nslookup.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import sys
import os
import re
from common import helpers

from xmpp.idlequeue import *

if os.name == 'nt':
	from subprocess import * # python24 only. we ask this for Windows
elif os.name == 'posix':
	import fcntl

# it is good to check validity of arguments, when calling system commands
ns_type_pattern = re.compile('^[a-z]+$')

# match srv host_name
host_pattern = re.compile('^[a-z0-9\-._]*[a-z0-9]\.[a-z]{2,}$')

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
					# strip '.' at the end of hostname
					if prop_value[-1] == '.':
						prop_value = prop_value[:-1]
					current_host['host'] = prop_value
				if len(current_host) == 4:
					hosts.append(current_host)
					current_host = None
		return hosts

	def _parse_srv_result_posix(self, fqdn, result):
		# typical output of bind-tools nslookup command:
		# _xmpp-client._tcp.jabber.org    service = 30 30 5222 jabber.org.
		if not result:
			return []
		ufqdn = helpers.ascii_to_idn(fqdn) # Unicode domain name
		hosts = []
		lines = result.split('\n')
		for line in lines:
			if line == '':
				continue
			domain = None
			if line.startswith(fqdn):
				domain = fqdn
			elif helpers.decode_string(line).startswith(ufqdn):
				line = helpers.decode_string(line)
				domain = ufqdn
			if domain:
				rest = line[len(domain):].split('=')
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
		if host not in self.resolved_hosts:
			self.resolved_hosts[host] = result_list
		if host in self.handlers:
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
		if host in self.resolved_hosts:
			# host is already resolved, return cached values
			on_ready(host, self.resolved_hosts[host])
			return
		if host in self.handlers:
			# host is about to be resolved by another connection,
			# attach our callback
			self.handlers[host].append(on_ready)
		else:
			# host has never been resolved, start now
			self.handlers[host] = [on_ready]
			self.start_resolve(host)

# TODO: move IdleCommand class in other file, maybe helpers ?
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
		self.result = ''

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
		return ' '.join(self._compose_command_args())

	def wait_child(self):
		if self.pipe.poll() is None:
			# result timeout
			if self.endtime < self.idlequeue.current_time():
				self._return_result()
				self.pipe.stdout.close()
				self.pipe.stdin.close()
			else:
				# child is still active, continue to wait
				self.idlequeue.set_alarm(self.wait_child, 0.1)
		else:
			# child has quit
			self.result = self.pipe.stdout.read()
			self._return_result()
			self.pipe.stdout.close()
			self.pipe.stdin.close()
	def start(self):
		if not self.canexecute:
			self.result = ''
			self._return_result()
			return
		if os.name == 'nt':
			self._start_nt()
		elif os.name == 'posix':
			self._start_posix()

	def _start_nt(self):
		# if gajim is started from noninteraactive shells stdin is closed and
		# cannot be forwarded, so we have to keep it open
		self.pipe = Popen(self._compose_command_args(), stdout=PIPE,
			bufsize = 1024, shell = True, stderr = STDOUT, stdin = PIPE)
		if self.commandtimeout >= 0:
			self.endtime = self.idlequeue.current_time() + self.commandtimeout
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
		except Exception:
			pass

	def pollend(self):
		self.idlequeue.remove_timeout(self.fd)
		self.end()
		self._return_result()

	def pollin(self):
		try:
			res = self.pipe.read()
		except Exception:
			res = ''
		if res == '':
			return self.pollend()
		else:
			self.result += res

	def read_timeout(self):
		self.end()
		self._return_result()

class NsLookup(IdleCommand):
	def __init__(self, on_result, host='_xmpp-client', type_ = 'srv'):
		IdleCommand.__init__(self, on_result)
		self.commandtimeout = 10
		self.host = host.lower()
		self.type = type_.lower()
		if not host_pattern.match(self.host):
			# invalid host name
			print >> sys.stderr, 'Invalid host: %s' % self.host
			self.canexecute = False
			return
		if not ns_type_pattern.match(self.type):
			print >> sys.stderr, 'Invalid querytype: %s' % self.type
			self.canexecute = False
			return

	def _compose_command_args(self):
		return ['nslookup', '-type=' + self.type , self.host]

	def _return_result(self):
		if self.result_handler:
			self.result_handler(self.host, self.result)
		self.result_handler = None

# below lines is on how to use API and assist in testing
if __name__ == '__main__':
	if os.name == 'posix':
		idlequeue = IdleQueue()
	elif os.name == 'nt':
		idlequeue = SelectIdleQueue()
	# testing Resolver class
	import gobject
	import gtk

	resolver = Resolver(idlequeue)

	def clicked(widget):
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

	def process():
		try:
			idlequeue.process()
		except Exception:
			# Otherwise, an exception will stop our loop
			gobject.timeout_add(200, process)
			raise
		return True

	gobject.timeout_add(200, process)
	gtk.main()

# vim: se ts=3:
