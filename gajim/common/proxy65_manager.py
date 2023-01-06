# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import errno
import logging
import socket
import struct

import nbxmpp
from nbxmpp.idlequeue import IdleObject
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common import helpers
from gajim.common.file_props import FilesProp
from gajim.common.socks5 import Socks5

log = logging.getLogger('gajim.c.proxy65_manager')

S_INITIAL = 0
S_STARTED = 1
S_RESOLVED = 2
S_ACTIVATED = 3
S_FINISHED = 4

CONNECT_TIMEOUT = 20


class Proxy65Manager:
    '''
    Keep records for file transfer proxies. Each time account establishes a
    connection to its server call proxy65manger.resolve(proxy) for every proxy
    that is configured within the account. The class takes care to resolve and
    test each proxy only once
    '''

    def __init__(self, idlequeue):
        # dict {proxy: proxy properties}
        self.idlequeue = idlequeue
        self.proxies = {}
        # dict {account: proxy} default proxy for account
        self.default_proxies = {}

    def resolve(self, proxy, connection, sender_jid, default=None,
                testit=True):
        '''
        Start
        if testit=False, Gajim won't try to resolve it
        '''
        if proxy not in self.proxies:
            # proxy is being resolved for the first time
            resolver = ProxyResolver(proxy, sender_jid, testit)
            self.proxies[proxy] = resolver
            resolver.add_connection(connection)
        if default:
            # add this proxy as default for account
            self.default_proxies[default] = proxy

    def disconnect(self, connection):
        for resolver in self.proxies.values():
            resolver.disconnect(connection)

    def resolve_result(self, proxy, query):
        if proxy not in self.proxies:
            return
        jid = None
        for item in query.getChildren():
            if item.getName() == 'streamhost':
                host = item.getAttr('host')
                jid = item.getAttr('jid')
                port = item.getAttr('port')
                try:
                    port = int(port)
                except (ValueError, TypeError):
                    port = 1080
                if not host or not jid:
                    self.proxies[proxy]._on_connect_failure()
                self.proxies[proxy].resolve_result(host, port, jid)
                # we can have only one streamhost
                raise nbxmpp.NodeProcessed

    def error_cb(self, proxy, query):
        sid = query.getAttr('sid')
        for resolver in self.proxies.values():
            if resolver.sid == sid:
                resolver.keep_conf()
                break

    def get_default_for_name(self, account):
        if account in self.default_proxies:
            return self.default_proxies[account]

    def get_proxy(self, proxy, account):
        if proxy in self.proxies:
            resolver = self.proxies[proxy]
            if resolver.state == S_FINISHED:
                return (resolver.host, resolver.port, resolver.jid)
        return (None, 0, None)


class ProxyResolver:
    def resolve_result(self, host, port, jid):
        '''
        Test if host has a real proxy65 listening on port
        '''
        self.host = str(host)
        self.port = int(port)
        self.jid = str(jid)
        if not self.testit:
            self.state = S_FINISHED
            return
        self.state = S_INITIAL
        log.info('start resolving %s:%s', self.host, self.port)
        self.receiver_tester = ReceiverTester(
            self.host, self.port, self.jid,
            self.sid, self.sender_jid, self._on_receiver_success,
            self._on_connect_failure)
        self.receiver_tester.connect()

    def _on_receiver_success(self):
        log.debug('Receiver successfully connected %s:%s',
                  self.host, self.port)
        self.host_tester = HostTester(
            self.host, self.port, self.jid,
            self.sid, self.sender_jid, self._on_connect_success,
            self._on_connect_failure)
        self.host_tester.connect()

    def _on_connect_success(self):
        log.debug('Host successfully connected %s:%s', self.host, self.port)
        iq = nbxmpp.Protocol(name='iq', to=self.jid, typ='set')
        query = iq.setTag('query')
        query.setNamespace(Namespace.BYTESTREAM)
        query.setAttr('sid', self.sid)

        activate = query.setTag('activate')
        activate.setData('test@gajim.org/test2')

        if self.active_connection:
            log.debug('Activating bytestream on %s:%s', self.host, self.port)
            self.active_connection.SendAndCallForResponse(
                iq, self._result_received)
            self.state = S_ACTIVATED
        else:
            self.state = S_INITIAL

    def _result_received(self, _nbxmpp_client, data):
        self.disconnect(self.active_connection)
        if data.getType() == 'result':
            self.keep_conf()
        else:
            self._on_connect_failure()

    def keep_conf(self):
        log.debug('Bytestream activated %s:%s', self.host, self.port)
        self.state = S_FINISHED

    def _on_connect_failure(self):
        log.debug('Connection failed with %s:%s', self.host, self.port)
        self.state = S_FINISHED
        self.host = None
        self.port = 0
        self.jid = None

    def disconnect(self, connection):
        if self.host_tester:
            self.host_tester.disconnect()
            FilesProp.deleteFileProp(self.host_tester.file_props)
            self.host_tester = None
        if self.receiver_tester:
            self.receiver_tester.disconnect()
            FilesProp.deleteFileProp(self.receiver_tester.file_props)
            self.receiver_tester = None
        try:
            self.connections.remove(connection)
        except ValueError:
            pass
        if connection == self.active_connection:
            self.active_connection = None
            if self.state != S_FINISHED:
                self.state = S_INITIAL
                self.try_next_connection()

    def try_next_connection(self):
        '''
        Try to resolve proxy with the next possible connection
        '''
        if self.connections:
            connection = self.connections.pop(0)
            self.start_resolve(connection)

    def add_connection(self, connection):
        '''
        Add a new connection in case the first fails
        '''
        self.connections.append(connection)
        if self.state == S_INITIAL:
            self.start_resolve(connection)

    def start_resolve(self, connection):
        '''
        Request network address from proxy
        '''
        self.state = S_STARTED
        self.active_connection = connection
        iq = nbxmpp.Protocol(name='iq', to=self.proxy, typ='get')
        query = iq.setTag('query')
        query.setNamespace(Namespace.BYTESTREAM)
        connection.send(iq)

    def __init__(self, proxy, sender_jid, testit):
        '''
        if testit is False, don't test it, only get IP/port
        '''
        self.proxy = proxy
        self.state = S_INITIAL
        self.active_connection = None
        self.connections = []
        self.host_tester = None
        self.receiver_tester = None
        self.jid = None
        self.host = None
        self.port = None
        self.sid = helpers.get_random_string()
        self.sender_jid = sender_jid
        self.testit = testit


class HostTester(Socks5, IdleObject):
    '''
    Fake proxy tester
    '''

    def __init__(self,
                 host,
                 port,
                 jid,
                 sid,
                 sender_jid,
                 on_success,
                 on_failure):
        '''
        Try to establish and auth to proxy at (host, port)

        Calls on_success, or on_failure according to the result.
        '''
        IdleObject.__init__(self)
        self.host = host
        self.port = port
        self.jid = jid
        self.on_success = on_success
        self.on_failure = on_failure
        self._sock = None
        self.file_props = FilesProp.getNewFileProp(jid, sid)
        self.file_props.is_a_proxy = True
        self.file_props.proxy_sender = sender_jid
        self.file_props.proxy_receiver = 'test@gajim.org/test2'
        Socks5.__init__(self, app.idlequeue, host, port, None, None, None)
        self.sid = sid

    def connect(self):
        '''
        Create the socket and plug it to the idlequeue
        '''
        if self.host is None:
            self.on_failure()
            return None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self.fd = self._sock.fileno()
        self.state = 0  # about to be connected
        app.idlequeue.plug_idle(self, True, False)
        self.do_connect()
        self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
        return None

    def read_timeout(self):
        self.idlequeue.remove_timeout(self.fd)
        self.pollend()

    def pollend(self):
        self.disconnect()
        self.on_failure()

    def pollout(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.state == 0:
            self.do_connect()
            return
        if self.state == 1:  # send initially: version and auth types
            data = self._get_auth_buff()
            self.send_raw(data)
        else:
            return
        self.state += 1
        # unplug and plug for reading
        app.idlequeue.plug_idle(self, False, True)
        app.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)

    def pollin(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.state == 2:
            self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
            # begin negotiation. on success 'address' != 0
            buff = self.receive()
            if buff == b'':
                # end connection
                self.pollend()
                return
            # read auth response
            if buff is None or len(buff) != 2:
                return None
            version, method = struct.unpack('!BB', buff[:2])
            if version != 0x05 or method == 0xff:
                self.pollend()
                return
            data = self._get_request_buff(self._get_sha1_auth())
            self.send_raw(data)
            self.state += 1
            log.debug('Host authenticating to %s:%s', self.host, self.port)
        elif self.state == 3:
            log.debug('Host authenticated to %s:%s', self.host, self.port)
            self.on_success()
            self.disconnect()
            self.state += 1
        else:
            raise AssertionError('unexpected state: %d' % self.state)

    def do_connect(self):
        try:
            self._sock.connect((self.host, self.port))
            self._sock.setblocking(False)
            log.debug('Host Connecting to %s:%s', self.host, self.port)
            self._send = self._sock.send
            self._recv = self._sock.recv
        except Exception as ee:
            errnum = ee.errno
            # 56 is for freebsd
            if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
                # still trying to connect
                return
            # win32 needs this
            if errnum not in (0, 10056, errno.EISCONN):
                # connection failed
                self.on_failure()
                return
            # socket is already connected
            self._sock.setblocking(False)
            self._send = self._sock.send
            self._recv = self._sock.recv
        self.buff = b''
        self.state = 1  # connected
        log.debug('Host connected to %s:%s', self.host, self.port)
        self.idlequeue.plug_idle(self, True, False)
        return


class ReceiverTester(Socks5, IdleObject):
    '''
    Fake proxy tester
    '''

    def __init__(self,
                 host,
                 port,
                 jid,
                 sid,
                 sender_jid,
                 on_success,
                 on_failure):
        '''
        Try to establish and auth to proxy at (host, port)

        Call on_success, or on_failure according to the result.
        '''
        IdleObject.__init__(self)
        self.host = host
        self.port = port
        self.jid = jid
        self.on_success = on_success
        self.on_failure = on_failure
        self._sock = None
        self.file_props = FilesProp.getNewFileProp(jid, sid)
        self.file_props.is_a_proxy = True
        self.file_props.proxy_sender = sender_jid
        self.file_props.proxy_receiver = 'test@gajim.org/test2'
        Socks5.__init__(self, app.idlequeue, host, port, None, None, None)
        self.sid = sid

    def connect(self):
        '''
        Create the socket and plug it to the idlequeue
        '''
        if self.host is None:
            self.on_failure()
            return None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self.fd = self._sock.fileno()
        self.state = 0  # about to be connected
        app.idlequeue.plug_idle(self, True, False)
        self.do_connect()
        self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
        return None

    def read_timeout(self):
        self.idlequeue.remove_timeout(self.fd)
        self.pollend()

    def pollend(self):
        self.disconnect()
        self.on_failure()

    def pollout(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.state == 0:
            self.do_connect()
            return
        if self.state == 1:  # send initially: version and auth types
            data = self._get_auth_buff()
            self.send_raw(data)
        else:
            return
        self.state += 1
        # unplug and plug for reading
        app.idlequeue.plug_idle(self, False, True)
        app.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)

    def pollin(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.state in (2, 3):
            self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
            # begin negotiation. on success 'address' != 0
            buff = self.receive()
            if buff == b'':
                # end connection
                self.pollend()
                return
        if self.state == 2:
            # read auth response
            if buff is None or len(buff) != 2:
                return None
            version, method = struct.unpack('!BB', buff[:2])
            if version != 0x05 or method == 0xff:
                self.pollend()
                return
            log.debug('Receiver authenticating to %s:%s', self.host, self.port)
            data = self._get_request_buff(self._get_sha1_auth())
            self.send_raw(data)
            self.state += 1
        elif self.state == 3:
            # read connect response
            if buff is None or len(buff) < 2:
                return None
            version, reply = struct.unpack('!BB', buff[:2])
            if version != 0x05 or reply != 0x00:
                self.pollend()
                return
            log.debug('Receiver authenticated to %s:%s', self.host, self.port)
            self.on_success()
            self.disconnect()
            self.state += 1
        else:
            raise AssertionError('unexpected state: %d' % self.state)

    def do_connect(self):
        try:
            self._sock.setblocking(False)
            self._sock.connect((self.host, self.port))
            log.debug('Receiver Connecting to %s:%s', self.host, self.port)
            self._send = self._sock.send
            self._recv = self._sock.recv
        except Exception as ee:
            errnum = ee.errno
            # 56 is for freebsd
            if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
                # still trying to connect
                return
            # win32 needs this
            if errnum not in (0, 10056, errno.EISCONN):
                # connection failed
                self.on_failure()
                return
            # socket is already connected
            self._sock.setblocking(False)
            self._send = self._sock.send
            self._recv = self._sock.recv
        self.buff = ''
        self.state = 1  # connected
        log.debug('Receiver connected to %s:%s', self.host, self.port)
        self.idlequeue.plug_idle(self, True, False)
