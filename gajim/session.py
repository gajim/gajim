# Copyright (C) 2008-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
#                    Stephan Erb <steve-e AT h3c.de>
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

import string
import random
import itertools

from gajim.common import helpers
from gajim.common import events
from gajim.common import app
from gajim.common import contacts
from gajim.common import ged
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import KindConstant
from gajim.gui.util import get_show_in_roster
from gajim.gui.util import get_show_in_systray


class ChatControlSession:
    def __init__(self, conn, jid, thread_id, type_='chat'):
        self.conn = conn
        self.jid = jid
        self.type_ = type_
        self.resource = jid.resource
        self.control = None

        if thread_id:
            self.received_thread_id = True
            self.thread_id = thread_id
        else:
            self.received_thread_id = False
            if type_ == 'normal':
                self.thread_id = None
            else:
                self.thread_id = self.generate_thread_id()

        self.loggable = True

        self.last_send = 0
        self.last_receive = 0

        app.ged.register_event_handler('decrypted-message-received',
                                       ged.PREGUI,
                                       self._nec_decrypted_message_received)

    def generate_thread_id(self):
        return ''.join(
            [f(string.ascii_letters) for f in itertools.repeat(
                random.choice, 32)]
        )

    def is_loggable(self):
        return helpers.should_log(self.conn.name, self.jid.bare)

    def get_to(self):
        bare_jid = self.jid.bare
        if not self.resource:
            return bare_jid
        return bare_jid + '/' + self.resource

    def _nec_decrypted_message_received(self, obj):
        """
        Dispatch a received <message> stanza
        """
        if obj.session != self:
            return

        if obj.properties.is_muc_pm:
            contact = app.contacts.get_gc_contact(
                self.conn.name, obj.jid, obj.resource)
        else:
            contact = app.contacts.get_contact(
                self.conn.name, obj.jid, obj.resource)
        if self.resource != obj.resource:
            self.resource = obj.resource
            if self.control:
                if isinstance(contact, contacts.GC_Contact):
                    self.control.gc_contact = contact
                    self.control.contact = contact.as_contact()
                else:
                    self.control.contact = contact
                if self.control.resource:
                    self.control.change_resource(self.resource)

        if not obj.msgtxt:
            return

        log_type = KindConstant.CHAT_MSG_RECV
        if obj.properties.is_sent_carbon:
            log_type = KindConstant.CHAT_MSG_SENT

        if self.is_loggable() and obj.msgtxt:
            jid = obj.fjid
            if not obj.properties.is_muc_pm:
                jid = obj.jid

            obj.msg_log_id = app.storage.archive.insert_into_logs(
                self.conn.name,
                jid,
                obj.properties.timestamp,
                log_type,
                message=obj.msgtxt,
                subject=obj.properties.subject,
                additional_data=obj.additional_data,
                stanza_id=obj.unique_id,
                message_id=obj.properties.id)

        if obj.properties.is_muc_pm and not obj.gc_control:
            # This is a carbon of a PM from a MUC we are not currently
            # joined. We log it silently without notification.
            return True

        if not obj.msgtxt: # empty message text
            return True

        if not self.control:
            ctrl = app.interface.msg_win_mgr.search_control(obj.jid,
                obj.conn.name, obj.resource)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
                if isinstance(contact, contacts.GC_Contact):
                    self.control.gc_contact = contact
                    self.control.contact = contact.as_contact()
                else:
                    self.control.contact = contact

        if not obj.properties.is_muc_pm:
            self.roster_message2(obj)

    def roster_message2(self, obj):
        """
        Display the message or show notification in the roster
        """
        contact = None
        jid = obj.jid
        resource = obj.resource

        fjid = jid

        # Try to catch the contact with correct resource
        if resource:
            fjid = jid + '/' + resource
            contact = app.contacts.get_contact(obj.conn.name, jid, resource)

        highest_contact = app.contacts.get_contact_with_highest_priority(
            obj.conn.name, jid)
        if not contact:
            # If there is another resource, it may be a message from an
            # invisible resource
            lcontact = app.contacts.get_contacts(obj.conn.name, jid)
            if (len(lcontact) > 1 or (lcontact and lcontact[0].resource and \
            lcontact[0].show != 'offline')) and jid.find('@') > 0:
                contact = app.contacts.copy_contact(highest_contact)
                contact.resource = resource
                contact.priority = 0
                contact.show = 'offline'
                contact.status = ''
                app.contacts.add_contact(obj.conn.name, contact)

            else:
                # Default to highest prio
                fjid = jid
                contact = highest_contact

        if not contact:
            # contact is not in roster
            contact = app.interface.roster.add_to_not_in_the_roster(
                obj.conn.name, jid, obj.properties.nickname)

        if not self.control:
            ctrl = app.interface.msg_win_mgr.search_control(obj.jid,
                obj.conn.name, obj.resource)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
            else:
                fjid = jid

        obj.popup = helpers.allow_popup_window(self.conn.name)

        event_t = events.ChatEvent
        event_type = 'message_received'

        if self.control:
            # We have a ChatControl open
            obj.show_in_roster = False
            obj.show_in_systray = False
            do_event = False
        elif obj.properties.is_sent_carbon:
            # Its a Carbon Copied Message we sent
            obj.show_in_roster = False
            obj.show_in_systray = False
            unread_events = app.events.get_events(
                self.conn.name, fjid, types=['chat'])
            read_ids = []
            for msg in unread_events:
                read_ids.append(msg.msg_log_id)
            app.storage.archive.set_read_messages(read_ids)
            app.events.remove_events(self.conn.name, fjid, types=['chat'])
            do_event = False
        else:
            # Everything else
            obj.show_in_roster = get_show_in_roster(event_type, self)
            obj.show_in_systray = get_show_in_systray(event_type,
                                                      obj.conn.name,
                                                      contact.jid)
            do_event = True
        if do_event:
            kind = obj.properties.type.value
            event = event_t(
                obj.msgtxt,
                obj.properties.subject,
                kind,
                obj.properties.timestamp,
                obj.resource,
                obj.msg_log_id,
                correct_id=obj.correct_id,
                message_id=obj.properties.id,
                session=self,
                displaymarking=obj.displaymarking,
                sent_forwarded=obj.properties.is_sent_carbon,
                show_in_roster=obj.show_in_roster,
                show_in_systray=obj.show_in_systray,
                additional_data=obj.additional_data)

            app.events.add_event(self.conn.name, fjid, event)

    def roster_message(self, jid, msg, tim, msg_type='',
    subject=None, resource='', msg_log_id=None, user_nick='',
    displaymarking=None, additional_data=None):
        """
        Display the message or show notification in the roster
        """
        contact = None
        fjid = jid

        if additional_data is None:
            additional_data = AdditionalDataDict()

        # Try to catch the contact with correct resource
        if resource:
            fjid = jid + '/' + resource
            contact = app.contacts.get_contact(self.conn.name, jid, resource)

        highest_contact = app.contacts.get_contact_with_highest_priority(
                self.conn.name, jid)
        if not contact:
            # If there is another resource, it may be a message from an invisible
            # resource
            lcontact = app.contacts.get_contacts(self.conn.name, jid)
            if (len(lcontact) > 1 or (lcontact and lcontact[0].resource and \
            lcontact[0].show != 'offline')) and jid.find('@') > 0:
                contact = app.contacts.copy_contact(highest_contact)
                contact.resource = resource
                if resource:
                    fjid = jid + '/' + resource
                contact.priority = 0
                contact.show = 'offline'
                contact.status = ''
                app.contacts.add_contact(self.conn.name, contact)

            else:
                # Default to highest prio
                fjid = jid
                contact = highest_contact

        if not contact:
            # contact is not in roster
            contact = app.interface.roster.add_to_not_in_the_roster(
                    self.conn.name, jid, user_nick)

        if not self.control:
            ctrl = app.interface.msg_win_mgr.get_control(fjid, self.conn.name)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
            else:
                fjid = jid

        # Do we have a queue?
        no_queue = len(app.events.get_events(self.conn.name, fjid)) == 0

        popup = helpers.allow_popup_window(self.conn.name)

        # We print if window is opened and it's not a single message
        if self.control:
            typ = ''

            if msg_type == 'error':
                typ = 'error'

            self.control.add_message(msg,
                                     typ,
                                     tim=tim,
                                     subject=subject,
                                     displaymarking=displaymarking,
                                     additional_data=additional_data)

            if msg_log_id:
                app.storage.archive.set_read_messages([msg_log_id])

            return

        # We save it in a queue
        event_t = events.ChatEvent
        event_type = 'message_received'

        show_in_roster = get_show_in_roster(event_type, self)
        show_in_systray = get_show_in_systray(event_type,
                                              self.conn.name,
                                              contact.jid)

        event = event_t(msg, subject, msg_type, tim, resource,
            msg_log_id, session=self,
            displaymarking=displaymarking, sent_forwarded=False,
            show_in_roster=show_in_roster, show_in_systray=show_in_systray,
            additional_data=additional_data)

        app.events.add_event(self.conn.name, fjid, event)

        if popup:
            if not self.control:
                self.control = app.interface.new_chat(contact,
                    self.conn.name, session=self)

                if app.events.get_events(self.conn.name, fjid):
                    self.control.read_queue()
        else:
            if no_queue: # We didn't have a queue: we change icons
                app.interface.roster.draw_contact(jid, self.conn.name)

            app.interface.roster.show_title() # we show the * or [n]
        # Select the big brother contact in roster, it's visible because it has
        # events.
        family = app.contacts.get_metacontacts_family(self.conn.name, jid)
        if family:
            _nearby_family, bb_jid, bb_account = \
                    app.contacts.get_nearby_family_and_big_brother(family,
                    self.conn.name)
        else:
            bb_jid, bb_account = jid, self.conn.name
        app.interface.roster.select_contact(bb_jid, bb_account)
