# Copyright (C) 2010-2014 Yann Leboulanger <asterix AT lagaule.org>
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

# pylint: disable=no-init
# pylint: disable=attribute-defined-outside-init

import logging

from nbxmpp.namespaces import Namespace

from gajim.common import nec
from gajim.common import app
from gajim.common.jingle_transport import JingleTransportSocks5
from gajim.common.file_props import FilesProp

log = logging.getLogger('gajim.c.connection_handlers_events')


class PresenceReceivedEvent(nec.NetworkIncomingEvent):

    name = 'presence-received'


class OurShowEvent(nec.NetworkIncomingEvent):

    name = 'our-show'

    def init(self):
        self.reconnect = False


class MessageSentEvent(nec.NetworkIncomingEvent):

    name = 'message-sent'


class ConnectionLostEvent(nec.NetworkIncomingEvent):

    name = 'connection-lost'

    def generate(self):
        app.nec.push_incoming_event(OurShowEvent(
            None,
            conn=self.conn,
            show='offline'))
        return True


class FileRequestReceivedEvent(nec.NetworkIncomingEvent):

    name = 'file-request-received'

    def init(self):
        self.jingle_content = None
        self.FT_content = None

    def generate(self):
        self.id_ = self.stanza.getID()
        self.fjid = self.conn.get_module('Bytestream')._ft_get_from(
            self.stanza)
        self.account = self.conn.name
        self.jid = app.get_jid_without_resource(self.fjid)
        if not self.jingle_content:
            return
        secu = self.jingle_content.getTag('security')
        self.FT_content.use_security = bool(secu)
        if secu:
            fingerprint = secu.getTag('fingerprint')
            if fingerprint:
                self.FT_content.x509_fingerprint = fingerprint.getData()
        if not self.FT_content.transport:
            self.FT_content.transport = JingleTransportSocks5()
            self.FT_content.transport.set_our_jid(
                self.FT_content.session.ourjid)
            self.FT_content.transport.set_connection(
                self.FT_content.session.connection)
        sid = self.stanza.getTag('jingle').getAttr('sid')
        self.file_props = FilesProp.getNewFileProp(self.conn.name, sid)
        self.file_props.transport_sid = self.FT_content.transport.sid
        self.FT_content.file_props = self.file_props
        self.FT_content.transport.set_file_props(self.file_props)
        self.file_props.streamhosts.extend(
            self.FT_content.transport.remote_candidates)
        for host in self.file_props.streamhosts:
            host['initiator'] = self.FT_content.session.initiator
            host['target'] = self.FT_content.session.responder
        self.file_props.session_type = 'jingle'
        self.file_props.stream_methods = Namespace.BYTESTREAM
        desc = self.jingle_content.getTag('description')
        if self.jingle_content.getAttr('creator') == 'initiator':
            file_tag = desc.getTag('file')
            self.file_props.sender = self.fjid
            self.file_props.receiver = self.conn.get_own_jid()
        else:
            file_tag = desc.getTag('file')
            hash_ = file_tag.getTag('hash')
            hash_ = hash_.getData() if hash_ else None
            file_name = file_tag.getTag('name')
            file_name = file_name.getData() if file_name else None
            pjid = app.get_jid_without_resource(self.fjid)
            file_info = self.conn.get_module('Jingle').get_file_info(
                pjid, hash_=hash_, name=file_name, account=self.conn.name)
            self.file_props.file_name = file_info['file-name']
            self.file_props.sender = self.conn.get_own_jid()
            self.file_props.receiver = self.fjid
            self.file_props.type_ = 's'
        for child in file_tag.getChildren():
            name = child.getName()
            val = child.getData()
            if val is None:
                continue
            if name == 'name':
                self.file_props.name = val
            if name == 'size':
                self.file_props.size = int(val)
            if name == 'hash':
                self.file_props.algo = child.getAttr('algo')
                self.file_props.hash_ = val
            if name == 'date':
                self.file_props.date = val

        self.file_props.request_id = self.id_
        file_desc_tag = file_tag.getTag('desc')
        if file_desc_tag is not None:
            self.file_props.desc = file_desc_tag.getData()
        self.file_props.transfered_size = []
        return True


class InformationEvent(nec.NetworkIncomingEvent):

    name = 'information'

    def init(self):
        self.args = None
        self.kwargs = {}
        self.dialog_name = None
        self.popup = True

    def generate(self):
        if self.args is None:
            self.args = ()
        else:
            self.args = (self.args,)
        return True
