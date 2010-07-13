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

import logging

log = logging.getLogger('gajim.c.jingle_ft')


class JingleFileTransfer(JingleContent):
    def __init__(self, session, transport=None, file_props=None):
        JingleContent.__init__(self, session, transport)
        
        log.info("transport value: %s" % transport)
        
        #events we might be interested in
        self.callbacks['session-initiate'] += [self.__on_session_initiate]
        self.callbacks['session-accept'] += [self.__on_session_accept]
        self.callbacks['session-terminate'] += [self.__on_session_terminate]
        self.callbacks['transport-accept'] += [self.__on_transport_accept]
        self.callbacks['transport-replace'] += [self.__on_transport_replace]    #fallback transport method
        self.callbacks['transport-reject'] += [self.__on_transport_reject]
        self.callbacks['transport-info'] += [self.__on_transport_info]
        self.callbacks['iq-result'] += [self.__on_iq_result]

        self.file_props = file_props
        if file_props is None:
            self.weinitiate = False
        else:
            self.weinitiate = True

        if self.file_props is not None:
            self.file_props['sender'] = session.ourjid
            self.file_props['receiver'] = session.peerjid
            self.file_props['session-type'] = 'jingle'
            self.file_props['sid'] = session.sid
            self.file_props['transfered_size'] = []
        
        log.info("FT request: %s" % file_props)


        if transport is None:
            self.transport = JingleTransportSocks5()
            self.transport.set_file_props(self.file_props)
            self.transport.set_our_jid(session.ourjid)
            self.transport.set_connection(session.connection)
        log.info('ourjid: %s' % session.ourjid)

        self.session = session
        self.media = 'file'
        
    def __on_session_initiate(self, stanza, content, error, action):
        jid = unicode(stanza.getFrom())
        log.info("jid:%s" % jid)
        
        file_props = {'type': 'r'}
        file_props['sender'] = jid
        file_props['request-id'] = unicode(stanza.getAttr('id'))

        file_props['session-type'] = 'jingle'

        file_tag = content.getTag('description').getTag('offer').getTag('file')
        for attribute in file_tag.getAttrs():
            if attribute in ('name', 'size', 'hash', 'date'):
                val = file_tag.getAttr(attribute)
                if val is None:
                    continue
                file_props[attribute] = val
        file_desc_tag = file_tag.getTag('desc')
        if file_desc_tag is not None:
            file_props['desc'] = file_desc_tag.getData()
        
        file_props['receiver'] = self.session.ourjid
        log.info("ourjid: %s" % self.session.ourjid)
        file_props['sid'] = unicode(stanza.getTag('jingle').getAttr('sid'))
        file_props['transfered_size'] = []

        self.file_props = file_props
        self.session.connection.files_props[file_props['sid']] = file_props
        if self.transport is None:
            self.transport = JingleTransportSocks5()
            self.transport.set_our_jid(self.session.ourjid)
            self.transport.set_connection(self.session.connection)
        self.transport.set_file_props(self.file_props)
        if self.file_props.has_key("streamhosts"):
            self.file_props['streamhosts'].extend(self.transport.remote_candidates)
        else:
            self.file_props['streamhosts'] = self.transport.remote_candidates
        for host in self.file_props['streamhosts']:
            host['initiator'] = self.session.initiator
            host['target'] = self.session.responder
        log.info("FT request: %s" % file_props)

        self.session.connection.dispatch('FILE_REQUEST', (jid, file_props))

        

    def __on_session_accept(self, stanza, content, error, action):
        log.info("__on_session_accept")

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
        
        streamhost_cid = content.getTag('transport').getTag('candidate-used').getAttr('cid')
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
                    streamhost_used = proxy
                    break
            if 'streamhosts' not in self.file_props:
                self.file_props['streamhosts'] = []
                self.file_props['streamhosts'].append(streamhost_used)
                self.file_props['is_a_proxy'] = True
                receiver = Socks5Receiver(gajim.idlequeue, streamhost_used,
                                          self.file_props['sid'], self.file_props)
                #gajim.socks5queue.add_file_props(self.session.ourjid, self.file_props)
                gajim.socks5queue.add_receiver(self.session.ourjid, receiver)
                streamhost_used['idx'] = receiver.queue_idx
                gajim.socks5queue.on_success = self.transport._on_proxy_auth_ok
            pass
        else:
            jid = gajim.get_jid_without_resource(self.session.ourjid)
            gajim.socks5queue.send_file(self.file_props, jid)
            
    def __on_iq_result(self, stanza, content, error, action):
        log.info("__on_iq_result")
        
        if self.weinitiate:
            self.session.connection.files_props[self.file_props['sid']] = self.file_props
            receiver = self.file_props['receiver']
            sender = self.file_props['sender']
        
            sha_str = helpers.get_auth_sha(self.file_props['sid'], sender, receiver)
            self.file_props['sha_str'] = sha_str
        
            port = gajim.config.get('file_transfers_port')
        
            listener = gajim.socks5queue.start_listener(port, sha_str,
            self._store_socks5_sid, self.file_props['sid'])
            
            if not listener:
                return
                # send error message, notify the user
        else: # session-accept iq-result
                if not gajim.socks5queue.get_file_props(self.session.ourjid, self.file_props['sid']):
                    gajim.socks5queue.add_file_props(self.session.ourjid, self.file_props)
                jid = gajim.get_jid_without_resource(self.session.ourjid)
                gajim.socks5queue.connect_to_hosts(jid, self.file_props['sid'],
                                                   self.send_candidate_used, self._on_connect_error)
                    
    def send_candidate_used(self, streamhost):
        """
        send candidate-used stanza
        """
        log.info("send_candidate_used")
        if streamhost is None:
            return
        
        content = xmpp.Node('content')
        content.setAttr('creator', 'initiator')
        content.setAttr('name', 'file')
        
        transport = xmpp.Node('transport')
        transport.setAttr('xmlns', xmpp.NS_JINGLE_BYTESTREAM)
        
        candidateused = xmpp.Node('candidate-used')
        candidateused.setAttr('cid', streamhost['cid'])
        
        transport.addChild(node=candidateused)
        content.addChild(node=transport)

        self.session.send_transport_info(content)
        
    def _on_connect_error(self, to, _id, sid, code=404):
        log.info("connect error, sid=" + sid)
        return
        
    def _fill_content(self, content):
        description_node = xmpp.simplexml.Node(tag=xmpp.NS_JINGLE_FILE_TRANSFER + ' description')

        sioffer = xmpp.simplexml.Node(tag='offer')
        file_tag = sioffer.setTag('file', namespace=xmpp.NS_FILE)
        file_tag.setAttr('name', self.file_props['name'])
        file_tag.setAttr('size', self.file_props['size'])
        desc = file_tag.setTag('desc')
        if 'desc' in self.file_props:
            desc.setData(self.file_props['desc'])

        description_node.addChild(node=sioffer)

        content.addChild(node=description_node)
        
    def _store_socks5_sid(self, sid, hash_id):
        # callback from socsk5queue.start_listener
        self.file_props['hash'] = hash_id
        return

def get_content(desc):
    return JingleFileTransfer


contents[xmpp.NS_JINGLE_FILE_TRANSFER] = get_content
