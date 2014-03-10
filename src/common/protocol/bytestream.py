# -*- coding:utf-8 -*-
## src/common/connection_handlers.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
##                         Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Jean-Marie Traissard <jim AT lapin.org>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import socket
import base64
from gi.repository import GLib
import time

import nbxmpp
from common import gajim
from common import helpers
from common import dataforms
from common import ged
from common import jingle_xtls
from common.file_props import FilesProp
from common.socks5 import Socks5SenderClient

import logging
log = logging.getLogger('gajim.c.p.bytestream')

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


class ConnectionBytestream:

    def __init__(self):
        gajim.ged.register_event_handler('file-request-received', ged.GUI1,
            self._nec_file_request_received)

    def cleanup(self):
        gajim.ged.remove_event_handler('file-request-received', ged.GUI1,
            self._nec_file_request_received)

    def _ft_get_our_jid(self):
        our_jid = gajim.get_jid_from_account(self.name)
        resource = self.server_resource
        return our_jid + '/' + resource

    def _ft_get_receiver_jid(self, file_props):
        return file_props.receiver.jid + '/' + file_props.receiver.resource

    def _ft_get_from(self, iq_obj):
        return helpers.get_full_jid_from_iq(iq_obj)

    def _ft_get_streamhost_jid_attr(self, streamhost):
        return helpers.parse_jid(streamhost.getAttr('jid'))

    def send_file_request(self, file_props):
        """
        Send iq for new FT request
        """
        if not self.connection or self.connected < 2:
            return
        file_props.sender = self._ft_get_our_jid()
        fjid = self._ft_get_receiver_jid(file_props)
        iq = nbxmpp.Iq(to=fjid, typ='set')
        iq.setID(file_props.sid)
        si = iq.setTag('si', namespace=nbxmpp.NS_SI)
        si.setAttr('profile', nbxmpp.NS_FILE)
        si.setAttr('id', file_props.sid)
        file_tag = si.setTag('file', namespace=nbxmpp.NS_FILE)
        file_tag.setAttr('name', file_props.name)
        file_tag.setAttr('size', file_props.size)
        desc = file_tag.setTag('desc')
        if file_props.desc:
            desc.setData(file_props.desc)
        file_tag.setTag('range')
        feature = si.setTag('feature', namespace=nbxmpp.NS_FEATURE)
        _feature = nbxmpp.DataForm(typ='form')
        feature.addChild(node=_feature)
        field = _feature.setField('stream-method')
        field.setAttr('type', 'list-single')
        field.addOption(nbxmpp.NS_BYTESTREAM)
        field.addOption(nbxmpp.NS_IBB)
        self.connection.send(iq)

    def send_file_approval(self, file_props):
        """
        Send iq, confirming that we want to download the file
        """
        # user response to ConfirmationDialog may come after we've disconneted
        if not self.connection or self.connected < 2:
            return

        # file transfer initiated by a jingle session
        log.info("send_file_approval: jingle session accept")
        if file_props.session_type == 'jingle':
            session = self.get_jingle_session(file_props.sender,
                file_props.sid)
            if not session:
                return
            content = None
            for c in session.contents.values():
                if c.transport.sid == file_props.transport_sid:
                    content = c
                    break
            if not content:
                return
            if not session.accepted:
                content = session.get_content('file', content.name)
                if content.use_security:
                    fingerprint = content.x509_fingerprint
                    if not jingle_xtls.check_cert(
                    gajim.get_jid_without_resource(file_props.sender),
                    fingerprint):
                        id_ = jingle_xtls.send_cert_request(self,
                            file_props.sender)
                        jingle_xtls.key_exchange_pend(id_,
                            content.on_cert_received, [])
                        return
                session.approve_session()

            session.approve_content('file', content.name)
            return

        iq = nbxmpp.Iq(to=file_props.sender, typ='result')
        iq.setAttr('id', file_props.request_id)
        si = iq.setTag('si', namespace=nbxmpp.NS_SI)
        if file_props.offset:
            file_tag = si.setTag('file', namespace=nbxmpp.NS_FILE)
            range_tag = file_tag.setTag('range')
            range_tag.setAttr('offset', file_props.offset)
        feature = si.setTag('feature', namespace=nbxmpp.NS_FEATURE)
        _feature = nbxmpp.DataForm(typ='submit')
        feature.addChild(node=_feature)
        field = _feature.setField('stream-method')
        field.delAttr('type')
        if nbxmpp.NS_BYTESTREAM in file_props.stream_methods:
            field.setValue(nbxmpp.NS_BYTESTREAM)
        else:
            file_props.transport_sid = file_props.sid
            field.setValue(nbxmpp.NS_IBB)
        self.connection.send(iq)

    def send_file_rejection(self, file_props, code='403', typ=None):
        """
        Inform sender that we refuse to download the file

        typ is used when code = '400', in this case typ can be 'strean' for
        invalid stream or 'profile' for invalid profile
        """
        # user response to ConfirmationDialog may come after we've disconneted
        if not self.connection or self.connected < 2:
            return
        if file_props.session_type == 'jingle':
            jingle = self._sessions[file_props.sid]
            jingle.cancel_session()
            return
        iq = nbxmpp.Iq(to=file_props.sender, typ='error')
        iq.setAttr('id', file_props.request_id)
        if code == '400' and typ in ('stream', 'profile'):
            name = 'bad-request'
            text = ''
        else:
            name = 'forbidden'
            text = 'Offer Declined'
        err = nbxmpp.ErrorNode(code=code, typ='cancel', name=name, text=text)
        if code == '400' and typ in ('stream', 'profile'):
            if typ == 'stream':
                err.setTag('no-valid-streams', namespace=nbxmpp.NS_SI)
            else:
                err.setTag('bad-profile', namespace=nbxmpp.NS_SI)
        iq.addChild(node=err)
        self.connection.send(iq)

    def _siResultCB(self, con, iq_obj):
        file_props = FilesProp.getFileProp(self.name, iq_obj.getAttr('id'))
        if not file_props:
            return
        if file_props.request_id:
            # we have already sent streamhosts info
            return
        file_props.receiver = self._ft_get_from(iq_obj)
        si = iq_obj.getTag('si')
        file_tag = si.getTag('file')
        range_tag = None
        if file_tag:
            range_tag = file_tag.getTag('range')
        if range_tag:
            offset = range_tag.getAttr('offset')
            if offset:
                file_props.offset = int(offset)
            length = range_tag.getAttr('length')
            if length:
                file_props.length = int(length)
        feature = si.setTag('feature')
        if feature.getNamespace() != nbxmpp.NS_FEATURE:
            return
        form_tag = feature.getTag('x')
        form = nbxmpp.DataForm(node=form_tag)
        field = form.getField('stream-method')
        if field.getValue() == nbxmpp.NS_BYTESTREAM:
            self._send_socks5_info(file_props)
            raise nbxmpp.NodeProcessed
        if field.getValue() == nbxmpp.NS_IBB:
            sid = file_props.sid
            file_props.transport_sid = sid
            fp = open(file_props.file_name, 'r')
            self.OpenStream(sid, file_props.receiver, fp)
            raise nbxmpp.NodeProcessed

    def _siSetCB(self, con, iq_obj):
        from common.connection_handlers_events import FileRequestReceivedEvent
        gajim.nec.push_incoming_event(FileRequestReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_file_request_received(self, obj):
        pass

    def _siErrorCB(self, con, iq_obj):
        si = iq_obj.getTag('si')
        profile = si.getAttr('profile')
        if profile != nbxmpp.NS_FILE:
            return
        file_props = FilesProp.getFileProp(con.name, iq_obj.getAttr('id'))
        if not file_props:
            return
        jid = self._ft_get_from(iq_obj)
        file_props.error = -3
        from common.connection_handlers_events import FileRequestErrorEvent
        gajim.nec.push_incoming_event(FileRequestErrorEvent(None, conn=self,
            jid=jid, file_props=file_props, error_msg=''))
        raise nbxmpp.NodeProcessed

class ConnectionSocks5Bytestream(ConnectionBytestream):

    def send_success_connect_reply(self, streamhost):
        """
        Send reply to the initiator of FT that we made a connection
        """
        if not self.connection or self.connected < 2:
            return
        if streamhost is None:
            return None
        iq = nbxmpp.Iq(to=streamhost['initiator'], typ='result',
                frm=streamhost['target'])
        iq.setAttr('id', streamhost['id'])
        query = iq.setTag('query', namespace=nbxmpp.NS_BYTESTREAM)
        stream_tag = query.setTag('streamhost-used')
        stream_tag.setAttr('jid', streamhost['jid'])
        self.connection.send(iq)

    def stop_all_active_file_transfers(self, contact):
        """
        Stop all active transfer to or from the given contact
        """
        for file_props in FilesProp.getAllFileProp():
            if is_transfer_stopped(file_props):
                continue
            receiver_jid = file_props.receiver
            if contact.get_full_jid() == receiver_jid:
                file_props.error = -5
                self.remove_transfer(file_props)
                from common.connection_handlers_events import \
                    FileRequestErrorEvent
                gajim.nec.push_incoming_event(FileRequestErrorEvent(None,
                    conn=self, jid=contact.jid, file_props=file_props,
                    error_msg=''))
            sender_jid = file_props.sender
            if contact.get_full_jid() == sender_jid:
                file_props.error = -3
                self.remove_transfer(file_props)

    def remove_all_transfers(self):
        """
        Stop and remove all active connections from the socks5 pool
        """
        for file_props in FilesProp.getAllFileProp():
            self.remove_transfer(file_props, remove_from_list=False)

    def remove_transfer(self, file_props, remove_from_list=True):
        if file_props is None:
            return
        self.disconnect_transfer(file_props)
        sid = file_props.sid

    def disconnect_transfer(self, file_props):
        if file_props is None:
            return
        if file_props.hash_:
            gajim.socks5queue.remove_sender(file_props.hash_)

        if file_props.streamhosts:
            for host in file_props.streamhosts:
                if 'idx' in host and host['idx'] > 0:
                    gajim.socks5queue.remove_receiver(host['idx'])
                    gajim.socks5queue.remove_sender(host['idx'])

    def _send_socks5_info(self, file_props):
        """
        Send iq for the present streamhosts and proxies
        """
        if not self.connection or self.connected < 2:
            return
        receiver = file_props.receiver
        sender = file_props.sender

        sha_str = helpers.get_auth_sha(file_props.sid, sender, receiver)
        file_props.sha_str = sha_str

        port = gajim.config.get('file_transfers_port')
        listener = gajim.socks5queue.start_listener(port, sha_str,
                self._result_socks5_sid, file_props)
        if not listener:
            file_props.error = -5
            from common.connection_handlers_events import FileRequestErrorEvent
            gajim.nec.push_incoming_event(FileRequestErrorEvent(None, conn=self,
                jid=receiver, file_props=file_props, error_msg=''))
            self._connect_error(receiver, file_props.sid,
                    file_props.sid, code=406)
        else:
            iq = nbxmpp.Iq(to=receiver, typ='set')
            file_props.request_id = 'id_' + file_props.sid
            iq.setID(file_props.request_id)
            query = iq.setTag('query', namespace=nbxmpp.NS_BYTESTREAM)
            query.setAttr('sid', file_props.sid)

            self._add_addiditional_streamhosts_to_query(query, file_props)
            self._add_local_ips_as_streamhosts_to_query(query, file_props)
            self._add_proxy_streamhosts_to_query(query, file_props)
            self._add_upnp_igd_as_streamhost_to_query(query, file_props, iq)
            # Upnp-igd is ascynchronous, so it will send the iq itself

    def _add_streamhosts_to_query(self, query, sender, port, hosts):
        for host in hosts:
            streamhost = nbxmpp.Node(tag='streamhost')
            query.addChild(node=streamhost)
            streamhost.setAttr('port', str(port))
            streamhost.setAttr('host', host)
            streamhost.setAttr('jid', sender)

    def _add_local_ips_as_streamhosts_to_query(self, query, file_props):
        if not gajim.config.get_per('accounts', self.name, 'ft_send_local_ips'):
            return
        try:
            my_ips = [self.peerhost[0]] # The ip we're connected to server with
            # all IPs from local DNS
            for addr in socket.getaddrinfo(socket.gethostname(), None):
                if not addr[4][0] in my_ips and not addr[4][0].startswith('127'):
                    my_ips.append(addr[4][0])

            sender = file_props.sender
            port = gajim.config.get('file_transfers_port')
            self._add_streamhosts_to_query(query, sender, port, my_ips)
        except socket.gaierror:
            from common.connection_handlers_events import InformationEvent
            gajim.nec.push_incoming_event(InformationEvent(None, conn=self,
                level='error', pri_txt=_('Wrong host'),
                sec_txt=_('Invalid local address? :-O')))

    def _add_addiditional_streamhosts_to_query(self, query, file_props):
        sender = file_props.sender
        port = gajim.config.get('file_transfers_port')
        ft_add_hosts_to_send = gajim.config.get('ft_add_hosts_to_send')
        additional_hosts = []
        if ft_add_hosts_to_send:
            additional_hosts = [e.strip() for e in ft_add_hosts_to_send.split(',')]
        else:
            additional_hosts = []
        self._add_streamhosts_to_query(query, sender, port, additional_hosts)

    def _add_upnp_igd_as_streamhost_to_query(self, query, file_props, iq):
        if not gajim.HAVE_UPNP_IGD:
            self.connection.send(iq)
            return

        def ip_is_local(ip):
            if '.' not in ip:
                # it's an IPv6
                return True
            ip_s = ip.split('.')
            ip_l = long(ip_s[0])<<24 | long(ip_s[1])<<16 | long(ip_s[2])<<8 | \
                 long(ip_s[3])
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


        my_ip = self.peerhost[0]

        if not ip_is_local(my_ip):
            self.connection.send(iq)
            return

        self.no_gupnp_reply_id = 0

        def cleanup_gupnp():
            if self.no_gupnp_reply_id:
                GLib.source_remove(self.no_gupnp_reply_id)
                self.no_gupnp_reply_id = 0
            gajim.gupnp_igd.disconnect(self.ok_id)
            gajim.gupnp_igd.disconnect(self.fail_id)

        def ok(s, proto, ext_ip, re, ext_port, local_ip, local_port, desc):
            log.debug('Got GUPnP-IGD answer: external: %s:%s, internal: %s:%s',
                ext_ip, ext_port, local_ip, local_port)
            if local_port != gajim.config.get('file_transfers_port'):
                sender = file_props.sender
                receiver = file_props.receiver
                sha_str = helpers.get_auth_sha(file_props.sid, sender,
                    receiver)
                listener = gajim.socks5queue.start_listener(local_port, sha_str,
                    self._result_socks5_sid, file_props.sid)
                if listener:
                    self._add_streamhosts_to_query(query, sender, ext_port,
                        [ext_ip])
            else:
                self._add_streamhosts_to_query(query, file_props.sender,
                    ext_port, [ext_ip])
            self.connection.send(iq)
            cleanup_gupnp()

        def fail(s, error, proto, ext_ip, local_ip, local_port, desc):
            log.debug('Got GUPnP-IGD error : %s', str(error))
            self.connection.send(iq)
            cleanup_gupnp()

        def no_upnp_reply():
            log.debug('Got not GUPnP-IGD answer')
            # stop trying to use it
            gajim.HAVE_UPNP_IGD = False
            self.no_gupnp_reply_id = 0
            self.connection.send(iq)
            cleanup_gupnp()
            return False


        self.ok_id = gajim.gupnp_igd.connect('mapped-external-port', ok)
        self.fail_id = gajim.gupnp_igd.connect('error-mapping-port', fail)

        port = gajim.config.get('file_transfers_port')
        self.no_gupnp_reply_id = GLib.timeout_add_seconds(10, no_upnp_reply)
        gajim.gupnp_igd.add_port('TCP', 0, my_ip, port, 3600,
            'Gajim file transfer')

    def _add_proxy_streamhosts_to_query(self, query, file_props):
        proxyhosts = self._get_file_transfer_proxies_from_config(file_props)
        if proxyhosts:
            file_props.proxy_receiver = file_props.receiver
            file_props.proxy_sender = file_props.sender
            file_props.proxyhosts = proxyhosts

            for proxyhost in proxyhosts:
                self._add_streamhosts_to_query(query, proxyhost['jid'],
                proxyhost['port'], [proxyhost['host']])

    def _get_file_transfer_proxies_from_config(self, file_props):
        configured_proxies = gajim.config.get_per('accounts', self.name,
                'file_transfer_proxies')
        shall_use_proxies = gajim.config.get_per('accounts', self.name,
                'use_ft_proxies')
        if shall_use_proxies and configured_proxies:
            proxyhost_dicts = []
            proxies = [item.strip() for item in configured_proxies.split(',')]
            default_proxy = gajim.proxy65_manager.get_default_for_name(self.name)
            if default_proxy:
                # add/move default proxy at top of the others
                if default_proxy in proxies:
                    proxies.remove(default_proxy)
                proxies.insert(0, default_proxy)

            for proxy in proxies:
                (host, _port, jid) = gajim.proxy65_manager.get_proxy(proxy, self.name)
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
        else:
            return []

    def _result_socks5_sid(self, sid, hash_id):
        """
        Store the result of SHA message from auth
        """
        file_props = FilesProp.getFilePropBySid(sid)
        file_props.hash_ = hash_id
        return

    def _connect_error(self,sid, code=404):
        """
        Called when there is an error establishing BS connection, or when
        connection is rejected
        """
        if not self.connection or self.connected < 2:
            return
        file_props = FilesProp.getFileProp(self.name, sid)
        if file_props is None:
            log.error('can not send iq error on failed transfer')
            return
        msg_dict = {
                404: 'Could not connect to given hosts',
                405: 'Cancel',
                406: 'Not acceptable',
        }
        msg = msg_dict[code]
        if file_props.type_ == 's':
            to = file_props.receiver
        else:
            to = file_props.sender
        iq = nbxmpp.Iq(to=to,     typ='error')
        iq.setAttr('id', file_props.sid)
        err = iq.setTag('error')
        err.setAttr('code', str(code))
        err.setData(msg)
        self.connection.send(iq)
        if code == 404:
            self.disconnect_transfer(file_props)
            file_props.error = -3
            from common.connection_handlers_events import \
                FileRequestErrorEvent
            gajim.nec.push_incoming_event(FileRequestErrorEvent(None,
                conn=self, jid=to, file_props=file_props, error_msg=msg))

    def _proxy_auth_ok(self, proxy):
        """
        Called after authentication to proxy server
        """
        if not self.connection or self.connected < 2:
            return
        file_props = FilesProp.getFileProp(self.name, proxy['sid'])
        iq = nbxmpp.Iq(to=proxy['initiator'], typ='set')
        auth_id = "au_" + proxy['sid']
        iq.setID(auth_id)
        query = iq.setTag('query', namespace=nbxmpp.NS_BYTESTREAM)
        query.setAttr('sid', proxy['sid'])
        activate = query.setTag('activate')
        activate.setData(file_props.proxy_receiver)
        iq.setID(auth_id)
        self.connection.send(iq)

    # register xmpppy handlers for bytestream and FT stanzas
    def _bytestreamErrorCB(self, con, iq_obj):
        id_ = iq_obj.getAttr('id')
        frm = helpers.get_full_jid_from_iq(iq_obj)
        query = iq_obj.getTag('query')
        gajim.proxy65_manager.error_cb(frm, query)
        jid = helpers.get_jid_from_iq(iq_obj)
        id_ = id_[3:]
        file_props = FilesProp.getFilePropBySid(id_)
        if not file_props:
            return
        file_props.error = -4
        from common.connection_handlers_events import FileRequestErrorEvent
        gajim.nec.push_incoming_event(FileRequestErrorEvent(None, conn=self,
            jid=jid, file_props=file_props, error_msg=''))
        raise nbxmpp.NodeProcessed

    def _bytestreamSetCB(self, con, iq_obj):
        target = iq_obj.getAttr('to')
        id_ = iq_obj.getAttr('id')
        query = iq_obj.getTag('query')
        sid = query.getAttr('sid')
        file_props = FilesProp.getFileProp(self.name, sid)
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
                gajim.socks5queue.connect_to_hosts(self.name, sid,
                        self.send_success_connect_reply, None)
                raise nbxmpp.NodeProcessed
        else:
            log.warning('Gajim got streamhosts for unknown transfer. Ignoring it.')
            raise nbxmpp.NodeProcessed

        file_props.streamhosts = streamhosts
        if file_props.type_ == 'r':
            gajim.socks5queue.connect_to_hosts(self.name, sid,
                    self.send_success_connect_reply, self._connect_error)
        raise nbxmpp.NodeProcessed

    def _ResultCB(self, con, iq_obj):
        # if we want to respect xep-0065 we have to check for proxy
        # activation result in any result iq
        real_id = iq_obj.getAttr('id')
        if not real_id.startswith('au_'):
            return
        frm = self._ft_get_from(iq_obj)
        id_ = real_id[3:]
        file_props = FilesProp.getFilePropBySid(id_)
        if file_props.streamhost_used:
            for host in file_props.proxyhosts:
                if host['initiator'] == frm and 'idx' in host:
                    gajim.socks5queue.activate_proxy(host['idx'])
                    raise nbxmpp.NodeProcessed

    def _bytestreamResultCB(self, con, iq_obj):
        frm = self._ft_get_from(iq_obj)
        real_id = iq_obj.getAttr('id')
        query = iq_obj.getTag('query')
        gajim.proxy65_manager.resolve_result(frm, query)

        try:
            streamhost = query.getTag('streamhost-used')
        except Exception: # this bytestream result is not what we need
            pass
        id_ = real_id[3:]
        file_props = FilesProp.getFileProp(self.name, id_)
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
                        gajim.socks5queue.activate_proxy(host['idx'])
                        break
            raise nbxmpp.NodeProcessed
        jid = self._ft_get_streamhost_jid_attr(streamhost)
        if file_props.streamhost_used is True:
            raise nbxmpp.NodeProcessed

        if real_id.startswith('au_'):
            if file_props.stopped:
                self.remove_transfer(file_props)
            else:
                gajim.socks5queue.send_file(file_props, self.name)
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
            idx = gajim.socks5queue.idx
            sender = Socks5SenderClient(gajim.idlequeue, idx,
                gajim.socks5queue, _sock=None, host=str(proxy['host']),
                port=int(proxy['port']), fingerprint=None,
                connected=False, file_props=file_props)
            sender.streamhost = proxy
            gajim.socks5queue.add_sockobj(self.name, sender)
            proxy['idx'] = sender.queue_idx
            gajim.socks5queue.on_success[file_props.sid] = self._proxy_auth_ok
            raise nbxmpp.NodeProcessed

        else:
            if file_props.stopped:
                self.remove_transfer(file_props)
            else:
                gajim.socks5queue.send_file(file_props, self.name, 'server')

        raise nbxmpp.NodeProcessed


class ConnectionIBBytestream(ConnectionBytestream):

    def __init__(self):
        ConnectionBytestream.__init__(self)
        self._streams = {}
        self.last_sent_ibb_id = None

    def IBBIqHandler(self, conn, stanza):
        """
        Handles streams state change. Used internally.
        """
        typ = stanza.getType()
        log.debug('IBBIqHandler called typ->%s' % typ)
        if typ == 'set' and stanza.getTag('open', namespace=nbxmpp.NS_IBB):
            self.StreamOpenHandler(conn, stanza)
        elif typ == 'set' and stanza.getTag('close', namespace=nbxmpp.NS_IBB):
            self.StreamCloseHandler(conn, stanza)
        elif typ == 'result':
            self.SendHandler()
        elif typ == 'error':
            gajim.socks5queue.error_cb()
        else:
            conn.send(nbxmpp.Error(stanza, nbxmpp.ERR_BAD_REQUEST))
        raise nbxmpp.NodeProcessed

    def StreamOpenHandler(self, conn, stanza):
        """
        Handles opening of new incoming stream. Used internally.
        """
        err = None
        sid = stanza.getTagAttr('open', 'sid')
        blocksize = stanza.getTagAttr('open', 'block-size')
        log.debug('StreamOpenHandler called sid->%s blocksize->%s' % (sid,
            blocksize))
        file_props = FilesProp.getFilePropByTransportSid(self.name, sid)
        try:
            blocksize = int(blocksize)
        except:
            err = nbxmpp.ERR_BAD_REQUEST
        if not sid or not blocksize:
            err = nbxmpp.ERR_BAD_REQUEST
        elif not file_props:
            err = nbxmpp.ERR_UNEXPECTED_REQUEST
        if err:
            rep = nbxmpp.Error(stanza, err)
        else:
            log.debug("Opening stream: id %s, block-size %s" % (sid, blocksize))
            rep = nbxmpp.Protocol('iq', stanza.getFrom(), 'result',
                stanza.getTo(), {'id': stanza.getID()})
            file_props.block_size = blocksize
            file_props.direction = '<'
            file_props.seq = 0
            file_props.received_len = 0
            file_props.last_time = time.time()
            file_props.error = 0
            file_props.paused = False
            file_props.connected = True
            file_props.completed = False
            file_props.disconnect_cb = None
            file_props.continue_cb = None
            file_props.syn_id = stanza.getID()
            file_props.fp = open(file_props.file_name, 'w')
        conn.send(rep)

    def CloseIBBStream(self, file_props):
        file_props.connected = False
        file_props.fp.close()
        file_props.stopped = True
        self.connection.send(nbxmpp.Protocol('iq',
            file_props.direction[1:], 'set',
            payload=[nbxmpp.Node(nbxmpp.NS_IBB + ' close',
            {'sid':file_props.sid})]))
        if file_props.session_type == 'jingle':
            peerjid = \
             file_props.receiver if file_props.type_ == 's' else file_props.sender
            session = self.get_jingle_session(peerjid, file_props.sid, 'file')
            # According to the xep, the initiator also cancels the jingle session
            # if there are no more files to send using IBB
            if session.weinitiate:
                session.cancel_session()

    def OpenStream(self, sid, to, fp, blocksize=4096):
        """
        Start new stream. You should provide stream id 'sid', the endpoind jid
        'to', the file object containing info for send 'fp'. Also the desired
        blocksize can be specified.
        Take into account that recommended stanza size is 4k and IBB uses
        base64 encoding that increases size of data by 1/3.
        """
        if not nbxmpp.JID(to).getResource():
            return
        file_props = FilesProp.getFilePropBySid(sid)
        file_props.direction = '|>' + to
        file_props.block_size = blocksize
        file_props.fp = fp
        file_props.seq = 0
        file_props.error = 0
        file_props.paused = False
        file_props.received_len = 0
        file_props.last_time = time.time()
        file_props.connected = True
        file_props.completed = False
        file_props.disconnect_cb = None
        file_props.continue_cb = None
        syn = nbxmpp.Protocol('iq', to, 'set', payload=[nbxmpp.Node(
            nbxmpp.NS_IBB + ' open', {'sid': file_props.transport_sid,
            'block-size': blocksize, 'stanza': 'iq'})])
        self.connection.send(syn)
        file_props.syn_id = syn.getID()
        return file_props

    def SendHandler(self):
        """
        Send next portion of data if it is time to do it. Used internally.
        """
        log.debug('SendHandler called')
        for file_props in FilesProp.getAllFileProp():
            if not file_props.direction:
                # it's socks5 bytestream
                continue
            sid = file_props.sid
            if file_props.direction[:2] == '|>':
                # We waitthat other part accept stream
                continue
            if file_props.direction[0] == '>':
                if file_props.paused:
                    continue
                if not file_props.connected:
                    #TODO: Reply with out of order error
                    continue
                chunk = file_props.fp.read(file_props.block_size)
                if chunk:
                    datanode = nbxmpp.Node(nbxmpp.NS_IBB + ' data', {
                        'sid': file_props.transport_sid,
                        'seq': file_props.seq}, base64.b64encode(chunk.encode(
                        'utf-8')).decode('utf-8'))
                    file_props.seq += 1
                    file_props.started = True
                    if file_props.seq == 65536:
                        file_props.seq = 0
                    self.last_sent_ibb_id = self.connection.send(
                        nbxmpp.Protocol(name='iq', to=file_props.direction[1:],
                        typ='set', payload=[datanode]))
                    current_time = time.time()
                    file_props.elapsed_time += current_time - file_props.last_time
                    file_props.last_time = current_time
                    file_props.received_len += len(chunk)
                    gajim.socks5queue.progress_transfer_cb(self.name,
                        file_props)
                else:
                    # notify the other side about stream closing
                    # notify the local user about sucessfull send
                    # delete the local stream
                    self.connection.send(nbxmpp.Protocol('iq',
                        file_props.direction[1:], 'set',
                        payload=[nbxmpp.Node(nbxmpp.NS_IBB + ' close',
                        {'sid': file_props.transport_sid})]))
                    file_props.completed = True

    def IBBMessageHandler(self, conn, stanza):
        """
        Receive next portion of incoming datastream and store it write
        it to temporary file. Used internally.
        """
        sid = stanza.getTagAttr('data', 'sid')
        seq = stanza.getTagAttr('data', 'seq')
        data = stanza.getTagData('data')
        log.debug('ReceiveHandler called sid->%s seq->%s' % (sid, seq))
        try:
            seq = int(seq)
            data = base64.b64decode(data.encode('utf-8')).decode('utf-8')
        except Exception:
            seq = ''
            data = ''
        err = None
        file_props = FilesProp.getFilePropByTransportSid(self.name, sid)
        if file_props is None:
            err = nbxmpp.ERR_ITEM_NOT_FOUND
        else:
            if not data:
                err = nbxmpp.ERR_BAD_REQUEST
            elif seq != file_props.seq:
                err = nbxmpp.ERR_UNEXPECTED_REQUEST
            else:
                log.debug('Successfull receive sid->%s %s+%s bytes' % (sid,
                    file_props.fp.tell(), len(data)))
                file_props.seq += 1
                file_props.started = True
                file_props.fp.write(data)
                current_time = time.time()
                file_props.elapsed_time += current_time - file_props.last_time
                file_props.last_time = current_time
                file_props.received_len += len(data)
                gajim.socks5queue.progress_transfer_cb(self.name, file_props)
                if file_props.received_len >= file_props.size:
                    file_props.completed = True
        if err:
            log.debug('Error on receive: %s' % err)
            conn.send(nbxmpp.Error(nbxmpp.Iq(to=stanza.getFrom(),
                frm=stanza.getTo(),
                payload=[nbxmpp.Node(nbxmpp.NS_IBB + ' close')]), err, reply=0))
        else:
            return True

    def StreamCloseHandler(self, conn, stanza):
        """
        Handle stream closure due to all data transmitted.
        Raise xmpppy event specifying successfull data receive.
        """
        sid = stanza.getTagAttr('close', 'sid')
        log.debug('StreamCloseHandler called sid->%s' % sid)
        # look in sending files
        file_props = FilesProp.getFilePropByTransportSid(self.name, sid)
        if file_props:
            reply = stanza.buildReply('result')
            reply.delChild('close')
            conn.send(reply)
            # look in receiving files
            file_props.fp.close()
            file_props.completed = file_props.received_len >= file_props.size
            if not file_props.completed:
                file_props.error = -1
            gajim.socks5queue.complete_transfer_cb(self.name, file_props)
        else:
            conn.send(nbxmpp.Error(stanza, nbxmpp.ERR_ITEM_NOT_FOUND))

    def IBBAllIqHandler(self, conn, stanza):
        """
        Handle remote side reply about if it agree or not to receive our
        datastream.
        Used internally. Raises xmpppy event specfiying if the data transfer
        is agreed upon.
        """
        syn_id = stanza.getID()
        log.debug('IBBAllIqHandler called syn_id->%s' % syn_id)
        for file_props in FilesProp.getAllFileProp():
            if not file_props.direction or not file_props.connected:
                # It's socks5 bytestream
                # Or we closed the IBB stream
                continue
            if file_props.syn_id == syn_id:
                if stanza.getType() == 'error':
                    if file_props.direction[0] == '<':
                        conn.Event('IBB', 'ERROR ON RECEIVE', file_props)
                    else:
                        conn.Event('IBB', 'ERROR ON SEND', file_props)
                elif stanza.getType() == 'result':
                    if file_props.direction[0] == '|':
                        file_props.direction = file_props.direction[1:]
                        self.SendHandler()
                    else:
                        conn.send(nbxmpp.Error(stanza,
                            nbxmpp.ERR_UNEXPECTED_REQUEST))
                break
        else:
            if stanza.getTag('data'):
                sid = stanza.getTagAttr('data', 'sid')
                file_props = FilesProp.getFilePropByTransportSid(self.name, sid)
                if file_props.connected and self.IBBMessageHandler(conn,
                stanza):
                    reply = stanza.buildReply('result')
                    reply.delChild('data')
                    conn.send(reply)
                    raise nbxmpp.NodeProcessed
            elif syn_id == self.last_sent_ibb_id:
                self.SendHandler()

class ConnectionSocks5BytestreamZeroconf(ConnectionSocks5Bytestream):

    def _ft_get_from(self, iq_obj):
        return iq_obj.getFrom()

    def _ft_get_our_jid(self):
        return gajim.get_jid_from_account(self.name)

    def _ft_get_receiver_jid(self, file_props):
        return file_props.receiver.jid

    def _ft_get_streamhost_jid_attr(self, streamhost):
        return streamhost.getAttr('jid')
