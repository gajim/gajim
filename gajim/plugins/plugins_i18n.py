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

import os
import gettext

from gajim.common import configpaths

DOMAIN = 'gajim_plugins'
plugin_user_dir = configpaths.get('PLUGINS_USER')
plugins_locale_dir = os.path.join(plugin_user_dir, 'locale')

try:
    t = gettext.translation(DOMAIN, plugins_locale_dir)
    _ = t.gettext
except OSError:
    _ = gettext.gettext
