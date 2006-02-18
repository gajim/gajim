#!/bin/sh
''':'
exec python -OOt "$0" ${1+"$@"}
' '''
##	scripts/gajim-remote.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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
import locale
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application
import traceback
import gobject

from common import exceptions
from common import i18n

_ = i18n._
i18n.init()

PREFERRED_ENCODING = locale.getpreferredencoding()

def send_error(error_message):
	'''Writes error message to stderr and exits'''
	print >> sys.stderr, error_message.encode(PREFERRED_ENCODING)
	sys.exit()

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
			'account_info': [
					_('Gets detailed info on a account'), 
					[
						('account', _('Name of the account'), True)
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
			
			'get_status_message': [
				_('Returns current status message(the global one unless account is specified)'),
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
				print self.help_on_command(sys.argv[2]).encode(PREFERRED_ENCODING)
			else:
				print self.compose_help().encode(PREFERRED_ENCODING)
			sys.exit()
		
		self.init_connection()
		self.check_arguments()
		
		if self.command == 'contact_info':
			if self.argv_len < 3:
				send_error(_('Missing argument "contact_jid"'))
		
		res = self.call_remote_method()
		self.print_result(res)
		
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
			elif self.command == 'account_info':
				if res:
					print self.print_info(0, res, True)
			elif self.command == 'list_contacts':
				for account_dict in res:
					print self.print_info(0, account_dict, True)
			elif self.command == 'prefs_list':
				pref_keys = res.keys()
				pref_keys.sort()
				for pref_key in pref_keys:
					print pref_key, '=', res[pref_key]
			elif self.command == 'contact_info':
				print self.print_info(0, res, True)
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
			str = _('Usage: %s %s %s \n\t %s') % (BASENAME, command, 
					arguments_str, command_props[0])
			if len(command_props[1]) > 0:
				str += '\n\n' + _('Arguments:') + '\n'
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
		
	def print_info(self, level, prop_dict, encode_return = False):
		''' return formated string from data structure '''
		if prop_dict is None or not isinstance(prop_dict, (dict, list, tuple)):
			return ''
		ret_str = ''
		if isinstance(prop_dict, (list, tuple)):
			ret_str = ''
			spacing = ' ' * level * 4
			for val in prop_dict:
				if val is None:
					ret_str +='\t'
				elif isinstance(val, int):
					ret_str +='\t' + str(val)
				elif isinstance(val, (str, unicode)):
					ret_str +='\t' + val
				elif isinstance(val, (list, tuple)):
					res = ''
					for items in val:
						res += self.print_info(level+1, items)
					if res != '':
						ret_str += '\t' + res
				elif isinstance(val, dict):
					ret_str += self.print_info(level+1, val)
			ret_str = '%s(%s)\n' % (spacing, ret_str[1:])
		elif isinstance(prop_dict, dict):
			for key in prop_dict.keys():
				val = prop_dict[key]
				spacing = ' ' * level * 4
				if isinstance(val, (unicode, int, str)):
					if val is not None:
						val = val.strip()
						ret_str += '%s%-10s: %s\n' % (spacing, key, val)
				elif isinstance(val, (list, tuple)):
					res = ''
					for items in val:
						res += self.print_info(level+1, items)
					if res != '':
						ret_str += '%s%s: \n%s' % (spacing, key, res)
				elif isinstance(val, dict):
					res = self.print_info(level+1, val)
					if res != '':
						ret_str += '%s%s: \n%s' % (spacing, key, res)
		if (encode_return):
			try:
				ret_str = ret_str.encode(PREFERRED_ENCODING)
			except:
				pass
		return ret_str
	
	def check_arguments(self):
		''' Make check if all necessary arguments are given '''
		argv_len = self.argv_len - 2
		args = self.commands[self.command][1]
		if len(args) > argv_len:
			if args[argv_len][2]:
				send_error(_('Argument "%s" is not specified. \n'
					'Type "%s help %s" for more info') % 
					(args[argv_len][0], BASENAME, self.command))
	
	def call_remote_method(self):
		''' calls self.method with arguments from sys.argv[2:] '''
		args = sys.argv[2:]
		if _version[1] >= 60:
			# make console arguments unicode
			args = [i.decode(PREFERRED_ENCODING) for i in sys.argv[2:]]
		if _version[1] >= 41:
			args = [dbus.String(i) for i in args]
		else:
			try:
				args = [i.encode('utf-8') for i in args]
			except:
				pass
		try:
			res = self.method(*args)
			return res
		except Exception:
			raise exceptions.ServiceNotAvailable
		return None

if __name__ == '__main__':
	GajimRemote()
