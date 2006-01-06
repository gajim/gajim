##	groupchat_control.py
##
## Copyright (C) 2005-2006 Travis Shirk <travis@pobox.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import time
import gtk
import gtk.glade
import pango
import gobject
import gtkgui_helpers
import message_control

from common import gajim
from chat_control import ChatControl
from chat_control import ChatControlBase
from conversation_textview import ConversationTextview
from message_textview import MessageTextView
from gettext import ngettext
from common import i18n

_ = i18n._
Q_ = i18n.Q_
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

#(status_image, type, nick, shown_nick)
(
C_IMG, # image to show state (online, new message etc)
C_TYPE, # type of the row ('contact' or 'group')
C_NICK, # contact nickame or group name
C_TEXT, # text shown in the cellrenderer
) = range(4)

class PrivateChatControl(ChatControl):
	TYPE_ID = message_control.TYPE_PM

	def __init__(self, parent_win, contact, acct):
		ChatControl.__init__(self, parent_win, contact, acct)
		self.TYPE_ID = 'pm'
		self.display_name = _('Private chat')

class GroupchatControl(ChatControlBase):
	TYPE_ID = message_control.TYPE_GC

	def __init__(self, parent_win, contact, acct):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
					'muc_child_vbox', _('Group Chat'), contact, acct);

		self.room_jid = self.contact.jid
		self.nick = contact.name
		self.name = self.room_jid.split('@')[0]

		self.compact_view_always = gajim.config.get('always_compact_view_gc')
		# alphanum sorted
		self.muc_cmds = ['ban', 'chat', 'query', 'clear', 'close', 'compact', 'help', 'invite',
			'join', 'kick', 'leave', 'me', 'msg', 'nick', 'part', 'say', 'topic']
		# muc attention flag (when we are mentioned in a muc)
		# if True, the room has mentioned us
		self.attention_flag = False
		self.room_creation = time.time()
		self.nick_hits = 0
		self.cmd_hits = 0
		self.last_key_tabs = False

		self.subject = ''
		self.subject_tooltip = gtk.Tooltips()

		self.allow_focus_out_line = True
		# holds the iter's offset which points to the end of --- line
		self.focus_out_end_iter_offset = None

		# connect the menuitems to their respective functions
		xm = gtk.glade.XML(GTKGUI_GLADE, 'gc_control_popup_menu', APP)
		xm.signal_autoconnect(self)
		self.gc_popup_menu = xm.get_widget('gc_popup_menu')

		self.name_label = self.xml.get_widget('banner_name_label')
		self.hpaneds = self.xml.get_widget('hpaned')

		list_treeview = self.list_treeview = self.xml.get_widget('list_treeview')
		list_treeview.get_selection().connect('changed',
			self.on_list_treeview_selection_changed)
		list_treeview.connect('style-set', self.on_list_treeview_style_set)

		self._last_selected_contact = None # None or holds jid, account tuple

	def iter_contact_rows(self):
		'''iterate over all contact rows in the tree model'''
		model = self.list_treeview.get_model()
		role_iter = model.get_iter_root()
		while role_iter:
			contact_iter = model.iter_children(role_iter)
			while contact_iter:
				yield model[contact_iter]
				contact_iter = model.iter_next(contact_iter)
			role_iter = model.iter_next(role_iter)

	def on_list_treeview_style_set(self, treeview, style):
		'''When style (theme) changes, redraw all contacts'''
		# Get the room_jid from treeview
		for contact in self.iter_contact_rows():
			nick = contact[C_NICK].decode('utf-8')
			self.draw_contact(nick)

	def on_list_treeview_selection_changed(self, selection):
		model, selected_iter = selection.get_selected()
		self.draw_contact(nick)
		if self._last_selected_contact is not None:
			self.draw_contact(self._last_selected_contact)
		if selected_iter is None:
			self._last_selected_contact = None
			return
		contact = model[selected_iter]
		nick = contact[C_NICK].decode('utf-8')
		self._last_selected_contact = nick
		if contact[C_TYPE] != 'contact':
			return
		self.draw_contact(nick, selected=True, focus=True)

	def get_tab_label(self, chatstate):
		'''Markup the label if necessary.  Returns a tuple such as:
		(new_label_str, color)
		either of which can be None
		if chatstate is given that means we have HE SENT US a chatstate'''
			
		num_unread = self.nb_unread

		has_focus = self.parent_win.window.get_property('has-toplevel-focus')
		current_tab = self.parent_win.get_active_control() == self
		color = None
		theme = gajim.config.get('roster_theme')
		if chatstate == 'attention' and (not has_focus or not current_tab):
			attention_flag = True
			color = gajim.config.get_per('themes', theme,
							'state_muc_directed_msg')
		elif chatstate:
			if chatstate == 'active' or (current_tab and has_focus):
				attention_flag = False
				color = gajim.config.get_per('themes', theme,
								'state_active_color')
			elif chatstate == 'newmsg' and (not has_focus or not current_tab) and\
			     not self.attention_flag:
				color = gajim.config.get_per('themes', theme, 'state_muc_msg')
		if color:
			color = gtk.gdk.colormap_get_system().alloc_color(color)
			if self.parent_win.get_active_control() != self:
				color = self.lighten_color(color)

		label_str = self.name
		if num_unread: # if unread, text in the label becomes bold
			label_str = '<b>' + str(num_unread) + label_str + '</b>'
		return (label_str, color)

	def get_tab_image(self):
		# Set tab image (always 16x16); unread messages show the 'message' image
		img_16 = gajim.interface.roster.get_appropriate_state_images(self.room_jid)

		# nb_unread is the number directed messages (msgs that mention our nick)
		tab_image = None
		if self.nb_unread and gajim.config.get('show_unread_tab_icon'):
			tab_image = img_16['message']
		else:

			tab_image = img_16['muc_active']
		return tab_image

	def prepare_context_menu(self):
		'''sets compact view menuitem active state
		sets active and sensitivity state for toggle_gpg_menuitem
		and remove possible 'Switch to' menuitems'''
		menu = self.gc_popup_menu
		childs = menu.get_children()
		# compact_view_menuitem
		childs[5].set_active(self.compact_view_current_state)
		menu = self.remove_possible_switch_to_menuitems(menu)
		return menu

	def on_message(self, nick, msg, tim):
		if not nick:
			# message from server
			self.print_conversation(msg, tim = tim)
		else:
			# message from someone
			self.print_conversation(msg, nick, tim)

	def on_private_message(self, nick, msg, tim):
		# Do we have a queue?
		fjid = self.room_jid + '/' + nick
		qs = gajim.awaiting_events[self.account]
		no_queue = True
		if qs.has_key(fjid):
			no_queue = False

		# We print if window is opened
		pm_control = gajim.interface.get_control(fjid)
		if pm_control:
			pm_control.print_conversation(msg, tim = tim)
			return

		if no_queue:
			qs[fjid] = []
		qs[fjid].append(('chat', (msg, '', 'incoming', tim, False, '')))

		autopopup = gajim.config.get('autopopup')
		autopopupaway = gajim.config.get('autopopupaway')
		iter = self.get_contact_iter(nick)
		path = self.list_treeview.get_model().get_path(iter)
		if not autopopup or (not autopopupaway and \
					gajim.connections[self.account].connected > 2):
			if no_queue: # We didn't have a queue: we change icons
				model = self.list_treeview.get_model()
				state_images =\
					gajim.interface.roster.get_appropriate_state_images(self.room_jid)
				image = state_images['message']
				model[iter][C_IMG] = image
				if gajim.interface.systray_enabled:
					gajim.interface.systray.add_jid(fjid, self.account, 'pm')
			self.parent_win.show_title()
		else:
			gc_c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
			c = gajim.contacts.contact_from_gc_contact(gc_c)
			gajim.interface.roster.new_chat(c, self.account)
		# Scroll to line
		self.list_treeview.expand_row(path[0:1], False)
		self.list_treeview.scroll_to_cell(path)
		self.list_treeview.set_cursor(path)

	def get_contact_iter(self, nick):
		model = self.list_treeview.get_model()
		fin = False
		role_iter = model.get_iter_root()
		if not role_iter:
			return None
		while not fin:
			fin2 = False
			user_iter = model.iter_children(role_iter)
			if not user_iter:
				fin2 = True
			while not fin2:
				if nick == model[user_iter][C_NICK].decode('utf-8'):
					return user_iter
				user_iter = model.iter_next(user_iter)
				if not user_iter:
					fin2 = True
			role_iter = model.iter_next(role_iter)
			if not role_iter:
				fin = True
		return None

	def print_conversation(self, text, contact = '', tim = None):
		'''Print a line in the conversation:
		if contact is set: it's a message from someone
		if contact is not set: it's a message from the server or help'''
		if isinstance(text, str):
			text = unicode(text, 'utf-8')
		other_tags_for_name = []
		other_tags_for_text = []
		if contact:
			if contact == self.nick: # it's us
				kind = 'outgoing'
			else:
				kind = 'incoming'
				# muc-specific chatstate
				self.parent_win.redraw_tab(self.contact, 'newmsg')
		else:
			kind = 'status'

		if kind == 'incoming': # it's a message NOT from us
			# highlighting and sounds
			(highlight, sound) = self.highlighting_for_message(text, tim)
			if highlight:
				self.redraw_tab(self.contact, 'attention') # muc-specific chatstate
				other_tags_for_name.append('bold')
				other_tags_for_text.append('marked')
			if sound == 'received':
				helpers.play_sound('muc_message_received')
			elif sound == 'highlight':
				helpers.play_sound('muc_message_highlight')

			self.check_and_possibly_add_focus_out_line()

		ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
			other_tags_for_name, [], other_tags_for_text)

	def highlighting_for_message(self, text, tim):
		'''Returns a 2-Tuple. The first says whether or not to highlight the
		text, the second, what sound to play.'''
		highlight, sound = (None, None)

		# Do we play a sound on every muc message?
		if gajim.config.get_per('soundevents', 'muc_message_received', 'enabled'):
			if gajim.config.get('notify_on_all_muc_messages'):
				sound = 'received'

		# Are any of the defined highlighting words in the text?
		if self.needs_visual_notification(text):
			highlight = True
			if gajim.config.get_per('soundevents', 'muc_message_highlight',
									'enabled'):
				sound = 'highlight'

		# Is it a history message? Don't want sound-floods when we join.
		if tim != time.localtime():
			sound = None

		return (highlight, sound)

	def check_and_possibly_add_focus_out_line(self):
		'''checks and possibly adds focus out line for room_jid if it needs it
		and does not already have it as last event. If it goes to add this line
		it removes previous line first'''

		win = gajim.interface.msg_win_mgr.get_window(self.room_jid)
		if self.room_jid == win.get_active_jid() and\
		win.window.get_property('has-toplevel-focus'):
			# it's the current room and it's the focused window.
			# we have full focus (we are reading it!)
			return

		if not self.allow_focus_out_line:
			# if room did not receive focus-in from the last time we added
			# --- line then do not readd
			return

		print_focus_out_line = False
		buffer = self.conv_textview.get_buffer()

		if self.focus_out_end_iter_offset is None:
			# this happens only first time we focus out on this room
			print_focus_out_line = True

		else:
			if self.focus_out_end_iter_offset != buffer.get_end_iter().get_offset():
				# this means after last-focus something was printed
				# (else end_iter's offset is the same as before)
				# only then print ---- line (eg. we avoid printing many following
				# ---- lines)
				print_focus_out_line = True

		if print_focus_out_line and buffer.get_char_count() > 0:
			buffer.begin_user_action()

			# remove previous focus out line if such focus out line exists
			if self.focus_out_end_iter_offset is not None:
				end_iter_for_previous_line = buffer.get_iter_at_offset(
					self.focus_out_end_iter_offset)
				begin_iter_for_previous_line = end_iter_for_previous_line.copy()
				begin_iter_for_previous_line.backward_chars(2) # img_char+1 (the '\n')

				# remove focus out line
				buffer.delete(begin_iter_for_previous_line,
					end_iter_for_previous_line)

			# add the new focus out line
			# FIXME: Why is this loaded from disk everytime
			path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps', 'muc_separator.png')
			focus_out_line_pixbuf = gtk.gdk.pixbuf_new_from_file(path_to_file)
			end_iter = buffer.get_end_iter()
			buffer.insert(end_iter, '\n')
			buffer.insert_pixbuf(end_iter, focus_out_line_pixbuf)

			end_iter = buffer.get_end_iter()
			before_img_iter = end_iter.copy()
			before_img_iter.backward_char() # one char back (an image also takes one char)
			buffer.apply_tag_by_name('focus-out-line', before_img_iter, end_iter)
			#FIXME: remove this workaround when bug is fixed
			# c http://bugzilla.gnome.org/show_bug.cgi?id=318569

			self.allow_focus_out_line = False

			# update the iter we hold to make comparison the next time
			self.focus_out_end_iter_offset = buffer.get_end_iter().get_offset()

			buffer.end_user_action()

			# scroll to the end (via idle in case the scrollbar has appeared)
			gobject.idle_add(self.conv_textview.scroll_to_end)

	def needs_visual_notification(self, text):
		'''checks text to see whether any of the words in (muc_highlight_words
		and nick) appear.'''

		special_words = gajim.config.get('muc_highlight_words').split(';')
		special_words.append(self.nick)
		# Strip empties: ''.split(';') == [''] and would highlight everything.
		# Also lowercase everything for case insensitive compare.
		special_words = [word.lower() for word in special_words if word]
		text = text.lower()

		text_splitted = text.split()
		for word in text_splitted: # get each word of the text
			for special_word in special_words:
				if word.startswith(special_word):
					return True
		return False

	def set_subject(self, subject):
		self.subject= subject
		full_subject = None

		subject = gtkgui_helpers.reduce_chars_newlines(subject, 0, 2)
		subject = gtkgui_helpers.escape_for_pango_markup(subject)
		self.name_label.set_markup(
		'<span weight="heavy" size="x-large">%s</span>\n%s' % (self.room_jid, subject))
		event_box = name_label.get_parent()
		if subject == '':
			subject = _('This room has no subject')

		if full_subject is not None:
			subject = full_subject # tooltip must always hold ALL the subject
		self.subject_tooltip.set_tip(event_box, subject)

	def save_var(self):
		return {
			'nick': self.nick,
			'model': self.list_treeview.get_model(),
			'subject': self.subject,
		}

	def load_var(self, room_jid, var):
		self.list_treeview.set_model(var['model'])
		self.list_treeviewexpand_all()
		self.set_subject(var['subject'])
		self.subject= var['subject']
		if gajim.gc_connected[self.account][room_jid]:
			self.got_connected()

	def got_connected(self):
		gajim.gc_connected[self.account][self.room_jid] = True
		message_textview = self.message_textviews[room_jid]
		self.msg_textview.set_sensitive(True)
		self.xml.get_widget('send_button').set_sensitive(True)

	def got_disconnected(self):
		model = self.list_treeview.get_model()
		model.clear()
		nick_list = gajim.contacts.get_nick_list(self.account, self.room_jid)
		for nick in nick_list:
			gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
				nick)
			gajim.contacts.remove_gc_contact(self.account, gc_contact)
		gajim.gc_connected[self.account][self.room_jid] = False
		self.msg_textview.set_sensitive(False)
		self.xml.get_widget('send_button').set_sensitive(False)

	def draw_contact(self, nick, selected=False, focus=False):
		iter = self.get_contact_iter(self.room_jid, nick)
		if not iter:
			return
		model = self.list_treeview.get_model()
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		state_images = gajim.interface.roster.jabber_state_images['16']
		if gajim.awaiting_events[self.account].has_key(self.room_jid + '/' + nick):
			image = state_images['message']
		else:
			image = state_images[gc_contact.show]

		name = gtkgui_helpers.escape_for_pango_markup(gc_contact.name)
		status = gc_contact.status
		# add status msg, if not empty, under contact name in the treeview
		if status and gajim.config.get('show_status_msgs_in_roster'):
			status = status.strip()
			if status != '':
				status = gtkgui_helpers.reduce_chars_newlines(status, max_lines = 1)
				# escape markup entities and make them small italic and fg color
				color = gtkgui_helpers._get_fade_color(self.list_treeview,
					selected, focus)
				colorstring = "#%04x%04x%04x" % (color.red, color.green, color.blue)
				name += '\n' '<span size="small" style="italic" foreground="%s">%s</span>'\
					% (colorstring, gtkgui_helpers.escape_for_pango_markup(status))

		model[iter][C_IMG] = image
		model[iter][C_TEXT] = name
