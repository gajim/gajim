# gajim-specific mock objects
from mock import Mock

from common import gajim

class MockConnection(Mock):
	def __init__(self, account, *args):
		Mock.__init__(self, *args)
		self.name = account
		self.connected = 2
		self.mood = {}
		self.activity = {}
		self.tune = {}
		self.blocked_contacts = {}
		self.blocked_groups = {}
		gajim.interface.instances[account] = {'infos': {}, 'disco': {}, 'gc_config': {}, 'search': {}}
		gajim.interface.minimized_controls[account] = {}
		gajim.contacts.add_account(account)
		gajim.groups[account] = {}
		gajim.gc_connected[account] = {}
		gajim.automatic_rooms[account] = {}
		gajim.newly_added[account] = []
		gajim.to_be_removed[account] = []
		gajim.nicks[account] = gajim.config.get_per('accounts', account, 'name')
		gajim.block_signed_in_notifications[account] = True
		gajim.sleeper_state[account] = 0
		gajim.encrypted_chats[account] = []
		gajim.last_message_time[account] = {}
		gajim.status_before_autoaway[account] = ''
		gajim.transport_avatar[account] = {}
		gajim.gajim_optional_features[account] = []
		gajim.caps_hash[account] = ''

		gajim.connections[account] = self

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
	def __init__(self, *args):
		Mock.__init__(self, *args)
		self.msg_win_mgr = Mock()
		self.roster = Mock()

		self.remote_ctrl = None
		self.instances = {}
		self.minimized_controls = {}
		self.status_sent_to_users = Mock()

		self.jabber_state_images = {'16': Mock(), '32': Mock(), 'opened': Mock(), 'closed': Mock()}

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

# vim: se ts=3:
