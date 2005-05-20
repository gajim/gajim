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

def get_uf_show(show):
	'''returns a userfriendly string for dnd/xa/chat
	and capitalize()s the rest'''
	if show == 'dnd':
		uf_show = 'Busy'
	elif show == 'xa':
		uf_show = 'Not Available'
	elif show == 'chat':
		uf_show = 'Free for Chat'
	else:
		uf_show = show.capitalize()
	return uf_show
