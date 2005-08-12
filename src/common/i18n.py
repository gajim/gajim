##	common/i18n.py
## -*- coding: utf-8 -*-
## Gajim Team:
##  - Yann Le Boulanger <asterix@lagaule.org>
##  - Vincent Hanquez <tab@snarc.org>
##  - Nikos Kouremenos <kourem@gmail.com>
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

APP = 'gajim'
DIR = '../po'

import locale
import gettext

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
	return _translation.gettext(s)

def Q_(s):
	# Qualified translatable strings
	# Some strings are too ambiguous to be easily translated.
	# so we must use as:
	# s = Q_('?vcard:Unknown')
	# widget.set_text(s)
	# Q_() removes the ?vcard: 
	# but gettext while parsing the file detects ?vcard:Unknown as a whole string.
	# translator can either put the ?vcard: part or no (easier for him to no)
	# nothing fails
	if s[0] == '?':
		s = s[s.index(':')+1:] # remove ?abc: part
	return s
