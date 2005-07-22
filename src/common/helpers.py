##	common/helpers.py
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

from common import i18n
_ = i18n._
import sre

def get_uf_show(show):
	'''returns a userfriendly string for dnd/xa/chat
	and makes the rest translatable'''
	if show == 'dnd':
		uf_show = _('Busy')
	elif show == 'xa':
		uf_show = _('Not Available')
	elif show == 'chat':
		uf_show = _('Free for Chat')
	elif show == 'online':
		uf_show = _('Available')
	elif show == 'connecting':
		uf_show = _('Connecting')
	elif show == 'away':
		uf_show = _('Away')
	elif show == 'offline':
		uf_show = _('Offline')
	elif show == 'invisible':
		uf_show = _('Invisible')
	elif show == 'not in the roster':
		uf_show = _('Not in the roster')
	else:
		uf_show = _('Has errors')
	return unicode(uf_show)

def get_sorted_keys(adict):
	keys = adict.keys()
	keys.sort()
	return keys

def get_fjid_from_nick(room_jid, nick):
	# fake jid is the jid for a contact in a room
	# gaim@conference.jabber.org/nick
	fjid = room_jid + '/' + nick
	return fjid

def get_nick_from_jid(jid):
	pos = jid.find('@')
	return jid[:pos]

def get_nick_from_fjid(jid):
	# fake jid is the jid for a contact in a room
	# gaim@conference.jabber.org/nick/nick-continued
	return jid.split('/', 1)[1]

def get_resource_from_jid(jid):
	return jid.split('/', 1)[1] # abc@doremi.org/res/res-continued

def to_one_line(msg):
	msg = msg.replace('\\', '\\\\')
	msg = msg.replace('\n', '\\n')
	# s1 = 'test\ntest\\ntest'
	# s11 = s1.replace('\\', '\\\\')
	# s12 = s11.replace('\n', '\\n')
	# s12
	# 'test\\ntest\\\\ntest'
	return msg

def from_one_line(msg):
	# (?<!\\) is a lookbehind assertion which asks anything but '\'
	# to match the regexp that follows it

	# So here match '\\n' but not if you have a '\' before that
	re = sre.compile(r'(?<!\\)\\n')
	msg = re.sub('\n', msg)
	msg = msg.replace('\\\\', '\\')
	# s12 = 'test\\ntest\\\\ntest'
	# s13 = re.sub('\n', s12)
	# s14 s13.replace('\\\\', '\\')
	# s14
	# 'test\ntest\\ntest'
	return msg
