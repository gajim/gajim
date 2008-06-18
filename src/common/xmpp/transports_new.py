from idlequeue import IdleObject
from client import PlugIn
import threading, socket, errno

import logging
log = logging.getLogger('gajim.c.x.transports_nb')
consoleloghandler = logging.StreamHandler()
consoleloghandler.setLevel(logging.DEBUG)
consoleloghandler.setFormatter(
	logging.Formatter('%(levelname)s: %(message)s')
)
log.setLevel(logging.DEBUG)
log.addHandler(consoleloghandler)
log.propagate = False

'''
this module will replace transports_nb.py
For now, it can be run from test/test_nonblockingtcp.py
* set credentials in the testing script
'''


class NBgetaddrinfo(threading.Thread):
	'''
	Class for nonblocking call of getaddrinfo. Maybe unnecessary.
	'''
	def __init__(self, server,  on_success, on_failure, timeout_sec):
		'''
		Call is started from constructor. It is not needed to hold reference on
		created instance.
		:param server: tuple (hostname, port) for DNS request
		:param on_success: callback for successful DNS request
		:param on_failure: called when DNS request couldn't be performed
		:param timeout_sec: max seconds to wait for return from getaddrinfo. After
			this time, on_failure is called with error message.
		'''
		threading.Thread.__init__(self)
		self.on_success = on_success
		self.on_failure = on_failure
		self.server = server
		self.lock = threading.Lock()
		self.already_called = False
		self.timer = threading.Timer(timeout_sec, self.on_timeout)
		self.timer.start()
		self.start()
	
	def on_timeout(self):
		'''
		Called by timer. Means that getaddrinfo takes too long and will be
		interrupted.
		'''
		self.do_call(False, 'NBgetaddrinfo timeout while looking up %s:%s' % self.server)

	def do_call(self, success, data):
		'''
		Method called either on success and failure. In case of timeout it will be
		called twice but only the first (failure) call will be performed.
		:param success: True if getaddrinfo returned properly, False if there was an
		error or on timeout.
		:param data: error message if failure, list of address structures if success
		'''
		log.debug('NBgetaddrinfo::do_call(): %s' % repr(data))
		self.timer.cancel()
		self.lock.acquire()
		if not self.already_called:
			self.already_called = True
			self.lock.release()
			if success:
				self.on_success(data)
			else: 
				self.on_failure(data)
			return
		else: 
			self.lock.release()
			return

	def run(self):
		try:
			ips = socket.getaddrinfo(self.server[0],self.server[1],socket.AF_UNSPEC,
				socket.SOCK_STREAM)
		except socket.gaierror, e:
			self.do_call(False, 'Lookup failure for %s: %s %s' % 
				 (repr(self.server), e[0], e[1]))
		except Exception, e: 
			self.do_call(False, 'Exception while DNS lookup of %s: %s' %
				(repr(e), repr(self.server)))
		else:
			self.do_call(True, ips)
					


DISCONNECTED ='DISCONNECTED' 	
CONNECTING ='CONNECTING'  
CONNECTED ='CONNECTED' 
DISCONNECTING ='DISCONNECTING' 

CONNECT_TIMEOUT_SECONDS = 5 
'''timeout to connect to the server socket, it doesn't include auth'''

DISCONNECT_TIMEOUT_SECONDS = 10
'''how long to wait for a disconnect to complete'''

class NonBlockingTcp(PlugIn, IdleObject):
	def __init__(self, on_xmpp_connect=None, on_xmpp_failure=None):
		'''
		Class constructor. All parameters can be reset in tcp_connect or xmpp_connect
		calls.

		'''
		PlugIn.__init__(self)
		IdleObject.__init__(self)
		self.on_tcp_connect = None
		self.on_tcp_failure = None
		self.sock = None
		self.idlequeue = None
		self.DBG_LINE='socket'
		self.state = DISCONNECTED
		'''
		CONNECTING - after non-blocking socket.connect() until TCP connection is estabilished
		CONNECTED - after TCP connection is estabilished
		DISCONNECTING - 
		DISCONNECTED
		'''
		self._exported_methods=[self.send, self.disconnect, self.onreceive, self.set_send_timeout, 
			self.start_disconnect, self.set_timeout, self.remove_timeout]


	def connect(self, conn_5tuple, on_tcp_connect, on_tcp_failure, idlequeue):
		'''
		Creates and connects socket to server and port defined in conn_5tupe which
		should be list item returned from getaddrinfo.
		:param conn_5tuple: 5-tuple returned from getaddrinfo
		:param on_tcp_connect: callback called on successful tcp connection
		:param on_tcp_failure: callback called on failure when estabilishing tcp 
			connection
		:param idlequeue: idlequeue for socket
		'''
		self.on_tcp_connect = on_tcp_connect
		self.on_tcp_failure = on_tcp_failure
		self.conn_5tuple = conn_5tuple
		try:
			self.sock = socket.socket(*conn_5tuple[:3])
		except socket.error, (errnum, errstr):
			on_tcp_failure('NonBlockingTcp: Error while creating socket: %s %s' % (errnum, errstr))
			return

		self.idlequeue = idlequeue
		self.fd = self.sock.fileno()
		self.idlequeue.plug_idle(self, True, False)

		errnum = 0
		''' variable for errno symbol that will be found from exception raised from connect() '''
	
		# set timeout for TCP connecting - if nonblocking connect() fails, pollend
		# is called. If if succeeds pollout is called.
		self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT_SECONDS)

		try: 
			self.sock.setblocking(False)
			self.sock.connect(conn_5tuple[4])
		except Exception, (errnum, errstr):
			pass

		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
			# connecting in progress
			self.state = CONNECTING
			log.debug('After nonblocking connect. "%s" raised => CONNECTING' % errstr)
			# on_tcp_connect/failure will be called from self.pollin/self.pollout
			return
		elif errnum in (0, 10056, errno.EISCONN):
			# already connected - this branch is very unlikely, nonblocking connect() will
			# return EINPROGRESS exception in most cases. Anyway, we don't need timeout
			# on connected descriptor
			log.debug('After nonblocking connect. "%s" raised => CONNECTED' % errstr)
			self._on_tcp_connect(self)
			return

		# if there was some other error, call failure callback and unplug transport
		# which will also remove read_timeouts for descriptor
		self._on_tcp_failure('Exception while connecting to %s: %s - %s' % 
			(conn_5tuple[4], errnum, errstr))
			
	def _on_tcp_connect(self, data):
		''' This method preceeds actual call of on_tcp_connect callback 
		'''
		self.state = CONNECTED
		self.idlequeue.remove_timeout(self.fd)
		self.on_tcp_connect(data)


	def _on_tcp_failure(self,err_msg):
		''' This method preceeds actual call of on_tcp_failure callback
		'''
		self.state = DISCONNECTED
		self.idlequeue.unplug_idle(self.fd)
		self.on_tcp_failure(err_msg)

	def pollin(self):
		'''called when receive on plugged socket is possible '''
		log.debug('pollin called, state == %s' % self.state)

	def pollout(self):
		'''called when send to plugged socket is possible'''
		log.debug('pollout called, state == %s' % self.state)

		if self.state==CONNECTING:
			self._on_tcp_connect(self)
			return

	def pollend(self):
		'''called when remote site closed connection'''
		log.debug('pollend called, state == %s' % self.state)
		if self.state==CONNECTING:
			self._on_tcp_failure('Error during connect to %s:%s' % self.conn_5tuple[4])

	def read_timeout(self):
		'''
		Implemntation of IdleObject function called on timeouts from IdleQueue.
		'''
		log.debug('read_timeout called, state == %s' % self.state)
		if self.state==CONNECTING:
			# if read_timeout is called during connecting, connect() didn't end yet
			# thus we have to close the socket
			try:
				self.sock.close()
			except socket.error, (errnum, errmsg):
				log.error('Error while closing socket on connection timeout: %s %s'
					% (errnum, errmsg))
			self._on_tcp_failure('Error during connect to %s:%s' % self.conn_5tuple[4])

	

	def disconnect(self, on_disconnect=None):
		if self.state == DISCONNECTED:
			return
		self.idlequeue.unplug_idle(self.fd)
		try:
			self.sock.shutdown(socket.SHUT_RDWR)
		except socket.error, (errnum, errstr):
			log.error('Error while disconnecting: %s %s' % (errnum,errstr))
		
		try:
			self.sock.close()
		except socket.error, (errnum, errmsg):
			log.error('Error closing socket: %s %s' % (errnum,errstr))
		if on_disconnect:
			on_disconnect()






	def send(self, data, now=False):
		pass

	def onreceive(self):
		pass

	def set_send_timeout(self):
		pass
	
	def set_timeout(self):
		pass

	def remove_timeout(self):
		pass

	def start_disconnect(self):
		pass
