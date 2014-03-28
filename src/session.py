# -*- coding:utf-8 -*-
## src/session.py
##
## Copyright (C) 2008-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##                    Stephan Erb <steve-e AT h3c.de>
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

from common import helpers

from common import exceptions
from common import gajim
from common import stanza_session
from common import contacts
from common import ged
from common.connection_handlers_events import ChatstateReceivedEvent, \
    InformationEvent

import message_control

import notify

import dialogs
import negotiation

class ChatControlSession(stanza_session.EncryptedStanzaSession):
    def __init__(self, conn, jid, thread_id, type_='chat'):
        stanza_session.EncryptedStanzaSession.__init__(self, conn, jid, thread_id,
                type_='chat')
        gajim.ged.register_event_handler('decrypted-message-received', ged.GUI1,
            self._nec_decrypted_message_received)

        self.control = None

    def detach_from_control(self):
        if self.control:
            self.control.set_session(None)

    def acknowledge_termination(self):
        self.detach_from_control()
        stanza_session.EncryptedStanzaSession.acknowledge_termination(self)

    def terminate(self, send_termination = True):
        stanza_session.EncryptedStanzaSession.terminate(self, send_termination)
        self.detach_from_control()

    def _nec_decrypted_message_received(self, obj):
        """
        Dispatch a received <message> stanza
        """
        if obj.session != self:
            return
        if self.resource != obj.resource:
            self.resource = obj.resource
            if self.control and self.control.resource:
                self.control.change_resource(self.resource)

        if obj.mtype == 'chat':
            if not obj.stanza.getTag('body') and obj.chatstate is None:
                return

            log_type = 'chat_msg'
        else:
            log_type = 'single_msg'
        end = '_recv'
        if obj.forwarded and obj.sent:
            end = '_sent'
        log_type += end

        if self.is_loggable() and obj.msgtxt:
            try:
                if obj.xhtml and gajim.config.get('log_xhtml_messages'):
                    msg_to_log = obj.xhtml
                else:
                    msg_to_log = obj.msgtxt
                obj.msg_id = gajim.logger.write(log_type, obj.fjid,
                    msg_to_log, tim=obj.timestamp, subject=obj.subject)
            except exceptions.PysqliteOperationalError as e:
                gajim.nec.push_incoming_event(InformationEvent(None,
                    conn=self.conn, level='error', pri_txt=_('Disk Write Error'),
                    sec_txt=str(e)))
            except exceptions.DatabaseMalformed:
                pritext = _('Database Error')
                sectext = _('The database file (%s) cannot be read. Try to '
                    'repair it (see http://trac.gajim.org/wiki/DatabaseBackup) '
                    'or remove it (all history will be lost).') % \
                    gajim.logger.LOG_DB_PATH
                gajim.nec.push_incoming_event(InformationEvent(None,
                    conn=self.conn, level='error', pri_txt=pritext,
                    sec_txt=sectext))

        treat_as = gajim.config.get('treat_incoming_messages')
        if treat_as:
            obj.mtype = treat_as
        pm = False
        if obj.gc_control and obj.resource:
            # It's a Private message
            pm = True
            obj.mtype = 'pm'

        # Handle chat states
        contact = gajim.contacts.get_contact(self.conn.name, obj.jid,
            obj.resource)
        if contact and (not obj.forwarded or not obj.sent):
            if self.control and self.control.type_id == \
            message_control.TYPE_CHAT:
                if obj.chatstate is not None:
                    # other peer sent us reply, so he supports jep85 or jep22
                    contact.chatstate = obj.chatstate
                    if contact.our_chatstate == 'ask': # we were jep85 disco?
                        contact.our_chatstate = 'active' # no more
                    gajim.nec.push_incoming_event(ChatstateReceivedEvent(None,
                        conn=obj.conn, msg_obj=obj))
                elif contact.chatstate != 'active':
                    # got no valid jep85 answer, peer does not support it
                    contact.chatstate = False
            elif obj.chatstate == 'active':
                # Brand new message, incoming.
                contact.our_chatstate = obj.chatstate
                contact.chatstate = obj.chatstate
                if obj.msg_id: # Do not overwrite an existing msg_id with None
                    contact.msg_id = obj.msg_id

        # THIS MUST BE AFTER chatstates handling
        # AND BEFORE playsound (else we ear sounding on chatstates!)
        if not obj.msgtxt: # empty message text
            return True

        if gajim.config.get_per('accounts', self.conn.name,
        'ignore_unknown_contacts') and not gajim.contacts.get_contacts(
        self.conn.name, obj.jid) and not pm:
            return True

        highest_contact = gajim.contacts.get_contact_with_highest_priority(
            self.conn.name, obj.jid)

        # does this resource have the highest priority of any available?
        is_highest = not highest_contact or not highest_contact.resource or \
            obj.resource == highest_contact.resource or highest_contact.show ==\
            'offline'

        if not self.control:
            ctrl = gajim.interface.msg_win_mgr.search_control(obj.jid,
                obj.conn.name, obj.resource)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
                self.control.contact = contact

        if not pm:
            self.roster_message2(obj)

        if gajim.interface.remote_ctrl:
            gajim.interface.remote_ctrl.raise_signal('NewMessage', (
                self.conn.name, [obj.fjid, obj.msgtxt, obj.timestamp,
                obj.encrypted, obj.mtype, obj.subject, obj.chatstate,
                obj.msg_id, obj.user_nick, obj.xhtml, obj.form_node]))

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
            contact = gajim.contacts.get_contact(obj.conn.name, jid, resource)

        highest_contact = gajim.contacts.get_contact_with_highest_priority(
            obj.conn.name, jid)
        if not contact:
            # If there is another resource, it may be a message from an
            # invisible resource
            lcontact = gajim.contacts.get_contacts(obj.conn.name, jid)
            if (len(lcontact) > 1 or (lcontact and lcontact[0].resource and \
            lcontact[0].show != 'offline')) and jid.find('@') > 0:
                contact = gajim.contacts.copy_contact(highest_contact)
                contact.resource = resource
                contact.priority = 0
                contact.show = 'offline'
                contact.status = ''
                gajim.contacts.add_contact(obj.conn.name, contact)

            else:
                # Default to highest prio
                fjid = jid
                contact = highest_contact

        if not contact:
            # contact is not in roster
            contact = gajim.interface.roster.add_to_not_in_the_roster(
                obj.conn.name, jid, obj.user_nick)

        if not self.control:
            ctrl = gajim.interface.msg_win_mgr.search_control(obj.jid,
                obj.conn.name, obj.resource)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
            else:
                fjid = jid

        obj.popup = helpers.allow_popup_window(self.conn.name)

        type_ = 'chat'
        event_type = 'message_received'

        if obj.mtype == 'normal':
            type_ = 'normal'
            event_type = 'single_message_received'

        if self.control and obj.mtype != 'normal':
            obj.show_in_roster = False
            obj.show_in_systray = False
        else:
            obj.show_in_roster = notify.get_show_in_roster(event_type,
                self.conn.name, contact, self)
            obj.show_in_systray = notify.get_show_in_systray(event_type,
                self.conn.name, contact)

        if (not self.control and obj.mtype != 'normal') or \
        (obj.mtype == 'normal' and not obj.popup):
            event = gajim.events.create_event(type_, (obj.msgtxt, obj.subject,
                obj.mtype, obj.timestamp, obj.encrypted, obj.resource,
                obj.msg_id, obj.xhtml, self, obj.form_node, obj.displaymarking,
                obj.forwarded and obj.sent),
                show_in_roster=obj.show_in_roster,
                show_in_systray=obj.show_in_systray)

            gajim.events.add_event(self.conn.name, fjid, event)

    def roster_message(self, jid, msg, tim, encrypted=False, msg_type='',
    subject=None, resource='', msg_id=None, user_nick='', xhtml=None,
    form_node=None, displaymarking=None):
        """
        Display the message or show notification in the roster
        """
        contact = None
        fjid = jid

        # Try to catch the contact with correct resource
        if resource:
            fjid = jid + '/' + resource
            contact = gajim.contacts.get_contact(self.conn.name, jid, resource)

        highest_contact = gajim.contacts.get_contact_with_highest_priority(
                self.conn.name, jid)
        if not contact:
            # If there is another resource, it may be a message from an invisible
            # resource
            lcontact = gajim.contacts.get_contacts(self.conn.name, jid)
            if (len(lcontact) > 1 or (lcontact and lcontact[0].resource and \
            lcontact[0].show != 'offline')) and jid.find('@') > 0:
                contact = gajim.contacts.copy_contact(highest_contact)
                contact.resource = resource
                if resource:
                    fjid = jid + '/' + resource
                contact.priority = 0
                contact.show = 'offline'
                contact.status = ''
                gajim.contacts.add_contact(self.conn.name, contact)

            else:
                # Default to highest prio
                fjid = jid
                contact = highest_contact

        if not contact:
            # contact is not in roster
            contact = gajim.interface.roster.add_to_not_in_the_roster(
                    self.conn.name, jid, user_nick)

        if not self.control:
            ctrl = gajim.interface.msg_win_mgr.get_control(fjid, self.conn.name)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
            else:
                fjid = jid

        # Do we have a queue?
        no_queue = len(gajim.events.get_events(self.conn.name, fjid)) == 0

        popup = helpers.allow_popup_window(self.conn.name)

        if msg_type == 'normal' and popup: # it's single message to be autopopuped
            dialogs.SingleMessageWindow(self.conn.name, contact.jid,
                    action='receive', from_whom=jid, subject=subject, message=msg,
                    resource=resource, session=self, form_node=form_node)
            return

        # We print if window is opened and it's not a single message
        if self.control and msg_type != 'normal':
            typ = ''

            if msg_type == 'error':
                typ = 'error'

            self.control.print_conversation(msg, typ, tim=tim, encrypted=encrypted,
                    subject=subject, xhtml=xhtml, displaymarking=displaymarking)

            if msg_id:
                gajim.logger.set_read_messages([msg_id])

            return

        # We save it in a queue
        type_ = 'chat'
        event_type = 'message_received'

        if msg_type == 'normal':
            type_ = 'normal'
            event_type = 'single_message_received'

        show_in_roster = notify.get_show_in_roster(event_type, self.conn.name,
                contact, self)
        show_in_systray = notify.get_show_in_systray(event_type, self.conn.name,
                contact)

        event = gajim.events.create_event(type_, (msg, subject, msg_type, tim,
            encrypted, resource, msg_id, xhtml, self, form_node, displaymarking,
            False), show_in_roster=show_in_roster,
            show_in_systray=show_in_systray)

        gajim.events.add_event(self.conn.name, fjid, event)

        if popup:
            if not self.control:
                self.control = gajim.interface.new_chat(contact,
                    self.conn.name, session=self)

                if len(gajim.events.get_events(self.conn.name, fjid)):
                    self.control.read_queue()
        else:
            if no_queue: # We didn't have a queue: we change icons
                gajim.interface.roster.draw_contact(jid, self.conn.name)

            gajim.interface.roster.show_title() # we show the * or [n]
        # Select the big brother contact in roster, it's visible because it has
        # events.
        family = gajim.contacts.get_metacontacts_family(self.conn.name, jid)
        if family:
            nearby_family, bb_jid, bb_account = \
                    gajim.contacts.get_nearby_family_and_big_brother(family,
                    self.conn.name)
        else:
            bb_jid, bb_account = jid, self.conn.name
        gajim.interface.roster.select_contact(bb_jid, bb_account)

    # ---- ESessions stuff ---

    def handle_negotiation(self, form):
        if form.getField('accept') and not form['accept'] in ('1', 'true'):
            self.cancelled_negotiation()
            return

        # encrypted session states. these are described in stanza_session.py

        try:
            if form.getType() == 'form' and 'security' in form.asDict():
                security_options = [x[1] for x in form.getField('security').\
                    getOptions()]
                if security_options == ['none']:
                    self.respond_archiving(form)
                else:
                    # bob responds

                    # we don't support 3-message negotiation as the responder
                    if 'dhkeys' in form.asDict():
                        self.fail_bad_negotiation('3 message negotiation not '
                            'supported when responding', ('dhkeys',))
                        return

                    negotiated, not_acceptable, ask_user = \
                        self.verify_options_bob(form)

                    if ask_user:
                        def accept_nondefault_options(is_checked):
                            self.dialog.destroy()
                            negotiated.update(ask_user)
                            self.respond_e2e_bob(form, negotiated,
                                not_acceptable)

                        def reject_nondefault_options():
                            self.dialog.destroy()
                            for key in ask_user.keys():
                                not_acceptable.append(key)
                            self.respond_e2e_bob(form, negotiated,
                                not_acceptable)

                        self.dialog = dialogs.YesNoDialog(_('Confirm these '
                            'session options'),
                            _('The remote client wants to negotiate a session '
                            'with these features:\n\n%s\n\nAre these options '
                            'acceptable?''') % (
                            negotiation.describe_features(ask_user)),
                            on_response_yes=accept_nondefault_options,
                            on_response_no=reject_nondefault_options,
                            transient_for=self.control.parent_win.window)
                    else:
                        self.respond_e2e_bob(form, negotiated, not_acceptable)

                return

            elif self.status == 'requested-archiving' and form.getType() == \
            'submit':
                try:
                    self.archiving_accepted(form)
                except exceptions.NegotiationError as details:
                    self.fail_bad_negotiation(details)

                return

            # alice accepts
            elif self.status == 'requested-e2e' and form.getType() == 'submit':
                negotiated, not_acceptable, ask_user = self.verify_options_alice(
                        form)

                if ask_user:
                    def accept_nondefault_options(is_checked):
                        if dialog:
                            dialog.destroy()

                        if is_checked:
                            allow_no_log_for = gajim.config.get_per(
                                'accounts', self.conn.name,
                                'allow_no_log_for').split()
                            jid = str(self.jid)
                            if jid not in allow_no_log_for:
                                allow_no_log_for.append(jid)
                                gajim.config.set_per('accounts', self.conn.name,
                                'allow_no_log_for', ' '.join(allow_no_log_for))

                        negotiated.update(ask_user)

                        try:
                            self.accept_e2e_alice(form, negotiated)
                        except exceptions.NegotiationError as details:
                            self.fail_bad_negotiation(details)

                    def reject_nondefault_options():
                        self.reject_negotiation()
                        dialog.destroy()

                    allow_no_log_for = gajim.config.get_per('accounts',
                        self.conn.name, 'allow_no_log_for').split()
                    if str(self.jid) in allow_no_log_for:
                        dialog = None
                        accept_nondefault_options(False)
                    else:
                        dialog = dialogs.YesNoDialog(_('Confirm these session '
                            'options'),
                            _('The remote client selected these options:\n\n%s'
                            '\n\nContinue with the session?') % (
                            negotiation.describe_features(ask_user)),
                            _('Always accept for this contact'),
                            on_response_yes = accept_nondefault_options,
                            on_response_no = reject_nondefault_options,
                            transient_for=self.control.parent_win.window)
                else:
                    try:
                        self.accept_e2e_alice(form, negotiated)
                    except exceptions.NegotiationError as details:
                        self.fail_bad_negotiation(details)

                return
            elif self.status == 'responded-archiving' and form.getType() == \
            'result':
                try:
                    self.we_accept_archiving(form)
                except exceptions.NegotiationError as details:
                    self.fail_bad_negotiation(details)

                return
            elif self.status == 'responded-e2e' and form.getType() == 'result':
                try:
                    self.accept_e2e_bob(form)
                except exceptions.NegotiationError as details:
                    self.fail_bad_negotiation(details)

                return
            elif self.status == 'identified-alice' and form.getType() == 'result':
                try:
                    self.final_steps_alice(form)
                except exceptions.NegotiationError as details:
                    self.fail_bad_negotiation(details)

                return
        except exceptions.Cancelled:
            # user cancelled the negotiation

            self.reject_negotiation()

            return

        if form.getField('terminate') and\
        form.getField('terminate').getValue() in ('1', 'true'):
            self.acknowledge_termination()

            self.conn.delete_session(str(self.jid), self.thread_id)

            return

        # non-esession negotiation. this isn't very useful, but i'm keeping it
        # around to test my test suite.
        if form.getType() == 'form':
            if not self.control:
                jid, resource = gajim.get_room_and_nick_from_fjid(str(self.jid))

                account = self.conn.name
                contact = gajim.contacts.get_contact(account, str(self.jid),
                    resource)

                if not contact:
                    contact = gajim.contacts.create_contact(jid=jid, account=account,
                            resource=resource, show=self.conn.get_status())

                gajim.interface.new_chat(contact, account, resource=resource,
                        session=self)

            negotiation.FeatureNegotiationWindow(account, str(self.jid), self,
                form)
