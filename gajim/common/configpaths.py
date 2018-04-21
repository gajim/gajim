# -*- coding:utf-8 -*-
## src/common/configpaths.py
##
## Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
##                    Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os
import sys
import tempfile
from enum import Enum, unique


@unique
class Type(Enum):
    CONFIG = 0
    CACHE = 1
    DATA = 2


def windowsify(s):
    if os.name == 'nt':
        return s.capitalize()
    return s


def get(key):
    return _paths[key]


def set_separation(active: bool):
    _paths.profile_separation = active


def set_profile(profile: str):
    _paths.profile = profile


def set_config_root(config_root: str):
    _paths.custom_config_root = config_root


def init():
    _paths.init()


class ConfigPaths:
    def __init__(self):
        self.paths = {}
        self.profile = ''
        self.profile_separation = False
        self.custom_config_root = None

        if os.name == 'nt':
            try:
                # Documents and Settings\[User Name]\Application Data\Gajim
                self.config_root = self.cache_root = self.data_root = \
                        os.path.join(os.environ['appdata'], 'Gajim')
            except KeyError:
                # win9x, in cwd
                self.config_root = self.cache_root = self.data_root = '.'
        else:
            expand = os.path.expanduser
            base = os.getenv('XDG_CONFIG_HOME')
            if base is None or base[0] != '/':
                base = expand('~/.config')
            self.config_root = os.path.join(base, 'gajim')
            base = os.getenv('XDG_CACHE_HOME')
            if base is None or base[0] != '/':
                base = expand('~/.cache')
            self.cache_root = os.path.join(base, 'gajim')
            base = os.getenv('XDG_DATA_HOME')
            if base is None or base[0] != '/':
                base = expand('~/.local/share')
            self.data_root = os.path.join(base, 'gajim')

        import pkg_resources
        basedir = pkg_resources.resource_filename("gajim", ".")
        self.add('DATA', None, os.path.join(basedir, 'data'))
        self.add('GUI', None, os.path.join(basedir, 'data', 'gui'))
        self.add('ICONS', None, os.path.join(basedir, 'data', 'icons'))
        self.add('HOME', None, os.path.expanduser('~'))
        self.add('PLUGINS_BASE', None, os.path.join(basedir, 'data', 'plugins'))

    def add(self, name, type_, path):
        self.paths[name] = (type_, path)

    def __getitem__(self, key):
        type_, path = self.paths[key]
        if type_ == Type.CONFIG:
            return os.path.join(self.config_root, path)
        elif type_ == Type.CACHE:
            return os.path.join(self.cache_root, path)
        elif type_ == Type.DATA:
            return os.path.join(self.data_root, path)
        return path

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        for key in self.paths.keys():
            yield (key, self[key])

    def init(self):
        if self.custom_config_root:
            self.cache_root = self.data_root = self.config_root = self.custom_config_root

        self.add('CONFIG_ROOT', None, self.config_root)
        self.add('CACHE_ROOT', None, self.cache_root)
        self.add('DATA_ROOT', None, self.data_root)

        self.init_profile(self.profile)

        if len(self.profile) > 0 and self.profile_separation:
            self.profile = u'.' + self.profile
        else:
            self.profile = ''

        d = {'LOG_DB': 'logs.db', 'MY_CACERTS': 'cacerts.pem',
             'MY_EMOTS': 'emoticons', 'MY_ICONSETS': 'iconsets',
             'MY_MOOD_ICONSETS': 'moods', 'MY_ACTIVITY_ICONSETS': 'activities',
             'PLUGINS_USER': 'plugins'}
        for name in d:
            d[name] += self.profile
            self.add(name, Type.DATA, windowsify(d[name]))
        if len(self.profile):
            self.add('MY_DATA', Type.DATA, 'data.dir')
        else:
            self.add('MY_DATA', Type.DATA, '')

        d = {'CACHE_DB': 'cache.db',
             'VCARD': 'vcards',
             'AVATAR': 'avatars'}
        for name in d:
            d[name] += self.profile
            self.add(name, Type.CACHE, windowsify(d[name]))
        if len(self.profile):
            self.add('MY_CACHE', Type.CACHE, 'cache.dir')
        else:
            self.add('MY_CACHE', Type.CACHE, '')

        if len(self.profile):
            self.add('MY_CONFIG', Type.CONFIG, 'config.dir')
        else:
            self.add('MY_CONFIG', Type.CONFIG, '')

        try:
            self.add('TMP', None, tempfile.gettempdir())
        except IOError as e:
            print('Error opening tmp folder: %s\nUsing %s' % (
                str(e), os.path.expanduser('~')), file=sys.stderr)
            self.add('TMP', None, os.path.expanduser('~'))

    def init_profile(self, profile):
        conffile = windowsify('config')
        secretsfile = windowsify('secrets')
        pluginsconfdir = windowsify('pluginsconfig')
        certsdir = windowsify(u'certs')
        localcertsdir = windowsify(u'localcerts')

        if len(profile) > 0:
            conffile += '.' + profile
            secretsfile += '.' + profile
            pluginsconfdir += '.' + profile
            certsdir += u'.' + profile
            localcertsdir += u'.' + profile

        self.add('SECRETS_FILE', Type.DATA, secretsfile)
        self.add('MY_PEER_CERTS', Type.DATA, certsdir)
        self.add('CONFIG_FILE', Type.CONFIG, conffile)
        self.add('PLUGINS_CONFIG_DIR', Type.CONFIG, pluginsconfdir)
        self.add('MY_CERT', Type.CONFIG, localcertsdir)


_paths = ConfigPaths()

# For backwards compatibility needed
# some plugins use that
gajimpaths = _paths
