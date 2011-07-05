# -*- coding:utf-8 -*-
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


"""
Handles  Jingle File Transfer (XEP 0234)
"""

import gajim
import xmpp
from jingle_content import contents, JingleContent
from jingle_transport import JingleTransportICEUDP, JingleTransportSocks5
from common import helpers
from common.socks5 import Socks5Receiver
from common.connection_handlers_events import FileRequestReceivedEvent

import logging
log = logging.getLogger('gajim.c.jingle_ft')

STATE_NOT_STARTED = 0
STATE_INITIALIZED = 1
STATE_ACCEPTED = 2
STATE_TRANSPORT_INFO = 3
STATE_PROXY_ACTIVATED = 4
STATE_TRANSPORT_REPLACE = 5

class JingleFileTransfer(JingleContent):
    def __init__(self, session, transport=None, file_props=None,
    use_security=False):
        JingleContent.__init__(self, session, transport)

        log.info("transport value: %s" % transport)

        # events we might be interested in
        self.callbacks['session-initiate'] += [self.__on_session_initiate]
        self.callbacks['content-add'] += [self.__on_session_initiate]
        self.callbacks['session-accept'] += [self.__on_session_accept]
        self.callbacks['session-terminate'] += [self.__on_session_terminate]
        self.callbacks['transport-accept'] += [self.__on_transport_accept]
        self.callbacks['transport-replace'] += [self.__on_transport_replace]
        # fallback transport method
        self.callbacks['transport-reject'] += [self.__on_transport_reject]
        self.callbacks['transport-info'] += [self.__on_transport_info]
        self.callbacks['iq-result'] += [self.__on_iq_result]

        self.state = STATE_NOT_STARTED

        self.use_security = use_security

        self.file_props = file_props
        if file_props is None:
            self.weinitiate = False
        else:
            self.weinitiate = True

        if self.file_props is not None:
            self.file_props['sender'] = session.ourjid
            self.file_props['receiver'] = session.peerjid
            self.file_props['session-type'] = 'jingle'
            self.file_props['session-sid'] = session.sid
            self.file_props['transfered_size'] = []

        log.info("FT request: %s" % file_props)

        if transport is None:
            self.transport = JingleTransportSocks5()
            self.transport.set_connection(session.connection)
            self.transport.set_file_props(self.file_props)
            self.transport.set_our_jid(session.ourjid)
        log.info('ourjid: %s' % session.ourjid)

        if self.file_props is not None:
            self.file_props['sid'] = self.transport.sid

        self.session = session
        self.media = 'file'
        

    def __on_session_initiate(self, stanza, content, error, action):
        gajim.nec.push_incoming_event(FileRequestReceivedEvent(None,
            conn=self.session.connection, stanza=stanza, jingle_content=content,
            FT_content=self))

    def __on_session_accept(self, stanza, content, error, action):
        log.info("__on_session_accept")

        security = content.getTag('security')
        if not security: # responder can not verify our fingerprint
            self.use_security = False
            
        if self.state == STATE_TRANSPORT_REPLACE:
            # We ack the session accept
            response = stanza.buildReply('result')
            con = self.session.connection
            con.connection.send(response)
            # We send the file
            con.files_props[self.file_props['sid']] = self.file_props
            fp = open(self.file_props['file-name'], 'r')
            con.OpenStream( self.transport.sid, self.session.peerjid, 
                            fp,    blocksize=4096)
            raise xmpp.NodeProcessed
            

    def __on_session_terminate(self, stanza, content, error, action):
        log.info("__on_session_terminate")

    def __on_transport_accept(self, stanza, content, error, action):
        log.info("__on_transport_accept")

    def __on_transport_replace(self, stanza, content, error, action):
        log.info("__on_transport_replace")

    def __on_transport_reject(self, stanza, content, error, action):
        log.info("__on_transport_reject")

    def __on_transport_info(self, stanza, content, error, action):
        log.info("__on_transport_info")

        if not self.weinitiate: # proxy activated from initiator
            return
        if content.getTag('transport').getTag('candidate-error'):
            self.session.transport_replace()
            return
        streamhost_cid = content.getTag('transport').getTag('candidate-used').\
            getAttr('cid')
        streamhost_used = None
        for cand in self.transport.candidates:
            if cand['candidate_id'] == streamhost_cid:
                streamhost_used = cand
                break
        if streamhost_used == None:
            log.info("unknow streamhost")
            return
        if streamhost_used['type'] == 'proxy':
            self.file_props['streamhost-used'] = True
            for proxy in self.file_props['proxyhosts']:
                if proxy['host'] == streamhost_used['host'] and \
                proxy['port'] == streamhost_used['port'] and \
                proxy['jid'] == streamhost_used['jid']:
                    host_used = proxy
                    break
            if 'streamhosts' not in self.file_props:
                self.file_props['streamhosts'] = []
                self.file_props['streamhosts'].append(streamhost_used)
                self.file_props['is_a_proxy'] = True
                receiver = Socks5Receiver(gajim.idlequeue, streamhost_used,
                    self.file_props['sid'], self.file_props)
                gajim.socks5queue.add_receiver(self.session.connection.name,
                    receiver)
                streamhost_used['idx'] = receiver.queue_idx
                gajim.socks5queue.on_success[self.file_props['sid']] = \
                     self.transport._on_proxy_auth_ok
        else:
            jid = gajim.get_jid_without_resource(self.session.ourjid)
            gajim.socks5queue.send_file(self.file_props,
                self.session.connection.name)

    def __on_iq_result(self, stanza, content, error, action):
        log.info("__on_iq_result")

        if self.weinitiate and self.state == STATE_NOT_STARTED:
            self.state = STATE_INITIALIZED
            self.session.connection.files_props[self.file_props['sid']] = \
                self.file_props
            receiver = self.file_props['receiver']
            sender = self.file_props['sender']

            sha_str = helpers.get_auth_sha(self.file_props['sid'], sender,
                receiver)
            self.file_props['sha_str'] = sha_str

            port = gajim.config.get('file_transfers_port')

            fingerprint = None
            if self.use_security:
                fingerprint = 'server'
            listener = gajim.socks5queue.start_listener(port, sha_str,
                self._store_socks5_sid, self.file_props['sid'],
                fingerprint=fingerprint)

            if not listener:
                return
                # send error message, notify the user
        elif not self.weinitiate and self.state == STATE_NOT_STARTED:
            # session-accept iq-result
            if not self.negotiated:
                return
            self.state = STATE_ACCEPTED
            if not gajim.socks5queue.get_file_props(
            self.session.connection.name, self.file_props['sid']):
                gajim.socks5queue.add_file_props(self.session.connection.name,
                    self.file_props)
            fingerprint = None
            if self.use_security:
                fingerprint = 'client'
            gajim.socks5queue.connect_to_hosts(self.session.connection.name,
                self.file_props['sid'], self.send_candidate_used,
                self._on_connect_error, fingerprint=fingerprint)
        elif not self.weinitiate and self.state == STATE_ACCEPTED:
            # transport-info iq-result
            self.state = STATE_TRANSPORT_INFO
        elif self.weinitiate and self.state == STATE_INITIALIZED:
            # proxy activated
            self.state = STATE_PROXY_ACTIVATED
        
    def send_candidate_used(self, streamhost):
        """
        send candidate-used stanza
        """
        log.info('send_candidate_used')
        if streamhost is None:
            return

        content = xmpp.Node('content')
        content.setAttr('creator', 'initiator')
        content.setAttr('name', self.name)

        transport = xmpp.Node('transport')
        transport.setNamespace(xmpp.NS_JINGLE_BYTESTREAM)
        transport.setAttr('sid', self.transport.sid)

        candidateused = xmpp.Node('candidate-used')
        candidateused.setAttr('cid', streamhost['cid'])

        transport.addChild(node=candidateused)
        content.addChild(node=transport)

        self.session.send_transport_info(content)

    def _on_connect_error(self, to, _id, sid, code=404):
        if code == 404 and self.file_props['sid'] == sid:
            self.send_error_candidate()
            
        log.info('connect error, sid=' + sid)

    def _fill_content(self, content):
        description_node = xmpp.simplexml.Node(
            tag=xmpp.NS_JINGLE_FILE_TRANSFER + ' description')

        sioffer = xmpp.simplexml.Node(tag='offer')
        file_tag = sioffer.setTag('file', namespace=xmpp.NS_FILE)
        file_tag.setAttr('name', self.file_props['name'])
        file_tag.setAttr('size', self.file_props['size'])
        desc = file_tag.setTag('desc')
        if 'desc' in self.file_props:
            desc.setData(self.file_props['desc'])

        description_node.addChild(node=sioffer)

        if self.use_security:
            security = xmpp.simplexml.Node(
                tag=xmpp.NS_JINGLE_XTLS + ' security')
            # TODO: add fingerprint element
            for m in ('x509', ): # supported authentication methods
                method = xmpp.simplexml.Node(tag='method')
                method.setAttr('name', m)
                security.addChild(node=method)
            content.addChild(node=security)

        content.addChild(node=description_node)

    def _store_socks5_sid(self, sid, hash_id):
        # callback from socsk5queue.start_listener
        self.file_props['hash'] = hash_id

def get_content(desc):
    return JingleFileTransfer

contents[xmpp.NS_JINGLE_FILE_TRANSFER] = get_content
