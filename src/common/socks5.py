
##	common/xmpp/socks5.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
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


import socket
import select
import os
import struct
import sha
import time

from errno import EWOULDBLOCK
from errno import ENOBUFS
from errno import EINTR

MAX_BUFF_LEN = 65536

class SocksQueue:
	''' queue for all file requests objects '''
	def __init__(self, complete_transfer_cb = None, progress_transfer_cb = None):
		self.connected = 0
		self.readers = {}
		self.files_props = {}
		self.senders = {}
		self.idx = 1
		self.listener = None
		self.sha_handlers = {}
		self.complete_transfer_cb = complete_transfer_cb
		self.progress_transfer_cb = progress_transfer_cb
		self.on_success = None
		self.on_failure = None
		
	def start_listener(self, host, port, sha_str, sha_handler, sid):
		self.sha_handlers[sha_str] = (sha_handler, sid)
		if self.listener == None:
			self.listener = Socks5Listener(host, port)
			self.listener.bind()
			if self.listener.started is False:
				self.listener = None
				import sys
				sys.stderr.write('\n\n\n========================================\
========================\nUnable to bind to port %s. \nMaybe you have another \
running instance of Gajim. \nFile Transfer will be canceled.\n==================\
==============================================\n\n\n' % port)
				return None
			self.connected += 1
		return self.listener
		
	def send_success_reply(self, file_props, streamhost):
		if file_props.has_key('streamhost-used') and \
			file_props['streamhost-used'] is True:
				if file_props.has_key('proxyhosts'):
					for proxy in file_props['proxyhosts']:
						if proxy == streamhost:
							self.on_success(streamhost)
							return 2
				return 0
		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if streamhost['state'] == 1:
					return 0
			streamhost['state'] = 1
			self.on_success(streamhost)
			return 1
		return 0

	def connect_to_hosts(self, account, sid, on_success = None, 
		on_failure = None):
		self.on_success = on_success
		self.on_failure = on_failure
		if not self.files_props.has_key(account):
			pass
			# FIXME ---- show error dialog
		else:
			file_props = self.files_props[account][sid]
		file_props['success_cb'] = on_success
		file_props['failure_cb'] = on_failure
		
		# add streamhosts to the queue 
		for streamhost in file_props['streamhosts']:
			receiver = Socks5Receiver(streamhost, sid, file_props)
			self.add_receiver(account, receiver)
			streamhost['idx'] = receiver.queue_idx
		
	def _socket_connected(self, streamhost, file_props):
		for host in file_props['streamhosts']:
			if host != streamhost and host.has_key('idx'):
				if host['state'] == 1:
					self.remove_receiver(streamhost['idx'])
					return
				else:
					host['state'] = -1
				self.remove_receiver(host['idx'])
		
	def _connection_refused(self, streamhost, file_props, idx):
		if file_props is None:
			return
		streamhost['state'] = -1
		self.remove_receiver(idx)
		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if host['state'] != -1:
					return
		if file_props.has_key('failure_cb') and file_props['failure_cb']:
			file_props['failure_cb'](streamhost['initiator'], streamhost['id'], 
				file_props['sid'], code = 404)
		
	def add_receiver(self, account, sock5_receiver):
		''' add new file request '''
		self.readers[self.idx] = sock5_receiver
		sock5_receiver.queue_idx = self.idx
		sock5_receiver.queue = self
		sock5_receiver.account = account
		self.idx += 1
		result = sock5_receiver.connect()
		self.connected += 1
		if result != None:
			result = sock5_receiver.main()
			self.process_result(result, sock5_receiver)
			return 1
		return None
		
	def get_file_from_sender(self, file_props, account):
		if file_props is None:
			return
			file_props['hash']
		if file_props.has_key('hash') and \
			self.senders.has_key(file_props['hash']):
			
			sender = self.senders[file_props['hash']]
			sender.account = account
			result = get_file_contents(0)
			self.process_result(result, sender)
			
	def result_sha(self, sha_str, idx):
		if self.sha_handlers.has_key(sha_str):
			props = self.sha_handlers[sha_str]
			props[0](props[1], idx)
	def activate_proxy(self, idx):
		if not self.readers.has_key(idx):
			return
		reader = self.readers[idx]
		if reader.file_props['type'] != 's':
			return
		if reader.state != 5:
			return
		reader.state = 6
		if reader.connected:
			reader.file_props['error'] = 0
			reader.file_props['disconnect_cb'] = reader.disconnect
			reader.file_props['started'] = True
			reader.file_props['completed'] = False
			reader.file_props['paused'] = False
			reader.file_props['stalled'] = False
			reader.file_props['elapsed-time'] = 0
			reader.file_props['last-time'] = time.time()
			reader.file_props['received-len'] = 0
			reader.pauses = 0
			result = reader.write_next()
			self.process_result(result, reader)
	
	def send_file(self, file_props, account):
		if file_props.has_key('hash') and \
			self.senders.has_key(file_props['hash']):
			sender = self.senders[file_props['hash']]
			file_props['streamhost-used'] = True
			sender.account = account
			if file_props['type'] == 's':
				sender.file_props = file_props 
				result = sender.send_file()
				self.process_result(result, sender)
			else:
				file_props['elapsed-time'] = 0
				file_props['last-time'] = time.time()
				file_props['received-len'] = 0
				sender.file_props = file_props
				
	def add_file_props(self, account, file_props):
		''' file_prop to the dict of current file_props.
		It is identified by account name and sid
		'''
		if file_props is None or \
			file_props.has_key('sid') is False:
			return
		_id = file_props['sid']
		if not self.files_props.has_key(account):
			self.files_props[account] = {}
		self.files_props[account][_id] = file_props
	
	def remove_file_props(self, account, sid):
		if self.files_props.has_key(account):
			fl_props = self.files_props[account]
			if fl_props.has_key(sid):
				del(fl_props[sid])
		
		if len(self.files_props) == 0:
			self.connected = 0
		
	def get_file_props(self, account, sid):
		''' get fil_prop by account name and session id '''
		if self.files_props.has_key(account):
			fl_props = self.files_props[account]
			if fl_props.has_key(sid):
				return fl_props[sid]
		return None

	def process(self, timeout=0):
		''' Process all registered connection.
		they can be receivers, senders and one listener 
		'''
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
					if sender.pending_data(timeout):
						result = sender.main()
						if sender.state == 4:
							self.result_sha(sender.sha_msg, idx)
						if result is None:
							continue
						if result == -1:
							sender.disconnect()
				elif sender.state == 5:
					if sender.file_props is not None and \
					sender.file_props['type'] == 'r':
						result = sender.get_file_contents(0)
						self.process_result(result, sender)
				elif sender.state == 7:
					while True:
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
						if result is None or result <= 0:
							break
				elif sender.state == 8:
					self.remove_sender(idx)
			else:
				self.remove_sender(idx)
		keys = self.readers.keys()
		for idx in keys:
			if not self.readers.has_key(idx):
				continue
			receiver = self.readers[idx]
			if receiver.state == 0:
				res = receiver.do_connect()
				continue
			if receiver.connected:
				if receiver.file_props['paused']:
					continue
				if receiver.state < 5:
					pd = receiver.pending_data(0)
					if pd:
						result = receiver.main(0)
						self.process_result(result, receiver)
				elif receiver.state == 5: # wait for proxy reply
					pass
				else:
					if receiver.file_props['type'] == 'r':
						result = receiver.get_file_contents(timeout)
					else:
						result = receiver.write_next()
					self.process_result(result, receiver)
			else:
				self.remove_receiver(idx)
		
	def process_result(self, result, actor):
		''' Take appropriate actions upon the result:
		[ 0, - 1 ] complete/end transfer
		[ > 0 ] send progress message
		[ None ] do nothing
		'''
		if result is None:
			return
		if result in (0, -1) and self.complete_transfer_cb is not None:
			account = actor.account
			self.complete_transfer_cb(account, actor.file_props)
		elif self.progress_transfer_cb is not None:
			self.progress_transfer_cb(actor.account, actor.file_props)
	
	def remove_receiver(self, idx, do_disconnect = True):
		''' Remove reciver from the list and decrease 
		the number of active connections with 1'''
		if idx != -1:
			if self.readers.has_key(idx):
				if do_disconnect:
					self.readers[idx].disconnect()
				else:
					if self.readers[idx].streamhost is not None:
						self.readers[idx].streamhost['state'] = -1
					del(self.readers[idx])
	
	def remove_sender(self, idx, do_disconnect = True):
		''' Remove sender from the list of senders and decrease the 
		number of active connections with 1'''
		if idx != -1:
			if self.senders.has_key(idx):
				if do_disconnect:
					self.senders[idx].disconnect()
					return
				else:
					del(self.senders[idx])
					if self.connected > 0:
						self.connected -= 1
			if len(self.senders) == 0 and self.listener is not None:
				self.listener.disconnect()
				self.listener = None
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
		self.pauses = 0
		self.size = 0
		self.remaining_buff = ''
		self.fd = None
		
	def open_file_for_reading(self):
		if self.fd == None:
			try:
				self.fd = open(self.file_props['file-name'],'rb')
				if self.file_props.has_key('offset') and self.file_props['offset']:
					self.size = self.file_props['offset']
					self.fd.seek(self.size)
					self.file_props['received-len'] = self.size
			except IOError, e:
				self.close_file()
				raise IOError, e
		
	def close_file(self):
		try:
			self.fd.close()
		except:
			pass
		
	def get_fd(self):
		''' Test if file is already open and return its fd,
		or just open the file and return the fd.
		'''
		if self.file_props.has_key('fd'):
			fd = self.file_props['fd']
		else:
			offset = 0
			opt = 'wb'
			if self.file_props.has_key('offset') and self.file_props['offset']:
				offset = self.file_props['offset']
				opt = 'ab'
			fd = open(self.file_props['file-name'], opt)
			self.file_props['fd'] = fd
			self.file_props['elapsed-time'] = 0
			self.file_props['last-time'] = time.time()
			self.file_props['received-len'] = offset
		return fd

	def rem_fd(self, fd):
		if self.file_props.has_key('fd'):
			del(self.file_props['fd'])
		try:
			fd.close()
		except:
			pass
			
		
	def receive(self):
		''' Reads small chunks of data. 
			Calls owner's disconnected() method if appropriate.'''
		if self.pending_read():
			received = ''
			try: 
				add = self._recv(64)
			except Exception, e: 
				add=''
			received +=add
			if len(add) == 0:
				self.disconnect()
		else:
			return None
		return add
	
	def send_raw(self,raw_data):
		''' Writes raw outgoing data. '''
		try:
			lenn = self._send(raw_data)
		except Exception, e:
			self.disconnect()
		return len(raw_data)
	
	def write_next(self):
		if self.remaining_buff != '':
			buff = self.remaining_buff
			self.remaining_buff = ''
		else:
			try:
				self.open_file_for_reading()
			except IOError, e:
				self.state = 8 # end connection
				self.disconnect()
				self.file_props['error'] = -7 # unable to read from file
				return -1
			buff = self.fd.read(MAX_BUFF_LEN)
		if len(buff) > 0:
			lenn = 0
			try:
				lenn = self._send(buff)
			except Exception, e:
				if e.args[0] not in (EINTR, ENOBUFS, EWOULDBLOCK):
					# peer stopped reading
					self.state = 8 # end connection
					self.close_file()
					self.disconnect()
					self.file_props['error'] = -1
					return -1
			self.size += lenn
			current_time = time.time()
			self.file_props['elapsed-time'] += current_time - \
				self.file_props['last-time']
			self.file_props['last-time'] = current_time
			self.file_props['received-len'] = self.size
			if self.size >= int(self.file_props['size']):
				self.state = 8 # end connection
				self.file_props['error'] = 0
				self.close_file()
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
			self.state = 7 # continue to write in the socket
			if lenn == 0 and self.file_props['stalled'] is False:
				return None
			return lenn
		else:
			self.state = 8 # end connection
			self.close_file()
			self.disconnect()
			return -1
	
	def get_file_contents(self, timeout):
		''' read file contents from socket and write them to file ''', \
			self.file_props['type'], self.file_props['sid']
		if self.file_props is None or \
			self.file_props.has_key('file-name') is False:
			self.file_props['error'] = -2
			return None
		fd = None
		if self.remaining_buff != '':
			fd = self.get_fd()
			fd.write(self.remaining_buff)
			lenn = len(self.remaining_buff)
			current_time = time.time()
			self.file_props['elapsed-time'] += current_time - \
				self.file_props['last-time']
			self.file_props['last-time'] = current_time
			self.file_props['received-len'] += lenn
			self.remaining_buff = ''
			if self.file_props['received-len'] == int(self.file_props['size']):
				self.rem_fd(fd)
				self.disconnect()
				self.file_props['error'] = 0
				self.file_props['completed'] = True
				return 0
		else:
			while self.pending_read(timeout):
				fd = self.get_fd()
				try: 
					buff = self._recv(MAX_BUFF_LEN)
				except Exception, e:
					buff = ''
				first_byte = False
				if self.file_props['received-len'] == 0:  
					if len(buff) > 0:  
						# delimiter between auth and data  
						if ord(buff[0]) == 0xD:  
							first_byte = True  
							buff = buff[1:]
				current_time = time.time()
				self.file_props['elapsed-time'] += current_time - \
					self.file_props['last-time']
				self.file_props['last-time'] = current_time
				self.file_props['received-len'] += len(buff)
				try:
					fd.write(buff)
				except IOError, e:
					self.rem_fd(fd)
					self.disconnect(False)
					self.file_props['error'] = -6 # file system error
					return 0
				if len(buff) == 0 and first_byte is False:
					# Transfer stopped  somehow:
					# reset, paused or network error
					self.rem_fd(fd)
					self.disconnect(False)
					self.file_props['error'] = -1
					return 0
				if self.file_props['received-len'] >= int(self.file_props['size']):
					# transfer completed
					self.rem_fd(fd)
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
	
	def disconnect(self, cb = True):
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
		try:
			ver, num_auth = struct.unpack('!BB', buff[:2])
			for i in xrange(num_auth):
				mechanism, = struct.unpack('!B', buff[1 + i])
				auth_mechanisms.append(mechanism)
		except:
			return None
		return auth_mechanisms
	def _get_auth_response(self):
		''' socks version(5), number of extra auth methods (we send
		0x00 - no auth
		) '''
		return struct.pack('!BB', 0x05, 0x00)
		
	def _get_connect_buff(self):
		''' Connect request by domain name '''
		buff = struct.pack('!BBBBB%dsBB' % len(self.host), 
			0x05, 0x01, 0x00, 0x03, len(self.host), self.host, 
			self.port >> 8, self.port & 0xff)
		return buff
	
	def _get_request_buff(self, msg, command = 0x01):
		''' Connect request by domain name, 
		sid sha, instead of domain name (jep 0096) '''
		buff = struct.pack('!BBBBB%dsBB' % len(msg), 
			0x05, command, 0x00, 0x03, len(msg), msg, 0, 0)
		return buff
		
	def _parse_request_buff(self, buff):
		try: # don't trust on what comes from the outside
			version, req_type, reserved, host_type,  = \
				struct.unpack('!BBBB', buff[:4])
			if host_type == 0x01:
				host_arr = struct.unpack('!iiii', buff[4:8])
				host, = reduce(lambda e1, e2: str(e1) + "." + str(e2), host_arr)
				host_len = len(host)
			elif host_type == 0x03:
				host_len,  = struct.unpack('!B' , buff[4])
				host, = struct.unpack('!%ds' % host_len, buff[5:5 + host_len])
			portlen = len(buff[host_len + 5:])
			if portlen == 1: 
				port, = struct.unpack('!B', buff[host_len + 5])
			elif portlen == 2: 
				port, = struct.unpack('!H', buff[host_len + 5:])
			# file data, comes with auth message (Gaim bug)
			else: 
				port, = struct.unpack('!H', buff[host_len + 5: host_len + 7])
				self.remaining_buff = buff[host_len + 7:]
		except:
			return (None, None, None)
		return (req_type, host, port)
		
	def read_connect(self):
		''' connect responce: version, auth method '''
		buff = self._recv()
		try:
			version, method = struct.unpack('!BB', buff)
		except:
			version, method = None, None
		if version != 0x05 or method == 0xff:
			self.disconnect()
		
	def _get_sha1_auth(self):
		''' get sha of sid + Initiator jid + Target jid '''
		if self.file_props.has_key('is_a_proxy'):
			del(self.file_props['is_a_proxy'])
			return sha.new('%s%s%s' % (self.sid, self.file_props['proxy_sender'], 
				self.file_props['proxy_receiver'])).hexdigest()
		return sha.new('%s%s%s' % (self.sid, self.initiator, self.target)).hexdigest()

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
		
	def send_file(self):
		''' start sending the file over verified connection ''' 
		self.file_props['error'] = 0
		self.file_props['disconnect_cb'] = self.disconnect
		self.file_props['started'] = True
		self.file_props['completed'] = False
		self.file_props['paused'] = False
		self.file_props['stalled'] = False
		self.file_props['connected'] = True
		self.file_props['elapsed-time'] = 0
		self.file_props['last-time'] = time.time()
		self.file_props['received-len'] = 0
		self.pauses = 0
		self.state = 7
		return self.write_next() # initial for nl byte
		
	def main(self):
		''' initial requests for verifying the connection '''
		if self.state == 1: # initial read
			buff = self.receive()
			if not self.connected:
				return -1
			mechs = self._parse_auth_buff(buff)
			if mechs is None:
				return -1 # invalid auth methods received
		elif self.state == 2: # send reply with desired auth type
			self.send_raw(self._get_auth_response())
		elif self.state == 3: # get next request
			buff = self.receive()
			(req_type, self.sha_msg, port) = self._parse_request_buff(buff)
			if req_type != 0x01:
				return -1 # request is not of type 'connect'
		elif self.state == 4: # send positive response to the 'connect'
			self.send_raw(self._get_request_buff(self.sha_msg, 0x00))
		self.state += 1 # go to the next step
		return None
			
	def pending_data(self,timeout=0):
		''' return true if there is a data ready to be read '''
		if self._sock is None:
			return False
		try:
			if self.state in (1, 3, 5):  # (initial, request, send file)
				return self.pending_read(timeout)
			elif self.state in (2, 4): # send auth and positive response
				return True
		except Exception, e:
			return False
		return False
		
	def disconnect(self, cb = True):
		''' Closes the socket. '''
		# close connection and remove us from the queue
		try:
			self._sock.close()
		except:
			pass
		self.connected = False
		if self.file_props is not None:
			self.file_props['connected'] = False
			self.file_props['disconnect_cb'] = None
		if self.queue is not None:
			self.queue.remove_sender(self.queue_idx, False)

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
			self._serv.setblocking(False)
		except Exception, e:
			# unable to bind, show error dialog
			return None
		self.started = True
	
	def disconnect(self):
		try:
			self._serv.close()
		except:
			pass
	
	def accept_conn(self):
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
			return False

class Socks5Receiver(Socks5):
	def __init__(self, streamhost, sid, file_props = None):
		self.queue_idx = -1
		self.streamhost = streamhost
		self.queue = None
		self.file_props = file_props
		self.connect_timeout = 0
		self.connected = False
		self.pauses = 0
		if not self.file_props:
			self.file_props = {}
		self.file_props['disconnect_cb'] = self.disconnect
		self.file_props['error'] = 0
		self.file_props['started'] = True
		self.file_props['completed'] = False
		self.file_props['paused'] = False
		self.file_props['stalled'] = False
		Socks5.__init__(self, streamhost['host'], int(streamhost['port']), 
			streamhost['initiator'], streamhost['target'], sid)
	
	def connect(self):
		''' create the socket and start the connect loop '''
		self._sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.settimeout(50)
		# this will not block the GUI
		self._sock.setblocking(False)
		self.state = 0 # about to be connected
		res = self.do_connect()
		return res
		
	def do_connect(self):
		try:
			self._sock.connect((self.host, self.port))
			self._sock.setblocking(False)
			self._send=self._sock.send
			self._recv=self._sock.recv
		except Exception, ee:
			(errnum, errstr) = ee
			self.connect_timeout += 1
			if errnum == 111 or self.connect_timeout > 1000:
				self.queue._connection_refused(self.streamhost, 
					self.file_props, self.queue_idx)
				return None
			# win32 needs this
			elif errnum != 10056 or self.state != 0:
				return None
			else: # socket is already connected
				self._sock.setblocking(False)
				self._send=self._sock.send
				self._recv=self._sock.recv
				pass
		self.buff = ''
		self.connected = True
		self.file_props['connected'] = True
		self.file_props['disconnect_cb'] = self.disconnect
		self.state = 1 # connected
		self.queue._socket_connected(self.streamhost, self.file_props)
		return 1 # we are connected
		
	def main(self, timeout = 0):
		''' begin negotiation. on success 'address' != 0 '''
		result = 1
		if self.state == 1: # send initially: version and auth types
			self.send_raw(self._get_auth_buff())
		elif self.state == 2: # read auth response
			buff = self.receive()
			if buff is None or len(buff) != 2:
				return None
			version, method = struct.unpack('!BB', buff[:2])
			if version != 0x05 or method == 0xff:
				self.disconnect()
		elif self.state == 3: # send 'connect' request
			self.send_raw(self._get_request_buff(self._get_sha1_auth()))
		elif self.state == 4: # get approve of our request
			buff = self.receive()
			if buff == None:
				return None
			sub_buff = buff[:4]
			if len(sub_buff) < 4:
				return None
			version, command, rsvd, address_type = struct.unpack('!BBBB', buff[:4])
			addrlen, address, port = 0, 0, 0
			if address_type == 0x03:
				addrlen = ord(buff[4])
				address = struct.unpack('!%ds' % addrlen, buff[5:addrlen + 5])
				portlen = len(buff[addrlen + 5:])
				if portlen == 1: 
					port, = struct.unpack('!B', buff[addrlen + 5])
				elif portlen == 2:
					port, = struct.unpack('!H', buff[addrlen + 5:])
				else: # Gaim bug :)
					port, = struct.unpack('!H', buff[addrlen + 5:addrlen + 7])
					self.remaining_buff = buff[addrlen + 7:]
			self.state = 5 # for senders: init file_props and send '\n'
			if self.queue.on_success:
				result = self.queue.send_success_reply(self.file_props, 
					self.streamhost)
				if result == 0:
					self.state = 8
					self.disconnect()
		
		# for senders: init file_props and send '\n'
		if result == 1 and self.state == 5: 
			if self.file_props['type'] == 's':
				self.file_props['error'] = 0
				self.file_props['disconnect_cb'] = self.disconnect
				self.file_props['started'] = True
				self.file_props['completed'] = False
				self.file_props['paused'] = False
				self.file_props['stalled'] = False
				self.file_props['elapsed-time'] = 0
				self.file_props['last-time'] = time.time()
				self.file_props['received-len'] = 0
				self.pauses = 0
			self.state = 6 # send/get file contents
		if self.state < 5:
			self.state += 1
			return None
		# we have set up the connection, next - retrieve file
	
	def pending_data(self, timeout=0):
		''' Returns true if there is a data ready to be read. '''
		if self._sock is None:
			return False
		try:
			if self.state in (2, 4, 6): # auth response, connect, file data
				return self.pending_read(0)
			elif self.state in (1, 3, 5): # auth types, connect request
				return True
		except Exception, e:
			return False
		return False
		
	def disconnect(self, cb = True):
		''' Closes the socket. '''
		# close connection and remove us from the queue
		if self._sock:
			try:
				self._sock.close()
			except:
				pass
		self.connected = False
		if cb is True:
			self.file_props['disconnect_cb'] = None
		if self.queue is not None:
			self.queue.remove_receiver(self.queue_idx, False)
