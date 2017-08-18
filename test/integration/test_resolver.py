import unittest

import time

import lib
lib.setup_env()

from gi.repository import GLib

from gajim.common import resolver

from mock import Mock, expectParams
from gajim_mocks import *
from xmpp_mocks import IdleQueueThread

GMAIL_SRV_NAME = '_xmpp-client._tcp.gmail.com'
NONSENSE_NAME = 'sfsdfsdfsdf.sdfs.fsd'
JABBERCZ_TXT_NAME = '_xmppconnect.jabber.cz'
JABBERCZ_SRV_NAME = '_xmpp-client._tcp.jabber.cz'

TEST_LIST = [(GMAIL_SRV_NAME, 'srv', True),
        (NONSENSE_NAME, 'srv', False),
        (JABBERCZ_SRV_NAME, 'srv', True)]

class TestResolver(unittest.TestCase):
    '''
    Test for LibAsyncNSResolver and NSLookupResolver. Requires working
    network connection.
    '''
    def setUp(self):
        self.idlequeue_thread = IdleQueueThread()
        self.idlequeue_thread.start()
        self.main_context = GLib.MainContext()
        self.main_context.push_thread_default()
        self.main_loop = GLib.MainLoop(self.main_context)

        self.iq = self.idlequeue_thread.iq
        self._reset()
        self.resolver = None

    def tearDown(self):
        self.main_context.pop_thread_default()
        self.idlequeue_thread.stop_thread()
        self.idlequeue_thread.join()

    def _reset(self):
        self.expect_results = False
        self.resolver = None

    def testGioResolver(self):
        self._reset()
        self.resolver = resolver.GioResolver()

        for name, type_, expect_results in TEST_LIST:
            self.expect_results = expect_results
            self._runGR(name, type_)

    def _runGR(self, name, type_):
        self.resolver.resolve(
                host = name,
                type_ = type_,
                on_ready = self._myonready)

        self.main_loop.run()

    def _myonready(self, name, result_set):
        if __name__ == '__main__':
            from pprint import pprint
            pprint('on_ready called ...')
            pprint('hostname: %s' % name)
            pprint('result set: %s' % result_set)
            pprint('res.resolved_hosts: %s' % self.resolver.resolved_hosts)
            pprint('')
        if self.expect_results:
            self.assertTrue(len(result_set) > 0)
        else:
            self.assertTrue(result_set == [])
        self.main_loop.quit()


if __name__ == '__main__':
    unittest.main()
