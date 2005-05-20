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

def get_uf_status(self, status):
	'''returns a userfriendly string for dnd/xa/chat
	and capitalize()s the rest'''
	if status == 'dnd':
		uf_status = 'Busy'
	elif status == 'xa':
		uf_status = 'Not Available'
	elif status == 'chat':
		uf_status = 'Free for Chat'
	else:
		uf_status = status.capitalize()
	return uf_status
