##	common/i18n.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@lagaule.org>
## 	- Vincent Hanquez <tab@snarc.org>
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

APP='gajim'
DIR='Messages'

import locale, gettext

locale.setlocale(locale.LC_ALL, '')
_translation = None

def init():
	global _translation
	try:
		_translation = gettext.translation(APP, DIR)
	except IOError:
		_translation = gettext.NullTranslations()

def _(s):
	if s == '':
		return s
	assert s
	return _translation.gettext(s)
