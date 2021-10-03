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
from gajim.common import helpers
from gajim.common import app
from gajim.common import i18n
from gajim.common.i18n import _
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


class NotificationEvent(nec.NetworkIncomingEvent):

    name = 'notification'

    def init(self):
        self.account = None
        self.contact = None

        self.notif_type = 'msg'

        self.popup_enabled = False
        self.popup_event_type = ''
        self.popup_msg_type = ''
        self.popup_title = ''
        self.popup_text = ''
        self.icon_name = None

        self.sound_file = ''  # Used by Triggers plugin only
        self.sound_event = ''

        self.command = ''  # Used by Triggers plugin only


class NotificationEventOld(nec.NetworkIncomingEvent):

    name = 'notification'
    base_network_events = ['gc-message-received',
                           'presence-received']

    def generate(self):
        # what's needed to compute output
        self.account = self.base_event.conn.name
        self.conn = self.base_event.conn
        self.jid = ''
        self.control = None
        self.control_focused = False
        self.first_unread = False

        # For output
        self.do_sound = False
        self.sound_file = ''
        self.sound_event = ''  # gajim sound played if not sound_file is set
        self.show_popup = False

        self.do_popup = False
        self.popup_title = ''
        self.popup_text = ''
        self.popup_event_type = ''
        self.popup_msg_type = ''
        self.icon_name = None
        self.transport_name = None
        self.show = None
        self.popup_timeout = -1

        self.do_command = False
        self.command = ''

        self.show_in_notification_area = False
        self.show_in_roster = False

        self.handle_incoming_pres_event(self.base_event)
        return True

    def handle_incoming_msg_event(self, msg_obj):
        # TODO: implement attention handling and remove this

        # don't alert for carbon copied messages from ourselves
        if msg_obj.properties.is_sent_carbon:
            return

        if msg_obj.properties.attention and not app.settings.get(
                'ignore_incoming_attention'):
            self.popup_timeout = 0
            self.do_popup = True
        else:
            self.popup_timeout = app.settings.get('notification_timeout')

        sound = app.settings.get_soundevent_settings('attention_received')

        if msg_obj.properties.attention and not app.settings.get(
                'ignore_incoming_attention') and sound['enabled']:
            self.sound_event = 'attention_received'
            self.do_sound = True

    def handle_incoming_pres_event(self, pres_obj):
        return
        # TODO
        if app.jid_is_transport(pres_obj.jid):
            return True
        account = pres_obj.conn.name
        client = app.get_client(account)
        self.jid = pres_obj.jid
        resource = pres_obj.resource or ''
        # It isn't an agent
        for c in pres_obj.contact_list:
            if c.resource == resource:
                # we look for other connected resources
                continue
            if c.show not in ('offline', 'error'):
                return True

        # no other resource is connected, let's look in metacontacts
        family = app.contacts.get_metacontacts_family(account, self.jid)
        for info in family:
            acct_ = info['account']
            jid_ = info['jid']
            c_ = app.contacts.get_contact_with_highest_priority(acct_, jid_)
            if not c_:
                continue
            if c_.jid == self.jid:
                continue
            if c_.show not in ('offline', 'error'):
                return True

        if pres_obj.old_show < 2 and pres_obj.new_show > 1:
            event = 'contact_connected'
            server = app.get_server_from_jid(self.jid)
            account_server = account + '/' + server
            block_transport = False
            if (account_server in app.block_signed_in_notifications and
                    app.block_signed_in_notifications[account_server]):
                block_transport = True

            sound = app.settings.get_soundevent_settings('contact_connected')
            if (sound['enabled'] and
                    not app.block_signed_in_notifications[account] and
                    not block_transport and helpers.allow_sound_notification(
                        account, 'contact_connected')):
                self.sound_event = event
                self.do_sound = True

        elif pres_obj.old_show > 1 and pres_obj.new_show < 2:
            event = 'contact_disconnected'
            sound = app.settings.get_soundevent_settings(
                'contact_disconnected')
            if sound['enabled'] and helpers.allow_sound_notification(
                    account, event):
                self.sound_event = event
                self.do_sound = True
        # Status change (not connected/disconnected or error (<1))
        elif pres_obj.new_show > 1:
            event = 'status_change'
        else:
            return True

        if app.jid_is_transport(self.jid):
            self.transport_name = app.get_transport_name_from_jid(self.jid)

        self.show = pres_obj.show

        self.popup_timeout = app.settings.get('notification_timeout')

        contact = client.get_module('Contacts').get_contact(self.jid)
        nick = i18n.direction_mark + contact.name
        if event == 'status_change':
            self.popup_title = _('%(nick)s Changed Status') % \
                {'nick': nick}
            self.popup_text = _('%(nick)s is now %(status)s') % \
                {'nick': nick, 'status': helpers.get_uf_show(pres_obj.show)}
            if pres_obj.status:
                self.popup_text = self.popup_text + " : " + pres_obj.status
            self.popup_event_type = _('Contact Changed Status')


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
