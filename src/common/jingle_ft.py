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
from jingle_transport import JingleTransportICEUDP
import logging

log = logging.getLogger('gajim.c.jingle_ft')


class JingleFileTransfer(JingleContent):
    def __init__(self, session, transport=None, file_props=None):
        JingleContent.__init__(self, session, transport)
        
        #events we might be interested in
        self.callbacks['session-initiate'] += [self.__on_session_initiate]
        self.callbacks['session-accept'] += [self.__on_session_accept]
        self.callbacks['session-terminate'] += [self.__on_session_terminate]
        self.callbacks['transport-accept'] += [self.__on_transport_accept]
        self.callbacks['transport-replace'] += [self.__on_transport_replace]    #fallback transport method
        self.callbacks['transport-reject'] += [self.__on_transport_reject]
        self.callbacks['transport-info'] += [self.__on_transport_info]

        self.file_props = file_props
        if file_props is None:
            self.weinitiate = False
        else:
            self.weinitiate = True

        if self.file_props is not None:
            self.file_props['sender'] = session.ourjid
            self.file_props['session-type'] = 'jingle'
            self.file_props['sid'] = session.sid
            self.file_props['transfered_size'] = []
        
        log.info("FT request: %s" % file_props)


        if transport is None:
            self.transport = JingleTransportICEUDP()

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
        
        log.info("FT request: %s" % file_props)

        #TODO
        #add file transfer to queue
        self.session.connection.dispatch('FILE_REQUEST', (jid, file_props))

        

    def __on_session_accept(self, stanza, content, error, action):
        log.info("__on_session_accept")
        pass

    def __on_session_terminate(self, stanza, content, error, action):
        log.info("__on_session_terminate")
        pass

    def __on_transport_accept(self, stanza, content, error, action):
        log.info("__on_transport_accept")
        pass

    def __on_transport_replace(self, stanza, content, error, action):
        log.info("__on_transport_replace")
        pass
    
    def __on_transport_reject(self, stanza, content, error, action):
        log.info("__on_transport_reject")
        pass

    def __on_transport_info(self, stanza, content, error, action):
        log.info("__on_transport_info")
        pass

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

def get_content(desc):
    return JingleFileTransfer


contents[xmpp.NS_JINGLE_FILE_TRANSFER] = get_content
