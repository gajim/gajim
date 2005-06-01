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
