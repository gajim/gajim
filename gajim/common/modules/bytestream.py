# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Junglecow J <junglecow AT gmail.com>
# Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
#                         Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Jean-Marie Traissard <jim AT lapin.org>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import socket
import logging

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from gi.repository import GLib

from gajim.common import app
from gajim.common import helpers
from gajim.common import jingle_xtls
from gajim.common.events import FileRequestError
from gajim.common.file_props import FilesProp
from gajim.common.socks5 import Socks5SenderClient
from gajim.common.modules.base import BaseModule


log = logging.getLogger('gajim.c.m.bytestream')

def is_transfer_paused(file_props):
    if file_props.stopped:
        return False
    if file_props.completed:
        return False
    if file_props.disconnect_cb:
        return False
    return file_props.paused

def is_transfer_active(file_props):
    if file_props.stopped:
        return False
    if file_props.completed:
        return False
    if not file_props.started:
        return False
    if file_props.paused:
        return True
    return not file_props.paused

def is_transfer_stopped(file_props):
    if not file_props:
        return True
    if file_props.error:
        return True
    if file_props.completed:
        return True
    if not file_props.stopped:
        return False
    return True


class Bytestream(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          typ='result',
                          ns=Namespace.BYTESTREAM,
                          callback=self._on_bytestream_result),
            StanzaHandler(name='iq',
                          typ='error',
                          ns=Namespace.BYTESTREAM,
                          callback=self._on_bytestream_error),
            StanzaHandler(name='iq',
                          typ='set',
                          ns=Namespace.BYTESTREAM,
                          callback=self._on_bytestream_set),
            StanzaHandler(name='iq',
                          typ='result',
                          callback=self._on_result),
        ]

        self.no_gupnp_reply_id = None
        self.ok_id = None
        self.fail_id = None

    def pass_disco(self, info):
        if Namespace.BYTESTREAM not in info.features:
            return
        if app.settings.get_account_setting(self._account, 'use_ft_proxies'):
            log.info('Discovered proxy: %s', info.jid)
            our_fjid = self._con.get_own_jid()
            testit = app.settings.get_account_setting(
                self._account, 'test_ft_proxies_on_startup')
            app.proxy65_manager.resolve(
                info.jid, self._con.connection, str(our_fjid),
                default=self._account, testit=testit)
            raise nbxmpp.NodeProcessed

    def _ft_get_receiver_jid(self, file_props):
        if self._account == 'Local':
            return file_props.receiver.jid
        return file_props.receiver.jid + '/' + file_props.receiver.resource

    def _ft_get_from(self, iq_obj):
        if self._account == 'Local':
            return iq_obj.getFrom()
        return helpers.get_full_jid_from_iq(iq_obj)

    def _ft_get_streamhost_jid_attr(self, streamhost):
        if self._account == 'Local':
            return streamhost.getAttr('jid')
        return helpers.parse_jid(streamhost.getAttr('jid'))

    def send_file_approval(self, file_props):
        """
        Send iq, confirming that we want to download the file
        """
        # user response to ConfirmationDialog may come after we've disconnected
        if not app.account_is_available(self._account):
            return

        # file transfer initiated by a jingle session
        log.info("send_file_approval: jingle session accept")

        session = self._con.get_module('Jingle').get_jingle_session(
            file_props.sender, file_props.sid)
        if not session:
            return
        content = None
        for content_ in session.contents.values():
            if content_.transport.sid == file_props.transport_sid:
                content = content_
                break

        if not content:
            return

        if not session.accepted:
            content = session.get_content('file', content.name)
            if content.use_security:
                fingerprint = content.x509_fingerprint
                if not jingle_xtls.check_cert(
                        app.get_jid_without_resource(file_props.sender),
                        fingerprint):
                    id_ = jingle_xtls.send_cert_request(
                        self._con, file_props.sender)
                    jingle_xtls.key_exchange_pend(id_,
                                                  content.on_cert_received, [])
                    return
            session.approve_session()

        session.approve_content('file', content.name)

    def send_file_rejection(self, file_props):
        """
        Inform sender that we refuse to download the file

        typ is used when code = '400', in this case typ can be 'stream' for
        invalid stream or 'profile' for invalid profile
        """
        # user response to ConfirmationDialog may come after we've disconnected
        if not app.account_is_available(self._account):
            return

        for session in self._con.get_module('Jingle').get_jingle_sessions(
                None, file_props.sid):
            session.cancel_session()

    def send_success_connect_reply(self, streamhost):
        """
        Send reply to the initiator of FT that we made a connection
        """
        if not app.account_is_available(self._account):
            return
        if streamhost is None:
            return
        iq = nbxmpp.Iq(to=streamhost['initiator'],
                       typ='result',
                       frm=streamhost['target'])
        iq.setAttr('id', streamhost['id'])
        query = iq.setTag('query', namespace=Namespace.BYTESTREAM)
        stream_tag = query.setTag('streamhost-used')
        stream_tag.setAttr('jid', streamhost['jid'])
        self._con.connection.send(iq)

    def stop_all_active_file_transfers(self, contact):
        """
        Stop all active transfer to or from the given contact
        """
        for file_props in FilesProp.getAllFileProp():
            if is_transfer_stopped(file_props):
                continue
            receiver_jid = file_props.receiver
            if contact.jid == receiver_jid:
                file_props.error = -5
                self.remove_transfer(file_props)
                app.ged.raise_event(
                    FileRequestError(
                        conn=self._con,
                        jid=app.get_jid_without_resource(contact.jid),
                        file_props=file_props,
                        error_msg=''))
            sender_jid = file_props.sender
            if contact.jid == sender_jid:
                file_props.error = -3
                self.remove_transfer(file_props)

    def remove_all_transfers(self):
        """
        Stop and remove all active connections from the socks5 pool
        """
        for file_props in FilesProp.getAllFileProp():
            self.remove_transfer(file_props)

    def remove_transfer(self, file_props):
        if file_props is None:
            return
        self.disconnect_transfer(file_props)

    @staticmethod
    def disconnect_transfer(file_props):
        if file_props is None:
            return
        if file_props.hash_:
            app.socks5queue.remove_sender(file_props.hash_)

        if file_props.streamhosts:
            for host in file_props.streamhosts:
                if 'idx' in host and host['idx'] > 0:
                    app.socks5queue.remove_receiver(host['idx'])
                    app.socks5queue.remove_sender(host['idx'])

    def _send_socks5_info(self, file_props):
        """
        Send iq for the present streamhosts and proxies
        """
        if not app.account_is_available(self._account):
            return
        receiver = file_props.receiver
        sender = file_props.sender

        sha_str = helpers.get_auth_sha(file_props.sid, sender, receiver)
        file_props.sha_str = sha_str

        port = app.settings.get('file_transfers_port')
        listener = app.socks5queue.start_listener(
            port,
            sha_str,
            self._result_socks5_sid, file_props)
        if not listener:
            file_props.error = -5
            app.ged.raise_event(
                FileRequestError(
                    conn=self._con,
                    jid=app.get_jid_without_resource(receiver),
                    file_props=file_props,
                    error_msg=''))
            self._connect_error(file_props.sid,
                                error='not-acceptable',
                                error_type='modify')
        else:
            iq = nbxmpp.Iq(to=receiver, typ='set')
            file_props.request_id = 'id_' + file_props.sid
            iq.setID(file_props.request_id)
            query = iq.setTag('query', namespace=Namespace.BYTESTREAM)
            query.setAttr('sid', file_props.sid)

            self._add_addiditional_streamhosts_to_query(query, file_props)
            self._add_local_ips_as_streamhosts_to_query(query, file_props)
            self._add_proxy_streamhosts_to_query(query, file_props)
            self._add_upnp_igd_as_streamhost_to_query(query, file_props, iq)
            # Upnp-igd is asynchronous, so it will send the iq itself

    @staticmethod
    def _add_streamhosts_to_query(query, sender, port, hosts):
        for host in hosts:
            streamhost = nbxmpp.Node(tag='streamhost')
            query.addChild(node=streamhost)
            streamhost.setAttr('port', str(port))
            streamhost.setAttr('host', host)
            streamhost.setAttr('jid', sender)

    def _add_local_ips_as_streamhosts_to_query(self, query, file_props):
        if not app.settings.get_account_setting(self._account,
                                                'ft_send_local_ips'):
            return

        my_ip = self._con.local_address
        if my_ip is None:
            log.warning('No local address available')
            return

        try:
            # The ip we're connected to server with
            my_ips = [my_ip]
            # all IPs from local DNS
            for addr in socket.getaddrinfo(socket.gethostname(), None):
                if (not addr[4][0] in my_ips and
                        not addr[4][0].startswith('127') and
                        not addr[4][0] == '::1'):
                    my_ips.append(addr[4][0])

            sender = file_props.sender
            port = app.settings.get('file_transfers_port')
            self._add_streamhosts_to_query(query, sender, port, my_ips)
        except socket.gaierror:
            log.error('wrong host, invalid local address?')

    def _add_addiditional_streamhosts_to_query(self, query, file_props):
        sender = file_props.sender
        port = app.settings.get('file_transfers_port')
        ft_add_hosts_to_send = app.settings.get('ft_add_hosts_to_send')
        add_hosts = []
        if ft_add_hosts_to_send:
            add_hosts = [e.strip() for e in ft_add_hosts_to_send.split(',')]
        else:
            add_hosts = []
        self._add_streamhosts_to_query(query, sender, port, add_hosts)

    def _add_upnp_igd_as_streamhost_to_query(self, query, file_props, iq):
        my_ip = self._con.local_address
        if my_ip is None or not app.is_installed('UPNP'):
            log.warning('No local address available')
            self._con.connection.send(iq)
            return

        # check if we are connected with an IPv4 address
        try:
            socket.inet_aton(my_ip)
        except socket.error:
            self._con.connection.send(iq)
            return

        def ip_is_local(ip):
            if '.' not in ip:
                # it's an IPv6
                return True
            ip_s = ip.split('.')
            ip_l = int(ip_s[0])<<24 | int(ip_s[1])<<16 | int(ip_s[2])<<8 | \
                 int(ip_s[3])
            # 10/8
            if ip_l & (255<<24) == 10<<24:
                return True
            # 172.16/12
            if ip_l & (255<<24 | 240<<16) == (172<<24 | 16<<16):
                return True
            # 192.168
            if ip_l & (255<<24 | 255<<16) == (192<<24 | 168<<16):
                return True
            return False

        if not ip_is_local(my_ip):
            self.connection.send(iq)
            return

        self.no_gupnp_reply_id = 0

        def cleanup_gupnp():
            if self.no_gupnp_reply_id:
                GLib.source_remove(self.no_gupnp_reply_id)
                self.no_gupnp_reply_id = 0
            app.gupnp_igd.disconnect(self.ok_id)
            app.gupnp_igd.disconnect(self.fail_id)

        def success(_gupnp, _proto, ext_ip, _re, ext_port,
                    local_ip, local_port, _desc):
            log.debug('Got GUPnP-IGD answer: external: %s:%s, internal: %s:%s',
                      ext_ip, ext_port, local_ip, local_port)
            if local_port != app.settings.get('file_transfers_port'):
                sender = file_props.sender
                receiver = file_props.receiver
                sha_str = helpers.get_auth_sha(file_props.sid,
                                               sender,
                                               receiver)
                listener = app.socks5queue.start_listener(
                    local_port,
                    sha_str,
                    self._result_socks5_sid,
                    file_props.sid)
                if listener:
                    self._add_streamhosts_to_query(query,
                                                   sender,
                                                   ext_port,
                                                   [ext_ip])
            else:
                self._add_streamhosts_to_query(query,
                                               file_props.sender,
                                               ext_port,
                                               [ext_ip])
            self._con.connection.send(iq)
            cleanup_gupnp()

        def fail(_gupnp, error, _proto, _ext_ip, _local_ip, _local_port, _desc):
            log.debug('Got GUPnP-IGD error: %s', error)
            self._con.connection.send(iq)
            cleanup_gupnp()

        def no_upnp_reply():
            log.debug('Got not GUPnP-IGD answer')
            # stop trying to use it
            app.disable_dependency('UPNP')
            self.no_gupnp_reply_id = 0
            self._con.connection.send(iq)
            cleanup_gupnp()
            return False


        self.ok_id = app.gupnp_igd.connect('mapped-external-port', success)
        self.fail_id = app.gupnp_igd.connect('error-mapping-port', fail)

        port = app.settings.get('file_transfers_port')
        self.no_gupnp_reply_id = GLib.timeout_add_seconds(10, no_upnp_reply)
        app.gupnp_igd.add_port('TCP',
                               0,
                               my_ip,
                               port,
                               3600,
                               'Gajim file transfer')

    def _add_proxy_streamhosts_to_query(self, query, file_props):
        proxyhosts = self._get_file_transfer_proxies_from_config(file_props)
        if proxyhosts:
            file_props.proxy_receiver = file_props.receiver
            file_props.proxy_sender = file_props.sender
            file_props.proxyhosts = proxyhosts

            for proxyhost in proxyhosts:
                self._add_streamhosts_to_query(query,
                                               proxyhost['jid'],
                                               proxyhost['port'],
                                               [proxyhost['host']])

    def _get_file_transfer_proxies_from_config(self, file_props):
        configured_proxies = app.settings.get_account_setting(
            self._account, 'file_transfer_proxies')
        shall_use_proxies = app.settings.get_account_setting(
            self._account, 'use_ft_proxies')
        if shall_use_proxies:
            proxyhost_dicts = []
            proxies = []
            if configured_proxies:
                proxies = [item.strip() for item in
                           configured_proxies.split(',')]
            default_proxy = app.proxy65_manager.get_default_for_name(
                self._account)
            if default_proxy:
                # add/move default proxy at top of the others
                if default_proxy in proxies:
                    proxies.remove(default_proxy)
                proxies.insert(0, default_proxy)

            for proxy in proxies:
                (host, _port, jid) = app.proxy65_manager.get_proxy(
                    proxy, self._account)
                if not host:
                    continue
                host_dict = {
                    'state': 0,
                    'target': file_props.receiver,
                    'id': file_props.sid,
                    'sid': file_props.sid,
                    'initiator': proxy,
                    'host': host,
                    'port': str(_port),
                    'jid': jid
                }
                proxyhost_dicts.append(host_dict)
            return proxyhost_dicts

        return []

    @staticmethod
    def _result_socks5_sid(sid, hash_id):
        """
        Store the result of SHA message from auth
        """
        file_props = FilesProp.getFilePropBySid(sid)
        file_props.hash_ = hash_id

    def _connect_error(self, sid, error, error_type, msg=None):
        """
        Called when there is an error establishing BS connection, or when
        connection is rejected
        """
        if not app.account_is_available(self._account):
            return
        file_props = FilesProp.getFileProp(self._account, sid)
        if file_props is None:
            log.error('can not send iq error on failed transfer')
            return
        if file_props.type_ == 's':
            to = file_props.receiver
        else:
            to = file_props.sender
        iq = nbxmpp.Iq(to=to, typ='error')
        iq.setAttr('id', file_props.request_id)
        err = iq.setTag('error')
        err.setAttr('type', error_type)
        err.setTag(error, namespace=Namespace.STANZAS)
        self._con.connection.send(iq)
        if msg:
            self.disconnect_transfer(file_props)
            file_props.error = -3
            app.ged.raise_event(
                FileRequestError(conn=self._con,
                                 jid=app.get_jid_without_resource(to),
                                 file_props=file_props,
                                 error_msg=msg))

    def _proxy_auth_ok(self, proxy):
        """
        Called after authentication to proxy server
        """
        if not app.account_is_available(self._account):
            return
        file_props = FilesProp.getFileProp(self._account, proxy['sid'])
        iq = nbxmpp.Iq(to=proxy['initiator'], typ='set')
        auth_id = "au_" + proxy['sid']
        iq.setID(auth_id)
        query = iq.setTag('query', namespace=Namespace.BYTESTREAM)
        query.setAttr('sid', proxy['sid'])
        activate = query.setTag('activate')
        activate.setData(file_props.proxy_receiver)
        iq.setID(auth_id)
        self._con.connection.send(iq)

    def _on_bytestream_error(self, _con, iq_obj, _properties):
        id_ = iq_obj.getAttr('id')
        frm = helpers.get_full_jid_from_iq(iq_obj)
        query = iq_obj.getTag('query')
        app.proxy65_manager.error_cb(frm, query)
        jid = helpers.get_jid_from_iq(iq_obj)
        id_ = id_[3:]
        file_props = FilesProp.getFilePropBySid(id_)
        if not file_props:
            return
        file_props.error = -4
        app.ged.raise_event(
            FileRequestError(conn=self._con,
                             jid=app.get_jid_without_resource(jid),
                             file_props=file_props,
                             error_msg=''))
        raise nbxmpp.NodeProcessed

    def _on_bytestream_set(self, _con, iq_obj, _properties):
        target = iq_obj.getAttr('to')
        id_ = iq_obj.getAttr('id')
        query = iq_obj.getTag('query')
        sid = query.getAttr('sid')
        file_props = FilesProp.getFileProp(self._account, sid)
        streamhosts = []
        for item in query.getChildren():
            if item.getName() == 'streamhost':
                host_dict = {
                    'state': 0,
                    'target': target,
                    'id': id_,
                    'sid': sid,
                    'initiator': self._ft_get_from(iq_obj)
                }
                for attr in item.getAttrs():
                    host_dict[attr] = item.getAttr(attr)
                if 'host' not in host_dict:
                    continue
                if 'jid' not in host_dict:
                    continue
                if 'port' not in host_dict:
                    continue
                streamhosts.append(host_dict)
        file_props = FilesProp.getFilePropBySid(sid)
        if file_props is not None:
            if file_props.type_ == 's': # FIXME: remove fast xmlns
                # only psi do this
                if file_props.streamhosts:
                    file_props.streamhosts.extend(streamhosts)
                else:
                    file_props.streamhosts = streamhosts
                app.socks5queue.connect_to_hosts(
                    self._account,
                    sid,
                    self.send_success_connect_reply,
                    None)
                raise nbxmpp.NodeProcessed
        else:
            log.warning('Gajim got streamhosts for unknown transfer. '
                        'Ignoring it.')
            raise nbxmpp.NodeProcessed

        file_props.streamhosts = streamhosts
        def _connection_error(sid):
            self._connect_error(sid,
                                'item-not-found',
                                'cancel',
                                msg='Could not connect to given hosts')
        if file_props.type_ == 'r':
            app.socks5queue.connect_to_hosts(
                self._account,
                sid,
                self.send_success_connect_reply,
                _connection_error)
        raise nbxmpp.NodeProcessed

    def _on_result(self, _con, iq_obj, _properties):
        # if we want to respect xep-0065 we have to check for proxy
        # activation result in any result iq
        real_id = iq_obj.getAttr('id')
        if real_id is None:
            log.warning('Invalid IQ without id attribute:\n%s', iq_obj)
            raise nbxmpp.NodeProcessed
        if real_id is None or not real_id.startswith('au_'):
            return
        frm = self._ft_get_from(iq_obj)
        id_ = real_id[3:]
        file_props = FilesProp.getFilePropByTransportSid(self._account, id_)
        if file_props.streamhost_used:
            for host in file_props.proxyhosts:
                if host['initiator'] == frm and 'idx' in host:
                    app.socks5queue.activate_proxy(host['idx'])
                    raise nbxmpp.NodeProcessed

    def _on_bytestream_result(self, _con, iq_obj, _properties):
        frm = self._ft_get_from(iq_obj)
        real_id = iq_obj.getAttr('id')
        query = iq_obj.getTag('query')
        app.proxy65_manager.resolve_result(frm, query)

        try:
            streamhost = query.getTag('streamhost-used')
        except Exception: # this bytestream result is not what we need
            pass
        id_ = real_id[3:]
        file_props = FilesProp.getFileProp(self._account, id_)
        if file_props is None:
            raise nbxmpp.NodeProcessed
        if streamhost is None:
            # proxy approves the activate query
            if real_id.startswith('au_'):
                if file_props.streamhost_used is False:
                    raise nbxmpp.NodeProcessed
                if  not file_props.proxyhosts:
                    raise nbxmpp.NodeProcessed
                for host in file_props.proxyhosts:
                    if host['initiator'] == frm and \
                    query.getAttr('sid') == file_props.sid:
                        app.socks5queue.activate_proxy(host['idx'])
                        break
            raise nbxmpp.NodeProcessed
        jid = self._ft_get_streamhost_jid_attr(streamhost)
        if file_props.streamhost_used is True:
            raise nbxmpp.NodeProcessed

        if real_id.startswith('au_'):
            if file_props.stopped:
                self.remove_transfer(file_props)
            else:
                app.socks5queue.send_file(file_props, self._account, 'server')
            raise nbxmpp.NodeProcessed

        proxy = None
        if file_props.proxyhosts:
            for proxyhost in file_props.proxyhosts:
                if proxyhost['jid'] == jid:
                    proxy = proxyhost

        if file_props.stopped:
            self.remove_transfer(file_props)
            raise nbxmpp.NodeProcessed
        if proxy is not None:
            file_props.streamhost_used = True
            file_props.streamhosts.append(proxy)
            file_props.is_a_proxy = True
            idx = app.socks5queue.idx
            sender = Socks5SenderClient(app.idlequeue,
                                        idx,
                                        app.socks5queue,
                                        _sock=None,
                                        host=str(proxy['host']),
                                        port=int(proxy['port']),
                                        fingerprint=None,
                                        connected=False,
                                        file_props=file_props)
            sender.streamhost = proxy
            app.socks5queue.add_sockobj(self._account, sender)
            proxy['idx'] = sender.queue_idx
            app.socks5queue.on_success[file_props.sid] = self._proxy_auth_ok
            raise nbxmpp.NodeProcessed

        if file_props.stopped:
            self.remove_transfer(file_props)
        else:
            app.socks5queue.send_file(file_props, self._account, 'server')

        raise nbxmpp.NodeProcessed
