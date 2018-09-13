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

import locale
import gettext
import os
import unicodedata

DOMAIN = 'gajim'
LANG = 'en'
direction_mark = '\u200E'
_translations = None


def get_locale_dir():
    if os.name == 'nt':
        return None
    # try to find domain in localedir
    path = gettext.find(DOMAIN)
    if path:
        # extract localedir from localedir/language/LC_MESSAGES/domain.mo
        path = os.path.split(path)[1]
        path = os.path.split(path)[1]
        localedir = os.path.split(path)[1]
    elif os.path.exists('/app/share/run-as-flatpak'):
        # Check if we run as flatpak
        return '/app/share/locale'
    else:
        # fallback to user locale
        base = os.getenv('XDG_DATA_HOME')
        if base is None or base[0] != '/':
            base = os.path.expanduser('~/.local/share')
        localedir = os.path.join(base, "locale")
    return localedir


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
        if bidi in ('AL', 'R'):
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
        text = text.split(':', 1)[1]
    return text


def ngettext(s_sing, s_plural, n, replace_sing=None, replace_plural=None):
    """
    Use as:
        i18n.ngettext(
            'leave room %s', 'leave rooms %s', len(rooms), 'a', 'a, b, c')

    In other words this is a hack to ngettext() to support %s %d etc..
    """
    text = _translations.ngettext(s_sing, s_plural, n)
    if n == 1 and replace_sing is not None:
        text = text % replace_sing
    elif n > 1 and replace_plural is not None:
        text = text % replace_plural
    return text


try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error as error:
    print(error)

try:
    # en_US, fr_FR, el_GR etc..
    default = locale.getdefaultlocale()[0]
    if default is not None:
        LANG = default[:2]
except (ValueError, locale.Error):
    pass

if os.name == 'nt':
    os.environ['LANG'] = LANG

_localedir = get_locale_dir()
if hasattr(locale, 'bindtextdomain'):
    locale.bindtextdomain(DOMAIN, _localedir)  # type: ignore
gettext.textdomain(DOMAIN)

gettext.install(DOMAIN, _localedir)

try:
    _ = gettext.translation(DOMAIN, _localedir).gettext
except OSError:
    _ = gettext.gettext

if gettext._translations:    # type: ignore
    _translations = list(gettext._translations.values())[0]  # type: ignore
else:
    _translations = gettext.NullTranslations()
