##	plugins/dialogs.py
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
from common import gajim
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

import gtkgui

GTKGUI_GLADE='gtkgui.glade'

class Vcard_information_window:
	"""Class for user's information window"""
	def on_user_information_window_destroy(self, widget=None):
		"""close window"""
		del self.plugin.windows[self.account]['infos'][self.jid]

	def on_vcard_information_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.destroy()

	def on_close_button_clicked(self, widget):
		"""Save user's informations and update the roster on the Jabber server"""
		if self.vcard:
			self.window.destroy()
			return
		#update user.name if it's not ""
		name_entry = self.xml.get_widget('nickname_entry')
		new_name = name_entry.get_text()
		if new_name != self.user.name and new_name != '':
			self.user.name = new_name
			for i in self.plugin.roster.get_user_iter(self.user.jid, self.account):
				self.plugin.roster.tree.get_model().set_value(i, 1, new_name)
			self.plugin.send('UPDUSER', self.account, (self.user.jid, \
				self.user.name, self.user.groups))
		#log history ?
		oldlog = 1
		no_log_for = gajim.config.get_per('accounts', self.account, 'no_log_for')\
			.split()
		if self.user.jid in no_log_for:
			oldlog = 0
		log = self.xml.get_widget('log_checkbutton').get_active()
		if not log and not self.user.jid in no_log_for:
			no_log_for.append(self.user.jid)
		if log and self.user.jid in no_log_for:
			no_log_for.remove(self.user.jid)
		if oldlog != log:
			gajim.config.set_per('accounts', self.account, 'no_log_for', \
				' '.join(no_log_for))
		self.window.destroy()

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError, e:
			pass

	def set_values(self, vcard):
		for i in vcard.keys():
			if type(vcard[i]) == type({}):
				for j in vcard[i].keys():
					self.set_value(i+'_'+j+'_entry', vcard[i][j])
			else:
				if i == 'DESC':
					self.xml.get_widget('DESC_textview').get_buffer().\
						set_text(vcard[i], 0)
				else:
					self.set_value(i+'_entry', vcard[i])
	
	def set_os_info(self, client_info, os_info):
		self.xml.get_widget('client_name_version_label').set_text(client_info)
		self.xml.get_widget('platform_label').set_text(os_info)

	def fill_jabber_page(self):
		self.xml.get_widget('nickname_label').set_text(self.user.name)
		self.xml.get_widget('jid_label').set_text(self.user.jid)
		self.xml.get_widget('subscription_label').set_text(self.user.sub)
		if self.user.ask:
			self.xml.get_widget('ask_label').set_text(self.user.ask)
		else:
			self.xml.get_widget('ask_label').set_text('None')
		self.xml.get_widget('nickname_entry').set_text(self.user.name)
		log = 1
		if self.user.jid in gajim.config.get_per('accounts', account, \
			'no_log_for').split(' '):
			log = 0
		self.xml.get_widget('log_checkbutton').set_active(log)
		resources = self.user.resource + ' (' + str(self.user.priority) + ')'
		if not self.user.status:
			self.user.status = ''
		stats = self.user.show + ': ' + self.user.status
		for u in self.plugin.roster.contacts[self.account][self.user.jid]:
			if u.resource != self.user.resource:
				resources += '\n' + u.resource + ' (' + str(u.priority) + ')'
				if not u.status:
					u.status = ''
				stats += '\n' + u.show + ': ' + u.status
		self.xml.get_widget('resource_label').set_text(resources)
		self.xml.get_widget('status_label').set_text(stats)
		self.plugin.send('ASK_VCARD', self.account, self.user.jid)
		self.plugin.send('ASK_OS_INFO', self.account, (self.user.jid, self.user.resource))

	def add_to_vcard(self, vcard, entry, txt):
		"""Add an information to the vCard dictionary"""
		entries = entry.split('_')
		loc = vcard
		while len(entries) > 1:
			if not loc.has_key(entries[0]):
				loc[entries[0]] = {}
			loc = loc[entries[0]]
			del entries[0]
		loc[entries[0]] = txt
		return vcard

	def make_vcard(self):
		"""make the vCard dictionary"""
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_USERID', 'URL', 'TEL_NUMBER',\
			'ADR_STREET', 'ADR_EXTADR', 'ADR_LOCALITY', 'ADR_REGION', 'ADR_PCODE',\
			'ADR_CTRY', 'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE'] 
		vcard = {}
		for e in entries: 
			txt = self.xml.get_widget(e+'_entry').get_text()
			if txt != '':
				vcard = self.add_to_vcard(vcard, e, txt)
		buffer = self.xml.get_widget('DESC_textview').get_buffer()
		start_iter = buffer.get_start_iter()
		end_iter = buffer.get_end_iter()
		txt = buffer.get_text(start_iter, end_iter, 0)
		if txt != '':
			vcard['DESC'] = txt
		return vcard

	def on_publish_button_clicked(self, widget):
		if self.plugin.connected[self.account] < 2:
			Error_dialog(_("You must be connected to publish your informations"))
			return
		vcard = self.make_vcard()
		nick = ''
		if vcard.has_key('NICKNAME'):
			nick = vcard['NICKNAME']
		if nick == '':
			nick = gajim.config.get_per('accounts', self.account, 'name')
		self.plugin.nicks[self.account] = nick
		self.plugin.send('VCARD', self.account, vcard)

	def on_retrieve_button_clicked(self, widget):
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_USERID', 'URL', 'TEL_NUMBER',\
			'ADR_STREET', 'ADR_EXTADR', 'ADR_LOCALITY', 'ADR_REGION', 'ADR_PCODE',\
			'ADR_CTRY', 'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE'] 
		if self.plugin.connected[self.account] > 1:
			# clear all entries
			for e in entries:
				self.xml.get_widget(e + '_entry').set_text('')
			self.xml.get_widget('DESC_textview').get_buffer().set_text('')
			self.plugin.send('ASK_VCARD', self.account, self.jid)
		else:
			Error_dialog(_('You must be connected to get your informations'))

	def change_to_vcard(self):
		self.xml.get_widget('information_notebook').remove_page(0)
		self.xml.get_widget('nickname_label').set_text('Personal details')
		information_hbuttonbox = self.xml.get_widget('information_hbuttonbox')
		#publish button
		button = gtk.Button(stock=gtk.STOCK_GOTO_TOP)
		button.get_children()[0].get_children()[0].get_children()[1].\
			set_text('Publish')
		button.connect('clicked', self.on_publish_button_clicked)
		button.show_all()
		information_hbuttonbox.pack_start(button)
		#retrieve button
		button = gtk.Button(stock=gtk.STOCK_GOTO_BOTTOM)
		button.get_children()[0].get_children()[0].get_children()[1].\
			set_text('Retrieve')
		button.connect('clicked', self.on_retrieve_button_clicked)
		button.show_all()
		information_hbuttonbox.pack_start(button)
		#close button at the end
		button = self.xml.get_widget('close_button')
		information_hbuttonbox.reorder_child(button, 2)
		
		#make all entries editable
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_USERID', 'URL', 'TEL_NUMBER',\
			'ADR_STREET', 'ADR_EXTADR', 'ADR_LOCALITY', 'ADR_REGION', 'ADR_PCODE',\
			'ADR_CTRY', 'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE'] 
		for e in entries:
			self.xml.get_widget(e + '_entry').set_property('editable', True)

		description_textview = self.xml.get_widget('DESC_textview')
		description_textview.set_editable(True)
		description_textview.set_cursor_visible(True)

	#the user variable is the jid if vcard is true
	def __init__(self, user, plugin, account, vcard=False):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'vcard_information_window', APP)
		self.window = self.xml.get_widget('vcard_information_window')
		self.plugin = plugin
		self.user = user #don't use it if vcard is true
		self.account = account
		self.vcard = vcard

		if vcard:
			self.jid = user
			self.change_to_vcard()
		else:
			self.jid = user.jid
			self.fill_jabber_page()

		self.xml.signal_autoconnect(self)
		self.window.show_all()

class Edit_groups_dialog:
	"""Class for the edit group dialog window"""
	def __init__(self, user, account, plugin):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'edit_groups_dialog', APP)
		self.dialog = self.xml.get_widget('edit_groups_dialog')
		self.plugin = plugin
		self.account = account
		self.user = user
		self.list = self.xml.get_widget('groups_treeview')
		self.xml.get_widget('nickname_label').set_markup(\
			_('Contact\'s name: <i>%s</i>') % user.name)
		self.xml.get_widget('jid_label').set_markup(\
			_('JID: <i>%s</i>') % user.jid)
		self.xml.signal_autoconnect(self)
		self.dialog.show_all()
		self.init_list()

	def run(self):
		self.dialog.run()
		self.dialog.destroy()
		#TODO: do not send if unnecesary
		self.plugin.send('UPDUSER', self.account, (self.user.jid, \
			self.user.name, self.user.groups))

	def update_user(self):
		self.plugin.roster.remove_user(self.user, self.account)
		self.plugin.roster.add_user_to_roster(self.user.jid, self.account)

	def on_add_button_clicked(self, widget):
		group = self.xml.get_widget('group_entry').get_text()
		if not group:
			return
		# check if it already exists
		model = self.list.get_model()
		iter = model.get_iter_root()
		while iter:
			if model.get_value(iter, 0) == group:
				return
			iter = model.iter_next(iter)
		model.append((group, True))
		self.user.groups.append(group)
		self.update_user()

	def group_toggled_cb(self, cell, path):
		model = self.list.get_model()
		if model[path][1] and len(self.user.groups) == 1: # we try to remove 
																		  # the latest group
			Error_dialog(_('There must be at least one group for each contact'))
			return
		model[path][1] = not model[path][1]
		if model[path][1]:
			self.user.groups.append(model[path][0])
		else:
			self.user.groups.remove(model[path][0])
		self.update_user()

	def init_list(self):
		store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
		self.list.set_model(store)
		for g in self.plugin.roster.groups[self.account].keys():
			iter = store.append()
			store.set(iter, 0, g)
			if g in self.user.groups:
				store.set(iter, 1, True)
			else:
				store.set(iter, 1, False)
		column = gtk.TreeViewColumn(_('Group'))
		self.list.append_column(column)
		renderer = gtk.CellRendererText()
		column.pack_start(renderer)
		column.set_attributes(renderer, text=0)
		
		column = gtk.TreeViewColumn(_('In the group'))
		self.list.append_column(column)
		renderer = gtk.CellRendererToggle()
		column.pack_start(renderer)
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.group_toggled_cb)
		column.set_attributes(renderer, active=1)

class Passphrase_dialog:
	"""Class for Passphrase dialog"""
	def run(self):
		"""Wait for OK button to be pressed and return passphrase/password"""
		if self.autoconnect:
			gtk.gdk.threads_enter()
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			passphrase = self.passphrase_entry.get_text()
		else:
			passphrase = -1
		save_passphrase_checkbutton = self.xml.\
			get_widget('save_passphrase_checkbutton')
		self.window.destroy()
		if self.autoconnect:
			gtk.gdk.threads_leave()
		return passphrase, save_passphrase_checkbutton.get_active()

	def __init__(self, labeltext, checkbuttontext, autoconnect=0):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'passphrase_dialog', APP)
		self.window = self.xml.get_widget('passphrase_dialog')
		self.passphrase_entry = self.xml.get_widget('passphrase_entry')
		self.passphrase = -1
		self.autoconnect = autoconnect
		self.xml.get_widget('message_label').set_text(labeltext)
		self.xml.get_widget('save_passphrase_checkbutton').set_label(checkbuttontext)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

class choose_gpg_key_dialog:
	"""Class for GPG key dialog"""
	def run(self):
		"""Wait for Ok button to be pressed and return the selected key"""
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			selection = self.keys_treeview.get_selection()
			(model, iter) = selection.get_selected()
			keyID = [model.get_value(iter, 0), model.get_value(iter, 1)]
		else:
			keyID = -1
		self.window.destroy()
		return keyID

	def fill_tree(self, list):
		model = self.keys_treeview.get_model()
		for keyID in list.keys():
			model.append((keyID, list[keyID]))
	
	def __init__(self, secret_keys):
		#list : {keyID: userName, ...}
		xml = gtk.glade.XML(GTKGUI_GLADE, 'choose_gpg_key_dialog', APP)
		self.window = xml.get_widget('choose_gpg_key_dialog')
		self.keys_treeview = xml.get_widget('keys_treeview')
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.keys_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		self.keys_treeview.insert_column_with_attributes(-1, _('KeyID'), \
			renderer, text=0)
		renderer = gtk.CellRendererText()
		self.keys_treeview.insert_column_with_attributes(-1, _('User name'), \
			renderer, text=1)
		self.fill_tree(secret_keys)

		self.window.show_all()

class Change_status_message_dialog:
	def __init__(self, plugin, status, autoconnect = 0):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'change_status_message_dialog', APP)
		self.window = self.xml.get_widget('change_status_message_dialog')
		self.window.set_title(status.capitalize() + ' Status Message')
		self.plugin = plugin
		self.autoconnect = autoconnect
		message_textview = self.xml.get_widget('message_textview')
		self.message_buffer = message_textview.get_buffer()
		self.message_buffer.set_text(gajim.config.get('last_msg'))
		self.values = {'':''}
		i = 0
		while gajim.config.exist('msg%s_name' % i):
			self.values[gajim.config.get('msg%s_name' % i)] = \
				gajim.config.get('msg%s' % i)
			i += 1
		liststore = gtk.ListStore(str, str)
		message_comboboxentry = self.xml.get_widget('message_comboboxentry')
		message_comboboxentry.set_model(liststore)
		message_comboboxentry.set_text_column(0)
		for val in self.values.keys():
			message_comboboxentry.append_text(val)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def run(self):
		"""Wait for OK button to be pressed and return away messsage"""
		if self.autoconnect:
			gtk.gdk.threads_enter()
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			beg, end = self.message_buffer.get_bounds()
			message = self.message_buffer.get_text(beg, end, 0)
			gajim.config.set('last_msg', message)
		else:
			message = -1
		self.window.destroy()
		if self.autoconnect:
			gtk.gdk.threads_leave()
		return message

	def on_message_comboboxentry_changed(self, widget, data=None):
		model = widget.get_model()
		active = widget.get_active()
		if active < 0:
			return None
		name = model[active][0]
		self.message_buffer.set_text(self.values[name])
	
	def on_change_status_message_dialog_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Return or \
		event.keyval == gtk.keysyms.KP_Enter:  # catch CTRL+ENTER
			if (event.state & gtk.gdk.CONTROL_MASK):
				self.window.response(gtk.RESPONSE_OK)

class Add_new_contact_window:
	"""Class for Add_new_contact_window"""
	def __init__(self, plugin, account, jid=None):
		if plugin.connected[account] < 2:
			Error_dialog(_('You must be connected to add a contact'))
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'add_new_contact_window', APP)
		self.window = self.xml.get_widget('add_new_contact_window')
		self.old_uid_value = ''
		liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		liststore.append(['Jabber', ''])
		self.agents = ['Jabber']
		jid_agents = []
		for j in self.plugin.roster.contacts[account]:
			user = self.plugin.roster.contacts[account][j][0]
			if 'Agents' in user.groups:
				jid_agents.append(j)
		for a in jid_agents:
			if a.find('aim') > -1:
				name = 'AIM'
			elif a.find('icq') > -1:
				name = 'ICQ'
			elif a.find('msn') > -1:
				name = 'MSN'
			elif a.find('yahoo') > -1:
				name = 'Yahoo!'
			else:
				name = a
			iter = liststore.append([name, a])
			self.agents.append(name)
		protocol_combobox = self.xml.get_widget('protocol_combobox')
		protocol_combobox.set_model(liststore)
		protocol_combobox.set_active(0)
		self.fill_jid()
		if jid:
			self.xml.get_widget('jid_entry').set_text(jid)
			jid_splited = jid.split('@')
			self.xml.get_widget('uid_entry').set_text(jid_splited[0])
			if jid_splited[1] in jid_agents:
				protocol_combobox.set_active(jid_agents.index(jid_splited[1])+1)

		self.group_comboboxentry = self.xml.get_widget('group_comboboxentry')
		liststore = gtk.ListStore(str)
		self.group_comboboxentry.set_model(liststore)
		for g in self.plugin.roster.groups[account].keys():
			if g != 'not in the roster' and g != 'Agents':
				self.group_comboboxentry.append_text(g)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_cancel_button_clicked(self, widget):
		"""When Cancel button is clicked"""
		self.window.destroy()

	def on_subscribe_button_clicked(self, widget):
		"""When Subscribe button is clicked"""
		jid = self.xml.get_widget('jid_entry').get_text()
		nickname = self.xml.get_widget('nickname_entry').get_text()
		if not jid:
			return
		if jid.find('@') < 0:
			Error_dialog(_("The contact's name must be something like login@hostname"))
			return
		message_buffer = self.xml.get_widget('message_textview').get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0)
		group = self.group_comboboxentry.child.get_text()
		self.plugin.roster.req_sub(self, jid, message, self.account, group,\
			nickname)
		if self.xml.get_widget('auto_authorize_checkbutton').get_active():
			self.plugin.send('AUTH', self.account, jid)
		self.window.destroy()
		
	def fill_jid(self):
		protocol_combobox = self.xml.get_widget('protocol_combobox')
		model = protocol_combobox.get_model()
		index = protocol_combobox.get_active()
		jid = self.xml.get_widget('uid_entry').get_text()
		if index > 0:
			jid = jid.replace('@', '%')
		agent = model[index][1]
		if agent:
			jid += '@' + agent
		self.xml.get_widget('jid_entry').set_text(jid)

	def on_protocol_combobox_changed(self, widget):
		self.fill_jid()

	def guess_agent(self):
		uid = self.xml.get_widget('uid_entry').get_text()
		protocol_combobox = self.xml.get_widget('protocol_combobox')
		model = protocol_combobox.get_model()
		
		#If login contains only numbers, it's probably an ICQ number
		try:
			int(uid) # will raise ValueError if not all numbers
		except:
			pass
		else:
			if 'ICQ' in self.agents:
				protocol_combobox.set_active(self.agents.index('ICQ'))
				return
		protocol_combobox.set_active(0)

	def set_nickname(self):
		uid = self.xml.get_widget('uid_entry').get_text()
		nickname = self.xml.get_widget('nickname_entry').get_text()
		if nickname == self.old_uid_value:
			self.xml.get_widget('nickname_entry').set_text(uid.split('@')[0])
			
	def on_uid_entry_changed(self, widget):
		self.guess_agent()
		self.set_nickname()
		self.fill_jid()
		uid = self.xml.get_widget('uid_entry').get_text()
		self.old_uid_value = uid.split('@')[0]

class About_dialog:
	"""Class for about dialog"""
	def __init__(self):
		if gtk.pygtk_version < (2, 6, 0):
			Information_dialog(_('Gajim - A GTK jabber client'))
			return

		dlg = gtk.AboutDialog()
		dlg.set_name('Gajim')
		dlg.set_version(gajim.version.version)
		s = u'Copyright \xa9 2003-2005 Gajim Team'
		dlg.set_copyright(s)
		text = open('COPYING').read()
		dlg.set_license(text)

		dlg.set_comments(_('A GTK jabber client'))
		dlg.set_website('http://www.gajim.org')

		authors = ['Yann Le Boulanger <asterix@lagaule.org>', 'Vincent Hanquez <tab@snarc.org>', 'Nikos Kouremenos <kourem@gmail.com>', 'Alex Podaras <bigpod@gmail.com>']
		dlg.set_authors(authors)
		dlg.set_logo(gtk.gdk.pixbuf_new_from_file('plugins/gtkgui/pixmaps/logo.png'))
		dlg.set_translator_credits(_('translator_credits'))

		rep = dlg.run() # this run doesn't crash threads.. interesting.. 
		dlg.destroy()

class Confirmation_dialog:
	"""Class for confirmation dialog"""
	def get_response(self):
		response = self.dialog.run()
		self.dialog.destroy()
		return response

	def __init__(self, label):
		self.dialog = gtk.MessageDialog(None,\
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,\
			gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, label)

class Warning_dialog:
	"""Class for warning dialog"""
	def on_response(self, dialog, response_id):
		dialog.destroy()

	def __init__(self, label):
		dialog = gtk.MessageDialog(None,\
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,\
			gtk.MESSAGE_WARNING, gtk.BUTTONS_CLOSE, label)
		dialog.connect('response', self.on_response)
		dialog.show()

class Information_dialog:
	"""Class for information dialog"""
	def on_response(self, dialog, response_id):
		dialog.destroy()

	def __init__(self, label):
		dialog = gtk.MessageDialog(None,\
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,\
			gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, label)
		dialog.connect('response', self.on_response)
		dialog.show()

class Error_dialog:
	"""Class for error dialog"""
	def on_response(self, dialog, response_id):
		dialog.destroy()

	def __init__(self, label):
		dialog = gtk.MessageDialog(None,\
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,\
			gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, label)
		dialog.connect('response', self.on_response)
		dialog.show()

class subscription_request_window:
	def __init__(self, plugin, jid, text, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'subscription_request_window', APP)
		self.window = xml.get_widget('subscription_request_window')
		self.plugin = plugin
		self.jid = jid
		self.account = account
		xml.get_widget('from_label').set_text(\
			_('Subscription request from %s') % self.jid)
		xml.get_widget('message_textview').get_buffer().set_text(text)
		xml.signal_autoconnect(self)
		self.window.show_all()

	"""Class for authorization window :
	window that appears when a user wants to add us to his/her roster"""
	def on_close_button_clicked(self, widget):
		"""When Close button is clicked"""
		self.window.destroy()
		
	def on_authorize_button_clicked(self, widget):
		"""Accept the request"""
		self.plugin.send('AUTH', self.account, self.jid)
		self.window.destroy()
		if not self.plugin.roster.contacts[self.account].has_key(self.jid):
			Add_new_contact_window(self.plugin, self.account, self.jid)
	
	def on_deny_button_clicked(self, widget):
		"""refuse the request"""
		self.plugin.send('DENY', self.account, self.jid)
		self.window.destroy()

class Join_groupchat_window:
	def __init__(self, plugin, account, server='', room = ''):
		if plugin.connected[account] < 2:
			Error_dialog(_('You must be connected to join a groupchat'))
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'join_groupchat_window', APP)
		self.window = self.xml.get_widget('join_groupchat_window')
		self.xml.get_widget('server_entry').set_text(server)
		self.xml.get_widget('room_entry').set_text(room)
		self.xml.get_widget('nickname_entry').\
			set_text(self.plugin.nicks[self.account])
		self.xml.signal_autoconnect(self)
		self.plugin.windows[account]['join_gc'] = self #now add us to open windows

		self.recently_combobox = self.xml.get_widget('recently_combobox')
		liststore = gtk.ListStore(str)
		self.recently_combobox.set_model(liststore)
		cell = gtk.CellRendererText()
		self.recently_combobox.pack_start(cell, True)
		self.recently_combobox.add_attribute(cell, 'text', 0)
		self.recently_groupchat = gajim.config.get('recently_groupchat').split()
		for g in self.recently_groupchat:
			self.recently_combobox.append_text(g)

		self.window.show_all()

	def on_join_groupchat_window_destroy(self, widget):
		"""close window"""
		del self.plugin.windows[self.account]['join_gc'] # remove us from open windows

	def on_join_groupchat_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			widget.destroy()

	def on_recently_combobox_changed(self, widget):
		model = widget.get_model()
		iter = widget.get_active_iter()
		gid = model.get_value(iter, 0)
		self.xml.get_widget('room_entry').set_text(gid.split('@')[0])
		self.xml.get_widget('server_entry').set_text(gid.split('@')[1])

	def on_cancel_button_clicked(self, widget):
		"""When Cancel button is clicked"""
		self.window.destroy()

	def on_join_button_clicked(self, widget):
		"""When Join button is clicked"""
		nickname = self.xml.get_widget('nickname_entry').get_text()
		room = self.xml.get_widget('room_entry').get_text()
		server = self.xml.get_widget('server_entry').get_text()
		password = self.xml.get_widget('password_entry').get_text()
		jid = '%s@%s' % (room, server)
		if jid in self.recently_groupchat:
			self.recently_groupchat.remove(jid)
		self.recently_groupchat.insert(0, jid)
		if len(self.recently_groupchat) > 10:
			self.recently_groupchat = self.recently_groupchat[0:10]
		gajim.config.set('recently_groupchat', ' '.join(self.recently_groupchat))
		self.plugin.roster.new_group(jid, nickname, self.account)
		self.plugin.send('GC_JOIN', self.account, (nickname, room, server, \
			password))
			
		self.window.destroy()

class New_message_dialog:
	def __init__(self, plugin, account):
		if plugin.connected[account] < 2:
			Error_dialog(_('You must be connected to send a message to a contact'))
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'new_message_dialog', APP)
		self.window = self.xml.get_widget('new_message_dialog')
		self.jid_entry = self.xml.get_widget('jid_entry')

		our_jid = gajim.config.get_per('accounts', self.account, 'name') + '@' + \
			gajim.config.get_per('accounts', self.account, 'hostname')
		if len(gajim.config.connections) > 1:
			title = 'New Message as ' + our_jid
		else:
			title = 'New Message'
		self.window.set_title(title)
		
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_delete_event(self, widget, event):
		"""close window"""
		del self.plugin.windows['new_message']

	def on_cancel_button_clicked(self, widget):
		"""When Cancel button is clicked"""
		self.window.destroy()

	def on_chat_button_clicked(self, widget):
		"""When Chat button is clicked"""
		jid = self.jid_entry.get_text()
		if jid.find('@') == -1: # if no @ was given
			Error_dialog(_('User ID is not valid'))
			return
		self.window.destroy()
		# use User class, new_chat expects it that way
		# is it in the roster?
		if self.plugin.roster.contacts[self.account].has_key(jid):
			user = self.plugin.roster.contacts[self.account][jid][0]
		else:
			user = gtkgui.User(jid, jid, ['not in the roster'], \
				'not in the roster', 'not in the roster', 'none', None, '', 0, '')
			self.plugin.roster.contacts[self.account][jid] = [user]
			self.plugin.roster.add_user_to_roster(user.jid, self.account)			

		if not self.plugin.windows[self.account]['chats'].has_key(jid):
			self.plugin.roster.new_chat(user, self.account)
		self.plugin.windows[self.account]['chats'][jid].active_tab(jid)
		self.plugin.windows[self.account]['chats'][jid].window.present()
		#FIXME: PROBLEM WITH FOCUS

class Change_password_dialog:
	def __init__(self, plugin, account):
		if plugin.connected[account] < 2:
			Error_dialog(_('You must be connected to change your password'))
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'change_password_dialog', APP)
		self.dialog = self.xml.get_widget('change_password_dialog')
		self.password1_entry = self.xml.get_widget('password1_entry')
		self.password2_entry = self.xml.get_widget('password2_entry')

		self.window.show_all()

	def run(self):
		"""Wait for OK button to be pressed and return new password"""
		end = False
		while not end:
			rep = self.dialog.run()
			if rep == gtk.RESPONSE_OK:
				password1 = self.password1_entry.get_text()
				if not password1:
					Error_dialog(_('Your password cannot be empty'))
					continue
				password2 = self.password2_entry.get_text()
				if password1 != password2:
					Error_dialog(_('Confirmation password is not the same'))
					continue
				message = password1
			else:
				message = -1
			end = True
		self.dialog.destroy()
		return message

class Popup_window:
	def __init__(self, plugin, event_type, jid, account):
		self.plugin = plugin
		self.account = account
		self.jid = jid
		
		xml = gtk.glade.XML(GTKGUI_GLADE, 'popup_window', APP)
		self.window = xml.get_widget('popup_window')
		close_button = xml.get_widget('close_button')
		event_type_label = xml.get_widget('event_type_label')
		event_description_label = xml.get_widget('event_description_label')
		eventbox = xml.get_widget('eventbox')
		
		event_type_label.set_markup('<b>'+event_type+'</b>')

		if self.jid in self.plugin.roster.contacts[account]:
			txt = self.plugin.roster.contacts[account][self.jid][0].name
		else:
			txt = self.jid

		event_description_label.set_text(txt)
		
		# set colors [ http://www.w3schools.com/html/html_colornames.asp ]
		self.window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
		if event_type == 'Contact Online':
			close_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('forestgreen'))
			eventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('forestgreen'))
		elif event_type == 'Contact Offline':
			close_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('firebrick'))
			eventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('firebrick'))
		elif event_type == 'New Message':
			close_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('dodgerblue'))
			eventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('dodgerblue'))
			txt = 'From ' + txt
	
		# position the window to bottom-right of screen
		window_width, self.window_height = self.window.get_size()
		self.plugin.roster.popups_height += self.window_height
		self.window.move(gtk.gdk.screen_width() - window_width, \
					gtk.gdk.screen_height() - self.plugin.roster.popups_height)
		
		xml.signal_autoconnect(self)
		self.window.show_all()
		gobject.timeout_add(5000, self.on_timeout)

	def on_close_button_clicked(self, widget):
		self.adjust_height_and_move_popup_windows()

	def on_timeout(self):
		self.adjust_height_and_move_popup_windows()
		
	def adjust_height_and_move_popup_windows(self):
		#remove
		self.plugin.roster.popups_height -= self.window_height
		self.window.destroy()
		
		if len(self.plugin.roster.popup_windows) > 0:
			# we want to remove the first window added in the list
			self.plugin.roster.popup_windows.pop(0) # remove first item
		
		# move the rest of popup windows
		self.plugin.roster.popups_height = 0
		for window_instance in self.plugin.roster.popup_windows:
			window_width, window_height = window_instance.window.get_size()
			self.plugin.roster.popups_height += window_height
			window_instance.window.move(gtk.gdk.screen_width() - window_width, \
					gtk.gdk.screen_height() - self.plugin.roster.popups_height)

	def on_popup_window_button_press_event(self, widget, event):
		# use User class, new_chat expects it that way
		# is it in the roster?
		if self.plugin.roster.contacts[self.account].has_key(self.jid):
			user = self.plugin.roster.contacts[self.account][self.jid][0]
		else:
			user = gtkgui.User(self.jid, self.jid, ['not in the roster'], \
				'not in the roster', 'not in the roster', 'none', None, '', 0, '')
			self.plugin.roster.contacts[self.account][self.jid] = [user]
			self.plugin.roster.add_user_to_roster(user.self.jid, self.account)			

		self.plugin.roster.new_chat(user, self.account)
		self.plugin.windows[self.account]['chats'][self.jid].active_tab(self.jid)
		self.plugin.windows[self.account]['chats'][self.jid].window.present()
		self.adjust_height_and_move_popup_windows()
