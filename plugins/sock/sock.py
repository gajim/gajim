##      plugins/sock.py
##
## Gajim Team:
##      - Yann Le Boulanger <asterix@lagaule.org>
##      - Vincent Hanquez <tab@snarc.org>
##
##      Copyright (C) 2003-2005 Gajim Team
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

import socket, select
import pickle
import Queue
import sys

from common import i18n
_ = i18n._


def XMLescape(txt):
	"Escape XML entities"
	txt = txt.replace("&", "&amp;")
	txt = txt.replace("<", "&lt;")
	txt = txt.replace(">", "&gt;")
	return txt

def XMLunescape(txt):
	"Unescape XML entities"
	txt = txt.replace("&gt;", ">")
	txt = txt.replace("&lt;", "<")
	txt = txt.replace("&amp;", "&")
	return txt

class plugin:

	def wait(self, what):
		"""Wait for a message from Core"""
		#TODO: timeout
		temp_q = Queue.Queue(50)
		while 1:
			if not self.queueIN.empty():
				ev = self.queueIN.get()
				if ev[0] == what and ev[2][0] == 'sock':
					#Restore messages
					while not temp_q.empty():
						ev2 = temp_q.get()
						self.queueIN.put(ev2)
					return ev[2][1]
				else:
					#Save messages
					temp_q.put(ev)

	def send(self, event, account, data):
		self.queueOUT.put((event, account, data))

	def handle_queue_quit(self, account, array):
#		for sock in self.active_socket:
#			if sock != self.active_socket:
#				sock.close()
		self.quit_recieved = 1

	def handle_socket_reg_message(self, sock, array):
		for type in array:
			if self.message_types.has_key(type):
				if not sock in self.message_types[type]:
					self.message_types[type].append(sock)
			else:
				self.message_types[type] = [sock]

	def send_to_socket(self, ev, sock):
		evp = pickle.dumps(ev)
		sock.send('<'+XMLescape(evp)+'>')
	
	def unparse_socket(self, data):
		list_ev = []
		while data:
			deb = data.find('<')
			end = data.find('>', deb)
			list_ev.append(pickle.loads(data[deb+1:end]))
			data = data[end+1:]
		return list_ev

	def read_queue(self):
		while self.queueIN.empty() == 0:
			ev = self.queueIN.get()
			if ev[0] in self.message_types:
				for sock in self.message_types[ev[0]]:
					self.send_to_socket(ev, sock)
			if ev[0] == 'QUIT':
				self.handle_queue_quit(ev[1], ev[2])
#				return 1
		return 0

	def read_socket(self):
		ready_to_read, ready_to_write, in_error = select.select(
			self.active_socket, [], [], 0.1)

		for sock in ready_to_read:
			if sock == self.socket:
				conn, addr = self.socket.accept()
				# Connected by  addr
				print _("Connection from "), addr
				self.active_socket.append(conn)
			else:
				try:
					data = sock.recv(1024)
				except:
					self.active_socket.remove(sock)
					break
				if not data:
					# disconnected
					print _("disconnected")
					self.active_socket.remove(sock)
					break
				while len(data) == 1024:
					data += sock.recv(1024)
				list_ev = self.unparse_socket(data)
				for ev in list_ev:
					if ev[0] == 'REG_MESSAGE':
						self.handle_socket_reg_message(sock, ev[2])
						ev = (ev[0], 'sock', ev[2])
					self.queueOUT.put(ev)
		return 0

	def __init__(self, quIN, quOUT):
		self.queueIN = quIN
		self.queueOUT = quOUT
		self.send('REG_MESSAGE', 'sock', ['QUIT', 'CONFIG'])
		quOUT.put(('ASK_CONFIG', None, ('sock', 'sock', {\
			'port':8255})))
		self.config = self.wait('CONFIG')
		self.message_types = {}
		#create socket
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		HOST = socket.gethostbyname(socket.gethostname())
		if self.config.has_key('host'):
			HOST = socket.gethostbyname(self.config['host'])
		try:
			self.socket.bind((HOST, self.config['port']))
		except:
			print _('plugin sock cannot be launched : ') + \
				str(sys.exc_info()[1][0:])
			return
		self.socket.listen(5)

		self.active_socket = [self.socket]
		end = 0
		self.quit_recieved = 0

		while not end:
			# listen to the socket
			end = self.read_socket()
			# listen to the input Queue
			end = self.read_queue()
			if self.quit_recieved:
				if len(self.active_socket) == 1:
					end = 1
		print _("plugin sock stopped")

if __name__ == "__main__":
	plugin(None, None)

print _("plugin sock loaded")
