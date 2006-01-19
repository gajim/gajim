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

import os
import time
import gtk
import gtk.glade
import pango
import gobject
import gtkgui_helpers
import message_control
import tooltips
import dialogs
import vcard
import cell_renderer_image
import history_window
import tooltips

from common import gajim
from common import helpers

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

	def send_message(self, message):
		'''call this function to send our message'''
		if not message:
			return

		# We need to make sure that we can still send through the room and that the 
		# recipient did not go away
		contact = gajim.contacts.get_first_contact_from_jid(self.account, self.contact.jid)
		if contact is None:
			# contact was from pm in MUC
			room, nick = gajim.get_room_and_nick_from_fjid(self.contact.jid)
			gc_contact = gajim.contacts.get_gc_contact(self.account, room, nick)
			if not gc_contact:
				dialogs.ErrorDialog(
					_('Sending private message failed'),
					#in second %s code replaces with nickname
					_('You are no longer in room "%s" or "%s" has left.') % \
					(room, nick)).get_response()
				return

		ChatControl.send_message(self, message)


class GroupchatControl(ChatControlBase):
	TYPE_ID = message_control.TYPE_GC

	def __init__(self, parent_win, contact, acct):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
					'muc_child_vbox', _('Group Chat'), contact, acct);

		self.room_jid = self.contact.jid
		self.nick = contact.name
		self.name = self.room_jid.split('@')[0]

		self.compact_view_always = gajim.config.get('always_compact_view_gc')
		self.gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')

		self._last_selected_contact = None # None or holds jid, account tuple
		# alphanum sorted
		self.muc_cmds = ['ban', 'chat', 'query', 'clear', 'close', 'compact', 'help', 'invite',
			'join', 'kick', 'leave', 'me', 'msg', 'nick', 'part', 'say', 'topic']
		# muc attention flag (when we are mentioned in a muc)
		# if True, the room has mentioned us
		self.attention_flag = False
		self.room_creation = time.time()
		self.nick_hits = []
		self.cmd_hits = []
		self.last_key_tabs = False

		self.subject = ''
		self.subject_tooltip = gtk.Tooltips()

		self.tooltip = tooltips.GCTooltip()

		self.allow_focus_out_line = True
		# holds the iter's offset which points to the end of --- line
		self.focus_out_end_iter_offset = None

		# connect the menuitems to their respective functions
		xm = gtk.glade.XML(GTKGUI_GLADE, 'gc_control_popup_menu', APP)
		xm.signal_autoconnect(self)
		self.gc_popup_menu = xm.get_widget('gc_control_popup_menu')

		self.name_label = self.xml.get_widget('banner_name_label')
		self.parent_win.window.connect('focus-in-event',
						self._on_window_focus_in_event)

		# set the position of the current hpaned
		self.hpaned_position = gajim.config.get('gc-hpaned-position')
		self.hpaned = self.xml.get_widget('hpaned')
		self.hpaned.set_position(self.hpaned_position)

		list_treeview = self.list_treeview = self.xml.get_widget('list_treeview')
		list_treeview.get_selection().connect('changed',
			self.on_list_treeview_selection_changed)
		list_treeview.connect('style-set', self.on_list_treeview_style_set)
		# we want to know when the the widget resizes, because that is
		# an indication that the hpaned has moved...
		# FIXME: Find a better indicator that the hpaned has moved.
		self.list_treeview.connect('size-allocate', self.on_treeview_size_allocate)

		#status_image, type, nickname, shown_nick
		store = gtk.TreeStore(gtk.Image, str, str, str)
		store.set_sort_column_id(C_TEXT, gtk.SORT_ASCENDING)
		column = gtk.TreeViewColumn('contacts')
		renderer_image = cell_renderer_image.CellRendererImage(0, 0)
		renderer_image.set_property('width', 20)
		column.pack_start(renderer_image, expand = False)
		column.add_attribute(renderer_image, 'image', 0)
		renderer_text = gtk.CellRendererText()
		column.pack_start(renderer_text, expand = True)
		column.set_attributes(renderer_text, markup = C_TEXT)
		column.set_cell_data_func(renderer_image, self.tree_cell_data_func, None)
		column.set_cell_data_func(renderer_text, self.tree_cell_data_func, None)

		self.list_treeview.append_column(column)
		self.list_treeview.set_model(store)

		# workaround to avoid gtk arrows to be shown
		column = gtk.TreeViewColumn() # 2nd COLUMN
		renderer = gtk.CellRendererPixbuf()
		column.pack_start(renderer, expand = False)
		self.list_treeview.append_column(column)
		column.set_visible(False)
		self.list_treeview.set_expander_column(column)

		# set an empty subject to show the room_jid
		self.set_subject('')
		self.got_disconnected() #init some variables

		self.update_ui()
		self.conv_textview.grab_focus()
		self.widget.show_all()

	def notify_on_new_messages(self):
		return gajim.config.get('notify_on_all_muc_messages') or self.attention_flag

	def _on_window_focus_in_event(self, widget, event):
		'''When window gets focus'''
		if self.parent_win.get_active_jid() == self.room_jid:
			self.allow_focus_out_line = True

	def tree_cell_data_func(self, column, renderer, model, iter, data=None):
		theme = gajim.config.get('roster_theme')
		if model.iter_parent(iter):
			bgcolor = gajim.config.get_per('themes', theme, 'contactbgcolor')
		else: # it is root (eg. group)
			bgcolor = gajim.config.get_per('themes', theme, 'groupbgcolor')
		if bgcolor:
			renderer.set_property('cell-background', bgcolor)
		else:
			renderer.set_property('cell-background', None)

	def on_treeview_size_allocate(self, widget, allocation):
		'''The MUC treeview has resized. Move the hpaned in all tabs to match'''
		self.hpaned_position = self.hpaned.get_position()
		self.hpaned.set_position(self.hpaned_position)

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
		self.draw_contact(self.nick)
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
		'''Markup the label if necessary. Returns a tuple such as:
		(new_label_str, color)
		either of which can be None
		if chatstate is given that means we have HE SENT US a chatstate'''
			
		has_focus = self.parent_win.window.get_property('has-toplevel-focus')
		current_tab = self.parent_win.get_active_control() == self
		color = None
		theme = gajim.config.get('roster_theme')
		if chatstate == 'attention' and (not has_focus or not current_tab):
			self.attention_flag = True
			color = gajim.config.get_per('themes', theme,
							'state_muc_directed_msg')
		elif chatstate:
			if chatstate == 'active' or (current_tab and has_focus):
				self.attention_flag = False
				color = gajim.config.get_per('themes', theme,
								'state_active_color')
			elif chatstate == 'newmsg' and (not has_focus or not current_tab) and\
					not self.attention_flag:
				color = gajim.config.get_per('themes', theme, 'state_muc_msg')
		if color:
			color = gtk.gdk.colormap_get_system().alloc_color(color)

		label_str = self.name
		return (label_str, color)

	def get_tab_image(self):
		# Set tab image (always 16x16); unread messages show the 'message' image
		img_16 = gajim.interface.roster.get_appropriate_state_images(self.room_jid)

		tab_image = None
		if self.attention_flag and gajim.config.get('show_unread_tab_icon'):
			tab_image = img_16['message']
		else:

			tab_image = img_16['muc_active']
		return tab_image

	def update_ui(self):
		ChatControlBase.update_ui(self)
		self.draw_roster()

	def prepare_context_menu(self):
		'''sets compact view menuitem active state
		sets active and sensitivity state for toggle_gpg_menuitem
		and remove possible 'Switch to' menuitems'''
		menu = self.gc_popup_menu
		childs = menu.get_children()
		# compact_view_menuitem
		childs[5].set_active(self.compact_view_current)
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
		pm_control = gajim.interface.msg_win_mgr.get_control(fjid)
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
			self._start_private_message(nick)
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
				# muc-specific chatstate
				self.parent_win.redraw_tab(self.contact, 'attention')
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
		self.subject = subject

		self.name_label.set_ellipsize(pango.ELLIPSIZE_END)
		subject = gtkgui_helpers.reduce_chars_newlines(subject, 0, 2)
		subject = gtkgui_helpers.escape_for_pango_markup(subject)
		self.name_label.set_markup(
		'<span weight="heavy" size="x-large">%s</span>\n%s' % (self.room_jid, subject))
		event_box = self.name_label.get_parent()
		if subject == '':
			self.subject = _('This room has no subject')

		# tooltip must always hold ALL the subject
		self.subject_tooltip.set_tip(event_box, self.subject)

	def got_connected(self):
		gajim.gc_connected[self.account][self.room_jid] = True
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

	def draw_roster(self):
		model = self.list_treeview.get_model()
		model.clear()
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
			self.add_contact_to_roster(nick, gc_contact.show, gc_contact.role,
						gc_contact.affiliation, gc_contact.status,
						gc_contact.jid)

	def on_send_pm(self, widget=None, model=None, iter=None, nick=None, msg=None):
		'''opens a chat window and msg is not None sends private message to a
		contact in a room'''
		if nick is None:
			nick = model[iter][C_NICK].decode('utf-8')
		fjid = gajim.construct_fjid(self.room_jid, nick) # 'fake' jid

		self._start_private_message(nick)
		if msg:
			gajim.interface.msg_win_mgr.get_control(fjid).send_message(msg)

	def draw_contact(self, nick, selected=False, focus=False):
		iter = self.get_contact_iter(nick)
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

	def chg_contact_status(self, nick, show, status, role, affiliation, jid, reason, actor,
				statusCode, new_nick):
		'''When an occupant changes his or her status'''
		if show == 'invisible':
			return

		if not role:
			role = 'visitor'
		if not affiliation:
			affiliation = 'none'

		if show in ('offline', 'error'):
			if statusCode == '307':
				if actor is None: # do not print 'kicked by None'
					s = _('%(nick)s has been kicked: %(reason)s') % {
						'nick': nick,
						'reason': reason }
				else:
					s = _('%(nick)s has been kicked by %(who)s: %(reason)s') % {
						'nick': nick,
						'who': actor,
						'reason': reason }
				self.print_conversation(s)
			elif statusCode == '301':
				if actor is None: # do not print 'banned by None'
					s = _('%(nick)s has been banned: %(reason)s') % {
						'nick': nick,
						'reason': reason }
				else:
					s = _('%(nick)s has been banned by %(who)s: %(reason)s') % {
						'nick': nick,
						'who': actor,
						'reason': reason }
				self.print_conversation(s, self.room_jid)
			elif statusCode == '303': # Someone changed his or her nick
				if nick == self.nick: # We changed our nick
					self.nick = new_nick
					s = _('You are now known as %s') % new_nick
				else:
					s = _('%s is now known as %s') % (nick, new_nick)
				self.print_conversation(s)

			if not gajim.awaiting_events[self.account].has_key(self.room_jid + '/' + nick):
				self.remove_contact(nick)
			else:
				c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
				c.show = show
				c.status = status
			if nick == self.nick and statusCode != '303': # We became offline
				self.got_disconnected()
		else:
			iter = self.get_contact_iter(nick)
			if not iter:
				iter = self.add_contact_to_roster(nick, show, role,
								affiliation, status, jid)
				if statusCode == '201': # We just created the room
					gajim.connections[self.account].request_gc_config(self.room_jid)
			else:
				actual_role = self.get_role(nick)
				if role != actual_role:
					self.remove_contact(nick)
					self.add_contact_to_roster(nick, show, role,
						affiliation, status, jid)
				else:
					c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
					if c.show == show and c.status == status and \
						c.affiliation == affiliation: #no change
						return
					c.show = show
					c.affiliation = affiliation
					c.status = status
					self.draw_contact(nick)

		self.parent_win.redraw_tab(self.contact)
		if (time.time() - self.room_creation) > 30 and \
				nick != self.nick and statusCode != '303':
			if show == 'offline':
				st = _('%s has left') % nick
			else:
				st = _('%s is now %s') % (nick, helpers.get_uf_show(show))
			if status:
				st += ' (' + status + ')'
			self.print_conversation(st)

	def add_contact_to_roster(self, nick, show, role, affiliation, status, jid = ''):
		model = self.list_treeview.get_model()
		role_name = helpers.get_uf_role(role, plural = True)

		resource = ''
		if jid:
			jids = jid.split('/', 1)
			j = jids[0]
			if len(jids) > 1:
				resource = jids[1]
		else:
			j = ''

		name = nick

		role_iter = self.get_role_iter(role)
		if not role_iter:
			role_iter = model.append(None,
				(gajim.interface.roster.jabber_state_images['16']['closed'], 'role', role,
				'<b>%s</b>' % role_name))
		iter = model.append(role_iter, (None, 'contact', nick, name))
		if not nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			gc_contact = gajim.contacts.create_gc_contact(room_jid = self.room_jid,
				name = nick, show = show, status = status, role = role,
				affiliation = affiliation, jid = j, resource = resource)
			gajim.contacts.add_gc_contact(self.account, gc_contact)
		self.draw_contact(nick)
		if nick == self.nick: # we became online
			self.got_connected()
		self.list_treeview.expand_row((model.get_path(role_iter)), False)
		return iter

	def get_role_iter(self, role):
		model = self.list_treeview.get_model()
		fin = False
		iter = model.get_iter_root()
		if not iter:
			return None
		while not fin:
			role_name = model[iter][C_NICK].decode('utf-8')
			if role == role_name:
				return iter
			iter = model.iter_next(iter)
			if not iter:
				fin = True
		return None

	def remove_contact(self, nick):
		'''Remove a user from the contacts_list'''
		model = self.list_treeview.get_model()
		iter = self.get_contact_iter(nick)
		if not iter:
			return
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		if gc_contact:
			gajim.contacts.remove_gc_contact(self.account, gc_contact)
		parent_iter = model.iter_parent(iter)
		model.remove(iter)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)

	def _process_command(self, message):
		if message[0] != '/':
			return False

		# Handle common commands
		if ChatControlBase._process_command(self, message):
			return True

		message = message[1:]
		message_array = message.split(' ', 1)
		command = message_array.pop(0).lower()
		if message_array == ['']:
			message_array = []

		if command == 'me':
			return False # This is not really a command
		
		if command == 'nick':
			# example: /nick foo
			if len(message_array):
				nick = message_array[0]
				gajim.connections[self.account].change_gc_nick(self.room_jid, nick)
				self.clear(self.msg_textview)
			else:
				self.get_command_help(command)
			return True
		elif command == 'query' or command == 'chat':
			# Open a chat window to the specified nick
			# example: /query foo
			if len(message_array):
				nick = message_array.pop(0)
				nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
				if nick in nicks:
					self.on_send_pm(nick = nick)
					self.clear(self.msg_textview)
				else:
					self.print_conversation(_('Nickname not found: %s') % nick)
			else:
				self.get_command_help(command)
			return True
		elif command == 'msg':
			# Send a message to a nick. Also opens a private message window.
			# example: /msg foo Hey, what's up?
			if len(message_array):
				message_array = message_array[0].split()
				nick = message_array.pop(0)
				room_nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
				if nick in room_nicks:
					privmsg = ' '.join(message_array)
					self.on_send_pm(nick=nick, msg=privmsg)
					self.clear(self.msg_textview)
				else:
					self.print_conversation(_('Nickname not found: %s') % nick)
			else:
				self.get_command_help(command)
			return True
		elif command == 'topic':
			# display or change the room topic
			# example: /topic : print topic
			# /topic foo : change topic to foo
			if len(message_array):
				new_topic = message_array.pop(0)
				gajim.connections[self.account].send_gc_subject(self.room_jid,
					new_topic)
			else:
				self.print_conversation(self.subject)
			self.clear(self.msg_textview)
			return True
		elif command == 'invite':
			# invite a user to a room for a reason
			# example: /invite user@example.com reason
			if len(message_array):
				message_array = message_array[0].split()
				invitee = message_array.pop(0)
				if invitee.find('@') >= 0:
					reason = ' '.join(message_array)
					gajim.connections[self.account].send_invite(self.room_jid,
						invitee, reason)
					s = _('Invited %(contact_jid)s to %(room_jid)s.') % {
						'contact_jid': invitee,
						'room_jid': self.room_jid}
					self.print_conversation(s)
					self.clear(self.msg_textview)
				else:
					#%s is something the user wrote but it is not a jid so we inform
					s = _('%s does not appear to be a valid JID') % invitee
					self.print_conversation(s)
			else:
				self.get_command_help(command)
			return True
		elif command == 'join':
			# example: /join room@conference.example.com/nick
			if len(message_array):
				message_array = message_array[0]
				if message_array.find('@') >= 0:
					room, servernick = message_array.split('@')
					if servernick.find('/') >= 0:
						server, nick = servernick.split('/', 1)
					else:
						server = servernick
						nick = ''
					#join_gc window is needed in order to provide for password entry.
					if gajim.interface.instances[self.account].has_key('join_gc'):
						gajim.interface.instances[self.account]['join_gc'].\
							window.present()
					else:
						try:
							gajim.interface.instances[self.account]['join_gc'] =\
								dialogs.JoinGroupchatWindow(self.account,
									server = server, room = room, nick = nick)
						except RuntimeError:
							pass
					self.clear(self.msg_textview)
				else:
					#%s is something the user wrote but it is not a jid so we inform
					s = _('%s does not appear to be a valid JID') % message_array
					self.print_conversation(s)
			else:
				self.get_command_help(command)
			return True
		elif command == 'leave' or command == 'part' or command == 'close':
			# Leave the room and close the tab or window
			# FIXME: Sometimes this doesn't actually leave the room. Why?
			reason = 'offline'
			if len(message_array):
				reason = message_array.pop(0)
			gajim.connections[self.account].send_gc_status(self.nick, self.room_jid,
							show='offline', status=reason)
			self.parent_win.remove_tab(self.contact)
			return True
		elif command == 'ban':
			if len(message_array):
				message_array = message_array[0].split()
				nick = message_array.pop(0)
				room_nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
				reason = ' '.join(message_array)
				if nick in room_nicks:
					ban_jid = gajim.construct_fjid(self.room_jid, nick)
					gajim.connections[self.account].gc_set_affiliation(self.room_jid,
						ban_jid, 'outcast', reason)
					self.clear(self.msg_textview)
				elif nick.find('@') >= 0:
					gajim.connections[self.account].gc_set_affiliation(self.room_jid,
						nick, 'outcast', reason)
					self.clear(self.msg_textview)
				else:
					self.print_conversation(_('Nickname not found: %s') % nick)
			else:
				self.get_command_help(command)
			return True
		elif command == 'kick':
			if len(message_array):
				message_array = message_array[0].split()
				nick = message_array.pop(0)
				room_nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
				reason = ' '.join(message_array)
				if nick in room_nicks:
					gajim.connections[self.account].gc_set_role(self.room_jid, nick,
						'none', reason)
					self.clear(self.msg_textview)
				else:
					self.print_conversation(_('Nickname not found: %s') % nick)
			else:
				self.get_command_help(command)
			return True
		elif command == 'help':
			if len(message_array):
				subcommand = message_array.pop(0)
				self.get_command_help(subcommand)
			else:
				self.get_command_help(command)
			self.clear(self.msg_textview)
			return True
		elif command == 'say':
			if len(message_array):
				gajim.connections[self.account].send_gc_message(self.room_jid,
										message[4:])
				self.clear(self.msg_textview)
			else:
				self.get_command_help(command)
			return True
		else:
			self.print_conversation(_('No such command: /%s (if you want to send this, '
						'prefix it with /say)') % command)
			return True

		return False

	def send_message(self, message):
		'''call this function to send our message'''
		if not message:
			return

		if message != '' or message != '\n':
			self.save_sent_message(message)

			if not self._process_command(message):
				# Send the message
				gajim.connections[self.account].send_gc_message(self.room_jid, message)
				self.msg_textview.get_buffer().set_text('')
				self.msg_textview.grab_focus()

	def get_command_help(self, command):
		if command == 'help':
			self.print_conversation(_('Commands: %s') % self.muc_cmds)
		elif command == 'ban':
			s = _('Usage: /%s <nickname|JID> [reason], bans the JID from the room.'
			' The nickname of an occupant may be substituted, but not if it contains "@".'
			' If the JID is currently in the room, he/she/it will also be kicked.'
			' Does NOT support spaces in nickname.') % command
			self.print_conversation(s)
		elif command == 'chat' or command == 'query':
			self.print_conversation(_('Usage: /%s <nickname>, opens a private chat '
						'window to the specified occupant.') % command)
		elif command == 'clear':
			self.print_conversation(_('Usage: /%s, clears the text window.') % command)
		elif command == 'close' or command == 'leave' or command == 'part':
			self.print_conversation(_('Usage: /%s [reason], closes the current window '
						'or tab, displaying reason if specified.') % command)
		elif command == 'compact':
			self.print_conversation(_('Usage: /%s, sets the groupchat window to compact '
						'mode.') % command)
		elif command == 'invite':
			self.print_conversation(_('Usage: /%s <JID> [reason], invites JID to the '
						'current room, optionally providing a reason.') % command)
		elif command == 'join':
			self.print_conversation(_('Usage: /%s <room>@<server>[/nickname], offers to '
						'join room@server optionally using specified '
						'nickname.') % command)
		elif command == 'kick':
			self.print_conversation(_('Usage: /%s <nickname> [reason], removes the occupant '
						'specified by nickname from the room and optionally '
						'displays a reason. Does NOT support spaces in '
						'nickname.') % command)
		elif command == 'me':
			self.print_conversation(_('Usage: /%s <action>, sends action to the current '
						'room. Use third person. (e.g. /%s explodes.)') %\
						(command, command))
		elif command == 'msg':
			s = _('Usage: /%s <nickname> [message], opens a private message window and '
				'sends message to the occupant specified by nickname.') % command
			self.print_conversation(s)
		elif command == 'nick':
			s = _('Usage: /%s <nickname>, changes your nickname in current room.') % command
			self.print_conversation(s)
		elif command == 'topic':
			self.print_conversation(_('Usage: /%s [topic], displays or updates the current '
						'room topic.') % command)
		elif command == 'say':
			self.print_conversation(_('Usage: /%s <message>, sends a message without '
						'looking for other commands.') % command)
		else:
			self.print_conversation(_('No help info for /%s') % command)

	def get_role(self, nick):
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		if gc_contact:
			return gc_contact.role
		else:
			return 'visitor'

	def show_change_nick_input_dialog(self, title, prompt, proposed_nick = None):
		'''asks user for new nick and on ok it sets it on room'''
		instance = dialogs.InputDialog(title, prompt, proposed_nick)
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			nick = instance.input_entry.get_text().decode('utf-8')
			gajim.connections[self.account].change_gc_nick(self.room_jid, nick)

	def shutdown(self):
		gajim.connections[self.account].send_gc_status(self.nick, self.room_jid,
							show='offline', status='offline')
		# They can already be removed by the destroy function
		if self.room_jid in gajim.contacts.get_gc_list(self.account):
			gajim.contacts.remove_room(self.account, self.room_jid)
			del gajim.gc_connected[self.account][self.room_jid]

	def allow_shutdown(self):
		retval = True
		# whether to ask for comfirmation before closing muc
		if not gajim.config.get('confirm_close_muc'):
			gajim.config.set('noconfirm_close_muc_rooms', '')
		else:
			excludes = gajim.config.get('noconfirm_close_muc_rooms')
			excludes = excludes.split(' ')
			if gajim.gc_connected[self.account][self.room_jid] and \
					self.room_jid not in excludes:
				pritext = _('Are you sure you want to leave room "%s"?') % self.name
				sectext = _('If you close this window, you will be disconnected '
						'from this room.')

				dialog = dialogs.ConfirmationDialogCheck(pritext, sectext,
							_('Do _not ask me about closing "%s" again' %\
							self.name))

				if dialog.get_response() != gtk.RESPONSE_OK:
					retval = False

				if dialog.is_checked():
					excludes = gajim.config.get('noconfirm_close_muc_rooms')
					excludes += ' %s' % self.room_jid
					gajim.config.set('noconfirm_close_muc_rooms', excludes)
				dialog.destroy()

		return retval

	def set_control_active(self, state):
		self.attention_flag = False
		ChatControlBase.set_control_active(self, state)
		if not state:
			# add the focus-out line to the tab we are leaving
			self.check_and_possibly_add_focus_out_line()

	def get_specific_unread(self):
		# returns the number of the number of unread msgs
		# for room_jid & number of unread private msgs with each contact
		# that we have
		nb = 0
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			fjid = self.room_jid + '/' + nick
			if gajim.awaiting_events[self.account].has_key(fjid):
				# gc can only have messages as event
				nb += len(gajim.awaiting_events[self.account][fjid])
		return nb

	def _on_change_subject_menuitem_activate(self, widget):
		instance = dialogs.InputDialog(_('Changing Subject'),
			_('Please specify the new subject:'), self.subject)
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			# Note, we don't update self.subject since we don't know whether it will work yet
			subject = instance.input_entry.get_text().decode('utf-8')
			gajim.connections[self.account].send_gc_subject(self.room_jid, subject)

	def _on_change_nick_menuitem_activate(self, widget):
		title = _('Changing Nickname')
		prompt = _('Please specify the new nickname you want to use:')
		self.show_change_nick_input_dialog(title, prompt, self.nick)

	def _on_configure_room_menuitem_activate(self, widget):
		gajim.connections[self.account].request_gc_config(self.room_jid)

	def _on_bookmark_room_menuitem_activate(self, widget):
		bm = {
			'name': self.name,
			'jid': self.room_jid,
			'autojoin': '0',
			'password': '',
			'nick': self.nick
		}

		for bookmark in gajim.connections[self.account].bookmarks:
			if bookmark['jid'] == bm['jid']:
				dialogs.ErrorDialog(
					_('Bookmark already set'),
					_('Room "%s" is already in your bookmarks.') % bm['jid']).\
						get_response()
				return

		gajim.connections[self.account].bookmarks.append(bm)
		gajim.connections[self.account].store_bookmarks()

		gajim.interface.roster.make_menu()

		dialogs.InformationDialog(
				_('Bookmark has been added successfully'),
				_('You can manage your bookmarks via Actions menu in your roster.'))

	def handle_message_textview_mykey_press(self, widget, event_keyval, event_keymod):
		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_room(). for this singal see message_textview.py

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		message_buffer = widget.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False).decode('utf-8')

		if event.keyval == gtk.keysyms.Tab: # TAB
			cursor_position = message_buffer.get_insert()
			end_iter = message_buffer.get_iter_at_mark(cursor_position)
			text = message_buffer.get_text(start_iter, end_iter, False).decode('utf-8')
			if not text or text.endswith(' '):
				# if we are nick cycling, last char will always be space
				if not self.last_key_tabs:
					return False

			splitted_text = text.split()
			# command completion
			if text.startswith('/') and len(splitted_text) == 1:
				text = splitted_text[0]
				if len(text) == 1: # user wants to cycle all commands
					self.cmd_hits = self.muc_cmds
				else:
					# cycle possible commands depending on what the user typed
					if self.last_key_tabs and len(self.cmd_hits) and \
					self.cmd_hits[0].startswith(text.lstrip('/')):
						self.cmd_hits.append(self.cmd_hits[0])
						self.cmd_hits.pop(0)
					else: # find possible commands
						self.cmd_hits = []
						for cmd in self.muc_cmds:
							if cmd.startswith(text.lstrip('/')):
								self.cmd_hits.append(cmd)
				if len(self.cmd_hits):
					message_buffer.delete(start_iter, end_iter)
					message_buffer.insert_at_cursor('/' + self.cmd_hits[0] + ' ')
					self.last_key_tabs = True
				return True

			# nick completion
			# check if tab is pressed with empty message
			if len(splitted_text): # if there are any words
				begin = splitted_text[-1] # last word we typed

				if len(self.nick_hits) and \
						self.nick_hits[0].startswith(begin.replace(
						self.gc_refer_to_nick_char, '')) and \
						self.last_key_tabs: # we should cycle
					self.nick_hits.append(self.nick_hits[0])
					self.nick_hits.pop(0)
				else:
					self.nick_hits = [] # clear the hit list
					list_nick = gajim.contacts.get_nick_list(self.account,
										self.room_jid)
					for nick in list_nick:
						if nick.lower().startswith(begin.lower()):
							# the word is the begining of a nick
							self.nick_hits.append(nick)
				if len(self.nick_hits):
					if len(splitted_text) == 1: # This is the 1st word of the line
						add = self.gc_refer_to_nick_char + ' '
					else:
						add = ' '
					start_iter = end_iter.copy()
					if self.last_key_tabs and begin.endswith(', '):
						# have to accomodate for the added space from last
						# completion
						start_iter.backward_chars(len(begin) + 2)
					elif self.last_key_tabs:
						# have to accomodate for the added space from last
						# completion
						start_iter.backward_chars(len(begin) + 1)
					else:
						start_iter.backward_chars(len(begin))

					message_buffer.delete(start_iter, end_iter)
					message_buffer.insert_at_cursor(self.nick_hits[0] + add)
					self.last_key_tabs = True
					return True
			self.last_key_tabs = False

	def on_list_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			widget.get_selection().unselect_all()

	def on_list_treeview_row_expanded(self, widget, iter, path):
		'''When a row is expanded: change the icon of the arrow'''
		model = widget.get_model()
		image = gajim.interface.roster.jabber_state_images['16']['opened']
		model[iter][C_IMG] = image

	def on_list_treeview_row_collapsed(self, widget, iter, path):
		'''When a row is collapsed: change the icon of the arrow'''
		model = widget.get_model()
		image = gajim.interface.roster.jabber_state_images['16']['closed']
		model[iter][C_IMG] = image

	def kick(self, widget, nick):
		'''kick a user'''
		# ask for reason
		instance = dialogs.InputDialog(_('Kicking %s') % nick,
					_('You may specify a reason below:'))
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			reason = instance.input_entry.get_text().decode('utf-8')
		else:
			return # stop kicking procedure
		gajim.connections[self.account].gc_set_role(self.room_jid, nick, 'none',
								reason)

	def mk_menu(self, event, iter):
		'''Make contact's popup menu'''
		model = self.list_treeview.get_model()
		nick = model[iter][C_NICK].decode('utf-8')
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		jid = c.jid
		target_affiliation = c.affiliation
		target_role = c.role

		# looking for user's affiliation and role
		user_nick = self.nick
		user_affiliation = gajim.contacts.get_gc_contact(self.account, self.room_jid,
			user_nick).affiliation
		user_role = self.get_role(user_nick)

		# making menu from glade
		xml = gtk.glade.XML(GTKGUI_GLADE, 'gc_occupants_menu', APP)

		# these conditions were taken from JEP 0045
		item = xml.get_widget('kick_menuitem')
		if user_role != 'moderator' or \
			(user_affiliation == 'admin' and target_affiliation == 'owner') or \
			(user_affiliation == 'member' and target_affiliation in ('admin', 'owner')) or \
			(user_affiliation == 'none' and target_affiliation != 'none'):
			item.set_sensitive(False)
		item.connect('activate', self.kick, nick)

		item = xml.get_widget('voice_checkmenuitem')
		item.set_active(target_role != 'visitor')
		if user_role != 'moderator' or \
			user_affiliation == 'none' or \
			(user_affiliation=='member' and target_affiliation!='none') or \
			target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		item.connect('activate', self.on_voice_checkmenuitem_activate, nick)

		item = xml.get_widget('moderator_checkmenuitem')
		item.set_active(target_role == 'moderator')
		if not user_affiliation in ('admin', 'owner') or \
			target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		item.connect('activate', self.on_moderator_checkmenuitem_activate, nick)

		item = xml.get_widget('ban_menuitem')
		if not user_affiliation in ('admin', 'owner') or \
			(target_affiliation in ('admin', 'owner') and\
			user_affiliation != 'owner'):
			item.set_sensitive(False)
		item.connect('activate', self.ban, jid)

		item = xml.get_widget('member_checkmenuitem')
		item.set_active(target_affiliation != 'none')
		if not user_affiliation in ('admin', 'owner') or \
			(user_affiliation != 'owner' and target_affiliation in ('admin','owner')):
			item.set_sensitive(False)
		item.connect('activate', self.on_member_checkmenuitem_activate, jid)

		item = xml.get_widget('admin_checkmenuitem')
		item.set_active(target_affiliation in ('admin', 'owner'))
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		item.connect('activate', self.on_admin_checkmenuitem_activate, jid)

		item = xml.get_widget('owner_checkmenuitem')
		item.set_active(target_affiliation == 'owner')
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		item.connect('activate', self.on_owner_checkmenuitem_activate, jid)

		item = xml.get_widget('information_menuitem')
		item.connect('activate', self.on_info, nick)

		item = xml.get_widget('history_menuitem')
		item.connect('activate', self.on_history, nick)

		item = xml.get_widget('add_to_roster_menuitem')
		if not jid:
			item.set_sensitive(False)
		item.connect('activate', self.on_add_to_roster, jid)

		item = xml.get_widget('send_private_message_menuitem')
		item.connect('activate', self.on_send_pm, model, iter)

		# show the popup now!
		menu = xml.get_widget('gc_occupants_menu')
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()

	def _start_private_message(self, nick):
		gc_c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		c = gajim.contacts.contact_from_gc_contact(gc_c)
		nick_jid = c.jid

		win = gajim.interface.msg_win_mgr.get_window(nick_jid)
		if not win:
			gajim.interface.roster.new_chat(c, self.account, private_chat = True)
			win = gajim.interface.msg_win_mgr.get_window(nick_jid)
		win.set_active_tab(nick_jid)
		win.window.present()

	def on_list_treeview_row_activated(self, widget, path, col = 0):
		'''When an iter is double clicked: open the chat window'''
		model = widget.get_model()
		iter = model.get_iter(path)
		if len(path) == 1: # It's a group
			if (widget.row_expanded(path)):
				widget.collapse_row(path)
			else:
				widget.expand_row(path, False)
		else: # We want to send a private message
			nick = model[iter][C_NICK].decode('utf-8')
			self._start_private_message(nick)

	def on_list_treeview_button_press_event(self, widget, event):
		'''popup user's group's or agent menu'''
		if event.button == 3: # right click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter = model.get_iter(path)
			if len(path) == 2:
				self.mk_menu(event, iter)
			return True

		elif event.button == 2: # middle click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter = model.get_iter(path)
			if len(path) == 2:
				nick = model[iter][C_NICK].decode('utf-8')
				self._start_private_message(nick)
			return True

		elif event.button == 1: # left click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return

			model = widget.get_model()
			iter = model.get_iter(path)
			nick = model[iter][C_NICK].decode('utf-8')
			if not nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
				#it's a group
				if x < 20: # first cell in 1st column (the arrow SINGLE clicked)
					if (widget.row_expanded(path)):
						widget.collapse_row(path)
					else:
						widget.expand_row(path, False)

	def on_list_treeview_motion_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id != props[0]:
				self.tooltip.hide_tooltip()
		if props:
			[row, col, x, y] = props
			iter = None
			try:
				iter = model.get_iter(row)
			except:
				self.tooltip.hide_tooltip()
				return
			typ = model[iter][C_TYPE].decode('utf-8')
			if typ == 'contact':
				account = self.account

				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					nick = model[iter][C_NICK].decode('utf-8')
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, gajim.contacts.get_gc_contact(account,
						self.room_jid, nick))

	def on_list_treeview_leave_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id == props[0]:
				self.tooltip.hide_tooltip()

	def show_tooltip(self, contact):
		pointer = self.list_treeview.get_pointer()
		props = self.list_treeview.get_path_at_pos(pointer[0], pointer[1])
		if props and self.tooltip.id == props[0]:
			# check if the current pointer is at the same path
			# as it was before setting the timeout
			rect = self.list_treeview.get_cell_area(props[0],props[1])
			position = self.list_treeview.window.get_origin()
			pointer = self.parent_win.window.get_pointer()
			self.tooltip.show_tooltip(contact, (0, rect.height),
				(self.parent_win.window.get_screen().get_display().get_pointer()[1],
				position[1] + rect.y))
		else:
			self.tooltip.hide_tooltip()


	def grant_voice(self, widget, nick):
		'''grant voice privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick, 'participant')

	def revoke_voice(self, widget, nick):
		'''revoke voice privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick, 'visitor')

	def grant_moderator(self, widget, nick):
		'''grant moderator privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick, 'moderator')

	def revoke_moderator(self, widget, nick):
		'''revoke moderator privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick, 'participant')

	def ban(self, widget, jid):
		'''ban a user'''
		# to ban we know the real jid. so jid is not fakejid
		nick = gajim.get_nick_from_jid(jid)
		# ask for reason
		instance = dialogs.InputDialog(_('Banning %s') % nick,
			_('You may specify a reason below:'))
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			reason = instance.input_entry.get_text().decode('utf-8')
		else:
			return # stop banning procedure
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
								'outcast', reason)

	def grant_membership(self, widget, jid):
		'''grant membership privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
								'member')

	def revoke_membership(self, widget, jid):
		'''revoke membership privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
								'none')

	def grant_admin(self, widget, jid):
		'''grant administrative privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid, 'admin')

	def revoke_admin(self, widget, jid):
		'''revoke administrative privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'member')

	def grant_owner(self, widget, jid):
		'''grant owner privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid, 'owner')

	def revoke_owner(self, widget, jid):
		'''revoke owner privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid, 'admin')

	def on_info(self, widget, nick):
		'''Call vcard_information_window class to display user's information'''
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		c2 = gajim.contacts.contact_from_gc_contact(c)
		if gajim.interface.instances[self.account]['infos'].has_key(c2.jid):
			gajim.interface.instances[self.account]['infos'][c2.jid].window.present()
		else:
			gajim.interface.instances[self.account]['infos'][c2.jid] = \
				vcard.VcardWindow(c2, self.account, False)

	def on_history(self, widget, nick):
		jid = gajim.construct_fjid(self.room_jid, nick)
		self._on_history_menuitem_activate(widget = widget, jid = jid)

	def on_add_to_roster(self, widget, jid):
		dialogs.AddNewContactWindow(self.account, jid)

	def on_voice_checkmenuitem_activate(self, widget, nick):
		if widget.get_active():
			self.grant_voice(widget, nick)
		else:
			self.revoke_voice(widget, nick)

	def on_moderator_checkmenuitem_activate(self, widget, nick):
		if widget.get_active():
			self.grant_moderator(widget, nick)
		else:
			self.revoke_moderator(widget, nick)

	def on_member_checkmenuitem_activate(self, widget, jid):
		if widget.get_active():
			self.grant_membership(widget, jid)
		else:
			self.revoke_membership(widget, jid)

	def on_admin_checkmenuitem_activate(self, widget, jid):
		if widget.get_active():
			self.grant_admin(widget, jid)
		else:
			self.revoke_admin(widget, jid)

	def on_owner_checkmenuitem_activate(self, widget, jid):
		if widget.get_active():
			self.grant_owner(widget, jid)
		else:
			self.revoke_owner(widget, jid)
