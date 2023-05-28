# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2004 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2009 Benjamin Richter <br AT waldteufel-online.net>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import cast

import gettext
import importlib.resources
import locale
import os
import sys
import unicodedata
from pathlib import Path

DOMAIN = 'gajim'


def get_win32_default_lang() -> str:
    import ctypes
    windll = ctypes.windll.kernel32
    return locale.windows_locale[windll.GetUserDefaultUILanguage()]


def get_darwin_default_lang() -> str:
    from AppKit import NSLocale

    # FIXME: This returns a two letter language code (en, de, fr)
    # We need a way to get en_US, de_DE etc.
    return NSLocale.currentLocale().languageCode()


def get_default_lang() -> str:
    if sys.platform == 'win32':
        return get_win32_default_lang()

    if sys.platform == 'darwin':
        return get_darwin_default_lang()

    return locale.getdefaultlocale()[0] or 'en'


def get_rfc5646_lang(lang: str | None = None) -> str:
    if lang is None:
        lang = LANG
    return lang.replace('_', '-')


def get_short_lang_code(lang: str | None = None) -> str:
    if lang is None:
        lang = LANG
    return lang[:2]


def is_rtl_text(text: str) -> bool:
    '''
    Determine paragraph writing direction according to
    http://www.unicode.org/reports/tr9/#The_Paragraph_Level
    '''
    for char in text:
        bidi = unicodedata.bidirectional(char)
        if bidi == 'L':
            return False
        if bidi in ('AL', 'R'):
            return True

    return False


def p_(context: str, message: str) -> str:
    return _translation.pgettext(context, message)


def ngettext(s_sing: str,
             s_plural: str,
             n: int,
             replace_sing: str | None = None,
             replace_plural: str | None = None) -> str:
    '''
    Use as:
        i18n.ngettext(
            'leave room %s', 'leave rooms %s', len(rooms), 'a', 'a, b, c')

    In other words this is a hack to ngettext() to support %s %d etc..
    '''
    text = _translation.ngettext(s_sing, s_plural, n)
    if n == 1 and replace_sing is not None:
        return text % replace_sing

    if n > 1 and replace_plural is not None:
        return text % replace_plural
    return text


try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error as error:
    print(error, file=sys.stderr)

LANG = get_default_lang()
if sys.platform == 'win32':
    # Set the env var on Windows because gettext.find() uses it to
    # find the translation
    # Use LANGUAGE instead of LANG, LANG sets LC_ALL and thus
    # doesn't retain other region settings like LC_TIME
    os.environ['LANGUAGE'] = LANG


package_dir = cast(Path, importlib.resources.files('gajim'))
locale_dir = package_dir / 'data' / 'locale'

try:
    _translation = gettext.translation(DOMAIN, locale_dir)
    _ = _translation.gettext
    if hasattr(locale, 'bindtextdomain'):
        locale.bindtextdomain(DOMAIN, locale_dir)
except OSError:
    _translation = gettext.NullTranslations()
    _ = _translation.gettext
    print('No translations found for', LANG, file=sys.stderr)
