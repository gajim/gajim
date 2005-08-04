##	common/xmpp/socks5.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
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
import os
try:
	import fcntl
except:
	pass
import struct
import sha

MAX_BUFF_LEN = 65536

class SocksQueue:
	''' queue for all file requests objects '''
	def __init__(self, complete_transfer_cb = None, \
		progress_transfer_cb = None):
		self.connected = 0
		self.readers = {}
		self.files_props = {}
		self.senders = {}
		self.idx = 0
		self.listener = None
		self.sha_handlers = {}
		self.complete_transfer_cb = complete_transfer_cb
		self.progress_transfer_cb = progress_transfer_cb
		
	def start_listener(self, host, port, sha_str, sha_handler, sid):
		self.sha_handlers[sha_str] = (sha_handler, sid)
		if self.listener == None:
			self.listener = Socks5Listener(host, port)
			self.listener.bind()
			if self.listener.started is False:
				return None
			self.connected += 1
		return self.listener
	
	def result_sha(self, sha_str, idx):
		if self.sha_handlers.has_key(sha_str):
			props = self.sha_handlers[sha_str]
			props[0](props[1], idx)
			
	def send_file(self, file_props, account):
		if self.senders.has_key(file_props['hash']):
			sender = self.senders[file_props['hash']]
			sender.account = account
			result = sender.send_file(file_props)
			self.process_result(result, sender)
	
	def add_receiver(self, account, sock5_receiver, auth_cb, auth_param):
		''' add new file request '''
		self.readers[self.idx] = sock5_receiver
		sock5_receiver.queue_idx = self.idx
		sock5_receiver.queue = self
		sock5_receiver.account = account
		sock5_receiver.auth_cb = auth_cb
		sock5_receiver.auth_param = auth_param
		self.idx += 1
		result = sock5_receiver.connect()
		if result != None:
			sock5_receiver._sock.setblocking(False)
			result = sock5_receiver.main()
			self.process_result(result, sock5_receiver)
			self.connected += 1
			return 1
		# we don't need blocking sockets anymore
		# this unblocks ui! 
		
		return None
	
	def add_file_props(self, account, file_props):
		if file_props is None or \
			file_props.has_key('sid') is False:
			return
		id = file_props['sid']
		if not self.files_props.has_key(account):
			self.files_props[account] = {}
		self.files_props[account][id] = file_props
	def get_file_props(self, account, sid):
		if self.files_props.has_key(account):
			fl_props = self.files_props[account]
			if fl_props.has_key(sid):
				return fl_props[sid]
		return None

	def process(self, timeout=0):
		''' process all file requests '''
		if self.listener is not None:
			if self.listener.pending_connection():
				_sock = self.listener.accept_conn()
				sock_hash =  _sock.__hash__()
				if not self.senders.has_key(sock_hash):
					self.senders[sock_hash] = Socks5Sender(sock_hash, self, 
						_sock[0], _sock[1][0], 	_sock[1][1])
					self.connected += 1
					
		for idx in self.senders.keys():
			sender = self.senders[idx]
			if sender.connected:
				
				if sender.state < 5:
					if sender.pending_data():
						result = sender.main()
						if sender.state == 4:
							self.result_sha(sender.sha_msg, idx)
						if result is None:
							continue
						if result == -1:
							sender.disconnect()
				elif sender.state == 7:
					for i in range(10):
						if sender.file_props['paused']:
							break
						if not sender.connected:
							self.process_result(-1, sender)
							break
						if sender.state == 8:
							self.remove_sender(idx)
							break
						result = sender.write_next()
						self.process_result(result, sender)
				elif sender.state == 8:
					self.remove_sender(idx)
			else:
				self.remove_sender(idx)
		for idx in self.readers.keys():
			receiver = self.readers[idx]
			if receiver.connected:
				if receiver.file_props['paused']:
					continue
				if receiver.state == 5:
					result = receiver.get_file_contents(timeout)
					self.process_result(result, receiver)
				else:
					pd = receiver.pending_data()
					if pd:
						result = receiver.main(timeout)
						self.process_result(result, receiver)
			else:
				self.remove_receiver(idx)
		
	def process_result(self, result, actor):
		if result is None:
			return
		if result in [0, -1] and \
			self.complete_transfer_cb is not None:
			self.complete_transfer_cb(actor.account, 
				actor.file_props)
		elif self.progress_transfer_cb is not None:
			self.progress_transfer_cb(actor.account, 
				actor.file_props)
	
	def remove_receiver(self, idx):
		if idx != -1:
			if self.readers.has_key(idx):
				del(self.readers[idx])
			if self.connected > 0:
				self.connected -= 1
	def remove_sender(self, idx):
		if idx != -1:
			if self.senders.has_key(idx):
				del(self.senders[idx])
			if self.connected > 0:
				self.connected -= 1
	
class Socks5:
	def __init__(self, host, port, initiator, target, sid):
		if host is not None:
			self.host = socket.gethostbyname(host)
		self.port = port
		self.initiator = initiator
		self.target = target
		self.sid = sid
		self._sock = None
		self.account = None
		self.state = 0 # not connected
	
	def connect(self):
		self._sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self._sock.connect((self.host, self.port))
			self._sock.setblocking(False)
			self._send=self._sock.send
			self._recv=self._sock.recv
		except Exception, e:
			return None
		self.buff = ''
		self.connected = True
		self.state = 1 # connected
		return 1
	
	def receive(self):
		''' Reads small pending incoming data. 
			Calls owner's disconnected() method if appropriate.'''
		
		if self.pending_read():
			received = ''
			while self.pending_read():
				try: 
					add = self._recv(64)
				except Exception, e: 
					add=''
				received +=add
				if not add: 
					break
			if len(received) == 0:
				self.disconnect()
		else:
			return None
		return received
		


	def send_raw(self,raw_data):
		''' Writes raw outgoing data. Blocks until done.
			If supplied data is unicode string, encodes it to utf-8 before send.'''
		try:
			lenn = self._send(raw_data)
		except Exception, e:
			self.disconnect()
		return len(raw_data)
			
	def disconnect(self):
		''' Closes the socket. '''
		self._sock.close()
		self.connected = False
		
	def pending_read(self,timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._sock is None:
			return False
		try:
			return select.select([self._sock],[],[],timeout)[0]
		except Exception, e:
			return False
		
	def pending_write(self,timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._sock is None:
			return False
		try:
			return select.select([],[self._sock],[],timeout)[0]
		except Exception, e:
			return False
			
	def pending_connection(self,timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._sock is None:
			return False
		try:
			return select.select([],[self._sock],[],timeout)[0]
		except Exception, e:
			return False
	
	def _get_auth_buff(self):
		''' Message, that we support 1 one auth mechanism: 
		the 'no auth' mechanism. '''
		return struct.pack('!BBB', 0x05, 0x01, 0x00)
		
	def _parse_auth_buff(self, buff):
		''' Parse the initial message and create a list of auth
		mechanisms '''
		auth_mechanisms = []
		ver, num_auth = struct.unpack('!BB', buff[:2])
		for i in range(num_auth):
			mechanism, = struct.unpack('!B', buff[1 + i])
			auth_mechanisms.append(mechanism)
		return auth_mechanisms
	def _get_auth_response(self):
		return struct.pack('!BB', 0x05, 0x00)
		
	def _get_connect_buff(self):
		''' Connect request by domain name '''
		buff = struct.pack('!BBBBB%dsBB' % len(self.host), \
			0x05, 0x01, 0x00, 0x03, len(self.host), self.host, \
			self.port >> 8, self.port & 0xff)
		return buff
	
	def _get_request_buff(self, msg, command = 0x01):
		''' Connect request by domain name, 
		sid sha, instead of domain name (jep 0096) '''
		buff = struct.pack('!BBBBB%dsBB' % len(msg), \
			0x05, command, 0x00, 0x03, len(msg), msg, 0, 0)
		return buff
		
	def _parse_request_buff(self, buff):
		version, req_type, reserved, host_type,  = \
			struct.unpack('!BBBB', buff[:4])
		if host_type == 0x01:
			host_arr = struct.unpack('!iiii', buff[4:8])
			host, = reduce(lambda e1, e2: str(e1) + "." + str(e2), host_arr)
			host_len = len(host)
		elif host_type == 0x03:
			host_len,  = struct.unpack('!B' , buff[4])
			host, = struct.unpack('!%ds' % host_len, buff[5:5 + host_len])
		portlen = len(buff[host_len + 5])
		if portlen == 1: # Gaim bug :)
			port, = struct.unpack('!B', buff[host_len + 5])
		else: 
			port, = struct.unpack('!H', buff[host_len + 5])
		return (req_type, host, port)
			
		
	def read_connect(self):
		buff = self._recv()
		version, method = struct.unpack('!BB', buff)
		
		if version != 0x05 or method == 0xff:
			self.disconnect()
	
	def _get_sha1_auth(self):
		return sha.new("%s%s%s" % (self.sid, self.initiator, self.target)).hexdigest()

class Socks5Sender(Socks5):
	''' class for sending file to socket over socks5 '''
	def __init__(self, sock_hash, parent, _sock, host = None, port = None):
		self.queue_idx = sock_hash
		self.queue = parent
		Socks5.__init__(self, host, port, None, None, None)
		self._sock = _sock
		self._sock.setblocking(False)
		self._recv = _sock.recv
		self._send = _sock.send
		self.connected = True
		self.state = 1 # waiting for first bytes
		self.file_props = None
		self.remaining_buff = ''
		
	def write_next(self):
		if self.remaining_buff != '':
			buff = self.remaining_buff
			self.remaining_buff = ''
		else:
			buff = self.fd.read(MAX_BUFF_LEN)
		if len(buff) > 0:
			lenn = 0
			try:
				lenn = self._send(buff)
			except Exception, e:
				if e.args[0] != 11:
					self.state = 8
					self.fd.close()
					self.disconnect()
					self.file_props['error'] = -1
					return -1
			self.size += lenn
			self.file_props['received-len'] = self.size
			if self.size == int(self.file_props['size']):
				self.state = 8
				self.file_props['error'] = 0
				self.fd.close()
				self.disconnect()
				return -1
			if lenn != len(buff):
				self.remaining_buff = buff[lenn:]
			else:
				self.remaining_buff = ''
			if lenn == 0:
				self.pauses +=1
			else:
				self.pauses = 0
			if self.pauses > 24:
				self.file_props['stalled'] = True
			else:
				self.file_props['stalled'] = False
			self.state = 7
			if lenn == 0 and self.file_props['stalled'] is False:
				return None
			return lenn
		else:
			self.state = 8
			self.disconnect()
			return -1
		
	def send_file(self, file_props):
		self.fd = open(file_props['file-name'])
		file_props['error'] = 0
		file_props['disconnect_cb'] = self.disconnect
		file_props['started'] = True
		file_props['completed'] = False
		file_props['paused'] = False
		file_props['stalled'] = False
		file_props['received-len'] = 0
		
		self.pauses = 0
		self.file_props = file_props
		self.size = 0
		return self.write_next()
		
	def main(self):
		if self.state == 1:
			buff = self.receive()
			if not self.connected:
				return -1
			mechs = self._parse_auth_buff(buff)
		elif self.state == 2:
			self.send_raw(self._get_auth_response())
		elif self.state == 3:
			buff = self.receive()
			(req_type, self.sha_msg, port) = self._parse_request_buff(buff)
		elif self.state == 4:
			self.send_raw(self._get_request_buff(self.sha_msg, 0x00))
		self.state += 1
		return None
			
	def pending_data(self,timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._sock is None:
			return False
		try:
			if self.state in [1, 3]:
				return self.pending_read()
			elif self.state in [2, 4, 5]:
				return True
		except Exception, e:
			return False
		return False
		
	def disconnect(self):
		''' Closes the socket. '''
		# close connection and remove us from the queue
		self._sock.close()
		self.connected = False
		if self.file_props is not None:
			self.file_props['disconnect_cb'] = None
		if self.queue is not None:
			self.queue.remove_sender(self.queue_idx)

	
class Socks5Listener:
	def __init__(self, host, port):
		self.host, self.port = host, port
		self.queue_idx = -1	
		self.queue = None
		self.started = False
		self._sock = None
		
	def bind(self):
		try:
			self._serv=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
			self._serv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
			self._serv.bind(('0.0.0.0', self.port))
			self._serv.listen(socket.SOMAXCONN)
		except Exception, (errno, errstr):
			return None
		self._serv.setblocking(False)
		self.started = True
	
	def accept_conn(self):
		self._serv.accept.__doc__
		_sock  = self._serv.accept()
		_sock[0].setblocking(False)
		return _sock
	
	def pending_connection(self,timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._serv is None:
			return False
		try:
			res = select.select([self._serv],[],[],timeout)
			return res[0]
		except Exception, e:
			self.file_props['started'] = True
			return False

class Socks5Receiver(Socks5):
	def __init__(self, host, port, initiator, target, sid, file_props = None):
		self.queue_idx = -1
		self.queue = None
		self.file_props = file_props
		self.file_props['started'] = True
		self.connected = False
		self.pauses = 0
		if file_props:
			file_props['disconnect_cb'] = self.disconnect
			file_props['error'] = 0
			self.file_props['started'] = True
			self.file_props['completed'] = False
			self.file_props['paused'] = False
			self.file_props['stalled'] = False
			self.file_props['started'] = True
		Socks5.__init__(self, host, port, initiator, target, sid)
	
	
	def main(self, timeout = 0):
		''' begin negotiation. on success 'address' != 0 '''
		if self.state == 1:
			self.send_raw(self._get_auth_buff())
		elif self.state == 2:
			buff = self.receive()
			if buff is None or len(buff) != 2:
				return None
			version, method = struct.unpack('!BB', buff[:2])
			if version != 0x05 or method == 0xff:
				self.disconnect()
		elif self.state == 3:
			self.send_raw(self._get_request_buff(self._get_sha1_auth()))
		elif self.state == 4:
			buff = self.receive()
			if buff == None:
				return None
			version, command, rsvd, address_type = struct.unpack('!BBBB', buff[:4])
			addrlen, address, port = 0, 0, 0
			if address_type == 0x03:
				addrlen = ord(buff[4])
				address = struct.unpack('!%ds' % addrlen, buff[5:addrlen + 5])
				portlen = len(buff[addrlen + 5])
				if portlen == 1: # Gaim bug :)
					port, = struct.unpack('!B', buff[addrlen + 5])
				else:
					port, = struct.unpack('!H', buff[addrlen + 5])
			self.state = 5
			self.auth_cb(self.auth_param)
			return None
		if self.state < 5:
			self.state += 1
			return None
		# we have set the connection, retrieve file
		
		return self.get_file_contents(timeout)
	
	
	def pending_data(self, timeout=0):
		''' Returns true if there is a data ready to be read. ''', self.state
		if self._sock is None:
			return False
		try:
			if self.state in [2, 4]:
				return self.pending_read()
			elif self.state in [1, 3, 5]:
				return True
		except Exception, e:
			return False
		return False
		
	def get_file_contents(self, timeout):
		''' read file contents from socket and write them to file '''
		if self.file_props is None or \
			self.file_props.has_key('file-name') is False:
			self.file_props['error'] = -2
			return None
		fd = None
		while self.pending_read(timeout):
			if self.file_props.has_key('fd'):
				fd = self.file_props['fd']
			else:
				fd = open(self.file_props['file-name'],'w')
				self.file_props['fd'] = fd
				self.file_props['received-len'] = 0
			try: 
				buff = self._recv(MAX_BUFF_LEN)
			except Exception, e:
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
				except Exception, e:
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
		if fd == None:
			self.pauses +=1
		else:
			self.pauses = 0
		if self.pauses > 24:
			self.file_props['stalled'] = True
		else:
			self.file_props['stalled'] = False
		if fd == None and self.file_props['stalled'] is False:
			return None
		if self.file_props.has_key('received-len'):
			if self.file_props['received-len'] != 0:
				return self.file_props['received-len']
		return None
		
	def disconnect(self):
		''' Closes the socket. '''
		# close connection and remove us from the queue
		self._sock.close()
		self.connected = False
		self.file_props['disconnect_cb'] = None
		if self.queue is not None:
			self.queue.remove_receiver(self.queue_idx)

