##	plugins/config.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@lagaule.org>
## 	- Vincent Hanquez <tab@snarc.org>
##  	- Nikos Kouremenos <nkour@jabber.org>
##		- Alex Podaras <bigpod@jabber.org>
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
import common.sleepy
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

from dialogs import *
import gtkgui

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'


class preferences_window:
	"""Class for Preferences window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['preferences']
	
	def on_tray_icon_checkbutton_toggled(self, widget):
		"""On Tray Icon Checkbutton Toggled"""
		if widget.get_active():
			self.plugin.config['trayicon'] = 1
			self.plugin.show_systray()
		else:
			self.plugin.config['trayicon'] = 0
			self.plugin.hide_systray()
		self.plugin.send('CONFIG', None, ('GtkGui', self.plugin.config, 'GtkGui'))
		self.plugin.roster.draw_roster()
	
	def on_save_position_checkbutton_toggled(self, widget):
		"""On Save Position Checkbutton Toggled"""
		if widget.get_active():
			self.plugin.config['saveposition'] = 1
		else:
			self.plugin.config['saveposition'] = 0
	
	def on_merge_checkbutton_toggled(self, widget):
		"""On Merge Accounts Checkbutton Toggled"""
		if widget.get_active():
			self.plugin.config['mergeaccounts'] = 1
		else:
			self.plugin.config['mergeaccounts'] = 0
		self.plugin.roster.regroup = self.plugin.config['mergeaccounts']
	
	def on_iconstyle_combobox_changed(self, widget, path):
		model = widget.get_model()
		icon_string = model[path][0]
		self.plugin.config['iconstyle'] = icon_string
		self.plugin.roster.mkpixbufs()
		
	def on_account_text_colorbutton_color_set(self, widget):
		"""Take The Color For The Account Text"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['accounttextcolor'] = color_string
		self.plugin.roster.draw_roster()
	
	def on_group_text_colorbutton_color_set(self, widget):
		"""Take The Color For The Group Text"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['grouptextcolor'] = color_string
		self.plugin.roster.draw_roster()

	def on_user_text_colorbutton_color_set(self, widget):
		"""Take The Color For The User Text"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['usertextcolor'] = color_string
		self.plugin.roster.draw_roster()

	def on_account_text_bg_colorbutton_color_set(self, widget):
		"""Take The Color For The Background Of Account Text"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['accountbgcolor'] = color_string
		self.plugin.roster.draw_roster()
	
	def on_group_text_bg_colorbutton_color_set(self, widget):
		"""Take The Color For The Background Of Group Text"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['groupbgcolor'] = color_string
		self.plugin.roster.draw_roster()
	
	def on_user_text_bg_colorbutton_color_set(self, widget):
		"""Take The Color For The Background Of User Text"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['userbgcolor'] = color_string
		self.plugin.roster.draw_roster()
	
	def on_account_text_fontbutton_font_set(self, widget):
		"""Take The Font For The User Text"""
		font_string = widget.get_font_name()
		self.plugin.config['accountfont'] = font_string
		self.plugin.roster.draw_roster()

	def on_group_text_fontbutton_font_set(self, widget):
		"""Take The Font For The Group Text"""
		font_string = widget.get_font_name()
		self.plugin.config['groupfont'] = font_string
		self.plugin.roster.draw_roster()
	
	def on_user_text_fontbutton_font_set(self, widget):
		"""Take The Font For The User Text"""
		font_string = widget.get_font_name()
		self.plugin.config['userfont'] = font_string
		self.plugin.roster.draw_roster()
	
	def on_reset_colors_and_fonts_button_clicked(self, widget):
		defaults = self.plugin.default_config
		self.plugin.config['accounttextcolor'] = defaults['accounttextcolor']
		self.plugin.config['grouptextcolor'] = defaults['grouptextcolor']
		self.plugin.config['usertextcolor'] = defaults['usertextcolor']
		self.plugin.config['accountbgcolor'] = defaults['accountbgcolor']
		self.plugin.config['groupbgcolor'] = defaults['groupbgcolor']
		self.plugin.config['userbgcolor'] = defaults['userbgcolor']
		self.plugin.config['accountfont'] = defaults['accountfont']
		self.plugin.config['groupfont'] = defaults['groupfont']
		self.plugin.config['userfont'] = defaults['userfont']
		self.xml.get_widget('account_text_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['accounttextcolor']))		
		self.xml.get_widget('group_text_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['grouptextcolor']))		
		self.xml.get_widget('user_text_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['usertextcolor']))	
		self.xml.get_widget('account_text_bg_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['accountbgcolor']))		
		self.xml.get_widget('group_text_bg_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['groupbgcolor']))		
		self.xml.get_widget('user_text_bg_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['userbgcolor']))
		self.xml.get_widget('account_text_fontbutton').set_font_name(\
			defaults['accountfont'])		
		self.xml.get_widget('group_text_fontbutton').set_font_name(\
			defaults['groupfont'])
		self.xml.get_widget('user_text_fontbutton').set_font_name(\
			defaults['userfont'])
		self.plugin.roster.draw_roster()
	
	def on_use_tabbed_chat_window_checkbutton_toggled(self, widget):
		"""On Use Tabbed Chat Window Checkbutton Toggled"""
		buf1 = {}
		buf2 = {}
		jids = {}
		if widget.get_active():
			#FIXME Does not work
			#save buffers and close windows
#			for acct in self.plugin.accounts:
#				buf1[acct] = {}
#				buf2[acct] = {}
#				jids[acct] = self.plugin.windows[acct]['chats'].keys()
#				for jid in jids[acct]:
#					buf1[acct][jid] = self.plugin.windows[acct]['chats'][jid].\
#						xmls[jid].get_widget('conversation_textview').get_buffer()
#					buf2[acct][jid] = self.plugin.windows[acct]['chats'][jid].\
#						xmls[jid].get_widget('message_textview').get_buffer()
#					self.plugin.windows[acct]['chats'][jid].window.destroy()
			self.plugin.config['usetabbedchat'] = 1
			#open new tabbed chat windows
#			for acct in self.plugin.accounts:
#				for jid in jids[acct]:
#					user = self.plugin.roster.contacts[acct][jid][0]
#					self.plugin.roster.new_chat(user, acct)
#					self.plugin.windows[acct]['chats'][jid].xmls[jid].\
#						get_widget('conversation_textview').set_buffer(\
#							buf1[acct][jid])
#					self.plugin.windows[acct]['chats'][jid].xmls[jid].\
#						get_widget('message_textview').set_buffer(buf2[acct][jid])
		else:
			#save buffers and close tabbed chat windows
#			for acct in self.plugin.accounts:
#				buf1[acct] = {}
#				buf2[acct] = {}
#				jids[acct] = self.plugin.windows[acct]['chats'].keys()
#				if 'tabbed' in jids[acct]:
#					jids[acct].remove('tabbed')
#					for jid in jids[acct]:
#						buf1[acct][jid] = self.plugin.windows[acct]['chats'][jid].\
#							xmls[jid].get_widget('conversation_textview').get_buffer()
#						buf2[acct][jid] = self.plugin.windows[acct]['chats'][jid].\
#							xmls[jid].get_widget('message_textview').get_buffer()
#					self.plugin.windows[acct]['chats']['tabbed'].window.destroy()
			self.plugin.config['usetabbedchat'] = 0
			#open new tabbed chat windows
#			for acct in self.plugin.accounts:
#				for jid in jids[acct]:
#					user = self.plugin.roster.contacts[acct][jid][0]
#					self.plugin.roster.new_chat(user, acct)
#					self.plugin.windows[acct]['chats'][jid].xmls[jid].\
#						get_widget('conversation_textview').set_buffer(\
#							buf1[acct][jid])
#					self.plugin.windows[acct]['chats'][jid].xmls[jid].\
#						get_widget('message_textview').set_buffer(buf2[acct][jid])
	
	def update_text_tags(self):
		"""Update Opened Chat Windows"""
		for a in self.plugin.accounts.keys():
			if self.plugin.windows[a]['chats'].has_key('tabbed'):
				self.plugin.windows[a]['chats']['tabbed'].update_tags()
			else:
				for jid in self.plugin.windows[a]['chats'].keys():
					self.plugin.windows[a]['chats'][jid].update_tags()
	
	def update_print_time(self):
		"""Update Opened Chat Windows"""
		for a in self.plugin.accounts.keys():
			if self.plugin.windows[a]['chats'].has_key('tabbed'):
				self.plugin.windows[a]['chats']['tabbed'].update_print_time()
			else:
				for jid in self.plugin.windows[a]['chats'].keys():
					self.plugin.windows[a]['chats'][jid].update_print_time()
	
	def on_incoming_msg_colorbutton_color_set(self, widget):
		"""Take The Color For The Incoming Messages"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['inmsgcolor'] = color_string
		self.update_text_tags()
		
	def on_outgoing_msg_colorbutton_color_set(self, widget):
		"""Take The Color For The Outgoing Messages"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['outmsgcolor'] = color_string
		self.update_text_tags()
	
	def on_status_msg_colorbutton_color_set(self, widget):
		"""Take The Color For The Status Messages"""
		color = widget.get_color()
		color_string = '#' + (hex(color.red) + '0')[2:4] + \
			(hex(color.green) + '0')[2:4] + (hex(color.blue) + '0')[2:4]
		self.plugin.config['statusmsgcolor'] = color_string
		self.update_text_tags()
	
	def on_reset_colors_button_clicked(self, widget):
		defaults = self.plugin.default_config
		self.plugin.config['inmsgcolor'] = defaults['inmsgcolor']
		self.plugin.config['outmsgcolor'] = defaults['outmsgcolor']
		self.plugin.config['statusmsgcolor'] = defaults['statusmsgcolor']
		self.xml.get_widget('incoming_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['inmsgcolor']))		
		self.xml.get_widget('outgoing_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['outmsgcolor']))		
		self.xml.get_widget('status_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(defaults['statusmsgcolor']))		
		self.update_text_tags()

	def on_time_never_radiobutton_toggled(self, widget):
		if widget.get_active():
			self.plugin.config['print_time'] = 'never'
		self.update_print_time()

	def on_time_sometimes_radiobutton_toggled(self, widget):
		if widget.get_active():
			self.plugin.config['print_time'] = 'sometimes'
		self.update_print_time()

	def on_time_always_radiobutton_toggled(self, widget):
		if widget.get_active():
			self.plugin.config['print_time'] = 'always'
		self.update_print_time()

	def on_use_emoticons_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'useemoticons',\
			[self.xml.get_widget('button_new_emoticon'),\
			self.xml.get_widget('button_remove_emoticon'),\
			self.xml.get_widget('treeview_emoticons'),\
			self.xml.get_widget('set_image_button'),\
			self.xml.get_widget('emoticons_image')])

	def on_emoticons_treemodel_row_deleted(self, model, path):
		iter = model.get_iter_first()
		emots = []
		while iter:
			emots.append(model.get_value(iter, 0))
			emots.append(model.get_value(iter, 1))
			iter = model.iter_next(iter)
		self.plugin.config['emoticons'] = '\t'.join(emots)
		self.plugin.init_regex()

	def on_emoticons_treemodel_row_changed(self, model, path, iter):
		if model[path][1] != None and len(model[path][1]) != 0:
			iter = model.get_iter_first()
			emots = []
			while iter:
				emots.append(model.get_value(iter, 0))
				emots.append(model.get_value(iter, 1))
				iter = model.iter_next(iter)
			self.plugin.config['emoticons'] = '\t'.join(emots)
			self.plugin.init_regex()

	def on_auto_pop_up_checkbox_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autopopup', None,\
			[self.auto_pp_away_checkbutton])

	def on_auto_pop_up_away_checkbox_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autopopupaway')

	def on_ignore_events_from_unknown_contacts_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ignore_unknown_contacts')

	def on_soundplayer_entry_changed(self, widget):
		self.plugin.config['soundplayer'] = widget.get_text()
		
	def on_prompt_online_status_message_checkbutton_toggled(self, widget):
		"""On Prompt Online Status Message Checkbutton Toggled"""
		self.on_checkbutton_toggled(widget, 'ask_online_status')
	
	def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
		"""On Prompt Offline Status Message Checkbutton Toggled"""
		self.on_checkbutton_toggled(widget, 'ask_offline_status')
	
	def on_sounds_treemodel_row_changed(self, model, path, iter):
		iter = model.get_iter_first()
		while iter:
			path = model.get_path(iter)
			sound_event = model.get_value(iter, 0)
			if model[path][1]:
				self.plugin.config['sound_' + sound_event] = 1
			else:
				self.plugin.config['sound_' + sound_event] = 0
			self.plugin.config['sound_' + sound_event + '_file'] = \
				model.get_value(iter, 2)
			iter = model.iter_next(iter)

	def on_auto_away_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autoaway', None,\
			[self.auto_away_time_spinbutton])

	def on_auto_away_time_spinbutton_value_changed(self, widget):
		aat = widget.get_value_as_int()
		self.plugin.config['autoawaytime'] = aat
		self.plugin.sleeper = common.sleepy.Sleepy(\
			self.plugin.config['autoawaytime']*60, \
			self.plugin.config['autoxatime']*60)

	def on_auto_xa_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autoxa', None,\
			[self.auto_xa_time_spinbutton])

	def on_auto_xa_time_spinbutton_value_changed(self, widget):
		axt = widget.get_value_as_int()
		self.plugin.config['autoxatime'] = axt
		self.plugin.sleeper = common.sleepy.Sleepy(\
			self.plugin.config['autoawaytime']*60, \
			self.plugin.config['autoxatime']*60)

	def on_msg_treemodel_row_changed(self, model, path, iter):
		iter = model.get_iter_first()
		i = 0
		while iter:
			self.plugin.config['msg%i_name' % i] = model.get_value(iter, 0)
			self.plugin.config['msg%i' % i] = model.get_value(iter, 1)
			iter = model.iter_next(iter)
			i += 1
		while self.plugin.config.has_key('msg%s_name' % i):
			del self.plugin.config['msg%i_name' % i]
			del self.plugin.config['msg%i' % i]
			i += 1

	def on_msg_treemodel_row_deleted(self, model, path, iter):
		iter = model.get_iter_first()
		i = 0
		while iter:
			self.plugin.config['msg%i_name' % i] = model.get_value(iter, 0)
			self.plugin.config['msg%i' % i] = model.get_value(iter, 1)
			iter = model.iter_next(iter)
			i += 1
		while self.plugin.config.has_key('msg%s_name' % i):
			del self.plugin.config['msg%i_name' % i]
			del self.plugin.config['msg%i' % i]
			i += 1

	def on_links_open_with_combobox_changed(self, widget):
		if widget.get_active() == 2:
			self.xml.get_widget('custom_apps_frame').set_sensitive(True)
			self.plugin.config['openwith'] = 'custom'
		else:
			if widget.get_active() == 0:
				self.plugin.config['openwith'] = 'gnome-open'
			if widget.get_active() == 1:
				self.plugin.config['openwith'] = 'kfmclient exec'
			self.xml.get_widget('custom_apps_frame').set_sensitive(False)

	def on_custom_browser_entry_changed(self, widget):
		self.plugin.config['custombrowser'] = widget.get_text()

	def on_custom_mail_client_entry_changed(self, widget):
		self.plugin.config['custommailapp'] = widget.get_text()

	def on_log_in_contact_checkbutton_toggled(self, widget):
		if widget.get_active():
			self.config_logger['lognotusr'] = 1
		else:
			self.config_logger['lognotusr'] = 0
		self.plugin.send('CONFIG', None, ('Logger', self.config_logger, 'GtkGui'))

	def on_log_in_extern_checkbutton_toggled(self, widget):
		if widget.get_active():
			self.config_logger['lognotsep'] = 1
		else:
			self.config_logger['lognotsep'] = 0
		self.plugin.send('CONFIG', None, ('Logger', self.config_logger, 'GtkGui'))
		
	def on_close_button_clicked(self, widget):
		"""When The close button is clicked"""
		widget.get_toplevel().destroy()

	def fill_msg_treeview(self):
		i = 0
		self.xml.get_widget('delete_msg_button').set_sensitive(False)
		model = self.msg_tree.get_model()
		model.clear()
		while self.plugin.config.has_key('msg%s_name' % i):
			iter = model.append()
			model.set(iter, 0, self.plugin.config['msg%s_name' % i], 1, self.plugin.config['msg%s' % i])
			i += 1

	def on_msg_cell_edited(self, cell, row, new_text):
		model = self.msg_tree.get_model()
		iter = model.get_iter_from_string(row)
		model.set_value(iter, 0, new_text)

	def on_msg_treeview_cursor_changed(self, widget, data=None):
		self.xml.get_widget('delete_msg_button').set_sensitive(True)
		buf = self.xml.get_widget('msg_textview').get_buffer()
		(model, iter) = self.msg_tree.get_selection().get_selected()
		name = model.get_value(iter, 0)
		msg = model.get_value(iter, 1)
		buf.set_text(msg)

	def on_new_msg_button_clicked(self, widget, data=None):
		model = self.msg_tree.get_model()
		iter = model.append()
		model.set(iter, 0, 'msg', 1, 'message')

	def on_delete_msg_button_clicked(self, widget, data=None):
		(model, iter) = self.msg_tree.get_selection().get_selected()
		buf = self.xml.get_widget('msg_textview').get_buffer()
		model.remove(iter)
		buf.set_text('')
		self.xml.get_widget('delete_msg_button').set_sensitive(False)
			
	def on_msg_textview_changed(self, widget, data=None):
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

	def image_is_ok(self, image):
		if not os.path.exists(image):
			return 0
		img = gtk.Image()
		try:
			img.set_from_file(image)
		except:
			return 0
		if img.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = img.get_pixbuf()
		else:
			return 0
		if pix.get_width() > 24 or pix.get_height() > 24:
			return 0
		return 1

	def load_emots(self):
		emots = {}
		split_line = self.plugin.config['emoticons'].split('\t')
		for i in range(0, len(split_line)/2):
			if not self.image_is_ok(split_line[2*i+1]):
				continue
			emots[split_line[2*i]] = split_line[2*i+1]
		return emots

	def fill_emot_treeview(self):
		model = self.emot_tree.get_model()
		model.clear()
		emots = self.load_emots()
		for i in emots:
			file = emots[i]
			iter = model.append((i, file, None))
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
		model = self.emot_tree.get_model()
		iter = model.get_iter_from_string(row)
		model.set_value(iter, 0, new_text)

	def on_set_image_button_clicked(self, widget, data=None):
		(model, iter) = self.emot_tree.get_selection().get_selected()
		if not iter:
			return
		file = model.get_value(iter, 1)
		dialog = gtk.FileChooserDialog("Choose image",
							None,
							gtk.FILE_CHOOSER_ACTION_OPEN,
							(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
							gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)
		filter = gtk.FileFilter()
		filter.set_name("All files")
		filter.add_pattern("*")
		dialog.add_filter(filter)

		filter = gtk.FileFilter()
		filter.set_name("Images")
		filter.add_mime_type("image/png")
		filter.add_mime_type("image/jpeg")
		filter.add_mime_type("image/gif")
		filter.add_pattern("*.png")
		filter.add_pattern("*.jpg")
		filter.add_pattern("*.gif")
		filter.add_pattern("*.tif")
		filter.add_pattern("*.xpm")
		dialog.add_filter(filter)
		dialog.set_filter(filter)

		file = os.path.join(os.getcwd(), file)
		dialog.set_filename(file)
		file = ''	
		ok = 0
		while(ok == 0):
			response = dialog.run()
			if response == gtk.RESPONSE_OK:
				file = dialog.get_filename()
				if self.image_is_ok(file):
					ok = 1
			else:
				ok = 1
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
		model.set(iter, 0, 'smeiley', 1, '')
		col = self.emot_tree.get_column(0)
		self.emot_tree.set_cursor(model.get_path(iter), col, True)

	def on_button_remove_emoticon_clicked(self, widget, data=None):
		(model, iter) = self.emot_tree.get_selection().get_selected()
		if not iter:
			return
		model.remove(iter)
		
	def on_checkbutton_toggled(self, widget, config_name, \
		extra_function = None, change_sensitivity_widgets = None):
		if widget.get_active():
			self.plugin.config[config_name] = 1
			if extra_function != None:
				apply(extra_function)
		else:
			self.plugin.config[config_name] = 0
		if change_sensitivity_widgets != None:
			for w in change_sensitivity_widgets:
				w.set_sensitive(widget.get_active())

	def on_treeview_emoticons_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Delete:
			self.on_button_remove_emoticon_clicked(widget)

	def sound_is_ok(self, sound):
		if not os.path.exists(sound):
			return 0
		return 1

	def sound_toggled_cb(self, cell, path):
		model = self.sound_tree.get_model()
		model[path][1] = not model[path][1]
		return

	def fill_sound_treeview(self):
		events = {}
		#events = {name : [use_it, file], name2 : [., .], ...}
		for key in self.plugin.config.keys():
			if key.find('sound_') == 0:
				if not self.plugin.config.has_key(key + '_file'):
					continue
				ev = key.replace('sound_', '')
				events[ev] = [self.plugin.config[key], self.plugin.config[key + \
					'_file']]
		model = self.sound_tree.get_model()
		model.clear()
		for ev in events:
			iter = model.append((ev, events[ev][0], events[ev][1]))

	def on_treeview_sounds_cursor_changed(self, widget, data=None):
		(model, iter) = self.sound_tree.get_selection().get_selected()
		if not iter:
			self.xml.get_widget('sounds_entry').set_text('')
			return
		str = model.get_value(iter, 2)
		self.xml.get_widget('sounds_entry').set_text(str)

	def on_button_sounds_clicked(self, widget, data=None):
		(model, iter) = self.sound_tree.get_selection().get_selected()
		if not iter:
			return
		file = model.get_value(iter, 2)
		dialog = gtk.FileChooserDialog(_('Choose sound'),
							None,
							gtk.FILE_CHOOSER_ACTION_OPEN,
							(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
							gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)
		filter = gtk.FileFilter()
		filter.set_name(_('All files'))
		filter.add_pattern("*")
		dialog.add_filter(filter)

		filter = gtk.FileFilter()
		filter.set_name(_('Wav Sounds'))
		filter.add_pattern("*.wav")
		dialog.add_filter(filter)
		dialog.set_filter(filter)

		file = os.path.join(os.getcwd(), file)
		dialog.set_filename(file)
		file = ''
		ok = 0
		while(ok == 0):
			response = dialog.run()
			if response == gtk.RESPONSE_OK:
				file = dialog.get_filename()
				if self.sound_is_ok(file):
					ok = 1
			else:
				ok = 1
		dialog.destroy()
		if file:
			self.xml.get_widget('sounds_entry').set_text(file)
			model.set_value(iter, 2, file)
			model.set_value(iter, 1, 1)

	def __init__(self, plugin):
		"""Initialize Preference window"""
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'preferences_window', APP)
		self.window = self.xml.get_widget('preferences_window')
		self.plugin = plugin
		self.xml.get_widget('emoticons_image').set_from_file(\
			'plugins/gtkgui/pixmaps/smile.png')
		self.iconstyle_combobox = self.xml.get_widget('iconstyle_combobox')
		self.auto_pp_checkbutton = self.xml.get_widget('auto_pop_up_checkbutton')
		self.auto_pp_away_checkbutton = self.xml.get_widget \
			('auto_pop_up_away_checkbutton')
		self.auto_away_checkbutton = self.xml.get_widget('auto_away_checkbutton')
		self.auto_away_time_spinbutton = self.xml.get_widget \
			('auto_away_time_spinbutton')
		self.auto_xa_checkbutton = self.xml.get_widget('auto_xa_checkbutton')
		self.auto_xa_time_spinbutton = self.xml.get_widget \
			('auto_xa_time_spinbutton')
		self.tray_icon_checkbutton = self.xml.get_widget('tray_icon_checkbutton')
		self.notebook = self.xml.get_widget('preferences_notebook')
		
		#trayicon
		st = self.plugin.config['trayicon']
		self.tray_icon_checkbutton.set_active(st)
		if isinstance(self.plugin.systray, gtkgui.systrayDummy):
			self.tray_icon_checkbutton.set_sensitive(False)

		#Save position
		st = self.plugin.config['saveposition']
		self.xml.get_widget('save_position_checkbutton').set_active(st)
		
		#Merge accounts
		st = self.plugin.config['mergeaccounts']
		self.xml.get_widget('merge_checkbutton').set_active(st)

		#iconStyle
		list_style = os.listdir('plugins/gtkgui/icons/')
		model = gtk.ListStore(gobject.TYPE_STRING)
		self.iconstyle_combobox.set_model(model)
		l = []
		for i in list_style:
			if i != 'CVS' and i[0] != '.':
				l.append(i)
		if l.count == 0:
			l.append(' ')
		for i in range(len(l)):
			model.append([l[i]])
			if self.plugin.config['iconstyle'] == l[i]:
				self.iconstyle_combobox.set_active(i)

		#Color for account text
		colSt = self.plugin.config['accounttextcolor']
		self.xml.get_widget('account_text_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Color for group text
		colSt = self.plugin.config['grouptextcolor']
		self.xml.get_widget('group_text_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Color for user text
		colSt = self.plugin.config['usertextcolor']
		self.xml.get_widget('user_text_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Color for background account
		colSt = self.plugin.config['accountbgcolor']
		self.xml.get_widget('account_text_bg_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Color for background group
		colSt = self.plugin.config['groupbgcolor']
		self.xml.get_widget('group_text_bg_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Color for background user
		colSt = self.plugin.config['userbgcolor']
		self.xml.get_widget('user_text_bg_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))

		#font for account
		fontStr = self.plugin.config['accountfont']
		self.xml.get_widget('account_text_fontbutton').set_font_name(fontStr)
		
		#font for group
		fontStr = self.plugin.config['groupfont']
		self.xml.get_widget('group_text_fontbutton').set_font_name(fontStr)
		
		#font for account
		fontStr = self.plugin.config['userfont']
		self.xml.get_widget('user_text_fontbutton').set_font_name(fontStr)
		
		#use tabbed chat window
		st = self.plugin.config['usetabbedchat']
		self.xml.get_widget('use_tabbed_chat_window_checkbutton').set_active(st)

		#Color for incomming messages
		colSt = self.plugin.config['inmsgcolor']
		self.xml.get_widget('incoming_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Color for outgoing messages
		colSt = self.plugin.config['outmsgcolor']
		self.xml.get_widget('outgoing_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Color for status messages
		colSt = self.plugin.config['statusmsgcolor']
		self.xml.get_widget('status_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(colSt))
		
		#Print time
		if self.plugin.config['print_time'] == 'never':
			self.xml.get_widget('time_never_radiobutton').set_active(1)
		elif self.plugin.config['print_time'] == 'sometimes':
			self.xml.get_widget('time_sometimes_radiobutton').set_active(1)
		else:
			self.xml.get_widget('time_always_radiobutton').set_active(1)

		#Use emoticons
		st = self.plugin.config['useemoticons']
		self.xml.get_widget('use_emoticons_checkbutton').set_active(st)
		self.xml.get_widget('button_new_emoticon').set_sensitive(st)
		self.xml.get_widget('button_remove_emoticon').set_sensitive(st)
		self.xml.get_widget('treeview_emoticons').set_sensitive(st)
		self.xml.get_widget('set_image_button').set_sensitive(st)

		#emoticons
		self.emot_tree = self.xml.get_widget('treeview_emoticons')
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gtk.Image)
		self.emot_tree.set_model(model)
		col = gtk.TreeViewColumn(_('Name'))
		self.emot_tree.append_column(col)
		renderer = gtk.CellRendererText()
		renderer.connect('edited', self.on_emot_cell_edited)
		renderer.set_property('editable', True)
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text=0)

		col = gtk.TreeViewColumn(_('Image'))
		self.emot_tree.append_column(col)
		renderer = gtkgui.ImageCellRenderer()
		col.pack_start(renderer, expand = False)
		col.add_attribute(renderer, 'image', 2)
		
		self.fill_emot_treeview()

		#Autopopup
		st = self.plugin.config['autopopup']
		self.auto_pp_checkbutton.set_active(st)

		#Autopopupaway
		st = self.plugin.config['autopopupaway']
		self.auto_pp_away_checkbutton.set_active(st)
		self.auto_pp_away_checkbutton.set_sensitive(self.plugin.config['autopopup'])

		#Ignore messages from unknown contacts
		self.xml.get_widget('ignore_events_from_unknown_contacts_checkbutton').\
			set_active(self.plugin.config['ignore_unknown_contacts'])

		#sound player
		self.xml.get_widget('soundplayer_entry').set_text(\
			self.plugin.config['soundplayer'])

		#sounds
		self.sound_tree = self.xml.get_widget('sounds_treeview')
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, \
			gobject.TYPE_STRING)
		self.sound_tree.set_model(model)

		col = gtk.TreeViewColumn(_('Active'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererToggle()
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.sound_toggled_cb)
		col.pack_start(renderer)
		col.set_attributes(renderer, active=1)

		col = gtk.TreeViewColumn(_('Event'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text=0)

		col = gtk.TreeViewColumn(_('Sound'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text=2)
		self.fill_sound_treeview()

		if not os.name == 'posix':
			self.xml.get_widget('soundplayer_entry').set_sensitive(False)
			self.sound_tree.set_sensitive(False)
			self.xml.get_widget('sounds_entry').set_sensitive(False)
			self.xml.get_widget('sounds_button').set_sensitive(False)
		
		#Autoaway
		st = self.plugin.config['autoaway']
		self.auto_away_checkbutton.set_active(st)

		#Autoawaytime
		st = self.plugin.config['autoawaytime']
		self.auto_away_time_spinbutton.set_value(st)
		self.auto_away_time_spinbutton.set_sensitive(self.plugin.config['autoaway'])

		#Autoxa
		st = self.plugin.config['autoxa']
		self.auto_xa_checkbutton.set_active(st)

		#Autoxatime
		st = self.plugin.config['autoxatime']
		self.auto_xa_time_spinbutton.set_value(st)
		self.auto_xa_time_spinbutton.set_sensitive(self.plugin.config['autoxa'])

		#ask_status when online / offline
		st = self.plugin.config['ask_online_status']
		self.xml.get_widget('prompt_online_status_message_checkbutton').\
			set_active(st)
		st = self.plugin.config['ask_offline_status']
		self.xml.get_widget('prompt_offline_status_message_checkbutton').\
			set_active(st)

		#Status messages
		self.msg_tree = self.xml.get_widget('msg_treeview')
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.msg_tree.set_model(model)
		col = gtk.TreeViewColumn('name')
		self.msg_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text=0)
		renderer.connect('edited', self.on_msg_cell_edited)
		renderer.set_property('editable', True)
		self.fill_msg_treeview()
		buf = self.xml.get_widget('msg_textview').get_buffer()
		buf.connect('changed', self.on_msg_textview_changed)

		self.plugin.send('ASK_CONFIG', None, ('GtkGui', 'Logger', {'lognotsep':1,\
			'lognotusr':1}))
		self.config_logger = self.plugin.wait('CONFIG')
		
		#open links with
		self.links_open_with_combobox = self.xml.get_widget('links_open_with_combobox')
		if self.plugin.config['openwith'] == 'gnome-open':
			self.links_open_with_combobox.set_active(0)
		elif self.plugin.config['openwith'] == 'kfmclient exec':
			self.links_open_with_combobox.set_active(1)
		elif self.plugin.config['openwith'] == 'custom':
			self.links_open_with_combobox.set_active(2)
			self.xml.get_widget('custom_apps_frame').set_sensitive(True)
		self.xml.get_widget('custom_browser_entry').set_text(\
			self.plugin.config['custombrowser'])
		self.xml.get_widget('custom_mail_client_entry').set_text(\
			self.plugin.config['custommailapp'])
				
		#log presences in user file
		st = self.config_logger['lognotusr']
		self.xml.get_widget('log_in_contact_checkbutton').set_active(st)

		#log presences in external file
		st = self.config_logger['lognotsep']
		self.xml.get_widget('log_in_extern_checkbutton').set_active(st)
		
		self.emot_tree.get_model().connect('row-changed', \
			self.on_emoticons_treemodel_row_changed)
		self.emot_tree.get_model().connect('row-deleted', \
			self.on_emoticons_treemodel_row_deleted)
		self.sound_tree.get_model().connect('row-changed', \
			self.on_sounds_treemodel_row_changed)
		self.msg_tree.get_model().connect('row-changed', \
			self.on_msg_treemodel_row_changed)
		self.msg_tree.get_model().connect('row-deleted', \
			self.on_msg_treemodel_row_deleted)
		
		self.xml.signal_autoconnect(self)

class Account_modification_window:
	"""Class for account informations"""
	def on_account_modification_window_destroy(self, widget):
		"""close window"""
		del self.plugin.windows['account_modification_window']
	
	def on_close_button_clicked(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def init_account(self, infos):
		"""Initialize window with defaults values"""
		if infos.has_key('accname'):
			self.xml.get_widget('name_entry').set_text(infos['accname'])
		if infos.has_key('jid'):
			self.xml.get_widget('jid_entry').set_text(infos['jid'])
		if infos.has_key('savepass'):
			self.xml.get_widget('save_password_checkbutton').set_active(\
				infos['savepass'])
			if infos['savepass']:
				password_entry = self.xml.get_widget('password_entry')
				password_entry.set_sensitive(True)
				if infos.has_key('password'):
					password_entry.set_text(infos['password'])
		if infos.has_key('resource'):
			self.xml.get_widget('resource_entry').set_text(infos['resource'])
		if infos.has_key('priority'):
			self.xml.get_widget('priority_spinbutton').set_value(infos['priority'])
		if infos.has_key('use_proxy'):
			self.xml.get_widget('use_proxy_checkbutton').\
				set_active(infos['use_proxy'])
		if infos.has_key('proxyhost'):
			self.xml.get_widget('proxyhost_entry').set_text(infos['proxyhost'])
		if infos.has_key('proxyport'):
			self.xml.get_widget('proxyport_entry').set_text(str(\
				infos['proxyport']))
		gpg_key_label = self.xml.get_widget('gpg_key_label')
		if not self.plugin.config.has_key('usegpg'):
			gpg_key_label.set_text('GPG is not usable on this computer')
			self.xml.get_widget('gpg_choose_button').set_sensitive(False)
		if infos.has_key('keyid') and self.plugin.config.has_key('usegpg'):
			if infos['keyid'] and self.plugin.config['usegpg']:
				gpg_key_label.set_text(infos['keyid'])
				if infos.has_key('keyname'):
					self.xml.get_widget('gpg_name_label').set_text(infos['keyname'])
				gpg_save_password_checkbutton = \
					self.xml.get_widget('gpg_save_password_checkbutton')
				gpg_save_password_checkbutton.set_sensitive(True)
				if infos.has_key('savegpgpass'):
					gpg_save_password_checkbutton.set_active(infos['savegpgpass'])
					if infos['savegpgpass']:
						gpg_password_entry = self.xml.get_widget('gpg_password_entry')
						gpg_password_entry.set_sensitive(True)
						if infos.has_key('gpgpassword'):
							gpg_password_entry.set_text(infos['gpgpassword'])
		if infos.has_key('autoconnect'):
			self.xml.get_widget('autoconnect_checkbutton').set_active(\
				infos['autoconnect'])
		if infos.has_key('sync_with_global_status'):
			self.xml.get_widget('sync_with_global_status_checkbutton').set_active(\
				infos['sync_with_global_status'])
		if infos.has_key('no_log_for'):
			list_no_log_for = infos['no_log_for'].split()
			if infos['accname'] in list_no_log_for:
				self.xml.get_widget('log_history_checkbutton').set_active(0)

	def on_save_button_clicked(self, widget):
		"""When save button is clicked : Save informations in config file"""
		save_password = 0
		if self.xml.get_widget('save_password_checkbutton').get_active():
			save_password = 1
		password = self.xml.get_widget('password_entry').get_text()
		resource = self.xml.get_widget('resource_entry').get_text()
		priority = self.xml.get_widget('priority_spinbutton').get_value_as_int()
		new_account_checkbutton = self.xml.get_widget('new_account_checkbutton')
		name = self.xml.get_widget('name_entry').get_text()
		jid = self.xml.get_widget('jid_entry').get_text()
		autoconnect = 0
		if self.xml.get_widget('autoconnect_checkbutton').get_active():
			autoconnect = 1

		if not self.infos.has_key('no_log_for'):
			self.infos['no_log_for'] = ''
		list_no_log_for = self.infos['no_log_for'].split()
		if self.account in list_no_log_for:
			list_no_log_for.remove(self.account)
		if not self.xml.get_widget('log_history_checkbutton').get_active():
			list_no_log_for.append(name)
		self.infos['no_log_for'] = ' '.join(list_no_log_for)

		sync_with_global_status = 0
		if self.xml.get_widget('sync_with_global_status_checkbutton').\
			get_active():
			sync_with_global_status = 1

		use_proxy = 0
		if self.xml.get_widget('use_proxy_checkbutton').get_active():
			use_proxy = 1
		proxyhost = self.xml.get_widget('proxyhost_entry').get_text()
		proxyport = self.xml.get_widget('proxyport_entry').get_text()
		if (name == ''):
			Error_dialog(_('You must enter a name for this account'))
			return
		if name.find(' ') != -1:
			Error_dialog(_('Spaces are not permited in account name'))
			return
		if (jid == '') or (jid.count('@') != 1):
			Error_dialog(_('You must enter a Jabber ID for this account\nFor example: someone@someserver.org'))
			return
		if new_account_checkbutton.get_active() and password == '':
			Error_dialog(_('You must enter a password to register a new account'))
			return
		if use_proxy:
			if proxyport != '':
				try:
					proxyport = int(proxyport)
				except ValueError:
					Error_dialog(_('Proxy Port must be a port number'))
					return
			if proxyhost == '':
				Error_dialog(_('You must enter a proxy host to use proxy'))

		(login, hostname) = jid.split('@')
		key_name = self.xml.get_widget('gpg_name_label').get_text()
		if key_name == '': #no key selected
			keyID = ''
			save_gpg_password = 0
			gpg_password = ''
		else:
			keyID = self.xml.get_widget('gpg_key_label').get_text()
			save_gpg_password = 0
			if self.xml.get_widget('gpg_save_password_checkbutton').get_active():
				save_gpg_password = 1
			gpg_password = self.xml.get_widget('gpg_password_entry').get_text()
		#if we are modifying an account
		if self.modify:
			#if we modify the name of the account
			if name != self.account:
				#update variables
				self.plugin.windows[name] = self.plugin.windows[self.account]
				self.plugin.queues[name] = self.plugin.queues[self.account]
				self.plugin.connected[name] = self.plugin.connected[self.account]
				self.plugin.nicks[name] = self.plugin.nicks[self.account]
				self.plugin.roster.groups[name] = \
					self.plugin.roster.groups[self.account]
				self.plugin.roster.contacts[name] = \
					self.plugin.roster.contacts[self.account]
				self.plugin.sleeper_state[name] = \
					self.plugin.sleeper_state[self.account]
				del self.plugin.windows[self.account]
				del self.plugin.queues[self.account]
				del self.plugin.connected[self.account]
				del self.plugin.nicks[self.account]
				del self.plugin.roster.groups[self.account]
				del self.plugin.roster.contacts[self.account]
				del self.plugin.accounts[self.account]
				del self.plugin.sleeper_state[self.account]
				self.plugin.send('ACC_CHG', self.account, name)
			self.plugin.accounts[name] = {'name': login, 'hostname': hostname,\
				'savepass': save_password, 'password': password, \
				'resource': resource, 'priority' : priority, \
				'autoconnect': autoconnect, 'use_proxy': use_proxy, 'proxyhost': \
				proxyhost, 'proxyport': proxyport, 'keyid': keyID, \
				'keyname': key_name, 'savegpgpass': save_gpg_password, \
				'gpgpassword': gpg_password, 'sync_with_global_status': \
				sync_with_global_status, 'no_log_for': self.infos['no_log_for']}
			self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts, \
				'GtkGui'))
			if save_password:
				self.plugin.send('PASSPHRASE', name, password)
			#refresh accounts window
			if self.plugin.windows.has_key('accounts_window'):
				self.plugin.windows['accounts_window'].init_accounts()
			#refresh roster
			self.plugin.roster.draw_roster()
			widget.get_toplevel().destroy()
			return
		#if it's a new account
		if name in self.plugin.accounts.keys():
			Error_dialog(_('An account already has this name'))
			return
		#if we neeed to register a new account
		if new_account_checkbutton.get_active():
			self.plugin.send('NEW_ACC', None, (hostname, login, password, name, \
				resource, priority, use_proxy, proxyhost, proxyport))
			return
		self.plugin.accounts[name] = {'name': login, 'hostname': hostname,\
			'savepass': save_password, 'password': password, 'resource': \
			resource, 'priority' : priority, 'autoconnect': autoconnect, \
			'use_proxy': use_proxy, 'proxyhost': proxyhost, \
			'proxyport': proxyport, 'keyid': keyID, 'keyname': key_name, \
			'savegpgpass': save_gpg_password, 'gpgpassword': gpg_password,\
			'sync_with_global_status': 1, 'no_log_for': self.infos['no_log_for']}
		self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts, \
			'GtkGui'))
		if save_password:
			self.plugin.send('PASSPHRASE', name, password)
		#update variables
		self.plugin.windows[name] = {'infos': {}, 'chats': {}, 'gc': {}}
		self.plugin.queues[name] = {}
		self.plugin.connected[name] = 0
		self.plugin.roster.groups[name] = {}
		self.plugin.roster.contacts[name] = {}
		self.plugin.nicks[name] = login
		self.plugin.sleeper_state[name] = 0
		#refresh accounts window
		if self.plugin.windows.has_key('accounts_window'):
			self.plugin.windows['accounts_window'].init_accounts()
		#refresh roster
		self.plugin.roster.draw_roster()
		widget.get_toplevel().destroy()

	def on_change_password_button_clicked(self, widget):
		dialog = Change_password_dialog(self.plugin, self.account)
		new_password = dialog.run()
		if new_password != -1:
			self.plugin.send('CHANGE_PASSWORD', self.account,\
				(new_password, self.plugin.nicks[self.account]))
			if self.xml.get_widget('save_password_checkbutton').get_active():
				self.xml.get_widget('password_entry').set_text(new_password)

	def account_is_ok(self, acct):
		"""When the account has been created with sucess"""
		self.xml.get_widget('new_account_checkbutton').set_active(False)
		self.modify = True
		self.account = acct
		jid = self.xml.get_widget('jid_entry').get_text()
		(login, hostname) = jid.split('@')
		save_password = 0
		password = self.xml.get_widget('password_entry').get_text()
		resource = self.xml.get_widget('resource_entry').get_text()
		priority = self.xml.get_widget('priority_spinbutton').get_value_as_int()
		autoconnect = 0
		if self.xml.get_widget('autoconnect_checkbutton').get_active():
			autoconnect = 1
		use_proxy = 0
		if self.xml.get_widget('use_proxy_checkbutton').get_active():
			use_proxy = 1
		proxyhost = self.xml.get_widget('proxyhost_entry').get_text()
		proxyport = self.xml.get_widget('proxyport_entry').get_text()
		key_name = self.xml.get_widget('gpg_name_label').get_text()
		if self.xml.get_widget('save_password_checkbutton').get_active():
			save_password = 1
		if key_name == '': #no key selected
			keyID = ''
			save_gpg_password = 0
			gpg_password = ''
		else:
			keyID = self.xml.get_widget('gpg_key_label').get_text()
			save_gpg_password = 0
			if self.xml.get_widget('gpg_save_password_checkbutton').get_active():
				save_gpg_password = 1
			gpg_password = self.xml.get_widget('gpg_password_entry').get_text()
		no_log_for = ''
		if self.xml.get_widget('log_history_checkbutton').get_active():
			no_log_for = acct
		self.plugin.accounts[acct] = {'name': login, 'hostname': hostname,\
			'savepass': save_password, 'password': password, 'resource': \
			resource, 'priority' : priority, 'autoconnect': autoconnect, \
			'use_proxy': use_proxy, 'proxyhost': proxyhost, \
			'proxyport': proxyport, 'keyid': keyID, 'keyname': key_name, \
			'savegpgpass': save_gpg_password, 'gpgpassword': gpg_password,\
			'sync_with_global_status': 1, 'no_log_for': no_log_for}
		self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts, \
			'GtkGui'))

	def on_edit_details_button_clicked(self, widget):
		if not self.plugin.windows.has_key(self.account):
			Error_dialog(_('You must first create your account before editing your information'))
			return
		jid = self.xml.get_widget('jid_entry').get_text()
		if self.plugin.connected[self.account] < 2:
			Error_dialog(_('You must be connected to edit your information'))
			return
		if not self.plugin.windows[self.account]['infos'].has_key('vcard'):
			self.plugin.windows[self.account]['infos'][jid] = \
				vcard_information_window(jid, self.plugin, self.account, True)
			self.plugin.send('ASK_VCARD', self.account, jid)
	
	def on_gpg_choose_button_clicked(self, widget, data=None):
		w = choose_gpg_key_dialog()
		self.plugin.windows['gpg_keys'] = w
		self.plugin.send('GPG_SECRETE_KEYS', None, ())
		keyID = w.run()
		if keyID == -1:
			return
		gpg_save_password_checkbutton = \
			self.xml.get_widget('gpg_save_password_checkbutton')
		gpg_key_label = self.xml.get_widget('gpg_key_label')
		gpg_name_label = self.xml.get_widget('gpg_name_label')
		if keyID[0] == 'None':
			gpg_key_label.set_text(_('No key selected'))
			gpg_name_label.set_text('')
			gpg_save_password_checkbutton.set_sensitive(False)
			self.xml.get_widget('gpg_password_entry').set_sensitive(False)
		else:
			gpg_key_label.set_text(keyID[0])
			gpg_name_label.set_text(keyID[1])
			gpg_save_password_checkbutton.set_sensitive(True)
		gpg_save_password_checkbutton.set_active(False)
		self.xml.get_widget('gpg_password_entry').set_text('')
	
	def on_checkbutton_toggled(self, widget, widgets):
		"""set or unset sensitivity of widgets when widget is toggled"""
		for w in widgets:
			w.set_sensitive(widget.get_active())

	def on_checkbutton_toggled_and_clear(self, widget, widgets):
		self.on_checkbutton_toggled(widget, widgets)
		for w in widgets:
			if not widget.get_active():
				w.set_text('')

	def on_gpg_save_password_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled_and_clear(widget, [\
			self.xml.get_widget('gpg_password_entry')])

	def on_save_password_checkbutton_toggled(self, widget):
		if self.xml.get_widget('new_account_checkbutton').get_active():
			return
		self.on_checkbutton_toggled_and_clear(widget, \
			[self.xml.get_widget('password_entry')])
		self.xml.get_widget('password_entry').grab_focus()

	def on_new_account_checkbutton_toggled(self, widget):
		password_entry = self.xml.get_widget('password_entry')
		if widget.get_active():
			password_entry.set_sensitive(True)
		elif not self.xml.get_widget('save_password_checkbutton').get_active():
			password_entry.set_sensitive(False)
			password_entry.set_text('')

	#infos must be a dictionnary
	def __init__(self, plugin, infos):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'account_modification_window', APP)
		self.window = self.xml.get_widget('account_modification_window')
		self.plugin = plugin
		self.account = ''
		self.modify = False
		self.infos = infos
		self.xml.get_widget('gpg_key_label').set_text('No key selected')
		self.xml.get_widget('gpg_name_label').set_text('')
		self.xml.get_widget('gpg_save_password_checkbutton').set_sensitive(False)
		self.xml.get_widget('gpg_password_entry').set_sensitive(False)
		self.xml.get_widget('password_entry').set_sensitive(False)
		self.xml.get_widget('log_history_checkbutton').set_active(1)
		#default is checked
		self.xml.get_widget('sync_with_global_status_checkbutton').set_active(1)
		self.xml.signal_autoconnect(self)
		if infos:
			self.modify = True
			self.account = infos['accname']
			self.init_account(infos)
			self.xml.get_widget('new_account_checkbutton').set_sensitive(False)

class Accounts_window:
	"""Class for accounts window : lists of accounts"""
	def on_accounts_window_destroy(self, widget):
		"""close window"""
		del self.plugin.windows['accounts_window']
		
	def on_close_button_clicked(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()
		
	def init_accounts(self):
		"""initialize listStore with existing accounts"""
		self.modify_button.set_sensitive(False)
		self.delete_button.set_sensitive(False)
		model = self.accounts_treeview.get_model()
		model.clear()
		for account in self.plugin.accounts:
			iter = model.append()
			model.set(iter, 0, account, 1,\
				self.plugin.accounts[account]['hostname'])

	def on_accounts_treeview_cursor_changed(self, widget):
		"""Activate delete and modify buttons when a row is selected"""
		self.modify_button.set_sensitive(True)
		self.delete_button.set_sensitive(True)

	def on_new_button_clicked(self, widget):
		"""When new button is clicked : open an account information window"""
		if not self.plugin.windows.has_key('account_modification_window'):
			self.plugin.windows['account_modification_window'] = \
				Account_modification_window(self.plugin, {}) #find out what's wrong
		else:
			self.plugin.windows[account_modification_window].window.present()

	def on_delete_button_clicked(self, widget):
		"""When delete button is clicked :
		Remove an account from the listStore and from the config file"""
		sel = self.accounts_treeview.get_selection()
		(model, iter) = sel.get_selected()
		account = model.get_value(iter, 0)
		dialog = Confirmation_dialog(_('Are you sure you want to remove account (%s) ?') % account)
		if dialog.get_response() == gtk.RESPONSE_YES:
			if self.plugin.connected[account]:
				self.plugin.send('STATUS', account, ('offline', 'offline'))
			del self.plugin.accounts[account]
			self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts, \
				'GtkGui'))
			del self.plugin.windows[account]
			del self.plugin.queues[account]
			del self.plugin.connected[account]
			del self.plugin.roster.groups[account]
			del self.plugin.roster.contacts[account]
			self.plugin.roster.draw_roster()
			self.init_accounts()

	def on_modify_button_clicked(self, widget):
		"""When modify button is clicked :
		open the account information window for this account"""
		if not self.plugin.windows.has_key('account_modification_window'):
			sel = self.accounts_treeview.get_selection()
			(model, iter) = sel.get_selected()
			account = model.get_value(iter, 0)
			infos = self.plugin.accounts[account]
			infos['accname'] = account
			infos['jid'] = self.plugin.accounts[account]['name'] + \
				'@' +  self.plugin.accounts[account]['hostname']
			self.plugin.windows['account_modification_window'] = \
				Account_modification_window(self.plugin, infos) # may it messes with this one
		else:
			self.plugin.windows[account_modification_window].window.present()

	def on_sync_with_global_status_checkbutton_toggled(self, widget):
		if widget.get_active():
			self.plugin.accounts[account]['sync_with_global_status'] = 0
		else:
			self.plugin.accounts[account]['sync_with_global_status'] = 1
		
	def __init__(self, plugin):
		self.plugin = plugin
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'accounts_window', APP)
		self.window = self.xml.get_widget('accounts_window')
		self.accounts_treeview = self.xml.get_widget('accounts_treeview')
		self.modify_button = self.xml.get_widget('modify_button')
		self.delete_button = self.xml.get_widget('delete_button')
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, \
			gobject.TYPE_BOOLEAN)
		self.accounts_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1, _('Name'), renderer, \
			text=0)
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1, _('Server'), \
			renderer, text=1)
		self.xml.signal_autoconnect(self)
		self.init_accounts()

class agent_registration_window:
	"""Class for agent registration window :
	window that appears when we want to subscribe to an agent"""
	def on_cancel_button_clicked(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()
		
	def draw_table(self):
		"""Draw the table in the window"""
		nbrow = 0
		table = self.xml.get_widget('table')
		for name in self.infos.keys():
			if name != 'key' and name != 'instructions' and name != 'x':
				nbrow = nbrow + 1
				table.resize(rows=nbrow, columns=2)
				label = gtk.Label(name)
				table.attach(label, 0, 1, nbrow-1, nbrow, 0, 0, 0, 0)
				entry = gtk.Entry()
				entry.set_text(self.infos[name])
				table.attach(entry, 1, 2, nbrow-1, nbrow, 0, 0, 0, 0)
				self.entries[name] = entry
				if nbrow == 1:
					entry.grab_focus()
		table.show_all()
	
	def on_ok_button_clicked(self, widget):
		"""When Ok button is clicked :
		send registration info to the core"""
		for name in self.entries.keys():
			self.infos[name] = self.entries[name].get_text()
		user1 = gtkgui.User(self.agent, self.agent, ['Agents'], 'offline', \
			'offline', 'from', '', '', 0, '')
		self.plugin.roster.contacts[self.account][self.agent] = [user1]
		self.plugin.roster.add_user_to_roster(self.agent, self.account)
		self.plugin.send('REG_AGENT', self.account, self.agent)
		widget.get_toplevel().destroy()
	
	def __init__(self, agent, infos, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'agent_registration_window', APP)
		self.agent = agent
		self.infos = infos
		self.plugin = plugin
		self.account = account
		window = self.xml.get_widget('agent_registration_window')
		window.set_title(_('Register to %s') % agent)
		self.xml.get_widget('label').set_text(infos['instructions'])
		self.entries = {}
		self.draw_table()
		self.xml.signal_autoconnect(self)


class agent_browser_window:
	"""Class for bowser agent window :
	to know the agents on the selected server"""
	def on_agent_browser_window_destroy(self, widget):
		"""close window"""
		del self.plugin.windows[self.account]['browser']

	def on_close_button_clicked(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()
		
	def browse(self):
		"""Send a request to the core to know the available agents"""
		self.plugin.send('REQ_AGENTS', self.account, None)
	
	def agents(self, agents):
		"""When list of available agent arrive :
		Fill the treeview with it"""
		model = self.agents_treeview.get_model()
		for agent in agents:
			iter = model.append(None, (agent['name'], agent['jid']))
			self.agent_infos[agent['jid']] = {'features' : []}
	
	def agent_info(self, agent, identities, features, items):
		"""When we recieve informations about an agent"""
		model = self.agents_treeview.get_model()
		iter = model.get_iter_root()
		expand = 0
		while (iter):
			if agent == model.get_value(iter, 1):
				break
			if model.iter_has_child(iter):
				iter = model.iter_children(iter)
			else:
				if not model.iter_next(iter):
					iter = model.iter_parent(iter)
				if iter:
					iter = model.iter_next(iter)
		if not iter:
			iter = model.append(None, (agent, agent))
			self.agent_infos[agent] = {'features' : []}
			expand = 1
		self.agent_infos[agent]['features'] = features
		if len(identities):
			self.agent_infos[agent]['identities'] = identities
			if identities[0].has_key('name'):
				model.set_value(iter, 0, identities[0]['name'])
		for item in items:
			if not item.has_key('name'):
				continue
			model.append(iter, (item['name'], item['jid']))
			self.agent_infos[item['jid']] = {'identities': [item]}
		if expand:
			self.agents_treeview.expand_row((model.get_path(iter)), False)

	def on_refresh_button_clicked(self, widget):
		"""When refresh button is clicked :
		refresh list : clear and rerequest it"""
		self.agents_treeview.get_model().clear()
		self.browse()

	def on_agents_treeview_row_activated(self, widget, path, col=0):
		"""When a row is activated :
		Register or join the selected agent"""
		#TODO
		pass

	def on_join_button_clicked(self, widget):
		"""When we want to join a conference :
		Ask specific informations about the selected agent and close the window"""
		model, iter = self.agents_treeview.get_selection().get_selected()
		if not iter:
			return
		service = model.get_value(iter, 1)
		room = ''
		if service.find('@') > -1:
			services = service.split('@')
			room = services[0]
			service = services[1]
		if not self.plugin.windows.has_key('join_gc'):
			self.plugin.windows['join_gc'] = Join_groupchat_window(self.plugin, self.account, service, room)

	def on_register_button_clicked(self, widget):
		"""When we want to register an agent :
		Ask specific informations about the selected agent and close the window"""
		model, iter = self.agents_treeview.get_selection().get_selected()
		if not iter :
			return
		service = model.get_value(iter, 1)
		self.plugin.send('REG_AGENT_INFO', self.account, service)
		widget.get_toplevel().destroy()
	
	def on_agents_treeview_cursor_changed(self, widget):
		"""When we select a row :
		activate buttons if needed"""
		model, iter = self.agents_treeview.get_selection().get_selected()
		jid = model.get_value(iter, 1)
		self.register_button.set_sensitive(False)
		if self.agent_infos[jid].has_key('features'):
			if common.jabber.NS_REGISTER in self.agent_infos[jid]['features']:
				self.register_button.set_sensitive(True)
		self.join_button.set_sensitive(False)
		if self.agent_infos[jid].has_key('identities'):
			if len(self.agent_infos[jid]['identities']):
				if self.agent_infos[jid]['identities'][0].has_key('category'):
					if self.agent_infos[jid]['identities'][0]['category'] == 'conference':
						self.join_button.set_sensitive(True)
		
	def __init__(self, plugin, account):
		if plugin.connected[account] < 2:
			Error_dialog(_("You must be connected to view Agents"))
			return
		xml = gtk.glade.XML(GTKGUI_GLADE, 'agent_browser_window', APP)
		self.window = xml.get_widget('agent_browser_window')
		self.agents_treeview = xml.get_widget('agents_treeview')
		self.plugin = plugin
		self.account = account
		self.agent_infos = {}
		model = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.agents_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.agents_treeview.insert_column_with_attributes(-1, 'Name', \
			renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.agents_treeview.insert_column_with_attributes(-1, 'Service', \
			renderer, text=1)

		self.register_button = xml.get_widget('register_button')
		self.register_button.set_sensitive(False)
		self.join_button = xml.get_widget('join_button')
		self.join_button.set_sensitive(False)
		xml.signal_autoconnect(self)
		self.browse()
