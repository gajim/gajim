# -*- coding:utf-8 -*-
## src/common/i18n.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2009 Benjamin Richter <br AT waldteufel-online.net>
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
from common import defs
import unicodedata

# May be changed after GTK is imported
direction_mark = '\u200E'

def paragraph_direction_mark(text):
    """
    Determine paragraph writing direction according to
    http://www.unicode.org/reports/tr9/#The_Paragraph_Level

    Returns either Unicode LTR mark or RTL mark.
    """
    for char in text:
        bidi = unicodedata.bidirectional(char)
        if bidi == 'L':
            return '\u200E'
        elif bidi == 'AL' or bidi == 'R':
            return '\u200F'

    return '\u200E'

APP = 'gajim'
DIR = defs.localedir

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

gettext.install(APP, DIR)
if gettext._translations:
    _translation = list(gettext._translations.values())[0]
else:
    _translation = gettext.NullTranslations()

def Q_(text):
    """
    Translate the given text, optionally qualified with a special
    construction, which will help translators to disambiguate between
    same terms, but in different contexts.

    When translated text is returned - this rudimentary construction
    will be stripped off, if it's present.

    Here is the construction to use:
        Q_("?vcard:Unknown")

    Everything between ? and : - is the qualifier to convey the context
    to the translators. Everything after : - is the text itself.
    """
    text = _(text)
    if text.startswith('?'):
        qualifier, text = text.split(':', 1)
    return text

def ngettext(s_sing, s_plural, n, replace_sing = None, replace_plural = None):
    """
    Use as:
            i18n.ngettext('leave room %s', 'leave rooms %s', len(rooms), 'a', 'a, b, c')

    In other words this is a hack to ngettext() to support %s %d etc..
    """
    text = _translation.ngettext(s_sing, s_plural, n)
    if n == 1 and replace_sing is not None:
        text = text % replace_sing
    elif n > 1 and replace_plural is not None:
        text = text % replace_plural
    return text
