'''
Module with dummy classes for Gajim specific unit testing
'''

from mock import Mock
from common import gajim

from common.connection_handlers import ConnectionHandlersBase

class MockConnection(Mock, ConnectionHandlersBase):
	def __init__(self, account, *args):
		Mock.__init__(self, *args)
		ConnectionHandlersBase.__init__(self)

		self.name = account
		self.connected = 2
		self.mood = {}
		self.activity = {}
		self.tune = {}
		self.blocked_contacts = {}
		self.blocked_groups = {}
		self.sessions = {}

		gajim.interface.instances[account] = {'infos': {}, 'disco': {},
			'gc_config': {}, 'search': {}}
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
		self._controls = {}

	def get_control(self, jid, account):
		try:
			return self._controls[account][jid]
		except KeyError:
			return None

	def has_control(self, jid, acct):
		return self.get_control(jid, acct) is not None

	def new_tab(self, ctrl):
		account = ctrl.account
		jid = ctrl.jid

		if account not in self._controls:
			self._controls[account] = {}

		if jid not in self._controls[account]:
			self._controls[account][jid] = {}

		self._controls[account][jid] = ctrl

	def __nonzero__(self):
		return True

class MockChatControl(Mock):
	def __init__(self, jid, account, *args):
		Mock.__init__(self, *args)

		self.jid = jid
		self.account = account

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
		gajim.interface = self
		self.msg_win_mgr = Mock()
		self.roster = Mock()

		self.remote_ctrl = None
		self.instances = {}
		self.minimized_controls = {}
		self.status_sent_to_users = Mock()

		if gajim.use_x:
			self.jabber_state_images = {'16': {}, '32': {}, 'opened': {},
				'closed': {}}

			import gtkgui_helpers
			gtkgui_helpers.make_jabber_state_images()
		else:
			self.jabber_state_images = {'16': Mock(), '32': Mock(),
				'opened': Mock(), 'closed': Mock()}

class MockLogger(Mock):
	def __init__(self):
		Mock.__init__(self, {'write': None, 'get_transports_type': {}})

class MockContact(Mock):
	def __nonzero__(self):
		return True

import random

class MockSession(Mock):
	def __init__(self, conn, jid, thread_id, type_):
		Mock.__init__(self)

		self.conn = conn
		self.jid = jid
		self.type = type_
		self.thread_id = thread_id

		if not self.thread_id:
			self.thread_id = '%0x' % random.randint(0, 10000)

	def __repr__(self):
		return '<MockSession %s>' % self.thread_id

	def __nonzero__(self):
		return True

	def __eq__(self, other):
		return self is other

# vim: se ts=3:
