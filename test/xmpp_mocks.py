'''
Module with dummy classes for unit testing of XMPP and related code.
'''

import threading, time, os.path, sys

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
sys.path.append(gajim_root + '/src/common/xmpp')
import idlequeue
from client import PlugIn

import lib
lib.setup_env()


from mock import Mock



idlequeue_interval = 0.2
'''
IdleQueue polling interval. 200ms is used in Gajim as default
'''

class IdleQueueThread(threading.Thread):
	'''
	Thread for regular processing of idlequeue.
	'''
	def __init__(self):
		self.iq = idlequeue.IdleQueue()
		self.stop = threading.Event()
		'''
		Event used to stopping the thread main loop.
		'''

		self.stop.clear()
		threading.Thread.__init__(self)
	
	def run(self):
		while not self.stop.isSet():
			self.iq.process()
			time.sleep(idlequeue_interval)

	def stop_thread(self):
		self.stop.set()

	
class IdleMock:
	'''
	Serves as template for testing objects that are normally controlled by GUI.
	Allows to wait for asynchronous callbacks with wait() method. 
	'''
	def __init__(self):
		self.event = threading.Event()
		'''
		Event is used for waiting on callbacks.
		'''
		self.event.clear()

	def wait(self):
		'''
		Waiting until some callback sets the event and clearing the event
		subsequently. 
		'''
		self.event.wait()
		self.event.clear()

	def set_event(self):
		self.event.set()


class MockConnectionClass(IdleMock, Mock):
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
		#print 'on_connect - args:'
		#print '    success - %s' % success
		#for i in args:
		#	print '    %s' % i
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
		#print 'on_auth - args:'
		#print '    con: %s' % con
		#print '    auth: %s' % auth
		self.auth_connection = con
		self.auth = auth
		self.set_event()

# vim: se ts=3:
