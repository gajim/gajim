#!/usr/bin/env python
##	scripts/gajim-remote.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
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

def send_error(error_message):
	sys.stderr.write(error_message + '\n')
	sys.stderr.flush()
	sys.exit(1)

try:
	import dbus
except:
	send_error('Dbus is not supported.\n')

_version = getattr(dbus, 'version', (0, 20, 0))

OBJ_PATH = '/org/gajim/dbus/RemoteObject'
INTERFACE = 'org.gajim.dbus.RemoteInterface'
SERVICE = 'org.gajim.dbus'
commands = ['help', 'show_roster', 'show_next_unread', 'list_contacts',
	'list_accounts', 'change_status', 'new_message', 'send_message', 
	'contact_info']
	
if _version[1] >= 41:
	import dbus.service
	import dbus.glib
	
def compose_help():
	str = 'Usage: '+ sys.argv[0] + ' command [arguments]\n'
	str += 'Command must be one of:\n'
	for command in commands:
		str += '\t' + command +'\n'
	return str

def show_vcard_info(*args, **keyword):
	if _version[1] >= 30:
		print args[0]
	else:
		if args and len(args) >= 5:
			print args[4].get_args_list()

	# remove_signal_receiver is broken in lower versions, 
	# so we leave the leak - nothing can be done
	if _version[1] >= 41:
		sbus.remove_signal_receiver(show_vcard_info, 'VcardInfo', INTERFACE, 
			SERVICE, OBJ_PATH)

	gtk.main_quit()
	
def gtk_quit():
	if _version[1] >= 41:
		sbus.remove_signal_receiver(show_vcard_info, 'VcardInfo', INTERFACE, 
			SERVICE, OBJ_PATH)
	gtk.main_quit()


argv_len = len(sys.argv) 

if argv_len  < 2:
	send_error('Usage: ' + sys.argv[0] + ' command [arguments]')

if sys.argv[1] not in commands:
	send_error(compose_help())
	
command = sys.argv[1]

if command == 'help':
	print compose_help()
	sys.exit()

try:
	sbus = dbus.SessionBus()
except:
	send_error('Session bus is not available.\n')


if _version[1] >= 30 and _version[1] <= 42:
	object = sbus.get_object(SERVICE, OBJ_PATH)
	interface = dbus.Interface(object, INTERFACE)
elif _version[1] < 30:
	service = sbus.get_service(SERVICE)
	interface = service.get_object(OBJ_PATH, INTERFACE)
else:
	send_error('Unknow dbus version: '+ _version)

method = interface.__getattr__(sys.argv[1]) # get the function asked

if command == 'contact_info':
	if argv_len < 3:
		send_error("Missing argument \'contact_jid'")
	try:
		id = sbus.add_signal_receiver(show_vcard_info, 'VcardInfo', 
			INTERFACE, SERVICE, OBJ_PATH)
	except:
		send_error('Service not available')

#FIXME: gajim-remote.py change_status help to inform what it does with optional arg (account). the same for rest of methods that accept args

#FIXME - didn't find more clever way for the below 8 lines of code.
# method(sys.argv[2:]) doesn't work, cos sys.argv[2:] is a tuple
try:
	if argv_len == 2:
		res = method()
	elif argv_len == 3:
		res = method(sys.argv[2])
	elif argv_len == 4:
		res = method(sys.argv[2], sys.argv[3])
	elif argv_len == 5:
		res = method(sys.argv[2], sys.argv[3], sys.argv[4])
	if res:
		print res
except:
	send_error('Service not available')

if command == 'contact_info':
	gobject.timeout_add(5000, gtk_quit) # wait 5 sec maximum
	gtk.main()
