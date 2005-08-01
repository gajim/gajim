##	common/xmpp/socks5.py
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
try:
	import fcntl
except:
	pass
import struct
import sha

class SocksQueue:
	''' queue for all file requests objects '''
	def __init__(self, complete_transfer_cb = None, \
		progress_transfer_cb = None):
		self.connected = 0
		self.readers = {}
		self.files_props = {}
		self.idx = 0
		self.complete_transfer_cb = complete_transfer_cb
		self.progress_transfer_cb = progress_transfer_cb
		
	def start_listener(self):
		Socks5Sender()
	
	def add_receiver(self, account, sock5_receiver):
		''' add new file request '''
		self.readers[self.idx] = sock5_receiver
		sock5_receiver.queue_idx = self.idx
		sock5_receiver.queue = self
		sock5_receiver.account = account
		self.idx += 1
		result = sock5_receiver.connect()
		self.connected += 1
		# we don;t need blocking sockets anymore
		# this unblocks ui! 
		sock5_receiver._sock.setblocking(False)
		return result
	
	def add_file_props(self, account, file_props):
		if file_props is None or \
			file_props.has_key('sid') is False:
			return
		id = file_props['sid']
		if not self.files_props.has_key(account):
			self.files_props[account] = {}
		self.files_props[account][id] = file_props
		
	def get_file_props(self, account, id):
		if self.files_props.has_key(account):
			fl_props = self.files_props[account]
		if fl_props.has_key(id):
			return fl_props[id]
		return None

	def process(self, timeout=0):
		''' process all file requests '''
		for idx in self.readers.keys():
			receiver = self.readers[idx]
			if receiver.connected:
				if receiver.file_props['paused']:
					continue
				if receiver.pending_data():
					result = receiver.get_file_contents(timeout)
					if result in [0, -1] and \
						self.complete_transfer_cb is not None:
						self.complete_transfer_cb(receiver.account, 
							receiver.file_props)
					
					elif self.progress_transfer_cb is not None:
						self.progress_transfer_cb(receiver.account, 
							receiver.file_props)
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
		self.account = None
	
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
		''' Writes raw outgoing data. Blocks until done.
			If supplied data is unicode string, encodes it to utf-8 before send.'''
		try:
			self._send(raw_data)
		except:
			self.disconnect()
		pass
			
	def disconnect(self):
		''' Closes the socket. '''
		if 'fcntl' in globals():
			fcntl.fcntl(self._sock, fcntl.F_SETFL, 0);
		self._sock.close()
		self.connected = False
		
	def pending_data(self,timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._sock is None:
			return False
		try:
			return select.select([self._sock],[],[],timeout)[0]
		except:
			return False
			
	def pending_connection(self,timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._sock is None:
			return False
		try:
			return select.select([],[self._sock],[],timeout)[0]
		except:
			return False
	
	def send_connect(self):
		''' begin negotiation. on success 'address' != 0 '''
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
			address = struct.unpack('!%ds' % addrlen, buff[5:addrlen+5])
			
			portlen = len(buff[addrlen+5])
			if portlen == 1: # Gaim bug :)
				(port) = struct.unpack('!B', buff[addrlen+5])
			else: 
				(port) = struct.unpack('!H', buff[addrlen+5])
			
		return (version, command, rsvd, address_type, addrlen, address, port)
		
		
	def _get_auth_buff(self):
		''' Message, that we support 1 one auth mechanism: 
		the 'no auth' mechanism. '''
		return struct.pack('!BBB', 0x05, 0x01, 0x00)
	
	def _get_connect_buff(self):
		''' Connect request by domain name '''
		buff = struct.pack('!BBBBB%dsBB' % len(self.host), \
			0x05, 0x01, 0x00, 0x03, len(self.host), self.host, \
			self.port >> 8, self.port & 0xff)
		return buff
	
	def _get_request_buff(self):
		''' Connect request by domain name, 
		sid sha, instead of domain name (jep 0096) '''
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

class Socks5Listener:
	def __init__(self, host, port):
		self.host, self.port
		self.queue_idx = -1	
		self.queue = None
		
		def bind(self):
			self._serv=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
			self._serv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
			self._serv.bind((self.host, self.port))
			self._serv.listen(socket.SOMAXCONN)
			self.connected = False
		
class Socks5Receiver(Socks5):
	def __init__(self, host, port, initiator, target, sid, file_props = None):
		self.queue_idx = -1
		self.queue = None
		self.file_props = file_props
		if file_props:
			file_props['disconnect_cb'] = self.disconnect
			file_props['error'] = 0
			self.file_props['completed'] = False
			self.file_props['paused'] = False
		Socks5.__init__(self, host, port, initiator, target, sid)
	
	def get_file_contents(self, timeout):
		''' read file contents from socket and write them to file "'''
		if self.file_props is None or \
			self.file_props.has_key('file-name') is False:
			return 
			#TODO error
		while self.pending_data(timeout):
			if self.file_props.has_key('fd'):
				fd = self.file_props['fd']
			else:
				fd = open(self.file_props['file-name'],'w')
				self.file_props['fd'] = fd
				self.file_props['received-len'] = 0
			try: 
				buff = self._recv(65536)
			except: 
				buff = ''
			self.file_props['received-len'] += len(buff)
			fd.write(buff)
			if len(buff) == 0:
				# Transfer stopped  somehow:
				# reset, paused or network error
				fd.close()
				try:
					# file is not complete, remove it
					os.remove(self.file_props['file-name'])
				except:
					# unable to remove the incomplete file
					pass
				self.disconnect()
				self.file_props['error'] = -1
				return -1
			
			if self.file_props['received-len'] == int(self.file_props['size']):
				# transfer completed
				fd.close()
				self.disconnect()
				self.file_props['error'] = 0
				self.file_props['completed'] = True
				return 0
		# return number of read bytes. It can be used in progressbar
		return self.file_props['received-len']
		
	def disconnect(self):
		''' Closes the socket. '''
		# close connection and remove us from the queue
		if 'fcntl' in globals():
			fcntl.fcntl(self._sock, fcntl.F_SETFL, 0);
		self._sock.close()
		self.connected = False
		self.file_props['disconnect_cb'] = None
		if self.queue is not None:
			self.queue.remove_receiver(self.queue_idx)

