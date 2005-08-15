##	roster_window.py
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

import gobject
import gtk
import os

from common import gajim
from time import time
from common import i18n

_ = i18n._

try:
	import dbus
	_version = getattr(dbus, 'version', (0, 20, 0)) 
except ImportError:
	_version = (0, 0, 0)
	
if _version >= (0, 41, 0):
	import dbus.service
	import dbus.glib # cause dbus 0.35+ doesn't return signal replies without it
	DbusPrototype = dbus.service.Object
elif _version >= (0, 20, 0):
	DbusPrototype = dbus.Object
else: #dbus is not defined
	DbusPrototype = str 

INTERFACE = 'org.gajim.dbus.RemoteInterface'
OBJ_PATH = '/org/gajim/dbus/RemoteObject'
SERVICE = 'org.gajim.dbus'

class Remote:
	def __init__(self, plugin):
		self.signal_object = None
		if 'dbus' not in globals() and not os.name == 'nt':
			print _('D-Bus python bindings are missing in this computer')
			print _('D-Bus capabilities of Gajim cannot be used')
			raise DbusNotSupported()
		try:
			session_bus = dbus.SessionBus()
		except:
			raise SessionBusNotPresent()
		
		if _version[1] >= 41:
			service = dbus.service.BusName(SERVICE, bus=session_bus)
			self.signal_object = SignalObject(service, plugin)
		elif _version[1] <= 40 and _version[1] >= 20:
			service=dbus.Service(SERVICE, session_bus)
			self.signal_object = SignalObject(service, plugin)
	
	def set_enabled(self, status):
		self.signal_object.disabled = not status
		
	def is_enabled(self):
		return not self.signal_object.disabled

	def raise_signal(self, signal, arg):
		if self.signal_object:
			self.signal_object.raise_signal(signal, repr(arg))
		

class SignalObject(DbusPrototype):
	''' Local object definition for /org/gajim/dbus/RemoteObject. This doc must 
	not be visible, because the clients can access only the remote object. '''
	
	def __init__(self, service, plugin):
		self.plugin = plugin
		self.first_show = True
		self.vcard_account = None
		self.disabled = False

		# register our dbus API
		if _version[1] >= 41:
			DbusPrototype.__init__(self, service, OBJ_PATH)
		elif _version[1] >= 30:
			DbusPrototype.__init__(self, OBJ_PATH, service)
		else:
			DbusPrototype.__init__(self, OBJ_PATH, service, 
			[	self.toggle_roster_appearance,
				self.show_next_unread,
				self.list_contacts,
				self.list_accounts,
				self.change_status,
				self.open_chat,
				self.send_message,
				self.contact_info
			])

	def raise_signal(self, signal, arg):
		''' raise a signal, with a single string message '''
		if self.disabled :
			return
		if _version[1] >= 30:
			from dbus import dbus_bindings
			message = dbus_bindings.Signal(OBJ_PATH, INTERFACE, signal)
			i = message.get_iter(True)
			i.append(arg)
			self._connection.send(message)
		else:
			self.emit_signal(INTERFACE, signal, arg)

	
	# signals 
	def VcardInfo(self, *vcard):
		pass

	def send_message(self, *args):
		''' send_message(jid, message, keyID=None, account=None)
		send 'message' to 'jid', using account (optional) 'account'.
		if keyID is specified, encrypt the message with the pgp key '''
		if self.disabled:
			return
		jid, message, keyID, account = self._get_real_arguments(args, 4)
		if not jid or not message:
			return None # or raise error
		if not keyID:
			keyID = ''
		connected_account = None
		accounts = gajim.contacts.keys()
		
		# if there is only one account in roster, take it as default
		if not account and len(accounts) == 1:
			account = accounts[0]
		if account:
			if gajim.connections[account].connected > 1: # account is  online
				connected_account = gajim.connections[account]
		else:
			for account in accounts:
				if gajim.contacts[account].has_key(jid) and \
					gajim.connections[account].connected > 1: # account is  online
					connected_account = gajim.connections[account]
					break
		if connected_account:
			res = connected_account.send_message(jid, message, keyID)
			return True
		return False

	def open_chat(self, *args):
		''' start_chat(jid, account=None) -> shows the tabbed window for new 
		message to 'jid', using account(optional) 'account ' '''
		if self.disabled:
			return
		jid, account = self._get_real_arguments(args, 2)
		if not jid:
			# FIXME: raise exception for missing argument (dbus0.35+ - released last week)
			return None
		if account:
			accounts = [account]
		else:
			accounts = gajim.connections.keys()
			if len(accounts) == 1:
				account = accounts[0]
		connected_account = None
		for acct in accounts:
			if gajim.connections[acct].connected > 1: # account is  online
				if self.plugin.windows[acct]['chats'].has_key(jid):
					connected_account = acct
					break
				# jid is in roster
				elif gajim.contacts[acct].has_key(jid):
					connected_account = acct
					break
				# we send the message to jid not in roster, because account is specified,
				# or there is only one account
				elif account: 
					connected_account = acct
		if connected_account:
			self.plugin.roster.new_chat_from_jid(connected_account, jid)
			# preserve the 'steal focus preservation'
			win = self.plugin.windows[connected_account]['chats'][jid].window
			if win.get_property('visible'):
				win.window.focus()
			return True
		return False
	
	def change_status(self, *args, **keywords):
		''' change_status(status, message, account). account is optional -
		if not specified status is changed for all accounts. '''
		if self.disabled:
			return
		status, message, account = self._get_real_arguments(args, 3)
		if status not in ('offline', 'online', 'chat', 
			'away', 'xa', 'dnd', 'invisible'):
			# FIXME: raise exception for bad status (dbus0.35)
			return None
		if account:
			gobject.idle_add(self.plugin.roster.send_status, account, 
				status, message)
		else:
			# account not specified, so change the status of all accounts
			for acc in gajim.contacts.keys():
				gobject.idle_add(self.plugin.roster.send_status, acc, 
					status, message)
		return None

	def show_next_unread(self, *args):
		''' Show the window(s) with next waiting messages in tabbed/group chats. '''
		if self.disabled:
			return
		#FIXME: when systray is disabled this method does nothing.
		#FIXME: show message from GC that refer to us (like systray does)
		if len(self.plugin.systray.jids) != 0:
			account = self.plugin.systray.jids[0][0]
			jid = self.plugin.systray.jids[0][1]
			acc = self.plugin.windows[account]
			jid_tab = None
			if acc['gc'].has_key(jid):
				jid_tab = acc['gc'][jid]
			elif acc['chats'].has_key(jid):
				jid_tab = acc['chats'][jid]
			else:
				self.plugin.roster.new_chat(
					gajim.contacts[account][jid][0], account)
				jid_tab = acc['chats'][jid]
			if jid_tab:
				jid_tab.set_active_tab(jid)
				jid_tab.window.present()
				# preserve the 'steal focus preservation'
				if self._is_first():
					jid_tab.window.window.focus()
				else:
					jid_tab.window.window.focus(long(time()))
				

	def contact_info(self, *args):
		''' get vcard info for a contact. This method returns nothing.
		You have to register the 'VcardInfo' signal to get the real vcard. '''
		if self.disabled:
			return
		
		[jid] = self._get_real_arguments(args, 1)
		if not jid:
			# FIXME: raise exception for missing argument (0.3+)
			return None

		accounts = gajim.contacts.keys()
		
		for account in accounts:
			if gajim.contacts[account].has_key(jid):
				self.vcard_account =  account
				gajim.connections[account].register_handler('VCARD', 
					self._receive_vcard)
				gajim.connections[account].request_vcard(jid)
				break
		return None

	def list_accounts(self, *args):
		''' list register accounts '''
		if self.disabled:
			return
		if gajim.contacts:
			result = gajim.contacts.keys()
			if result and len(result) > 0:
				return result
		return None


	def list_contacts(self, *args):
		if self.disabled:
			return
		''' list all contacts in the roster. If the first argument is specified,
		then return the contacts for the specified account '''
		[for_account] = self._get_real_arguments(args, 1)
		result = []
		if not gajim.contacts or len(gajim.contacts) == 0:
			return None
		if for_account:
			if gajim.contacts.has_key(for_account):
				for jid in gajim.contacts[for_account]:
					item = self._serialized_contacts(
						gajim.contacts[for_account][jid])
					if item:
						result.append(item)
			else:
				# 'for_account: is not recognised:', 
				# FIXME: there can be a return status for this [0.3+]
				return None
		else:
			for account in gajim.contacts:
				for jid in gajim.contacts[account]:
					item = self._serialized_contacts(gajim.contacts[account][jid])
					if item:
						result.append(item)
		# dbus 0.40 does not support return result as empty list
		if result == []:
			return None
		return result

	def toggle_roster_appearance(self, *args):
		''' shows/hides the roster window '''
		if self.disabled:
			return
		win = self.plugin.roster.window
		if win.get_property('visible'):
			gobject.idle_add(win.hide)
		else:
			win.present()
			# preserve the 'steal focus preservation'
			if self._is_first():
				win.window.focus()
			else:
				win.window.focus(long(time()))

	def _is_first(self):
		if self.first_show:
			self.first_show = False
			return True
		return False

	def _receive_vcard(self,account, array):
		if self.vcard_account:
			gajim.connections[self.vcard_account].unregister_handler('VCARD', 
				self._receive_vcard)
			self.unregistered_vcard = None
			if self.disabled:
				return
			if _version[1] >=30:
				self.VcardInfo(repr(array))
			else:
				self.emit_signal(INTERFACE, 'VcardInfo', 
					repr(array))

	def _get_real_arguments(self, args, desired_length):
		# supresses the first 'message' argument, which is set in dbus 0.23
		if _version[1] == 20:
			args=args[1:]
		if desired_length > 0:
			args = list(args)
			args.extend([None] * (desired_length - len(args)))
			args = args[:desired_length]
		return args

	def _serialized_contacts(self, contacts):
		''' get info from list of Contact objects and create a serialized
		dict for sending it over dbus '''
		if not contacts:
			return None
		prim_contact = None # primary contact
		for contact in contacts:
			if prim_contact == None or contact.priority > prim_contact.priority:
				prim_contact = contact
		contact_dict = {}
		contact_dict['name'] = prim_contact.name
		contact_dict['show'] = prim_contact.show
		contact_dict['jid'] = prim_contact.jid
		if prim_contact.keyID:
			keyID = None
			if len(prim_contact.keyID) == 8:
				keyID = prim_contact.keyID
			elif len(prim_contact.keyID) == 16:
				keyID = prim_contact.keyID[8:]
			if keyID:
				contact_dict['openpgp'] = keyID
		contact_dict['resources'] = []
		for contact in contacts:
			contact_dict['resources'].append(tuple([contact.resource, 
				contact.priority, contact.status]))
		return repr(contact_dict)
	
	
	if _version[1] >= 30 and _version[1] <= 40:
		method = dbus.method
		signal = dbus.signal
	elif _version[1] >= 41:
		method = dbus.service.method
		signal = dbus.service.signal

	if _version[1] >= 30:
		# prevent using decorators, because they are not supported 
		# on python < 2.4
		# FIXME: use decorators when python2.3 (and dbus 0.23) is OOOOOOLD
		toggle_roster_appearance = method(INTERFACE)(toggle_roster_appearance)
		list_contacts = method(INTERFACE)(list_contacts)
		list_accounts = method(INTERFACE)(list_accounts)
		show_next_unread = method(INTERFACE)(show_next_unread)
		change_status = method(INTERFACE)(change_status)
		open_chat = method(INTERFACE)(open_chat)
		contact_info = method(INTERFACE)(contact_info)
		send_message = method(INTERFACE)(send_message)
		VcardInfo = signal(INTERFACE)(VcardInfo)

class SessionBusNotPresent(Exception):
	''' This exception indicates that there is no session daemon '''
	def __init__(self):
		Exception.__init__(self)

	def __str__(self):
		return _('Session bus is not available')

class DbusNotSupported(Exception):
	''' D-Bus is not installed or python bindings are missing '''
	def __init__(self):
		Exception.__init__(self)

	def __str__(self):
		return _('D-Bus is not present on this machine')
