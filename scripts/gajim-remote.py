#!/usr/bin/env python
##	scripts/gajim-remote.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
##
## This file was initially written by Dimitur Kirov
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

import i18n

_ = i18n._
i18n.init()

def send_error(error_message):
	sys.stderr.write(error_message + '\n')
	sys.stderr.flush()
	sys.exit(1)

try:
	import dbus
except:
	send_error('Dbus is not supported.\n')

_version = getattr(dbus, 'version', (0, 20, 0))
if _version[1] >= 41:
	import dbus.service
	import dbus.glib

OBJ_PATH = '/org/gajim/dbus/RemoteObject'
INTERFACE = 'org.gajim.dbus.RemoteInterface'
SERVICE = 'org.gajim.dbus'
BASENAME = 'gajim-remote'
# define commands dict. Prototype :
# {
#	'command': [comment, [list of arguments] ]
# }
#
# each argument is defined as a tuple:
#    (argument name, help on argument, is mandatory)
#
commands = {
	'help':[
			_('show a help on specific command'),
			[
				(_('on_command'), _('show help on command'), False)
			]
		], 
	'toggle_roster_appearance' : [
			_('Shows or hides the roster window'),
			[]
		], 
	'show_next_unread': [
			_('Popup a window with the next unread message'),
			[]
		],
	'list_contacts': [
			_('Print a list of all contacts in the roster. \
Each contact appear on a separate line'),
			[
				(_('account'), _('show only contacts of the given account'),
					False)
			]
			
		],	
	'list_accounts': [
			_('Print a list of registered accounts'),
			[]
		], 
	'change_status': [
			_('Change '),
			[
				(_('status'), _('one of: offline, online, chat, \
away, xa, dnd, invisible '), True), 
				(_('message'), _('status message'), False), 
				(_('account'), _('change status of the account "accounts". \
If not specified try to change status of all accounts that \
have "sync with global status" option set'), False)
			]
		],
	'open_chat': [ 
			_('Show the chat dialog so that you can send message to a contact'), 
			[
				('jid', _('jid of the contact that you want to chat with'),
					True), 
				(_('account'), _('if specified contact is taken from the contact \
list of this account'), False)
			]
		],
	'send_message':[
			_('Send new message to a contact in the roster'), 
			[
				('jid', _('jid of the contact that will receive the message'), True),
				(_('message'), _('message contents'), True),
				(_('keyID'), _('if specified the message will be encrypted using \
this pulic key'), False),
				(_('account'), _('if specified the message will be sent using this account'), False),
			]
		], 
	'contact_info': [
			_('Get detailed info on a contact'), 
			[
				('jid', _('jid of the contact'), True)
			]
		]
	}

	
def make_arguments_row(args):
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
	
def help_on_command(command):
	''' return help message for a given command '''
	if command in commands:
		str = _('Usage: %s %s %s \n\t') % (BASENAME, command,
			make_arguments_row(commands[command][1]))
		str += commands[command][0] + '\n\nArguments:\n'
		for argument in commands[command][1]:
			str += ' ' +  argument[0] + ' - ' + argument[1] + '\n'
		return str
	send_error(_(' %s not found') % command)
		
def compose_help():
	''' print usage, and list available commands '''
	str = _('Usage: %s command [arguments]\nCommand is one of:\n' ) % BASENAME
	for command in commands.keys():
		str += '  ' + command 
		for argument in commands[command][1]:
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

def show_vcard_info(*args, **keyword):
	# FIXME: more cleaner output
	if _version[1] >= 30:
		print args[0]
	else:
		if args and len(args) >= 5:
			print args[4].get_args_list()

	# remove_signal_receiver is broken in lower versions (< 0.35), 
	# so we leave the leak - nothing can be done
	if _version[1] >= 41:
		sbus.remove_signal_receiver(show_vcard_info, 'VcardInfo', INTERFACE, 
			SERVICE, OBJ_PATH)

	gtk.main_quit()
	
def check_arguments(command):
	''' Make check if all necessary arguments are given '''
	argv_len = len(sys.argv) - 2
	args = commands[command][1]
	if len(args) > argv_len:
		if args[argv_len][2]:
			send_error(_('Argument "%s" is not specified. \n\
Type "%s help %s" for more info') % \
			(args[argv_len][0], BASENAME, command))

def gtk_quit():
	if _version[1] >= 41:
		sbus.remove_signal_receiver(show_vcard_info, 'VcardInfo', INTERFACE, 
			SERVICE, OBJ_PATH)
	gtk.main_quit()

#FIXME - didn't find more clever way for the below 8 lines of code.
# method(sys.argv[2:]) doesn't work, cos sys.argv[2:] is a tuple
def call_remote_method(method):
	argv_len = len(sys.argv)
	try:
		if argv_len == 2:
			res = method()
		elif argv_len == 3:
			res = method(sys.argv[2])
		elif argv_len == 4:
			res = method(sys.argv[2], sys.argv[3])
		elif argv_len == 5:
			res = method(sys.argv[2], sys.argv[3], sys.argv[4])
		return res
	except:
		send_error(_('Service not available'))
	return None


argv_len = len(sys.argv) 

if argv_len  < 2 or sys.argv[1] not in commands.keys(): # no args or bad args
	send_error(compose_help())

command = sys.argv[1]

if command == 'help':
	if argv_len == 3:
		print help_on_command(sys.argv[2])
	else:
		print compose_help()
	sys.exit()

try:
	sbus = dbus.SessionBus()
except:
	send_error(_('Session bus is not available.\n'))


if _version[1] >= 30 and _version[1] <= 42:
	object = sbus.get_object(SERVICE, OBJ_PATH)
	interface = dbus.Interface(object, INTERFACE)
elif _version[1] < 30:
	service = sbus.get_service(SERVICE)
	interface = service.get_object(OBJ_PATH, INTERFACE)
else:
	send_error(_('Unknow dbus version: %s') % _version)

method = interface.__getattr__(sys.argv[1]) # get the function asked

check_arguments(command)
if command == 'contact_info':
	if argv_len < 3:
		send_error(_('Missing argument "contact_jid"'))
	try:
		id = sbus.add_signal_receiver(show_vcard_info, 'VcardInfo', 
			INTERFACE, SERVICE, OBJ_PATH)
	except:
		send_error(_('Service not available'))

res = call_remote_method(method)


if res:
	print res

if command == 'contact_info':
	gobject.timeout_add(5000, gtk_quit) # wait 5 sec maximum
	gtk.main()
