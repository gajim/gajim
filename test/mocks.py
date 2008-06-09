# gajim-specific mock objects
from mock import Mock

from common import gajim

class MockConnection(Mock):
	def __init__(self, name, *args):
		Mock.__init__(self, *args)
		self.name = name
		gajim.connections[name] = self

class MockWindow(Mock):
	def __init__(self, *args):
		Mock.__init__(self, *args)
		self.window = Mock()

class MockChatControl(Mock):
	def __init__(self, *args):
		Mock.__init__(self, *args)

		self.parent_win = MockWindow({'get_active_control': self})
		self.session = None

	def set_session(self, sess):
		self.session = sess

	def __nonzero__(self):
		return True

	def __eq__(self, other):
		return self is other

class MockInterface(Mock):
	def __init__(self, acct, *args):
		Mock.__init__(self, *args)
		self.msg_win_mgr = Mock()
		self.roster = Mock()

		self.remote_ctrl = None
		self.minimized_controls = { acct: {} }

class MockLogger(Mock):
	def __init__(self):
		Mock.__init__(self, {'write': None})

class MockContact(Mock):
	def __nonzero__(self):
		return True

import random

class MockSession(Mock):
	def __init__(self, conn, jid, thread_id, type):
		Mock.__init__(self)

		self.conn = conn
		self.jid = jid
		self.type = type
		self.thread_id = thread_id

		if not self.thread_id:
			self.thread_id = '%0x' % random.randint(0, 10000)

	def __repr__(self):
		print '<MockSession %s>' % self.thread_id

	def __nonzero__(self):
		return True
