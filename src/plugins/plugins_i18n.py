# -*- coding: utf-8 -*-
#
## src/plugins/plugin_installer/plugins_i18n.py
##
## Copyright (C) 2010-2011 Denis Fomin <fominde AT gmail.com>
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
from os import path as os_path
import os
from common import gajim

APP = 'gajim_plugins'
plugins_locale_dir = os_path.join(gajim.PLUGINS_DIRS[1], 'locale')

if os.name != 'nt':
    locale.setlocale(locale.LC_ALL, '')
    locale.bindtextdomain(APP, plugins_locale_dir)
    gettext.bindtextdomain(APP, plugins_locale_dir)
    gettext.textdomain(APP)

try:
    t = gettext.translation(APP, plugins_locale_dir)
    _ = t.gettext
except IOError:
    from common import i18n
    _ = gettext.gettext
