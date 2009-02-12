# -*- coding: utf-8 -*-
## src/dialogs.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2005-2008 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import gtk
import gobject
import os

import gtkgui_helpers
import vcard
import conversation_textview
import message_control
import dataforms_widget

from random import randrange
from common import pep

try:
	import gtkspell
	HAS_GTK_SPELL = True
except ImportError:
	HAS_GTK_SPELL = False

# those imports are not used in this file, but in files that 'import dialogs'
# so they can do dialog.GajimThemesWindow() for example
from filetransfers_window import FileTransfersWindow
from gajim_themes_window import GajimThemesWindow
from advanced import AdvancedConfigurationWindow

from common import gajim
from common import helpers
from common import dataforms
from common.exceptions import GajimGeneralException

class EditGroupsDialog:
	'''Class for the edit group dialog window'''
	def __init__(self, list_):
		'''list_ is a list of (contact, account) tuples'''
		self.xml = gtkgui_helpers.get_glade('edit_groups_dialog.glade')
		self.dialog = self.xml.get_widget('edit_groups_dialog')
		self.dialog.set_transient_for(gajim.interface.roster.window)
		self.list_ = list_
		self.changes_made = False
		self.treeview = self.xml.get_widget('groups_treeview')
		if len(list_) == 1:
			contact = list_[0][0]
			self.xml.get_widget('nickname_label').set_markup(
				_('Contact name: <i>%s</i>') % contact.get_shown_name())
			self.xml.get_widget('jid_label').set_markup(
				_('Jabber ID: <i>%s</i>') % contact.jid)
		else:
			self.xml.get_widget('nickname_label').set_no_show_all(True)
			self.xml.get_widget('nickname_label').hide()
			self.xml.get_widget('jid_label').set_no_show_all(True)
			self.xml.get_widget('jid_label').hide()

		self.xml.signal_autoconnect(self)
		self.init_list()

		self.dialog.show_all()
		if self.changes_made:
			for (contact, account) in self.list_:
				gajim.connections[account].update_contact(contact.jid, contact.name,
					contact.groups)

	def on_edit_groups_dialog_response(self, widget, response_id):
		if response_id == gtk.RESPONSE_CLOSE:
			self.dialog.destroy()

	def remove_group(self, group):
		'''remove group group from all contacts and all their brothers'''
		for (contact, account) in self.list_:
			gajim.interface.roster.remove_contact_from_groups(contact.jid, account, [group])

		# FIXME: Ugly workaround.
		gajim.interface.roster.draw_group(_('General'), account)

	def add_group(self, group):
		'''add group group to all contacts and all their brothers'''
		for (contact, account) in self.list_:
			gajim.interface.roster.add_contact_to_groups(contact.jid, account, [group])

		# FIXME: Ugly workaround. Maybe we haven't been in any group (defaults to General)
		gajim.interface.roster.draw_group(_('General'), account)

	def on_add_button_clicked(self, widget):
		group = self.xml.get_widget('group_entry').get_text().decode('utf-8')
		if not group:
			return
		# Do not allow special groups
		if group in helpers.special_groups:
			return
		# check if it already exists
		model = self.treeview.get_model()
		iter_ = model.get_iter_root()
		while iter_:
			if model.get_value(iter_, 0).decode('utf-8') == group:
				return
			iter_ = model.iter_next(iter_)
		self.changes_made = True
		model.append((group, True, False))
		self.add_group(group)
		self.init_list() # Re-draw list to sort new item

	def group_toggled_cb(self, cell, path):
		self.changes_made = True
		model = self.treeview.get_model()
		if model[path][2]:
			model[path][2] = False
			model[path][1] = True
		else:
			model[path][1] = not model[path][1]
		group = model[path][0].decode('utf-8')
		if model[path][1]:
			self.add_group(group)
		else:
			self.remove_group(group)

	def init_list(self):
		store = gtk.ListStore(str, bool, bool)
		self.treeview.set_model(store)
		for column in self.treeview.get_columns():
			# Clear treeview when re-drawing
			self.treeview.remove_column(column)
		accounts = []
		# Store groups in a list so we can sort them and the number of contacts in
		# it
		groups = {}
		for (contact, account) in self.list_:
			if account not in accounts:
				accounts.append(account)
				for g in gajim.groups[account].keys():
					if g in groups:
						continue
					groups[g] = 0
			c_groups = contact.groups
			for g in c_groups:
				groups[g] += 1
		group_list = []
		# Remove special groups if they are empty
		for group in groups:
			if group not in helpers.special_groups or groups[group] > 0:
				group_list.append(group)
		group_list.sort()
		for group in group_list:
			iter_ = store.append()
			store.set(iter_, 0, group) # Group name
			if groups[group] == 0:
				store.set(iter_, 1, False)
			else:
				store.set(iter_, 1, True)
				if groups[group] == len(self.list_):
					# all contacts are in this group
					store.set(iter_, 2, False)
				else:
					store.set(iter_, 2, True)
		column = gtk.TreeViewColumn(_('Group'))
		column.set_expand(True)
		self.treeview.append_column(column)
		renderer = gtk.CellRendererText()
		column.pack_start(renderer)
		column.set_attributes(renderer, text=0)

		column = gtk.TreeViewColumn(_('In the group'))
		column.set_expand(False)
		self.treeview.append_column(column)
		renderer = gtk.CellRendererToggle()
		column.pack_start(renderer)
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.group_toggled_cb)
		column.set_attributes(renderer, active=1, inconsistent=2)

class PassphraseDialog:
	'''Class for Passphrase dialog'''
	def __init__(self, titletext, labeltext, checkbuttontext=None,
	ok_handler=None, cancel_handler=None):
		self.xml = gtkgui_helpers.get_glade('passphrase_dialog.glade')
		self.window = self.xml.get_widget('passphrase_dialog')
		self.passphrase_entry = self.xml.get_widget('passphrase_entry')
		self.passphrase = -1
		self.window.set_title(titletext)
		self.xml.get_widget('message_label').set_text(labeltext)

		self.ok = False

		self.cancel_handler = cancel_handler
		self.ok_handler = ok_handler
		okbutton = self.xml.get_widget('ok_button')
		okbutton.connect('clicked', self.on_okbutton_clicked)
		cancelbutton = self.xml.get_widget('cancel_button')
		cancelbutton.connect('clicked', self.on_cancelbutton_clicked)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

		self.check = bool(checkbuttontext)
		checkbutton =	self.xml.get_widget('save_passphrase_checkbutton')
		if self.check:
			checkbutton.set_label(checkbuttontext)
		else:
			checkbutton.hide()

	def on_okbutton_clicked(self, widget):
		if not self.ok_handler:
			return

		passph = self.passphrase_entry.get_text().decode('utf-8')

		if self.check:
			checked = self.xml.get_widget('save_passphrase_checkbutton').\
				get_active()
		else:
			checked = False

		self.ok = True

		self.window.destroy()

		if isinstance(self.ok_handler, tuple):
			self.ok_handler[0](passph, checked, *self.ok_handler[1:])
		else:
			self.ok_handler(passph, checked)

	def on_cancelbutton_clicked(self, widget):
		self.window.destroy()

	def on_passphrase_dialog_destroy(self, widget):
		if self.cancel_handler and not self.ok:
			self.cancel_handler()

class ChooseGPGKeyDialog:
	'''Class for GPG key dialog'''
	def __init__(self, title_text, prompt_text, secret_keys, on_response,
	selected=None):
		'''secret_keys : {keyID: userName, ...}'''
		self.on_response = on_response
		xml = gtkgui_helpers.get_glade('choose_gpg_key_dialog.glade')
		self.window = xml.get_widget('choose_gpg_key_dialog')
		self.window.set_title(title_text)
		self.keys_treeview = xml.get_widget('keys_treeview')
		prompt_label = xml.get_widget('prompt_label')
		prompt_label.set_text(prompt_text)
		model = gtk.ListStore(str, str)
		model.set_sort_func(1, self.sort_keys)
		model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.keys_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		col = self.keys_treeview.insert_column_with_attributes(-1, _('KeyID'),
			renderer, text = 0)
		col.set_sort_column_id(0)
		renderer = gtk.CellRendererText()
		col = self.keys_treeview.insert_column_with_attributes(-1,
			_('Contact name'), renderer, text=1)
		col.set_sort_column_id(1)
		self.keys_treeview.set_search_column(1)
		self.fill_tree(secret_keys, selected)
		self.window.connect('response', self.on_dialog_response)
		self.window.show_all()

	def sort_keys(self, model, iter1, iter2):
		value1 = model[iter1][1]
		value2 = model[iter2][1]
		if value1 == _('None'):
			return -1
		elif value2 == _('None'):
			return 1
		elif value1 < value2:
			return -1
		return 1

	def on_dialog_response(self, dialog, response):
		selection = self.keys_treeview.get_selection()
		(model, iter_) = selection.get_selected()
		if iter_ and response == gtk.RESPONSE_OK:
			keyID = [ model[iter_][0].decode('utf-8'),
				model[iter_][1].decode('utf-8') ]
		else:
			keyID = None
		self.on_response(keyID)
		self.window.destroy()

	def fill_tree(self, list_, selected):
		model = self.keys_treeview.get_model()
		for keyID in list_.keys():
			iter_ = model.append((keyID, list_[keyID]))
			if keyID == selected:
				path = model.get_path(iter_)
				self.keys_treeview.set_cursor(path)


class ChangeActivityDialog:
	PAGELIST = ['doing_chores', 'drinking', 'eating', 'exercising', 'grooming',
		'having_appointment', 'inactive', 'relaxing', 'talking', 'traveling',
		'working']

	def __init__(self, account):
		self.account = account
		self.xml = gtkgui_helpers.get_glade(
			'change_activity_dialog.glade')
		self.window = self.xml.get_widget('change_activity_dialog')
		self.window.set_transient_for(gajim.interface.roster.window)

		self.checkbutton = self.xml.get_widget('enable_checkbutton')
		self.notebook = self.xml.get_widget('notebook')
		self.entry = self.xml.get_widget('description_entry')

		self.activity = 'working'
		self.subactivity = 'other'

		rbtns = {}
		group = None

		for category in pep.ACTIVITIES:
			item = self.xml.get_widget(category + '_image')
			item.set_from_pixbuf(
				gtkgui_helpers.load_activity_icon(category).get_pixbuf())
			gtk.Tooltips().set_tip(item, pep.ACTIVITIES[category]['category'])

			vbox = self.xml.get_widget(category + '_vbox')
			vbox.set_border_width(5)

			# Other
			act = category + '_other'

			if group:
				rbtns[act] = gtk.RadioButton(group)
			else:
				rbtns[act] = group = gtk.RadioButton()

			hbox = gtk.HBox(False, 5)
			hbox.pack_start(gtkgui_helpers.load_activity_icon(category),
				False, False, 0)
			lbl = gtk.Label('<b>' + pep.ACTIVITIES[category]['category'] + '</b>')
			lbl.set_use_markup(True)
			hbox.pack_start(lbl, False, False, 0)
			rbtns[act].add(hbox)
			rbtns[act].connect('toggled', self.on_rbtn_toggled,
				[category, 'other'])
			vbox.pack_start(rbtns[act], False, False, 0)

			activities = []
			for activity in pep.ACTIVITIES[category]:
				activities.append(activity)
			activities.sort()

			for activity in activities:
				if activity == 'category':
					continue

				act = category + '_' + activity

				if group:
					rbtns[act] = gtk.RadioButton(group)
				else:
					rbtns[act] = group = gtk.RadioButton()

				hbox = gtk.HBox(False, 5)
				hbox.pack_start(gtkgui_helpers.load_activity_icon(category,
					activity), False, False, 0)
				hbox.pack_start(gtk.Label(pep.ACTIVITIES[category][activity]),
					False, False, 0)
				rbtns[act].connect('toggled', self.on_rbtn_toggled,
					[category, activity])
				rbtns[act].add(hbox)
				vbox.pack_start(rbtns[act], False, False, 0)

		rbtns['working_other'].set_active(True)

		con = gajim.connections[account]

		if 'activity' in con.activity \
		and con.activity['activity'] in pep.ACTIVITIES:
			if 'subactivity' in con.activity \
			and con.activity['subactivity'] in pep.ACTIVITIES[con.activity['activity']]:
				subactivity = con.activity['subactivity']
			else:
				subactivity = 'other'

			rbtns[con.activity['activity'] + '_' + subactivity]. \
				set_active(True)

			self.checkbutton.set_active(True)
			self.notebook.set_sensitive(True)
			self.entry.set_sensitive(True)

			self.notebook.set_current_page(
				self.PAGELIST.index(con.activity['activity']))

		if 'text' in con.activity:
			self.entry.set_text(con.activity['text'])

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_enable_checkbutton_toggled(self, widget):
		self.notebook.set_sensitive(widget.get_active())
		self.entry.set_sensitive(widget.get_active())

	def on_rbtn_toggled(self, widget, data):
		if widget.get_active():
			self.activity = data[0]
			self.subactivity = data[1]

	def on_ok_button_clicked(self, widget):
		'''
		Return activity and messsage (None if no activity selected)
		'''
		if self.checkbutton.get_active():
			pep.user_send_activity(self.account, self.activity,
				self.subactivity,
				self.entry.get_text().decode('utf-8'))
		else:
			pep.user_send_activity(self.account, '')
		self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

class ChangeMoodDialog:
	COLS = 11

	def __init__(self, account):
		self.account = account
		self.xml = gtkgui_helpers.get_glade('change_mood_dialog.glade')
		self.mood = None

		self.window = self.xml.get_widget('change_mood_dialog')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.window.set_title(_('Set Mood'))

		table = self.xml.get_widget('mood_icons_table')
		self.label = self.xml.get_widget('mood_label')
		self.entry = self.xml.get_widget('description_entry')

		no_mood_button = self.xml.get_widget('no_mood_button')
		no_mood_button.set_mode(False)
		no_mood_button.connect('clicked',
			self.on_mood_button_clicked, None)

		x = 1
		y = 0
		self.mood_buttons = {}

		# Order them first
		self.MOODS = []
		for mood in pep.MOODS:
			self.MOODS.append(mood)
		self.MOODS.sort()

		for mood in self.MOODS:
			self.mood_buttons[mood] = gtk.RadioButton(no_mood_button)
			self.mood_buttons[mood].set_mode(False)
			self.mood_buttons[mood].add(gtkgui_helpers.load_mood_icon(mood))
			self.mood_buttons[mood].set_relief(gtk.RELIEF_NONE)
			gtk.Tooltips().set_tip(self.mood_buttons[mood], pep.MOODS[mood])
			self.mood_buttons[mood].connect('clicked',
				self.on_mood_button_clicked, mood)
			table.attach(self.mood_buttons[mood], x, x + 1, y, y + 1)

			# Calculate the next position
			x += 1
			if x >= self.COLS:
				x = 0
				y += 1

		con = gajim.connections[account]
		if 'mood' in con.mood:
			self.mood = con.mood['mood']
			if self.mood in pep.MOODS:
				self.mood_buttons[self.mood].set_active(True)
				self.label.set_text(pep.MOODS[self.mood])
			else:
				self.label.set_text(self.mood)

		if self.mood:
			self.entry.set_sensitive(True)
		else:
			self.entry.set_sensitive(False)

		if 'text' in con.mood:
			self.entry.set_text(con.mood['text'])

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_mood_button_clicked(self, widget, data):
		if data:
			self.label.set_text(pep.MOODS[data])
			self.entry.set_sensitive(True)
		else:
			self.label.set_text(_('None'))
			self.entry.set_text('')
			self.entry.set_sensitive(False)
		self.mood = data

	def on_ok_button_clicked(self, widget):
		'''Return mood and messsage (None if no mood selected)'''
		message = self.entry.get_text().decode('utf-8')
		if self.mood is None:
			pep.user_send_mood(self.account, '')
		else:
			pep.user_send_mood(self.account, self.mood, message)
		self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

class ChangeStatusMessageDialog:
	def __init__(self, on_response, show=None):
		self.show = show
		self.on_response = on_response
		self.xml = gtkgui_helpers.get_glade('change_status_message_dialog.glade')
		self.window = self.xml.get_widget('change_status_message_dialog')
		self.window.set_transient_for(gajim.interface.roster.window)
		if show:
			uf_show = helpers.get_uf_show(show)
			self.title_text = _('%s Status Message') % uf_show
		else:
			self.title_text = _('Status Message')
		self.window.set_title(self.title_text)

		message_textview = self.xml.get_widget('message_textview')
		self.message_buffer = message_textview.get_buffer()
		self.message_buffer.connect('changed',
			self.toggle_sensitiviy_of_save_as_preset)
		msg = None
		if show:
			msg = gajim.config.get('last_status_msg_' + show)
		if not msg:
			msg = ''
		msg = helpers.from_one_line(msg)
		self.message_buffer.set_text(msg)

		# have an empty string selectable, so user can clear msg
		self.preset_messages_dict = {'': ''}
		for msg_name in gajim.config.get_per('statusmsg'):
			msg_text = gajim.config.get_per('statusmsg', msg_name, 'message')
			msg_text = helpers.from_one_line(msg_text)
			self.preset_messages_dict[msg_name] = msg_text
		sorted_keys_list = helpers.get_sorted_keys(self.preset_messages_dict)

		self.countdown_time = gajim.config.get('change_status_window_timeout')
		self.countdown_left = self.countdown_time
		self.countdown_enabled = True

		self.message_liststore = gtk.ListStore(str) # msg_name
		self.message_combobox = self.xml.get_widget('message_combobox')
		self.message_combobox.set_model(self.message_liststore)
		cellrenderertext = gtk.CellRendererText()
		self.message_combobox.pack_start(cellrenderertext, True)
		self.message_combobox.add_attribute(cellrenderertext, 'text', 0)
		for msg_name in sorted_keys_list:
			self.message_liststore.append((msg_name,))
		self.xml.signal_autoconnect(self)
		if self.countdown_time > 0:
			self.countdown()
			gobject.timeout_add(1000, self.countdown)
		self.window.connect('response', self.on_dialog_response)
		self.window.show_all()

	def countdown(self):
		if self.countdown_enabled:
			if self.countdown_left <= 0:
				# Prevent GUI freeze when the combobox menu is opened on close
				self.message_combobox.popdown()
				self.window.response(gtk.RESPONSE_OK)
				return False
			self.window.set_title('%s [%s]' % (self.title_text,
				str(self.countdown_left)))
			self.countdown_left -= 1
			return True
		else:
			self.window.set_title(self.title_text)
			return False

	def on_dialog_response(self, dialog, response):
		if response == gtk.RESPONSE_OK:
			beg, end = self.message_buffer.get_bounds()
			message = self.message_buffer.get_text(beg, end).decode('utf-8')\
				.strip()
			message = helpers.remove_invalid_xml_chars(message)
			msg = helpers.to_one_line(message)
			if self.show:
				gajim.config.set('last_status_msg_' + self.show, msg)
		else:
			message = None # user pressed Cancel button or X wm button
		self.window.destroy()
		self.on_response(message)

	def on_message_combobox_changed(self, widget):
		self.countdown_enabled = False
		model = widget.get_model()
		active = widget.get_active()
		if active < 0:
			return None
		name = model[active][0].decode('utf-8')
		self.message_buffer.set_text(self.preset_messages_dict[name])

	def on_change_status_message_dialog_key_press_event(self, widget, event):
		self.countdown_enabled = False
		if event.keyval == gtk.keysyms.Return or \
		event.keyval == gtk.keysyms.KP_Enter: # catch CTRL+ENTER
			if (event.state & gtk.gdk.CONTROL_MASK):
				self.window.response(gtk.RESPONSE_OK)
				# Stop the event
				return True

	def toggle_sensitiviy_of_save_as_preset(self, widget):
		btn = self.xml.get_widget('save_as_preset_button')
		if self.message_buffer.get_char_count() == 0:
			btn.set_sensitive(False)
		else:
			btn.set_sensitive(True)

	def on_save_as_preset_button_clicked(self, widget):
		self.countdown_enabled = False
		start_iter, finish_iter = self.message_buffer.get_bounds()
		status_message_to_save_as_preset = self.message_buffer.get_text(
			start_iter, finish_iter)
		def on_ok(msg_name):
			msg_text = status_message_to_save_as_preset.decode('utf-8')
			msg_text_1l = helpers.to_one_line(msg_text)
			if not msg_name: # msg_name was ''
				msg_name = msg_text_1l.decode('utf-8')

			if msg_name in self.preset_messages_dict:
				def on_ok2():
					self.preset_messages_dict[msg_name] = msg_text
					gajim.config.set_per('statusmsg', msg_name, 'message',
						msg_text_1l)
				ConfirmationDialog(_('Overwrite Status Message?'),
					_('This name is already used. Do you want to overwrite this '
					'status message?'), on_response_ok=on_ok2)
				return
			self.preset_messages_dict[msg_name] = msg_text
			iter_ = self.message_liststore.append((msg_name,))
			gajim.config.add_per('statusmsg', msg_name)
			# select in combobox the one we just saved
			self.message_combobox.set_active_iter(iter_)
			gajim.config.set_per('statusmsg', msg_name, 'message', msg_text_1l)
		InputDialog(_('Save as Preset Status Message'),
			_('Please type a name for this status message'), is_modal=False,
			ok_handler=on_ok)

class AddNewContactWindow:
	'''Class for AddNewContactWindow'''
	uid_labels = {'jabber': _('Jabber ID:'),
		'aim': _('AIM Address:'),
		'gadu-gadu': _('GG Number:'),
		'icq': _('ICQ Number:'),
		'msn': _('MSN Address:'),
		'yahoo': _('Yahoo! Address:')}
	def __init__(self, account=None, jid=None, user_nick=None, group=None):
		self.account = account
		if account is None:
			# fill accounts with active accounts
			accounts = []
			for account in gajim.connections.keys():
				if gajim.connections[account].connected > 1:
					accounts.append(account)
			if not accounts:
				return
			if len(accounts) == 1:
				self.account = account
		else:
			accounts = [self.account]
		if self.account:
			location = gajim.interface.instances[self.account]
		else:
			location = gajim.interface.instances
		if 'add_contact' in location:
			location['add_contact'].window.present()
			# An instance is already opened
			return
		location['add_contact'] = self
		self.xml = gtkgui_helpers.get_glade('add_new_contact_window.glade')
		self.xml.signal_autoconnect(self)
		self.window = self.xml.get_widget('add_new_contact_window')
		for w in ('account_combobox', 'account_hbox', 'account_label',
		'uid_label', 'uid_entry', 'protocol_combobox', 'protocol_jid_combobox',
		'protocol_hbox', 'nickname_entry', 'message_scrolledwindow',
		'register_hbox', 'subscription_table', 'add_button',
		'message_textview', 'connected_label', 'group_comboboxentry',
		'auto_authorize_checkbutton'):
			self.__dict__[w] = self.xml.get_widget(w)
		if account and len(gajim.connections) >= 2:
			prompt_text =\
_('Please fill in the data of the contact you want to add in account %s') %account
		else:
			prompt_text = _('Please fill in the data of the contact you want to add')
		self.xml.get_widget('prompt_label').set_text(prompt_text)
		self.agents = {'jabber': []}
		# types to which we are not subscribed but account has an agent for it
		self.available_types = []
		for acct in accounts:
			for j in gajim.contacts.get_jid_list(acct):
				if gajim.jid_is_transport(j):
					type_ = gajim.get_transport_name_from_jid(j, False)
					if not type_:
						continue
					if type_ in self.agents:
						self.agents[type_].append(j)
					else:
						self.agents[type_] = [j]
		# Now add the one to which we can register
		for acct in accounts:
			for type_ in gajim.connections[acct].available_transports:
				if type_ in self.agents:
					continue
				self.agents[type_] = []
				for jid_ in gajim.connections[acct].available_transports[type_]:
					if not jid_ in self.agents[type_]:
						self.agents[type_].append(jid_)
				self.available_types.append(type_)
		liststore = gtk.ListStore(str)
		self.group_comboboxentry.set_model(liststore)
		# Combobox with transport/jabber icons
		liststore = gtk.ListStore(str, gtk.gdk.Pixbuf, str)
		cell = gtk.CellRendererPixbuf()
		self.protocol_combobox.pack_start(cell, False)
		self.protocol_combobox.add_attribute(cell, 'pixbuf', 1)
		cell = gtk.CellRendererText()
		cell.set_property('xpad', 5)
		self.protocol_combobox.pack_start(cell, True)
		self.protocol_combobox.add_attribute(cell, 'text', 0)
		self.protocol_combobox.set_model(liststore)
		uf_type = {'jabber': 'Jabber', 'aim': 'AIM', 'gadu-gadu': 'Gadu Gadu',
			'icq': 'ICQ', 'msn': 'MSN', 'yahoo': 'Yahoo'}
		# Jabber as first
		img = gajim.interface.jabber_state_images['16']['online']
		liststore.append(['Jabber', img.get_pixbuf(), 'jabber'])
		for type_ in self.agents:
			if type_ == 'jabber':
				continue
			imgs = gajim.interface.roster.transports_state_images
			img = None
			if type_ in imgs['16'] and 'online' in imgs['16'][type_]:
				img = imgs['16'][type_]['online']
				if type_ in uf_type:
					liststore.append([uf_type[type_], img.get_pixbuf(), type_])
				else:
					liststore.append([type_, img.get_pixbuf(), type_])
			else:
				liststore.append([type_, img, type_])
		self.protocol_combobox.set_active(0)
		self.auto_authorize_checkbutton.show()
		liststore = gtk.ListStore(str)
		self.protocol_jid_combobox.set_model(liststore)
		if jid:
			type_ = gajim.get_transport_name_from_jid(jid)
			if not type_:
				type_ = 'jabber'
			if type_ == 'jabber':
				self.uid_entry.set_text(jid)
			else:
				uid, transport = gajim.get_name_and_server_from_jid(jid)
				self.uid_entry.set_text(uid.replace('%', '@', 1))
			#set protocol_combobox
			model = self.protocol_combobox.get_model()
			iter_ = model.get_iter_first()
			i = 0
			while iter_:
				if model[iter_][2] == type_:
					self.protocol_combobox.set_active(i)
					break
				iter_ = model.iter_next(iter_)
				i += 1

			# set protocol_jid_combobox
			self.protocol_jid_combobox.set_active(0)
			model = self.protocol_jid_combobox.get_model()
			iter_ = model.get_iter_first()
			i = 0
			while iter_:
				if model[iter_][0] == transport:
					self.protocol_jid_combobox.set_active(i)
					break
				iter_ = model.iter_next(iter_)
				i += 1
			if user_nick:
				self.nickname_entry.set_text(user_nick)
			self.nickname_entry.grab_focus()
		else:
			self.uid_entry.grab_focus()
		group_names = []
		for acct in accounts:
			for g in gajim.groups[acct].keys():
				if g not in helpers.special_groups and g not in group_names:
					group_names.append(g)
		group_names.sort()
		i = 0
		for g in group_names:
			self.group_comboboxentry.append_text(g)
			if group == g:
				self.group_comboboxentry.set_active(i)
			i += 1

		self.window.show_all()

		if self.account:
			self.account_label.hide()
			self.account_hbox.hide()
		else:
			liststore = gtk.ListStore(str, str)
			for acct in accounts:
				liststore.append([acct, acct])
			self.account_combobox.set_model(liststore)
			self.account_combobox.set_active(0)

	def on_add_new_contact_window_destroy(self, widget):
		if self.account:
			location = gajim.interface.instances[self.account]
		else:
			location = gajim.interface.instances
		del location['add_contact']

	def on_register_button_clicked(self, widget):
		jid = self.protocol_jid_combobox.get_active_text().decode('utf-8')
		gajim.connections[self.account].request_register_agent_info(jid)

	def on_add_new_contact_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		'''When Cancel button is clicked'''
		self.window.destroy()

	def on_add_button_clicked(self, widget):
		'''When Subscribe button is clicked'''
		jid = self.uid_entry.get_text().decode('utf-8')
		if not jid:
			return

		model = self.protocol_combobox.get_model()
		iter_ = self.protocol_combobox.get_active_iter()
		type_ = model[iter_][2]
		if type_ != 'jabber':
			transport = self.protocol_jid_combobox.get_active_text().decode(
				'utf-8')
			jid = jid.replace('@', '%') + '@' + transport

		# check if jid is conform to RFC and stringprep it
		try:
			jid = helpers.parse_jid(jid)
		except helpers.InvalidFormat, s:
			pritext = _('Invalid User ID')
			ErrorDialog(pritext, str(s))
			return

		# No resource in jid
		if jid.find('/') >= 0:
			pritext = _('Invalid User ID')
			ErrorDialog(pritext, _('The user ID must not contain a resource.'))
			return

		if jid == gajim.get_jid_from_account(self.account):
			pritext = _('Invalid User ID')
			ErrorDialog(pritext, _('You cannot add yourself to your roster.'))
			return

		nickname = self.nickname_entry.get_text().decode('utf-8') or ''
		# get value of account combobox, if account was not specified
		if not self.account:
			model = self.account_combobox.get_model()
			index = self.account_combobox.get_active()
			self.account = model[index][1]

		# Check if jid is already in roster
		if jid in gajim.contacts.get_jid_list(self.account):
			c = gajim.contacts.get_first_contact_from_jid(self.account, jid)
			if _('Not in Roster') not in c.groups and c.sub in ('both', 'to'):
				ErrorDialog(_('Contact already in roster'),
				_('This contact is already listed in your roster.'))
				return

		if type_ == 'jabber':
			message_buffer = self.message_textview.get_buffer()
			start_iter = message_buffer.get_start_iter()
			end_iter = message_buffer.get_end_iter()
			message = message_buffer.get_text(start_iter, end_iter).decode('utf-8')
		else:
			message= ''
		group = self.group_comboboxentry.child.get_text().decode('utf-8')
		groups = []
		if group:
			groups = [group]
		auto_auth = self.auto_authorize_checkbutton.get_active()
		gajim.interface.roster.req_sub(self, jid, message, self.account,
			groups = groups, nickname = nickname, auto_auth = auto_auth)
		self.window.destroy()

	def on_protocol_combobox_changed(self, widget):
		model = widget.get_model()
		iter_ = widget.get_active_iter()
		type_ = model[iter_][2]
		model = self.protocol_jid_combobox.get_model()
		model.clear()
		if len(self.agents[type_]):
			for jid_ in self.agents[type_]:
				model.append([jid_])
			self.protocol_jid_combobox.set_active(0)
		if len(self.agents[type_]) > 1:
			self.protocol_jid_combobox.show()
		else:
			self.protocol_jid_combobox.hide()
		if type_ in self.uid_labels:
			self.uid_label.set_text(self.uid_labels[type_])
		else:
			self.uid_label.set_text(_('User ID:'))
		if type_ == 'jabber':
			self.message_scrolledwindow.show()
		else:
			self.message_scrolledwindow.hide()
		if type_ in self.available_types:
			self.register_hbox.show()
			self.auto_authorize_checkbutton.hide()
			self.connected_label.hide()
			self.subscription_table.hide()
			self.add_button.set_sensitive(False)
		else:
			self.register_hbox.hide()
			if type_ != 'jabber':
				jid = self.protocol_jid_combobox.get_active_text()
				contact = gajim.contacts.get_first_contact_from_jid(self.account,
					jid)
				if contact.show in ('offline', 'error'):
					self.subscription_table.hide()
					self.connected_label.show()
					self.add_button.set_sensitive(False)
					self.auto_authorize_checkbutton.hide()
					return
			self.subscription_table.show()
			self.auto_authorize_checkbutton.show()
			self.connected_label.hide()
			self.add_button.set_sensitive(True)

	def transport_signed_in(self, jid):
		if self.protocol_jid_combobox.get_active_text() == jid:
			self.register_hbox.hide()
			self.connected_label.hide()
			self.subscription_table.show()
			self.auto_authorize_checkbutton.show()
			self.add_button.set_sensitive(True)

	def transport_signed_out(self, jid):
		if self.protocol_jid_combobox.get_active_text() == jid:
			self.subscription_table.hide()
			self.auto_authorize_checkbutton.hide()
			self.connected_label.show()
			self.add_button.set_sensitive(False)

class AboutDialog:
	'''Class for about dialog'''
	def __init__(self):
		dlg = gtk.AboutDialog()
		dlg.set_transient_for(gajim.interface.roster.window)
		dlg.set_name('Gajim')
		dlg.set_version(gajim.version)
		s = u'Copyright © 2003-2008 Gajim Team'
		dlg.set_copyright(s)
		copying_file_path = self.get_path('COPYING')
		if copying_file_path:
			text = open(copying_file_path).read()
			dlg.set_license(text)

		dlg.set_comments('%s\n%s %s\n%s %s'
			% (_('A GTK+ jabber client'), \
			_('GTK+ Version:'), self.tuple2str(gtk.gtk_version), \
			_('PyGTK Version:'), self.tuple2str(gtk.pygtk_version)))
		dlg.set_website('http://www.gajim.org/')

		authors_file_path = self.get_path('AUTHORS')
		if authors_file_path:
			authors = []
			authors_file = open(authors_file_path).read()
			authors_file = authors_file.split('\n')
			for author in authors_file:
				if author == 'CURRENT DEVELOPERS:':
					authors.append(_('Current Developers:'))
				elif author == 'PAST DEVELOPERS:':
					authors.append('\n' + _('Past Developers:'))
				elif author != '': # Real author line
					authors.append(author)

			thanks_file_path = self.get_path('THANKS')
			if thanks_file_path:
				authors.append('\n' + _('THANKS:'))

				text = open(thanks_file_path).read()
				text_splitted = text.split('\n')
				text = '\n'.join(text_splitted[:-2]) # remove one english sentence
				# and add it manually as translatable
				text += '\n%s\n' % _('Last but not least, we would like to thank all '
					'the package maintainers.')
				authors.append(text)

			dlg.set_authors(authors)

		dlg.props.wrap_license = True

		pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(
			gajim.DATA_DIR, 'pixmaps', 'gajim_about.png'))

		dlg.set_logo(pixbuf)
		#here you write your name in the form Name FamilyName <someone@somewhere>
		dlg.set_translator_credits(_('translator-credits'))

		thanks_artists_file_path = self.get_path('THANKS.artists')
		if thanks_artists_file_path:
			artists_text = open(thanks_artists_file_path).read()
			artists = artists_text.split('\n')
			dlg.set_artists(artists)
		# connect close button to destroy() function
		for button in dlg.action_area.get_children():
			if button.get_property('label') == gtk.STOCK_CLOSE:
				button.connect('clicked', lambda x:dlg.destroy())
		dlg.show_all()

	def tuple2str(self, tuple_):
		str_ = ''
		for num in tuple_:
			str_ += str(num) + '.'
		return str_[0:-1] # remove latest .

	def get_path(self, filename):
		'''where can we find this Credits file ?'''
		if os.path.isfile(os.path.join(gajim.defs.docdir, filename)):
			return os.path.join(gajim.defs.docdir, filename)
		elif os.path.isfile('../' + filename):
			return ('../' + filename)
		else:
			return None

class Dialog(gtk.Dialog):
	def __init__(self, parent, title, buttons, default=None,
	on_response_ok=None, on_response_cancel=None):
		gtk.Dialog.__init__(self, title, parent, gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_NO_SEPARATOR)

		self.user_response_ok = on_response_ok
		self.user_response_cancel = on_response_cancel
		self.set_border_width(6)
		self.vbox.set_spacing(12)
		self.set_resizable(False)

		possible_responses = {gtk.STOCK_OK: self.on_response_ok,
			gtk.STOCK_CANCEL: self.on_response_cancel}
		for stock, response in buttons:
			b = self.add_button(stock, response)
			for response in possible_responses:
				if stock == response:
					b.connect('clicked', possible_responses[response])
					break

		if default is not None:
			self.set_default_response(default)
		else:
			self.set_default_response(buttons[-1][1])

	def on_response_ok(self, widget):
		if self.user_response_ok:
			if isinstance(self.user_response_ok, tuple):
				self.user_response_ok[0](*self.user_response_ok[1:])
			else:
				self.user_response_ok()
		self.destroy()

	def on_response_cancel(self, widget):
		if self.user_response_cancel:
			if isinstance(self.user_response_cancel, tuple):
				self.user_response_cancel[0](*self.user_response_ok[1:])
			else:
				self.user_response_cancel()
		self.destroy()

	def just_destroy(self, widget):
		self.destroy()

	def get_button(self, index):
		buttons = self.action_area.get_children()
		return index < len(buttons) and buttons[index] or None


class HigDialog(gtk.MessageDialog):
	def __init__(self, parent, type_, buttons, pritext, sectext,
	on_response_ok = None, on_response_cancel = None, on_response_yes = None,
	on_response_no = None):
		gtk.MessageDialog.__init__(self, parent,
				gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
				type_, buttons, message_format = pritext)

		self.format_secondary_markup(sectext)

		buttons = self.action_area.get_children()
		possible_responses = {gtk.STOCK_OK: on_response_ok,
			gtk.STOCK_CANCEL: on_response_cancel, gtk.STOCK_YES: on_response_yes,
			gtk.STOCK_NO: on_response_no}
		for b in buttons:
			for response in possible_responses:
				if b.get_label() == response:
					if not possible_responses[response]:
						b.connect('clicked', self.just_destroy)
					elif isinstance(possible_responses[response], tuple):
						if len(possible_responses[response]) == 1:
							b.connect('clicked', possible_responses[response][0])
						else:
							b.connect('clicked', *possible_responses[response])
					else:
						b.connect('clicked', possible_responses[response])
					break

	def just_destroy(self, widget):
		self.destroy()

	def popup(self):
		'''show dialog'''
		vb = self.get_children()[0].get_children()[0] # Give focus to top vbox
		vb.set_flags(gtk.CAN_FOCUS)
		vb.grab_focus()
		self.show_all()

class FileChooserDialog(gtk.FileChooserDialog):
	'''Non-blocking FileChooser Dialog around gtk.FileChooserDialog'''
	def __init__(self, title_text, action, buttons, default_response,
	select_multiple = False, current_folder = None, on_response_ok = None,
	on_response_cancel = None):

		gtk.FileChooserDialog.__init__(self, title=title_text, action=action,
			buttons=buttons)

		self.set_default_response(default_response)
		self.set_select_multiple(select_multiple)
		if current_folder and os.path.isdir(current_folder):
			self.set_current_folder(current_folder)
		else:
			self.set_current_folder(helpers.get_documents_path())
		self.response_ok, self.response_cancel = \
			on_response_ok, on_response_cancel
		# in gtk+-2.10 clicked signal on some of the buttons in a dialog
		# is emitted twice, so we cannot rely on 'clicked' signal
		self.connect('response', self.on_dialog_response)
		self.show_all()

	def on_dialog_response(self, dialog, response):
		if response in (gtk.RESPONSE_CANCEL, gtk.RESPONSE_CLOSE):
			if self.response_cancel:
				if isinstance(self.response_cancel, tuple):
					self.response_cancel[0](dialog, *self.response_cancel[1:])
				else:
					self.response_cancel(dialog)
			else:
				self.just_destroy(dialog)
		elif response == gtk.RESPONSE_OK:
			if self.response_ok:
				if isinstance(self.response_ok, tuple):
					self.response_ok[0](dialog, *self.response_ok[1:])
				else:
					self.response_ok(dialog)
			else:
				self.just_destroy(dialog)

	def just_destroy(self, widget):
		self.destroy()

class AspellDictError:
	def __init__(self, lang):
		ErrorDialog(
			_('Dictionary for lang %s not available') % lang,
			_('You have to install %s dictionary to use spellchecking, or '
			'choose another language by setting the speller_language option.'
			'\n\nHighlighting misspelled words feature will not be used') % lang)
		gajim.config.set('use_speller', False)

class ConfirmationDialog(HigDialog):
	'''HIG compliant confirmation dialog.'''
	def __init__(self, pritext, sectext='', on_response_ok=None,
	on_response_cancel=None):
		self.user_response_ok = on_response_ok
		self.user_response_cancel = on_response_cancel
		HigDialog.__init__(self, None,
			gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, pritext, sectext,
			self.on_response_ok, self.on_response_cancel)
		self.popup()

	def on_response_ok(self, widget):
		if self.user_response_ok:
			if isinstance(self.user_response_ok, tuple):
				self.user_response_ok[0](*self.user_response_ok[1:])
			else:
				self.user_response_ok()
		self.destroy()

	def on_response_cancel(self, widget):
		if self.user_response_cancel:
			if isinstance(self.user_response_cancel, tuple):
				self.user_response_cancel[0](*self.user_response_ok[1:])
			else:
				self.user_response_cancel()
		self.destroy()

class NonModalConfirmationDialog(HigDialog):
	'''HIG compliant non modal confirmation dialog.'''
	def __init__(self, pritext, sectext='', on_response_ok=None,
	on_response_cancel=None):
		self.user_response_ok = on_response_ok
		self.user_response_cancel = on_response_cancel
		HigDialog.__init__(self, None,
			gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, pritext, sectext,
			self.on_response_ok, self.on_response_cancel)
		self.set_modal(False)

	def on_response_ok(self, widget):
		if self.user_response_ok:
			if isinstance(self.user_response_ok, tuple):
				self.user_response_ok[0](*self.user_response_ok[1:])
			else:
				self.user_response_ok()
		self.destroy()

	def on_response_cancel(self, widget):
		if self.user_response_cancel:
			if isinstance(self.user_response_cancel, tuple):
				self.user_response_cancel[0](*self.user_response_cancel[1:])
			else:
				self.user_response_cancel()
		self.destroy()

class WarningDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		'''HIG compliant warning dialog.'''
		HigDialog.__init__( self, None,
			gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, pritext, sectext)
		self.set_modal(False)
		self.set_transient_for(gajim.interface.roster.window)
		self.popup()

class InformationDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		'''HIG compliant info dialog.'''
		HigDialog.__init__(self, None,
			gtk.MESSAGE_INFO, gtk.BUTTONS_OK, pritext, sectext)
		self.set_modal(False)
		self.set_transient_for(gajim.interface.roster.window)
		self.popup()

class ErrorDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		'''HIG compliant error dialog.'''
		HigDialog.__init__( self, None,
			gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, pritext, sectext)
		self.popup()

class YesNoDialog(HigDialog):
	def __init__(self, pritext, sectext='', checktext='', on_response_yes=None,
	on_response_no=None):
		'''HIG compliant YesNo dialog.'''
		self.user_response_yes = on_response_yes
		self.user_response_no = on_response_no
		HigDialog.__init__( self, None,
			gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, pritext, sectext,
				on_response_yes=self.on_response_yes,
				on_response_no=self.on_response_no)

		if checktext:
			self.checkbutton = gtk.CheckButton(checktext)
			self.vbox.pack_start(self.checkbutton, expand=False, fill=True)
		else:
			self.checkbutton = None
		self.set_modal(False)
		self.popup()

	def on_response_yes(self, widget):
		if self.user_response_yes:
			if isinstance(self.user_response_yes, tuple):
				self.user_response_yes[0](self.is_checked(),
					*self.user_response_yes[1:])
			else:
				self.user_response_yes(self.is_checked())
		self.destroy()

	def on_response_no(self, widget):
		if self.user_response_no:
			if isinstance(self.user_response_no, tuple):
				self.user_response_no[0](*self.user_response_no[1:])
			else:
				self.user_response_no()
		self.destroy()

	def is_checked(self):
		''' Get active state of the checkbutton '''
		if not self.checkbutton:
			return False
		return self.checkbutton.get_active()

class ConfirmationDialogCheck(ConfirmationDialog):
	'''HIG compliant confirmation dialog with checkbutton.'''
	def __init__(self, pritext, sectext='', checktext='',
	on_response_ok=None, on_response_cancel=None, is_modal=True):
		self.user_response_ok = on_response_ok
		self.user_response_cancel = on_response_cancel

		HigDialog.__init__(self, None, gtk.MESSAGE_QUESTION,
			gtk.BUTTONS_OK_CANCEL, pritext, sectext, self.on_response_ok,
			self.on_response_cancel)

		self.set_default_response(gtk.RESPONSE_OK)

		ok_button = self.action_area.get_children()[0] # right to left
		ok_button.grab_focus()

		self.checkbutton = gtk.CheckButton(checktext)
		self.vbox.pack_start(self.checkbutton, expand=False, fill=True)
		self.set_modal(is_modal)
		self.popup()

	# XXX should cancel if somebody closes the dialog

	def on_response_ok(self, widget):
		if self.user_response_ok:
			if isinstance(self.user_response_ok, tuple):
				self.user_response_ok[0](self.is_checked(),
					*self.user_response_ok[1:])
			else:
				self.user_response_ok(self.is_checked())
		self.destroy()

	def on_response_cancel(self, widget):
		if self.user_response_cancel:
			if isinstance(self.user_response_cancel, tuple):
				self.user_response_cancel[0](self.is_checked(),
					*self.user_response_cancel[1:])
			else:
				self.user_response_cancel(self.is_checked())
		self.destroy()

	def is_checked(self):
		''' Get active state of the checkbutton '''
		return self.checkbutton.get_active()

class ConfirmationDialogDubbleCheck(ConfirmationDialog):
	'''HIG compliant confirmation dialog with 2 checkbuttons.'''
	def __init__(self, pritext, sectext='', checktext1='', checktext2='',
	on_response_ok=None, on_response_cancel=None, is_modal=True):
		self.user_response_ok = on_response_ok
		self.user_response_cancel = on_response_cancel

		HigDialog.__init__(self, None, gtk.MESSAGE_QUESTION,
			gtk.BUTTONS_OK_CANCEL, pritext, sectext, self.on_response_ok,
			self.on_response_cancel)

		self.set_default_response(gtk.RESPONSE_OK)

		ok_button = self.action_area.get_children()[0] # right to left
		ok_button.grab_focus()

		if checktext1:
			self.checkbutton1 = gtk.CheckButton(checktext1)
			self.vbox.pack_start(self.checkbutton1, expand=False, fill=True)
		else:
			self.checkbutton1 = None
		if checktext2:
			self.checkbutton2 = gtk.CheckButton(checktext2)
			self.vbox.pack_start(self.checkbutton2, expand=False, fill=True)
		else:
			self.checkbutton2 = None

		self.set_modal(is_modal)
		self.popup()

	# XXX should cancel if somebody closes the dialog

	def on_response_ok(self, widget):
		if self.user_response_ok:
			if isinstance(self.user_response_ok, tuple):
				self.user_response_ok[0](self.is_checked(),
					*self.user_response_ok[1:])
			else:
				self.user_response_ok(self.is_checked())
		self.destroy()

	def on_response_cancel(self, widget):
		if self.user_response_cancel:
			if isinstance(self.user_response_cancel, tuple):
				self.user_response_cancel[0](*self.user_response_cancel[1:])
			else:
				self.user_response_cancel()
		self.destroy()

	def is_checked(self):
		''' Get active state of the checkbutton '''
		if self.checkbutton1:
			is_checked_1 = self.checkbutton1.get_active()
		else:
			is_checked_1 = False
		if self.checkbutton2:
			is_checked_2 = self.checkbutton2.get_active()
		else:
			is_checked_2 = False
		return [is_checked_1, is_checked_2]

class FTOverwriteConfirmationDialog(ConfirmationDialog):
	'''HIG compliant confirmation dialog to overwrite or resume a file transfert'''
	def __init__(self, pritext, sectext='', propose_resume=True,
	on_response=None):
		HigDialog.__init__(self, None, gtk.MESSAGE_QUESTION, gtk.BUTTONS_CANCEL,
			pritext, sectext)

		self.on_response = on_response

		if propose_resume:
			b = gtk.Button('', gtk.STOCK_REFRESH)
			align = b.get_children()[0]
			hbox = align.get_children()[0]
			label = hbox.get_children()[1]
			label.set_text('_Resume')
			label.set_use_underline(True)
			self.add_action_widget(b, 100)

		b = gtk.Button('', gtk.STOCK_SAVE_AS)
		align = b.get_children()[0]
		hbox = align.get_children()[0]
		label = hbox.get_children()[1]
		label.set_text('Re_place')
		label.set_use_underline(True)
		self.add_action_widget(b, 200)

		self.connect('response', self.on_dialog_response)
		self.show_all()

	def on_dialog_response(self, dialog, response):
		if self.on_response:
			if isinstance(self.on_response, tuple):
				self.on_response[0](response, *self.on_response[1:])
			else:
				self.on_response(response)
		self.destroy()

class CommonInputDialog:
	'''Common Class for Input dialogs'''
	def __init__(self, title, label_str, is_modal, ok_handler, cancel_handler):
		self.dialog = self.xml.get_widget('input_dialog')
		label = self.xml.get_widget('label')
		self.dialog.set_title(title)
		label.set_markup(label_str)
		self.cancel_handler = cancel_handler

		self.ok_handler = ok_handler
		okbutton = self.xml.get_widget('okbutton')
		okbutton.connect('clicked', self.on_okbutton_clicked)
		cancelbutton = self.xml.get_widget('cancelbutton')
		cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
		self.xml.signal_autoconnect(self)
		self.dialog.show_all()

	def on_input_dialog_destroy(self, widget):
		if self.cancel_handler:
			self.cancel_handler()

	def on_okbutton_clicked(self, widget):
		user_input = self.get_text()
		if user_input:
			user_input = user_input.decode('utf-8')
		self.cancel_handler = None
		self.dialog.destroy()
		if isinstance(self.ok_handler, tuple):
			self.ok_handler[0](user_input, *self.ok_handler[1:])
		else:
			self.ok_handler(user_input)

	def on_cancelbutton_clicked(self, widget):
		self.dialog.destroy()

class InputDialog(CommonInputDialog):
	'''Class for Input dialog'''
	def __init__(self, title, label_str, input_str=None, is_modal=True,
	ok_handler=None, cancel_handler=None):
		self.xml = gtkgui_helpers.get_glade('input_dialog.glade')
		CommonInputDialog.__init__(self, title, label_str, is_modal, ok_handler,
			cancel_handler)
		self.input_entry = self.xml.get_widget('input_entry')
		if input_str:
			self.input_entry.set_text(input_str)
			self.input_entry.select_region(0, -1) # select all

	def get_text(self):
		return self.input_entry.get_text().decode('utf-8')

class InputTextDialog(CommonInputDialog):
	'''Class for multilines Input dialog (more place than InputDialog)'''
	def __init__(self, title, label_str, input_str=None, is_modal=True,
	ok_handler=None, cancel_handler=None):
		self.xml = gtkgui_helpers.get_glade('input_text_dialog.glade')
		CommonInputDialog.__init__(self, title, label_str, is_modal, ok_handler,
			cancel_handler)
		self.input_buffer = self.xml.get_widget('input_textview').get_buffer()
		if input_str:
			self.input_buffer.set_text(input_str)
			start_iter, end_iter = self.input_buffer.get_bounds()
			self.input_buffer.select_range(start_iter, end_iter) # select all

	def get_text(self):
		start_iter, end_iter = self.input_buffer.get_bounds()
		return self.input_buffer.get_text(start_iter, end_iter).decode('utf-8')

class DubbleInputDialog:
	'''Class for Dubble Input dialog'''
	def __init__(self, title, label_str1, label_str2, input_str1=None,
	input_str2=None, is_modal=True, ok_handler=None, cancel_handler=None):
		self.xml = gtkgui_helpers.get_glade('dubbleinput_dialog.glade')
		self.dialog = self.xml.get_widget('dubbleinput_dialog')
		label1 = self.xml.get_widget('label1')
		self.input_entry1 = self.xml.get_widget('input_entry1')
		label2 = self.xml.get_widget('label2')
		self.input_entry2 = self.xml.get_widget('input_entry2')
		self.dialog.set_title(title)
		label1.set_markup(label_str1)
		label2.set_markup(label_str2)
		self.cancel_handler = cancel_handler
		if input_str1:
			self.input_entry1.set_text(input_str1)
			self.input_entry1.select_region(0, -1) # select all
		if input_str2:
			self.input_entry2.set_text(input_str2)
			self.input_entry2.select_region(0, -1) # select all

		self.dialog.set_modal(is_modal)

		self.ok_handler = ok_handler
		okbutton = self.xml.get_widget('okbutton')
		okbutton.connect('clicked', self.on_okbutton_clicked)
		cancelbutton = self.xml.get_widget('cancelbutton')
		cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
		self.xml.signal_autoconnect(self)
		self.dialog.show_all()

	def on_dubbleinput_dialog_destroy(self, widget):
		if not self.cancel_handler:
			return False
		if isinstance(self.cancel_handler, tuple):
			self.cancel_handler[0](*self.cancel_handler[1:])
		else:
			self.cancel_handler()

	def on_okbutton_clicked(self, widget):
		user_input1 = self.input_entry1.get_text().decode('utf-8')
		user_input2 = self.input_entry2.get_text().decode('utf-8')
		self.dialog.destroy()
		if not self.ok_handler:
			return
		if isinstance(self.ok_handler, tuple):
			self.ok_handler[0](user_input1, user_input2, *self.ok_handler[1:])
		else:
			self.ok_handler(user_input1, user_input2)

	def on_cancelbutton_clicked(self, widget):
		self.dialog.destroy()
		if not self.cancel_handler:
			return
		if isinstance(self.cancel_handler, tuple):
			self.cancel_handler[0](*self.cancel_handler[1:])
		else:
			self.cancel_handler()

class SubscriptionRequestWindow:
	def __init__(self, jid, text, account, user_nick=None):
		xml = gtkgui_helpers.get_glade('subscription_request_window.glade')
		self.window = xml.get_widget('subscription_request_window')
		self.jid = jid
		self.account = account
		self.user_nick = user_nick
		if len(gajim.connections) >= 2:
			prompt_text = \
				_('Subscription request for account %(account)s from %(jid)s')\
				% {'account': account, 'jid': self.jid}
		else:
			prompt_text = _('Subscription request from %s') % self.jid
		xml.get_widget('from_label').set_text(prompt_text)
		xml.get_widget('message_textview').get_buffer().set_text(text)
		xml.signal_autoconnect(self)
		self.window.show_all()

	def prepare_popup_menu(self):
		xml = gtkgui_helpers.get_glade('subscription_request_popup_menu.glade')
		menu = xml.get_widget('subscription_request_popup_menu')
		xml.signal_autoconnect(self)
		return menu

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_authorize_button_clicked(self, widget):
		'''accept the request'''
		gajim.connections[self.account].send_authorization(self.jid)
		self.window.destroy()
		if self.jid not in gajim.contacts.get_jid_list(self.account):
			AddNewContactWindow(self.account, self.jid, self.user_nick)

	def on_contact_info_activate(self, widget):
		'''ask vcard'''
		if self.jid in gajim.interface.instances[self.account]['infos']:
			gajim.interface.instances[self.account]['infos'][self.jid].window.present()
		else:
			contact = gajim.contacts.create_contact(jid=self.jid, name='',
			groups=[], show='', status='', sub='', ask='', resource='',
			priority=5, keyID='', our_chatstate=None, chatstate=None)
			gajim.interface.instances[self.account]['infos'][self.jid] = \
				vcard.VcardWindow(contact, self.account)
			# Remove jabber page
			gajim.interface.instances[self.account]['infos'][self.jid].xml.\
				get_widget('information_notebook').remove_page(0)

	def on_start_chat_activate(self, widget):
		'''open chat'''
		gajim.interface.new_chat_from_jid(self.account, self.jid)

	def on_deny_button_clicked(self, widget):
		'''refuse the request'''
		gajim.connections[self.account].refuse_authorization(self.jid)
		self.window.destroy()

	def on_actions_button_clicked(self, widget):
		'''popup action menu'''
		menu = self.prepare_popup_menu()
		menu.show_all()
		gtkgui_helpers.popup_emoticons_under_button(menu, widget, self.window.window)


class JoinGroupchatWindow:
	def __init__(self, account, room_jid='', nick='', password='',
	automatic=False):
		'''automatic is a dict like {'invities': []}
		If automatic is not empty, this means room must be automaticaly configured
		and when done, invities must be automatically invited'''
		if room_jid != '':
			if room_jid in gajim.gc_connected[account] and\
			gajim.gc_connected[account][room_jid]:
				ErrorDialog(_('You are already in group chat %s') % room_jid)
				raise GajimGeneralException, 'You are already in this group chat'
		self.account = account
		self.automatic = automatic
		if nick == '':
			nick = gajim.nicks[self.account]
		if gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
				_('You can not join a group chat unless you are connected.'))
			raise GajimGeneralException, 'You must be connected to join a groupchat'

		self._empty_required_widgets = []

		self.xml = gtkgui_helpers.get_glade('join_groupchat_window.glade')
		self.window = self.xml.get_widget('join_groupchat_window')
		self._room_jid_entry = self.xml.get_widget('room_jid_entry')
		self._nickname_entry = self.xml.get_widget('nickname_entry')
		self._password_entry = self.xml.get_widget('password_entry')

		self._room_jid_entry.set_text(room_jid)
		self._nickname_entry.set_text(nick)
		if password:
			self._password_entry.set_text(password)
		self.xml.signal_autoconnect(self)
		# now add us to open windows
		gajim.interface.instances[account]['join_gc'] = self
		if len(gajim.connections) > 1:
			title = _('Join Group Chat with account %s') % account
		else:
			title = _('Join Group Chat')
		self.window.set_title(title)

		self.recently_combobox = self.xml.get_widget('recently_combobox')
		liststore = gtk.ListStore(str)
		self.recently_combobox.set_model(liststore)
		cell = gtk.CellRendererText()
		self.recently_combobox.pack_start(cell, True)
		self.recently_combobox.add_attribute(cell, 'text', 0)
		self.recently_groupchat = gajim.config.get('recently_groupchat').split()
		for g in self.recently_groupchat:
			self.recently_combobox.append_text(g)
		if len(self.recently_groupchat) == 0:
			self.recently_combobox.set_sensitive(False)
		elif room_jid == '':
			self.recently_combobox.set_active(0)
			self._room_jid_entry.select_region(0, -1)
		elif room_jid != '':
			self.xml.get_widget('join_button').grab_focus()

		if not self._room_jid_entry.get_text():
			self._empty_required_widgets.append(self._room_jid_entry)
		if not self._nickname_entry.get_text():
			self._empty_required_widgets.append(self._nickname_entry)
		if len(self._empty_required_widgets):
			self.xml.get_widget('join_button').set_sensitive(False)

		if not gajim.connections[account].private_storage_supported:
			self.xml.get_widget('auto_join_checkbutton').set_sensitive(False)

		self.window.show_all()

	def on_join_groupchat_window_destroy(self, widget):
		'''close window'''
		# remove us from open windows
		del gajim.interface.instances[self.account]['join_gc']

	def on_join_groupchat_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			widget.destroy()

	def on_required_entry_changed(self, widget):
		if not widget.get_text():
			self._empty_required_widgets.append(widget)
			self.xml.get_widget('join_button').set_sensitive(False)
		else:
			if widget in self._empty_required_widgets:
				self._empty_required_widgets.remove(widget)
				if len(self._empty_required_widgets) == 0:
					self.xml.get_widget('join_button').set_sensitive(True)

	def on_recently_combobox_changed(self, widget):
		model = widget.get_model()
		iter_ = widget.get_active_iter()
		room_jid = model[iter_][0].decode('utf-8')
		self._room_jid_entry.set_text(room_jid)

	def on_cancel_button_clicked(self, widget):
		'''When Cancel button is clicked'''
		self.window.destroy()

	def on_join_button_clicked(self, widget):
		'''When Join button is clicked'''
		nickname = self._nickname_entry.get_text().decode('utf-8')
		room_jid = self._room_jid_entry.get_text().decode('utf-8')
		password = self._password_entry.get_text().decode('utf-8')
		try:
			nickname = helpers.parse_resource(nickname)
		except Exception:
			ErrorDialog(_('Invalid Nickname'),
				_('The nickname has not allowed characters.'))
			return
		user, server, resource = helpers.decompose_jid(room_jid)
		if not user or not server or resource:
			ErrorDialog(_('Invalid group chat Jabber ID'),
				_('The group chat Jabber ID has not allowed characters.'))
			return
		try:
			room_jid = helpers.parse_jid(room_jid)
		except Exception:
			ErrorDialog(_('Invalid group chat Jabber ID'),
				_('The group chat Jabber ID has not allowed characters.'))
			return

		if gajim.interface.msg_win_mgr.has_window(room_jid, self.account):
			ctrl = gajim.interface.msg_win_mgr.get_gc_control(room_jid, self.account)
			if ctrl.type_id != message_control.TYPE_GC:
				ErrorDialog(_('This is not a group chat'),
					_('%s is not the name of a group chat.') % room_jid)
				return
		if room_jid in self.recently_groupchat:
			self.recently_groupchat.remove(room_jid)
		self.recently_groupchat.insert(0, room_jid)
		if len(self.recently_groupchat) > 10:
			self.recently_groupchat = self.recently_groupchat[0:10]
		gajim.config.set('recently_groupchat',
			' '.join(self.recently_groupchat))

		if self.xml.get_widget('auto_join_checkbutton').get_active():
			# Add as bookmark, with autojoin and not minimized
			name = gajim.get_nick_from_jid(room_jid)
			gajim.interface.add_gc_bookmark(self.account, name, room_jid, '1', \
				'0', password, nickname)

		if self.automatic:
			gajim.automatic_rooms[self.account][room_jid] = self.automatic
		gajim.interface.join_gc_room(self.account, room_jid, nickname,	password)

		self.window.destroy()

class SynchroniseSelectAccountDialog:
	def __init__(self, account):
		# 'account' can be None if we are about to create our first one
		if not account or gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
				_('Without a connection, you can not synchronise your contacts.'))
			raise GajimGeneralException, 'You are not connected to the server'
		self.account = account
		self.xml = gtkgui_helpers.get_glade('synchronise_select_account_dialog.glade')
		self.dialog = self.xml.get_widget('synchronise_select_account_dialog')
		self.accounts_treeview = self.xml.get_widget('accounts_treeview')
		model = gtk.ListStore(str, str, bool)
		self.accounts_treeview.set_model(model)
		# columns
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1,
					_('Name'), renderer, text=0)
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1,
					_('Server'), renderer, text=1)

		self.xml.signal_autoconnect(self)
		self.init_accounts()
		self.dialog.show_all()

	def on_accounts_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def init_accounts(self):
		'''initialize listStore with existing accounts'''
		model = self.accounts_treeview.get_model()
		model.clear()
		for remote_account in gajim.connections:
			if remote_account == self.account:
				# Do not show the account we're sync'ing
				continue
			iter_ = model.append()
			model.set(iter_, 0, remote_account, 1, gajim.get_hostname_from_account(
				remote_account))

	def on_cancel_button_clicked(self, widget):
		self.dialog.destroy()

	def on_ok_button_clicked(self, widget):
		sel = self.accounts_treeview.get_selection()
		(model, iter_) = sel.get_selected()
		if not iter_:
			return
		remote_account = model.get_value(iter_, 0).decode('utf-8')

		if gajim.connections[remote_account].connected < 2:
			ErrorDialog(_('This account is not connected to the server'),
				_('You cannot synchronize with an account unless it is connected.'))
			return
		else:
			try:
				SynchroniseSelectContactsDialog(self.account, remote_account)
			except GajimGeneralException:
				# if we showed ErrorDialog, there will not be dialog instance
				return
		self.dialog.destroy()

class SynchroniseSelectContactsDialog:
	def __init__(self, account, remote_account):
		self.local_account = account
		self.remote_account = remote_account
		self.xml = gtkgui_helpers.get_glade('synchronise_select_contacts_dialog.glade')
		self.dialog = self.xml.get_widget('synchronise_select_contacts_dialog')
		self.contacts_treeview = self.xml.get_widget('contacts_treeview')
		model = gtk.ListStore(bool, str)
		self.contacts_treeview.set_model(model)
		# columns
		renderer1 = gtk.CellRendererToggle()
		renderer1.set_property('activatable', True)
		renderer1.connect('toggled', self.toggled_callback)
		self.contacts_treeview.insert_column_with_attributes(-1,
					_('Synchronise'), renderer1, active=0)
		renderer2 = gtk.CellRendererText()
		self.contacts_treeview.insert_column_with_attributes(-1,
					_('Name'), renderer2, text=1)

		self.xml.signal_autoconnect(self)
		self.init_contacts()
		self.dialog.show_all()

	def toggled_callback(self, cell, path):
		model = self.contacts_treeview.get_model()
		iter_ = model.get_iter(path)
		model[iter_][0] = not cell.get_active()

	def on_contacts_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def init_contacts(self):
		'''initialize listStore with existing accounts'''
		model = self.contacts_treeview.get_model()
		model.clear()

		# recover local contacts
		local_jid_list = gajim.contacts.get_jid_list(self.local_account)

		remote_jid_list = gajim.contacts.get_jid_list(self.remote_account)
		for remote_jid in remote_jid_list:
			if remote_jid not in local_jid_list:
				iter_ = model.append()
				model.set(iter_, 0, True, 1, remote_jid)

	def on_cancel_button_clicked(self, widget):
		self.dialog.destroy()

	def on_ok_button_clicked(self, widget):
		model = self.contacts_treeview.get_model()
		iter_ = model.get_iter_root()
		while iter_:
			if model[iter_][0]:
				# it is selected
				remote_jid = model[iter_][1].decode('utf-8')
				message = 'I\'m synchronizing my contacts from my %s account, could you please add this address to your contact list?' % \
					gajim.get_hostname_from_account(self.remote_account)
				remote_contact = gajim.contacts.get_first_contact_from_jid(
					self.remote_account, remote_jid)
				# keep same groups and same nickname
				gajim.interface.roster.req_sub(self, remote_jid, message,
					self.local_account, groups = remote_contact.groups,
					nickname = remote_contact.name, auto_auth = True)
			iter_ = model.iter_next(iter_)
		self.dialog.destroy()

class NewChatDialog(InputDialog):
	def __init__(self, account):
		self.account = account

		if len(gajim.connections) > 1:
			title = _('Start Chat with account %s') % account
		else:
			title = _('Start Chat')
		prompt_text = _('Fill in the nickname or the Jabber ID of the contact you would like\nto send a chat message to:')
		InputDialog.__init__(self, title, prompt_text, is_modal=False)

		self.completion_dict = {}
		liststore = gtkgui_helpers.get_completion_liststore(self.input_entry)
		self.completion_dict = helpers.get_contact_dict_for_account(account)
		# add all contacts to the model
		keys = sorted(self.completion_dict.keys())
		for jid in keys:
			contact = self.completion_dict[jid]
			img = gajim.interface.jabber_state_images['16'][contact.show]
			liststore.append((img.get_pixbuf(), jid))

		self.ok_handler = self.new_chat_response
		okbutton = self.xml.get_widget('okbutton')
		okbutton.connect('clicked', self.on_okbutton_clicked)
		cancelbutton = self.xml.get_widget('cancelbutton')
		cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
		self.dialog.show_all()

	def new_chat_response(self, jid):
		''' called when ok button is clicked '''
		if gajim.connections[self.account].connected <= 1:
			#if offline or connecting
			ErrorDialog(_('Connection not available'),
		_('Please make sure you are connected with "%s".') % self.account)
			return

		if jid in self.completion_dict:
			jid = self.completion_dict[jid].jid
		else:
			try:
				jid = helpers.parse_jid(jid)
			except helpers.InvalidFormat, e:
				ErrorDialog(_('Invalid JID'), e[0])
				return
			except:
				ErrorDialog(_('Invalid JID'), _('Unable to parse "%s".') % jid)
				return
		gajim.interface.new_chat_from_jid(self.account, jid)

class ChangePasswordDialog:
	def __init__(self, account, on_response):
		# 'account' can be None if we are about to create our first one
		if not account or gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
				_('Without a connection, you can not change your password.'))
			raise GajimGeneralException, 'You are not connected to the server'
		self.account = account
		self.on_response = on_response
		self.xml = gtkgui_helpers.get_glade('change_password_dialog.glade')
		self.dialog = self.xml.get_widget('change_password_dialog')
		self.password1_entry = self.xml.get_widget('password1_entry')
		self.password2_entry = self.xml.get_widget('password2_entry')
		self.dialog.connect('response', self.on_dialog_response)

		self.dialog.show_all()

	def on_dialog_response(self, dialog, response):
		if response != gtk.RESPONSE_OK:
			dialog.destroy()
			self.on_response(None)
			return
		password1 = self.password1_entry.get_text().decode('utf-8')
		if not password1:
			ErrorDialog(_('Invalid password'), _('You must enter a password.'))
			return
		password2 = self.password2_entry.get_text().decode('utf-8')
		if password1 != password2:
			ErrorDialog(_('Passwords do not match'),
				_('The passwords typed in both fields must be identical.'))
			return
		dialog.destroy()
		self.on_response(password1)

class PopupNotificationWindow:
	def __init__(self, event_type, jid, account, msg_type='',
	path_to_image=None, title=None, text=None):
		self.account = account
		self.jid = jid
		self.msg_type = msg_type

		xml = gtkgui_helpers.get_glade('popup_notification_window.glade')
		self.window = xml.get_widget('popup_notification_window')
		if gtk.gtk_version >= (2, 10, 0) and gtk.pygtk_version >= (2, 10, 0):
			self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_TOOLTIP)
		close_button = xml.get_widget('close_button')
		event_type_label = xml.get_widget('event_type_label')
		event_description_label = xml.get_widget('event_description_label')
		eventbox = xml.get_widget('eventbox')
		image = xml.get_widget('notification_image')

		if not text:
			text = gajim.get_name_from_jid(account, jid) # default value of text
		if not title:
			title = ''

		event_type_label.set_markup(
			'<span foreground="black" weight="bold">%s</span>' %
			gobject.markup_escape_text(title))

		# set colors [ http://www.pitt.edu/~nisg/cis/web/cgi/rgb.html ]
		self.window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

		# default image
		if not path_to_image:
			path_to_image = os.path.abspath(
				os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
					'chat_msg_recv.png')) # img to display

		if event_type == _('Contact Signed In'):
			bg_color = 'limegreen'
		elif event_type == _('Contact Signed Out'):
			bg_color = 'red'
		elif event_type in (_('New Message'), _('New Single Message'),
			_('New Private Message'), _('New E-mail')):
			bg_color = 'dodgerblue'
		elif event_type == _('File Transfer Request'):
			bg_color = 'khaki'
		elif event_type == _('File Transfer Error'):
			bg_color = 'firebrick'
		elif event_type in (_('File Transfer Completed'),
			_('File Transfer Stopped')):
			bg_color = 'yellowgreen'
		elif event_type == _('Groupchat Invitation'):
			bg_color = 'tan1'
		elif event_type == _('Contact Changed Status'):
			bg_color = 'thistle2'
		else: # Unknown event! Shouldn't happen but deal with it
			bg_color = 'white'
		popup_bg_color = gtk.gdk.color_parse(bg_color)
		close_button.modify_bg(gtk.STATE_NORMAL, popup_bg_color)
		eventbox.modify_bg(gtk.STATE_NORMAL, popup_bg_color)
		event_description_label.set_markup('<span foreground="black">%s</span>' %
			gobject.markup_escape_text(text))

		# set the image
		image.set_from_file(path_to_image)

		# position the window to bottom-right of screen
		window_width, self.window_height = self.window.get_size()
		gajim.interface.roster.popups_notification_height += self.window_height
		pos_x = gajim.config.get('notification_position_x')
		if pos_x < 0:
			pos_x = gtk.gdk.screen_width() - window_width + pos_x + 1
		pos_y = gajim.config.get('notification_position_y')
		if pos_y < 0:
			pos_y = gtk.gdk.screen_height() - \
				gajim.interface.roster.popups_notification_height + pos_y + 1
		self.window.move(pos_x, pos_y)

		xml.signal_autoconnect(self)
		self.window.show_all()
		timeout = gajim.config.get('notification_timeout')
		gobject.timeout_add_seconds(timeout, self.on_timeout)

	def on_close_button_clicked(self, widget):
		self.adjust_height_and_move_popup_notification_windows()

	def on_timeout(self):
		self.adjust_height_and_move_popup_notification_windows()

	def adjust_height_and_move_popup_notification_windows(self):
		#remove
		gajim.interface.roster.popups_notification_height -= self.window_height
		self.window.destroy()

		if len(gajim.interface.roster.popup_notification_windows) > 0:
			# we want to remove the first window added in the list
			gajim.interface.roster.popup_notification_windows.pop(0)

		# move the rest of popup windows
		gajim.interface.roster.popups_notification_height = 0
		for window_instance in gajim.interface.roster.popup_notification_windows:
			window_width, window_height = window_instance.window.get_size()
			gajim.interface.roster.popups_notification_height += window_height
			window_instance.window.move(gtk.gdk.screen_width() - window_width,
				gtk.gdk.screen_height() - \
				gajim.interface.roster.popups_notification_height)

	def on_popup_notification_window_button_press_event(self, widget, event):
		if event.button != 1:
			self.window.destroy()
			return
		gajim.interface.handle_event(self.account, self.jid, self.msg_type)
		self.adjust_height_and_move_popup_notification_windows()

class SingleMessageWindow:
	'''SingleMessageWindow can send or show a received
	singled message depending on action argument which can be 'send'
	or 'receive'.
	'''
	# Keep a reference on windows so garbage collector don't restroy them
	instances = []
	def __init__(self, account, to='', action='', from_whom='', subject='',
	message='', resource='', session=None, form_node=None):
		self.instances.append(self)
		self.account = account
		self.action = action

		self.subject = subject
		self.message = message
		self.to = to
		self.from_whom = from_whom
		self.resource = resource
		self.session = session

		self.xml = gtkgui_helpers.get_glade('single_message_window.glade')
		self.window = self.xml.get_widget('single_message_window')
		self.count_chars_label = self.xml.get_widget('count_chars_label')
		self.from_label = self.xml.get_widget('from_label')
		self.from_entry = self.xml.get_widget('from_entry')
		self.to_label = self.xml.get_widget('to_label')
		self.to_entry = self.xml.get_widget('to_entry')
		self.subject_entry = self.xml.get_widget('subject_entry')
		self.message_scrolledwindow = self.xml.get_widget(
			'message_scrolledwindow')
		self.message_textview = self.xml.get_widget('message_textview')
		self.message_tv_buffer = self.message_textview.get_buffer()
		self.conversation_scrolledwindow = self.xml.get_widget(
			'conversation_scrolledwindow')
		self.conversation_textview = conversation_textview.ConversationTextview(
			account)
		self.conversation_textview.tv.show()
		self.conversation_tv_buffer = self.conversation_textview.tv.get_buffer()
		self.xml.get_widget('conversation_scrolledwindow').add(
			self.conversation_textview.tv)

		self.form_widget = None
		parent_box = self.xml.get_widget('conversation_scrolledwindow').\
			get_parent()
		if form_node:
			dataform = dataforms.ExtendForm(node=form_node)
			self.form_widget = dataforms_widget.DataFormWidget(dataform)
			self.form_widget.show_all()
			parent_box.add(self.form_widget)
			parent_box.child_set_property(self.form_widget, 'position',
				parent_box.child_get_property(self.xml.get_widget(
					'conversation_scrolledwindow'), 'position'))
			self.action = 'form'

		self.send_button = self.xml.get_widget('send_button')
		self.reply_button = self.xml.get_widget('reply_button')
		self.send_and_close_button = self.xml.get_widget('send_and_close_button')
		self.cancel_button = self.xml.get_widget('cancel_button')
		self.close_button = self.xml.get_widget('close_button')
		self.message_tv_buffer.connect('changed', self.update_char_counter)
		if isinstance(to, list):
			jid = ', '.join( [i[0].jid + '/' + i[0].resource for i in to])
			self.to_entry.set_text(jid)
			self.to_entry.set_sensitive(False)
		else:
			self.to_entry.set_text(to)

		if gajim.config.get('use_speller') and HAS_GTK_SPELL and action == 'send':
			try:
				lang = gajim.config.get('speller_language')
				if not lang:
					lang = gajim.LANG
				gtkspell.Spell(self.conversation_textview.tv, lang)
				gtkspell.Spell(self.message_textview, lang)
			except (gobject.GError, TypeError, RuntimeError):
				AspellDictError(lang)

		self.prepare_widgets_for(self.action)

		# set_text(None) raises TypeError exception
		if self.subject is None:
			self.subject = ''
		self.subject_entry.set_text(self.subject)


		if to == '':
			liststore = gtkgui_helpers.get_completion_liststore(self.to_entry)
			self.completion_dict = helpers.get_contact_dict_for_account(account)
			keys = sorted(self.completion_dict.keys())
			for jid in keys:
				contact = self.completion_dict[jid]
				img = gajim.interface.jabber_state_images['16'][contact.show]
				liststore.append((img.get_pixbuf(), jid))
		else:
			self.completion_dict = {}
		self.xml.signal_autoconnect(self)

		# get window position and size from config
		gtkgui_helpers.resize_window(self.window,
			gajim.config.get('single-msg-width'),
			gajim.config.get('single-msg-height'))
		gtkgui_helpers.move_window(self.window,
			gajim.config.get('single-msg-x-position'),
			gajim.config.get('single-msg-y-position'))

		self.window.show_all()

	def on_single_message_window_destroy(self, widget):
		self.instances.remove(self)

	def set_cursor_to_end(self):
		end_iter = self.message_tv_buffer.get_end_iter()
		self.message_tv_buffer.place_cursor(end_iter)

	def save_pos(self):
		# save the window size and position
		x, y = self.window.get_position()
		gajim.config.set('single-msg-x-position', x)
		gajim.config.set('single-msg-y-position', y)
		width, height = self.window.get_size()
		gajim.config.set('single-msg-width', width)
		gajim.config.set('single-msg-height', height)
		gajim.interface.save_config()

	def on_single_message_window_delete_event(self, window, ev):
		self.save_pos()

	def prepare_widgets_for(self, action):
		if len(gajim.connections) > 1:
			if action == 'send':
				title = _('Single Message using account %s') % self.account
			else:
				title = _('Single Message in account %s') % self.account
		else:
			title = _('Single Message')

		if action == 'send': # prepare UI for Sending
			title = _('Send %s') % title
			self.send_button.show()
			self.send_and_close_button.show()
			self.to_label.show()
			self.to_entry.show()
			self.reply_button.hide()
			self.from_label.hide()
			self.from_entry.hide()
			self.conversation_scrolledwindow.hide()
			self.message_scrolledwindow.show()

			if self.message: # we come from a reply?
				self.message_textview.grab_focus()
				self.cancel_button.hide()
				self.close_button.show()
				self.message_tv_buffer.set_text(self.message)
				gobject.idle_add(self.set_cursor_to_end)
			else: # we write a new message (not from reply)
				self.close_button.hide()
				if self.to: # do we already have jid?
					self.subject_entry.grab_focus()

		elif action == 'receive': # prepare UI for Receiving
			title = _('Received %s') % title
			self.reply_button.show()
			self.from_label.show()
			self.from_entry.show()
			self.send_button.hide()
			self.send_and_close_button.hide()
			self.to_label.hide()
			self.to_entry.hide()
			self.conversation_scrolledwindow.show()
			self.message_scrolledwindow.hide()

			if self.message:
				self.conversation_textview.print_real_text(self.message)
			fjid = self.from_whom
			if self.resource:
				fjid += '/' + self.resource # Full jid of sender (with resource)
			self.from_entry.set_text(fjid)
			self.from_entry.set_property('editable', False)
			self.subject_entry.set_property('editable', False)
			self.reply_button.grab_focus()
			self.cancel_button.hide()
			self.close_button.show()
		elif action == 'form': # prepare UI for Receiving
			title = _('Form %s') % title
			self.send_button.show()
			self.send_and_close_button.show()
			self.to_label.show()
			self.to_entry.show()
			self.reply_button.hide()
			self.from_label.hide()
			self.from_entry.hide()
			self.conversation_scrolledwindow.hide()
			self.message_scrolledwindow.hide()

		self.window.set_title(title)

	def on_cancel_button_clicked(self, widget):
		self.save_pos()
		self.window.destroy()

	def on_close_button_clicked(self, widget):
		self.save_pos()
		self.window.destroy()

	def update_char_counter(self, widget):
		characters_no = self.message_tv_buffer.get_char_count()
		self.count_chars_label.set_text(unicode(characters_no))

	def send_single_message(self):
		if gajim.connections[self.account].connected <= 1:
			# if offline or connecting
			ErrorDialog(_('Connection not available'),
				_('Please make sure you are connected with "%s".') % self.account)
			return
		if isinstance(self.to, list):
			sender_list = [i[0].jid + '/' + i[0].resource for i in self.to]
		else:
			sender_list = [self.to_entry.get_text().decode('utf-8')]

		for to_whom_jid in sender_list:
			if to_whom_jid in self.completion_dict:
				to_whom_jid = self.completion_dict[to_whom_jid].jid
			try:
				to_whom_jid = helpers.parse_jid(to_whom_jid)
			except helpers.InvalidFormat:
				ErrorDialog(_('Invalid Jabber ID'),
					_('It is not possible to send a message to %s, this JID is not '
					'valid.') % to_whom_jid)
				return

			subject = self.subject_entry.get_text().decode('utf-8')
			begin, end = self.message_tv_buffer.get_bounds()
			message = self.message_tv_buffer.get_text(begin, end).decode('utf-8')

			if '/announce/' in to_whom_jid:
				gajim.connections[self.account].send_motd(to_whom_jid, subject,
					message)
				continue

			if self.session:
				session = self.session
			else:
				session = gajim.connections[self.account].make_new_session(
					to_whom_jid)

			if self.form_widget:
				form_node = self.form_widget.data_form
			else:
				form_node = None
			# FIXME: allow GPG message some day
			gajim.connections[self.account].send_message(to_whom_jid, message,
				keyID=None, type_='normal', subject=subject, session=session,
				form_node=form_node)

		self.subject_entry.set_text('') # we sent ok, clear the subject
		self.message_tv_buffer.set_text('') # we sent ok, clear the textview

	def on_send_button_clicked(self, widget):
		self.send_single_message()

	def on_reply_button_clicked(self, widget):
		# we create a new blank window to send and we preset RE: and to jid
		self.subject = _('RE: %s') % self.subject
		self.message = _('%s wrote:\n') % self.from_whom + self.message
		# add > at the begining of each line
		self.message = self.message.replace('\n', '\n> ') + '\n\n'
		self.window.destroy()
		SingleMessageWindow(self.account, to=self.from_whom, action='send',
			from_whom=self.from_whom, subject=self.subject, message=self.message,
			session=self.session)

	def on_send_and_close_button_clicked(self, widget):
		self.send_single_message()
		self.save_pos()
		self.window.destroy()

	def on_single_message_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.save_pos()
			self.window.destroy()

class XMLConsoleWindow:
	def __init__(self, account):
		self.account = account

		self.xml = gtkgui_helpers.get_glade('xml_console_window.glade')
		self.window = self.xml.get_widget('xml_console_window')
		self.input_textview = self.xml.get_widget('input_textview')
		self.stanzas_log_textview = self.xml.get_widget('stanzas_log_textview')
		self.input_tv_buffer = self.input_textview.get_buffer()
		buffer_ = self.stanzas_log_textview.get_buffer()
		end_iter = buffer_.get_end_iter()
		buffer_.create_mark('end', end_iter, False)

		self.tagIn = buffer_.create_tag('incoming')
		color = gajim.config.get('inmsgcolor')
		self.tagIn.set_property('foreground', color)
		self.tagOut = buffer_.create_tag('outgoing')
		color = gajim.config.get('outmsgcolor')
		self.tagOut.set_property('foreground', color)

		self.enabled = False

		self.input_textview.modify_text(
			gtk.STATE_NORMAL, gtk.gdk.color_parse(color))

		if len(gajim.connections) > 1:
			title = _('XML Console for %s') % self.account
		else:
			title = _('XML Console')

		self.window.set_title(title)
		self.window.show_all()

		self.xml.signal_autoconnect(self)

	def on_xml_console_window_delete_event(self, widget, event):
		self.window.hide()
		return True # do NOT destroy the window

	def on_clear_button_clicked(self, widget):
		buffer_ = self.stanzas_log_textview.get_buffer()
		buffer_.set_text('')

	def on_enable_checkbutton_toggled(self, widget):
		self.enabled = widget.get_active()

	def scroll_to_end(self, ):
		parent = self.stanzas_log_textview.get_parent()
		buffer_ = self.stanzas_log_textview.get_buffer()
		end_mark = buffer_.get_mark('end')
		if not end_mark:
			return False
		self.stanzas_log_textview.scroll_to_mark(end_mark, 0, True,	0, 1)
		adjustment = parent.get_hadjustment()
		adjustment.set_value(0)
		return False

	def print_stanza(self, stanza, kind):
		# kind must be 'incoming' or 'outgoing'
		if not self.enabled:
			return
		if not stanza:
			return

		buffer = self.stanzas_log_textview.get_buffer()
		at_the_end = False
		end_iter = buffer.get_end_iter()
		end_rect = self.stanzas_log_textview.get_iter_location(end_iter)
		visible_rect = self.stanzas_log_textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			at_the_end = True
		end_iter = buffer.get_end_iter()
		buffer.insert_with_tags_by_name(end_iter, stanza.replace('><', '>\n<') + \
			'\n\n', kind)
		if at_the_end:
			gobject.idle_add(self.scroll_to_end)

	def on_send_button_clicked(self, widget):
		if gajim.connections[self.account].connected <= 1:
			#if offline or connecting
			ErrorDialog(_('Connection not available'),
		_('Please make sure you are connected with "%s".') % self.account)
			return
		begin_iter, end_iter = self.input_tv_buffer.get_bounds()
		stanza = self.input_tv_buffer.get_text(begin_iter, end_iter).decode(
			'utf-8')
		if stanza:
			gajim.connections[self.account].send_stanza(stanza)
			self.input_tv_buffer.set_text('') # we sent ok, clear the textview

	def on_presence_button_clicked(self, widget):
		self.input_tv_buffer.set_text(
		'<presence><show></show><status></status><priority></priority></presence>'
		)

	def on_iq_button_clicked(self, widget):
		self.input_tv_buffer.set_text(
			'<iq to="" type=""><query xmlns=""></query></iq>'
		)

	def on_message_button_clicked(self, widget):
		self.input_tv_buffer.set_text(
			'<message to="" type=""><body></body></message>'
		)

	def on_expander_activate(self, widget):
		if not widget.get_expanded(): # it's the opposite!
			# it's expanded!!
			self.input_textview.grab_focus()

class PrivacyListWindow:
	'''Window that is used for creating NEW or EDITING already there privacy
	lists'''
	def __init__(self, account, privacy_list_name, action):
		'''action is 'EDIT' or 'NEW' depending on if we create a new priv list
		or edit an already existing one'''
		self.account = account
		self.privacy_list_name = privacy_list_name

		# Dicts and Default Values
		self.active_rule = ''
		self.global_rules = {}
		self.list_of_groups = {}

		# Default Edit Values
		self.edit_rule_type = 'jid'
		self.allow_deny = 'allow'

		# Connect to glade
		self.xml = gtkgui_helpers.get_glade('privacy_list_window.glade')
		self.window = self.xml.get_widget('privacy_list_edit_window')

		# Add Widgets

		for widget_to_add in ('title_hbox', 'privacy_lists_title_label',
		'list_of_rules_label', 'add_edit_rule_label', 'delete_open_buttons_hbox',
		'privacy_list_active_checkbutton', 'privacy_list_default_checkbutton',
		'list_of_rules_combobox', 'delete_open_buttons_hbox',
		'delete_rule_button', 'open_rule_button', 'edit_allow_radiobutton',
		'edit_deny_radiobutton', 'edit_type_jabberid_radiobutton',
		'edit_type_jabberid_entry', 'edit_type_group_radiobutton',
		'edit_type_group_combobox', 'edit_type_subscription_radiobutton',
		'edit_type_subscription_combobox', 'edit_type_select_all_radiobutton',
		'edit_queries_send_checkbutton', 'edit_send_messages_checkbutton',
		'edit_view_status_checkbutton', 'edit_order_spinbutton',
		'new_rule_button', 'save_rule_button', 'privacy_list_refresh_button',
		'privacy_list_close_button', 'edit_send_status_checkbutton',
		'add_edit_vbox', 'privacy_list_active_checkbutton',
		'privacy_list_default_checkbutton'):
			self.__dict__[widget_to_add] = self.xml.get_widget(widget_to_add)

		self.privacy_lists_title_label.set_label(
			_('Privacy List <b><i>%s</i></b>') % \
			gobject.markup_escape_text(self.privacy_list_name))

		if len(gajim.connections) > 1:
			title = _('Privacy List for %s') % self.account
		else:
			title = _('Privacy List')

		self.delete_rule_button.set_sensitive(False)
		self.open_rule_button.set_sensitive(False)
		self.privacy_list_active_checkbutton.set_sensitive(False)
		self.privacy_list_default_checkbutton.set_sensitive(False)
		self.list_of_rules_combobox.set_sensitive(False)

		# set jabber id completion
		jids_list_store = gtk.ListStore(gobject.TYPE_STRING)
		for jid in gajim.contacts.get_jid_list(self.account):
			jids_list_store.append([jid])
		jid_entry_completion = gtk.EntryCompletion()
		jid_entry_completion.set_text_column(0)
		jid_entry_completion.set_model(jids_list_store)
		jid_entry_completion.set_popup_completion(True)
		self.edit_type_jabberid_entry.set_completion(jid_entry_completion)
		if action == 'EDIT':
			self.refresh_rules()

		count = 0
		for group in gajim.groups[self.account]:
			self.list_of_groups[group] = count
			count += 1
			self.edit_type_group_combobox.append_text(group)
		self.edit_type_group_combobox.set_active(0)

		self.window.set_title(title)

		self.window.show_all()
		self.add_edit_vbox.hide()

		self.xml.signal_autoconnect(self)

	def on_privacy_list_edit_window_destroy(self, widget):
		key_name = 'privacy_list_%s' % self.privacy_list_name
		if key_name in gajim.interface.instances[self.account]:
			del gajim.interface.instances[self.account][key_name]

	def check_active_default(self, a_d_dict):
		if a_d_dict['active'] == self.privacy_list_name:
			self.privacy_list_active_checkbutton.set_active(True)
		else:
			self.privacy_list_active_checkbutton.set_active(False)
		if a_d_dict['default'] == self.privacy_list_name:
			self.privacy_list_default_checkbutton.set_active(True)
		else:
			self.privacy_list_default_checkbutton.set_active(False)

	def privacy_list_received(self, rules):
		self.list_of_rules_combobox.get_model().clear()
		self.global_rules = {}
		for rule in rules:
			if 'type' in rule:
				text_item = _('Order: %(order)s, action: %(action)s, type: %(type)s'
				', value: %(value)s') % {'order': rule['order'],
				'action': rule['action'], 'type': rule['type'],
				'value': rule['value']}
			else:
				text_item = _('Order: %(order)s, action: %(action)s') % \
				{'order': rule['order'], 'action': rule['action']}
			self.global_rules[text_item] = rule
			self.list_of_rules_combobox.append_text(text_item)
		if len(rules) == 0:
			self.title_hbox.set_sensitive(False)
			self.list_of_rules_combobox.set_sensitive(False)
			self.delete_rule_button.set_sensitive(False)
			self.open_rule_button.set_sensitive(False)
			self.privacy_list_active_checkbutton.set_sensitive(False)
			self.privacy_list_default_checkbutton.set_sensitive(False)
		else:
			self.list_of_rules_combobox.set_active(0)
			self.title_hbox.set_sensitive(True)
			self.list_of_rules_combobox.set_sensitive(True)
			self.delete_rule_button.set_sensitive(True)
			self.open_rule_button.set_sensitive(True)
			self.privacy_list_active_checkbutton.set_sensitive(True)
			self.privacy_list_default_checkbutton.set_sensitive(True)
		self.reset_fields()
		gajim.connections[self.account].get_active_default_lists()

	def refresh_rules(self):
		gajim.connections[self.account].get_privacy_list(self.privacy_list_name)

	def on_delete_rule_button_clicked(self, widget):
		tags = []
		for rule in self.global_rules:
			if rule != self.list_of_rules_combobox.get_active_text():
				tags.append(self.global_rules[rule])
		gajim.connections[self.account].set_privacy_list(
			self.privacy_list_name, tags)
		self.privacy_list_received(tags)
		self.add_edit_vbox.hide()
		if not tags: # we removed latest rule
			if 'privacy_lists' in gajim.interface.instances[self.account]:
				win = gajim.interface.instances[self.account]['privacy_lists']
				win.remove_privacy_list_from_combobox(self.privacy_list_name)
				win.draw_widgets()

	def on_open_rule_button_clicked(self, widget):
		self.add_edit_rule_label.set_label(
			_('<b>Edit a rule</b>'))
		active_num = self.list_of_rules_combobox.get_active()
		if active_num == -1:
			self.active_rule = ''
		else:
			self.active_rule = \
				self.list_of_rules_combobox.get_active_text().decode('utf-8')
		if self.active_rule != '':
			rule_info = self.global_rules[self.active_rule]
			self.edit_order_spinbutton.set_value(int(rule_info['order']))
			if 'type' in rule_info:
				if rule_info['type'] == 'jid':
					self.edit_type_jabberid_radiobutton.set_active(True)
					self.edit_type_jabberid_entry.set_text(rule_info['value'])
				elif rule_info['type'] == 'group':
					self.edit_type_group_radiobutton.set_active(True)
					if rule_info['value'] in self.list_of_groups:
						self.edit_type_group_combobox.set_active(
							self.list_of_groups[rule_info['value']])
					else:
						self.edit_type_group_combobox.set_active(0)
				elif rule_info['type'] == 'subscription':
					self.edit_type_subscription_radiobutton.set_active(True)
					sub_value = rule_info['value']
					if sub_value == 'none':
						self.edit_type_subscription_combobox.set_active(0)
					elif sub_value == 'both':
						self.edit_type_subscription_combobox.set_active(1)
					elif sub_value == 'from':
						self.edit_type_subscription_combobox.set_active(2)
					elif sub_value == 'to':
						self.edit_type_subscription_combobox.set_active(3)
				else:
					self.edit_type_select_all_radiobutton.set_active(True)
			else:
				self.edit_type_select_all_radiobutton.set_active(True)
			self.edit_send_messages_checkbutton.set_active(False)
			self.edit_queries_send_checkbutton.set_active(False)
			self.edit_view_status_checkbutton.set_active(False)
			self.edit_send_status_checkbutton.set_active(False)
			for child in rule_info['child']:
				if child == 'presence-out':
					self.edit_send_status_checkbutton.set_active(True)
				elif child == 'presence-in':
					self.edit_view_status_checkbutton.set_active(True)
				elif child == 'iq':
					self.edit_queries_send_checkbutton.set_active(True)
				elif child == 'message':
					self.edit_send_messages_checkbutton.set_active(True)

			if rule_info['action'] == 'allow':
				self.edit_allow_radiobutton.set_active(True)
			else:
				self.edit_deny_radiobutton.set_active(True)
		self.add_edit_vbox.show()

	def on_privacy_list_active_checkbutton_toggled(self, widget):
		if widget.get_active():
			gajim.connections[self.account].set_active_list(
				self.privacy_list_name)
		else:
			gajim.connections[self.account].set_active_list(None)

	def on_privacy_list_default_checkbutton_toggled(self, widget):
		if widget.get_active():
			gajim.connections[self.account].set_default_list(
				self.privacy_list_name)
		else:
			gajim.connections[self.account].set_default_list(None)

	def on_new_rule_button_clicked(self, widget):
		self.reset_fields()
		self.add_edit_vbox.show()

	def reset_fields(self):
		self.edit_type_jabberid_entry.set_text('')
		self.edit_allow_radiobutton.set_active(True)
		self.edit_type_jabberid_radiobutton.set_active(True)
		self.active_rule = ''
		self.edit_send_messages_checkbutton.set_active(False)
		self.edit_queries_send_checkbutton.set_active(False)
		self.edit_view_status_checkbutton.set_active(False)
		self.edit_send_status_checkbutton.set_active(False)
		self.edit_order_spinbutton.set_value(1)
		self.edit_type_group_combobox.set_active(0)
		self.edit_type_subscription_combobox.set_active(0)
		self.add_edit_rule_label.set_label(
			_('<b>Add a rule</b>'))

	def get_current_tags(self):
		if self.edit_type_jabberid_radiobutton.get_active():
			edit_type = 'jid'
			edit_value = self.edit_type_jabberid_entry.get_text()
		elif self.edit_type_group_radiobutton.get_active():
			edit_type = 'group'
			edit_value = self.edit_type_group_combobox.get_active_text()
		elif self.edit_type_subscription_radiobutton.get_active():
			edit_type = 'subscription'
			subs = ['none', 'both', 'from', 'to']
			edit_value = subs[self.edit_type_subscription_combobox.get_active()]
		elif self.edit_type_select_all_radiobutton.get_active():
			edit_type = ''
			edit_value = ''
		edit_order = str(self.edit_order_spinbutton.get_value_as_int())
		if self.edit_allow_radiobutton.get_active():
			edit_deny = 'allow'
		else:
			edit_deny = 'deny'
		child = []
		if self.edit_send_messages_checkbutton.get_active():
			child.append('message')
		if self.edit_queries_send_checkbutton.get_active():
			child.append('iq')
		if self.edit_send_status_checkbutton.get_active():
			child.append('presence-out')
		if self.edit_view_status_checkbutton.get_active():
			child.append('presence-in')
		if edit_type != '':
			return {'order': edit_order, 'action': edit_deny,
				'type': edit_type, 'value': edit_value, 'child': child}
		return {'order': edit_order, 'action': edit_deny, 'child': child}

	def on_save_rule_button_clicked(self, widget):
		tags=[]
		current_tags = self.get_current_tags()
		if self.active_rule == '':
			tags.append(current_tags)

		for rule in self.global_rules:
			if rule != self.active_rule:
				tags.append(self.global_rules[rule])
			else:
				tags.append(current_tags)

		gajim.connections[self.account].set_privacy_list(
			self.privacy_list_name, tags)
		self.refresh_rules()
		self.add_edit_vbox.hide()
		if 'privacy_lists' in gajim.interface.instances[self.account]:
			win = gajim.interface.instances[self.account]['privacy_lists']
			win.add_privacy_list_to_combobox(self.privacy_list_name)
			win.draw_widgets()

	def on_list_of_rules_combobox_changed(self, widget):
		self.add_edit_vbox.hide()

	def on_edit_type_radiobutton_changed(self, widget, radiobutton):
		active_bool = widget.get_active()
		if active_bool:
			self.edit_rule_type = radiobutton

	def on_edit_allow_radiobutton_changed(self, widget, radiobutton):
		active_bool = widget.get_active()
		if active_bool:
			self.allow_deny = radiobutton

	def on_close_button_clicked(self, widget):
		self.window.destroy()

class PrivacyListsWindow:
	'''Window that is the main window for Privacy Lists;
	we can list there the privacy lists and ask to create a new one
	or edit an already there one'''
	def __init__(self, account):
		self.account = account
		self.privacy_lists_save = []

		self.xml = gtkgui_helpers.get_glade('privacy_lists_window.glade')

		self.window = self.xml.get_widget('privacy_lists_first_window')
		for widget_to_add in ('list_of_privacy_lists_combobox',
		'delete_privacy_list_button', 'open_privacy_list_button',
		'new_privacy_list_button', 'new_privacy_list_entry',
		'privacy_lists_refresh_button', 'close_privacy_lists_window_button'):
			self.__dict__[widget_to_add] = self.xml.get_widget(
				widget_to_add)

		self.draw_privacy_lists_in_combobox([])
		self.privacy_lists_refresh()

		self.enabled = True

		if len(gajim.connections) > 1:
			title = _('Privacy Lists for %s') % self.account
		else:
			title = _('Privacy Lists')

		self.window.set_title(title)

		self.window.show_all()

		self.xml.signal_autoconnect(self)

	def on_privacy_lists_first_window_destroy(self, widget):
		if 'privacy_lists' in gajim.interface.instances[self.account]:
			del gajim.interface.instances[self.account]['privacy_lists']

	def remove_privacy_list_from_combobox(self, privacy_list):
		if privacy_list not in self.privacy_lists_save:
			return
		privacy_list_index = self.privacy_lists_save.index(privacy_list)
		self.list_of_privacy_lists_combobox.remove_text(privacy_list_index)
		self.privacy_lists_save.remove(privacy_list)

	def add_privacy_list_to_combobox(self, privacy_list):
		if privacy_list in self.privacy_lists_save:
			return
		self.list_of_privacy_lists_combobox.append_text(privacy_list)
		self.privacy_lists_save.append(privacy_list)

	def draw_privacy_lists_in_combobox(self, privacy_lists):
		self.list_of_privacy_lists_combobox.set_active(-1)
		self.list_of_privacy_lists_combobox.get_model().clear()
		self.privacy_lists_save = []
		for add_item in privacy_lists:
			self.add_privacy_list_to_combobox(add_item)
		self.draw_widgets()

	def draw_widgets(self):
		if len(self.privacy_lists_save) == 0:
			self.list_of_privacy_lists_combobox.set_sensitive(False)
			self.open_privacy_list_button.set_sensitive(False)
			self.delete_privacy_list_button.set_sensitive(False)
		else:
			self.list_of_privacy_lists_combobox.set_sensitive(True)
			self.list_of_privacy_lists_combobox.set_active(0)
			self.open_privacy_list_button.set_sensitive(True)
			self.delete_privacy_list_button.set_sensitive(True)

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_delete_privacy_list_button_clicked(self, widget):
		active_list = self.privacy_lists_save[
			self.list_of_privacy_lists_combobox.get_active()]
		gajim.connections[self.account].del_privacy_list(active_list)

	def privacy_list_removed(self, active_list):
		self.privacy_lists_save.remove(active_list)
		self.privacy_lists_received({'lists': self.privacy_lists_save})

	def privacy_lists_received(self, lists):
		if not lists:
			return
		privacy_lists = []
		for privacy_list in lists['lists']:
			privacy_lists.append(privacy_list)
		self.draw_privacy_lists_in_combobox(privacy_lists)

	def privacy_lists_refresh(self):
		gajim.connections[self.account].get_privacy_lists()

	def on_new_privacy_list_button_clicked(self, widget):
		name = self.new_privacy_list_entry.get_text()
		if not name:
			ErrorDialog(_('Invalid List Name'),
				_('You must enter a name to create a privacy list.'))
			return
		key_name = 'privacy_list_%s' % name
		if key_name in gajim.interface.instances[self.account]:
			gajim.interface.instances[self.account][key_name].window.present()
		else:
			gajim.interface.instances[self.account][key_name] = \
				PrivacyListWindow(self.account, name, 'NEW')
		self.new_privacy_list_entry.set_text('')

	def on_privacy_lists_refresh_button_clicked(self, widget):
		self.privacy_lists_refresh()

	def on_open_privacy_list_button_clicked(self, widget):
		name = self.privacy_lists_save[
			self.list_of_privacy_lists_combobox.get_active()]
		key_name = 'privacy_list_%s' % name
		if key_name in gajim.interface.instances[self.account]:
			gajim.interface.instances[self.account][key_name].window.present()
		else:
			gajim.interface.instances[self.account][key_name] = \
				PrivacyListWindow(self.account, name, 'EDIT')

class InvitationReceivedDialog:
	def __init__(self, account, room_jid, contact_jid, password=None,
	comment=None, is_continued=False):

		self.room_jid = room_jid
		self.account = account
		self.password = password
		self.is_continued = is_continued

		pritext = _('''You are invited to a groupchat''')
		#Don't translate $Contact
		if is_continued:
			sectext = _('$Contact has invited you to join a discussion')
		else:
			sectext = _('$Contact has invited you to group chat %(room_jid)s')\
				% {'room_jid': room_jid}
		contact = gajim.contacts.get_first_contact_from_jid(account, contact_jid)
		contact_text = contact and contact.name or contact_jid
		sectext = sectext.replace('$Contact', contact_text)

		if comment: # only if not None and not ''
			comment = gobject.markup_escape_text(comment)
			comment = _('Comment: %s') % comment
			sectext += '\n\n%s' % comment
		sectext += '\n\n' + _('Do you want to accept the invitation?')

		def on_yes(checked):
			try:
				if self.is_continued:
					gajim.interface.join_gc_room(self.account, self.room_jid,
						gajim.nicks[self.account], None, is_continued=True)
				else:
					JoinGroupchatWindow(self.account, self.room_jid)
			except GajimGeneralException:
				pass

		YesNoDialog(pritext, sectext, on_response_yes=on_yes)

class ProgressDialog:
	def __init__(self, title_text, during_text, messages_queue):
		'''during text is what to show during the procedure,
		messages_queue has the message to show
		in the textview'''
		self.xml = gtkgui_helpers.get_glade('progress_dialog.glade')
		self.dialog = self.xml.get_widget('progress_dialog')
		self.label = self.xml.get_widget('label')
		self.label.set_markup('<big>' + during_text + '</big>')
		self.progressbar = self.xml.get_widget('progressbar')
		self.dialog.set_title(title_text)
		self.dialog.set_default_size(450, 250)
		self.dialog.show_all()
		self.xml.signal_autoconnect(self)

		self.update_progressbar_timeout_id = gobject.timeout_add(100,
					self.update_progressbar)

	def update_progressbar(self):
		if self.dialog:
			self.progressbar.pulse()
			return True # loop forever
		return False

	def on_progress_dialog_delete_event(self, widget, event):
		return True # WM's X button or Escape key should not destroy the window


class SoundChooserDialog(FileChooserDialog):
	def __init__(self, path_to_snd_file='', on_response_ok=None,
	on_response_cancel=None):
		'''optionally accepts path_to_snd_file so it has that as selected'''
		def on_ok(widget, callback):
			'''check if file exists and call callback'''
			path_to_snd_file = self.get_filename()
			path_to_snd_file = gtkgui_helpers.decode_filechooser_file_paths(
				(path_to_snd_file,))[0]
			if os.path.exists(path_to_snd_file):
				callback(widget, path_to_snd_file)

		FileChooserDialog.__init__(self,
			title_text = _('Choose Sound'),
			action = gtk.FILE_CHOOSER_ACTION_OPEN,
			buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
				gtk.STOCK_OPEN, gtk.RESPONSE_OK),
			default_response = gtk.RESPONSE_OK,
			current_folder = gajim.config.get('last_sounds_dir'),
			on_response_ok = (on_ok, on_response_ok),
			on_response_cancel = on_response_cancel)

		filter_ = gtk.FileFilter()
		filter_.set_name(_('All files'))
		filter_.add_pattern('*')
		self.add_filter(filter_)

		filter_ = gtk.FileFilter()
		filter_.set_name(_('Wav Sounds'))
		filter_.add_pattern('*.wav')
		self.add_filter(filter_)
		self.set_filter(filter_)

		if path_to_snd_file:
			self.set_filename(path_to_snd_file)

class ImageChooserDialog(FileChooserDialog):
	def __init__(self, path_to_file='', on_response_ok=None,
	on_response_cancel=None):
		'''optionally accepts path_to_snd_file so it has that as selected'''
		def on_ok(widget, callback):
			'''check if file exists and call callback'''
			path_to_file = self.get_filename()
			if not path_to_file:
				return
			path_to_file = gtkgui_helpers.decode_filechooser_file_paths(
				(path_to_file,))[0]
			if os.path.exists(path_to_file):
				if isinstance(callback, tuple):
					callback[0](widget, path_to_file, *callback[1:])
				else:
					callback(widget, path_to_file)

		try:
			if os.name == 'nt':
				path = helpers.get_my_pictures_path()
			else:
				path = os.environ['HOME']
		except Exception:
			path = ''
		FileChooserDialog.__init__(self,
			title_text = _('Choose Image'),
			action = gtk.FILE_CHOOSER_ACTION_OPEN,
			buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
				gtk.STOCK_OPEN, gtk.RESPONSE_OK),
			default_response = gtk.RESPONSE_OK,
			current_folder = path,
			on_response_ok = (on_ok, on_response_ok),
			on_response_cancel = on_response_cancel)

		if on_response_cancel:
			self.connect('destroy', on_response_cancel)

		filter_ = gtk.FileFilter()
		filter_.set_name(_('All files'))
		filter_.add_pattern('*')
		self.add_filter(filter_)

		filter_ = gtk.FileFilter()
		filter_.set_name(_('Images'))
		filter_.add_mime_type('image/png')
		filter_.add_mime_type('image/jpeg')
		filter_.add_mime_type('image/gif')
		filter_.add_mime_type('image/tiff')
		filter_.add_mime_type('image/svg+xml')
		filter_.add_mime_type('image/x-xpixmap') # xpm
		self.add_filter(filter_)
		self.set_filter(filter_)

		if path_to_file:
			self.set_filename(path_to_file)

		self.set_use_preview_label(False)
		self.set_preview_widget(gtk.Image())
		self.connect('selection-changed', self.update_preview)

	def update_preview(self, widget):
		path_to_file = widget.get_preview_filename()
		if path_to_file is None or os.path.isdir(path_to_file):
			# nothing to preview or directory
			# make sure you clean image do show nothing
			widget.get_preview_widget().set_from_file(None)
			return
		try:
			pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(path_to_file, 100, 100)
		except gobject.GError:
			return
		widget.get_preview_widget().set_from_pixbuf(pixbuf)

class AvatarChooserDialog(ImageChooserDialog):
	def __init__(self, path_to_file='', on_response_ok=None,
	on_response_cancel=None, on_response_clear=None):
		ImageChooserDialog.__init__(self, path_to_file, on_response_ok,
			on_response_cancel)
		button = gtk.Button(None, gtk.STOCK_CLEAR)
		self.response_clear = on_response_clear
		if on_response_clear:
			button.connect('clicked', self.on_clear)
		button.show_all()
		self.action_area.pack_start(button)
		self.action_area.reorder_child(button, 0)

	def on_clear(self, widget):
		if isinstance(self.response_clear, tuple):
			self.response_clear[0](widget, *self.response_clear[1:])
		else:
			self.response_clear(widget)

class AddSpecialNotificationDialog:
	def __init__(self, jid):
		'''jid is the jid for which we want to add special notification
		(sound and notification popups)'''
		self.xml = gtkgui_helpers.get_glade('add_special_notification_window.glade')
		self.window = self.xml.get_widget('add_special_notification_window')
		self.condition_combobox = self.xml.get_widget('condition_combobox')
		self.condition_combobox.set_active(0)
		self.notification_popup_yes_no_combobox = self.xml.get_widget(
			'notification_popup_yes_no_combobox')
		self.notification_popup_yes_no_combobox.set_active(0)
		self.listen_sound_combobox = self.xml.get_widget('listen_sound_combobox')
		self.listen_sound_combobox.set_active(0)

		self.jid = jid
		self.xml.get_widget('when_foo_becomes_label').set_text(
			_('When %s becomes:') % self.jid)

		self.window.set_title(_('Adding Special Notification for %s') % jid)
		self.window.show_all()
		self.xml.signal_autoconnect(self)

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def on_add_special_notification_window_delete_event(self, widget, event):
		self.window.destroy()

	def on_listen_sound_combobox_changed(self, widget):
		active = widget.get_active()
		if active == 1: # user selected 'choose sound'
			def on_ok(widget, path_to_snd_file):
				pass
				#print path_to_snd_file

			def on_cancel(widget):
				widget.set_active(0) # go back to No Sound

			self.dialog = SoundChooserDialog(on_response_ok=on_ok,
				on_response_cancel=on_cancel)

	def on_ok_button_clicked(self, widget):
		conditions = ('online', 'chat', 'online_and_chat',
			'away', 'xa', 'away_and_xa', 'dnd', 'xa_and_dnd', 'offline')
		active = self.condition_combobox.get_active()

		active_iter = self.listen_sound_combobox.get_active_iter()
		listen_sound_model = self.listen_sound_combobox.get_model()

class AdvancedNotificationsWindow:
	events_list = ['message_received', 'contact_connected',
		'contact_disconnected', 'contact_change_status', 'gc_msg_highlight',
		'gc_msg', 'ft_request', 'ft_started', 'ft_finished']
	recipient_types_list = ['contact', 'group', 'all']
	config_options = ['event', 'recipient_type', 'recipients', 'status',
		'tab_opened', 'sound', 'sound_file', 'popup', 'auto_open',
		'run_command', 'command', 'systray', 'roster', 'urgency_hint']
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('advanced_notifications_window.glade')
		self.window = self.xml.get_widget('advanced_notifications_window')
		for w in ('conditions_treeview', 'config_vbox', 'event_combobox',
		'recipient_type_combobox', 'recipient_list_entry', 'delete_button',
		'status_hbox', 'use_sound_cb', 'disable_sound_cb', 'use_popup_cb',
		'disable_popup_cb', 'use_auto_open_cb', 'disable_auto_open_cb',
		'use_systray_cb', 'disable_systray_cb', 'use_roster_cb',
		'disable_roster_cb', 'tab_opened_cb', 'not_tab_opened_cb',
		'sound_entry', 'sound_file_hbox', 'up_button', 'down_button',
		'run_command_cb', 'command_entry', 'urgency_hint_cb'):
			self.__dict__[w] = self.xml.get_widget(w)

		# Contains status checkboxes
		childs = self.status_hbox.get_children()

		self.all_status_rb = childs[0]
		self.special_status_rb = childs[1]
		self.online_cb = childs[2]
		self.away_cb = childs[3]
		self.xa_cb = childs[4]
		self.dnd_cb = childs[5]
		self.invisible_cb = childs[6]

		model = gtk.ListStore(int, str)
		model.set_sort_column_id(0, gtk.SORT_ASCENDING)
		model.clear()
		self.conditions_treeview.set_model(model)

		## means number
		col = gtk.TreeViewColumn(_('#'))
		self.conditions_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand=False)
		col.set_attributes(renderer, text=0)

		col = gtk.TreeViewColumn(_('Condition'))
		self.conditions_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand=True)
		col.set_attributes(renderer, text=1)

		self.xml.signal_autoconnect(self)

		# Fill conditions_treeview
		num = 0
		while gajim.config.get_per('notifications', str(num)):
			iter_ = model.append((num, ''))
			path = model.get_path(iter_)
			self.conditions_treeview.set_cursor(path)
			self.active_num = num
			self.initiate_rule_state()
			self.set_treeview_string()
			num += 1

		# No rule selected at init time
		self.conditions_treeview.get_selection().unselect_all()
		self.active_num = -1
		self.config_vbox.set_sensitive(False)
		self.delete_button.set_sensitive(False)
		self.down_button.set_sensitive(False)
		self.up_button.set_sensitive(False)

		self.window.show_all()

	def initiate_rule_state(self):
		'''Set values for all widgets'''
		if self.active_num < 0:
			return
		# event
		value = gajim.config.get_per('notifications', str(self.active_num),
			'event')
		if value:
			self.event_combobox.set_active(self.events_list.index(value))
		else:
			self.event_combobox.set_active(-1)
		# recipient_type
		value = gajim.config.get_per('notifications', str(self.active_num),
			'recipient_type')
		if value:
			self.recipient_type_combobox.set_active(
				self.recipient_types_list.index(value))
		else:
			self.recipient_type_combobox.set_active(-1)
		# recipient
		value = gajim.config.get_per('notifications', str(self.active_num),
			'recipients')
		if not value:
			value = ''
		self.recipient_list_entry.set_text(value)
		# status
		value = gajim.config.get_per('notifications', str(self.active_num),
			'status')
		if value == 'all':
			self.all_status_rb.set_active(True)
		else:
			self.special_status_rb.set_active(True)
			values = value.split()
			for v in ('online', 'away', 'xa', 'dnd', 'invisible'):
				if v in values:
					self.__dict__[v + '_cb'].set_active(True)
				else:
					self.__dict__[v + '_cb'].set_active(False)
		self.on_status_radiobutton_toggled(self.all_status_rb)
		# tab_opened
		value = gajim.config.get_per('notifications', str(self.active_num),
			'tab_opened')
		self.tab_opened_cb.set_active(True)
		self.not_tab_opened_cb.set_active(True)
		if value == 'no':
			self.tab_opened_cb.set_active(False)
		elif value == 'yes':
			self.not_tab_opened_cb.set_active(False)
		# sound_file
		value = gajim.config.get_per('notifications', str(self.active_num),
			'sound_file')
		self.sound_entry.set_text(value)
		# sound, popup, auto_open, systray, roster
		for option in ('sound', 'popup', 'auto_open', 'systray', 'roster'):
			value = gajim.config.get_per('notifications', str(self.active_num),
				option)
			if value == 'yes':
				self.__dict__['use_' + option + '_cb'].set_active(True)
			else:
				self.__dict__['use_' + option + '_cb'].set_active(False)
			if value == 'no':
				self.__dict__['disable_' + option + '_cb'].set_active(True)
			else:
				self.__dict__['disable_' + option + '_cb'].set_active(False)
		# run_command
		value = gajim.config.get_per('notifications', str(self.active_num),
			'run_command')
		self.run_command_cb.set_active(value)
		# command
		value = gajim.config.get_per('notifications', str(self.active_num),
			'command')
		self.command_entry.set_text(value)
		# urgency_hint
		value = gajim.config.get_per('notifications', str(self.active_num),
			'urgency_hint')
		self.urgency_hint_cb.set_active(value)

	def set_treeview_string(self):
		(model, iter_) = self.conditions_treeview.get_selection().get_selected()
		if not iter_:
			return
		event = self.event_combobox.get_active_text()
		recipient_type = self.recipient_type_combobox.get_active_text()
		recipient = ''
		if recipient_type != 'everybody':
			recipient = self.recipient_list_entry.get_text()
		if self.all_status_rb.get_active():
			status = ''
		else:
			status = _('when I am ')
			for st in ('online', 'away', 'xa', 'dnd', 'invisible'):
				if self.__dict__[st + '_cb'].get_active():
					status += helpers.get_uf_show(st) + ' '
		model[iter_][1] = "When %s for %s %s %s" % (event, recipient_type,
			recipient, status)

	def on_conditions_treeview_cursor_changed(self, widget):
		(model, iter_) = widget.get_selection().get_selected()
		if not iter_:
			self.active_num = -1
			return
		self.active_num = model[iter_][0]
		if self.active_num == 0:
			self.up_button.set_sensitive(False)
		else:
			self.up_button.set_sensitive(True)
		max = self.conditions_treeview.get_model().iter_n_children(None)
		if self.active_num == max - 1:
			self.down_button.set_sensitive(False)
		else:
			self.down_button.set_sensitive(True)
		self.initiate_rule_state()
		self.config_vbox.set_sensitive(True)
		self.delete_button.set_sensitive(True)

	def on_new_button_clicked(self, widget):
		model = self.conditions_treeview.get_model()
		num = self.conditions_treeview.get_model().iter_n_children(None)
		gajim.config.add_per('notifications', str(num))
		iter_ = model.append((num, ''))
		path = model.get_path(iter_)
		self.conditions_treeview.set_cursor(path)
		self.active_num = num
		self.set_treeview_string()
		self.config_vbox.set_sensitive(True)

	def on_delete_button_clicked(self, widget):
		(model, iter_) = self.conditions_treeview.get_selection().get_selected()
		if not iter_:
			return
		# up all others
		iter2 = model.iter_next(iter_)
		num = self.active_num
		while iter2:
			num = model[iter2][0]
			model[iter2][0] = num - 1
			for opt in self.config_options:
				val = gajim.config.get_per('notifications', str(num), opt)
				gajim.config.set_per('notifications', str(num - 1), opt, val)
			iter2 = model.iter_next(iter2)
		model.remove(iter_)
		gajim.config.del_per('notifications', str(num)) # delete latest
		self.active_num = -1
		self.config_vbox.set_sensitive(False)
		self.delete_button.set_sensitive(False)
		self.up_button.set_sensitive(False)
		self.down_button.set_sensitive(False)

	def on_up_button_clicked(self, widget):
		(model, iter_) = self.conditions_treeview.get_selection().\
			get_selected()
		if not iter_:
			return
		for opt in self.config_options:
			val = gajim.config.get_per('notifications', str(self.active_num), opt)
			val2 = gajim.config.get_per('notifications', str(self.active_num - 1),
				opt)
			gajim.config.set_per('notifications', str(self.active_num), opt, val2)
			gajim.config.set_per('notifications', str(self.active_num - 1), opt,
				val)

		model[iter_][0] = self.active_num - 1
		# get previous iter
		path = model.get_path(iter_)
		iter_ = model.get_iter((path[0] - 1,))
		model[iter_][0] = self.active_num
		self.on_conditions_treeview_cursor_changed(self.conditions_treeview)

	def on_down_button_clicked(self, widget):
		(model, iter_) = self.conditions_treeview.get_selection().get_selected()
		if not iter_:
			return
		for opt in self.config_options:
			val = gajim.config.get_per('notifications', str(self.active_num), opt)
			val2 = gajim.config.get_per('notifications', str(self.active_num + 1),
				opt)
			gajim.config.set_per('notifications', str(self.active_num), opt, val2)
			gajim.config.set_per('notifications', str(self.active_num + 1), opt,
				val)

		model[iter_][0] = self.active_num + 1
		iter_ = model.iter_next(iter_)
		model[iter_][0] = self.active_num
		self.on_conditions_treeview_cursor_changed(self.conditions_treeview)

	def on_event_combobox_changed(self, widget):
		if self.active_num < 0:
			return
		active = self.event_combobox.get_active()
		if active == -1:
			event = ''
		else:
			event = self.events_list[active]
		gajim.config.set_per('notifications', str(self.active_num), 'event',
			event)
		self.set_treeview_string()

	def on_recipient_type_combobox_changed(self, widget):
		if self.active_num < 0:
			return
		recipient_type = self.recipient_types_list[self.recipient_type_combobox.\
			get_active()]
		gajim.config.set_per('notifications', str(self.active_num),
			'recipient_type', recipient_type)
		if recipient_type == 'all':
			self.recipient_list_entry.hide()
		else:
			self.recipient_list_entry.show()
		self.set_treeview_string()

	def on_recipient_list_entry_changed(self, widget):
		if self.active_num < 0:
			return
		recipients = widget.get_text().decode('utf-8')
		#TODO: do some check
		gajim.config.set_per('notifications', str(self.active_num),
			'recipients', recipients)
		self.set_treeview_string()

	def set_status_config(self):
		if self.active_num < 0:
			return
		status = ''
		for st in ('online', 'away', 'xa', 'dnd', 'invisible'):
			if self.__dict__[st + '_cb'].get_active():
				status += st + ' '
		if status:
			status = status[:-1]
		gajim.config.set_per('notifications', str(self.active_num), 'status',
			status)
		self.set_treeview_string()

	def on_status_radiobutton_toggled(self, widget):
		if self.active_num < 0:
			return
		if self.all_status_rb.get_active():
			gajim.config.set_per('notifications', str(self.active_num), 'status',
				'all')
			# 'All status' clicked
			for st in ('online', 'away', 'xa', 'dnd', 'invisible'):
				self.__dict__[st + '_cb'].hide()

			self.special_status_rb.show()
		else:
			self.set_status_config()
			# 'special status' clicked
			for st in ('online', 'away', 'xa', 'dnd', 'invisible'):
				self.__dict__[st + '_cb'].show()

			self.special_status_rb.hide()
		self.set_treeview_string()

	def on_status_cb_toggled(self, widget):
		if self.active_num < 0:
			return
		self.set_status_config()

	# tab_opened OR (not xor) not_tab_opened must be active
	def on_tab_opened_cb_toggled(self, widget):
		if self.active_num < 0:
			return
		if self.tab_opened_cb.get_active():
			if self.not_tab_opened_cb.get_active():
				gajim.config.set_per('notifications', str(self.active_num),
					'tab_opened', 'both')
			else:
				gajim.config.set_per('notifications', str(self.active_num),
					'tab_opened', 'yes')
		elif not self.not_tab_opened_cb.get_active():
			self.not_tab_opened_cb.set_active(True)
			gajim.config.set_per('notifications', str(self.active_num),
				'tab_opened', 'no')

	def on_not_tab_opened_cb_toggled(self, widget):
		if self.active_num < 0:
			return
		if self.not_tab_opened_cb.get_active():
			if self.tab_opened_cb.get_active():
				gajim.config.set_per('notifications', str(self.active_num),
					'tab_opened', 'both')
			else:
				gajim.config.set_per('notifications', str(self.active_num),
					'tab_opened', 'no')
		elif not self.tab_opened_cb.get_active():
			self.tab_opened_cb.set_active(True)
			gajim.config.set_per('notifications', str(self.active_num),
				'tab_opened', 'yes')

	def on_use_it_toggled(self, widget, oposite_widget, option):
		if widget.get_active():
			if oposite_widget.get_active():
				oposite_widget.set_active(False)
			gajim.config.set_per('notifications', str(self.active_num), option,
				'yes')
		elif oposite_widget.get_active():
			gajim.config.set_per('notifications', str(self.active_num), option,
				'no')
		else:
			gajim.config.set_per('notifications', str(self.active_num), option, '')

	def on_disable_it_toggled(self, widget, oposite_widget, option):
		if widget.get_active():
			if oposite_widget.get_active():
				oposite_widget.set_active(False)
			gajim.config.set_per('notifications', str(self.active_num), option,
				'no')
		elif oposite_widget.get_active():
			gajim.config.set_per('notifications', str(self.active_num), option,
				'yes')
		else:
			gajim.config.set_per('notifications', str(self.active_num), option, '')

	def on_use_sound_cb_toggled(self, widget):
		self.on_use_it_toggled(widget, self.disable_sound_cb, 'sound')
		if widget.get_active():
			self.sound_file_hbox.set_sensitive(True)
		else:
			self.sound_file_hbox.set_sensitive(False)

	def on_browse_for_sounds_button_clicked(self, widget, data=None):
		if self.active_num < 0:
			return

		def on_ok(widget, path_to_snd_file):
			dialog.destroy()
			if not path_to_snd_file:
				path_to_snd_file = ''
			gajim.config.set_per('notifications', str(self.active_num),
				'sound_file', path_to_snd_file)
			self.sound_entry.set_text(path_to_snd_file)

		path_to_snd_file = self.sound_entry.get_text().decode('utf-8')
		path_to_snd_file = os.path.join(os.getcwd(), path_to_snd_file)
		dialog = SoundChooserDialog(path_to_snd_file, on_ok)

	def on_play_button_clicked(self, widget):
		helpers.play_sound_file(self.sound_entry.get_text().decode('utf-8'))

	def on_disable_sound_cb_toggled(self, widget):
		self.on_disable_it_toggled(widget, self.use_sound_cb, 'sound')

	def on_sound_entry_changed(self, widget):
		gajim.config.set_per('notifications', str(self.active_num),
			'sound_file', widget.get_text().decode('utf-8'))

	def on_use_popup_cb_toggled(self, widget):
		self.on_use_it_toggled(widget, self.disable_popup_cb, 'popup')

	def on_disable_popup_cb_toggled(self, widget):
		self.on_disable_it_toggled(widget, self.use_popup_cb, 'popup')

	def on_use_auto_open_cb_toggled(self, widget):
		self.on_use_it_toggled(widget, self.disable_auto_open_cb, 'auto_open')

	def on_disable_auto_open_cb_toggled(self, widget):
		self.on_disable_it_toggled(widget, self.use_auto_open_cb, 'auto_open')

	def on_run_command_cb_toggled(self, widget):
		gajim.config.set_per('notifications', str(self.active_num), 'run_command',
			widget.get_active())
		if widget.get_active():
			self.command_entry.set_sensitive(True)
		else:
			self.command_entry.set_sensitive(False)

	def on_command_entry_changed(self, widget):
		gajim.config.set_per('notifications', str(self.active_num), 'command',
			widget.get_text().decode('utf-8'))

	def on_use_systray_cb_toggled(self, widget):
		self.on_use_it_toggled(widget, self.disable_systray_cb, 'systray')

	def on_disable_systray_cb_toggled(self, widget):
		self.on_disable_it_toggled(widget, self.use_systray_cb, 'systray')

	def on_use_roster_cb_toggled(self, widget):
		self.on_use_it_toggled(widget, self.disable_roster_cb, 'roster')

	def on_disable_roster_cb_toggled(self, widget):
		self.on_disable_it_toggled(widget, self.use_roster_cb, 'roster')

	def on_urgency_hint_cb_toggled(self, widget):
		gajim.config.set_per('notifications', str(self.active_num),
			'uregency_hint', widget.get_active())

	def on_close_window(self, widget):
		self.window.destroy()

class TransformChatToMUC:
	# Keep a reference on windows so garbage collector don't restroy them
	instances = []
	def __init__(self, account, jids, preselected=None):
		'''This window is used to trasform a one-to-one chat to a MUC.
		We do 2 things: first select the server and then make a guests list.'''

		self.instances.append(self)
		self.account = account
		self.auto_jids = jids
		self.preselected_jids = preselected

		self.xml = gtkgui_helpers.get_glade('chat_to_muc_window.glade')
		self.window = self.xml.get_widget('chat_to_muc_window')

		for widget_to_add in ('invite_button', 'cancel_button',
		'server_list_comboboxentry', 'guests_treeview',
		'server_and_guests_hseparator', 'server_select_label'):
			self.__dict__[widget_to_add] = self.xml.get_widget(widget_to_add)

		server_list = []
		self.servers = gtk.ListStore(str)
		self.server_list_comboboxentry.set_model(self.servers)

		self.server_list_comboboxentry.set_text_column(0)

		# get the muc server of our server
		if 'jabber' in gajim.connections[account].muc_jid:
			server_list.append(gajim.connections[account].muc_jid['jabber'])
		# add servers or recently joined groupchats
		recently_groupchat = gajim.config.get('recently_groupchat').split()
		for g in recently_groupchat:
			server = gajim.get_server_from_jid(g)
			if server not in server_list and not server.startswith('irc'):
				server_list.append(server)
		# add a default server
		if not server_list:
			server_list.append('conference.jabber.org')

		for s in server_list:
			self.servers.append([s])

		self.server_list_comboboxentry.set_active(0)

		# set treeview
		# name, jid
		self.store = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
		self.store.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.guests_treeview.set_model(self.store)

		renderer1 = gtk.CellRendererText()
		renderer2 = gtk.CellRendererPixbuf()
		column = gtk.TreeViewColumn('Status', renderer2, pixbuf=0)
		self.guests_treeview.append_column(column)
		column = gtk.TreeViewColumn('Name', renderer1, text=1)
		self.guests_treeview.append_column(column)

		self.guests_treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

		# All contacts beside the following can be invited:
		# 	transports, zeroconf contacts, minimized groupchats
		def invitable(contact, contact_transport=None):
			return (contact.jid not in self.auto_jids and
			contact.jid != gajim.get_jid_from_account(self.account) and
			contact.jid not in gajim.interface.minimized_controls[account] and
			not contact.is_transport() and
			not contact_transport)

		# set jabber id and pseudos
		for account in gajim.contacts.get_accounts():
			if gajim.connections[account].is_zeroconf:
				continue
			for jid in gajim.contacts.get_jid_list(account):
				contact = \
					gajim.contacts.get_contact_with_highest_priority(account, jid)
				contact_transport = gajim.get_transport_name_from_jid(jid)
				# Add contact if it can be invited
				if invitable(contact, contact_transport) and \
						contact.show not in ('offline', 'error'):
					img = gajim.interface.jabber_state_images['16'][contact.show]
					name = contact.name
					if name == '':
						name = jid.split('@')[0]
					iter_ = self.store.append([img.get_pixbuf(), name, jid])
					# preselect treeview rows
					if self.preselected_jids and jid in self.preselected_jids:
						path = self.store.get_path(iter_)
						self.guests_treeview.get_selection().\
							select_path(path)

		# show all
		self.window.show_all()

		self.xml.signal_autoconnect(self)

	def on_chat_to_muc_window_destroy(self, widget):
		self.instances.remove(self)

	def on_chat_to_muc_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.destroy()

	def on_invite_button_clicked(self, widget):
		server = self.server_list_comboboxentry.get_active_text()
		if server == '':
			return
		gajim.connections[self.account].check_unique_room_id_support(server, self)

	def unique_room_id_supported(self, server, room_id):
		guest_list = []
		guests = self.guests_treeview.get_selection().get_selected_rows()
		for guest in guests[1]:
			iter_ = self.store.get_iter(guest)
			guest_list.append(self.store[iter_][2].decode('utf-8'))
		for guest in self.auto_jids:
			guest_list.append(guest)
		room_jid = room_id + '@' + server
		gajim.automatic_rooms[self.account][room_jid] = {}
		gajim.automatic_rooms[self.account][room_jid]['invities'] = guest_list
		gajim.automatic_rooms[self.account][room_jid]['continue_tag'] = True
		gajim.interface.join_gc_room(self.account, room_jid,
			gajim.nicks[self.account], None, is_continued=True)
		self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def unique_room_id_error(self, server):
		self.unique_room_id_supported(server,
			gajim.nicks[self.account].lower().replace(' ','') + str(randrange(
				9999999)))

class DataFormWindow(Dialog):
	def __init__(self, form, on_response_ok):
		self.df_response_ok = on_response_ok
		Dialog.__init__(self, None, 'test', [(gtk.STOCK_CANCEL,
			gtk.RESPONSE_REJECT), (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)],
			on_response_ok=self.on_ok)
		self.set_resizable(True)
		gtkgui_helpers.resize_window(self, 600, 400)
		self.dataform_widget =  dataforms_widget.DataFormWidget()
		self.dataform = dataforms.ExtendForm(node=form)
		self.dataform_widget.set_sensitive(True)
		self.dataform_widget.data_form = self.dataform
		self.dataform_widget.show_all()
		self.vbox.pack_start(self.dataform_widget)

	def on_ok(self):
		form = self.dataform_widget.data_form
		if isinstance(self.df_response_ok, tuple):
			self.df_response_ok[0](form, *self.df_response_ok[1:])
		else:
			self.df_response_ok(form)
		self.destroy()

class ESessionInfoWindow:
	'''Class for displaying information about a XEP-0116 encrypted session'''
	def __init__(self, session):
		self.session = session

		self.xml = gtkgui_helpers.get_glade('esession_info_window.glade')
		self.xml.signal_autoconnect(self)

		self.security_image = self.xml.get_widget('security_image')
		self.verify_now_button = self.xml.get_widget('verify_now_button')
		self.button_label = self.xml.get_widget('button_label')
		self.window = self.xml.get_widget('esession_info_window')
		self.update_info()


		self.window.show_all()

	def update_info(self):
		labeltext = _('''Your chat session with <b>%(jid)s</b> is encrypted.\n\nThis session's Short Authentication String is <b>%(sas)s</b>.''') % {'jid': self.session.jid, 'sas': self.session.sas}
		dir_ = os.path.join(gajim.DATA_DIR, 'pixmaps')

		if self.session.verified_identity:
			labeltext += '\n\n' + _('''You have already verified this contact's identity.''')
			security_image = 'security-high-big.png'
			if self.session.control:
				self.session.control._show_lock_image(True, 'E2E', True,
					self.session.is_loggable(), True)

			verification_status = _('''Contact's identity verified''')
			self.window.set_title(verification_status)
			self.xml.get_widget('verification_status_label').set_markup(
				'<b><span size="x-large">' +
				verification_status +
				'</span></b>')

			self.xml.get_widget('dialog-action_area1').set_no_show_all(True)
			self.button_label.set_text(_('Verify again...'))
		else:
			if self.session.control:
				self.session.control._show_lock_image(True, 'E2E', True,
					self.session.is_loggable(), False)
			labeltext += '\n\n' + _('''To be certain that <b>only</b> the expected person can read your messages or send you messages, you need to verify their identity by clicking the button below.''')
			security_image = 'security-low-big.png'

			verification_status = _('''Contact's identity NOT verified''')
			self.window.set_title(verification_status)
			self.xml.get_widget('verification_status_label').set_markup(
				'<b><span size="x-large">' +
				verification_status +
				'</span></b>')

			self.button_label.set_text(_('Verify...'))

		path = os.path.join(dir_, security_image)
		filename = os.path.abspath(path)
		self.security_image.set_from_file(filename)

		self.xml.get_widget('info_display').set_markup(labeltext)

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_verify_now_button_clicked(self, widget):
		pritext = _('''Have you verified the contact's identity?''')
		sectext = _('''To prevent talking to an unknown person, you should speak to <b>%(jid)s</b> directly (in person or on the phone) and verify that they see the same Short Authentication String (SAS) as you.\n\nThis session's Short Authentication String is <b>%(sas)s</b>.''') % {'jid': self.session.jid, 'sas': self.session.sas}
		sectext += '\n\n' + _('Did you talk to the remote contact and verify the SAS?')

		def on_yes(checked):
			self.session._verified_srs_cb()
			self.session.verified_identity = True
			self.update_info()

		def on_no():
			self.session._unverified_srs_cb()
			self.session.verified_identity = False
			self.update_info()

		YesNoDialog(pritext, sectext, on_response_yes=on_yes, on_response_no=on_no)

class GPGInfoWindow:
	'''Class for displaying information about a XEP-0116 encrypted session'''
	def __init__(self, control):
		xml = gtkgui_helpers.get_glade('esession_info_window.glade')
		security_image = xml.get_widget('security_image')
		status_label = xml.get_widget('verification_status_label')
		info_label = xml.get_widget('info_display')
		verify_now_button = xml.get_widget('verify_now_button')
		self.window = xml.get_widget('esession_info_window')
		account = control.account
		keyID = control.contact.keyID
		error = None

		verify_now_button.set_no_show_all(True)
		verify_now_button.hide()

		if keyID.endswith('MISMATCH'):
			verification_status = _('''Contact's identity NOT verified''')
			info = _('The contact\'s key (%s) <b>does not match</b> the key '
				'assigned in Gajim.') % keyID[:8]
			image = 'security-low-big.png'
		elif not keyID:
			# No key assigned nor a key is used by remote contact
			verification_status = _('No GPG key assigned')
			info = _('No GPG key is assigned to this contact. So you cannot '
				'encrypt messages.')
			image = 'security-low-big.png'
		else:
			error = gajim.connections[account].gpg.encrypt('test', [keyID])[1]
			if error:
				verification_status = _('''Contact's identity NOT verified''')
				info = _('GPG key is assigned to this contact, but <b>you do not '
					'trust his key</b>, so message <b>cannot</b> be encrypted. Use '
					'your GPG client to trust this key.')
				image = 'security-low-big.png'
			else:
				verification_status = _('''Contact's identity verified''')
				info = _('GPG Key is assigned to this contact, and you trust his '
					'key, so messages will be encrypted.')
				image = 'security-high-big.png'

		status_label.set_markup('<b><span size="x-large">%s</span></b>' % \
			verification_status)
		info_label.set_markup(info)

		dir_ = os.path.join(gajim.DATA_DIR, 'pixmaps')
		path = os.path.join(dir_, image)
		filename = os.path.abspath(path)
		security_image.set_from_file(filename)

		xml.signal_autoconnect(self)
		self.window.show_all()

	def on_close_button_clicked(self, widget):
		self.window.destroy()

# vim: se ts=3:
