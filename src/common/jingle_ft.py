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
    def __init__(self, session, file_props, transport=None):
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

        if transport == None:
            self.transport = JingleTransportICEUDP()
        
    def __on_session_initiate(self, stanza, content, error, action):
        log.info("__on_session_initiate")
        pass

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
        content.addChild("description", namespace = xmpp.NS_JINGLE_FILE_TRANSFER)
