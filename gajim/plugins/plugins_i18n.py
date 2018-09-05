# Copyright (C) 2010-2011 Denis Fomin <fominde AT gmail.com>
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
from os import path as os_path
import os
from gajim.common import app
from gajim.common import configpaths

APP = 'gajim_plugins'
plugins_locale_dir = os_path.join(configpaths.get('PLUGINS_USER'), 'locale')

if os.name != 'nt':
    locale.setlocale(locale.LC_ALL, '')
    gettext.bindtextdomain(APP, plugins_locale_dir)
    gettext.textdomain(APP)

try:
    t = gettext.translation(APP, plugins_locale_dir)
    _ = t.gettext
except IOError:
    from gajim.common import i18n
    _ = gettext.gettext
