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
from pathlib import Path

from gajim.common import configpaths

DOMAIN = 'gajim_plugins'
try:
    plugin_user_dir = configpaths.get('PLUGINS_USER')
except KeyError:
    # This allows to import the module for tests
    print('No plugin translation path available')
    plugin_user_dir = Path.cwd()


# python 3.7 gettext module does not support Path objects
plugins_locale_dir = str(plugin_user_dir / 'locale')

try:
    t = gettext.translation(DOMAIN, plugins_locale_dir)
    _ = t.gettext
except OSError:
    _ = gettext.gettext

if hasattr(locale, 'bindtextdomain'):
    locale.bindtextdomain(DOMAIN, plugins_locale_dir)  # type: ignore
