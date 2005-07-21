##	gtkgui_helpers.py
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

import cgi

from common import gajim

def get_contact_instances_from_jid(account, jid):
	''' we may have two or more resources on that jid '''
	contact_instances = gajim.contacts[account][jid]
	return contact_instances

def get_first_contact_instance_from_jid(account, jid):
	contact_instances = get_contact_instances_from_jid(account, jid)
	return contact_instances[0]

def get_contact_name_from_jid(account, jid):
	contact_instances = get_contact_instances_from_jid(account, jid)
	return contact_instances[0].name

def escape_for_pango_markup(string):
	# escapes chars for pango markup not to break
	return cgi.escape(string)
