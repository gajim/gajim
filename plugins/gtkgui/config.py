#!/usr/bin/env python
##	plugins/config.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
##
##	Copyright (C) 2003 Gajim Team
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
import os,string#,time,Queue
#import common.optparser,common.sleepy

from dialogs import *

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'


class vCard_Window:
	"""Class for window that show vCard information"""
	def delete_event(self, widget=None):
		"""close window"""
		del self.plugin.windows[self.account]['infos'][self.jid]

	def on_close(self, widget):
		"""When Close button is clicked"""
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

	def add_to_vcard(self, vcard, entry, txt):
		"""Add an information to the vCard dictionary"""
		entries = string.split(entry, '_')
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
			txt = self.xml.get_widget('entry_'+e).get_text()
			if txt != '':
				vcard = self.add_to_vcard(vcard, e, txt)
		buf = self.xml.get_widget('textview_DESC').get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		if txt != '':
			vcard['DESC']= txt
		return vcard


	def on_retrieve(self, widget):
		if self.plugin.connected[self.account]:
			self.plugin.send('ASK_VCARD', self.account, self.jid)
		else:
			warning_Window("You must be connected to get your informations")

	def on_publish(self, widget):
		if not self.plugin.connected[self.account]:
			warning_Window("You must be connected to publish your informations")
			return
		vcard = self.make_vcard()
		nick = ''
		if vcard.has_key('NICKNAME'):
			nick = vcard['NICKNAME']
		if nick == '':
			nick = self.plugin.accounts[self.account]['name']
		self.plugin.nicks[self.account] = nick
		self.plugin.send('VCARD', self.account, vcard)

	def __init__(self, jid, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'vcard')
		self.jid = jid
		self.plugin = plugin
		self.account = account
		
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_close_clicked', self.on_close)
		self.xml.signal_connect('on_retrieve_clicked', self.on_retrieve)
		self.xml.signal_connect('on_publish_clicked', self.on_publish)


class preference_Window:
	"""Class for Preferences window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['preferences']

	def on_cancel(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def on_color_button_clicked(self, widget):
		"""Open a ColorSelectionDialog and change button's color"""
		if widget.name == 'colorIn':
			color = self.colorIn
			da = self.da_in
		elif widget.name == 'colorOut':
			color = self.colorOut
			da = self.da_out
		elif widget.name == 'colorStatus':
			color = self.colorStatus
			da = self.da_status
		colorseldlg = gtk.ColorSelectionDialog('Select Color')
		colorsel = colorseldlg.colorsel
		colorsel.set_previous_color(color)
		colorsel.set_current_color(color)
		colorsel.set_has_palette(gtk.TRUE)
		response = colorseldlg.run()
		if response == gtk.RESPONSE_OK:
			color = colorsel.get_current_color()
			da.modify_bg(gtk.STATE_NORMAL, color)
			if widget.name == 'colorIn':
				self.colorIn = color
			elif widget.name == 'colorOut':
				self.colorOut = color
			elif widget.name == 'colorStatus':
				self.colorStatus = color
		colorseldlg.destroy()
	
	def write_cfg(self):
		"""Save preferences in config File and apply them"""
		#Color for incomming messages
		colSt_in = '#'+(hex(self.colorIn.red)+'0')[2:4]\
			+(hex(self.colorIn.green)+'0')[2:4]\
			+(hex(self.colorIn.blue)+'0')[2:4]
		self.plugin.config['inmsgcolor'] = colSt_in
		#Color for outgoing messages
		colSt_out = '#'+(hex(self.colorOut.red)+'0')[2:4]\
			+(hex(self.colorOut.green)+'0')[2:4]\
			+(hex(self.colorOut.blue)+'0')[2:4]
		self.plugin.config['outmsgcolor'] = colSt_out
		#Color for status messages
		colSt_status = '#'+(hex(self.colorStatus.red)+'0')[2:4]\
			+(hex(self.colorStatus.green)+'0')[2:4]\
			+(hex(self.colorStatus.blue)+'0')[2:4]
		self.plugin.config['statusmsgcolor'] = colSt_status
		#update opened chat windows
		for a in self.plugin.accounts.keys():
			for w in self.plugin.windows[a]['chats'].keys():
				self.plugin.windows[a]['chats'][w].tagIn.\
					set_property("foreground", colSt_in)
				self.plugin.windows[a]['chats'][w].tagOut.\
					set_property("foreground", colSt_out)
				self.plugin.windows[a]['chats'][w].tagStatus.\
					set_property("foreground", colSt_status)
		#IconStyle
		ist = self.combo_iconstyle.entry.get_text()
		self.plugin.config['iconstyle'] = ist
		self.plugin.roster.mkpixbufs()
		#autopopup
		pp = self.chk_autopp.get_active()
		if pp == True:
			self.plugin.config['autopopup'] = 1
		else:
			self.plugin.config['autopopup'] = 0
		#autoaway
		aw = self.chk_autoaway.get_active()
		if aw == True:
			self.plugin.config['autoaway'] = 1
		else:
			self.plugin.config['autoaway'] = 0
		aat = self.spin_autoawaytime.get_value_as_int()
		self.plugin.config['autoawaytime'] = aat
		#autoxa
		xa = self.chk_autoxa.get_active()
		if xa == True:
			self.plugin.config['autoxa'] = 1
		else:
			self.plugin.config['autoxa'] = 0
		axt = self.spin_autoxatime.get_value_as_int()
		self.plugin.config['autoxatime'] = axt
		if self.plugin.sleeper:
			self.plugin.sleeper = common.sleepy.Sleepy(\
				self.plugin['autoawaytime']*60, self.plugin['autoxatime']*60)
		self.plugin.send('CONFIG', None, ('GtkGui', self.plugin.config))
		self.plugin.roster.draw_roster()
		
	def on_ok(self, widget):
		"""When Ok button is clicked"""
		self.write_cfg()
		self.xml.get_widget('Preferences').destroy()

	def change_notebook_page(self, number):
		self.notebook.set_current_page(number)

	def on_lookfeel_button_clicked(self, widget, data=None):
		self.change_notebook_page(0)
		
	def on_events_button_clicked(self, widget, data=None):
		self.change_notebook_page(1)
		
	def on_presence_button_clicked(self, widget, data=None):
		self.change_notebook_page(2)

	def __init__(self, plugin):
		"""Initialize Preference window"""
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Preferences')
		self.plugin = plugin
		self.da_in = self.xml.get_widget('drawing_in')
		self.da_out = self.xml.get_widget('drawing_out')
		self.da_status = self.xml.get_widget('drawing_status')
		self.combo_iconstyle = self.xml.get_widget('combo_iconstyle')
		self.chk_autopp = self.xml.get_widget('chk_autopopup')
		self.chk_autoaway = self.xml.get_widget('chk_autoaway')
		self.spin_autoawaytime = self.xml.get_widget('spin_autoawaytime')
		self.chk_autoxa = self.xml.get_widget('chk_autoxa')
		self.spin_autoxatime = self.xml.get_widget('spin_autoxatime')
		self.notebook = self.xml.get_widget('preferences_notebook')
		
		button = self.xml.get_widget('lookfeel_button')
		button.connect('clicked', self.on_lookfeel_button_clicked)
		button = self.xml.get_widget('events_button')
		button.connect('clicked', self.on_events_button_clicked)
		button = self.xml.get_widget('presence_button')
		button.connect('clicked', self.on_presence_button_clicked)

		#Color for incomming messages
		colSt = self.plugin.config['inmsgcolor']
		if not colSt:
			colSt = '#ff0000'
		cmapIn = self.da_in.get_colormap()
		self.colorIn = cmapIn.alloc_color(colSt)
		self.da_in.window.set_background(self.colorIn)
		
		#Color for outgoing messages
		colSt = self.plugin.config['outmsgcolor']
		if not colSt:
			colSt = '#0000ff'
		cmapOut = self.da_out.get_colormap()
		self.colorOut = cmapOut.alloc_color(colSt)
		self.da_out.window.set_background(self.colorOut)
		
		#Color for status messages
		colSt = self.plugin.config['statusmsgcolor']
		if not colSt:
			colSt = '#00ff00'
		cmapStatus = self.da_status.get_colormap()
		self.colorStatus = cmapStatus.alloc_color(colSt)
		self.da_status.window.set_background(self.colorStatus)
		
		#iconStyle
		list_style = os.listdir('plugins/gtkgui/icons/')
		l = []
		for i in list_style:
			if i != 'CVS' and i[0] != '.':
				l.append(i)
		if l.count == 0:
			l.append(" ")
		self.combo_iconstyle.set_popdown_strings(l)
		if self.plugin.config['iconstyle'] in l:
			self.combo_iconstyle.entry.set_text(self.plugin.config['iconstyle'])
		
		#Autopopup
		st = 0
		if self.plugin.config.has_key('autopopup'):
			st = self.plugin.config['autopopup']
		self.chk_autopp.set_active(st)

		#Autoaway
		st = 1
		if self.plugin.config.has_key('autoaway'):
			st = self.plugin.config['autoaway']
		self.chk_autoaway.set_active(st)
		self.chk_autoaway.set_sensitive(0)

		#Autoawaytime
		st = 10
		if self.plugin.config.has_key('autoawaytime'):
			st = self.plugin.config['autoawaytime']
		self.spin_autoawaytime.set_value(st)
		self.spin_autoawaytime.set_sensitive(0)

		#Autoxa
		st = 1
		if self.plugin.config.has_key('autoxa'):
			st = self.plugin.config['autoxa']
		self.chk_autoxa.set_active(st)
		self.chk_autoxa.set_sensitive(0)

		#Autoxatime
		st = 20
		if self.plugin.config.has_key('autoxatime'):
			st = self.plugin.config['autoxatime']
		self.spin_autoxatime.set_value(st)
		self.spin_autoxatime.set_sensitive(0)

		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_but_col_clicked', \
			self.on_color_button_clicked)
		self.xml.signal_connect('on_ok_clicked', self.on_ok)
		self.xml.signal_connect('on_cancel_clicked', self.on_cancel)


class accountPreference_Window:
	"""Class for account informations"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['accountPreference']
	
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def init_account(self, infos):
		"""Initialize window with defaults values"""
		if infos.has_key('name'):
			self.xml.get_widget("entry_name").set_text(infos['name'])
		if infos.has_key('jid'):
			self.xml.get_widget("entry_jid").set_text(infos['jid'])
		if infos.has_key('password'):
			self.xml.get_widget("entry_password").set_text(infos['password'])
		if infos.has_key('ressource'):
			self.xml.get_widget("entry_ressource").set_text(infos['ressource'])
		if infos.has_key('use_proxy'):
			self.xml.get_widget("checkbutton_proxy").set_active(infos['use_proxy'])
		if infos.has_key('proxyhost'):
			self.xml.get_widget("entry_proxyhost").set_text(infos['proxyhost'])
		if infos.has_key('proxyport'):
#			self.xml.get_widget("entry_proxyport").set_text('%i'%\
			self.xml.get_widget("entry_proxyport").set_text(\
				infos['proxyport'])

	def on_save_clicked(self, widget):
		"""When save button is clicked : Save informations in config file"""
		entryPass = self.xml.get_widget("entry_password")
		entryRessource = self.xml.get_widget("entry_ressource")
		check = self.xml.get_widget("checkbutton")
		entryName = self.xml.get_widget("entry_name")
		entryJid = self.xml.get_widget("entry_jid")
		checkProxy = self.xml.get_widget("checkbutton_proxy")
		if checkProxy.get_active():
			useProxy = 1
		else:
			useProxy = 0
		entryProxyhost = self.xml.get_widget("entry_proxyhost")
		entryProxyport = self.xml.get_widget("entry_proxyport")
		proxyPort = entryProxyport.get_text()
		name = entryName.get_text()
		jid = entryJid.get_text()
		if (name == ''):
			warning_Window('You must enter a name for this account')
			return 0
		if (jid == '') or (string.count(jid, '@') != 1):
			warning_Window('You must enter a Jabber ID for this account\n\
				For example : login@hostname')
			return 0
		if proxyPort != '':
			try:
				proxyPort = string.atoi(proxyPort)
			except ValueError:
				warning_Window('Proxy Port must be a port number')
				return 0
		(login, hostname) = string.split(jid, '@')
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
				del self.plugin.windows[self.account]
				del self.plugin.queues[self.account]
				del self.plugin.connected[self.account]
				del self.plugin.nicks[self.account]
				del self.plugin.roster.groups[self.account]
				del self.plugin.roster.contacts[self.account]
				del self.plugin.accounts[self.account]
				self.plugin.send('ACC_CHG', self.account, name)
				self.plugin.accounts[name] = {'name': login, 'hostname': hostname,\
					'password': entryPass.get_text(), 'ressource': \
					entryRessource.get_text(), 'use_proxy': useProxy, 'proxyhost': \
					entryProxyhost.get_text(), 'proxyport': proxyPort}
				self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts))
				#refresh accounts window
				if self.plugin.windows.has_key('accounts'):
					self.plugin.windows['accounts'].init_accounts()
				#refresh roster
				self.plugin.roster.draw_roster()
				widget.get_toplevel().destroy()
				return
		#if it's a new account
		else:
			if name in self.plugin.accounts.keys():
				warning_Window('An account already has this name')
				return
			#if we neeed to register a new account
			if check.get_active():
				self.plugin.send('NEW_ACC', None, (hostname, login, \
					entryPass.get_text(), name, entryRessource.get_text(), \
					checkProxy.get_active(), entryProxyhost.get_text(), \
					entryProxyport.get_text()))
				check.set_active(FALSE)
				return
		self.plugin.accounts[name] = {'name': login, 'hostname': hostname,\
			'password': entryPass.get_text(), 'ressource': \
			entryRessource.get_text(), 'use_proxy': useProxy, 'proxyhost': \
			entryProxyhost.get_text(), 'proxyport': proxyPort}
		self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts))
		#update variables
		self.plugin.windows[name] = {'infos': {}, 'chats': {}}
		self.plugin.queues[name] = {}
		self.plugin.connected[name] = 0
		self.plugin.roster.groups[name] = {}
		self.plugin.roster.contacts[name] = {}
		#refresh accounts window
		if self.plugin.windows.has_key('accounts'):
			self.plugin.windows['accounts'].init_accounts()
		#refresh roster
		self.plugin.roster.draw_roster()
		widget.get_toplevel().destroy()

	def on_edit_details_clicked(self, widget):
		entryJid = self.xml.get_widget("entry_jid")
		if not self.plugin.windows.has_key('vcard'):
			self.plugin.windows[self.account]['infos'][entryJid.get_text()] = \
				vCard_Window(entryJid.get_text(), self.plugin, self.account)
			if self.plugin.connected[self.account]:
				self.plugin.send('ASK_VCARD', self.account, entryJid.get_text())
			else:
				warning_Window("You must be connected to get your informations")
	
	#info must be a dictionnary
	def __init__(self, plugin, infos = {}):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Account')
		self.plugin = plugin
		self.account = ''
		self.modify = False
		if infos:
			self.modify = True
			self.account = infos['name']
			self.init_account(infos)
			self.xml.get_widget("checkbutton").set_sensitive(FALSE)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_save_clicked', self.on_save_clicked)
		self.xml.signal_connect('on_edit_details_clicked', \
			self.on_edit_details_clicked)
		self.xml.signal_connect('on_close_clicked', self.on_close)


class accounts_Window:
	"""Class for accounts window : lists of accounts"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['accounts']
		
#Not for the moment ... but maybe one day there will be a button	
#	def on_close(self, widget):
#		"""When Close button is clicked"""
#		widget.get_toplevel().destroy()
		
	def init_accounts(self):
		"""initialize listStore with existing accounts"""
		self.xml.get_widget("modify_button").set_sensitive(False)
		self.xml.get_widget("delete_button").set_sensitive(False)
		model = self.treeview.get_model()
		model.clear()
		for account in self.plugin.accounts:
			iter = model.append()
			model.set(iter, 0, account, 1, \
				self.plugin.accounts[account]["hostname"])

	def on_row_activated(self, widget):
		"""Activate delete and modify buttons when a row is selected"""
		self.xml.get_widget("modify_button").set_sensitive(True)
		self.xml.get_widget("delete_button").set_sensitive(True)

	def on_new_clicked(self, widget):
		"""When new button is clicked : open an account information window"""
		if not self.plugin.windows.has_key('accountPreference'):
			self.plugin.windows['accountPreference'] = \
				accountPreference_Window(self.plugin)

	def on_delete_clicked(self, widget):
		"""When delete button is clicked :
		Remove an account from the listStore and from the config file"""
		sel = self.treeview.get_selection()
		(model, iter) = sel.get_selected()
		account = model.get_value(iter, 0)
		window = confirm_Window('Are you sure you want to remove this account (' \
			+ account + ') ?')
		if window.wait() == gtk.RESPONSE_OK:
			if self.plugin.connected[account]:
				self.plugin.send('STATUS', account, ('offline', 'offline'))
			del self.plugin.accounts[account]
			self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts))
			del self.plugin.windows[account]
			del self.plugin.queues[account]
			del self.plugin.connected[account]
			del self.plugin.roster.groups[account]
			del self.plugin.roster.contacts[account]
			self.plugin.roster.draw_roster()
			self.init_accounts()

	def on_modify_clicked(self, widget):
		"""When modify button is clicked :
		open the account information window for this account"""
		if not self.plugin.windows.has_key('accountPreference'):
			infos = {}
			sel = self.treeview.get_selection()
			(model, iter) = sel.get_selected()
			account = model.get_value(iter, 0)
			infos['name'] = account
			if self.plugin.accounts[account].has_key("name"):
				infos['jid'] = self.plugin.accounts[account]["name"] + \
					'@' +  self.plugin.accounts[account]["hostname"]
			if self.plugin.accounts[account].has_key("password"):
				infos['password'] = self.plugin.accounts[account]["password"]
			if self.plugin.accounts[account].has_key("ressource"):
				infos['ressource'] = self.plugin.accounts[account]["ressource"]
			if self.plugin.accounts[account].has_key("use_proxy"):
				infos['use_proxy'] = self.plugin.accounts[account]["use_proxy"]
			if self.plugin.accounts[account].has_key("proxyhost"):
				infos['proxyhost'] = self.plugin.accounts[account]["proxyhost"]
			if self.plugin.accounts[account].has_key("proxyport"):
				infos['proxyport'] = self.plugin.accounts[account]["proxyport"]
			self.plugin.windows['accountPreference'] = \
				accountPreference_Window(self.plugin, infos)
		
	def __init__(self, plugin):
		self.plugin = plugin
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Accounts')
		self.treeview = self.xml.get_widget("treeview")
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.treeview.insert_column_with_attributes(-1, 'Name', renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.treeview.insert_column_with_attributes(-1, 'Server', \
			renderer, text=1)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		self.xml.signal_connect('on_new_clicked', self.on_new_clicked)
		self.xml.signal_connect('on_delete_clicked', self.on_delete_clicked)
		self.xml.signal_connect('on_modify_clicked', self.on_modify_clicked)
		self.init_accounts()


class agentRegistration_Window:
	"""Class for agent registration window :
	window that appears when we want to subscribe to an agent"""
	def on_cancel(self, widget):
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
	
	def on_ok(self, widget):
		"""When Ok button is clicked :
		send registration info to the core"""
		for name in self.entries.keys():
			self.infos[name] = self.entries[name].get_text()
		self.plugin.send('REG_AGENT', self.account, self.agent)
		widget.get_toplevel().destroy()
	
	def __init__(self, agent, infos, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'agent_reg')
		self.agent = agent
		self.infos = infos
		self.plugin = plugin
		self.account = account
		self.xml.get_widget('agent_reg').set_title('Register to ' + agent)
		self.xml.get_widget('label').set_text(infos['instructions'])
		self.entries = {}
		self.draw_table()
		self.xml.signal_connect('on_cancel_clicked', self.on_cancel)
		self.xml.signal_connect('on_button_ok_clicked', self.on_ok)


class browseAgent_Window:
	"""Class for bowser agent window :
	to know the agents on the selected server"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows[self.account]['browser']

	def on_cancel(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()
		
	def browse(self):
		"""Send a request to the core to know the available agents"""
		self.plugin.send('REQ_AGENTS', self.account, None)
	
	def agents(self, agents):
		"""When list of available agent arrive :
		Fill the treeview with it"""
		model = self.treeview.get_model()
		for jid in agents.keys():
			iter = model.append()
#			model.set(iter, 0, agents[jid]['name'], 1, agents[jid]['service'])
			model.set(iter, 0, agents[jid]['name'], 1, jid)

	def on_refresh(self, widget):
		"""When refresh button is clicked :
		refresh list : clear and rerequest it"""
		self.treeview.get_model().clear()
		self.browse()

	def on_row_activated(self, widget, path, col=0):
		"""When a row is activated :
		Ask specific informations about the selected agent and close the window"""
		model = self.treeview.get_model()
		iter = model.get_iter(path)
		service = model.get_value(iter, 1)
		self.plugin.send('REQ_AGENT_INFO', self.account, service)
		widget.get_toplevel().destroy()
		
	def __init__(self, plugin, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'browser')
		self.treeview = xml.get_widget('treeview')
		self.plugin = plugin
		self.account = account
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.treeview.insert_column_with_attributes(-1, 'Name', renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.treeview.insert_column_with_attributes(-1, 'Service', \
			renderer, text=1)

		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_refresh_clicked', self.on_refresh)
		xml.signal_connect('on_row_activated', self.on_row_activated)
		xml.signal_connect('on_close_clicked', self.on_close)
		if self.plugin.connected[account]:
			self.browse()
		else:
			warning_Window("You must be connected to view Agents")
