##	config.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
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

import gtk
import gtk.glade
import gobject
import os
import common.config
import common.sleepy

import dialogs
import cell_renderer_image
import cell_renderer_image

try:
	import gtkspell
except:
	pass

from gajim import Contact
from common import gajim
from common import connection
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'


# helper function to create #aabbcc color string
def mk_color_string(color):
	return '#' + (hex(color.red) + '0')[2:4] + \
		(hex(color.green) + '0')[2:4] + \
		(hex(color.blue) + '0')[2:4]


#---------- PreferencesWindow class -------------#
class PreferencesWindow:
	'''Class for Preferences window'''
	
	def on_preferences_window_delete_event(self, widget, event):
		self.window.hide()
		return True # do NOT destroy the window
	
	def on_close_button_clicked(self, widget):
		self.window.hide()

	def __init__(self, plugin):
		'''Initialize Preferences window'''
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'preferences_window', APP)
		self.window = self.xml.get_widget('preferences_window')
		self.plugin = plugin
		self.iconset_combobox = self.xml.get_widget('iconset_combobox')
		self.notify_on_new_message_radiobutton = self.xml.get_widget \
			('notify_on_new_message_radiobutton')
		self.popup_new_message_radiobutton = self.xml.get_widget \
			('popup_new_message_radiobutton')
		self.notify_on_signin_checkbutton = self.xml.get_widget \
			('notify_on_signin_checkbutton')
		self.notify_on_signout_checkbutton = self.xml.get_widget \
			('notify_on_signout_checkbutton')
		self.auto_popup_away_checkbutton = self.xml.get_widget \
			('auto_popup_away_checkbutton')
		self.auto_away_checkbutton = self.xml.get_widget('auto_away_checkbutton')
		self.auto_away_time_spinbutton = self.xml.get_widget \
			('auto_away_time_spinbutton')
		self.auto_xa_checkbutton = self.xml.get_widget('auto_xa_checkbutton')
		self.auto_xa_time_spinbutton = self.xml.get_widget \
			('auto_xa_time_spinbutton')
		self.trayicon_checkbutton = self.xml.get_widget('trayicon_checkbutton')
		self.notebook = self.xml.get_widget('preferences_notebook')
		
		#trayicon
		if self.plugin.systray_capabilities:
			st = gajim.config.get('trayicon')
			self.trayicon_checkbutton.set_active(st)
		else:
			if os.name == 'nt':
				self.trayicon_checkbutton.set_no_show_all(True)
			else:
				self.trayicon_checkbutton.set_sensitive(False)

		#Show roster on Gajim startup
		st = gajim.config.get('show_roster_on_startup')
		show_roster_on_startup_checkbutton = self.xml.get_widget(
			'show_roster_on_startup_checkbutton')
		if os.name == 'nt':
			show_roster_on_startup_checkbutton.set_no_show_all(True)
		else:
			if gajim.config.get('trayicon'): # allow it only when trayicon ON
				show_roster_on_startup_checkbutton.set_active(st)
			else:
				show_roster_on_startup_checkbutton.set_sensitive(False)
				show_roster_on_startup_checkbutton.set_active(st)

		#Save position
		st = gajim.config.get('saveposition')
		self.xml.get_widget('save_position_checkbutton').set_active(st)
		
		#Merge accounts
		st = gajim.config.get('mergeaccounts')
		self.xml.get_widget('merge_checkbutton').set_active(st)

		# Sort contacts by show
		st = gajim.config.get('sort_by_show')
		self.xml.get_widget('sort_by_show_checkbutton').set_active(st)

		#Use emoticons
		st = gajim.config.get('useemoticons')
		self.xml.get_widget('use_emoticons_checkbutton').set_active(st)
		self.xml.get_widget('add_remove_emoticons_button').set_sensitive(st)

		#iconset
		iconsets_list = os.listdir(os.path.join(gajim.DATA_DIR, 'iconsets'))
		# new model, image in 0, string in 1
		model = gtk.ListStore(gtk.Image, str)
		renderer_image = cell_renderer_image.CellRendererImage()
		renderer_text = gtk.CellRendererText()
		renderer_text.set_property('xpad', 5)
		self.iconset_combobox.pack_start(renderer_image, expand=False)
		self.iconset_combobox.pack_start(renderer_text, expand=True)
		self.iconset_combobox.set_attributes(renderer_text, text=1)
		self.iconset_combobox.add_attribute(renderer_image, 'image', 0)
		self.iconset_combobox.set_model(model)
		l = []
		for dir in iconsets_list:
			if dir != '.svn' and dir != 'transports':
				l.append(dir)
		if l.count == 0:
			l.append(' ')
		for i in range(len(l)):
			preview = gtk.Image()
			files = []
			files.append(os.path.join(gajim.DATA_DIR, 'iconsets', l[i], '16x16', 'online.png'))
			files.append(os.path.join(gajim.DATA_DIR, 'iconsets', l[i], '16x16', 'online.gif'))
			for file in files:
				if os.path.exists(file):
					preview.set_from_file(file)
			model.append([preview, l[i]])
			if gajim.config.get('iconset') == l[i]:
				self.iconset_combobox.set_active(i)

		# Use transports iconsets
		st = gajim.config.get('use_transports_iconsets')
		self.xml.get_widget('transports_iconsets_checkbutton').set_active(st)

		theme_combobox = self.xml.get_widget('theme_combobox')
		cell = gtk.CellRendererText()
		theme_combobox.pack_start(cell, True)
		theme_combobox.add_attribute(cell, 'text', 0)  
		model = gtk.ListStore(str)
		theme_combobox.set_model(model)
		i = 0
		for t in gajim.config.get_per('themes'):
			model.append([t])
			if gajim.config.get('roster_theme') == t:
				theme_combobox.set_active(i)
			i += 1
		self.on_theme_combobox_changed(theme_combobox)

		#use tabbed chat window
		st = gajim.config.get('usetabbedchat')
		self.xml.get_widget('use_tabbed_chat_window_checkbutton').set_active(st)
		
		#use speller
		if os.name == 'nt':
			self.xml.get_widget('speller_checkbutton').set_no_show_all(True)
		else:
			if 'gtkspell' in globals():
				st = gajim.config.get('use_speller')
				self.xml.get_widget('speller_checkbutton').set_active(st)
			else:
				self.xml.get_widget('speller_checkbutton').set_sensitive(False)
		
		#Print time
		if gajim.config.get('print_time') == 'never':
			self.xml.get_widget('time_never_radiobutton').set_active(True)
		elif gajim.config.get('print_time') == 'sometimes':
			self.xml.get_widget('time_sometimes_radiobutton').set_active(True)
		else:
			self.xml.get_widget('time_always_radiobutton').set_active(True)

		#before time
		st = gajim.config.get('before_time')
		self.xml.get_widget('before_time_entry').set_text(st)
		
		#after time
		st = gajim.config.get('after_time')
		self.xml.get_widget('after_time_entry').set_text(st)

		#before nickname
		st = gajim.config.get('before_nickname')
		self.xml.get_widget('before_nickname_entry').set_text(st)

		#after nickanme
		st = gajim.config.get('after_nickname')
		self.xml.get_widget('after_nickname_entry').set_text(st)

		#Color for incomming messages
		colSt = gajim.config.get('inmsgcolor')
		self.xml.get_widget('incoming_msg_colorbutton').set_color(
			gtk.gdk.color_parse(colSt))
		
		#Color for outgoing messages
		colSt = gajim.config.get('outmsgcolor')
		self.xml.get_widget('outgoing_msg_colorbutton').set_color(
			gtk.gdk.color_parse(colSt))
		
		#Color for status messages
		colSt = gajim.config.get('statusmsgcolor')
		self.xml.get_widget('status_msg_colorbutton').set_color(
			gtk.gdk.color_parse(colSt))

		# on new message
		only_in_roster = True
		if gajim.config.get('notify_on_new_message'):
			self.xml.get_widget('notify_on_new_message_radiobutton').set_active(1)
			only_in_roster = False
		if gajim.config.get('autopopup'):
			self.xml.get_widget('popup_new_message_radiobutton').set_active(True)
			only_in_roster = False
		if only_in_roster:
			self.xml.get_widget('only_in_roster_radiobutton').set_active(True)

		#notify on online statuses
		st = gajim.config.get('notify_on_signin')
		self.notify_on_signin_checkbutton.set_active(st)

		#notify on offline statuses
		st = gajim.config.get('notify_on_signout')
		self.notify_on_signout_checkbutton.set_active(st)

		#autopopupaway
		st = gajim.config.get('autopopupaway')
		self.auto_popup_away_checkbutton.set_active(st)

		#Ignore messages from unknown contacts
		self.xml.get_widget('ignore_events_from_unknown_contacts_checkbutton').\
			set_active(gajim.config.get('ignore_unknown_contacts'))

		#sounds
		if os.name == 'nt': # if windows, player must not become visible on show_all
			soundplayer_hbox = self.xml.get_widget('soundplayer_hbox')
			soundplayer_hbox.set_no_show_all(True)
		if gajim.config.get('sounds_on'):
			self.xml.get_widget('play_sounds_checkbutton').set_active(True)
		else:
			self.xml.get_widget('soundplayer_hbox').set_sensitive(False)
			self.xml.get_widget('sounds_scrolledwindow').set_sensitive(False)
			self.xml.get_widget('browse_sounds_hbox').set_sensitive(False)

		#sound player
		self.xml.get_widget('soundplayer_entry').set_text(
			gajim.config.get('soundplayer'))

		#sounds treeview
		self.sound_tree = self.xml.get_widget('sounds_treeview')
		model = gtk.ListStore(str,	bool, str)
		self.sound_tree.set_model(model)

		col = gtk.TreeViewColumn(_('Active'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererToggle()
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.sound_toggled_cb)
		col.pack_start(renderer)
		col.set_attributes(renderer, active = 1)

		col = gtk.TreeViewColumn(_('Event'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 0)

		col = gtk.TreeViewColumn(_('Sound'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 2)
		self.fill_sound_treeview()
		
		#Autoaway
		st = gajim.config.get('autoaway')
		self.auto_away_checkbutton.set_active(st)

		#Autoawaytime
		st = gajim.config.get('autoawaytime')
		self.auto_away_time_spinbutton.set_value(st)
		self.auto_away_time_spinbutton.set_sensitive(gajim.config.get('autoaway'))

		#Autoxa
		st = gajim.config.get('autoxa')
		self.auto_xa_checkbutton.set_active(st)

		#Autoxatime
		st = gajim.config.get('autoxatime')
		self.auto_xa_time_spinbutton.set_value(st)
		self.auto_xa_time_spinbutton.set_sensitive(gajim.config.get('autoxa'))

		#ask_status when online / offline
		st = gajim.config.get('ask_online_status')
		self.xml.get_widget('prompt_online_status_message_checkbutton').\
			set_active(st)
		st = gajim.config.get('ask_offline_status')
		self.xml.get_widget('prompt_offline_status_message_checkbutton').\
			set_active(st)

		#Status messages
		self.msg_tree = self.xml.get_widget('msg_treeview')
		model = gtk.ListStore(str, str)
		self.msg_tree.set_model(model)
		col = gtk.TreeViewColumn('name')
		self.msg_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 0)
		renderer.connect('edited', self.on_msg_cell_edited)
		renderer.set_property('editable', True)
		self.fill_msg_treeview()
		buf = self.xml.get_widget('msg_textview').get_buffer()
		buf.connect('changed', self.on_msg_textview_changed)

		#open links with
		if os.name == 'nt':
			self.links_frame = self.xml.get_widget('links_frame')
			self.links_frame.set_no_show_all(True)
		else:
			self.links_open_with_combobox = self.xml.get_widget('links_open_with_combobox')
			if gajim.config.get('openwith') == 'gnome-open':
				self.links_open_with_combobox.set_active(0)
			elif gajim.config.get('openwith') == 'kfmclient exec':
				self.links_open_with_combobox.set_active(True)
			elif gajim.config.get('openwith') == 'custom':
				self.links_open_with_combobox.set_active(2)
				self.xml.get_widget('custom_apps_frame').set_sensitive(True)
			self.xml.get_widget('custom_browser_entry').set_text(
				gajim.config.get('custombrowser'))
			self.xml.get_widget('custom_mail_client_entry').set_text(
				gajim.config.get('custommailapp'))
				
		#log presences in user file
		st = gajim.config.get('log_notif_in_user_file')
		self.xml.get_widget('log_in_contact_checkbutton').set_active(st)

		#log presences in external file
		st = gajim.config.get('log_notif_in_sep_file')
		self.xml.get_widget('log_in_extern_checkbutton').set_active(st)
		
		# don't send os info
		st = gajim.config.get('send_os_info')
		self.xml.get_widget('send_os_info_checkbutton').set_active(st)
		
		# don't check for new version
		st = gajim.config.get('check_for_new_version')
		btn = self.xml.get_widget('check_for_new_version_checkbutton')
		btn.set_active(st)
		
		self.xml.signal_autoconnect(self)
		
		self.sound_tree.get_model().connect('row-changed',
					self.on_sounds_treemodel_row_changed)
		self.msg_tree.get_model().connect('row-changed',
					self.on_msg_treemodel_row_changed)
		self.msg_tree.get_model().connect('row-deleted',
					self.on_msg_treemodel_row_deleted)

	def on_preferences_window_show(self, widget):
		self.notebook.set_current_page(0)

	def on_preferences_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.hide()

	def on_checkbutton_toggled(self, widget, config_name, \
		change_sensitivity_widgets = None):
		gajim.config.set(config_name, widget.get_active())
		if change_sensitivity_widgets:
			for w in change_sensitivity_widgets:
				w.set_sensitive(widget.get_active())
		self.plugin.save_config()

	def on_trayicon_checkbutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('trayicon', True)
			self.plugin.show_systray()
			self.plugin.roster.update_status_comboxbox()

			self.xml.get_widget(
				'show_roster_on_startup_checkbutton').set_sensitive(True)
		else:
			gajim.config.set('trayicon', False)
			self.plugin.hide_systray()
			show_roster_on_startup_checkbutton = self.xml.get_widget(
				'show_roster_on_startup_checkbutton')
			gajim.config.set('show_roster_on_startup', True) # no tray, show roster!
			show_roster_on_startup_checkbutton.set_active(True)
			show_roster_on_startup_checkbutton.set_sensitive(False)
		self.plugin.roster.draw_roster()
		self.plugin.save_config()
	
	def on_save_position_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'saveposition')
	
	def on_merge_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'mergeaccounts')
		self.plugin.roster.regroup = gajim.config.get('mergeaccounts')
		self.plugin.roster.draw_roster()
	
	def on_sort_by_show_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'sort_by_show')
		self.plugin.roster.draw_roster()
	
	def on_use_emoticons_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'useemoticons', 
			[self.xml.get_widget('add_remove_emoticons_button')])
	
	def on_add_remove_emoticons_button_clicked(self, widget):
		window = self.plugin.windows['add_remove_emoticons'].window
		if window.get_property('visible'):
			window.present()
		else:
			window.show_all()

	def on_iconset_combobox_changed(self, widget):
		model = widget.get_model()
		active = widget.get_active()
		icon_string = model[active][1]
		gajim.config.set('iconset', icon_string)
		self.plugin.roster.reload_jabber_state_images()
		self.plugin.save_config()
	
	def on_transports_iconsets_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'use_transports_iconsets')
		self.plugin.roster.draw_roster()

	def on_manage_theme_button_clicked(self, widget):
		dialogs.GajimThemesWindow(self.plugin)
	
	def on_theme_combobox_changed(self, widget):
		model = widget.get_model()
		active = widget.get_active()
		theme = model[active][0]
				
		gajim.config.set('roster_theme', theme)

		# begin repainting themed widgets throughout
		self.plugin.roster.repaint_themed_widgets()
		self.plugin.save_config()
		self.plugin.roster.draw_roster()

	def merge_windows(self, kind):
		for acct in gajim.connections:
			#save buffers and close windows
			buf1 = {}
			buf2 = {}
			saved_var = {}
			windows = self.plugin.windows[acct][kind]
			jids = windows.keys()
			for jid in jids:
				window = windows[jid]
				buf1[jid] = window.xmls[jid].get_widget('conversation_textview').\
					get_buffer()
				buf2[jid] = window.xmls[jid].get_widget('message_textview').\
					get_buffer()
				saved_var[jid] = window.save_var(jid)
				window.window.destroy()
			#open new tabbed chat windows
			for jid in jids:
				if kind == 'chats':
					user = self.plugin.roster.contacts[acct][jid][0]
					self.plugin.roster.new_chat(user, acct)
				if kind == 'gc':
					self.plugin.roster.new_room(jid, saved_var[jid]['nick'], acct)
				window = windows[jid]
				window.xmls[jid].get_widget('conversation_textview').set_buffer(
					buf1[jid])
				window.xmls[jid].get_widget('message_textview').set_buffer(
					buf2[jid])
				window.load_var(jid, saved_var[jid])

	def split_windows(self, kind):
		for acct in gajim.connections:
			#save buffers and close tabbed chat windows
			buf1 = {}
			buf2 = {}
			saved_var = {}
			windows = self.plugin.windows[acct][kind]
			jids = windows.keys()
			if not 'tabbed' in jids:
				continue
			jids.remove('tabbed')
			for jid in jids:
				window = windows[jid]
				buf1[jid] = window.xmls[jid].get_widget('conversation_textview').\
					get_buffer()
				buf2[jid] = window.xmls[jid].get_widget('message_textview').\
					get_buffer()
				saved_var[jid] = window.save_var(jid)
			windows['tabbed'].window.destroy()
			#open new tabbed chat windows
			for jid in jids:
				if kind == 'chats':
					user = self.plugin.roster.contacts[acct][jid][0]
					self.plugin.roster.new_chat(user, acct)
				if kind == 'gc':
					self.plugin.roster.new_room(jid, saved_var[jid]['nick'], acct)
				window = windows[jid]
				window.xmls[jid].get_widget('conversation_textview').set_buffer(
					buf1[jid])
				window.xmls[jid].get_widget('message_textview').set_buffer(
					buf2[jid])
				window.load_var(jid, saved_var[jid])

	def on_show_roster_on_startup_checkbutton_toggled(self, widget):
		active = widget.get_active()
		gajim.config.set('show_roster_on_startup', active)
		self.plugin.save_config()

	def on_use_tabbed_chat_window_checkbutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('usetabbedchat', True)
			self.merge_windows('chats')
			self.merge_windows('gc')
		else:
			gajim.config.set('usetabbedchat', False)
			self.split_windows('chats')
			self.split_windows('gc')
		self.plugin.save_config()

	def apply_speller(self, kind):
		for acct in gajim.connections:
			windows = self.plugin.windows[acct][kind]
			jids = windows.keys()
			for jid in jids:
				if jid == 'tabbed':
					continue
				window = windows[jid]
				textview = window.xmls[jid].get_widget('message_textview')
				gtkspell.Spell(textview)

	def remove_speller(self, kind):
		for acct in gajim.connections:
			windows = self.plugin.windows[acct][kind]
			jids = windows.keys()
			for jid in jids:
				if jid == 'tabbed':
					continue
				window = windows[jid]
				textview = window.xmls[jid].get_widget('message_textview')
				spell_obj = gtkspell.get_from_text_view(textview)
				if spell_obj:
					spell_obj.detach()

	def on_speller_checkbutton_toggled(self, widget):
		active = widget.get_active()
		gajim.config.set('use_speller', active)
		self.plugin.save_config()
		if active:
			self.apply_speller('chats')
			self.apply_speller('gc')
		else:
			self.remove_speller('chats')
			self.remove_speller('gc')

	def update_print_time(self):
		'''Update time in Opened Chat Windows'''
		for a in gajim.connections:
			window = self.plugin.windows[a]['chats']
			if window.has_key('tabbed'):
				window['tabbed'].update_print_time()
			else:
				for jid in window.keys():
					window[jid].update_print_time()
	
	def on_time_never_radiobutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('print_time', 'never')
		self.update_print_time()
		self.plugin.save_config()

	def on_time_sometimes_radiobutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('print_time', 'sometimes')
		self.update_print_time()
		self.plugin.save_config()

	def on_time_always_radiobutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('print_time', 'always')
		self.update_print_time()
		self.plugin.save_config()

	def on_before_time_entry_focus_out_event(self, widget, event):
		gajim.config.set('before_time', widget.get_text())
		self.plugin.save_config()
	
	def on_after_time_entry_focus_out_event(self, widget, event):
		gajim.config.set('after_time', widget.get_text())
		self.plugin.save_config()

	def on_before_nickname_entry_focus_out_event(self, widget, event):
		gajim.config.set('before_nickname', widget.get_text())
		self.plugin.save_config()

	def on_after_nickname_entry_focus_out_event(self, widget, event):
		gajim.config.set('after_nickname', widget.get_text())
		self.plugin.save_config()

	def update_text_tags(self):
		'''Update color tags in Opened Chat Windows'''
		for a in gajim.connections:
			window = self.plugin.windows[a]['chats']
			if window.has_key('tabbed'):
				window['tabbed'].update_tags()
			else:
				for jid in window.keys():
					window[jid].update_tags()
	
	def on_preference_widget_color_set(self, widget, text):
		color = widget.get_color()
		color_string = mk_color_string(color)
		gajim.config.set(text, color_string)
		self.update_text_tags()
		self.plugin.save_config()
	
	def on_incoming_msg_colorbutton_color_set(self, widget):
		self.on_preference_widget_color_set(widget, 'inmsgcolor')
		
	def on_outgoing_msg_colorbutton_color_set(self, widget):
		self.on_preference_widget_color_set(widget, 'outmsgcolor')
	
	def on_status_msg_colorbutton_color_set(self, widget):
		self.on_preference_widget_color_set(widget, 'statusmsgcolor')
	
	def on_reset_colors_button_clicked(self, widget):
		for i in ['inmsgcolor', 'outmsgcolor', 'statusmsgcolor']:
			gajim.config.set(i, self.plugin.default_values[i])

		self.xml.get_widget('incoming_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(gajim.config.get('inmsgcolor')))
		self.xml.get_widget('outgoing_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(gajim.config.get('outmsgcolor')))
		self.xml.get_widget('status_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(gajim.config.get('statusmsgcolor')))
		self.update_text_tags()
		self.plugin.save_config()

	def on_notify_on_new_message_radiobutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_new_message',
					[self.auto_popup_away_checkbutton])

	def on_popup_new_message_radiobutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autopopup',
					[self.auto_popup_away_checkbutton])

	def on_only_in_roster_radiobutton_toggled(self, widget):
		if widget.get_active():
			self.auto_popup_away_checkbutton.set_sensitive(False)

	def on_notify_on_signin_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_signin')

	def on_notify_on_signout_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_signout')

	def on_auto_popup_away_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autopopupaway')

	def on_ignore_events_from_unknown_contacts_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ignore_unknown_contacts')

	def on_play_sounds_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'sounds_on',
				[self.xml.get_widget('soundplayer_hbox'),
				self.xml.get_widget('sounds_scrolledwindow'),
				self.xml.get_widget('browse_sounds_hbox')])
	
	def on_soundplayer_entry_changed(self, widget):
		gajim.config.set('soundplayer', widget.get_text())
		self.plugin.save_config()
		
	def on_prompt_online_status_message_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ask_online_status')
	
	def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ask_offline_status')
	
	def on_sounds_treemodel_row_changed(self, model, path, iter):
		sound_event = model.get_value(iter, 0)
		gajim.config.set_per('soundevents', sound_event, 'enabled',
					bool(model[path][1]))
		gajim.config.set_per('soundevents', sound_event, 'path',
					model.get_value(iter, 2))
		self.plugin.save_config()

	def on_auto_away_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autoaway',
					[self.auto_away_time_spinbutton])

	def on_auto_away_time_spinbutton_value_changed(self, widget):
		aat = widget.get_value_as_int()
		gajim.config.set('autoawaytime', aat)
		self.plugin.sleeper = common.sleepy.Sleepy(
					gajim.config.get('autoawaytime') * 60,
					gajim.config.get('autoxatime') * 60)
		self.plugin.save_config()

	def on_auto_xa_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autoxa',
					[self.auto_xa_time_spinbutton])

	def on_auto_xa_time_spinbutton_value_changed(self, widget):
		axt = widget.get_value_as_int()
		gajim.config.set('autoxatime', axt)
		self.plugin.sleeper = common.sleepy.Sleepy(
					gajim.config.get('autoawaytime') * 60,
					gajim.config.get('autoxatime') * 60)
		self.plugin.save_config()

	def save_status_messages(self, model):
		for msg in gajim.config.get_per('statusmsg'):
			gajim.config.del_per('statusmsg', msg)
		iter = model.get_iter_first()
		while iter:
			val = model.get_value(iter, 0)
			gajim.config.add_per('statusmsg', val)
			gajim.config.set_per('statusmsg', val, 'message',
						model.get_value(iter, 1))
			iter = model.iter_next(iter)
		self.plugin.save_config()

	def on_msg_treemodel_row_changed(self, model, path, iter):
		self.save_status_messages(model)

	def on_msg_treemodel_row_deleted(self, model, path):
		self.save_status_messages(model)

	def on_links_open_with_combobox_changed(self, widget):
		if widget.get_active() == 2:
			self.xml.get_widget('custom_apps_frame').set_sensitive(True)
			gajim.config.set('openwith', 'custom')
		else:
			if widget.get_active() == 0:
				gajim.config.set('openwith', 'gnome-open')
			if widget.get_active() == 1:
				gajim.config.set('openwith', 'kfmclient exec')
			self.xml.get_widget('custom_apps_frame').set_sensitive(False)
		self.plugin.save_config()

	def on_custom_browser_entry_changed(self, widget):
		gajim.config.set('custombrowser', widget.get_text())
		self.plugin.save_config()

	def on_custom_mail_client_entry_changed(self, widget):
		gajim.config.set('custommailapp', widget.get_text())
		self.plugin.save_config()

	def on_log_in_contact_checkbutton_toggled(self, widget):
		gajim.config.set('log_notif_in_user_file', widget.get_active())
		self.plugin.save_config()

	def on_log_in_extern_checkbutton_toggled(self, widget):
		gajim.config.set('log_notif_in_sep_file', widget.get_active())
		self.plugin.save_config()

	def on_send_os_info_checkbutton_toggled(self, widget):
		gajim.config.set('send_os_info', widget.get_active())
		self.plugin.save_config()

	def on_check_for_new_version_checkbutton_toggled(self, widget):
		gajim.config.set('check_for_new_version', widget.get_active())
		self.plugin.save_config()

	def fill_msg_treeview(self):
		self.xml.get_widget('delete_msg_button').set_sensitive(False)
		model = self.msg_tree.get_model()
		model.clear()
		for msg in gajim.config.get_per('statusmsg'):
			iter = model.append()
			val = gajim.config.get_per('statusmsg', msg, 'message')
			model.set(iter, 0, msg, 1, val)

	def on_msg_cell_edited(self, cell, row, new_text):
		model = self.msg_tree.get_model()
		iter = model.get_iter_from_string(row)
		model.set_value(iter, 0, new_text)

	def on_msg_treeview_cursor_changed(self, widget, data = None):
		(model, iter) = self.msg_tree.get_selection().get_selected()
		if not iter:
			return
		self.xml.get_widget('delete_msg_button').set_sensitive(True)
		buf = self.xml.get_widget('msg_textview').get_buffer()
		name = model.get_value(iter, 0)
		msg = model.get_value(iter, 1)
		buf.set_text(msg)

	def on_new_msg_button_clicked(self, widget, data = None):
		model = self.msg_tree.get_model()
		iter = model.append()
		model.set(iter, 0, 'msg', 1, 'message')

	def on_delete_msg_button_clicked(self, widget, data = None):
		(model, iter) = self.msg_tree.get_selection().get_selected()
		if not iter:
			return
		buf = self.xml.get_widget('msg_textview').get_buffer()
		model.remove(iter)
		buf.set_text('')
		self.xml.get_widget('delete_msg_button').set_sensitive(False)
			
	def on_msg_textview_changed(self, widget, data = None):
		(model, iter) = self.msg_tree.get_selection().get_selected()
		if not iter:
			return
		buf = self.xml.get_widget('msg_textview').get_buffer()
		first_iter, end_iter = buf.get_bounds()
		name = model.get_value(iter, 0)
		model.set_value(iter, 1, buf.get_text(first_iter, end_iter))
	
	def on_msg_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Delete:
			self.on_delete_msg_button_clicked(widget)

	def sound_toggled_cb(self, cell, path):
		model = self.sound_tree.get_model()
		model[path][1] = not model[path][1]

	def fill_sound_treeview(self):
		sounds = gajim.config.get_per('soundevents')
		model = self.sound_tree.get_model()
		model.clear()
		for sound in sounds:
			val = gajim.config.get_per('soundevents', sound,
								'enabled')
			path = gajim.config.get_per('soundevents', sound,
								'path')
			iter = model.append((sound, val, path))

	def on_treeview_sounds_cursor_changed(self, widget, data = None):
		(model, iter) = self.sound_tree.get_selection().get_selected()
		sounds_entry = self.xml.get_widget('sounds_entry')
		if not iter:
			sounds_entry.set_text('')
			return
		str = model.get_value(iter, 2)
		sounds_entry.set_text(str)

	def on_button_sounds_clicked(self, widget, data = None):
		(model, iter) = self.sound_tree.get_selection().get_selected()
		if not iter:
			return
		file = model.get_value(iter, 2)
		dialog = gtk.FileChooserDialog(_('Choose Sound'), None,
					gtk.FILE_CHOOSER_ACTION_OPEN,
					(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
					gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)

		filter = gtk.FileFilter()
		filter.set_name(_('All files'))
		filter.add_pattern('*')
		dialog.add_filter(filter)

		filter = gtk.FileFilter()
		filter.set_name(_('Wav Sounds'))
		filter.add_pattern('*.wav')
		dialog.add_filter(filter)
		dialog.set_filter(filter)

		file = os.path.join(os.getcwd(), file)
		dialog.set_filename(file)
		file = ''
		while True:
			response = dialog.run()
			if response != gtk.RESPONSE_OK:
				break
			file = dialog.get_filename()
			if os.path.exists(file):
				break
		dialog.destroy()
		if file:
			self.xml.get_widget('sounds_entry').set_text(file)
			model.set_value(iter, 2, file)
			model.set_value(iter, 1, 1)

	def on_sounds_entry_changed(self, widget):
		path_to_file = widget.get_text()
		model, iter = self.sound_tree.get_selection().get_selected()
		model.set_value(iter, 2, path_to_file)
		model.set_value(iter, 1, 1)

	def on_open_advanced_editor_button_clicked(self, widget, data = None):
		if self.plugin.windows.has_key('advanced_config'):
			self.plugin.windows['advanced_config'].window.present()
		else:
			self.plugin.windows['advanced_config'] = \
				dialogs.AdvancedConfigurationWindow(self.plugin)

#---------- AccountModificationWindow class -------------#
class AccountModificationWindow:
	'''Class for account informations'''
	def on_account_modification_window_destroy(self, widget):
		'''close window'''
		if self.plugin.windows.has_key(self.account):
			if self.plugin.windows[self.account].has_key('account_modification'):
				del self.plugin.windows[self.account]['account_modification']
				return
		if self.plugin.windows.has_key('account_modification'):
			del self.plugin.windows['account_modification']
	
	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self, plugin, account = ''):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'account_modification_window', APP)
		self.window = self.xml.get_widget('account_modification_window')
		self.plugin = plugin
		self.account = account
		self.modify = False # if we 're modifying an existing or creating a new account

		# init proxy list
		self.update_proxy_list()

		self.xml.signal_autoconnect(self)
		if account: # we modify an existing account
			self.modify = True
			self.init_account()
			self.xml.get_widget('new_account_checkbutton').set_sensitive(False)
			self.xml.get_widget('save_button').grab_focus()
		else: # we create a new account
			if len(gajim.connections) == 0: # is it the first accound we're creating?
				# the first account *has* to sync
				self.xml.get_widget('sync_with_global_status_checkbutton').set_active(True)
				self.xml.get_widget('name_entry').set_text('Main')
				self.xml.get_widget('jid_entry').grab_focus()
		self.window.show_all()

	def on_checkbutton_toggled(self, widget, widgets):
		'''set or unset sensitivity of widgets when widget is toggled'''
		for w in widgets:
			w.set_sensitive(widget.get_active())

	def init_account_gpg(self):
		keyid = gajim.config.get_per('accounts', self.account, 'keyid')
		keyname = gajim.config.get_per('accounts', self.account, 'keyname')
		savegpgpass = gajim.config.get_per('accounts', self.account,
																'savegpgpass')

		if not keyid or not gajim.config.get('usegpg'):
			return

		self.xml.get_widget('gpg_key_label').set_text(keyid)
		self.xml.get_widget('gpg_name_label').set_text(keyname)
		gpg_save_password_checkbutton = \
			self.xml.get_widget('gpg_save_password_checkbutton')
		gpg_save_password_checkbutton.set_sensitive(True)
		gpg_save_password_checkbutton.set_active(savegpgpass)

		if savegpgpass:
			entry = self.xml.get_widget('gpg_password_entry')
			entry.set_sensitive(True)
			gpgpassword = gajim.config.get_per('accounts',
						self.account, 'gpgpassword')
			entry.set_text(gpgpassword)

	def update_proxy_list(self):
		if self.account:
			our_proxy = gajim.config.get_per('accounts', self.account, 'proxy')
		else:
			our_proxy = ''
		if not our_proxy:
			our_proxy = 'None'
		self.proxy_combobox = self.xml.get_widget('proxies_combobox')
		model = gtk.ListStore(str)
		self.proxy_combobox.set_model(model)
		l = gajim.config.get_per('proxies')
		l.insert(0, 'None')
		for i in range(len(l)):
			model.append([l[i]])
			if our_proxy == l[i]:
				self.proxy_combobox.set_active(i)

	def init_account(self):
		'''Initialize window with defaults values'''
		self.xml.get_widget('name_entry').set_text(self.account)
		jid = gajim.config.get_per('accounts', self.account, 'name') \
			+ '@' + gajim.config.get_per('accounts',
						self.account, 'hostname')
		self.xml.get_widget('jid_entry').set_text(jid)
		self.xml.get_widget('save_password_checkbutton').set_active(
			gajim.config.get_per('accounts', self.account, 'savepass'))
		if gajim.config.get_per('accounts', self.account, 'savepass'):
			passstr = gajim.config.get_per('accounts',
						self.account, 'password')
			password_entry = self.xml.get_widget('password_entry')
			password_entry.set_sensitive(True)
			password_entry.set_text(passstr)

		self.xml.get_widget('resource_entry').set_text(gajim.config.get_per(
			'accounts', self.account, 'resource'))
		self.xml.get_widget('priority_spinbutton').set_value(gajim.config.\
			get_per('accounts', self.account, 'priority'))

		usessl = gajim.config.get_per('accounts', self.account, 'usessl')
		self.xml.get_widget('use_ssl_checkbutton').set_active(usessl)

		use_custom_host = gajim.config.get_per('accounts', self.account,
			'use_custom_host')
		self.xml.get_widget('custom_host_port_checkbutton').set_active(
			use_custom_host)
		custom_host = gajim.config.get_per('accounts', self.account,
			'custom_host')
		if not custom_host:
			custom_host = gajim.config.get_per('accounts',
				self.account, 'hostname')
		self.xml.get_widget('custom_host_entry').set_text(custom_host)
		custom_port = gajim.config.get_per('accounts', self.account,
			'custom_port')
		if not custom_port:
			custom_port = 5222
		self.xml.get_widget('custom_port_entry').set_text(str(custom_port))

		gpg_key_label = self.xml.get_widget('gpg_key_label')
		if gajim.config.get('usegpg'):
			self.init_account_gpg()
		else:
			gpg_key_label.set_text(_('OpenPGP is not usable in this computer'))
			self.xml.get_widget('gpg_choose_button').set_sensitive(False)
		self.xml.get_widget('autoconnect_checkbutton').set_active(gajim.config.\
			get_per('accounts', self.account, 'autoconnect'))

		if len(gajim.connections) != 0: # only if we already have one account already
			# we check that so we avoid the first account to have sync=False
			self.xml.get_widget('sync_with_global_status_checkbutton').set_active(
				gajim.config.get_per('accounts', self.account,
					'sync_with_global_status'))
		list_no_log_for = gajim.config.get_per('accounts', self.account,
			'no_log_for').split()
		if self.account in list_no_log_for:
			self.xml.get_widget('log_history_checkbutton').set_active(0)

	def on_save_button_clicked(self, widget):
		'''When save button is clicked: Save information in config file'''
		config = {}
		name = self.xml.get_widget('name_entry').get_text()
		if gajim.connections.has_key(self.account):
			if name != self.account and \
			   gajim.connections[self.account].connected != 0:
				dialogs.ErrorDialog(_('You are connected to the server'),
_('To change the account name, it must be disconnected.')).get_response()
				return
		if (name == ''):
			dialogs.ErrorDialog(_('Invalid account name'),
				_('Account names cannot be empty.')).get_response()
			return
		if name.find(' ') != -1:
			dialogs.ErrorDialog(_('Invalid account name'),
				_('Account names cannot contain spaces.')).get_response()
			return
		jid = self.xml.get_widget('jid_entry').get_text()
		if jid == '' or jid.count('@') != 1:
			dialogs.ErrorDialog(_('Invalid Jabber ID'),
           _('A Jabber ID must be in the form "user@servername".')).get_response()
			return
		new_account = self.xml.get_widget('new_account_checkbutton').get_active()
		config['savepass'] = self.xml.get_widget(
				'save_password_checkbutton').get_active()
		config['password'] = self.xml.get_widget('password_entry').get_text()
		if new_account and config['password'] == '':
			dialogs.ErrorDialog(_('Invalid password'),
				_('You must enter a password for the new account.')).get_response()
			return
		config['resource'] = self.xml.get_widget('resource_entry').get_text()
		config['priority'] = self.xml.get_widget('priority_spinbutton').\
																			get_value_as_int()
		config['autoconnect'] = self.xml.get_widget('autoconnect_checkbutton').\
																					get_active()

		if self.account:
			list_no_log_for = gajim.config.get_per('accounts',
					self.account, 'no_log_for').split()
		else:
			list_no_log_for = []
		if self.account in list_no_log_for:
			list_no_log_for.remove(self.account)
		if not self.xml.get_widget('log_history_checkbutton').get_active():
			list_no_log_for.append(name)
		config['no_log_for'] = ' '.join(list_no_log_for)
		
		config['sync_with_global_status'] = self.xml.get_widget(
				'sync_with_global_status_checkbutton').get_active()
		
		active = self.proxy_combobox.get_active()
		proxy = self.proxy_combobox.get_model()[active][0]
		if proxy == 'None':
			proxy = ''
		config['proxy'] = proxy
		
		config['usessl'] = self.xml.get_widget('use_ssl_checkbutton').get_active()
		(config['name'], config['hostname']) = jid.split('@')

		config['use_custom_host'] = self.xml.get_widget(
			'custom_host_port_checkbutton').get_active()
		custom_port = self.xml.get_widget('custom_port_entry').get_text()
		try:
			custom_port = int(custom_port)
		except:
			dialogs.ErrorDialog(_('Invalid entry'),
				_('Custom port must be a port number.')).get_response()
			return
		config['custom_port'] = custom_port
		config['custom_host'] = self.xml.get_widget(
			'custom_host_entry').get_text()

		config['keyname'] = self.xml.get_widget('gpg_name_label').get_text()
		if config['keyname'] == '': #no key selected
			config['keyid'] = ''
			config['savegpgpass'] = False
			config['gpgpassword'] = ''
		else:
			config['keyid'] = self.xml.get_widget('gpg_key_label').get_text()
			config['savegpgpass'] = self.xml.get_widget(
					'gpg_save_password_checkbutton').get_active()
			config['gpgpassword'] = self.xml.get_widget('gpg_password_entry').\
																						get_text()
		#if we are modifying an account
		if self.modify:
			#if we modify the name of the account
			if name != self.account:
				#update variables
				self.plugin.windows[name] = self.plugin.windows[self.account]
				self.plugin.queues[name] = self.plugin.queues[self.account]
				self.plugin.nicks[name] = self.plugin.nicks[self.account]
				self.plugin.allow_notifications[name] = \
					self.plugin.allow_notifications[self.account]
				self.plugin.roster.groups[name] = \
					self.plugin.roster.groups[self.account]
				self.plugin.roster.contacts[name] = \
					self.plugin.roster.contacts[self.account]
				self.plugin.roster.newly_added[name] = \
					self.plugin.roster.newly_added[self.account]
				self.plugin.roster.to_be_removed[name] = \
					self.plugin.roster.to_be_removed[self.account]
				self.plugin.sleeper_state[name] = \
					self.plugin.sleeper_state[self.account]
				#upgrade account variable in opened windows
				for kind in ['infos', 'chats', 'gc', 'gc_config']:
					for j in self.plugin.windows[name][kind]:
						self.plugin.windows[name][kind][j].account = name
				#upgrade account in systray
				for list in self.plugin.systray.jids:
					if list[0] == self.account:
						list[0] = name
				del self.plugin.windows[self.account]
				del self.plugin.queues[self.account]
				del self.plugin.nicks[self.account]
				del self.plugin.allow_notifications[self.account]
				del self.plugin.roster.groups[self.account]
				del self.plugin.roster.contacts[self.account]
				del self.plugin.sleeper_state[self.account]
				gajim.connections[self.account].name = name
				gajim.connections[name] = gajim.connections[self.account]
				del gajim.connections[self.account]
				gajim.config.del_per('accounts', self.account)
				gajim.config.add_per('accounts', name)
				self.account = name
			
			for opt in config:
				gajim.config.set_per('accounts', name, opt, config[opt])
			if config['savepass']:
				gajim.connections[name].password = config['password']
			#refresh accounts window
			if self.plugin.windows.has_key('accounts'):
				self.plugin.windows['accounts'].init_accounts()
			#refresh roster
			self.plugin.roster.draw_roster()
			self.plugin.save_config()
			self.window.destroy()
			return
		#if it's a new account
		if name in gajim.connections:
			dialogs.ErrorDialog(_('Account name is in use'),
				_('You already have an account using this name.')).get_response()
			return
		con = connection.Connection(name)
		self.plugin.register_handlers(con)
		#if we need to register a new account
		if new_account:
			con.new_account(name, config)
			return
		# The account we add already exists on the server
		gajim.connections[name] = con
		gajim.config.add_per('accounts', name)
		for opt in config:
			gajim.config.set_per('accounts', name, opt, config[opt])
		if config['savepass']:
			gajim.connections[name].password = config['password']
		#update variables
		self.plugin.windows[name] = {'infos': {}, 'chats': {}, 'gc': {}, \
			'gc_config': {}}
		self.plugin.queues[name] = {}
		gajim.connections[name].connected = 0
		self.plugin.roster.groups[name] = {}
		self.plugin.roster.contacts[name] = {}
		self.plugin.roster.newly_added[name] = []
		self.plugin.roster.to_be_removed[name] = []
		self.plugin.nicks[name] = config['name']
		self.plugin.allow_notifications[name] = False
		self.plugin.sleeper_state[name] = 0
		#refresh accounts window
		if self.plugin.windows.has_key('accounts'):
			self.plugin.windows['accounts'].init_accounts()
		#refresh roster
		self.plugin.roster.draw_roster()
		self.plugin.save_config()
		self.window.destroy()

	def on_change_password_button_clicked(self, widget):
		dialog = dialogs.ChangePasswordDialog(self.plugin, self.account)
		new_password = dialog.run()
		if new_password != -1:
			gajim.connections[self.account].change_password(new_password, \
				self.plugin.nicks[self.account])
			if self.xml.get_widget('save_password_checkbutton').get_active():
				self.xml.get_widget('password_entry').set_text(new_password)

	def account_is_ok(self, acct):
		'''When the account has been created with sucess'''
		self.xml.get_widget('new_account_checkbutton').set_active(False)
		self.modify = True
		self.account = acct

	def on_edit_details_button_clicked(self, widget):
		if not self.plugin.windows.has_key(self.account):
			dialogs.ErrorDialog(_('No such account available'),
				_('You must create your account before editing your personal information.')).get_response()
			return
		jid = self.xml.get_widget('jid_entry').get_text()
		if gajim.connections[self.account].connected < 2:
			dialogs.ErrorDialog(_('You are not connected to the server'),
				_('Without a connection, you can not edit your personal information.')).get_response()
			return
		if not self.plugin.windows[self.account]['infos'].has_key('vcard'):
			self.plugin.windows[self.account]['infos'][jid] = \
				dialogs.VcardWindow(jid, self.plugin,	self.account, True)
			gajim.connections[self.account].request_vcard(jid)

	def on_manage_proxies_button_clicked(self, widget):
		if self.plugin.windows.has_key('manage_proxies'):
			self.plugin.windows['manage_proxies'].window.present()
		else:
			self.plugin.windows['manage_proxies'] = \
				ManageProxiesWindow(self.plugin)

	def on_gpg_choose_button_clicked(self, widget, data = None):
		secret_keys = gajim.connections[self.account].ask_gpg_secrete_keys()
		if not secret_keys:
			dialogs.ErrorDialog(_('Failed to get secret keys'),
_('There was a problem retrieving your GPG secret keys.')).get_response()
			return
		secret_keys['None'] = 'None'
		w = dialogs.ChooseGPGKeyDialog(_('Passphrase'), _('Choose your OpenPGP key'), secret_keys)
		keyID = w.run()
		if keyID == -1:
			return
		checkbutton = self.xml.get_widget('gpg_save_password_checkbutton')
		gpg_key_label = self.xml.get_widget('gpg_key_label')
		gpg_name_label = self.xml.get_widget('gpg_name_label')
		if keyID[0] == 'None':
			gpg_key_label.set_text(_('No key selected'))
			gpg_name_label.set_text('')
			checkbutton.set_sensitive(False)
			self.xml.get_widget('gpg_password_entry').set_sensitive(False)
		else:
			gpg_key_label.set_text(keyID[0])
			gpg_name_label.set_text(keyID[1])
			checkbutton.set_sensitive(True)
		checkbutton.set_active(False)
		self.xml.get_widget('gpg_password_entry').set_text('')

	def on_checkbutton_toggled_and_clear(self, widget, widgets):
		self.on_checkbutton_toggled(widget, widgets)
		for w in widgets:
			if not widget.get_active():
				w.set_text('')

	def on_use_ssl_checkbutton_toggled(self, widget):
		isactive = widget.get_active()
		if isactive:
			self.xml.get_widget('custom_port_entry').set_text('5223')
		else:
			self.xml.get_widget('custom_port_entry').set_text('5222')

	def on_send_keepalive_checkbutton_toggled(self, widget):
		isactive = widget.get_active()
		gajim.config.set_per('accounts', self.account,
			'keep_alives_enabled', isactive)
	
	def on_custom_host_port_checkbutton_toggled(self, widget):
		isactive = widget.get_active()
		self.xml.get_widget('custom_host_port_hbox').set_sensitive(isactive)

	def on_gpg_save_password_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled_and_clear(widget, [
			self.xml.get_widget('gpg_password_entry')])

	def on_save_password_checkbutton_toggled(self, widget):
		if self.xml.get_widget('new_account_checkbutton').get_active():
			return
		self.on_checkbutton_toggled_and_clear(widget,
			[self.xml.get_widget('password_entry')])
		self.xml.get_widget('password_entry').grab_focus()

	def on_new_account_checkbutton_toggled(self, widget):
		password_entry = self.xml.get_widget('password_entry')
		if widget.get_active():
			password_entry.set_sensitive(True)
		elif not self.xml.get_widget('save_password_checkbutton').get_active():
			password_entry.set_sensitive(False)
			password_entry.set_text('')

#---------- ManageProxiesWindow class -------------#
class ManageProxiesWindow:
	def __init__(self, plugin):
		self.plugin = plugin
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'manage_proxies_window', APP)
		self.window = self.xml.get_widget('manage_proxies_window')
		self.proxies_treeview = self.xml.get_widget('proxies_treeview')
		self.proxyname_entry = self.xml.get_widget('proxyname_entry')
		self.init_list()
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def fill_proxies_treeview(self):
		model = self.proxies_treeview.get_model()
		model.clear()
		iter = model.append()
		model.set(iter, 0, 'None')
		for p in gajim.config.get_per('proxies'):
			iter = model.append()
			model.set(iter, 0, p)

	def init_list(self):
		self.xml.get_widget('remove_proxy_button').set_sensitive(False)
		self.xml.get_widget('proxytype_combobox').set_sensitive(False)
		self.xml.get_widget('proxy_table').set_sensitive(False)
		model = gtk.ListStore(str)
		self.proxies_treeview.set_model(model)
		col = gtk.TreeViewColumn('Proxies')
		self.proxies_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 0)
		self.fill_proxies_treeview()
		self.xml.get_widget('proxytype_combobox').set_active(0)

	def on_manage_proxies_window_destroy(self, widget):
		for account in gajim.connections:
			if self.plugin.windows[account].has_key('account_modification'):
				self.plugin.windows[account]['account_modification'].\
					update_proxy_list()
		if self.plugin.windows.has_key('account_modification'):
			self.plugin.windows['account_modification'].update_proxy_list()
		del self.plugin.windows['manage_proxies'] 

	def on_add_proxy_button_clicked(self, widget):
		model = self.proxies_treeview.get_model()
		proxies = gajim.config.get_per('proxies')
		i = 1
		while ('proxy' + str(i)) in proxies:
			i += 1
		iter = model.append()
		model.set(iter, 0, 'proxy' + str(i))
		gajim.config.add_per('proxies', 'proxy' + str(i))

	def on_remove_proxy_button_clicked(self, widget):
		(model, iter) = self.proxies_treeview.get_selection().get_selected()
		if not iter:
			return
		proxy = model.get_value(iter, 0)
		model.remove(iter)
		gajim.config.del_per('proxies', proxy)
		self.xml.get_widget('remove_proxy_button').set_sensitive(False)

	def on_close_button_clicked(self, widget):
		self.window.destroy()
	
	def on_useauth_checkbutton_toggled(self, widget):
		act = widget.get_active()
		self.xml.get_widget('proxyuser_entry').set_sensitive(act)
		self.xml.get_widget('proxypass_entry').set_sensitive(act)

	def on_proxies_treeview_cursor_changed(self, widget):
		#TODO: check if off proxy settings are correct (see http://trac.gajim.org/changeset/1921#file2 line 1221
		(model, iter) = widget.get_selection().get_selected()
		if not iter:
			return
		self.xml.get_widget('remove_proxy_button').set_sensitive(True)
		proxy = model.get_value(iter, 0)
		self.xml.get_widget('proxyname_entry').set_text(proxy)
		proxyhost_entry = self.xml.get_widget('proxyhost_entry')
		proxyport_entry = self.xml.get_widget('proxyport_entry')
		proxyuser_entry = self.xml.get_widget('proxyuser_entry')
		proxypass_entry = self.xml.get_widget('proxypass_entry')
		useauth_checkbutton = self.xml.get_widget('useauth_checkbutton')
		proxyhost_entry.set_text('')
		proxyport_entry.set_text('')
		proxyuser_entry.set_text('')
		proxypass_entry.set_text('')
		useauth_checkbutton.set_active(False)
		self.on_useauth_checkbutton_toggled(useauth_checkbutton)
		if proxy == 'None':
			self.proxyname_entry.set_editable(False)
			self.xml.get_widget('proxytype_combobox').set_sensitive(False)
			self.xml.get_widget('proxy_table').set_sensitive(False)
		else:
			self.proxyname_entry.set_editable(True)
			self.xml.get_widget('proxytype_combobox').set_sensitive(True)
			self.xml.get_widget('proxy_table').set_sensitive(True)
			proxyhost_entry.set_text(gajim.config.get_per('proxies', proxy,
				'host'))
			proxyport_entry.set_text(str(gajim.config.get_per('proxies', proxy,
				'port')))
			proxyuser_entry.set_text(gajim.config.get_per('proxies', proxy,
				'user'))
			proxypass_entry.set_text(gajim.config.get_per('proxies', proxy,
				'pass'))
			#TODO: if we have several proxy type, set the combobox
			if gajim.config.get_per('proxies', proxy, 'user'):
				useauth_checkbutton.set_active(True)

	def on_proxies_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Delete:
			self.on_remove_proxy_button_clicked(widget)

	def on_proxyname_entry_changed(self, widget):
		(model, iter) = self.proxies_treeview.get_selection().get_selected()
		if not iter:
			return
		old_name = model.get_value(iter, 0)
		new_name = widget.get_text()
		if new_name == '':
			return
		if new_name == old_name:
			return
		config = gajim.config.get_per('proxies', old_name)
		gajim.config.del_per('proxies', old_name)
		gajim.config.add_per('proxies', new_name)
		for option in config:
			gajim.config.set_per('proxies', new_name, option,
				config[option][common.config.OPT_VAL])
		model.set_value(iter, 0, new_name)

	def on_proxytype_combobox_changed(self, widget):
		#TODO: if we have several proxy type
		pass

	def on_proxyhost_entry_changed(self, widget):
		value = widget.get_text()
		proxy = self.proxyname_entry.get_text()
		gajim.config.set_per('proxies', proxy, 'host', value)

	def on_proxyport_entry_changed(self, widget):
		value = widget.get_text()
		proxy = self.proxyname_entry.get_text()
		gajim.config.set_per('proxies', proxy, 'port', value)

	def on_proxyuser_entry_changed(self, widget):
		value = widget.get_text()
		proxy = self.proxyname_entry.get_text()
		gajim.config.set_per('proxies', proxy, 'user', value)

	def on_proxypass_entry_changed(self, widget):
		value = widget.get_text()
		proxy = self.proxyname_entry.get_text()
		gajim.config.set_per('proxies', proxy, 'pass', value)


#---------- AccountsWindow class -------------#
class AccountsWindow:
	'''Class for accounts window: list of accounts'''
	def on_accounts_window_destroy(self, widget):
		del self.plugin.windows['accounts'] 

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self, plugin):
		self.plugin = plugin
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'accounts_window', APP)
		self.window = self.xml.get_widget('accounts_window')
		self.accounts_treeview = self.xml.get_widget('accounts_treeview')
		self.modify_button = self.xml.get_widget('modify_button')
		self.remove_button = self.xml.get_widget('remove_button')
		model = gtk.ListStore(str, str,
					bool)
		self.accounts_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1,
					_('Name'), renderer, text = 0)
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1,
					_('Server'), renderer, text = 1)
		self.xml.signal_autoconnect(self)
		self.init_accounts()
		self.window.show_all()

	def on_accounts_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()	

	def init_accounts(self):
		'''initialize listStore with existing accounts'''
		self.modify_button.set_sensitive(False)
		self.remove_button.set_sensitive(False)
		model = self.accounts_treeview.get_model()
		model.clear()
		for account in gajim.connections:
			iter = model.append()
			model.set(iter, 0, account, 1, gajim.config.get_per('accounts',
				account, 'hostname'))

	def on_accounts_treeview_cursor_changed(self, widget):
		'''Activate delete and modify buttons when a row is selected'''
		self.modify_button.set_sensitive(True)
		self.remove_button.set_sensitive(True)

	def on_new_button_clicked(self, widget):
		'''When new button is clicked: open an account information window'''
		if self.plugin.windows.has_key('account_modification'):
			self.plugin.windows['account_modification'].window.present()			
		else:
			self.plugin.windows['account_modification'] = \
				AccountModificationWindow(self.plugin, '')

	def on_remove_button_clicked(self, widget):
		'''When delete button is clicked:
		Remove an account from the listStore and from the config file'''
		sel = self.accounts_treeview.get_selection()
		(model, iter) = sel.get_selected()
		if not iter:
			return
		account = model.get_value(iter, 0)
		if self.plugin.windows[account].has_key('remove_account'):
			self.plugin.windows[account]['remove_account'].window.present()
		else:
			self.plugin.windows[account]['remove_account'] = \
				RemoveAccountWindow(self.plugin, account)

	def on_modify_button_clicked(self, widget):
		'''When modify button is clicked:
		open/show the account modification window for this account'''
		sel = self.accounts_treeview.get_selection()
		(model, iter) = sel.get_selected()
		if not iter:
			return
		account = model.get_value(iter, 0)
		if self.plugin.windows[account].has_key('account_modification'):
			self.plugin.windows[account]['account_modification'].window.present()
		else:
			self.plugin.windows[account]['account_modification'] = \
				AccountModificationWindow(self.plugin, account)

#---------- ServiceRegistrationWindow class -------------#
class ServiceRegistrationWindow:
	'''Class for Service registration window:
	Window that appears when we want to subscribe to a service'''
	def on_cancel_button_clicked(self, widget):
		self.window.destroy()
		
	def draw_table(self):
		'''Draw the table in the window'''
		nbrow = 0
		table = self.xml.get_widget('table')
		for name in self.infos.keys():
			if name in ['key', 'instructions', 'x', 'registered']:
				continue
			if not name:
				continue

			nbrow = nbrow + 1
			table.resize(rows = nbrow, columns = 2)
			label = gtk.Label(name.capitalize() + ':')
			table.attach(label, 0, 1, nbrow - 1, nbrow, 0, 0, 0, 0)
			entry = gtk.Entry()
			entry.set_activates_default(True)
			if self.infos[name]:
				entry.set_text(self.infos[name])
			if name == 'password':
				entry.set_visibility(False)
			table.attach(entry, 1, 2, nbrow - 1, nbrow, 0, 0, 0, 0)
			self.entries[name] = entry
			if nbrow == 1:
				entry.grab_focus()
		table.show_all()
	
	def on_ok_button_clicked(self, widget):
		'''When Ok button is clicked:
		send registration info to the core'''
		for name in self.entries.keys():
			self.infos[name] = self.entries[name].get_text()
		if self.infos.has_key('instructions'):
			del self.infos['instructions']
		if self.infos.has_key('registered'):
			del self.infos['registered']
		else:
			user1 = Contact(jid = self.service, name = self.service,
			groups = ['Transports'], show = 'offline', status = 'offline',
			sub = 'from')
			self.plugin.roster.contacts[self.account][self.service] = [user1]
			self.plugin.roster.add_user_to_roster(self.service, self.account)
		gajim.connections[self.account].register_agent(self.service, self.infos)
		self.window.destroy()
	
	def __init__(self, service, infos, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE,	'service_registration_window', APP)
		self.service = service
		self.infos = infos
		self.plugin = plugin
		self.account = account
		self.window = self.xml.get_widget('service_registration_window')
		if infos.has_key('registered'):
			self.window.set_title(_('Edit %s' % service))
		else:
			self.window.set_title(_('Register to %s' % service))
		self.xml.get_widget('label').set_text(infos['instructions'])
		self.entries = {}
		self.draw_table()
		self.xml.signal_autoconnect(self)
		self.window.show_all()


#---------- ManageEmoticonsWindow class -------------#
class ManageEmoticonsWindow:
	def __init__(self, plugin):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'manage_emoticons_window', APP)
		self.window = self.xml.get_widget('manage_emoticons_window')
		self.plugin = plugin

		#emoticons
		self.emot_tree = self.xml.get_widget('emoticons_treeview')
		model = gtk.ListStore(str, str, gtk.Image)
		model.set_sort_column_id(0, gtk.SORT_ASCENDING)
		self.emot_tree.set_model(model)
		col = gtk.TreeViewColumn(_('Text'))
		self.emot_tree.append_column(col)
		renderer = gtk.CellRendererText()
		renderer.connect('edited', self.on_emot_cell_edited)
		renderer.set_property('editable', True)
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 0)

		col = gtk.TreeViewColumn(_('Image'))
		self.emot_tree.append_column(col)
		renderer = cell_renderer_image.CellRendererImage()
		col.pack_start(renderer, expand = False)
		col.add_attribute(renderer, 'image', 2)
		
		self.fill_emot_treeview()
		self.emot_tree.get_model().connect('row-changed', 
				self.on_emoticons_treemodel_row_changed)

		self.plugin = plugin
		self.xml.signal_autoconnect(self)

	def on_add_remove_emoticons_window_delete_event(self, widget, event):
		self.window.hide()
		self.plugin.init_regexp() # update regexp [emoticons included]
		return True # do NOT destroy the window
	
	def on_close_button_clicked(self, widget):
		self.window.hide()

	def on_emoticons_treemodel_row_changed(self, model, path, iter):
		emots = gajim.config.get_per('emoticons')
		emot = model.get_value(iter, 0).upper()
		if not emot in emots:
			gajim.config.add_per('emoticons', emot)
			self.plugin.init_regexp() # update regexp [emoticons included]
		gajim.config.set_per('emoticons', emot, 'path', model.get_value(iter, 1))
		self.plugin.save_config()

	def image_is_ok(self, image):
		if not os.path.exists(image):
			return False
		img = gtk.Image()
		try:
			img.set_from_file(image)
		except:
			return False
		t = img.get_storage_type()
		if t == gtk.IMAGE_PIXBUF:
			pix = img.get_pixbuf()
		elif t == gtk.IMAGE_ANIMATION:
			pix = img.get_animation().get_static_image()
		else:
			return False

		if pix.get_width() > 24 or pix.get_height() > 24:
			dialogs.ErrorDialog(_('Image is too big'), _('Image for emoticon has to be less than or equal to 24 pixels in width and 24 in height.')).get_response()
			return False
		return True

	def fill_emot_treeview(self):
		model = self.emot_tree.get_model()
		model.clear()
		emots = gajim.config.get_per('emoticons')
		for emot in emots:
			file = gajim.config.get_per('emoticons', emot, 'path')
			iter = model.append((emot, file, None))
			if not os.path.exists(file):
				continue
			img = gtk.Image()
			img.show()
			if file.find('.gif') != -1:
				pix = gtk.gdk.PixbufAnimation(file)
				img.set_from_animation(pix)
			else:
				pix = gtk.gdk.pixbuf_new_from_file(file)
				img.set_from_pixbuf(pix)
			model.set(iter, 2, img)

	def on_emot_cell_edited(self, cell, row, new_text):
		emots = gajim.config.get_per('emoticons')
		model = self.emot_tree.get_model()
		iter = model.get_iter_from_string(row)
		old_text = model.get_value(iter, 0)
		if old_text in emots:
			gajim.config.del_per('emoticons', old_text)
		emot = new_text.upper()
		if emot in emots:
			model.remove(iter)
		else:
			gajim.config.add_per('emoticons', emot)
			self.plugin.init_regexp() # update regexp [emoticons included]
			gajim.config.set_per('emoticons', emot, 'path',
				model.get_value(iter, 1))
			model.set_value(iter, 0, emot)
		self.plugin.save_config()

	def update_preview(self, widget):
		path_to_file = widget.get_preview_filename()
		widget.get_preview_widget().set_from_file(path_to_file)

	def on_set_image_button_clicked(self, widget, data=None):
		(model, iter) = self.emot_tree.get_selection().get_selected()
		if not iter:
			return
		file = model.get_value(iter, 1)
		dialog = gtk.FileChooserDialog(_('Choose image'), None,
					gtk.FILE_CHOOSER_ACTION_OPEN,
					(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
					gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)
		filter = gtk.FileFilter()
		filter.set_name(_('All files'))
		filter.add_pattern('*')
		dialog.add_filter(filter)

		filter = gtk.FileFilter()
		filter.set_name(_('Images'))
		filter.add_mime_type('image/png')
		filter.add_mime_type('image/jpeg')
		filter.add_mime_type('image/gif')
		filter.add_pattern('*.png')
		filter.add_pattern('*.jpg')
		filter.add_pattern('*.gif')
		filter.add_pattern('*.tif')
		filter.add_pattern('*.xpm')
		dialog.add_filter(filter)
		dialog.set_filter(filter)
		dialog.set_use_preview_label(False)
		dialog.set_preview_widget(gtk.Image())
		dialog.connect('selection-changed', self.update_preview)

		file = os.path.join(os.getcwd(), file)
		dialog.set_filename(file)
		file = ''	
		ok = False
		while not ok:
			response = dialog.run()
			if response == gtk.RESPONSE_OK:
				file = dialog.get_filename()
				if self.image_is_ok(file):
					ok = True
			else:
				file = None
				ok = True
		dialog.destroy()
		if file:
			model.set_value(iter, 1, file)
			img = gtk.Image()
			img.show()
			if file.find('.gif') != -1:
				pix = gtk.gdk.PixbufAnimation(file)
				img.set_from_animation(pix)
			else:
				pix = gtk.gdk.pixbuf_new_from_file(file)
				img.set_from_pixbuf(pix)
			model.set(iter, 2, img)

	def on_button_new_emoticon_clicked(self, widget, data=None):
		model = self.emot_tree.get_model()
		iter = model.append()
		model.set(iter, 0, 'EMOTICON', 1, '')
		col = self.emot_tree.get_column(0)
		self.emot_tree.set_cursor(model.get_path(iter), col, True)

	def on_button_remove_emoticon_clicked(self, widget, data=None):
		(model, iter) = self.emot_tree.get_selection().get_selected()
		if not iter:
			return
		gajim.config.del_per('emoticons', model.get_value(iter, 0))
		self.plugin.init_regexp() # update regexp [emoticons included]
		self.plugin.save_config()
		model.remove(iter)

	def on_emoticons_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Delete:
			self.on_button_remove_emoticon_clicked(widget)


#---------- ServiceDiscoveryWindow class -------------#
class ServiceDiscoveryWindow:
	'''Class for Service Discovery Window:
	to know the services on a server'''
	def on_service_discovery_window_destroy(self, widget):
		del self.plugin.windows[self.account]['disco']

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self, plugin, account):
		self.plugin = plugin
		self.account = account
		self.agent_infos = {}
		if gajim.connections[account].connected < 2:
			dialogs.ErrorDialog(_('You are not connected to the server'),
_('Without a connection, you can not browse available services')).get_response()
			raise RuntimeError, 'You must be connected to browse services'
		xml = gtk.glade.XML(GTKGUI_GLADE, 'service_discovery_window', APP)
		self.window = xml.get_widget('service_discovery_window')
		if len(gajim.connections):
			self.window.set_title(_('Service Discovery using %s account') %account)
		else:
			self.window.set_title(_('Service Discovery'))
		self.services_treeview = xml.get_widget('services_treeview')
		self.join_button = xml.get_widget('join_button')
		self.register_button = xml.get_widget('register_button')
		self.address_comboboxentry = xml.get_widget('address_comboboxentry')
		self.address_comboboxentry_entry = self.address_comboboxentry.child
		self.address_comboboxentry_entry.set_activates_default(True)
		
		model = gtk.TreeStore(str, str, str)
		model.set_sort_column_id(0, gtk.SORT_ASCENDING)
		self.services_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		col = self.services_treeview.insert_column_with_attributes(-1, 
			_('Name'), renderer, text = 0)
		col.set_resizable(True)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		col = self.services_treeview.insert_column_with_attributes(-1, 
			_('Service'), renderer, text = 1)
		col.set_resizable(True)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		col = self.services_treeview.insert_column_with_attributes(-1,
			_('Node'), renderer, text = 2)
		col.set_resizable(True)

		self.address_comboboxentry = xml.get_widget('address_comboboxentry')
		liststore = gtk.ListStore(str)
		self.address_comboboxentry.set_model(liststore)
		self.address_comboboxentry.set_text_column(0)
		self.latest_addresses = gajim.config.get('latest_disco_addresses').split()
		server_address = gajim.config.get_per('accounts', self.account,
			'hostname')
		if server_address in self.latest_addresses:
			self.latest_addresses.remove(server_address)
		self.latest_addresses.insert(0, server_address)
		if len(self.latest_addresses) > 10:
			self.latest_addresses = self.latest_addresses[0:10]
		for j in self.latest_addresses:
			self.address_comboboxentry.append_text(j)
		self.address_comboboxentry.child.set_text(server_address)

		self.register_button.set_sensitive(False)
		self.join_button.set_sensitive(False)
		xml.signal_autoconnect(self)
		self.browse(server_address)
		self.window.show_all()
		
	def browse(self, jid, node = ''):
		'''Send a request to the core to know the available services'''
		model = self.services_treeview.get_model()
		if not model.get_iter_first():
			# we begin to fill the treevier with the first line
			iter = model.append(None, (jid, jid, node))
			self.agent_infos[jid] = {'features' : []}
		gajim.connections[self.account].request_agents(jid, node)
	
	def agents(self, agents):
		'''When list of available agent arrive:
		Fill the treeview with it'''
		model = self.services_treeview.get_model()
		for agent in agents:
			node = ''
			if agent.has_key('node'):
				node = agent['node']
			iter = model.append(None, (agent['name'], agent['jid'], node))
			self.agent_infos[agent['jid'] + node] = {'features' : []}

	def iter_is_visible(self, iter):
		if not iter:
			return False
		model = self.services_treeview.get_model()
		iter = model.iter_parent(iter)
		while iter:
			if not self.services_treeview.row_expanded(model.get_path(iter)):
				return False
			iter = model.iter_parent(iter)
		return True

	def on_services_treeview_row_expanded(self, widget, iter, path):
		model = self.services_treeview.get_model()
		jid = model.get_value(iter, 1)
		child = model.iter_children(iter)
		while child:
			child_jid = model.get_value(child, 1)
			child_node = model.get_value(child, 2)
			# We never requested its infos
			if not self.agent_infos[child_jid + child_node].has_key('features'):
				self.browse(child_jid, child_node)
			child = model.iter_next(child)
	
	def agent_info_info(self, agent, node, identities, features):
		'''When we recieve informations about an agent, but not its items'''
		model = self.services_treeview.get_model()
		iter = model.get_iter_root()
		# We look if this agent is in the treeview
		while (iter):
			if agent == model.get_value(iter, 1) and node == model.get_value(
					iter, 2):
				break
			if model.iter_has_child(iter):
				iter = model.iter_children(iter)
			else:
				if not model.iter_next(iter):
					iter = model.iter_parent(iter)
				if iter:
					iter = model.iter_next(iter)
		if not iter: #If it is not we stop
			return
		self.agent_infos[agent + node]['features'] = features
		if len(identities):
			self.agent_infos[agent + node]['identities'] = identities
			if identities[0].has_key('name'):
				model.set_value(iter, 0, identities[0]['name'])
		self.on_services_treeview_cursor_changed(self.services_treeview)

	def agent_info_items(self, agent, node, items, do_browse = True):
		'''When we recieve items about an agent'''
		model = self.services_treeview.get_model()
		iter = model.get_iter_root()
		# We look if this agent is in the treeview
		while (iter):
			if agent == model.get_value(iter, 1) and node == model.get_value(
					iter, 2):
				break
			if model.iter_has_child(iter):
				iter = model.iter_children(iter)
			else:
				if not model.iter_next(iter):
					iter = model.iter_parent(iter)
				if iter:
					iter = model.iter_next(iter)
		if not iter: #If it is not, we stop
			return
		expand = False
		if len(model.get_path(iter)) == 1:
			expand = True
		for item in items:
			name = ''
			if item.has_key('name'):
				name = item['name']
			node = ''
			if item.has_key('node'):
				node = item['node']
			# We look if this item is already in the treeview
			iter_child = model.iter_children(iter)
			while iter_child:
				if item['jid'] == model.get_value(iter_child, 1) and \
						node == model.get_value(iter_child, 2):
					break
				iter_child = model.iter_next(iter_child)
			if not iter_child: # If it is not we add it
				iter_child = model.append(iter, (name, item['jid'], node))
			self.agent_infos[item['jid'] + node] = {'identities': [item]}
			if self.iter_is_visible(iter_child) and not expand and do_browse:
				self.browse(item['jid'], node)
		if expand:
			self.services_treeview.expand_row((model.get_path(iter)), False)

	def agent_info(self, agent, identities, features, items):
		'''When we recieve informations about an agent'''
		self.agent_info_info(agent, '', identities, features)
		self.agent_info_items(agent, '', items, False)

	def on_refresh_button_clicked(self, widget):
		'''When refresh button is clicked: refresh list: clear and rerequest it'''
		self.services_treeview.get_model().clear()
		jid = self.address_comboboxentry.child.get_text()
		self.browse(jid)

	def on_address_comboboxentry_changed(self, widget):
		'is executed on each keypress'
		if self.address_comboboxentry.get_active() != -1:
			# user selected one of the entries so do auto-visit
			self.services_treeview.get_model().clear()
			server_address = self.address_comboboxentry.child.get_text()
			self.browse(server_address)

	def on_services_treeview_row_activated(self, widget, path, col = 0):
		'''When a row is activated: Register or join the selected agent'''
		#if both buttons are sensitive, it will register [default]
		if self.register_button.get_property('sensitive'):
			self.on_register_button_clicked(widget)
		elif self.join_button.get_property('sensitive'):
			self.on_join_button_clicked(widget)

	def on_join_button_clicked(self, widget):
		'''When we want to join a conference:
		Ask specific informations about the selected agent and close the window'''
		model, iter = self.services_treeview.get_selection().get_selected()
		if not iter:
			return
		service = model.get_value(iter, 1)
		room = ''
		if service.find('@') != -1:
			services = service.split('@')
			room = services[0]
			service = services[1]
		if not self.plugin.windows[self.account].has_key('join_gc'):
			dialogs.JoinGroupchatWindow(self.plugin, self.account, service, room)
		else:
			self.plugin.windows[self.account]['join_gc'].window.present()

	def on_register_button_clicked(self, widget):
		'''When we want to register an agent:
		Ask specific informations about the selected agent and close the window'''
		model, iter = self.services_treeview.get_selection().get_selected()
		if not iter :
			return
		service = model.get_value(iter, 1)
		gajim.connections[self.account].request_register_agent_info(service)

		self.window.destroy()
	
	def on_services_treeview_cursor_changed(self, widget):
		'''When we select a row :
		activate buttons if needed'''
		self.join_button.set_sensitive(False)
		self.register_button.set_sensitive(False)
		model, iter = self.services_treeview.get_selection().get_selected()
		if not iter:
			return
		path = model.get_path(iter)
		if len(path) == 1: # we selected the jabber server
			return
		jid = model.get_value(iter, 1)
		node = model.get_value(iter, 2)
		registered_transports = []
		contacts = self.plugin.roster.contacts[self.account]
		for j in contacts:
			if 'Transports' in contacts[j][0].groups:
				registered_transports.append(j)
		if jid in registered_transports:
			self.register_button.set_label(_('_Edit'))
		else:
			self.register_button.set_label(_('Re_gister'))
		if self.agent_infos[jid + node].has_key('features'):
			if common.xmpp.NS_REGISTER in self.agent_infos[jid + node] \
					['features']:
				self.register_button.set_sensitive(True)
		if self.agent_infos[jid + node].has_key('identities') and \
				len(self.agent_infos[jid + node]['identities']):
			if self.agent_infos[jid + node]['identities'][0].has_key('category'):
				if self.agent_infos[jid + node]['identities'][0]['category'] == \
						'conference':
					self.join_button.set_sensitive(True)
	
	def on_go_button_clicked(self, widget):
		server_address = self.address_comboboxentry.child.get_text()
		if server_address in self.latest_addresses:
			self.latest_addresses.remove(server_address)
		self.latest_addresses.insert(0, server_address)
		if len(self.latest_addresses) > 10:
			self.latest_addresses = self.latest_addresses[0:10]
		self.address_comboboxentry.get_model().clear()
		for j in self.latest_addresses:
			self.address_comboboxentry.append_text(j)
		gajim.config.set('latest_disco_addresses',
			' '.join(self.latest_addresses))
		self.services_treeview.get_model().clear()
		self.browse(server_address)
		self.plugin.save_config()

#---------- GroupchatConfigWindow class -------------#
class GroupchatConfigWindow:
	'''GroupchatConfigWindow class'''
	def __init__(self, plugin, account, room_jid, config):
		self.plugin = plugin
		self.account = account
		self.room_jid = room_jid
		self.config = config
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'groupchat_config_window', APP)
		self.window = self.xml.get_widget('groupchat_config_window')
		self.config_table = self.xml.get_widget('config_table')
		self.fill_table()
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_groupchat_config_window_destroy(self, widget):
		del self.plugin.windows[self.account]['gc_config'][self.room_jid]

	def on_close_button_clicked(self, widget):
		self.window.destroy()
	
	def on_change_button_clicked(self, widget):
		gajim.connections[self.account].send_gc_config(self.room_jid, self.config)
		self.window.destroy()

	def on_checkbutton_toggled(self, widget, index):
		self.config[index]['values'][0] = widget.get_active()

	def on_combobox_changed(self, widget, index):
		self.config[index]['values'][0] = self.config[index]['options'][ \
			widget.get_active()]['values'][0]

	def on_entry_changed(self, widget, index):
		self.config[index]['values'][0] = widget.get_text()

	def on_textbuffer_changed(self, widget, index):
		begin, end = widget.get_bounds()
		self.config[index]['values'][0] = widget.get_text(begin, end)
		
	def fill_table(self):
		if self.config.has_key('title'):
			self.window.set_title(self.config['title'])
		if self.config.has_key('instructions'):
			self.xml.get_widget('instructions_label').set_text(
				self.config['instructions'])
		i = 0
		while self.config.has_key(i):
			if not self.config[i].has_key('type'):
				i += 1
				continue
			ctype = self.config[i]['type']
			if ctype == 'hidden':
				i += 1
				continue
			nbrows = self.config_table.get_property('n-rows')
			self.config_table.resize(nbrows + 1, 2)
			if self.config[i].has_key('label'):
				label = gtk.Label(self.config[i]['label'])
				label.set_alignment(0.0, 0.5)
				self.config_table.attach(label, 0, 1, nbrows, nbrows + 1, 
					gtk.FILL	| gtk.SHRINK)
			desc = None
			if self.config[i].has_key('desc'):
				desc = self.config[i]['desc']
			max = 1
			if ctype == 'boolean':
				widget = gtk.CheckButton(desc, False)
				widget.set_active(self.config[i]['values'][0])
				widget.connect('toggled', self.on_checkbutton_toggled, i)
				max = 2
			elif ctype == 'fixed':
				widget = gtk.Label('\n'.join(self.config[i]['values']))
				widget.set_alignment(0.0, 0.5)
				max = 4
			elif ctype == 'jid-multi':
				#TODO
				widget = gtk.Label('')
			elif ctype == 'jid-single':
				#TODO
				widget = gtk.Label('')
			elif ctype == 'list-multi':
				#TODO
				widget = gtk.Label('')
			elif ctype == 'list-single':
				widget = gtk.combo_box_new_text()
				widget.connect('changed', self.on_combobox_changed, i)
				index = 0
				j = 0
				while self.config[i]['options'].has_key(j):
					if self.config[i]['options'][j]['values'][0] == \
						self.config[i]['values'][0]:
						index = j
					widget.append_text(self.config[i]['options'][j]['label'])
					j += 1
				widget.set_active(index)
				max = 3
			elif ctype == 'text-multi':
				widget = gtk.TextView()
				widget.get_buffer().connect('changed', self.on_textbuffer_changed, \
					i)
				widget.get_buffer().set_text('\n'.join(self.config[i]['values']))
				max = 4
			elif ctype == 'text-private':
				widget = gtk.Entry()
				widget.connect('changed', self.on_entry_changed, i)
				widget.set_text(self.config[i]['values'][0])
				widget.set_visibility(False)
				max = 3
			elif ctype == 'text-single':
				widget = gtk.Entry()
				widget.connect('changed', self.on_entry_changed, i)
				widget.set_text(self.config[i]['values'][0])
				max = 3
			i += 1
			if max < 4:
				self.config_table.attach(widget, 1, max,
							nbrows, nbrows + 1,
							gtk.FILL | gtk.SHRINK)
				widget = gtk.Label()
				self.config_table.attach(widget, max, 4,
							nbrows, nbrows + 1)
			else:
				self.config_table.attach(widget, 1, max,
							nbrows, nbrows + 1)
		self.config_table.show_all()

#---------- RemoveAccountWindow class -------------#
class RemoveAccountWindow:
	'''ask for removing from gajim only or from gajim and server too
	and do removing of the account given'''
	
	def on_remove_account_window_destroy(self, widget):
		if self.plugin.windows.has_key(self.account):
			del self.plugin.windows[self.account]['remove_account']

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()
	
	def __init__(self, plugin, account):
		self.plugin = plugin
		self.account = account
		xml = gtk.glade.XML(GTKGUI_GLADE, 'remove_account_window', APP)
		self.window = xml.get_widget('remove_account_window')
		self.remove_and_unregister_radiobutton = xml.get_widget(
														'remove_and_unregister_radiobutton')
		self.window.set_title(_('Removing %s account') % self.account)
		xml.signal_autoconnect(self)
		self.window.show_all()

	def on_remove_button_clicked(self, widget):
		if gajim.connections[self.account].connected:
			dialog = dialogs.ConfirmationDialog(
				_('Account "%s" is connected to the server' % self.account),
				_('If you remove it, the connection will be lost.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return
			gajim.connections[self.account].change_status('offline', 'offline')
		
		if self.remove_and_unregister_radiobutton.get_active():  
			gajim.connections[self.account].unregister_account()
		del gajim.connections[self.account]
		gajim.config.del_per('accounts', self.account)
		self.plugin.save_config()
		del self.plugin.windows[self.account]
		del self.plugin.queues[self.account]
		del self.plugin.nicks[self.account]
		del self.plugin.allow_notifications[self.account]
		del self.plugin.roster.groups[self.account]
		del self.plugin.roster.contacts[self.account]
		del self.plugin.roster.to_be_removed[self.account]
		del self.plugin.roster.newly_added[self.account]
		self.plugin.roster.draw_roster()
		if self.plugin.windows.has_key('accounts'):
			self.plugin.windows['accounts'].init_accounts()
		self.window.destroy()

#---------- ManageBookmarksWindow class -------------#
class ManageBookmarksWindow:
	def __init__(self, plugin):
		self.plugin = plugin
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'manage_bookmarks_window', APP)
		self.window = self.xml.get_widget('manage_bookmarks_window')

		#Account-JID, RoomName, Room-JID, Autojoin, Passowrd, Nick
		self.treestore = gtk.TreeStore(str, str, str, bool, str, str)

		#Store bookmarks in treeview.
		for account in gajim.connections:
			if gajim.connections[account].connected <= 1:
				continue
			iter = self.treestore.append(None, [None, account,None,
							    None, None, None])

			for bookmark in gajim.connections[account].bookmarks:
				if bookmark['name'] == '':
					#No name was given for this bookmark.
					#Use the first part of JID instead...
					name = bookmark['jid'].split("@")[0]
					bookmark['name'] = name

				#Convert '1'/'0' to True/False
				autojoin = bool(int(bookmark['autojoin']))
				
				self.treestore.append( iter, [
						account,
						bookmark['name'],
						bookmark['jid'],
						autojoin,
						bookmark['password'],
						bookmark['nick'] ])

		self.view = self.xml.get_widget('bookmarks_treeview')
		self.view.set_model(self.treestore)
		self.view.expand_all()
		
		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn('Bookmarks', renderer, text=1)
		self.view.append_column(column)

		self.selection = self.view.get_selection()
		self.selection.connect('changed', self.bookmark_selected)

		
		#Prepare input fields
		self.title_entry = self.xml.get_widget('title_entry')
		self.title_entry.connect('changed', self.on_title_entry_changed)
		self.nick_entry = self.xml.get_widget('nick_entry')
		self.nick_entry.connect('changed', self.on_nick_entry_changed)
		self.server_entry = self.xml.get_widget('server_entry')
		self.server_entry.connect('changed', self.on_server_entry_changed)
		self.room_entry = self.xml.get_widget('room_entry')
		self.room_entry.connect('changed', self.on_room_entry_changed)
		self.pass_entry = self.xml.get_widget('pass_entry')
		self.pass_entry.connect('changed', self.on_pass_entry_changed)
		self.autojoin_checkbutton = self.xml.get_widget('autojoin_checkbutton')
		
		self.xml.signal_autoconnect(self)
		self.window.show_all()
	
	def on_bookmarks_treeview_button_press_event(self, widget, event):
		(model, iter) = self.selection.get_selected()
		if not iter:
			#Removed a bookmark before
			return

		if model.iter_parent(iter):
			#The currently selected node is a bookmark
			return not self.check_valid_bookmark()

	def on_manage_bookmarks_window_destroy(self, widget, event):
		del self.plugin.windows['manage_bookmarks']

	def on_add_bookmark_button_clicked(self,widget):
		'''
		Add a new bookmark.
		'''
		#Get the account that is currently used 
		#(the parent of the currently selected item)
		(model, iter) = self.selection.get_selected()
		if not iter: #Nothing selected, do nothing
			return

		parent = model.iter_parent(iter)

		if parent:
			#We got a bookmark selected, so we add_to the parent
			add_to = parent
		else:
			#No parent, so we got an account -> add to this.
			add_to = iter

		account = model.get_value(add_to, 1)
		self.treestore.append(add_to, [account,_('New Room'), '', False, '', ''])

		self.view.expand_row(model.get_path(add_to), True)

	def on_remove_bookmark_button_clicked(self, widget):
		'''
		Remove selected bookmark.
		'''
		(model, iter) = self.selection.get_selected()
		if not iter: #Nothing selected
			return

		if not model.iter_parent(iter):
			#Don't remove account iters
			return

		model.remove(iter)
		self.clear_fields()

	def check_valid_bookmark(self):
		'''
		Check if all neccessary fields are entered correctly.
		'''
		(model, iter) = self.selection.get_selected()

		if not model.iter_parent(iter):
			#Account data can't be changed
			return

		if self.server_entry.get_text() == '' or self.room_entry.get_text() == '':
			dialogs.ErrorDialog(_('This bookmark has invalid data'),
_('Please be sure to fill out server and room fields or remove this bookmark.')).get_response()
			return False

		return True

	def on_ok_button_clicked(self, widget):
		'''
		Parse the treestore data into our new bookmarks array,
		then send the new bookmarks to the server.
		'''
		(model, iter) = self.selection.get_selected()
		if iter and model.iter_parent(iter):
			#bookmark selected, check it
			if not self.check_valid_bookmark():
				return

		for account in self.treestore:
			gajim.connections[account[1]].bookmarks = []

			for bm in account.iterchildren():
				#Convert True/False/None to '1' or '0'
				autojoin = str(int(bm[3]))
				
				#create the bookmark-dict
				bmdict = { 'name': bm[1], 'jid': bm[2], 'autojoin': autojoin,
					'password': bm[4], 'nick': bm[5] }
				
				gajim.connections[account[1]].bookmarks.append(bmdict)

			gajim.connections[account[1]].store_bookmarks()
		self.plugin.roster.make_menu()
		self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def bookmark_selected(self, selection):
		'''
		Fill in the bookmark's data into the fields.
		'''
		(model, iter) = selection.get_selected()

		if not iter:
			#After removing the last bookmark for one account
			#this will be None, so we will just:
			return

		widgets = [ self.title_entry, self.nick_entry, self.room_entry,
			self.server_entry, self.pass_entry, self.autojoin_checkbutton ]

		if model.iter_parent(iter):
			#make the fields sensitive
			for field in widgets:
				field.set_sensitive(True)
		else:
			#Top-level has no data (it's the account fields)
			#clear fields & make them insensitive
			self.clear_fields()
			for field in widgets:
				field.set_sensitive(False)
			return

		#Fill in the data for childs
		self.title_entry.set_text(model.get_value(iter, 1))
		room_jid = model.get_value(iter, 2)
		try:
			(room, server) = room_jid.split('@')
		except ValueError:
			#We just added this one
			room = ''
			server = ''
		self.room_entry.set_text(room)
		self.server_entry.set_text(server)
	
		self.autojoin_checkbutton.set_active(model.get_value(iter, 3))
		self.pass_entry.set_text(model.get_value(iter, 4))
		self.nick_entry.set_text(model.get_value(iter, 5))

	def on_title_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter: #After removing a bookmark, we got nothing selected
			if model.iter_parent(iter):
				#Don't clear the title field for account nodes
				model.set_value(iter, 1, self.title_entry.get_text())

	def on_nick_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model.set_value(iter, 5, self.nick_entry.get_text())
	
	def on_server_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			room_jid = self.room_entry.get_text() + '@' + \
				self.server_entry.get_text()
			model.set_value(iter, 2, room_jid)

	def on_room_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			room_jid = self.room_entry.get_text() + '@' + \
				self.server_entry.get_text()
			model.set_value(iter, 2, room_jid)

	def on_pass_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model.set_value(iter, 4, self.pass_entry.get_text())

	def on_autojoin_checkbutton_toggled(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model.set_value(iter, 3, self.autojoin_checkbutton.get_active())

	def clear_fields(self):
		widgets = [ self.title_entry, self.nick_entry, self.room_entry,
			self.server_entry, self.pass_entry ]
		for field in widgets:
			field.set_text('')
		self.autojoin_checkbutton.set_active(False)
