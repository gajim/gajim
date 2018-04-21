# -*- coding:utf-8 -*-
## src/common/configpaths.py
##
## Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
##                    Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os
import tempfile

from gajim.common.const import PathType, PathLocation


def get(key):
    return _paths[key]


def get_paths(type_):
    for key, value in _paths.items():
        location, path, path_type = value
        if type_ != path_type:
            continue
        yield _paths[key]


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
        self._paths = {}
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

        source_paths = [
            ('DATA', os.path.join(basedir, 'data')),
            ('GUI', os.path.join(basedir, 'data', 'gui')),
            ('ICONS', os.path.join(basedir, 'data', 'icons')),
            ('HOME', os.path.expanduser('~')),
            ('PLUGINS_BASE', os.path.join(basedir, 'data', 'plugins')),
        ]

        for path in source_paths:
            self._add(*path)

    def __getitem__(self, key):
        location, path, _ = self._paths[key]
        if location == PathLocation.CONFIG:
            return os.path.join(self.config_root, path)
        elif location == PathLocation.CACHE:
            return os.path.join(self.cache_root, path)
        elif location == PathLocation.DATA:
            return os.path.join(self.data_root, path)
        return path

    def items(self):
        for key, value in self._paths.items():
            yield (key, value)

    def _prepare(self, path, unique):
        if os.name == 'nt':
            path = path.capitalize()
        if self.profile:
            if unique or self.profile_separation:
                return '%s.%s' % (path, self.profile)
        return path

    def _add(self, name, path, location=None, path_type=None, unique=False):
        if location is not None:
            path = self._prepare(path, unique)
        self._paths[name] = (location, path, path_type)

    def init(self):
        if self.custom_config_root:
            self.cache_root = self.data_root = self.config_root = self.custom_config_root

        user_dir_paths = [
            ('TMP', tempfile.gettempdir()),
            ('CONFIG_ROOT', self.config_root),
            ('CACHE_ROOT', self.cache_root),
            ('DATA_ROOT', self.data_root),
        ]

        for path in user_dir_paths:
            self._add(*path)

        # These paths are unique per profile
        unique_profile_paths = [
            # Data paths
            ('SECRETS_FILE', 'secrets', PathLocation.DATA, PathType.FILE),
            ('MY_PEER_CERTS', 'certs', PathLocation.DATA, PathType.FOLDER),

            # Config paths
            ('CONFIG_FILE', 'config', PathLocation.CONFIG, PathType.FILE),
            ('PLUGINS_CONFIG_DIR', 'pluginsconfig', PathLocation.CONFIG, PathType.FOLDER),
            ('MY_CERT', 'localcerts', PathLocation.CONFIG, PathType.FOLDER),
        ]

        for path in unique_profile_paths:
            self._add(*path, unique=True)

        # These paths are only unique per profile if the commandline arg
        # `separate` is passed
        paths = [
            # Data paths
            ('LOG_DB', 'logs.db', PathLocation.DATA, PathType.FILE),
            ('MY_CACERTS', 'cacerts.pem', PathLocation.DATA, PathType.FILE),
            ('MY_EMOTS', 'emoticons', PathLocation.DATA, PathType.FOLDER),
            ('MY_ICONSETS', 'iconsets', PathLocation.DATA, PathType.FOLDER),
            ('MY_MOOD_ICONSETS', 'moods', PathLocation.DATA, PathType.FOLDER),
            ('MY_ACTIVITY_ICONSETS', 'activities', PathLocation.DATA, PathType.FOLDER),
            ('PLUGINS_USER', 'plugins', PathLocation.DATA, PathType.FOLDER),

            # Cache paths
            ('CACHE_DB', 'cache.db', PathLocation.CACHE, PathType.FILE),
            ('AVATAR', 'avatars', PathLocation.CACHE, PathType.FOLDER),
        ]

        for path in paths:
            self._add(*path)


_paths = ConfigPaths()

# For backwards compatibility needed
# some plugins use that
gajimpaths = _paths
