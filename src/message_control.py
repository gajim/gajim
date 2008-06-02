##	message_control.py
##
## Copyright (C) 2006-2007 Travis Shirk <travis@pobox.com>
## Copyright (C) 2007 Stephan Erb <steve-e@h3c.de> 
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##
import gtkgui_helpers

from common import gajim

# Derived types MUST register their type IDs here if custom behavor is required
TYPE_CHAT = 'chat'
TYPE_GC = 'gc'
TYPE_PM = 'pm'

####################

class MessageControl:
	'''An abstract base widget that can embed in the gtk.Notebook of a MessageWindow'''

	def __init__(self, type_id, parent_win, widget_name, contact, account, resource = None):
		# dict { cb id : widget}
		# keep all registered callbacks of widgets, created by self.xml
		self.handlers = {}
		self.type_id = type_id
		self.parent_win = parent_win
		self.widget_name = widget_name
		self.contact = contact
		self.account = account
		self.hide_chat_buttons = False
		self.resource = resource

		gajim.last_message_time[self.account][self.get_full_jid()] = 0

		self.xml = gtkgui_helpers.get_glade('message_window.glade', widget_name)
		self.widget = self.xml.get_widget(widget_name)

	def get_full_jid(self):
		fjid = self.contact.jid
		if self.resource:
			fjid += '/' + self.resource
		return fjid

	def set_control_active(self, state):
		'''Called when the control becomes active (state is True)
		or inactive (state is False)'''
		pass  # Derived classes MUST implement this method

	def allow_shutdown(self, method):
		'''Called to check is a control is allowed to shutdown.
		If a control is not in a suitable shutdown state this method
		should return 'no', else 'yes' or 'minimize' '''
		# NOTE: Derived classes MAY implement this
		return 'yes'

	def shutdown(self):
		# NOTE: Derived classes MUST implement this
		pass

	def repaint_themed_widgets(self):
		pass # NOTE: Derived classes SHOULD implement this

	def update_ui(self):
		pass # NOTE: Derived classes SHOULD implement this

	def toggle_emoticons(self):
		pass # NOTE: Derived classes MAY implement this

	def update_font(self):
		pass # NOTE: Derived classes SHOULD implement this

	def update_tags(self):
		pass # NOTE: Derived classes SHOULD implement this

	def get_tab_label(self, chatstate):
		'''Return a suitable tab label string.  Returns a tuple such as:
		(label_str, color) either of which can be None
		if chatstate is given that means we have HE SENT US a chatstate and
		we want it displayed'''
		# NOTE: Derived classes MUST implement this
		# Return a markup'd label and optional gtk.Color in a tupple like:
		#return (label_str, None)
		pass

	def get_tab_image(self):
		# Return a suitable tab image for display.
		# None clears any current label.
		return None

	def prepare_context_menu(self):
		# NOTE: Derived classes SHOULD implement this
		return None

	def chat_buttons_set_visible(self, state):
		# NOTE: Derived classes MAY implement this
		self.hide_chat_buttons = state

	def got_connected(self):
		pass

	def got_disconnected(self):
		pass

	def get_specific_unread(self):
		return len(gajim.events.get_events(self.account,
			self.contact.jid))

	def set_session(self, session):
		oldsession = None
		if hasattr(self, 'session'):
			oldsession = self.session

		if oldsession and session == oldsession:
			return

		self.session = session

		new_key = None
		if session:
			session.control = self
			new_key = session.thread_id

		if oldsession:
			jid = self.contact.jid
			if self.resource:
				jid += '/' + self.resource

			self.parent_win.change_thread_key(jid, self.account,
				oldsession.thread_id, new_key)

			if oldsession.enable_encryption:
				self.print_esession_details()
		else:
			self.parent_win.move_from_sessionless(self)

	def send_message(self, message, keyID = '', type = 'chat',
	chatstate = None, msg_id = None, composing_xep = None, resource = None,
	user_nick = None):
		# Send the given message to the active tab.
		# Doesn't return None if error
		jid = self.contact.jid
		original_message = message

		if not self.session:
			sess = gajim.connections[self.account].make_new_session(jid)
			self.set_session(sess)

		xep_200 = bool(self.session) and self.session.enable_encryption

		if gajim.otr_module and not xep_200 and (jid not in gajim.otr_dont_append_tag):
			if type == 'chat' and isinstance(message, unicode):
				d = {'kwargs': {'keyID': keyID, 'type': type,
					'chatstate': chatstate,
					'msg_id': msg_id,
					'composing_xep': composing_xep,
					'resource': self.resource,
					'user_nick': user_nick,
					'session': self.session,
					'original_message': original_message},
					'account': self.account}

				new_msg = gajim.otr_module.otrl_message_sending(
					self.session.conn.otr_userstates,
					(gajim.otr_ui_ops, d),
					gajim.get_jid_from_account(
					self.account).encode(),
					gajim.OTR_PROTO,
					self.contact.get_full_jid().encode(),
					message.encode(), None,
					(gajim.otr_add_appdata, self.account))

				ctx = gajim.otr_module.otrl_context_find(
					self.session.conn.otr_userstates,
					self.contact.get_full_jid().encode(),
					gajim.get_jid_from_account(
					self.account).encode(),
					gajim.OTR_PROTO, 1,
					(gajim.otr_add_appdata,
					self.account))[0]

				# we send all because inject_message can filter
				# on HTML stuff then
				gajim.otr_module.otrl_message_fragment_and_send(
					(gajim.otr_ui_ops, d), ctx, new_msg,
					gajim.otr_module.OTRL_FRAGMENT_SEND_ALL)
				return

		# Send and update history
		return gajim.connections[self.account].send_message(jid,
			message, keyID, type = type, chatstate = chatstate,
			msg_id = msg_id, composing_xep = composing_xep,
			resource = self.resource, user_nick = user_nick,
			session = self.session,
			original_message = original_message)
