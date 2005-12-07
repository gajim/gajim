#!/bin/sh
''':'
exec python -OOt "$0" ${1+"$@"}
' '''
##	scripts/gajim-remote.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
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

# gajim-remote help will show you the DBUS API of Gajim

import sys
import gtk
import gobject

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application
import traceback

from common import exceptions
from common import i18n

_ = i18n._
i18n.init()

def send_error(error_message):
		''' Writes error message to stderr and exits'''
		sys.stderr.write(error_message + '\n')
		sys.stderr.flush()
		sys.exit(1)

try:
	import dbus
except:
	raise exceptions.DbusNotSupported

_version = getattr(dbus, 'version', (0, 20, 0))
if _version[1] >= 41:
	import dbus.service
	import dbus.glib

OBJ_PATH = '/org/gajim/dbus/RemoteObject'
INTERFACE = 'org.gajim.dbus.RemoteInterface'
SERVICE = 'org.gajim.dbus'
BASENAME = 'gajim-remote'

class GajimRemote:
	
	def __init__(self):
		self.argv_len = len(sys.argv) 
		# define commands dict. Prototype :
		# {
		#	'command': [comment, [list of arguments] ]
		# }
		#
		# each argument is defined as a tuple:
		#    (argument name, help on argument, is mandatory)
		#
		self.commands = {
			'help':[
					_('shows a help on specific command'),
					[
						#User gets help for the command, specified by this parameter
						(_('command'), 
						_('show help on command'), False)
					]
				], 
			'toggle_roster_appearance' : [
					_('Shows or hides the roster window'),
					[]
				], 
			'show_next_unread': [
					_('Popups a window with the next unread message'),
					[]
				],
			'list_contacts': [
					_('Prints a list of all contacts in the roster. Each contact appear on a separate line'),
					[
						(_('account'), _('show only contacts of the given account'), False)
					]
					
				],	
			'list_accounts': [
					_('Prints a list of registered accounts'),
					[]
				], 
			'change_status': [
					_('Changes the status of account or accounts'),
					[
						(_('status'), _('one of: offline, online, chat, away, xa, dnd, invisible '), True), 
						(_('message'), _('status message'), False), 
						(_('account'), _('change status of account "account". '
		'If not specified, try to change status of all accounts that have '
		'"sync with global status" option set'), False)
					]
				],
			'open_chat': [ 
					_('Shows the chat dialog so that you can send messages to a contact'), 
					[
						('jid', _('JID of the contact that you want to chat with'),
							True), 
						(_('account'), _('if specified, contact is taken from the '
						'contact list of this account'), False)
					]
				],
			'send_message':[
					_('Sends new message to a contact in the roster. Both OpenPGP key '
					'and account are optional. If you want to set only \'account\', '
					'without \'OpenPGP key\', just set \'OpenPGP key\' to \'\'.'), 
					[
						('jid', _('JID of the contact that will receive the message'), True),
						(_('message'), _('message contents'), True),
						(_('pgp key'), _('if specified, the message will be encrypted '
							'using this public key'), False),
						(_('account'), _('if specified, the message will be sent '
							'using this account'), False),
					]
				], 
			'contact_info': [
					_('Gets detailed info on a contact'), 
					[
						('jid', _('JID of the contact'), True)
					]
				],
			'send_file': [
					_('Sends file to a contact'),
					[
						(_('file'), _('File path'), True),
						('jid', _('JID of the contact'), True),
						(_('account'), _('if specified, file will be sent using this '
							'account'), False)
					]
				],
			'prefs_list': [
					_('Lists all preferences and their values'),
					[ ]
				],
			'prefs_put': [
					_('Sets value of \'key\' to \'value\'.'),
					[
						(_('key=value'), _('\'key\' is the name of the preference, '
							'\'value\' is the value to set it to'), True)
					]
				],
			'prefs_del': [
					_('Deletes a preference item'),
					[ 
						(_('key'), _('name of the preference to be deleted'), True) 
					]
				],
			'prefs_store': [
					_('Writes the current state of Gajim preferences to the .config '
						'file'),
					[ ]
				],
			'remove_contact': [
					_('Removes contact from roster'),
					[ 
						('jid', _('JID of the contact'), True),
						(_('account'), _('if specified, contact is taken from the '
							'contact list of this account'), False)
						
					]
				],
			'add_contact': [
					_('Adds contact to roster'),
					[ 
						(_('account'), _('Adds new contact to this account.'), True)
					]
				],
			
			'get_status': [
				_('Returns current status (the global one unless account is specified)'),
					[
						(_('account'), _(''), False)
					]
				],
				
			}
		if self.argv_len  < 2 or \
			sys.argv[1] not in self.commands.keys(): # no args or bad args
			send_error(self.compose_help())
		self.command = sys.argv[1]
		if self.command == 'help':
			if self.argv_len == 3:
				print self.help_on_command(sys.argv[2])
			else:
				print self.compose_help()
			sys.exit()
		
		self.init_connection()
		self.check_arguments()
		
		if self.command == 'contact_info':
			if self.argv_len < 3:
				send_error(_('Missing argument "contact_jid"'))
			try:
				id = self.sbus.add_signal_receiver(self.show_vcard_info, 
					'VcardInfo', INTERFACE, SERVICE, OBJ_PATH)
			except Exception, e:
				raise exceptions.ServiceNotAvailable
		
		res = self.call_remote_method()
		self.print_result(res)
		
		if self.command == 'contact_info':
			gobject.timeout_add(10000, self.gtk_quit) # wait 10 sec for response
			gtk.main()
	
	def print_result(self, res):
		''' Print retrieved result to the output '''
		if res is not None:
			if self.command in ('open_chat', 'send_message'):
				if self.command == 'send_message':
					self.argv_len -= 2
				
				if res is False:
					if self.argv_len < 4:
						send_error(_('\'%s\' is not in your roster.\n'
					'Please specify account for sending the message.') % sys.argv[2])
					else:
						send_error(_('You have no active account'))
			elif self.command == 'list_accounts':
				if isinstance(res, list):
					for account in res:
						print account
			elif self.command == 'list_contacts':
				for single_res in res:
					accounts = self.unrepr(single_res)
					for account_dict in accounts:
						print self.print_info(0, account_dict)
			elif self.command == 'prefs_list':
				prefs_dict = self.unrepr(res)
				pref_keys = prefs_dict[0].keys()
				pref_keys.sort()
				for pref_key in pref_keys:
					print pref_key, '=', prefs_dict[0][pref_key]
			elif res:
				print res
	
	def init_connection(self):
		''' create the onnection to the session dbus,
		or exit if it is not possible '''
		try:
			self.sbus = dbus.SessionBus()
		except:
			raise exceptions.SessionBusNotPresent
		
		if _version[1] >= 30:
			obj = self.sbus.get_object(SERVICE, OBJ_PATH)
			interface = dbus.Interface(obj, INTERFACE)
		elif _version[1] < 30:
			self.service = self.sbus.get_service(SERVICE)
			interface = self.service.get_object(OBJ_PATH, INTERFACE)
		else:
			send_error(_('Unknown D-Bus version: %s') % _version[1])
			
		# get the function asked
		self.method = interface.__getattr__(self.command)
		
	def make_arguments_row(self, args):
		''' return arguments list. Mandatory arguments are enclosed with:
		'<', '>', optional arguments - with '[', ']' '''
		str = ''
		for argument in args:
			str += ' '
			if argument[2]:
				str += '<'
			else:
				str += '['
			str += argument[0]
			if argument[2]:
				str += '>'
			else:
				str += ']'
		return str
		
	def help_on_command(self, command):
		''' return help message for a given command '''
		if command in self.commands:
			command_props = self.commands[command]
			arguments_str = self.make_arguments_row(command_props[1])
			str = _('Usage: %s %s %s \n\t') % (BASENAME, command, 
					arguments_str)
			if len(command_props[1]) > 0:
				str += command_props[0] + '\n\n' + _('Arguments:') + '\n'
				for argument in command_props[1]:
					str += ' ' +  argument[0] + ' - ' + argument[1] + '\n'
			return str
		send_error(_('%s not found') % command)
			
	def compose_help(self):
		''' print usage, and list available commands '''
		str = _('Usage: %s command [arguments]\nCommand is one of:\n' ) % BASENAME
		commands = self.commands.keys()
		commands.sort()
		for command in commands:
			str += '  ' + command 
			for argument in self.commands[command][1]:
				str += ' '
				if argument[2]:
					str += '<'
				else:
					str += '['
				str += argument[0]
				if argument[2]:
					str += '>'
				else:
					str += ']'
			str += '\n'
		return str
		
	def print_info(self, level, prop_dict):
		''' return formated string from serialized vcard data '''
		if prop_dict is None or type(prop_dict) \
			not in (dict, list, tuple):
			return ''
		ret_str = ''
		if type(prop_dict) in (list, tuple):
			ret_str = ''
			spacing = ' ' * level * 4
			for val in prop_dict:
				if val is None:
					ret_str +='\t'
				elif type(val) in (unicode, int, str):
					ret_str +='\t' + str(val)
				elif type(val) in (list, tuple):
					res = ''
					for items in val:
						res += self.print_info(level+1, items)
					if res != '':
						ret_str += '\t' + res
				elif type(val) == dict:
					ret_str += self.print_info(level+1, val)
			ret_str = '%s(%s)\n' % (spacing, ret_str[1:])
		elif isinstance(prop_dict, dict):
			for key in prop_dict.keys():
				val = prop_dict[key]
				spacing = ' ' * level * 4
				if type(val) in (unicode, int, str):
					if val is not None:
						val = val.strip()
						ret_str += '%s%-10s: %s\n' % (spacing, key, val)
				elif type(val) in (list, tuple):
					res = ''
					for items in val:
						res += self.print_info(level+1, items)
					if res != '':
						ret_str += '%s%s: \n%s' % (spacing, key, res)
				elif isinstance(val, dict):
					res = self.print_info(level+1, val)
					if res != '':
						ret_str += '%s%s: \n%s' % (spacing, key, res)
		return ret_str
		
	def unrepr(self, serialized_data):
		''' works the same as eval, but only for structural values, 
		not functions! e.g. dicts, lists, strings, tuples '''
		if not serialized_data:
			return (None, '') 
		value = serialized_data.strip()
		first_char = value[0]
		is_unicode  = False
		is_int  = False
		
		if first_char == 'u':
			is_unicode = True
			value = value[1:]
			first_char = value[0]
		elif '0123456789.'.find(first_char) != -1:
			is_int = True
			_str = first_char
			if first_char == '.':
				is_float = True
			else:
				is_float =  False
			for i in xrange(len(value) - 1):
				chr = value[i+1]
				if chr == '.':
					is_float = True
				elif '0123456789'.find(chr) == -1:
					break
				_str += chr
			if is_float:
				return (float(_str), value[len(_str):])
			else:
				return (int(_str), value[len(_str):])
		elif first_char == 'N':
			if value[1:4] == 'one':
				return (None, value[4:])
			else:
				return (None, '')
		if first_char == "'" or first_char == '"': # handle strings and unicode
			if len(value) < 2:
				return ('',value[1:])
			_str = ''
			previous_slash = False
			slashes = 0
			for i in xrange(len(value) - 1):
				chr = value[i+1]
				if previous_slash:
					previous_slash = False
					if chr == '\\':
						_str += '\\'
					elif chr == 'n':
						_str += '\n'
					elif chr == 't':
						_str += '\t'
					elif chr == 'r':
						_str += '\r'
					elif chr == 'b':
						_str += '\b'
					elif chr == '\'':
						_str += '\''
					elif chr == '\"':
						_str += '\"'
					elif chr in ('u', 'x') and is_unicode:
						slashes -= 1
						_str += '\\' + chr
					else:
						_str += chr
				elif chr == first_char:
					break
				elif chr == '\\':
					previous_slash = True
					slashes += 1
				else:
					_str += chr
			substr_len = len(_str) + 2 + slashes
			if is_unicode and _str:
				_str = _str.decode('unicode-escape').encode('utf-8')
			return (_str, value[substr_len :])
		elif first_char == '{': # dict
			_dict = {}
			if value[1] == '}':
				return ({}, value[2:])
			while True:
				if value[1] == '}':
					break
				key, next = self.unrepr(value[1:])
				if type(key) not in (str, unicode):
					send_error('Wrong string: %s' % value)
				next = next.strip()
				if not next or next[0] != ':':
					send_error('Wrong string: %s' % (value))
				val, next = self.unrepr(next[1:])
				_dict[key] = val
				next = next.strip()
				if not next:
					break
				if next[0] == ',':
					value = next
				elif next[0] == '}':
					break
				else:
					break
			return (_dict, next[1:])
		elif first_char in ('[', '('): # return list 
			_tuple = []
			if value[1] == ']':
				return ([], value[2:])
			while True:
				if value[1] == ']':
					break
				val, next = self.unrepr(value[1:])
				next = next.strip()
				if not next:
					send_error('Wrong string: %s' % val)
				_tuple.append(val)
				next = next.strip()
				if not next:
					break
				if next[0] == ',':
					value = next
				elif next[0] in (']', ')'):
					break
			return (_tuple, next[1:])
		
	def show_vcard_info(self, *args, **keyword):
		''' write user vcart in a formated output '''
		props_dict = None
		if _version[1] >= 30:
			props_dict = self.unrepr(args[0])
		else:
			if args and len(args) >= 5:
				props_dict = self.unrepr(args[4].get_args_list()[0])
		if props_dict:
			print self.print_info(0,props_dict[0])
		# remove_signal_receiver is broken in lower versions (< 0.35), 
		# so we leave the leak - nothing can be done
		if _version[1] >= 41:
			self.sbus.remove_signal_receiver(self.show_vcard_info, 'VcardInfo', 
				INTERFACE, SERVICE, OBJ_PATH)
	
		gtk.main_quit()
		
	def check_arguments(self):
		''' Make check if all necessary arguments are given '''
		argv_len = self.argv_len - 2
		args = self.commands[self.command][1]
		if len(args) > argv_len:
			if args[argv_len][2]:
				send_error(_('Argument "%s" is not specified. \n\
Type "%s help %s" for more info') % (args[argv_len][0], BASENAME, self.command))

	def gtk_quit(self):
		if _version[1] >= 41:
			self.sbus.remove_signal_receiver(self.show_vcard_info, 'VcardInfo', 
				INTERFACE, SERVICE, OBJ_PATH)
		gtk.main_quit()
	
	# FIXME - didn't find more clever way for the below method.
	# method(sys.argv[2:]) doesn't work, cos sys.argv[2:] is a tuple
	def call_remote_method(self):
		''' calls self.method with arguments from sys.argv[2:] '''
		try:
			if self.argv_len == 2:
				res = self.method()
			elif self.argv_len == 3:
				res = self.method(sys.argv[2])
			elif self.argv_len == 4:
				res = self.method(sys.argv[2], sys.argv[3])
			elif self.argv_len == 5:
				res = self.method(sys.argv[2], sys.argv[3], sys.argv[4])
			elif argv_len == 6:
				res = self.method(sys.argv[2], sys.argv[3], sys.argv[4],
					sys.argv[5])
			return res
		except Exception, e:
			print str(e)
			raise exceptions.ServiceNotAvailable
		return None

if __name__ == '__main__':
	GajimRemote()
