##	plugins/dialogs.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@lagaule.org>
## 	- Vincent Hanquez <tab@snarc.org>
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

import pygtk
pygtk.require('2.0')
import gtk
from gtk import TRUE, FALSE
import gtk.glade,gobject
import string
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'


class infoUser_Window:
	"""Class for user's information window"""
	def delete_event(self, widget=None):
		"""close window"""
		del self.plugin.windows[self.account]['infos'][self.user.jid]

	def on_close(self, widget):
		"""Save user's informations and update the roster on the Jabber server"""
		#update: to know if things have changed to send things 
		# to server only if changes are done
		update = 0
		#update user.name if it's not ""
		entry_name = self.xml.get_widget('entry_name')
		newName = entry_name.get_text()
		if newName != self.user.name and newName != '':
			update = 1
			self.user.name = newName
			for i in self.plugin.roster.get_user_iter(self.user.jid, self.account):
				self.plugin.roster.tree.get_model().set_value(i, 1, newName)
		if update:
			self.plugin.send('UPDUSER', self.account, (self.user.jid, \
				self.user.name, self.user.groups))
		#log history ?
		acct = self.plugin.accounts[self.account]
		oldlog = 1
		no_log_for = []
		if acct.has_key('no_log_for'):
			no_log_for = acct['no_log_for'].split(' ')
			if self.user.jid in no_log_for:
				oldlog = 0
		log = self.xml.get_widget('chk_log').get_active()
		if not log and not self.user.jid in no_log_for:
			no_log_for.append(self.user.jid)
		if log and self.user.jid in no_log_for:
			no_log_for.remove(self.user.jid)
		if oldlog != log:
			acct['no_log_for'] = string.join(no_log_for, ' ')
			self.plugin.accounts[self.account] = acct
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
					self.set_value('entry_'+i+'_'+j, vcard[i][j])
			else:
				if i == 'DESC':
					self.xml.get_widget('textview_DESC').get_buffer().\
						set_text(vcard[i], 0)
				else:
					self.set_value('entry_'+i, vcard[i])

	def __init__(self, user, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Info_user', APP)
		self.window = self.xml.get_widget("Info_user")
		self.plugin = plugin
		self.user = user
		self.account = account

		self.xml.get_widget('label_name').set_text(user.name)
		self.xml.get_widget('label_id').set_text(user.jid)
		self.xml.get_widget('label_sub').set_text(user.sub)
		if user.ask:
			self.xml.get_widget('label_ask').set_text(user.ask)
		else:
			self.xml.get_widget('label_ask').set_text('None')
		self.xml.get_widget('entry_name').set_text(user.name)
		acct = self.plugin.accounts[account]
		log = 1
		if acct.has_key('no_log_for'):
			if user.jid in acct['no_log_for'].split(' '):
				log = 0
		self.xml.get_widget('chk_log').set_active(log)
		resources = user.resource + ' (' + str(user.priority) + ')'
		if not user.status:
			user.status = ''
		stats = user.show + ' : ' + user.status
		for u in self.plugin.roster.contacts[account][user.jid]:
			if u.resource != user.resource:
				resources += '\n' + u.resource + ' (' + str(u.priority) + ')'
				if not u.status:
					u.status = ''
				stats += '\n' + u.show + ' : ' + u.status
		self.xml.get_widget('label_resource').set_text(resources)
		self.xml.get_widget('label_status').set_text(stats)
		plugin.send('ASK_VCARD', account, self.user.jid)
		
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_close_clicked', self.on_close)

class passphrase_Window:
	"""Class for Passphrase Window"""
	def run(self):
		"""Wait for Ok button to be pressed and return passphrase"""
		rep = self.win.run()
		if rep == gtk.RESPONSE_OK:
			msg = self.entry.get_text()
		else:
			msg = -1
		chk = self.xml.get_widget("save_checkbutton")
		self.win.destroy()
		return msg, chk.get_active()

	def on_key_pressed(self, widget, event):
		if event.keyval == gtk.keysyms.Return:
			if self.autoconnect:
				self.on_ok_clicked(widget)
			else:
				self.win.response(gtk.RESPONSE_OK)

	def on_ok_clicked(self, widget):
		if self.autoconnect:
			self.msg = self.entry.get_text()
			gtk.main_quit()
	
	def on_cancel_clicked(self, widget):
		if self.autoconnect:
			gtk.main_quit()
	
	def get_pass(self):
		self.autoconnect = 0
		chk = self.xml.get_widget("save_checkbutton")
		self.win.destroy()
		return self.msg, chk.get_active()
		
	def delete_event(self, widget=None):
		"""close window"""
		if self.autoconnect:
			gtk.main_quit()

	def __init__(self, txt, autoconnect=0):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Passphrase', APP)
		self.win = self.xml.get_widget("Passphrase")
		self.entry = self.xml.get_widget("entry")
		self.msg = -1
		self.autoconnect = autoconnect
		self.xml.get_widget("label").set_text(txt)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_ok_clicked', self.on_ok_clicked)
		self.xml.signal_connect('on_cancel_clicked', self.on_cancel_clicked)
		self.xml.signal_connect('on_Passphrase_key_press_event', \
			self.on_key_pressed)

class choose_gpg_Window:
	"""Class for Away Message Window"""
	def run(self):
		"""Wait for Ok button to be pressed and return the selected key"""
		rep = self.xml.get_widget("Choose_gpg_key").run()
		if rep == gtk.RESPONSE_OK:
			selection = self.treeview.get_selection()
			(model, iter) = selection.get_selected()
			keyID = [model.get_value(iter, 0), model.get_value(iter, 1)]
		else:
			keyID = -1
		self.xml.get_widget("Choose_gpg_key").destroy()
		return keyID

	def fill_tree(self, list):
		model = self.treeview.get_model()
		for keyID in list.keys():
			model.append((keyID, list[keyID]))
	
	def __init__(self):
		#list : {keyID: userName, ...}
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Choose_gpg_key', APP)
		self.window = self.xml.get_widget("Choose_gpg_key")
		self.treeview = self.xml.get_widget("treeview")
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		self.treeview.insert_column_with_attributes(-1, _('KeyID'), renderer, \
			text=0)
		renderer = gtk.CellRendererText()
		self.treeview.insert_column_with_attributes(-1, _('User name'), renderer,\
			text=1)

class awayMsg_Window:
	"""Class for Away Message Window"""
	def run(self):
		"""Wait for Ok button to be pressed and return away messsage"""
		rep = self.xml.get_widget("Away_msg").run()
		if rep == gtk.RESPONSE_OK:
			beg, end = self.txtBuffer.get_bounds()
			msg = self.txtBuffer.get_text(beg, end, 0)
			self.plugin.config['last_msg'] = msg
		else:
			msg = -1
		self.xml.get_widget("Away_msg").destroy()
		return msg

	def on_entry_changed(self, widget, data=None):
		model = widget.get_model()
		active = widget.get_active()
		if active < 0:
			return None
		name = model[active][0]
		self.txtBuffer.set_text(self.values[name])
	
	def on_key_pressed(self, widget, event):
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.CONTROL_MASK):
				self.xml.get_widget("Away_msg").response(gtk.RESPONSE_OK)
	
	def __init__(self, plugin):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Away_msg', APP)
		self.plugin = plugin
		txt = self.xml.get_widget("textview")
		self.txtBuffer = txt.get_buffer()
		self.txtBuffer.set_text(self.plugin.config['last_msg'])
		self.values = {'':''}
		i = 0
		while self.plugin.config.has_key('msg%s_name' % i):
			self.values[self.plugin.config['msg%s_name' % i]] = \
				self.plugin.config['msg%s' % i]
			i += 1
		liststore = gtk.ListStore(str, str)
		cb = self.xml.get_widget('comboboxentry')
		cb.set_model(liststore)
		cb.set_text_column(0)
		for val in self.values.keys():
			cb.append_text(val)
		self.xml.signal_connect('on_comboboxentry_changed', self.on_entry_changed)
		self.xml.signal_connect('on_key_press_event', self.on_key_pressed)

class addContact_Window:
	"""Class for Add user window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['add']

	def on_cancel(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def on_subscribe(self, widget):
		"""When Subscribe button is clicked"""
		textview_sub = self.xml.get_widget("textview_sub")
		who = self.xml.get_widget('entry_who').get_text()
		pseudo = self.xml.get_widget('entry_pseudo').get_text()
		if not who:
			return
		if who.find('@') < 0:
			warning_Window(_("The contact's name must be something like login@hostname"))
			return
		buf = textview_sub.get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		self.plugin.roster.req_sub(self, who, txt, self.account, pseudo)
		if self.xml.get_widget('checkbutton_auth').get_active():
			self.plugin.send('AUTH', self.account, who)
		widget.get_toplevel().destroy()
		
	def fill_who(self):
		cb = self.xml.get_widget('combobox_agent')
		model = cb.get_model()
		index = cb.get_active()
		str = self.xml.get_widget('entry_login').get_text()
		if index > 0:
			str = str.replace("@", "%")
		agent = model[index][1]
		if agent:
			str += "@" + agent
		self.xml.get_widget('entry_who').set_text(str)

	def on_cb_changed(self, widget):
		self.fill_who()

	def guess_agent(self):
		login = self.xml.get_widget('entry_login').get_text()
		cb = self.xml.get_widget('combobox_agent')
		model = cb.get_model()
		
		#If login contains only numbers, it's probably an ICQ number
		try:
			string.atoi(login)
		except:
			pass
		else:
			if 'ICQ' in self.agents:
				cb.set_active(self.agents.index('ICQ'))
				return
		cb.set_active(0)

	def set_pseudo(self):
		login = self.xml.get_widget('entry_login').get_text()
		pseudo = self.xml.get_widget('entry_pseudo').get_text()
		if pseudo == self.old_login_value:
			self.xml.get_widget('entry_pseudo').set_text(login)
			
	def on_entry_login_changed(self, widget):
		self.guess_agent()
		self.set_pseudo()
		self.fill_who()
		self.old_login_value = self.xml.get_widget('entry_login').get_text()
		
	def __init__(self, plugin, account, jid=None):
		if not plugin.connected[account]:
			warning_Window(_("You must be connected to add a contact"))
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Add', APP)
		self.window = self.xml.get_widget('Add')
		self.old_login_value = ''
		liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		liststore.append(['Jabber', ''])
		self.agents = ['Jabber']
		jid_agents = []
		for j in self.plugin.roster.contacts[account]:
			user = self.plugin.roster.contacts[account][j][0]
			if 'Agents' in user.groups:
				jid_agents.append(j)
		for a in jid_agents:
			if a.find("aim") > -1:
				name = "AIM"
			elif a.find("icq") > -1:
				name = "ICQ"
			elif a.find("msn") > -1:
				name = "MSN"
			elif a.find("yahoo") > -1:
				name = "Yahoo!"
			else:
				name = a
			iter = liststore.append([name, a])
			self.agents.append(name)
		cb = self.xml.get_widget('combobox_agent')
		cb.set_model(liststore)
		cb.set_active(0)
		self.fill_who()
		if jid:
			self.xml.get_widget('entry_who').set_text(jid)
			jida = jid.split("@")
			self.xml.get_widget('entry_login').set_text(jida[0])
			if jida[1] in jid_agents:
				cb.set_active(jid_agents.index(jida[1])+1)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_button_sub_clicked', self.on_subscribe)
		self.xml.signal_connect('on_cancel_clicked', self.on_cancel)
		self.xml.signal_connect('on_cb_changed', self.on_cb_changed)
		self.xml.signal_connect('on_entry_login_changed', \
			self.on_entry_login_changed)

class warning_Window:
	"""Class for warning window : print a warning message"""
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def __init__(self, txt):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Warning', APP)
		xml.get_widget('label').set_text(txt)
		xml.signal_connect('on_close_clicked', self.on_close)

class about_Window:
	"""Class for about window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['about']
		
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def __init__(self, plugin):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'about_window', APP)
		self.window = xml.get_widget('about_window')
		self.plugin = plugin
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_close_clicked', self.on_close)


class confirm_Window:
	"""Class for confirmation window"""
	def wait(self):
		out = self.win.run()
		self.win.destroy()
		return out

	def __init__(self, label):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Confirm', APP)
		xml.get_widget('label_confirm').set_text(label)
		self.win = xml.get_widget('Confirm')

class authorize_Window:
	"""Class for authorization window :
	window that appears when a user wants to add us to his/her roster"""
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()
		
	def auth(self, widget):
		"""Accept the request"""
		self.plugin.send('AUTH', self.account, self.jid)
		widget.get_toplevel().destroy()
		if not self.plugin.roster.contacts[self.account].has_key(self.jid):
			addContact_Window(self.plugin, self.account, self.jid)
	
	def deny(self, widget):
		"""refuse the request"""
		self.plugin.send('DENY', self.account, self.jid)
		widget.get_toplevel().destroy()
	
	def __init__(self, plugin, jid, txt, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Sub_req', APP)
		self.plugin = plugin
		self.jid = jid
		self.account = account
		xml.get_widget('label').set_text(_("Subscription request from %s") % self.jid)
		xml.get_widget("textview").get_buffer().set_text(txt)
		xml.signal_connect('on_button_auth_clicked', self.auth)
		xml.signal_connect('on_button_deny_clicked', self.deny)
		xml.signal_connect('on_button_close_clicked', self.on_close)
