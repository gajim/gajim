# -*- coding:utf-8 -*-
## src/common/i18n.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2009 Benjamin Richter <br AT waldteufel-online.net>
## Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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
import unicodedata

DOMAIN = 'gajim'
LANG = 'en'
direction_mark = '\u200E'
_translations = None


def initialize():
    global _translations

    locale.setlocale(locale.LC_ALL, '')
    # initialize_win_translation() broken
    initialize_lang()
    set_i18n_env()

    localedir = get_locale_dir()
    if hasattr(locale, 'bindtextdomain'):
        locale.bindtextdomain(DOMAIN, localedir)

    gettext.install(DOMAIN, localedir)
    if gettext._translations:
        _translations = list(gettext._translations.values())[0]
    else:
        _translations = gettext.NullTranslations()


def set_i18n_env():
    if os.name == 'nt':
        lang = os.getenv('LANG')
        if lang is None:
            default_lang = locale.getdefaultlocale()[0]
            if default_lang:
                lang = default_lang

        if lang:
            os.environ['LANG'] = lang


def initialize_lang():
    global LANG
    try:
        # en_US, fr_FR, el_GR etc..
        default = locale.getdefaultlocale()[0]
        if default is None:
            # LC_ALL=C
            return
        LANG = LANG[:2]
    except (ValueError, locale.Error):
        pass


def get_locale_dir():
    if os.name == 'nt':
        return "../po"

    # try to find domain in localedir
    path = gettext.find(DOMAIN)
    if path:
        # extract localedir from localedir/language/LC_MESSAGES/domain.mo
        path, tail = os.path.split(path)
        path, tail = os.path.split(path)
        localedir, tail = os.path.split(path)
    else:
        # fallback to user locale
        base = os.getenv('XDG_DATA_HOME')
        if base is None or base[0] != '/':
            base = os.path.expanduser('~/.local/share')
        localedir = os.path.join(base, "locale")
    return localedir


def initialize_win_translation():
    # broken for now
    return

    if os.name != 'nt':
        return

    # needed for docutils
    # sys.path.append('.')
    APP = 'gajim'
    DIR = '../po'
    lang = locale.getdefaultlocale()[0]
    os.environ['LANG'] = lang
    gettext.bindtextdomain(APP, DIR)
    gettext.textdomain(APP)
    gettext.install(APP, DIR)

    # This is for Windows translation which is currently not
    # working on GTK 3.18.9
    #    locale.setlocale(locale.LC_ALL, '')
    #    import ctypes
    #    import ctypes.util
    #    libintl_path = ctypes.util.find_library('intl')
    #    if libintl_path == None:
    #        local_intl = os.path.join('gtk', 'bin', 'intl.dll')
    #        if os.path.exists(local_intl):
    #            libintl_path = local_intl
    #    if libintl_path == None:
    #        raise ImportError('intl.dll library not found')
    #    libintl = ctypes.cdll.LoadLibrary(libintl_path)
    #    libintl.bindtextdomain(APP, DIR)
    #    libintl.bind_textdomain_codeset(APP, 'UTF-8')
    #    plugins_locale_dir = os.path.join(common.configpaths[
    #       'PLUGINS_USER'], 'locale').encode(locale.getpreferredencoding())
    #    libintl.bindtextdomain('gajim_plugins', plugins_locale_dir)
    #    libintl.bind_textdomain_codeset('gajim_plugins', 'UTF-8')


def initialize_direction_mark():
    from gi.repository import Gtk

    global direction_mark

    if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
        direction_mark = '\u200F'


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


def ngettext(s_sing, s_plural, n, replace_sing=None, replace_plural=None):
    """
    Use as:
        i18n.ngettext('leave room %s', 'leave rooms %s', len(rooms), 'a', 'a, b, c')

    In other words this is a hack to ngettext() to support %s %d etc..
    """
    text = _translations.ngettext(s_sing, s_plural, n)
    if n == 1 and replace_sing is not None:
        text = text % replace_sing
    elif n > 1 and replace_plural is not None:
        text = text % replace_plural
    return text


initialize()
