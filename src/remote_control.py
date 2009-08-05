# -*- coding:utf-8 -*-
## src/remote_control.py
##
## Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
##                         Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    Julien Pivotto <roidelapluie AT gmail.com>
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

import gobject
import os

from common import gajim
from common import helpers
from time import time
from dialogs import AddNewContactWindow, NewChatDialog, JoinGroupchatWindow

from common import dbus_support
if dbus_support.supported:
	import dbus
	if dbus_support:
		import dbus.service
		import dbus.glib

INTERFACE = 'org.gajim.dbus.RemoteInterface'
OBJ_PATH = '/org/gajim/dbus/RemoteObject'
SERVICE = 'org.gajim.dbus'

# type mapping

# in most cases it is a utf-8 string
DBUS_STRING = dbus.String

# general type (for use in dicts, where all values should have the same type)
DBUS_BOOLEAN = dbus.Boolean
DBUS_DOUBLE = dbus.Double
DBUS_INT32 = dbus.Int32
# dictionary with string key and binary value
DBUS_DICT_SV = lambda : dbus.Dictionary({}, signature="sv")
# dictionary with string key and value
DBUS_DICT_SS = lambda : dbus.Dictionary({}, signature="ss")
# empty type (there is no equivalent of None on D-Bus, but historically gajim
# used 0 instead)
DBUS_NONE = lambda : dbus.Int32(0)

def get_dbus_struct(obj):
	''' recursively go through all the items and replace
	them with their casted dbus equivalents
	'''
	if obj is None:
		return DBUS_NONE()
	if isinstance(obj, (unicode, str)):
		return DBUS_STRING(obj)
	if isinstance(obj, int):
		return DBUS_INT32(obj)
	if isinstance(obj, float):
		return DBUS_DOUBLE(obj)
	if isinstance(obj, bool):
		return DBUS_BOOLEAN(obj)
	if isinstance(obj, (list, tuple)):
		result = dbus.Array([get_dbus_struct(i) for i in obj],
			signature='v')
		if result == []:
			return DBUS_NONE()
		return result
	if isinstance(obj, dict):
		result = DBUS_DICT_SV()
		for key, value in obj.items():
			result[DBUS_STRING(key)] = get_dbus_struct(value)
		if result == {}:
			return DBUS_NONE()
		return result
	# unknown type
	return DBUS_NONE()

class Remote:
	def __init__(self):
		self.signal_object = None
		session_bus = dbus_support.session_bus.SessionBus()

		bus_name = dbus.service.BusName(SERVICE, bus=session_bus)
		self.signal_object = SignalObject(bus_name)

	def raise_signal(self, signal, arg):
		if self.signal_object:
			try:
				getattr(self.signal_object, signal)(get_dbus_struct(arg))
			except UnicodeDecodeError:
				pass # ignore error when we fail to announce on dbus


class SignalObject(dbus.service.Object):
	''' Local object definition for /org/gajim/dbus/RemoteObject.
	(This docstring is not be visible, because the clients can access only the remote object.)'''

	def __init__(self, bus_name):
		self.first_show = True
		self.vcard_account = None

		# register our dbus API
		dbus.service.Object.__init__(self, bus_name, OBJ_PATH)

	@dbus.service.signal(INTERFACE, signature='av')
	def Roster(self, account_and_data):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def AccountPresence(self, status_and_account):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def ContactPresence(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def ContactAbsence(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def ContactStatus(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def NewMessage(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def Subscribe(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def Subscribed(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def Unsubscribed(self, account_and_jid):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def NewAccount(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def VcardInfo(self, account_and_vcard):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def LastStatusTime(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def OsInfo(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def EntityTime(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def GCPresence(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def GCMessage(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def RosterInfo(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE, signature='av')
	def NewGmail(self, account_and_array):
		pass

	def raise_signal(self, signal, arg):
		'''raise a signal, with a single argument of unspecified type
		Instead of obj.raise_signal("Foo", bar), use obj.Foo(bar).'''
		getattr(self, signal)(arg)

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='s')
	def get_status(self, account):
		'''Returns status (show to be exact) which is the global one
		unless account is given'''
		if not account:
			# If user did not ask for account, returns the global status
			return DBUS_STRING(helpers.get_global_show())
		# return show for the given account
		index = gajim.connections[account].connected
		return DBUS_STRING(gajim.SHOW_LIST[index])

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='s')
	def get_status_message(self, account):
		'''Returns status which is the global one
		unless account is given'''
		if not account:
			# If user did not ask for account, returns the global status
			return DBUS_STRING(str(helpers.get_global_status()))
		# return show for the given account
		status = gajim.connections[account].status
		return DBUS_STRING(status)

	def _get_account_and_contact(self, account, jid):
		'''get the account (if not given) and contact instance from jid'''
		connected_account = None
		contact = None
		accounts = gajim.contacts.get_accounts()
		# if there is only one account in roster, take it as default
		# if user did not ask for account
		if not account and len(accounts) == 1:
			account = accounts[0]
		if account:
			if gajim.connections[account].connected > 1: # account is connected
				connected_account = account
				contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
		else:
			for account in accounts:
				contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
				if contact and gajim.connections[account].connected > 1:
					# account is connected
					connected_account = account
					break
		if not contact:
			contact = jid

		return connected_account, contact

	def _get_account_for_groupchat(self, account, room_jid):
		'''get the account which is connected to groupchat (if not given)
		or check if the given account is connected to the groupchat'''
		connected_account = None
		accounts = gajim.contacts.get_accounts()
		# if there is only one account in roster, take it as default
		# if user did not ask for account
		if not account and len(accounts) == 1:
			account = accounts[0]
		if account:
			if gajim.connections[account].connected > 1 and \
			room_jid in gajim.gc_connected[account] and \
			gajim.gc_connected[account][room_jid]:
				# account and groupchat are connected
				connected_account = account
		else:
			for account in accounts:
				if gajim.connections[account].connected > 1 and \
				room_jid in gajim.gc_connected[account] and \
				gajim.gc_connected[account][room_jid]:
					# account and groupchat are connected
					connected_account = account
					break
		return connected_account

	@dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
	def send_file(self, file_path, jid, account):
		'''send file, located at 'file_path' to 'jid', using account
		(optional) 'account' '''
		jid = self._get_real_jid(jid, account)
		connected_account, contact = self._get_account_and_contact(account, jid)

		if connected_account:
			if file_path.startswith('file://'):
				file_path=file_path[7:]
			if os.path.isfile(file_path): # is it file?
				gajim.interface.instances['file_transfers'].send_file(
					connected_account, contact, file_path)
				return DBUS_BOOLEAN(True)
		return DBUS_BOOLEAN(False)

	def _send_message(self, jid, message, keyID, account, type_ = 'chat',
	subject = None):
		'''can be called from send_chat_message (default when send_message)
		or send_single_message'''
		if not jid or not message:
			return DBUS_BOOLEAN(False)
		if not keyID:
			keyID = ''

		connected_account, contact = self._get_account_and_contact(account, jid)
		if connected_account:
			connection = gajim.connections[connected_account]
			connection.send_message(jid, message, keyID, type_, subject)
			return DBUS_BOOLEAN(True)
		return DBUS_BOOLEAN(False)

	@dbus.service.method(INTERFACE, in_signature='ssss', out_signature='b')
	def send_chat_message(self, jid, message, keyID, account):
		'''Send chat 'message' to 'jid', using account (optional) 'account'.
		if keyID is specified, encrypt the message with the pgp key '''
		jid = self._get_real_jid(jid, account)
		return self._send_message(jid, message, keyID, account)

	@dbus.service.method(INTERFACE, in_signature='sssss', out_signature='b')
	def send_single_message(self, jid, subject, message, keyID, account):
		'''Send single 'message' to 'jid', using account (optional) 'account'.
		if keyID is specified, encrypt the message with the pgp key '''
		jid = self._get_real_jid(jid, account)
		return self._send_message(jid, message, keyID, account, type, subject)

	@dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
	def send_groupchat_message(self, room_jid, message, account):
		'''Send 'message' to groupchat 'room_jid',
		using account (optional) 'account'.'''
		if not room_jid or not message:
			return DBUS_BOOLEAN(False)
		connected_account = self._get_account_for_groupchat(account, room_jid)
		if connected_account:
			connection = gajim.connections[connected_account]
			connection.send_gc_message(room_jid, message)
			return DBUS_BOOLEAN(True)
		return DBUS_BOOLEAN(False)

	@dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
	def open_chat(self, jid, account, message):
		'''Shows the tabbed window for new message to 'jid', using account
		(optional) 'account' '''
		if not jid:
			raise dbus_support.MissingArgument()
		jid = self._get_real_jid(jid, account)
		try:
			jid = helpers.parse_jid(jid)
		except Exception:
			# Jid is not conform, ignore it
			return DBUS_BOOLEAN(False)

		if account:
			accounts = [account]
		else:
			accounts = gajim.connections.keys()
			if len(accounts) == 1:
				account = accounts[0]
		connected_account = None
		first_connected_acct = None
		for acct in accounts:
			if gajim.connections[acct].connected > 1: # account is  online
				contact = gajim.contacts.get_first_contact_from_jid(acct, jid)
				if gajim.interface.msg_win_mgr.has_window(jid, acct):
					connected_account = acct
					break
				# jid is in roster
				elif contact:
					connected_account = acct
					break
				# we send the message to jid not in roster, because account is
				# specified, or there is only one account
				elif account:
					connected_account = acct
				elif first_connected_acct is None:
					first_connected_acct = acct

		# if jid is not a conntact, open-chat with first connected account
		if connected_account is None and first_connected_acct:
			connected_account = first_connected_acct

		if connected_account:
			gajim.interface.new_chat_from_jid(connected_account, jid, message)
			# preserve the 'steal focus preservation'
			win = gajim.interface.msg_win_mgr.get_window(jid,
				connected_account).window
			if win.get_property('visible'):
				win.window.focus()
			return DBUS_BOOLEAN(True)
		return DBUS_BOOLEAN(False)

	@dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
	def change_status(self, status, message, account):
		''' change_status(status, message, account). account is optional -
		if not specified status is changed for all accounts. '''
		if status not in ('offline', 'online', 'chat',
			'away', 'xa', 'dnd', 'invisible'):
			return DBUS_BOOLEAN(False)
		if account:
			gobject.idle_add(gajim.interface.roster.send_status, account,
				status, message)
		else:
			# account not specified, so change the status of all accounts
			for acc in gajim.contacts.get_accounts():
				if not gajim.config.get_per('accounts', acc,
				'sync_with_global_status'):
					continue
				gobject.idle_add(gajim.interface.roster.send_status, acc,
					status, message)
		return DBUS_BOOLEAN(False)

	@dbus.service.method(INTERFACE, in_signature='', out_signature='')
	def show_next_pending_event(self):
		'''Show the window(s) with next pending event in tabbed/group chats.'''
		if gajim.events.get_nb_events():
			gajim.interface.systray.handle_first_event()

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='a{sv}')
	def contact_info(self, jid):
		'''get vcard info for a contact. Return cached value of the vcard.
		'''
		if not isinstance(jid, unicode):
			jid = unicode(jid)
		if not jid:
			raise dbus_support.MissingArgument()
		jid = self._get_real_jid(jid)

		cached_vcard = gajim.connections.values()[0].get_cached_vcard(jid)
		if cached_vcard:
			return get_dbus_struct(cached_vcard)

		# return empty dict
		return DBUS_DICT_SV()

	@dbus.service.method(INTERFACE, in_signature='', out_signature='as')
	def list_accounts(self):
		'''list register accounts'''
		result = gajim.contacts.get_accounts()
		result_array = dbus.Array([], signature='s')
		if result and len(result) > 0:
			for account in result:
				result_array.append(DBUS_STRING(account))
		return result_array

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='a{ss}')
	def account_info(self, account):
		'''show info on account: resource, jid, nick, prio, message'''
		result = DBUS_DICT_SS()
		if account in gajim.connections:
			# account is valid
			con = gajim.connections[account]
			index = con.connected
			result['status'] = DBUS_STRING(gajim.SHOW_LIST[index])
			result['name'] = DBUS_STRING(con.name)
			result['jid'] = DBUS_STRING(gajim.get_jid_from_account(con.name))
			result['message'] = DBUS_STRING(con.status)
			result['priority'] = DBUS_STRING(unicode(con.priority))
			result['resource'] = DBUS_STRING(unicode(gajim.config.get_per(
				'accounts', con.name, 'resource')))
		return result

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='aa{sv}')
	def list_contacts(self, account):
		'''list all contacts in the roster. If the first argument is specified,
		then return the contacts for the specified account'''
		result = dbus.Array([], signature='aa{sv}')
		accounts = gajim.contacts.get_accounts()
		if len(accounts) == 0:
			return result
		if account:
			accounts_to_search = [account]
		else:
			accounts_to_search = accounts
		for acct in accounts_to_search:
			if acct in accounts:
				for jid in gajim.contacts.get_jid_list(acct):
					item = self._contacts_as_dbus_structure(
						gajim.contacts.get_contacts(acct, jid))
					if item:
						result.append(item)
		return result

	@dbus.service.method(INTERFACE, in_signature='', out_signature='')
	def toggle_roster_appearance(self):
		''' shows/hides the roster window '''
		win = gajim.interface.roster.window
		if win.get_property('visible'):
			gobject.idle_add(win.hide)
		else:
			win.present()
			# preserve the 'steal focus preservation'
			if self._is_first():
				win.window.focus()
			else:
				win.window.focus(long(time()))

	@dbus.service.method(INTERFACE, in_signature='', out_signature='')
	def toggle_ipython(self):
		''' shows/hides the ipython window '''
		win = gajim.ipython_window
		if win:
			if win.window.is_visible():
				gobject.idle_add(win.hide)
			else:
				win.show_all()
				win.present()
		else:
			gajim.interface.create_ipython_window()

	@dbus.service.method(INTERFACE, in_signature='', out_signature='a{ss}')
	def prefs_list(self):
		prefs_dict = DBUS_DICT_SS()
		def get_prefs(data, name, path, value):
			if value is None:
				return
			key = ''
			if path is not None:
				for node in path:
					key += node + '#'
			key += name
			prefs_dict[DBUS_STRING(key)] = DBUS_STRING(value[1])
		gajim.config.foreach(get_prefs)
		return prefs_dict

	@dbus.service.method(INTERFACE, in_signature='', out_signature='b')
	def prefs_store(self):
		try:
			gajim.interface.save_config()
		except Exception, e:
			return DBUS_BOOLEAN(False)
		return DBUS_BOOLEAN(True)

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='b')
	def prefs_del(self, key):
		if not key:
			return DBUS_BOOLEAN(False)
		key_path = key.split('#', 2)
		if len(key_path) != 3:
			return DBUS_BOOLEAN(False)
		if key_path[2] == '*':
			gajim.config.del_per(key_path[0], key_path[1])
		else:
			gajim.config.del_per(key_path[0], key_path[1], key_path[2])
		return DBUS_BOOLEAN(True)

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='b')
	def prefs_put(self, key):
		if not key:
			return DBUS_BOOLEAN(False)
		key_path = key.split('#', 2)
		if len(key_path) < 3:
			subname, value = key.split('=', 1)
			gajim.config.set(subname, value)
			return DBUS_BOOLEAN(True)
		subname, value = key_path[2].split('=', 1)
		gajim.config.set_per(key_path[0], key_path[1], subname, value)
		return DBUS_BOOLEAN(True)

	@dbus.service.method(INTERFACE, in_signature='ss', out_signature='b')
	def add_contact(self, jid, account):
		if account:
			if account in gajim.connections and \
				gajim.connections[account].connected > 1:
				# if given account is active, use it
				AddNewContactWindow(account = account, jid = jid)
			else:
				# wrong account
				return DBUS_BOOLEAN(False)
		else:
			# if account is not given, show account combobox
			AddNewContactWindow(account = None, jid = jid)
		return DBUS_BOOLEAN(True)

	@dbus.service.method(INTERFACE, in_signature='ss', out_signature='b')
	def remove_contact(self, jid, account):
		jid = self._get_real_jid(jid, account)
		accounts = gajim.contacts.get_accounts()

		# if there is only one account in roster, take it as default
		if account:
			accounts = [account]
		contact_exists = False
		for account in accounts:
			contacts = gajim.contacts.get_contacts(account, jid)
			if contacts:
				gajim.connections[account].unsubscribe(jid)
				for contact in contacts:
					gajim.interface.roster.remove_contact(contact, account)
				gajim.contacts.remove_jid(account, jid)
				contact_exists = True
		return DBUS_BOOLEAN(contact_exists)

	def _is_first(self):
		if self.first_show:
			self.first_show = False
			return True
		return False

	def _get_real_jid(self, jid, account = None):
		'''get the real jid from the given one: removes xmpp: or get jid from nick
		if account is specified, search only in this account
		'''
		if account:
			accounts = [account]
		else:
			accounts = gajim.connections.keys()
		if jid.startswith('xmpp:'):
			return jid[5:] # len('xmpp:') = 5
		nick_in_roster = None # Is jid a nick ?
		for account in accounts:
			# Does jid exists in roster of one account ?
			if gajim.contacts.get_contacts(account, jid):
				return jid
			if not nick_in_roster:
				# look in all contact if one has jid as nick
				for jid_ in gajim.contacts.get_jid_list(account):
					c = gajim.contacts.get_contacts(account, jid_)
					if c[0].name == jid:
						nick_in_roster = jid_
						break
		if nick_in_roster:
			# We have not found jid in roster, but we found is as a nick
			return nick_in_roster
		# We have not found it as jid nor as nick, probably a not in roster jid
		return jid

	def _contacts_as_dbus_structure(self, contacts):
		''' get info from list of Contact objects and create dbus dict '''
		if not contacts:
			return None
		prim_contact = None # primary contact
		for contact in contacts:
			if prim_contact is None or contact.priority > prim_contact.priority:
				prim_contact = contact
		contact_dict = DBUS_DICT_SV()
		contact_dict['name'] = DBUS_STRING(prim_contact.name)
		contact_dict['show'] = DBUS_STRING(prim_contact.show)
		contact_dict['jid'] = DBUS_STRING(prim_contact.jid)
		if prim_contact.keyID:
			keyID = None
			if len(prim_contact.keyID) == 8:
				keyID = prim_contact.keyID
			elif len(prim_contact.keyID) == 16:
				keyID = prim_contact.keyID[8:]
			if keyID:
				contact_dict['openpgp'] = keyID
		contact_dict['resources'] = dbus.Array([], signature='(sis)')
		for contact in contacts:
			resource_props = dbus.Struct((DBUS_STRING(contact.resource),
				dbus.Int32(contact.priority), DBUS_STRING(contact.status)))
			contact_dict['resources'].append(resource_props)
		contact_dict['groups'] = dbus.Array([], signature='(s)')
		for group in prim_contact.groups:
			contact_dict['groups'].append((DBUS_STRING(group),))
		return contact_dict

	@dbus.service.method(INTERFACE, in_signature='', out_signature='s')
	def get_unread_msgs_number(self):
		return DBUS_STRING(str(gajim.events.get_nb_events()))

	@dbus.service.method(INTERFACE, in_signature='s', out_signature='b')
	def start_chat(self, account):
		if not account:
			# error is shown in gajim-remote check_arguments(..)
			return DBUS_BOOLEAN(False)
		NewChatDialog(account)
		return DBUS_BOOLEAN(True)

	@dbus.service.method(INTERFACE, in_signature='ss', out_signature='')
	def send_xml(self, xml, account):
		if account:
			gajim.connections[account].send_stanza(str(xml))
		else:
			for acc in gajim.contacts.get_accounts():
				gajim.connections[acc].send_stanza(str(xml))

	@dbus.service.method(INTERFACE, in_signature='ssss', out_signature='')
	def join_room(self, room_jid, nick, password, account):
		if not account:
			# get the first connected account
			accounts = gajim.connections.keys()
			for acct in accounts:
				if gajim.account_is_connected(acct):
					account = acct
					break
			if not account:
				return
		if not nick:
			nick = ''
			gajim.interface.instances[account]['join_gc'] = \
					JoinGroupchatWindow(account, room_jid, nick)
		else:
			gajim.interface.join_gc_room(account, room_jid, nick, password)

# vim: se ts=3:
