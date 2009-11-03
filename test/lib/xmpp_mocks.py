'''
Module with dummy classes for unit testing of XMPP and related code.
'''

import threading, time

from mock import Mock

from common.xmpp import idlequeue

IDLEQUEUE_INTERVAL = 0.2 # polling interval. 200ms is used in Gajim as default
IDLEMOCK_TIMEOUT = 30 # how long we wait for an event

class IdleQueueThread(threading.Thread):
	'''
	Thread for regular processing of idlequeue.
	'''
	def __init__(self):
		self.iq = idlequeue.IdleQueue()
		self.stop = threading.Event() # Event to stop the thread main loop.
		self.stop.clear()
		threading.Thread.__init__(self)
	
	def run(self):
		while not self.stop.isSet():
			self.iq.process()
			time.sleep(IDLEQUEUE_INTERVAL)

	def stop_thread(self):
		self.stop.set()

	
class IdleMock:
	'''
	Serves as template for testing objects that are normally controlled by GUI.
	Allows to wait for asynchronous callbacks with wait() method. 
	'''
	def __init__(self):
		self._event = threading.Event()
		self._event.clear()

	def wait(self):
		'''
		Block until some callback sets the event and clearing the event
		subsequently. 
		Returns True if event was set, False on timeout
		'''
		self._event.wait(IDLEMOCK_TIMEOUT)
		if self._event.isSet():
			self._event.clear()
			return True
		else:
			return False

	def set_event(self):
		self._event.set()


class MockConnection(IdleMock, Mock):
	'''
	Class simulating Connection class from src/common/connection.py

	It is derived from Mock in order to avoid defining all methods
	from real Connection that are called from NBClient or Dispatcher
	( _event_dispatcher for example)
	'''

	def __init__(self, *args):
		self.connect_succeeded = True
		IdleMock.__init__(self)
		Mock.__init__(self, *args)

	def on_connect(self, success, *args):
		'''
		Method called after connecting - after receiving <stream:features>
		from server (NOT after TLS stream restart) or connect failure
		'''
		self.connect_succeeded = success
		self.set_event()
		

	def on_auth(self, con, auth):
		'''
		Method called after authentication, regardless of the result.

		:Parameters:
			con : NonBlockingClient
				reference to authenticated object
			auth : string
				type of authetication in case of success ('old_auth', 'sasl') or
				None in case of auth failure
		'''
		self.auth_connection = con
		self.auth = auth
		self.set_event()

# vim: se ts=3:
