# -*- coding:utf-8 -*-
## src/common/i18n.py
##
## Copyright (C) 2003-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2004-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import locale
import gettext
import os

APP = 'gajim'
if os.path.isdir('../po'):
	DIR = '../po'
else:
	DIR = '../../locale'

# set '' so each part of the locale that should be modified is set
# according to the environment variables
locale.setlocale(locale.LC_ALL, '')

## For windows: set, if needed, a value in LANG environmental variable ##
if os.name == 'nt':
	lang = os.getenv('LANG')
	if lang is None:
		default_lang = locale.getdefaultlocale()[0] # en_US, fr_FR, el_GR etc..
		if default_lang:
			lang = default_lang

	if lang:
		os.environ['LANG'] = lang

gettext.install(APP, DIR, unicode = True)
if gettext._translations:
	_translation = gettext._translations.values()[0]
else:
	_translation = gettext.NullTranslations()

def Q_(s):
	# Qualified translatable strings
	# Some strings are too ambiguous to be easily translated.
	# so we must use as:
	# s = Q_('?vcard:Unknown')
	# widget.set_text(s)
	# Q_() removes the ?vcard:
	# but gettext while parsing the file detects ?vcard:Unknown as a whole string.
	# translator can either put the ?vcard: part or no (easier for him or her to no)
	# nothing fails
	s = _(s)
	if s[0] == '?':
		s = s[s.find(':')+1:] # remove ?abc: part
	return s

def ngettext(s_sing, s_plural, n, replace_sing = None, replace_plural = None):
	'''use as:
	i18n.ngettext('leave room %s', 'leave rooms %s', len(rooms), 'a', 'a, b, c')

	in other words this is a hack to ngettext() to support %s %d etc..
	'''
	text = _translation.ungettext(s_sing, s_plural, n)
	if n == 1 and replace_sing is not None:
		text = text % replace_sing
	elif n > 1 and replace_plural is not None:
		text = text % replace_plural
	return text

# vim: se ts=3:
