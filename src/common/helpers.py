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
	and makes all strings translatable'''
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
	elif show == 'requested':
		uf_show = _('Unknown')
	else:
		uf_show = _('Has errors')
	return unicode(uf_show)
	
def get_uf_sub(sub):
	if sub == 'none':
		uf_sub = _('None')
	elif sub == 'to':
		uf_sub = _('To')
	elif sub == 'from':
		uf_sub = _('From')
	elif sub == 'both':
		uf_sub = _('Both')
	else:
		uf_sub = sub
	
	return uf_sub

def get_uf_ask(ask):
	if ask is None:
		uf_ask = _('None')
	elif ask == 'subscribe':
		uf_ask = _('Subscribe')
	else:
		uf_ask = ask
	
	return uf_ask

def get_sorted_keys(adict):
	keys = adict.keys()
	keys.sort()
	return keys

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

def get_uf_chatstate(chatstate):
	'''removes chatstate jargon and returns user friendly messages'''
	if chatstate == 'active':
		return _('is paying attention to the conversation')
	elif chatstate == 'inactive':
		return _('is doing something else')
	elif chatstate == 'composing':
		return _('is composing a message...')
	elif chatstate == 'paused':
		return _('paused composing a message...')
	elif chatstate == 'gone':
		return _('has closed the chat window or tab')
