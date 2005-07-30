##	common/socks5.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##  - Dimitur Kirov <dkirov@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
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


import socket
import select 
import fcntl
import struct
import sha

class SocksQueue:
	''' qwueue for all file requests objects '''
	def __init__(self):
		self.connected = 0
		self.readers = {}
		self.files_props = {}
		self.idx = 0
	
	def add_receiver(self, sock5_receiver):
		''' add new file request '''
		self.readers[self.idx] = sock5_receiver
		sock5_receiver.queue_idx = self.idx
		sock5_receiver.queue = self
		self.idx += 1
		result = sock5_receiver.connect()
		self.connected += 1
		return result
	
	def add_file_props(self, file_props):
		if file_props is None or \
			file_props.has_key('sid') is False:
			return
		id = file_props['sid']
		self.files_props[id] = file_props
		
	def get_file_props(self, id):
		if self.files_props.has_key(id):
			return self.files_props[id]
		return None

	def process(self, timeout=0):
		''' process all file requests '''
		for idx in self.readers.keys():
			receiver = self.readers[idx]
			if receiver.connected:
				if not receiver.receiving and receiver.pending_data():
					receiver.get_file_contents(timeout)
			else:
				self.remove_receiver(idx)
		
	def remove_receiver(self, idx):
		if idx != -1:
			if self.readers.has_key(idx):
				del(self.readers[idx])
			if self.connected > 0:
				self.connected -= 1
	
class Socks5:
	def __init__(self, host, port, initiator, target, sid):
		self.host = socket.gethostbyname(host)
		self.port = port
		self.initiator = initiator
		self.target = target
		self.sid = sid
		self._sock = None
	
	def connect(self):
		self._sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.connect((self.host, self.port))
		self._sock.setblocking(True)
		self._send=self._sock.sendall
		self._recv=self._sock.recv
		self.connected = True
		return self.send_connect()
	
	def receive(self):
		''' Reads all pending incoming data. 
			Calls owner's disconnected() method if appropriate.'''
		try: 
			received = self._recv(64)
		except: 
			received = ''
	
		while self.pending_data():
			try: 
				add = self._recv(64)
			except: 
				add=''
			received +=add
			if not add: 
				break
	
		if len(received) == 0:
			self.disconnect()
		return received

	def send_raw(self,raw_data):
		""" Writes raw outgoing data. Blocks until done.
			If supplied data is unicode string, encodes it to utf-8 before send."""
		try:
			self._send(raw_data)
		except:
			self.disconnect()
		pass
			
	def disconnect(self):
		""" Closes the socket. """
		fcntl.fcntl(self._sock, fcntl.F_SETFL, 0);
		self._sock.close()
		self.connected = False
		
	def pending_data(self,timeout=0):
		""" Returns true if there is a data ready to be read. """
		if self._sock is None:
			return False
		try:
			return select.select([self._sock],[],[],timeout)[0]
		except:
			return False
	
	def send_connect(self):
		self.send_raw(self._get_auth_buff())
		buff = self.receive()
		version, method = struct.unpack('!BB', buff[:2])
		if version != 0x05 or method == 0xff:
			self.disconnect()
			return None
		self.send_raw(self._get_request_buff())
		buff = self.receive()
		version, command, rsvd, address_type = struct.unpack('!BBBB', buff[:4])
		addrlen, address, port = 0, 0, 0
		if address_type == 0x03:
			addrlen = ord(buff[4])
			address, port= struct.unpack('!%dsH' % addrlen, buff[5:])
		return (version, command, rsvd, address_type, addrlen, address, port)
		
		
	def _get_auth_buff(self):
		return struct.pack('!BBB', 0x05, 0x01, 0x00)
	
	def _get_connect_buff(self):
		buff = struct.pack('!BBBBB%dsBB' % len(self.host), \
			0x05, 0x01, 0x00, 0x03, len(self.host), self.host, \
			self.port >> 8, self.port & 0xff)
		return buff
	
	def _get_request_buff(self):
		msg = self._get_sha1_auth()
		buff = struct.pack('!BBBBB%dsBB' % len(msg), \
			0x05, 0x01, 0x00, 0x03, len(msg), msg, 0, 0)
		return buff
	
	def read_connect(self):
		buff = self._recv()
		version, method = struct.unpack('!BB', buff)
		
		if version != 0x05 or method == 0xff:
			self.disconnect()
	
	def _get_sha1_auth(self):
		return sha.new("%s%s%s" % (self.sid, self.initiator, self.target)).hexdigest()
		
	def mainloop():
		pass

class Socks5Receiver(Socks5):
	def __init__(self, host, port, initiator, target, sid, file_props = None):
		self.queue_idx = -1
		self.queue = None
		self.receiving = False
		self.file_props = file_props
		Socks5.__init__(self, host, port, initiator, target, sid)
	
	def get_file_contents(self, timeout):
		''' read file contents from socket and write them to file "'''
		if self.receiving is True:
			return 
		else:
			self.receiving = True
		if self.file_props is None or \
			self.file_props.has_key('file-name') is False:
			return 
			#TODO error
		try: 
			buff = self._recv(512)
		except: 
			buff = ''
		
		fd = open(self.file_props['file-name'],'w')
		fd.write(buff)
		self.receiving = True
		while self.pending_data(timeout):
			try: 
				buff = self._recv(512)
			except: 
				buff=''
			fd.write(buff)
			if not buff: 
				break
		# TODO check if size is the same
		fd.close()
		self.disconnect()
		self.receiving = False
	
	def disconnect(self):
		""" Closes the socket. """
		try:
			fcntl.fcntl(self._sock, fcntl.F_SETFL, 0);
			self._sock.close()
		except:
			pass
		self.connected = False
		if self.queue is not None:
			self.queue.remove_receiver(self.queue_idx)


# TODO REMOVE above lines when ready