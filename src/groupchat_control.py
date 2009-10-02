# -*- coding:utf-8 -*-
## src/groupchat_control.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2007-2008 Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os
import time
import gtk
import pango
import gobject
import gtkgui_helpers
import message_control
import tooltips
import dialogs
import config
import vcard
import cell_renderer_image

from common import gajim
from common import helpers

from chat_control import ChatControl
from chat_control import ChatControlBase
from common.exceptions import GajimGeneralException

from command_system.implementation.hosts import PrivateChatCommands
from command_system.implementation.hosts import GroupChatCommands

import logging
log = logging.getLogger('gajim.groupchat_control')

#(status_image, type, nick, shown_nick)
(
C_IMG, # image to show state (online, new message etc)
C_NICK, # contact nickame or ROLE name
C_TYPE, # type of the row ('contact' or 'role')
C_TEXT, # text shown in the cellrenderer
C_AVATAR, # avatar of the contact
) = range(5)

def set_renderer_color(treeview, renderer, set_background=True):
	'''set style for group row, using PRELIGHT system color'''
	if set_background:
		bgcolor = treeview.style.bg[gtk.STATE_PRELIGHT]
		renderer.set_property('cell-background-gdk', bgcolor)
	else:
		fgcolor = treeview.style.fg[gtk.STATE_PRELIGHT]
		renderer.set_property('foreground-gdk', fgcolor)

def tree_cell_data_func(column, renderer, model, iter_, tv=None):
	# cell data func is global, because we don't want it to keep
	# reference to GroupchatControl instance (self)
	theme = gajim.config.get('roster_theme')
	# allocate space for avatar only if needed
	parent_iter = model.iter_parent(iter_)
	if isinstance(renderer, gtk.CellRendererPixbuf):
		avatar_position = gajim.config.get('avatar_position_in_roster')
		if avatar_position == 'right':
			renderer.set_property('xalign', 1) # align pixbuf to the right
		else:
			renderer.set_property('xalign', 0.5)
		if parent_iter and (model[iter_][C_AVATAR] or avatar_position == 'left'):
			renderer.set_property('visible', True)
			renderer.set_property('width', gajim.config.get('roster_avatar_width'))
		else:
			renderer.set_property('visible', False)
	if parent_iter:
		bgcolor = gajim.config.get_per('themes', theme, 'contactbgcolor')
		if bgcolor:
			renderer.set_property('cell-background', bgcolor)
		else:
			renderer.set_property('cell-background', None)
		if isinstance(renderer, gtk.CellRendererText):
			# foreground property is only with CellRendererText
			color = gajim.config.get_per('themes', theme, 'contacttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
	else: # it is root (eg. group)
		bgcolor = gajim.config.get_per('themes', theme, 'groupbgcolor')
		if bgcolor:
			renderer.set_property('cell-background', bgcolor)
		else:
			set_renderer_color(tv, renderer)
		if isinstance(renderer, gtk.CellRendererText):
			# foreground property is only with CellRendererText
			color = gajim.config.get_per('themes', theme, 'grouptextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				set_renderer_color(tv, renderer, False)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))

class PrivateChatControl(ChatControl):
	TYPE_ID = message_control.TYPE_PM

   # Set a command host to bound to. Every command given through a private chat
   # will be processed with this command host.
	COMMAND_HOST = PrivateChatCommands

	def __init__(self, parent_win, gc_contact, contact, account, session):
		room_jid = contact.jid.split('/')[0]
		room_ctrl = gajim.interface.msg_win_mgr.get_gc_control(room_jid, account)
		if room_jid in gajim.interface.minimized_controls[account]:
			room_ctrl = gajim.interface.minimized_controls[account][room_jid]
		if room_ctrl:
			self.room_name = room_ctrl.name
		else:
			self.room_name = room_jid
		self.gc_contact = gc_contact
		ChatControl.__init__(self, parent_win, contact, account, session)
		self.TYPE_ID = 'pm'

	def send_message(self, message, xhtml=None, process_commands=True):
		'''call this function to send our message'''
		if not message:
			return

		message = helpers.remove_invalid_xml_chars(message)

		if not message:
			return

		# We need to make sure that we can still send through the room and that
		# the recipient did not go away
		contact = gajim.contacts.get_first_contact_from_jid(self.account,
			self.contact.jid)
		if contact is None:
			# contact was from pm in MUC
			room, nick = gajim.get_room_and_nick_from_fjid(self.contact.jid)
			gc_contact = gajim.contacts.get_gc_contact(self.account, room, nick)
			if not gc_contact:
				dialogs.ErrorDialog(
					_('Sending private message failed'),
					#in second %s code replaces with nickname
					_('You are no longer in group chat "%(room)s" or "%(nick)s" has '
					'left.') % {'room': room, 'nick': nick})
				return

		ChatControl.send_message(self, message, xhtml=xhtml,
				process_commands=process_commands)

	def update_ui(self):
		if self.contact.show == 'offline':
			self.got_disconnected()
		else:
			self.got_connected()
		ChatControl.update_ui(self)

	def update_contact(self):
		self.contact = gajim.contacts.contact_from_gc_contact(self.gc_contact)

	def begin_e2e_negotiation(self):
		self.no_autonegotiation = True

		if not self.session:
			fjid = self.gc_contact.get_full_jid()
			new_sess = gajim.connections[self.account].make_new_session(fjid, type_=self.type_id)
			self.set_session(new_sess)

		self.session.negotiate_e2e(False)

class GroupchatControl(ChatControlBase):
	TYPE_ID = message_control.TYPE_GC

   # Set a command host to bound to. Every command given through a group chat
   # will be processed with this command host.
	COMMAND_HOST = GroupChatCommands

	def __init__(self, parent_win, contact, acct, is_continued=False):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
					'muc_child_vbox', contact, acct)

		self.is_continued=is_continued
		self.is_anonymous = True

		# Controls the state of autorejoin.
		# None - autorejoin is neutral.
		# False - autorejoin is to be prevented (gets reset to initial state in
		#         got_connected()).
		# int - autorejoin is being active and working (gets reset to initial
		#       state in got_connected()).
		self.autorejoin = None

		self.actions_button = self.xml.get_widget('muc_window_actions_button')
		id_ = self.actions_button.connect('clicked',
			self.on_actions_button_clicked)
		self.handlers[id_] = self.actions_button

		widget = self.xml.get_widget('change_nick_button')
		id_ = widget.connect('clicked', self._on_change_nick_menuitem_activate)
		self.handlers[id_] = widget

		widget = self.xml.get_widget('change_subject_button')
		id_ = widget.connect('clicked', self._on_change_subject_menuitem_activate)
		self.handlers[id_] = widget

		widget = self.xml.get_widget('bookmark_button')
		for bm in gajim.connections[self.account].bookmarks:
			if bm['jid'] == self.contact.jid:
				widget.hide()
				break
		else:
			id_ = widget.connect('clicked',
				self._on_bookmark_room_menuitem_activate)
			self.handlers[id_] = widget
			widget.show()

		widget = self.xml.get_widget('list_treeview')
		id_ = widget.connect('row_expanded', self.on_list_treeview_row_expanded)
		self.handlers[id_] = widget

		id_ = widget.connect('row_collapsed', self.on_list_treeview_row_collapsed)
		self.handlers[id_] = widget

		id_ = widget.connect('row_activated',
			self.on_list_treeview_row_activated)
		self.handlers[id_] = widget

		id_ = widget.connect('button_press_event',
			self.on_list_treeview_button_press_event)
		self.handlers[id_] = widget

		id_ = widget.connect('key_press_event',
			self.on_list_treeview_key_press_event)
		self.handlers[id_] = widget

		id_ = widget.connect('motion_notify_event',
			self.on_list_treeview_motion_notify_event)
		self.handlers[id_] = widget

		id_ = widget.connect('leave_notify_event',
			self.on_list_treeview_leave_notify_event)
		self.handlers[id_] = widget

		self.room_jid = self.contact.jid
		self.nick = contact.name.decode('utf-8')
		self.new_nick = ''
		self.name = ''
		for bm in gajim.connections[self.account].bookmarks:
			if bm['jid'] == self.room_jid:
				self.name = bm['name']
				break
		if not self.name:
			self.name = self.room_jid.split('@')[0]

		compact_view = gajim.config.get('compact_view')
		self.chat_buttons_set_visible(compact_view)
		self.widget_set_visible(self.xml.get_widget('banner_eventbox'),
			gajim.config.get('hide_groupchat_banner'))
		self.widget_set_visible(self.xml.get_widget('list_scrolledwindow'),
			gajim.config.get('hide_groupchat_occupants_list'))

		self._last_selected_contact = None # None or holds jid, account tuple

		# muc attention flag (when we are mentioned in a muc)
		# if True, the room has mentioned us
		self.attention_flag = False

		# sorted list of nicks who mentioned us (last at the end)
		self.attention_list = []
		self.room_creation = int(time.time()) # Use int to reduce mem usage
		self.nick_hits = []
		self.last_key_tabs = False

		self.subject = ''
		self.subject_tooltip = gtk.Tooltips()

		self.tooltip = tooltips.GCTooltip()

		# nickname coloring
		self.gc_count_nicknames_colors = 0
		self.gc_custom_colors = {}
		self.number_of_colors = len(gajim.config.get('gc_nicknames_colors').\
			split(':'))

		self.name_label = self.xml.get_widget('banner_name_label')
		self.event_box = self.xml.get_widget('banner_eventbox')

		# set the position of the current hpaned
		hpaned_position = gajim.config.get('gc-hpaned-position')
		self.hpaned = self.xml.get_widget('hpaned')
		self.hpaned.set_position(hpaned_position)

		self.list_treeview = self.xml.get_widget('list_treeview')
		selection = self.list_treeview.get_selection()
		id_ = selection.connect('changed',
				self.on_list_treeview_selection_changed)
		self.handlers[id_] = selection
		id_ = self.list_treeview.connect('style-set',
			self.on_list_treeview_style_set)
		self.handlers[id_] = self.list_treeview
		# we want to know when the the widget resizes, because that is
		# an indication that the hpaned has moved...
		# FIXME: Find a better indicator that the hpaned has moved.
		id_ = self.list_treeview.connect('size-allocate',
			self.on_treeview_size_allocate)
		self.handlers[id_] = self.list_treeview
		#status_image, shown_nick, type, nickname, avatar
		store = gtk.TreeStore(gtk.Image, str, str, str, gtk.gdk.Pixbuf)
		store.set_sort_func(C_NICK, self.tree_compare_iters)
		store.set_sort_column_id(C_NICK, gtk.SORT_ASCENDING)
		self.list_treeview.set_model(store)

		# columns

		# this col has 3 cells:
		# first one img, second one text, third is sec pixbuf
		column = gtk.TreeViewColumn()

		def add_avatar_renderer():
			renderer_pixbuf = gtk.CellRendererPixbuf() # avatar image
			column.pack_start(renderer_pixbuf, expand=False)
			column.add_attribute(renderer_pixbuf, 'pixbuf', C_AVATAR)
			column.set_cell_data_func(renderer_pixbuf, tree_cell_data_func,
				self.list_treeview)

		if gajim.config.get('avatar_position_in_roster') == 'left':
			add_avatar_renderer()

		renderer_image = cell_renderer_image.CellRendererImage(0, 0) # status img
		renderer_image.set_property('width', 26)
		column.pack_start(renderer_image, expand=False)
		column.add_attribute(renderer_image, 'image', C_IMG)
		column.set_cell_data_func(renderer_image, tree_cell_data_func,
			self.list_treeview)

		renderer_text = gtk.CellRendererText() # nickname
		column.pack_start(renderer_text, expand=True)
		column.add_attribute(renderer_text, 'markup', C_TEXT)
		renderer_text.set_property("ellipsize", pango.ELLIPSIZE_END)
		column.set_cell_data_func(renderer_text, tree_cell_data_func,
			self.list_treeview)

		if gajim.config.get('avatar_position_in_roster') == 'right':
			add_avatar_renderer()

		self.list_treeview.append_column(column)

		# workaround to avoid gtk arrows to be shown
		column = gtk.TreeViewColumn() # 2nd COLUMN
		renderer = gtk.CellRendererPixbuf()
		column.pack_start(renderer, expand=False)
		self.list_treeview.append_column(column)
		column.set_visible(False)
		self.list_treeview.set_expander_column(column)

		gajim.gc_connected[self.account][self.room_jid] = False
		# disable win, we are not connected yet
		ChatControlBase.got_disconnected(self)

		self.update_ui()
		self.conv_textview.tv.grab_focus()
		self.widget.show_all()

	def tree_compare_iters(self, model, iter1, iter2):
		'''Compare two iters to sort them'''
		type1 = model[iter1][C_TYPE]
		type2 = model[iter2][C_TYPE]
		if not type1 or not type2:
			return 0
		nick1 = model[iter1][C_NICK]
		nick2 = model[iter2][C_NICK]
		if not nick1 or not nick2:
			return 0
		nick1 = nick1.decode('utf-8')
		nick2 = nick2.decode('utf-8')
		if type1 == 'role':
			if nick1 < nick2:
				return -1
			return 1
		if type1 == 'contact':
			gc_contact1 = gajim.contacts.get_gc_contact(self.account,
				self.room_jid, nick1)
			if not gc_contact1:
				return 0
		if type2 == 'contact':
			gc_contact2 = gajim.contacts.get_gc_contact(self.account,
				self.room_jid, nick2)
			if not gc_contact2:
				return 0
		if type1 == 'contact' and type2 == 'contact' and \
		gajim.config.get('sort_by_show_in_muc'):
			cshow = {'chat':0, 'online': 1, 'away': 2, 'xa': 3, 'dnd': 4,
				'invisible': 5, 'offline': 6, 'error': 7}
			show1 = cshow[gc_contact1.show]
			show2 = cshow[gc_contact2.show]
			if show1 < show2:
				return -1
			elif show1 > show2:
				return 1
		# We compare names
		name1 = gc_contact1.get_shown_name()
		name2 = gc_contact2.get_shown_name()
		if name1.lower() < name2.lower():
			return -1
		if name2.lower() < name1.lower():
			return 1
		return 0

	def on_msg_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend Clear
		and the ability to insert a nick'''
		ChatControlBase.on_msg_textview_populate_popup(self, textview, menu)
		item = gtk.SeparatorMenuItem()
		menu.prepend(item)

		item = gtk.MenuItem(_('Insert Nickname'))
		menu.prepend(item)
		submenu = gtk.Menu()
		item.set_submenu(submenu)

		for nick in sorted(gajim.contacts.get_nick_list(self.account,
		self.room_jid)):
			item = gtk.MenuItem(nick, use_underline=False)
			submenu.append(item)
			id_ = item.connect('activate', self.append_nick_in_msg_textview, nick)
			self.handlers[id_] = item

		menu.show_all()

	def on_treeview_size_allocate(self, widget, allocation):
		'''The MUC treeview has resized. Move the hpaned in all tabs to match'''
		hpaned_position = self.hpaned.get_position()
		for account in gajim.gc_connected:
			for room_jid in [i for i in gajim.gc_connected[account] if \
			gajim.gc_connected[account][i]]:
				ctrl = gajim.interface.msg_win_mgr.get_gc_control(room_jid, account)
				if not ctrl:
					ctrl = gajim.interface.minimized_controls[account][room_jid]
				if ctrl:
					ctrl.hpaned.set_position(hpaned_position)

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
		color_name = None
		color = None
		theme = gajim.config.get('roster_theme')
		if chatstate == 'attention' and (not has_focus or not current_tab):
			self.attention_flag = True
			color_name = gajim.config.get_per('themes', theme,
							'state_muc_directed_msg_color')
		elif chatstate:
			if chatstate == 'active' or (current_tab and has_focus):
				self.attention_flag = False
				# get active color from gtk
				color = self.parent_win.notebook.style.fg[gtk.STATE_ACTIVE]
			elif chatstate == 'newmsg' and (not has_focus or not current_tab) and\
					not self.attention_flag:
				color_name = gajim.config.get_per('themes', theme,
					'state_muc_msg_color')
		if color_name:
			color = gtk.gdk.colormap_get_system().alloc_color(color_name)

		if self.is_continued:
			# if this is a continued conversation
			label_str = self.get_continued_conversation_name()
		else:
			label_str = self.name

		# count waiting highlighted messages
		unread = ''
		num_unread = self.get_nb_unread()
		if num_unread == 1:
			unread = '*'
		elif num_unread > 1:
			unread = '[' + unicode(num_unread) + ']'
		label_str = unread + label_str
		return (label_str, color)

	def get_tab_image(self):
		# Set tab image (always 16x16)
		tab_image = None
		if gajim.gc_connected[self.account][self.room_jid]:
			tab_image = gtkgui_helpers.load_icon('muc_active')
		else:
			tab_image = gtkgui_helpers.load_icon('muc_inactive')
		return tab_image

	def update_ui(self):
		ChatControlBase.update_ui(self)
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			self.draw_contact(nick)

	def _change_style(self, model, path, iter_):
		model[iter_][C_NICK] = model[iter_][C_NICK]

	def change_roster_style(self):
		model = self.list_treeview.get_model()
		model.foreach(self._change_style)

	def repaint_themed_widgets(self):
		ChatControlBase.repaint_themed_widgets(self)
		self.change_roster_style()

	def _update_banner_state_image(self):
		banner_status_img = self.xml.get_widget('gc_banner_status_image')
		images = gajim.interface.jabber_state_images
		if self.room_jid in gajim.gc_connected[self.account] and \
		gajim.gc_connected[self.account][self.room_jid]:
			image = 'muc_active'
		else:
			image = 'muc_inactive'
		if '32' in images and image in images['32']:
			muc_icon = images['32'][image]
			if muc_icon.get_storage_type() != gtk.IMAGE_EMPTY:
				pix = muc_icon.get_pixbuf()
				banner_status_img.set_from_pixbuf(pix)
				return
		# we need to scale 16x16 to 32x32
		muc_icon = images['16'][image]
		pix = muc_icon.get_pixbuf()
		scaled_pix = pix.scale_simple(32, 32, gtk.gdk.INTERP_BILINEAR)
		banner_status_img.set_from_pixbuf(scaled_pix)

	def get_continued_conversation_name(self):
		'''Get the name of a continued conversation.
		Will return Continued Conversation if there isn't any other
		contact in the room
		'''
		nicks = []
		for nick in gajim.contacts.get_nick_list(self.account,
		self.room_jid):
			if nick != self.nick:
				nicks.append(nick)
		if nicks != []:
			title = ', '
			title = _('Conversation with ') + title.join(nicks)
		else:
			title = _('Continued conversation')
		return title

	def draw_banner_text(self):
		'''Draw the text in the fat line at the top of the window that
		houses the room jid, subject.
		'''
		self.name_label.set_ellipsize(pango.ELLIPSIZE_END)
		self.banner_status_label.set_ellipsize(pango.ELLIPSIZE_END)
		font_attrs, font_attrs_small = self.get_font_attrs()
		if self.is_continued:
			name = self.get_continued_conversation_name()
		else:
			name = self.room_jid
		text = '<span %s>%s</span>' % (font_attrs, name)
		self.name_label.set_markup(text)

		if self.subject:
			subject = helpers.reduce_chars_newlines(self.subject, max_lines=2)
			subject = gobject.markup_escape_text(subject)
			if gajim.HAVE_PYSEXY:
				subject_text = self.urlfinder.sub(self.make_href, subject)
				subject_text = '<span %s>%s</span>' % (font_attrs_small,
					subject_text)
			else:
				subject_text = '<span %s>%s</span>' % (font_attrs_small, subject)

			# tooltip must always hold ALL the subject
			self.subject_tooltip.set_tip(self.event_box, self.subject)
			self.banner_status_label.show()
			self.banner_status_label.set_no_show_all(False)
		else:
			subject_text = ''
			self.subject_tooltip.disable()
			self.banner_status_label.hide()
			self.banner_status_label.set_no_show_all(True)

		self.banner_status_label.set_markup(subject_text)

	def prepare_context_menu(self, hide_buttonbar_entries=False):
		'''sets sensitivity state for configure_room'''
		xml = gtkgui_helpers.get_glade('gc_control_popup_menu.glade')
		menu = xml.get_widget('gc_control_popup_menu')

		bookmark_room_menuitem = xml.get_widget('bookmark_room_menuitem')
		change_nick_menuitem = xml.get_widget('change_nick_menuitem')
		configure_room_menuitem = xml.get_widget('configure_room_menuitem')
		destroy_room_menuitem = xml.get_widget('destroy_room_menuitem')
		change_subject_menuitem = xml.get_widget('change_subject_menuitem')
		history_menuitem = xml.get_widget('history_menuitem')
		minimize_menuitem = xml.get_widget('minimize_menuitem')
		bookmark_separator = xml.get_widget('bookmark_separator')
		separatormenuitem2 = xml.get_widget('separatormenuitem2')

		if hide_buttonbar_entries:
			change_nick_menuitem.hide()
			change_subject_menuitem.hide()
			bookmark_room_menuitem.hide()
			history_menuitem.hide()
			bookmark_separator.hide()
			separatormenuitem2.hide()
		else:
			change_nick_menuitem.show()
			change_subject_menuitem.show()
			bookmark_room_menuitem.show()
			history_menuitem.show()
			bookmark_separator.show()
			separatormenuitem2.show()
			for bm in gajim.connections[self.account].bookmarks:
				if bm['jid'] == self.room_jid:
					bookmark_room_menuitem.hide()
					bookmark_separator.hide()
					break

		ag = gtk.accel_groups_from_object(self.parent_win.window)[0]
		change_nick_menuitem.add_accelerator('activate', ag, gtk.keysyms.n,
			gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
		change_subject_menuitem.add_accelerator('activate', ag,
			gtk.keysyms.t, gtk.gdk.MOD1_MASK, gtk.ACCEL_VISIBLE)
		bookmark_room_menuitem.add_accelerator('activate', ag, gtk.keysyms.b,
			gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
		history_menuitem.add_accelerator('activate', ag, gtk.keysyms.h,
			gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

		if self.contact.jid in gajim.config.get_per('accounts', self.account,
		'minimized_gc').split(' '):
			minimize_menuitem.set_active(True)
		if not gajim.connections[self.account].private_storage_supported:
			bookmark_room_menuitem.set_sensitive(False)
		if gajim.gc_connected[self.account][self.room_jid]:
			c = gajim.contacts.get_gc_contact(self.account, self.room_jid,
				self.nick)
			if c.affiliation not in ('owner', 'admin'):
				configure_room_menuitem.set_sensitive(False)
			else:
				configure_room_menuitem.set_sensitive(True)
			if c.affiliation != 'owner':
				destroy_room_menuitem.set_sensitive(False)
			else:
				destroy_room_menuitem.set_sensitive(True)
			change_subject_menuitem.set_sensitive(True)
			change_nick_menuitem.set_sensitive(True)
		else:
			# We are not connected to this groupchat, disable unusable menuitems
			configure_room_menuitem.set_sensitive(False)
			destroy_room_menuitem.set_sensitive(False)
			change_subject_menuitem.set_sensitive(False)
			change_nick_menuitem.set_sensitive(False)

		# connect the menuitems to their respective functions
		id_ = bookmark_room_menuitem.connect('activate',
			self._on_bookmark_room_menuitem_activate)
		self.handlers[id_] = bookmark_room_menuitem

		id_ = change_nick_menuitem.connect('activate',
			self._on_change_nick_menuitem_activate)
		self.handlers[id_] = change_nick_menuitem

		id_ = configure_room_menuitem.connect('activate',
			self._on_configure_room_menuitem_activate)
		self.handlers[id_] = configure_room_menuitem

		id_ = destroy_room_menuitem.connect('activate',
			self._on_destroy_room_menuitem_activate)
		self.handlers[id_] = destroy_room_menuitem

		id_ = change_subject_menuitem.connect('activate',
			self._on_change_subject_menuitem_activate)
		self.handlers[id_] = change_subject_menuitem

		id_ = history_menuitem.connect('activate',
			self._on_history_menuitem_activate)
		self.handlers[id_] = history_menuitem

		id_ = minimize_menuitem.connect('toggled',
			self.on_minimize_menuitem_toggled)
		self.handlers[id_] = minimize_menuitem

		menu.connect('selection-done', self.destroy_menu,
         change_nick_menuitem, change_subject_menuitem,
         bookmark_room_menuitem, history_menuitem)
		return menu

	def destroy_menu(self, menu, change_nick_menuitem, change_subject_menuitem,
	bookmark_room_menuitem, history_menuitem):
		# destroy accelerators
		ag = gtk.accel_groups_from_object(self.parent_win.window)[0]
		change_nick_menuitem.remove_accelerator(ag, gtk.keysyms.n,
			gtk.gdk.CONTROL_MASK)
		change_subject_menuitem.remove_accelerator(ag, gtk.keysyms.t,
			gtk.gdk.MOD1_MASK)
		bookmark_room_menuitem.remove_accelerator(ag, gtk.keysyms.b,
			gtk.gdk.CONTROL_MASK)
		history_menuitem.remove_accelerator(ag, gtk.keysyms.h,
			gtk.gdk.CONTROL_MASK)
		# destroy menu
		menu.destroy()

	def on_message(self, nick, msg, tim, has_timestamp=False, xhtml=None,
	status_code=[]):
		if '100' in status_code:
			# Room is not anonymous
			self.is_anonymous = False
		if not nick:
			# message from server
			self.print_conversation(msg, tim=tim, xhtml=xhtml)
		else:
			# message from someone
			if has_timestamp:
				# don't print xhtml if it's an old message.
				# Like that xhtml messages are grayed too.
				self.print_old_conversation(msg, nick, tim, None)
			else:
				self.print_conversation(msg, nick, tim, xhtml)

	def on_private_message(self, nick, msg, tim, xhtml, session,
	msg_id=None, encrypted=False):
		# Do we have a queue?
		fjid = self.room_jid + '/' + nick
		no_queue = len(gajim.events.get_events(self.account, fjid)) == 0

		event = gajim.events.create_event('pm', (msg, '', 'incoming', tim,
			encrypted, '', msg_id, xhtml, session))
		gajim.events.add_event(self.account, fjid, event)

		autopopup = gajim.config.get('autopopup')
		autopopupaway = gajim.config.get('autopopupaway')
		iter_ = self.get_contact_iter(nick)
		path = self.list_treeview.get_model().get_path(iter_)
		if not autopopup or (not autopopupaway and \
		gajim.connections[self.account].connected > 2):
			if no_queue: # We didn't have a queue: we change icons
				model = self.list_treeview.get_model()
				state_images =\
					gajim.interface.roster.get_appropriate_state_images(
						self.room_jid, icon_name='event')
				image = state_images['event']
				model[iter_][C_IMG] = image
			if self.parent_win:
				self.parent_win.show_title()
				self.parent_win.redraw_tab(self)
		else:
			self._start_private_message(nick)
		# Scroll to line
		self.list_treeview.expand_row(path[0:1], False)
		self.list_treeview.scroll_to_cell(path)
		self.list_treeview.set_cursor(path)
		contact = gajim.contacts.get_contact_with_highest_priority(self.account, \
			self.room_jid)
		if contact:
			gajim.interface.roster.draw_contact(self.room_jid, self.account)

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

	def print_old_conversation(self, text, contact='', tim=None,
	xhtml = None):
		if isinstance(text, str):
			text = unicode(text, 'utf-8')
		if contact:
			if contact == self.nick: # it's us
				kind = 'outgoing'
			else:
				kind = 'incoming'
		else:
			kind = 'status'
		if gajim.config.get('restored_messages_small'):
			small_attr = ['small']
		else:
			small_attr = []
		ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
			small_attr, small_attr + ['restored_message'],
			small_attr + ['restored_message'], count_as_new=False, xhtml=xhtml)

	def print_conversation(self, text, contact='', tim=None, xhtml=None,
	graphics=True):
		'''Print a line in the conversation:
		if contact is set: it's a message from someone or an info message (contact
		= 'info' in such a case)
		if contact is not set: it's a message from the server or help'''
		if isinstance(text, str):
			text = unicode(text, 'utf-8')
		other_tags_for_name = []
		other_tags_for_text = []
		if contact:
			if contact == self.nick: # it's us
				kind = 'outgoing'
			elif contact == 'info':
				kind = 'info'
				contact = None
			else:
				kind = 'incoming'
				# muc-specific chatstate
				if self.parent_win:
					self.parent_win.redraw_tab(self, 'newmsg')
		else:
			kind = 'status'

		if kind == 'incoming': # it's a message NOT from us
			# highlighting and sounds
			(highlight, sound) = self.highlighting_for_message(text, tim)
			if contact in self.gc_custom_colors:
				other_tags_for_name.append('gc_nickname_color_' + \
					str(self.gc_custom_colors[contact]))
			else:
				self.gc_count_nicknames_colors += 1
				if self.gc_count_nicknames_colors == self.number_of_colors:
					self.gc_count_nicknames_colors = 0
				self.gc_custom_colors[contact] = \
					self.gc_count_nicknames_colors
				other_tags_for_name.append('gc_nickname_color_' + \
					str(self.gc_count_nicknames_colors))
			if highlight:
				# muc-specific chatstate
				if self.parent_win:
					self.parent_win.redraw_tab(self, 'attention')
				else:
					self.attention_flag = True
				other_tags_for_name.append('bold')
				other_tags_for_text.append('marked')

				if contact in self.attention_list:
					self.attention_list.remove(contact)
				elif len(self.attention_list) > 6:
					self.attention_list.pop(0) # remove older
				self.attention_list.append(contact)

			if sound == 'received':
				helpers.play_sound('muc_message_received')
			elif sound == 'highlight':
				helpers.play_sound('muc_message_highlight')
			if text.startswith('/me ') or text.startswith('/me\n'):
				other_tags_for_text.append('gc_nickname_color_' + \
					str(self.gc_custom_colors[contact]))

			self.check_and_possibly_add_focus_out_line()

		ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
			other_tags_for_name, [], other_tags_for_text, xhtml=xhtml,
			graphics=graphics)

	def get_nb_unread(self):
		type_events = ['printed_marked_gc_msg']
		if gajim.config.get('notify_on_all_muc_messages'):
			type_events.append('printed_gc_msg')
		nb = len(gajim.events.get_events(self.account, self.room_jid,
			type_events))
		nb += self.get_nb_unread_pm()
		return nb

	def get_nb_unread_pm(self):
		nb = 0
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			nb += len(gajim.events.get_events(self.account, self.room_jid + '/' + \
				nick, ['pm']))
		return nb

	def highlighting_for_message(self, text, tim):
		'''Returns a 2-Tuple. The first says whether or not to highlight the
		text, the second, what sound to play.'''
		highlight, sound = (None, None)

		# Are any of the defined highlighting words in the text?
		if self.needs_visual_notification(text):
			highlight = True
			if gajim.config.get_per('soundevents', 'muc_message_highlight',
			'enabled'):
				sound = 'highlight'

		# Do we play a sound on every muc message?
		elif gajim.config.get_per('soundevents', 'muc_message_received', \
		'enabled'):
			sound = 'received'

		# Is it a history message? Don't want sound-floods when we join.
		if tim != time.localtime():
			sound = None

		return (highlight, sound)

	def check_and_possibly_add_focus_out_line(self):
		'''checks and possibly adds focus out line for room_jid if it needs it
		and does not already have it as last event. If it goes to add this line
		it removes previous line first'''

		win = gajim.interface.msg_win_mgr.get_window(self.room_jid, self.account)
		if win and self.room_jid == win.get_active_jid() and\
		win.window.get_property('has-toplevel-focus') and\
		self.parent_win.get_active_control() == self:
			# it's the current room and it's the focused window.
			# we have full focus (we are reading it!)
			return

		self.conv_textview.show_focus_out_line()

	def needs_visual_notification(self, text):
		'''checks text to see whether any of the words in (muc_highlight_words
		and nick) appear.'''

		special_words = gajim.config.get('muc_highlight_words').split(';')
		special_words.append(self.nick)
		# Strip empties: ''.split(';') == [''] and would highlight everything.
		# Also lowercase everything for case insensitive compare.
		special_words = [word.lower() for word in special_words if word]
		text = text.lower()

		for special_word in special_words:
			found_here = text.find(special_word)
			while(found_here > -1):
				end_here = found_here + len(special_word)
				if (found_here == 0 or not text[found_here - 1].isalpha()) and \
				(end_here == len(text) or not text[end_here].isalpha()):
					# It is beginning of text or char before is not alpha AND
					# it is end of text or char after is not alpha
					return True
				# continue searching
				start = found_here + 1
				found_here = text.find(special_word, start)
		return False

	def set_subject(self, subject):
		self.subject = subject
		self.draw_banner_text()

	def got_connected(self):
		# Make autorejoin stop.
		if self.autorejoin:
			gobject.source_remove(self.autorejoin)
		self.autorejoin = None

		gajim.gc_connected[self.account][self.room_jid] = True
		ChatControlBase.got_connected(self)
		# We don't redraw the whole banner here, because only icon change
		self._update_banner_state_image()
		if self.parent_win:
			self.parent_win.redraw_tab(self)

	def got_disconnected(self):
		self.list_treeview.get_model().clear()
		nick_list = gajim.contacts.get_nick_list(self.account, self.room_jid)
		for nick in nick_list:
			# Update pm chat window
			fjid = self.room_jid + '/' + nick
			gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
				nick)

			ctrl = gajim.interface.msg_win_mgr.get_control(fjid, self.account)
			if ctrl:
				gc_contact.show = 'offline'
				gc_contact.status = ''
				ctrl.update_ui()
				if ctrl.parent_win:
					ctrl.parent_win.redraw_tab(ctrl)

			gajim.contacts.remove_gc_contact(self.account, gc_contact)
		gajim.gc_connected[self.account][self.room_jid] = False
		ChatControlBase.got_disconnected(self)
		# Tell connection to note the date we disconnect to avoid duplicate logs
		gajim.connections[self.account].gc_got_disconnected(self.room_jid)
		# We don't redraw the whole banner here, because only icon change
		self._update_banner_state_image()
		if self.parent_win:
			self.parent_win.redraw_tab(self)

		# Autorejoin stuff goes here.
		# Notice that we don't need to activate autorejoin if connection is lost
		# or in progress.
		if self.autorejoin is None and gajim.account_is_connected(self.account):
			ar_to = gajim.config.get('muc_autorejoin_timeout')
			if ar_to:
				self.autorejoin = gobject.timeout_add_seconds(ar_to, self.rejoin)

	def rejoin(self):
		if not self.autorejoin:
			return False
		password = gajim.gc_passwords.get(self.room_jid, '')
		gajim.connections[self.account].join_gc(self.nick, self.room_jid,
			password)
		return True

	def draw_roster(self):
		self.list_treeview.get_model().clear()
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
				nick)
			self.add_contact_to_roster(nick, gc_contact.show, gc_contact.role,
				gc_contact.affiliation, gc_contact.status, gc_contact.jid)
		self.draw_all_roles()
		# Recalculate column width for ellipsizin
		self.list_treeview.columns_autosize()

	def on_send_pm(self, widget=None, model=None, iter_=None, nick=None,
	msg=None):
		'''opens a chat window and if msg is not None sends private message to a
		contact in a room'''
		if nick is None:
			nick = model[iter_][C_NICK].decode('utf-8')

		ctrl = self._start_private_message(nick)
		if ctrl and msg:
			ctrl.send_message(msg)

	def on_send_file(self, widget, gc_contact):
		'''sends a file to a contact in the room'''
		self._on_send_file(gc_contact)

	def draw_contact(self, nick, selected=False, focus=False):
		iter_ = self.get_contact_iter(nick)
		if not iter_:
			return
		model = self.list_treeview.get_model()
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
			nick)
		state_images = gajim.interface.jabber_state_images['16']
		if len(gajim.events.get_events(self.account, self.room_jid + '/' + nick)):
			image = state_images['event']
		else:
			image = state_images[gc_contact.show]

		name = gobject.markup_escape_text(gc_contact.name)

		# Strike name if blocked
		fjid = self.room_jid + '/' + nick
		if helpers.jid_is_blocked(self.account, fjid):
			name = '<span strikethrough="true">%s</span>' % name

		status = gc_contact.status
		# add status msg, if not empty, under contact name in the treeview
		if status and gajim.config.get('show_status_msgs_in_roster'):
			status = status.strip()
			if status != '':
				status = helpers.reduce_chars_newlines(status, max_lines=1)
				# escape markup entities and make them small italic and fg color
				color = gtkgui_helpers._get_fade_color(self.list_treeview,
					selected, focus)
				colorstring = "#%04x%04x%04x" % (color.red, color.green, color.blue)
				name += ('\n<span size="small" style="italic" foreground="%s">'
				         '%s</span>') % (colorstring, gobject.markup_escape_text(status))

		if image.get_storage_type() == gtk.IMAGE_PIXBUF and \
		gc_contact.affiliation != 'none':
			pixbuf1 = image.get_pixbuf().copy()
			pixbuf2 = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 4, 4)
			if gc_contact.affiliation == 'owner':
				pixbuf2.fill(0xff0000ff) # Red
			elif gc_contact.affiliation == 'admin':
				pixbuf2.fill(0xffb200ff) # Oragne
			elif gc_contact.affiliation == 'member':
				pixbuf2.fill(0x00ff00ff) # Green
			pixbuf2.composite(pixbuf1, 12, 12, pixbuf2.get_property('width'),
				pixbuf2.get_property('height'), 0, 0, 1.0, 1.0,
				gtk.gdk.INTERP_HYPER, 127)
			image = gtk.image_new_from_pixbuf(pixbuf1)
		model[iter_][C_IMG] = image
		model[iter_][C_TEXT] = name

	def draw_avatar(self, nick):
		if not gajim.config.get('show_avatars_in_roster'):
			return
		model = self.list_treeview.get_model()
		iter_ = self.get_contact_iter(nick)
		if not iter_:
			return
		pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(self.room_jid + \
			'/' + nick, True)
		if pixbuf in ('ask', None):
			scaled_pixbuf = None
		else:
			scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'roster')
		model[iter_][C_AVATAR] = scaled_pixbuf

	def draw_role(self, role):
		role_iter = self.get_role_iter(role)
		if not role_iter:
			return
		model = self.list_treeview.get_model()
		role_name = helpers.get_uf_role(role, plural=True)
		if gajim.config.get('show_contacts_number'):
			nbr_role, nbr_total = gajim.contacts.get_nb_role_total_gc_contacts(
				self.account, self.room_jid, role)
			role_name += ' (%s/%s)' % (repr(nbr_role), repr(nbr_total))
		model[role_iter][C_TEXT] = role_name

	def draw_all_roles(self):
		for role in ('visitor', 'participant', 'moderator'):
			self.draw_role(role)

	def chg_contact_status(self, nick, show, status, role, affiliation, jid,
	reason, actor, statusCode, new_nick, avatar_sha, tim=None):
		'''When an occupant changes his or her status'''
		if show == 'invisible':
			return

		if not role:
			role = 'visitor'
		if not affiliation:
			affiliation = 'none'
		fake_jid = self.room_jid + '/' + nick
		newly_created = False
		nick_jid = nick

		# Set to true if role or affiliation have changed
		right_changed = False

		if jid:
			# delete ressource
			simple_jid = gajim.get_jid_without_resource(jid)
			nick_jid += ' (%s)' % simple_jid

		# statusCode
		# http://www.xmpp.org/extensions/xep-0045.html#registrar-statuscodes-init
		if statusCode:
			if '100' in statusCode:
				# Can be a message (see handle_event_gc_config_change in gajim.py)
				self.print_conversation(\
					_('Any occupant is allowed to see your full JID'))
			if '170' in statusCode:
				# Can be a message (see handle_event_gc_config_change in gajim.py)
				self.print_conversation(_('Room logging is enabled'))
			if '201' in statusCode:
				self.print_conversation(_('A new room has been created'))
			if '210' in statusCode:
				self.print_conversation(\
					_('The server has assigned or modified your roomnick'))

		if show in ('offline', 'error'):
			if statusCode:
				if '307' in statusCode:
					if actor is None: # do not print 'kicked by None'
						s = _('%(nick)s has been kicked: %(reason)s') % {
							'nick': nick,
							'reason': reason }
					else:
						s = _('%(nick)s has been kicked by %(who)s: %(reason)s') % {
							'nick': nick,
							'who': actor,
							'reason': reason }
					self.print_conversation(s, 'info', tim=tim, graphics=False)
					if nick == self.nick and not gajim.config.get(
					'muc_autorejoin_on_kick'):
						self.autorejoin = False
				elif '301' in statusCode:
					if actor is None: # do not print 'banned by None'
						s = _('%(nick)s has been banned: %(reason)s') % {
							'nick': nick,
							'reason': reason }
					else:
						s = _('%(nick)s has been banned by %(who)s: %(reason)s') % {
							'nick': nick,
							'who': actor,
							'reason': reason }
					self.print_conversation(s, 'info', tim=tim, graphics=False)
					if nick == self.nick:
						self.autorejoin = False
				elif '303' in statusCode: # Someone changed his or her nick
					if new_nick == self.new_nick or nick == self.nick:
						# We changed our nick
						self.nick = new_nick
						self.new_nick = ''
						s = _('You are now known as %s') % new_nick
						# Stop all E2E sessions
						nick_list = gajim.contacts.get_nick_list(self.account,
							self.room_jid)
						for nick_ in nick_list:
							fjid_ = self.room_jid + '/' + nick_
							ctrl = gajim.interface.msg_win_mgr.get_control(fjid_,
								self.account)
							if ctrl and ctrl.session and \
							ctrl.session.enable_encryption:
								thread_id = ctrl.session.thread_id
								ctrl.session.terminate_e2e()
								gajim.connections[self.account].delete_session(fjid_,
									thread_id)
								ctrl.no_autonegotiation = False
					else:
						s = _('%(nick)s is now known as %(new_nick)s') % {
							'nick': nick, 'new_nick': new_nick}
					# We add new nick to muc roster here, so we don't see
					# that "new_nick has joined the room" when he just changed nick.
					# add_contact_to_roster will be called a second time
					# after that, but that doesn't hurt
					self.add_contact_to_roster(new_nick, show, role, affiliation,
						status, jid)
					if nick in self.attention_list:
						self.attention_list.remove(nick)
					# keep nickname color
					if nick in self.gc_custom_colors:
						self.gc_custom_colors[new_nick] = \
							self.gc_custom_colors[nick]
					# rename vcard / avatar
					puny_jid = helpers.sanitize_filename(self.room_jid)
					puny_nick = helpers.sanitize_filename(nick)
					puny_new_nick = helpers.sanitize_filename(new_nick)
					old_path = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
					new_path = os.path.join(gajim.VCARD_PATH, puny_jid,
						puny_new_nick)
					files = {old_path: new_path}
					path = os.path.join(gajim.AVATAR_PATH, puny_jid)
					# possible extensions
					for ext in ('.png', '.jpeg', '_notif_size_bw.png',
					'_notif_size_colored.png'):
						files[os.path.join(path, puny_nick + ext)] = \
							os.path.join(path, puny_new_nick + ext)
					for old_file in files:
						if os.path.exists(old_file) and old_file != files[old_file]:
							if os.path.exists(files[old_file]) and helpers.windowsify(
							old_file) != helpers.windowsify(files[old_file]):
								# Windows require this, but os.remove('test') will also
								# remove 'TEST'
								os.remove(files[old_file])
							os.rename(old_file, files[old_file])
					self.print_conversation(s, 'info', tim=tim, graphics=False)
				elif '321' in statusCode:
					s = _('%(nick)s has been removed from the room (%(reason)s)') % {
						'nick': nick, 'reason': _('affiliation changed') }
					self.print_conversation(s, 'info', tim=tim, graphics=False)
				elif '322' in statusCode:
					s = _('%(nick)s has been removed from the room (%(reason)s)') % {
						'nick': nick,
						'reason': _('room configuration changed to members-only') }
					self.print_conversation(s, 'info', tim=tim, graphics=False)
				elif '332' in statusCode:
					s = _('%(nick)s has been removed from the room (%(reason)s)') % {
						'nick': nick,
						'reason': _('system shutdown') }
					self.print_conversation(s, 'info', tim=tim, graphics=False)
				elif 'destroyed' in statusCode: # Room has been destroyed
					self.print_conversation(reason, 'info', tim, graphics=False)

			if len(gajim.events.get_events(self.account, jid=fake_jid,
			types=['pm'])) == 0:
				self.remove_contact(nick)
				self.draw_all_roles()
			else:
				c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
				c.show = show
				c.status = status
			if nick == self.nick and (not statusCode or \
			'303' not in statusCode): # We became offline
				self.got_disconnected()
				contact = gajim.contacts.\
					get_contact_with_highest_priority(self.account, self.room_jid)
				if contact:
					gajim.interface.roster.draw_contact(self.room_jid, self.account)
				if self.parent_win:
					self.parent_win.redraw_tab(self)
		else:
			iter_ = self.get_contact_iter(nick)
			if not iter_:
				if '210' in statusCode:
					# Server changed our nick
					self.nick = nick
					s = _('You are now known as %s') % nick
					self.print_conversation(s, 'info', tim=tim, graphics=False)
				iter_ = self.add_contact_to_roster(nick, show, role, affiliation,
					status, jid)
				newly_created = True
				self.draw_all_roles()
				if statusCode and '201' in statusCode: # We just created the room
					gajim.connections[self.account].request_gc_config(self.room_jid)
			else:
				gc_c = gajim.contacts.get_gc_contact(self.account, self.room_jid,
					nick)
				if not gc_c:
					log.error('%s has an iter, but no gc_contact instance')
					return
				# Re-get vcard if avatar has changed
				# We do that here because we may request it to the real JID if we
				# knows it. connections.py doesn't know it.
				con = gajim.connections[self.account]
				if gc_c and gc_c.jid:
					real_jid = gc_c.jid
					if gc_c.resource:
						real_jid += '/' + gc_c.resource
				else:
					real_jid = fake_jid
				if fake_jid in con.vcard_shas:
					if avatar_sha != con.vcard_shas[fake_jid]:
						server = gajim.get_server_from_jid(self.room_jid)
						if not server.startswith('irc'):
							con.request_vcard(real_jid, fake_jid)
				else:
					cached_vcard = con.get_cached_vcard(fake_jid, True)
					if cached_vcard and 'PHOTO' in cached_vcard and \
					'SHA' in cached_vcard['PHOTO']:
						cached_sha = cached_vcard['PHOTO']['SHA']
					else:
						cached_sha = ''
					if cached_sha != avatar_sha:
						# avatar has been updated
						# sha in mem will be updated later
						server = gajim.get_server_from_jid(self.room_jid)
						if not server.startswith('irc'):
							con.request_vcard(real_jid, fake_jid)
					else:
						# save sha in mem NOW
						con.vcard_shas[fake_jid] = avatar_sha

				actual_affiliation = gc_c.affiliation
				if affiliation != actual_affiliation:
					if actor:
						st = _('** Affiliation of %(nick)s has been set to '
							'%(affiliation)s by %(actor)s') % {'nick': nick_jid,
							'affiliation': affiliation, 'actor': actor}
					else:
						st = _('** Affiliation of %(nick)s has been set to '
							'%(affiliation)s') % {'nick': nick_jid,
							'affiliation': affiliation}
					if reason:
						st += ' (%s)' % reason
					self.print_conversation(st, tim=tim, graphics=False)
					right_changed = True
				actual_role = self.get_role(nick)
				if role != actual_role:
					self.remove_contact(nick)
					self.add_contact_to_roster(nick, show, role,
						affiliation, status, jid)
					self.draw_role(actual_role)
					self.draw_role(role)
					if actor:
						st = _('** Role of %(nick)s has been set to %(role)s by '
							'%(actor)s') % {'nick': nick_jid, 'role': role,
							'actor': actor}
					else:
						st = _('** Role of %(nick)s has been set to %(role)s') % {
							'nick': nick_jid, 'role': role}
					if reason:
						st += ' (%s)' % reason
					self.print_conversation(st, tim=tim, graphics=False)
					right_changed = True
				else:
					if gc_c.show == show and gc_c.status == status and \
						gc_c.affiliation == affiliation: # no change
						return
					gc_c.show = show
					gc_c.affiliation = affiliation
					gc_c.status = status
					self.draw_contact(nick)
		if (time.time() - self.room_creation) > 30 and nick != self.nick and \
		(not statusCode or '303' not in statusCode) and not right_changed:
			st = ''
			print_status = None
			for bookmark in gajim.connections[self.account].bookmarks:
				if bookmark['jid'] == self.room_jid:
					print_status = bookmark.get('print_status', None)
					break
			if not print_status:
				print_status = gajim.config.get('print_status_in_muc')
			if show == 'offline':
				if nick in self.attention_list:
					self.attention_list.remove(nick)
			if show == 'offline' and print_status in ('all', 'in_and_out') and \
			(not statusCode or '307' not in statusCode):
				st = _('%s has left') % nick_jid
				if reason:
					st += ' [%s]' % reason
			else:
				if newly_created and print_status in ('all', 'in_and_out'):
					st = _('%s has joined the group chat') % nick_jid
				elif print_status == 'all':
					st = _('%(nick)s is now %(status)s') % {'nick': nick_jid,
						'status': helpers.get_uf_show(show)}
			if st:
				if status:
					st += ' (' + status + ')'
				self.print_conversation(st, tim=tim, graphics=False)

	def add_contact_to_roster(self, nick, show, role, affiliation, status,
	jid=''):
		model = self.list_treeview.get_model()
		role_name = helpers.get_uf_role(role, plural=True)

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
				(gajim.interface.jabber_state_images['16']['closed'], role,
				'role', role_name,  None))
			self.draw_all_roles()
		iter_ = model.append(role_iter, (None, nick, 'contact', name, None))
		if not nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			gc_contact = gajim.contacts.create_gc_contact(room_jid=self.room_jid,
				name=nick, show=show, status=status, role=role,
				affiliation=affiliation, jid=j, resource=resource)
			gajim.contacts.add_gc_contact(self.account, gc_contact)
		self.draw_contact(nick)
		self.draw_avatar(nick)
		# Do not ask avatar to irc rooms as irc transports reply with messages
		server = gajim.get_server_from_jid(self.room_jid)
		if gajim.config.get('ask_avatars_on_startup') and \
		not server.startswith('irc'):
			fake_jid = self.room_jid + '/' + nick
			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(fake_jid, True)
			if pixbuf == 'ask':
				if j:
					fjid = j
					if resource:
						fjid += '/' + resource
					gajim.connections[self.account].request_vcard(fjid, fake_jid)
				else:
					gajim.connections[self.account].request_vcard(fake_jid, fake_jid)
		if nick == self.nick: # we became online
			self.got_connected()
		self.list_treeview.expand_row((model.get_path(role_iter)), False)
		if self.is_continued:
			self.draw_banner_text()
		return iter_

	def get_role_iter(self, role):
		model = self.list_treeview.get_model()
		fin = False
		iter_ = model.get_iter_root()
		if not iter_:
			return None
		while not fin:
			role_name = model[iter_][C_NICK].decode('utf-8')
			if role == role_name:
				return iter_
			iter_ = model.iter_next(iter_)
			if not iter_:
				fin = True
		return None

	def remove_contact(self, nick):
		'''Remove a user from the contacts_list'''
		model = self.list_treeview.get_model()
		iter_ = self.get_contact_iter(nick)
		if not iter_:
			return
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
			nick)
		if gc_contact:
			gajim.contacts.remove_gc_contact(self.account, gc_contact)
		parent_iter = model.iter_parent(iter_)
		model.remove(iter_)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)

	def send_message(self, message, xhtml=None, process_commands=True):
		'''call this function to send our message'''
		if not message:
			return

		if process_commands and self.process_as_command(message):
			return

		message = helpers.remove_invalid_xml_chars(message)

		if not message:
			return

		if message != '' or message != '\n':
			self.save_sent_message(message)
         
			# Send the message
			gajim.connections[self.account].send_gc_message(self.room_jid, 
				message, xhtml=xhtml)
			self.msg_textview.get_buffer().set_text('')
			self.msg_textview.grab_focus()

	def get_role(self, nick):
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
			nick)
		if gc_contact:
			return gc_contact.role
		else:
			return 'visitor'

	def minimizable(self):
		if self.contact.jid in gajim.config.get_per('accounts', self.account,
		'minimized_gc').split(' '):
			return True
		return False

	def minimize(self, status='offline'):
		# Minimize it
		win = gajim.interface.msg_win_mgr.get_window(self.contact.jid,
			self.account)
		ctrl = win.get_control(self.contact.jid, self.account)

		ctrl_page = win.notebook.page_num(ctrl.widget)
		control = win.notebook.get_nth_page(ctrl_page)

		win.notebook.remove_page(ctrl_page)
		control.unparent()
		ctrl.parent_win = None

		gajim.interface.roster.add_groupchat(self.contact.jid, self.account,
			status = self.subject)

		del win._controls[self.account][self.contact.jid]

	def shutdown(self, status='offline'):
		# destroy banner tooltip - bug #pygtk for that!
		self.subject_tooltip.destroy()

		# Preventing autorejoin from being activated
		self.autorejoin = False

		if self.room_jid in gajim.gc_connected[self.account] and \
		gajim.gc_connected[self.account][self.room_jid]:
			# Tell connection to note the date we disconnect to avoid duplicate
			# logs. We do it only when connected because if connection was lost
			# there may be new messages since disconnection.
			gajim.connections[self.account].gc_got_disconnected(self.room_jid)
		gajim.connections[self.account].send_gc_status(self.nick, self.room_jid,
							show='offline', status=status)
		nick_list = gajim.contacts.get_nick_list(self.account, self.room_jid)
		for nick in nick_list:
			# Update pm chat window
			fjid = self.room_jid + '/' + nick
			ctrl = gajim.interface.msg_win_mgr.get_gc_control(fjid, self.account)
			if ctrl:
				contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
					nick)
				contact.show = 'offline'
				contact.status = ''
				ctrl.update_ui()
				ctrl.parent_win.redraw_tab(ctrl)
			for sess in gajim.connections[self.account].get_sessions(fjid):
				if sess.control:
					sess.control.no_autonegotiation = False
				if sess.enable_encryption:
					sess.terminate_e2e()
					gajim.connections[self.account].delete_session(fjid,
						sess.thread_id)
		# They can already be removed by the destroy function
		if self.room_jid in gajim.contacts.get_gc_list(self.account):
			gajim.contacts.remove_room(self.account, self.room_jid)
			del gajim.gc_connected[self.account][self.room_jid]
		# Save hpaned position
		gajim.config.set('gc-hpaned-position', self.hpaned.get_position())
		# remove all register handlers on wigets, created by self.xml
		# to prevent circular references among objects
		for i in self.handlers.keys():
			if self.handlers[i].handler_is_connected(i):
				self.handlers[i].disconnect(i)
			del self.handlers[i]
		# Remove unread events from systray
		gajim.events.remove_events(self.account, self.room_jid)

	def safe_shutdown(self):
		if self.minimizable():
			return True
		includes = gajim.config.get('confirm_close_muc_rooms').split(' ')
		excludes = gajim.config.get('noconfirm_close_muc_rooms').split(' ')
		# whether to ask for comfirmation before closing muc
		if (gajim.config.get('confirm_close_muc') or self.room_jid in includes) \
		and gajim.gc_connected[self.account][self.room_jid] and self.room_jid not\
		in excludes:
			return False
		return True

	def allow_shutdown(self, method, on_yes, on_no, on_minimize):
		if self.minimizable():
			on_minimize(self)
			return
		if method == self.parent_win.CLOSE_ESC:
			iter_ = self.list_treeview.get_selection().get_selected()[1]
			if iter_:
				self.list_treeview.get_selection().unselect_all()
				on_no(self)
				return
		includes = gajim.config.get('confirm_close_muc_rooms').split(' ')
		excludes = gajim.config.get('noconfirm_close_muc_rooms').split(' ')
		# whether to ask for comfirmation before closing muc
		if (gajim.config.get('confirm_close_muc') or self.room_jid in includes) \
		and gajim.gc_connected[self.account][self.room_jid] and self.room_jid not\
		in excludes:

			def on_ok(clicked):
				if clicked:
					# user does not want to be asked again
					gajim.config.set('confirm_close_muc', False)
				on_yes(self)

			def on_cancel(clicked):
				if clicked:
					# user does not want to be asked again
					gajim.config.set('confirm_close_muc', False)
				on_no(self)

			pritext = _('Are you sure you want to leave group chat "%s"?')\
				% self.name
			sectext = _('If you close this window, you will be disconnected '
					'from this group chat.')

			dialogs.ConfirmationDialogCheck(pritext, sectext,
				_('Do _not ask me again'), on_response_ok=on_ok,
				on_response_cancel=on_cancel)
			return

		on_yes(self)

	def set_control_active(self, state):
		self.conv_textview.allow_focus_out_line = True
		self.attention_flag = False
		ChatControlBase.set_control_active(self, state)
		if not state:
			# add the focus-out line to the tab we are leaving
			self.check_and_possibly_add_focus_out_line()
		# Sending active to undo unread state
		self.parent_win.redraw_tab(self, 'active')

	def get_specific_unread(self):
		# returns the number of the number of unread msgs
		# for room_jid & number of unread private msgs with each contact
		# that we have
		nb = 0
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			fjid = self.room_jid + '/' + nick
			nb += len(gajim.events.get_events(self.account, fjid))
			# gc can only have messages as event
		return nb

	def _on_change_subject_menuitem_activate(self, widget):
		def on_ok(subject):
			# Note, we don't update self.subject since we don't know whether it
			# will work yet
			gajim.connections[self.account].send_gc_subject(self.room_jid, subject)

		dialogs.InputTextDialog(_('Changing Subject'),
			_('Please specify the new subject:'), input_str=self.subject,
			ok_handler=on_ok)

	def _on_change_nick_menuitem_activate(self, widget):
		if 'change_nick_dialog' in gajim.interface.instances:
			gajim.interface.instances['change_nick_dialog'].present()
		else:
			title = _('Changing Nickname')
			prompt = _('Please specify the new nickname you want to use:')
			gajim.interface.instances['change_nick_dialog'] = \
				dialogs.ChangeNickDialog(self.account, self.room_jid, title,
				prompt)

	def _on_configure_room_menuitem_activate(self, widget):
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, self.nick)
		if c.affiliation == 'owner':
			gajim.connections[self.account].request_gc_config(self.room_jid)
		elif c.affiliation == 'admin':
			if self.room_jid not in gajim.interface.instances[self.account][
			'gc_config']:
				gajim.interface.instances[self.account]['gc_config'][self.room_jid]\
					= config.GroupchatConfigWindow(self.account, self.room_jid)

	def _on_destroy_room_menuitem_activate(self, widget):
		def on_ok(reason, jid):
			if jid:
				# Test jid
				try:
					jid = helpers.parse_jid(jid)
				except Exception:
					dialogs.ErrorDialog(_('Invalid group chat Jabber ID'),
					_('The group chat Jabber ID has not allowed characters.'))
					return
			gajim.connections[self.account].destroy_gc_room(self.room_jid, reason,
				jid)

		# Ask for a reason
		dialogs.DubbleInputDialog(_('Destroying %s') % self.room_jid,
			_('You are going to definitively destroy this room.\n'
			'You may specify a reason below:'),
			_('You may also enter an alternate venue:'), ok_handler=on_ok)

	def _on_bookmark_room_menuitem_activate(self, widget):
		'''bookmark the room, without autojoin and not minimized'''
		password = gajim.gc_passwords.get(self.room_jid, '')
		gajim.interface.add_gc_bookmark(self.account, self.name, self.room_jid, \
			'0', '0', password, self.nick)

	def _on_drag_data_received(self, widget, context, x, y, selection,
			target_type, timestamp):
		# Invite contact to groupchat
		treeview = gajim.interface.roster.tree
		model = treeview.get_model()
		if not selection.data or target_type == 80:
			#  target_type = 80 means a file is dropped
			return
		data = selection.data
		path = treeview.get_selection().get_selected_rows()[1][0]
		iter_ = model.get_iter(path)
		type_ = model[iter_][2]
		if type_ != 'contact': # source is not a contact
			return
		contact_jid = data.decode('utf-8')
		gajim.connections[self.account].send_invite(self.room_jid, contact_jid)

	def handle_message_textview_mykey_press(self, widget, event_keyval,
		event_keymod):
		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_room(). for this singal see message_textview.py

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		message_buffer = widget.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()

		if event.keyval == gtk.keysyms.Tab: # TAB
			cursor_position = message_buffer.get_insert()
			end_iter = message_buffer.get_iter_at_mark(cursor_position)
			text = message_buffer.get_text(start_iter, end_iter, False).decode(
				'utf-8')

			splitted_text = text.split()

			# HACK: Not the best soltution.
			if (text.startswith(self.COMMAND_PREFIX) and not
				text.startswith(self.COMMAND_PREFIX * 2) and len(splitted_text) == 1):
				return super(GroupchatControl,
					self).handle_message_textview_mykey_press(widget, event_keyval,
							event_keymod)

			# nick completion
			# check if tab is pressed with empty message
			if len(splitted_text): # if there are any words
				begin = splitted_text[-1] # last word we typed
			else:
				begin = ''

			gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')
			with_refer_to_nick_char = False

			# first part of this if : works fine even if refer_to_nick_char
			if gc_refer_to_nick_char and begin.endswith(gc_refer_to_nick_char):
				with_refer_to_nick_char = True
			if len(self.nick_hits) and self.last_key_tabs and \
			(text[:-1].endswith(self.nick_hits[0]) or \
			text[:-2].endswith(self.nick_hits[0])): # we should cycle
				# Previous nick in list may had a space inside, so we check text and
				# not splitted_text and store it into 'begin' var
				self.nick_hits.append(self.nick_hits[0])
				begin = self.nick_hits.pop(0)
			else:
				self.nick_hits = [] # clear the hit list
				list_nick = gajim.contacts.get_nick_list(self.account,
									self.room_jid)
				list_nick.sort(key=unicode.lower) # case-insensitive sort
				if begin == '':
					# empty message, show lasts nicks that highlighted us first
					for nick in self.attention_list:
						if nick in list_nick:
							list_nick.remove(nick)
						list_nick.insert(0, nick)

				list_nick.remove(self.nick) # Skip self
				for nick in list_nick:
					if nick.lower().startswith(begin.lower()):
						# the word is the begining of a nick
						self.nick_hits.append(nick)
			if len(self.nick_hits):
				if len(splitted_text) < 2 or with_refer_to_nick_char:
				# This is the 1st word of the line or no word or we are cycling
				# at the beginning, possibly with a space in one nick
					add = gc_refer_to_nick_char + ' '
				else:
					add = ' '
				start_iter = end_iter.copy()
				if self.last_key_tabs and with_refer_to_nick_char:
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
			selection = widget.get_selection()
			iter_ = selection.get_selected()[1]
			if iter_:
				widget.get_selection().unselect_all()
				return True

	def on_list_treeview_row_expanded(self, widget, iter_, path):
		'''When a row is expanded: change the icon of the arrow'''
		model = widget.get_model()
		image = gajim.interface.jabber_state_images['16']['opened']
		model[iter_][C_IMG] = image

	def on_list_treeview_row_collapsed(self, widget, iter_, path):
		'''When a row is collapsed: change the icon of the arrow'''
		model = widget.get_model()
		image = gajim.interface.jabber_state_images['16']['closed']
		model[iter_][C_IMG] = image

	def kick(self, widget, nick):
		'''kick a user'''
		def on_ok(reason):
			gajim.connections[self.account].gc_set_role(self.room_jid, nick,
				'none', reason)

		# ask for reason
		dialogs.InputDialog(_('Kicking %s') % nick,
					_('You may specify a reason below:'), ok_handler=on_ok)

	def mk_menu(self, event, iter_):
		'''Make contact's popup menu'''
		model = self.list_treeview.get_model()
		nick = model[iter_][C_NICK].decode('utf-8')
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		fjid = self.room_jid + '/' + nick
		jid = c.jid
		target_affiliation = c.affiliation
		target_role = c.role

		# looking for user's affiliation and role
		user_nick = self.nick
		user_affiliation = gajim.contacts.get_gc_contact(self.account,
			self.room_jid, user_nick).affiliation
		user_role = self.get_role(user_nick)

		# making menu from glade
		xml = gtkgui_helpers.get_glade('gc_occupants_menu.glade')

		# these conditions were taken from JEP 0045
		item = xml.get_widget('kick_menuitem')
		if user_role != 'moderator' or \
		(user_affiliation == 'admin' and target_affiliation == 'owner') or \
		(user_affiliation == 'member' and target_affiliation in ('admin',
		'owner')) or (user_affiliation == 'none' and target_affiliation != \
		'none'):
			item.set_sensitive(False)
		id_ = item.connect('activate', self.kick, nick)
		self.handlers[id_] = item

		item = xml.get_widget('voice_checkmenuitem')
		item.set_active(target_role != 'visitor')
		if user_role != 'moderator' or \
		user_affiliation == 'none' or \
		(user_affiliation=='member' and target_affiliation!='none') or \
		target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		id_ = item.connect('activate', self.on_voice_checkmenuitem_activate,
			nick)
		self.handlers[id_] = item

		item = xml.get_widget('moderator_checkmenuitem')
		item.set_active(target_role == 'moderator')
		if not user_affiliation in ('admin', 'owner') or \
		target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		id_ = item.connect('activate', self.on_moderator_checkmenuitem_activate,
					nick)
		self.handlers[id_] = item

		item = xml.get_widget('ban_menuitem')
		if not user_affiliation in ('admin', 'owner') or \
		(target_affiliation in ('admin', 'owner') and\
		user_affiliation != 'owner'):
			item.set_sensitive(False)
		id_ = item.connect('activate', self.ban, jid)
		self.handlers[id_] = item

		item = xml.get_widget('member_checkmenuitem')
		item.set_active(target_affiliation != 'none')
		if not user_affiliation in ('admin', 'owner') or \
		(user_affiliation != 'owner' and target_affiliation in ('admin','owner')):
			item.set_sensitive(False)
		id_ = item.connect('activate', self.on_member_checkmenuitem_activate, jid)
		self.handlers[id_] = item

		item = xml.get_widget('admin_checkmenuitem')
		item.set_active(target_affiliation in ('admin', 'owner'))
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		id_ = item.connect('activate', self.on_admin_checkmenuitem_activate, jid)
		self.handlers[id_] = item

		item = xml.get_widget('owner_checkmenuitem')
		item.set_active(target_affiliation == 'owner')
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		id_ = item.connect('activate', self.on_owner_checkmenuitem_activate, jid)
		self.handlers[id_] = item

		item = xml.get_widget('information_menuitem')
		id_ = item.connect('activate', self.on_info, nick)
		self.handlers[id_] = item

		item = xml.get_widget('history_menuitem')
		id_ = item.connect('activate', self.on_history, nick)
		self.handlers[id_] = item

		item = xml.get_widget('add_to_roster_menuitem')
		our_jid = gajim.get_jid_from_account(self.account)
		if not jid or jid == our_jid:
			item.set_sensitive(False)
		else:
			id_ = item.connect('activate', self.on_add_to_roster, jid)
			self.handlers[id_] = item

		item = xml.get_widget('block_menuitem')
		item2 = xml.get_widget('unblock_menuitem')
		if helpers.jid_is_blocked(self.account, fjid):
			item.set_no_show_all(True)
			item.hide()
			id_ = item2.connect('activate', self.on_unblock, nick)
			self.handlers[id_] = item2
		else:
			id_ = item.connect('activate', self.on_block, nick)
			self.handlers[id_] = item
			item2.set_no_show_all(True)
			item2.hide()

		item = xml.get_widget('send_private_message_menuitem')
		id_ = item.connect('activate', self.on_send_pm, model, iter_)
		self.handlers[id_] = item

		item = xml.get_widget('send_file_menuitem')
		# add a special img for send file menuitem
		path_to_upload_img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'upload.png')
		img = gtk.Image()
		img.set_from_file(path_to_upload_img)
		item.set_image(img)

		if not c.resource:
			item.set_sensitive(False)
		else:
			id_ = item.connect('activate', self.on_send_file, c)
			self.handlers[id_] = item

		# show the popup now!
		menu = xml.get_widget('gc_occupants_menu')
		menu.show_all()
		menu.popup(None, None, None, event.button, event.time)

	def _start_private_message(self, nick):
		gc_c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		nick_jid = gc_c.get_full_jid()

		ctrl = gajim.interface.msg_win_mgr.get_control(nick_jid, self.account)
		if not ctrl:
			ctrl = gajim.interface.new_private_chat(gc_c, self.account)

		if ctrl:
			ctrl.parent_win.set_active_tab(ctrl)

		return ctrl

	def on_row_activated(self, widget, path):
		'''When an iter is activated (dubblick or single click if gnome is set
		this way'''
		model = widget.get_model()
		if len(path) == 1: # It's a group
			if (widget.row_expanded(path)):
				widget.collapse_row(path)
			else:
				widget.expand_row(path, False)
		else: # We want to send a private message
			nick = model[path][C_NICK].decode('utf-8')
			self._start_private_message(nick)

	def on_list_treeview_row_activated(self, widget, path, col=0):
		'''When an iter is double clicked: open the chat window'''
		if not gajim.single_click:
			self.on_row_activated(widget, path)

	def on_list_treeview_button_press_event(self, widget, event):
		'''popup user's group's or agent menu'''
		# hide tooltip, no matter the button is pressed
		self.tooltip.hide_tooltip()
		try:
			pos = widget.get_path_at_pos(int(event.x), int(event.y))
			path, x = pos[0], pos[2]
		except TypeError:
			widget.get_selection().unselect_all()
			return
		if event.button == 3: # right click
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter_ = model.get_iter(path)
			if len(path) == 2:
				self.mk_menu(event, iter_)
			return True

		elif event.button == 2: # middle click
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter_ = model.get_iter(path)
			if len(path) == 2:
				nick = model[iter_][C_NICK].decode('utf-8')
				self._start_private_message(nick)
			return True

		elif event.button == 1: # left click
			if gajim.single_click and not event.state & gtk.gdk.SHIFT_MASK:
				self.on_row_activated(widget, path)
				return True
			else:
				model = widget.get_model()
				iter_ = model.get_iter(path)
				nick = model[iter_][C_NICK].decode('utf-8')
				if not nick in gajim.contacts.get_nick_list(self.account,
				self.room_jid):
					# it's a group
					if x < 27:
						if (widget.row_expanded(path)):
							widget.collapse_row(path)
						else:
							widget.expand_row(path, False)
				elif event.state & gtk.gdk.SHIFT_MASK:
					self.append_nick_in_msg_textview(self.msg_textview, nick)
					self.msg_textview.grab_focus()
					return True

	def append_nick_in_msg_textview(self, widget, nick):
		message_buffer = self.msg_textview.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		cursor_position = message_buffer.get_insert()
		end_iter = message_buffer.get_iter_at_mark(cursor_position)
		text = message_buffer.get_text(start_iter, end_iter, False)
		start = ''
		if text: # Cursor is not at first position
			if not text[-1] in (' ', '\n', '\t'):
				start = ' '
			add = ' '
		else:
			gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')
			add = gc_refer_to_nick_char + ' '
		message_buffer.insert_at_cursor(start + nick + add)

	def on_list_treeview_motion_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id != props[0]:
				self.tooltip.hide_tooltip()
		if props:
			[row, col, x, y] = props
			iter_ = None
			try:
				iter_ = model.get_iter(row)
			except Exception:
				self.tooltip.hide_tooltip()
				return
			typ = model[iter_][C_TYPE].decode('utf-8')
			if typ == 'contact':
				account = self.account

				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					nick = model[iter_][C_NICK].decode('utf-8')
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, gajim.contacts.get_gc_contact(account,
						self.room_jid, nick))

	def on_list_treeview_leave_notify_event(self, widget, event):
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id == props[0]:
				self.tooltip.hide_tooltip()

	def show_tooltip(self, contact):
		if not self.list_treeview.window:
			# control has been destroyed since tooltip was requested
			return
		pointer = self.list_treeview.get_pointer()
		props = self.list_treeview.get_path_at_pos(pointer[0], pointer[1])
		# check if the current pointer is at the same path
		# as it was before setting the timeout
		if props and self.tooltip.id == props[0]:
			rect = self.list_treeview.get_cell_area(props[0],props[1])
			position = self.list_treeview.window.get_origin()
			self.tooltip.show_tooltip(contact, rect.height,
											position[1] + rect.y)
		else:
			self.tooltip.hide_tooltip()

	def grant_voice(self, widget, nick):
		'''grant voice privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'participant')

	def revoke_voice(self, widget, nick):
		'''revoke voice privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'visitor')

	def grant_moderator(self, widget, nick):
		'''grant moderator privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'moderator')

	def revoke_moderator(self, widget, nick):
		'''revoke moderator privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'participant')

	def ban(self, widget, jid):
		'''ban a user'''
		def on_ok(reason):
			gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
				'outcast', reason)

		# to ban we know the real jid. so jid is not fakejid
		nick = gajim.get_nick_from_jid(jid)
		# ask for reason
		dialogs.InputDialog(_('Banning %s') % nick,
			_('You may specify a reason below:'), ok_handler=on_ok)

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
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'admin')

	def revoke_admin(self, widget, jid):
		'''revoke administrative privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'member')

	def grant_owner(self, widget, jid):
		'''grant owner privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'owner')

	def revoke_owner(self, widget, jid):
		'''revoke owner privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'admin')

	def on_info(self, widget, nick):
		'''Call vcard_information_window class to display user's information'''
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		c2 = gajim.contacts.contact_from_gc_contact(c)
		if c2.jid in gajim.interface.instances[self.account]['infos']:
			gajim.interface.instances[self.account]['infos'][c2.jid].window.\
				present()
		else:
			gajim.interface.instances[self.account]['infos'][c2.jid] = \
				vcard.VcardWindow(c2, self.account, c)

	def on_history(self, widget, nick):
		jid = gajim.construct_fjid(self.room_jid, nick)
		self._on_history_menuitem_activate(widget=widget, jid=jid)

	def on_add_to_roster(self, widget, jid):
		dialogs.AddNewContactWindow(self.account, jid)

	def on_block(self, widget, nick):
		fjid = self.room_jid + '/' + nick
		connection = gajim.connections[self.account]
		if fjid in connection.blocked_contacts:
			return
		new_rule = {'order': u'1', 'type': u'jid', 'action': u'deny',
			'value' : fjid, 'child': [u'message', u'iq', u'presence-out']}
		connection.blocked_list.append(new_rule)
		connection.blocked_contacts.append(fjid)
		self.draw_contact(nick)
		connection.set_privacy_list('block', connection.blocked_list)
		if len(connection.blocked_list) == 1:
			connection.set_active_list('block')
			connection.set_default_list('block')
		connection.get_privacy_list('block')

	def on_unblock(self, widget, nick):
		fjid = self.room_jid + '/' + nick
		connection = gajim.connections[self.account]
		connection.new_blocked_list = []
		# needed for draw_contact:
		if fjid in connection.blocked_contacts:
			connection.blocked_contacts.remove(fjid)
		self.draw_contact(nick)
		for rule in connection.blocked_list:
			if rule['action'] != 'deny' or rule['type'] != 'jid' \
			or rule['value'] != fjid:
				connection.new_blocked_list.append(rule)

		connection.set_privacy_list('block', connection.new_blocked_list)
		connection.get_privacy_list('block')
		if len(connection.new_blocked_list) == 0:
			connection.blocked_list = []
			connection.blocked_contacts = []
			connection.blocked_groups = []
			connection.set_default_list('')
			connection.set_active_list('')
			connection.del_privacy_list('block')
			if 'blocked_contacts' in gajim.interface.instances[self.account]:
				gajim.interface.instances[self.account]['blocked_contacts'].\
					privacy_list_received([])

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

# vim: se ts=3:
