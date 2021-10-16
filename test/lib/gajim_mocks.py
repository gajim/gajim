'''
Module with dummy classes for Gajim specific unit testing
'''

from .mock import Mock
from gajim.common import app
from gajim.common import ged

from gajim.common.connection_handlers import ConnectionHandlers

class MockConnection(Mock, ConnectionHandlers):
    def __init__(self, account, *args):
        Mock.__init__(self, *args)

        self.connection = Mock()

        self.name = account

        ConnectionHandlers.__init__(self)

        self.connected = 2
        self.pep = {}
        self.sessions = {}
        self.server_resource = 'Gajim'

        app.interface.instances[account] = {
            'infos': {},
            'disco': {}
        }
        app.interface.minimized_controls[account] = {}
        app.contacts.add_account(account)
        app.groups[account] = {}
        app.gc_connected[account] = {}
        app.automatic_rooms[account] = {}
        app.newly_added[account] = []
        app.to_be_removed[account] = []
        app.nicks[account] = app.settings.get_account_setting(account, 'name')
        app.block_signed_in_notifications[account] = True

        app.connections[account] = self

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
        app.interface = self
        self.msg_win_mgr = Mock()
        self.roster = Mock()
        app.ged = ged.GlobalEventsDispatcher()
        from gajim import plugins
        app.plugin_manager = plugins.PluginManager()

        self.instances = {}
        self.minimized_controls = {}


class MockLogger(Mock):
    def __init__(self):
        Mock.__init__(self, {'insert_into_logs': None,
            'get_transports_type': {}})
        self.cur = Mock()


class MockContact(Mock):
    def __nonzero__(self):
        return True


import random

class MockSession(Mock):
    def __init__(self, conn, jid, thread_id, type_):
        Mock.__init__(self)

        self.conn = conn
        self.jid = jid
        self.type_ = type_
        self.thread_id = thread_id
        self.resource = ''

        if not self.thread_id:
            self.thread_id = '%0x' % random.randint(0, 10000)

    def __repr__(self):
        return '<MockSession %s>' % self.thread_id

    def __nonzero__(self):
        return True

    def __eq__(self, other):
        return self is other
