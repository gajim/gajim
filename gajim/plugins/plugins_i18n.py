# Copyright (C) 2010-2011 Denis Fomin <fominde AT gmail.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import gettext
import locale
from pathlib import Path

from gajim.common import configpaths

DOMAIN = 'gajim_plugins'
try:
    plugin_user_dir = configpaths.get('PLUGINS_USER')
except KeyError:
    # This allows to import the module for tests
    print('No plugin translation path available')
    plugin_user_dir = Path.cwd()


plugins_locale_dir = plugin_user_dir / 'locale'

try:
    t = gettext.translation(DOMAIN, plugins_locale_dir)
    _ = t.gettext
except OSError:
    _ = gettext.gettext

if hasattr(locale, 'bindtextdomain'):
    locale.bindtextdomain(DOMAIN, plugins_locale_dir)
