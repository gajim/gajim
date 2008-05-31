# Example script for usage of BOSHClient class
# --------------------------------------------
# run `python run_client_bosh.py` in gajim/src/common/xmpp/examples/ directory
# and quit with CTRL + c.
# Script will open TCP connection to Connection Manager, send BOSH initial
# request and receive initial response. Handling of init response is not
# done yet.


# imports gtk because of gobject.timeout_add() which is used for processing
# idlequeue
# TODO: rewrite to thread timer
import gtk
import gobject
import sys, os.path

xmpppy_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
sys.path.append(xmpppy_dir)

import idlequeue
from client_bosh import BOSHClient


class DummyConnection():
	'''
	Dummy class for test run of bosh_client. I use it because in Connection class
	the gajim.py module is imported and stuff from it is read in there, so it
	would be difficult to debug IMHO. On the other hand, I will have to test with
	Connection class sooner or later somehow because that's the main place where
	BOSHClient should be used.
	DummyConnection class holds and processes IdleQueue for BOSHClient.
	'''

	def __init__(self, iq_interval_ms=1000):
		self.classname = self.__class__.__name__
		self.iq_interval_ms = iq_interval_ms
		self.idlequeue = idlequeue.IdleQueue()
		self.timer=gobject.timeout_add(iq_interval_ms, self.process_idlequeue)


	def process_idlequeue(self):
		''' 
		called each iq_interval_ms miliseconds. Checks for idlequeue timeouts.
		'''
		self.idlequeue.process()
		return True

	# callback stubs follows
	def _event_dispatcher(self, realm, event, data):
		print "\n>>> %s._event_dispatcher called:" % self.classname
		print ">>> realm: %s, event: %s, data: %s\n" % (realm, event, data)


	def onconsucc(self):
		print '%s: CONNECTION SUCCEEDED' % self.classname


	def onconfail(self, retry=None):
		print '%s: CONNECTION FAILED.. retry?: %s' % (self.classname, retry)


if __name__ == "__main__":
	dc = DummyConnection()

	# you can use my instalation of ejabberd2:
	server = 'star.securitynet.cz'
	bosh_conn_mgr = 'http://star.securitynet.cz/http-bind/'

        #server='jabbim.cz'
        #bosh_conn_mgr='http://bind.jabbim.cz/'

	bc = BOSHClient(
		server = server,
		bosh_conn_mgr = bosh_conn_mgr,
		bosh_port = 80,
		on_connect = dc.onconsucc,
		on_connect_failure = dc.onconfail,
		caller = dc
	)

	bc.set_idlequeue(dc.idlequeue)

	bc.connect()

	try:
		gtk.main()
	except KeyboardInterrupt:
		dc.process_idlequeue()

