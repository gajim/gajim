# -*- coding:utf-8 -*-
## src/session.py
##
## Copyright (C) 2008 Yann Leboulanger <asterix AT lagaule.org>
##                    Brendan Taylor <whateley AT gmail.com>
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

import common.xmpp

import message_control

import notify

import dialogs
import negotiation

class ChatControlSession(stanza_session.EncryptedStanzaSession):
	def __init__(self, conn, jid, thread_id, type_='chat'):
		stanza_session.EncryptedStanzaSession.__init__(self, conn, jid, thread_id,
			type_='chat')

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

	def get_chatstate(self, msg, msgtxt):
		'''extracts chatstate from a <message/> stanza'''
		composing_xep = None
		chatstate = None

		# chatstates - look for chatstate tags in a message if not delayed
		delayed = msg.getTag('x', namespace=common.xmpp.NS_DELAY) is not None
		if not delayed:
			composing_xep = False
			children = msg.getChildren()
			for child in children:
				if child.getNamespace() == 'http://jabber.org/protocol/chatstates':
					chatstate = child.getName()
					composing_xep = 'XEP-0085'
					break
			# No XEP-0085 support, fallback to XEP-0022
			if not chatstate:
				chatstate_child = msg.getTag('x', namespace=common.xmpp.NS_EVENT)
				if chatstate_child:
					chatstate = 'active'
					composing_xep = 'XEP-0022'
					if not msgtxt and chatstate_child.getTag('composing'):
						chatstate = 'composing'

		return (composing_xep, chatstate)

	def received(self, full_jid_with_resource, msgtxt, tim, encrypted, msg):
		'''dispatch a received <message> stanza'''
		msg_type = msg.getType()
		subject = msg.getSubject()

		if not msg_type or msg_type not in ('chat', 'groupchat', 'error'):
			msg_type = 'normal'

		msg_id = None

		# XEP-0172 User Nickname
		user_nick = msg.getTagData('nick')
		if not user_nick:
			user_nick = ''

		form_node = None
		for xtag in msg.getTags('x'):
			if xtag.getNamespace() == common.xmpp.NS_DATA:
				form_node = xtag
				break

		composing_xep, chatstate = self.get_chatstate(msg, msgtxt)

		xhtml = msg.getXHTML()

		if msg_type == 'chat':
			if not msg.getTag('body') and chatstate is None:
				return

			log_type = 'chat_msg_recv'
		else:
			log_type = 'single_msg_recv'

		if self.is_loggable() and msgtxt:
			try:
				msg_id = gajim.logger.write(log_type, full_jid_with_resource,
					msgtxt, tim=tim, subject=subject)
			except exceptions.PysqliteOperationalError, e:
				self.conn.dispatch('ERROR', (_('Disk WriteError'), str(e)))

		treat_as = gajim.config.get('treat_incoming_messages')
		if treat_as:
			msg_type = treat_as

		jid = gajim.get_jid_without_resource(full_jid_with_resource)
		resource = gajim.get_resource_from_jid(full_jid_with_resource)

		if gajim.config.get('ignore_incoming_xhtml'):
			xhtml = None
		if gajim.jid_is_transport(jid):
			jid = jid.replace('@', '')

		groupchat_control = gajim.interface.msg_win_mgr.get_gc_control(jid,
			self.conn.name)

		if not groupchat_control and \
		jid in gajim.interface.minimized_controls[self.conn.name]:
			groupchat_control = gajim.interface.minimized_controls[self.conn.name]\
				[jid]

		pm = False
		if groupchat_control and groupchat_control.type_id == \
		message_control.TYPE_GC and resource:
			# It's a Private message
			pm = True
			msg_type = 'pm'

		highest_contact = gajim.contacts.get_contact_with_highest_priority(
			self.conn.name, jid)

		# does this resource have the highest priority of any available?
		is_highest = not highest_contact or not highest_contact.resource or \
			resource == highest_contact.resource or highest_contact.show == \
				'offline'

		# Handle chat states
		contact = gajim.contacts.get_contact(self.conn.name, jid, resource)
		if contact:
			if contact.composing_xep != 'XEP-0085': # We cache xep85 support
				contact.composing_xep = composing_xep
			if self.control and self.control.type_id == message_control.TYPE_CHAT:
				if chatstate is not None:
					# other peer sent us reply, so he supports jep85 or jep22
					contact.chatstate = chatstate
					if contact.our_chatstate == 'ask': # we were jep85 disco?
						contact.our_chatstate = 'active' # no more
					self.control.handle_incoming_chatstate()
				elif contact.chatstate != 'active':
					# got no valid jep85 answer, peer does not support it
					contact.chatstate = False
			elif chatstate == 'active':
				# Brand new message, incoming.
				contact.our_chatstate = chatstate
				contact.chatstate = chatstate
				if msg_id: # Do not overwrite an existing msg_id with None
					contact.msg_id = msg_id

		# THIS MUST BE AFTER chatstates handling
		# AND BEFORE playsound (else we ear sounding on chatstates!)
		if not msgtxt: # empty message text
			return

		if gajim.config.get_per('accounts', self.conn.name,
		'ignore_unknown_contacts') and not gajim.contacts.get_contacts(
		self.conn.name, jid) and not pm:
			return

		if not contact:
			# contact is not in the roster, create a fake one to display
			# notification
			contact = contacts.Contact(jid=jid, resource=resource)

		advanced_notif_num = notify.get_advanced_notification('message_received',
			self.conn.name, contact)

		if not pm and is_highest:
			jid_of_control = jid
		else:
			jid_of_control = full_jid_with_resource

		if not self.control:
			ctrl = gajim.interface.msg_win_mgr.get_control(jid_of_control,
				self.conn.name)
			if ctrl:
				self.control = ctrl
				self.control.set_session(self)

		# Is it a first or next message received ?
		first = False
		if not self.control and not gajim.events.get_events(self.conn.name, \
		jid_of_control, [msg_type]):
			first = True

		if pm:
			nickname = resource
			if self.control:
				# print if a control is open
				self.control.print_conversation(msgtxt, tim=tim, xhtml=xhtml,
					encrypted=encrypted)
			else:
				# otherwise pass it off to the control to be queued
				groupchat_control.on_private_message(nickname, msgtxt, tim,
					xhtml, self, msg_id=msg_id, encrypted=encrypted)
		else:
			self.roster_message(jid, msgtxt, tim, encrypted, msg_type,
				subject, resource, msg_id, user_nick, advanced_notif_num,
				xhtml=xhtml, form_node=form_node)

			nickname = gajim.get_name_from_jid(self.conn.name, jid)

		# Check and do wanted notifications
		msg = msgtxt
		if subject:
			msg = _('Subject: %s') % subject + '\n' + msg
		focused = False

		if self.control:
			parent_win = self.control.parent_win
			if self.control == parent_win.get_active_control() and \
			parent_win.window.has_focus:
				focused = True

		notify.notify('new_message', jid_of_control, self.conn.name, [msg_type,
			first, nickname, msg, focused], advanced_notif_num)

		if gajim.interface.remote_ctrl:
			gajim.interface.remote_ctrl.raise_signal('NewMessage', (self.conn.name,
				[full_jid_with_resource, msgtxt, tim, encrypted, msg_type, subject,
				chatstate, msg_id, composing_xep, user_nick, xhtml, form_node]))

	def roster_message(self, jid, msg, tim, encrypted=False, msg_type='',
	subject=None, resource='', msg_id=None, user_nick='',
	advanced_notif_num=None, xhtml=None, form_node=None):
		'''display the message or show notification in the roster'''
		contact = None
		# if chat window will be for specific resource
		resource_for_chat = resource

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
				resource_for_chat = None
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
				# if no control exists and message comes from highest prio, the new
				# control shouldn't have a resource
				if highest_contact and contact.resource == highest_contact.resource\
				and not jid == gajim.get_jid_from_account(self.conn.name):
					fjid = jid
					resource_for_chat = None

		# Do we have a queue?
		no_queue = len(gajim.events.get_events(self.conn.name, fjid)) == 0

		popup = helpers.allow_popup_window(self.conn.name, advanced_notif_num)

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
				subject=subject, xhtml=xhtml)

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
			encrypted, resource, msg_id, xhtml, self, form_node),
			show_in_roster=show_in_roster, show_in_systray=show_in_systray)

		gajim.events.add_event(self.conn.name, fjid, event)

		if popup:
			if not self.control:
				self.control = gajim.interface.new_chat(contact,
					self.conn.name, resource=resource_for_chat, session=self)

				if len(gajim.events.get_events(self.conn.name, fjid)):
					self.control.read_queue()
		else:
			if no_queue: # We didn't have a queue: we change icons
				gajim.interface.roster.draw_contact(jid, self.conn.name)

			gajim.interface.roster.show_title() # we show the * or [n]
		# Select contact row in roster.
		gajim.interface.roster.select_contact(jid, self.conn.name)

	# ---- ESessions stuff ---

	def handle_negotiation(self, form):
		if form.getField('accept') and not form['accept'] in ('1', 'true'):
			self.cancelled_negotiation()
			return

		# encrypted session states. these are described in stanza_session.py

		try:
			# bob responds
			if form.getType() == 'form' and 'security' in form.asDict():
				# we don't support 3-message negotiation as the responder
				if 'dhkeys' in form.asDict():
					self.fail_bad_negotiation('3 message negotiation not supported '
						'when responding', ('dhkeys',))
					return

				negotiated, not_acceptable, ask_user = self.verify_options_bob(form)

				if ask_user:
					def accept_nondefault_options(is_checked):
						self.dialog.destroy()
						negotiated.update(ask_user)
						self.respond_e2e_bob(form, negotiated, not_acceptable)

					def reject_nondefault_options():
						self.dialog.destroy()
						for key in ask_user.keys():
							not_acceptable.append(key)
						self.respond_e2e_bob(form, negotiated, not_acceptable)

					self.dialog = dialogs.YesNoDialog(_('Confirm these session '
						'options'),
						_('''The remote client wants to negotiate an session with these features:

	%s

	Are these options acceptable?''') % (negotiation.describe_features(
						ask_user)),
						on_response_yes=accept_nondefault_options,
						on_response_no=reject_nondefault_options)
				else:
					self.respond_e2e_bob(form, negotiated, not_acceptable)

				return

			# alice accepts
			elif self.status == 'requested-e2e' and form.getType() == 'submit':
				negotiated, not_acceptable, ask_user = self.verify_options_alice(
					form)

				if ask_user:
					def accept_nondefault_options(is_checked):
						dialog.destroy()

						negotiated.update(ask_user)

						try:
							self.accept_e2e_alice(form, negotiated)
						except exceptions.NegotiationError, details:
							self.fail_bad_negotiation(details)

					def reject_nondefault_options():
						self.reject_negotiation()
						dialog.destroy()

					dialog = dialogs.YesNoDialog(_('Confirm these session options'),
						_('The remote client selected these options:\n\n%s\n\n'
						'Continue with the session?') % (
						negotiation.describe_features(ask_user)),
						on_response_yes = accept_nondefault_options,
						on_response_no = reject_nondefault_options)
				else:
					try:
						self.accept_e2e_alice(form, negotiated)
					except exceptions.NegotiationError, details:
						self.fail_bad_negotiation(details)

				return
			elif self.status == 'responded-e2e' and form.getType() == 'result':
				try:
					self.accept_e2e_bob(form)
				except exceptions.NegotiationError, details:
					self.fail_bad_negotiation(details)

				return
			elif self.status == 'identified-alice' and form.getType() == 'result':
				try:
					self.final_steps_alice(form)
				except exceptions.NegotiationError, details:
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
				jid, resource = gajim.get_room_and_nick_from_fjid(self.jid)

				account = self.conn.name
				contact = gajim.contacts.get_contact(account, self.jid, resource)

				if not contact:
					contact = gajim.contacts.create_contact(jid=jid,
						resource=resource, show=self.conn.get_status())

				gajim.interface.new_chat(contact, account, resource=resource,
					session=self)

			negotiation.FeatureNegotiationWindow(account, self.jid, self, form)

# vim: se ts=3:
