##	plugins/dialogs.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Alex Podaras <bigpod@gmail.com>
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
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

import gtkgui

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'


class vcard_information_window:
	"""Class for user's information window"""
	def on_user_information_window_destroy(self, widget=None):
		"""close window"""
		del self.plugin.windows[self.account]['infos'][self.jid]

	def on_close_button_clicked(self, widget):
		"""Save user's informations and update the roster on the Jabber server"""
		if self.vcard:
			widget.get_toplevel().destroy()
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
		account_info = self.plugin.accounts[self.account]
		oldlog = 1
		no_log_for = []
		if account_info.has_key('no_log_for'):
			no_log_for = account_info['no_log_for'].split()
			if self.user.jid in no_log_for:
				oldlog = 0
		log = self.xml.get_widget('log_checkbutton').get_active()
		if not log and not self.user.jid in no_log_for:
			no_log_for.append(self.user.jid)
		if log and self.user.jid in no_log_for:
			no_log_for.remove(self.user.jid)
		if oldlog != log:
			account_info['no_log_for'] = ' '.join(no_log_for)
			self.plugin.accounts[self.account] = account_info
			self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts, \
				'Gtkgui'))
		widget.get_toplevel().destroy()

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

	def fill_jabber_page(self):
		self.xml.get_widget('nickname_label').set_text(self.user.name)
		self.xml.get_widget('jid_label').set_text(self.user.jid)
		self.xml.get_widget('subscription_label').set_text(self.user.sub)
		if self.user.ask:
			self.xml.get_widget('ask_label').set_text(self.user.ask)
		else:
			self.xml.get_widget('ask_label').set_text('None')
		self.xml.get_widget('nickname_entry').set_text(self.user.name)
		account_info = self.plugin.accounts[self.account]
		log = 1
		if account_info.has_key('no_log_for'):
			if self.user.jid in account_info['no_log_for'].split(' '):
				log = 0
		self.xml.get_widget('log_checkbutton').set_active(log)
		resources = self.user.resource + ' (' + str(self.user.priority) + ')'
		if not self.user.status:
			self.user.status = ''
		stats = self.user.show + ' : ' + self.user.status
		for u in self.plugin.roster.contacts[self.account][self.user.jid]:
			if u.resource != self.user.resource:
				resources += '\n' + u.resource + ' (' + str(u.priority) + ')'
				if not u.status:
					u.status = ''
				stats += '\n' + u.show + ' : ' + u.status
		self.xml.get_widget('resource_label').set_text(resources)
		self.xml.get_widget('status_label').set_text(stats)
		self.plugin.send('ASK_VCARD', self.account, self.user.jid)

	def add_to_vcard(self, vcard, entry, txt):
		"""Add an information to the vCard dictionary"""
		entries = '_'.split(entry)
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
			nick = self.plugin.accounts[self.account]['name']
		self.plugin.nicks[self.account] = nick
		self.plugin.send('VCARD', self.account, vcard)

	def on_retrieve_button_clicked(self, widget):
		if self.plugin.connected[self.account] > 1:
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

	#the user variable is the jid if vcard is true
	def __init__(self, user, plugin, account, vcard=False):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'vcard_information_window', APP)
		self.window = self.xml.get_widget('vcard_information_window')
		self.plugin = plugin
		self.user = user #don't use it is vcard is true
		self.account = account
		self.vcard = vcard

		if vcard:
			self.jid = user
			self.change_to_vcard()
		else:
			self.jid = user.jid
			self.fill_jabber_page()

		self.xml.signal_autoconnect(self)

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
		self.init_list()

	def run(self):
		self.dialog.run()
		self.dialog.destroy()
		#TODO: send to the core

	def update_user(self):
		luser = self.plugin.roster.contacts[self.account][self.user.jid]
		for u in luser:
			self.plugin.roster.remove_user(u, self.account)
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
			#TODO: re-set the checkbutton
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
	
	def __init__(self):
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

class Change_status_message_dialog:
	"""Class for Away message dialog"""
	def run(self):
		"""Wait for OK button to be pressed and return away messsage"""
		if self.autoconnect:
			gtk.gdk.threads_enter()
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			beg, end = self.message_buffer.get_bounds()
			message = self.message_buffer.get_text(beg, end, 0)
			self.plugin.config['last_msg'] = message
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
		if event.keyval == gtk.keysyms.Return or 
		event.keyval == gtk.keysyms.KP_Enter:  # catch CTRL+ENTER
			if (event.state & gtk.gdk.CONTROL_MASK):
				self.window.response(gtk.RESPONSE_OK)
	
	def __init__(self, plugin, status, autoconnect = 0):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'change_status_message_dialog', APP)
		self.window = self.xml.get_widget('change_status_message_dialog')
		self.window.set_title(status.capitalize() + ' Status Message')
		self.plugin = plugin
		self.autoconnect = autoconnect
		message_textview = self.xml.get_widget('message_textview')
		self.message_buffer = message_textview.get_buffer()
		self.message_buffer.set_text(self.plugin.config['last_msg'])
		self.values = {'':''}
		i = 0
		while self.plugin.config.has_key('msg%s_name' % i):
			self.values[self.plugin.config['msg%s_name' % i]] = \
				self.plugin.config['msg%s' % i]
			i += 1
		liststore = gtk.ListStore(str, str)
		message_comboboxentry = self.xml.get_widget('message_comboboxentry')
		message_comboboxentry.set_model(liststore)
		message_comboboxentry.set_text_column(0)
		for val in self.values.keys():
			message_comboboxentry.append_text(val)
		self.xml.signal_autoconnect(self)

class Add_contact_window:
	"""Class for add_contact_window"""
	def on_cancel_button_clicked(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

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
		self.plugin.roster.req_sub(self, jid, message, self.account, nickname)
		if self.xml.get_widget('auto_authorize_checkbutton').get_active():
			self.plugin.send('AUTH', self.account, jid)
		widget.get_toplevel().destroy()
		
	def fill_jid(self):
		agent_combobox = self.xml.get_widget('agent_combobox')
		model = agent_combobox.get_model()
		index = agent_combobox.get_active()
		jid = self.xml.get_widget('uid_entry').get_text()
		if index > 0:
			jid = jid.replace('@', '%')
		agent = model[index][1]
		if agent:
			jid += '@' + agent
		self.xml.get_widget('jid_entry').set_text(jid)

	def on_agent_combobox_changed(self, widget):
		self.fill_jid()

	def guess_agent(self):
		uid = self.xml.get_widget('uid_entry').get_text()
		agent_combobox = self.xml.get_widget('agent_combobox')
		model = agent_combobox.get_model()
		
		#If login contains only numbers, it's probably an ICQ number
		try:
			int(uid) # will raise ValueError if not all numbers
		except:
			pass
		else:
			if 'ICQ' in self.agents:
				agent_combobox.set_active(self.agents.index('ICQ'))
				return
		agent_combobox.set_active(0)

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
		
	def __init__(self, plugin, account, jid=None):
		if plugin.connected[account] < 2:
			Error_dialog(_('You must be connected to add a contact'))
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'add_contact_window', APP)
		self.window = self.xml.get_widget('add_contact_window')
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
		agent_combobox = self.xml.get_widget('agent_combobox')
		agent_combobox.set_model(liststore)
		agent_combobox.set_active(0)
		self.fill_jid()
		if jid:
			self.xml.get_widget('jid_entry').set_text(jid)
			jid_splited = jid.split('@')
			self.xml.get_widget('uid_entry').set_text(jid_splited[0])
			if jid_splited[1] in jid_agents:
				agent_combobox.set_active(jid_agents.index(jid_splited[1])+1)
		self.xml.signal_autoconnect(self)

class About_dialog:
	"""Class for about dialog"""
	def __init__(self, plugin):
		if gtk.pygtk_version < (2, 6, 0):
			Information_dialog('Gajim - A GTK jabber client')
			return
		self.plugin = plugin
		dlg = gtk.AboutDialog()
		dlg.set_name('Gajim')
		dlg.set_version('0.6')
		s = u'Copyright \xa9 2003-2005 Gajim Team'
		dlg.set_copyright(s)
		text = open('COPYING').read()
		dlg.set_license(text)

		dlg.set_comments('A GTK jabber client')
		dlg.set_website('http://www.gajim.org')

		authors = ['Yann Le Boulanger <asterix@lagaule.org>', 'Vincent Hanquez <tab@snarc.org>', 'Nikos Kouremenos <kourem@gmail.com>', 'Alex Podaras <bigpod@gmail.com>']
		dlg.set_authors(authors)
		dlg.set_logo(gtk.gdk.pixbuf_new_from_file('plugins/gtkgui/pixmaps/logo.png'))
		dlg.set_translator_credits(_('translator_credits'))

		rep = dlg.run()
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
		#dialog.run() #IT freezes WHY? also if you do a lot of stuff all together it freezes

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
	"""Class for authorization window :
	window that appears when a user wants to add us to his/her roster"""
	def on_close_button_clicked(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()
		
	def on_authorize_button_clicked(self, widget):
		"""Accept the request"""
		self.plugin.send('AUTH', self.account, self.jid)
		widget.get_toplevel().destroy()
		if not self.plugin.roster.contacts[self.account].has_key(self.jid):
			Add_contact_window(self.plugin, self.account, self.jid)
	
	def on_deny_button_clicked(self, widget):
		"""refuse the request"""
		self.plugin.send('DENY', self.account, self.jid)
		widget.get_toplevel().destroy()
	
	def __init__(self, plugin, jid, text, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'subscription_request_window', APP)
		self.plugin = plugin
		self.jid = jid
		self.account = account
		xml.get_widget('from_label').set_text(\
			_('Subscription request from %s') % self.jid)
		xml.get_widget('message_textview').get_buffer().set_text(text)
		xml.signal_autoconnect(self)

class Join_groupchat_window:
	def on_join_groupchat_window_destroy(self, widget):
		"""close window"""
		del self.plugin.windows['join_gc'] # remove us from open windows

	def on_cancel_button_clicked(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def on_join_button_clicked(self, widget):
		"""When Join button is clicked"""
		nickname = self.xml.get_widget('nickname_entry').get_text()
		room = self.xml.get_widget('room_entry').get_text()
		server = self.xml.get_widget('server_entry').get_text()
		password = self.xml.get_widget('password_entry').get_text()
		jid = '%s@%s' % (room, server)
		self.plugin.roster.new_group(jid, nickname, self.account)
		#TODO: verify entries
		self.plugin.send('GC_JOIN', self.account, (nickname, room, server, \
			password))
			
		#FIXME: call active_tab()
		widget.get_toplevel().destroy()

	def __init__(self, plugin, account, server='', room = ''):
		if plugin.connected[account] < 2:
			Error_dialog(_('You must be connected to join a group chat'))
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
		self.plugin.windows['join_gc'] = self # now add us to open windows

class New_message_dialog:
	def on_delete_event(self, widget, event):
		"""close window"""
		del self.plugin.windows['new_message']

	def on_cancel_button_clicked(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def on_chat_button_clicked(self, widget):
		"""When Chat button is clicked"""
		jid = self.jid_entry.get_text()
		# use User class, new_chat expects it that way
		# is it in the roster?
		if not self.plugin.roster.contacts[self.account].has_key(jid):
			user = gtkgui.User(jid, jid, ['not in the roster'], \
				'not in the roster', 'not in the roster', 'none', None, '', 0, '')
			self.plugin.roster.contacts[self.account][jid] = [user]
			self.plugin.roster.add_user_to_roster(user.jid, self.account)
		else:
			user = self.plugin.roster.contacts[self.account][jid][0]
			
		if not self.plugin.windows[self.account]['chats'].has_key(jid):
			self.plugin.roster.new_chat(user, self.account)
		self.plugin.windows[self.account]['chats'][jid].active_tab(jid)
		self.plugin.windows[self.account]['chats'][jid].window.present()
		
		widget.get_toplevel().destroy()

	def __init__(self, plugin, account):
		if plugin.connected[account] < 2:
			Error_dialog(_('You must be connected to send a message to a contact'))
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'new_message_dialog', APP)
		self.window = self.xml.get_widget('new_message_dialog')
		self.jid_entry = self.xml.get_widget('jid_entry')
		self.xml.signal_autoconnect(self)
		self.plugin.windows['new_message'] = self # now add us to open windows

class Change_password_dialog:
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
		self.password1_entry.set_activates_default(True)
