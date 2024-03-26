# Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
#                    Junglecow J <junglecow AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import importlib.resources
import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

from gi.repository import GLib

import gajim
from gajim.common.const import PathLocation
from gajim.common.const import PathType
from gajim.common.i18n import _

PathTupleT = tuple[PathLocation | None, Path, PathType | None]


def get(key: str) -> Path:
    return _paths[key]


def get_plugin_dirs() -> list[Path]:
    if gajim.IS_FLATPAK:
        return [Path(_paths['PLUGINS_BASE']),
                Path('/app/plugins')]
    return [Path(_paths['PLUGINS_BASE']),
            Path(_paths['PLUGINS_USER'])]


def get_paths(type_: PathType) -> Generator[Path, None, None]:
    # pylint: disable=unnecessary-dict-index-lookup
    for key, value in _paths.items():
        path_type = value[2]
        if type_ != path_type:
            continue
        yield _paths[key]


def set_separation(active: bool) -> None:
    _paths.profile_separation = active


def set_profile(profile: str) -> None:
    _paths.profile = profile


def set_config_root(config_root: str) -> None:
    _paths.custom_config_root = Path(config_root).resolve()


def init() -> None:
    _paths.init()


def create_paths() -> None:
    for path in get_paths(PathType.FOLDER):
        if path.is_file():
            print(_('%s is a file but it should be a directory') % path)
            print(_('Gajim will now exit'))
            sys.exit()

        if not path.exists():
            for parent_path in reversed(path.parents):
                # Create all parent folders
                # don't use mkdir(parent=True), as it ignores `mode`
                # when creating the parents
                if not parent_path.exists():
                    print(('creating %s directory') % parent_path)
                    parent_path.mkdir(mode=0o700)
            print(('creating %s directory') % path)
            path.mkdir(mode=0o700)


class ConfigPaths:
    def __init__(self) -> None:
        self._paths: dict[str, PathTupleT] = {}
        self.profile = ''
        self.profile_separation = False
        self.custom_config_root: Path | None = None

        if os.name == 'nt':
            if gajim.IS_PORTABLE:
                application_path = Path(sys.executable).parent
                self.config_root = self.cache_root = self.data_root = \
                    application_path.parent / 'UserData'
            else:
                # Documents and Settings\[User Name]\Application Data\Gajim
                self.config_root = self.cache_root = self.data_root = \
                    Path(os.environ['APPDATA']) / 'Gajim'
        else:
            self.config_root = Path(GLib.get_user_config_dir()) / 'gajim'
            self.cache_root = Path(GLib.get_user_cache_dir()) / 'gajim'
            self.data_root = Path(GLib.get_user_data_dir()) / 'gajim'

        basedir = cast(Path, importlib.resources.files('gajim'))

        source_paths = [
            ('DATA', basedir / 'data'),
            ('STYLE', basedir / 'data' / 'style'),
            ('GUI', basedir / 'data' / 'gui'),
            ('ICONS', basedir / 'data' / 'icons'),
            ('HOME', Path.home()),
            ('PLUGINS_BASE', basedir / 'data' / 'plugins'),
        ]

        for path in source_paths:
            self.add(*path)

    def __getitem__(self, key: str) -> Path:
        location, path, _ = self._paths[key]
        if location == PathLocation.CONFIG:
            return self.config_root / path
        if location == PathLocation.CACHE:
            return self.cache_root / path
        if location == PathLocation.DATA:
            return self.data_root / path
        return path

    def items(self) -> Generator[tuple[str, PathTupleT], None, None]:
        yield from self._paths.items()

    def _prepare(self, path: Path, unique: bool) -> Path:
        if os.name == 'nt':
            path = Path(str(path).capitalize())
        if self.profile:
            if unique or self.profile_separation:
                return Path(f'{path}.{self.profile}')
        return path

    def add(self,
            name: str,
            path: Path | str,
            location: PathLocation | None = None,
            path_type: PathType | None = None,
            unique: bool = False) -> None:

        path = Path(path)

        if location is not None:
            path = self._prepare(path, unique)
        self._paths[name] = (location, path, path_type)

    def init(self):
        if self.custom_config_root:
            self.config_root = self.custom_config_root
            self.cache_root = self.data_root = self.custom_config_root

        user_dir_paths = [
            ('TMP', Path(tempfile.gettempdir()), None, None),
            ('MY_CONFIG', Path(), PathLocation.CONFIG, PathType.FOLDER),
            ('MY_CACHE', Path(), PathLocation.CACHE, PathType.FOLDER),
            ('MY_DATA', Path(), PathLocation.DATA, PathType.FOLDER),
        ]

        for path in user_dir_paths:
            self.add(*path)

        # These paths are unique per profile
        unique_profile_paths = [
            # Data paths
            ('SECRETS_FILE', 'secrets', PathLocation.DATA, PathType.FILE),
            ('CERT_STORE', 'cert_store', PathLocation.DATA, PathType.FOLDER),
            ('DEBUG', 'debug', PathLocation.DATA, PathType.FOLDER),
            ('PLUGINS_DATA', 'plugins_data',
             PathLocation.DATA, PathType.FOLDER),

            # Config paths
            ('SETTINGS', 'settings.sqlite', PathLocation.CONFIG, PathType.FILE),
            ('CONFIG_FILE', 'config', PathLocation.CONFIG, PathType.FILE),
            ('PLUGINS_CONFIG_DIR',
             'pluginsconfig', PathLocation.CONFIG, PathType.FOLDER),
            ('MY_SHORTCUTS', 'shortcuts.json',
             PathLocation.CONFIG, PathType.FILE),
        ]

        for path in unique_profile_paths:
            self.add(*path, unique=True)

        # These paths are only unique per profile if the commandline arg
        # `separate` is passed
        paths = [
            # Data paths
            ('LOG_DB', 'logs.db', PathLocation.DATA, PathType.FILE),
            ('PLUGINS_DOWNLOAD', 'plugins_download',
             PathLocation.CACHE, PathType.FOLDER),
            ('PLUGINS_IMAGES', 'plugins_images',
             PathLocation.CACHE, PathType.FOLDER),
            ('PLUGINS_USER', 'plugins', PathLocation.DATA, PathType.FOLDER),
            ('MY_ICONSETS',
             'iconsets', PathLocation.DATA, PathType.FOLDER_OPTIONAL),

            # Cache paths
            ('CACHE_DB', 'cache.db', PathLocation.CACHE, PathType.FILE),
            ('AVATAR', 'avatars', PathLocation.CACHE, PathType.FOLDER),
            ('AVATAR_ICONS', 'avatar_icons',
             PathLocation.CACHE, PathType.FOLDER),
            ('BOB', 'bob', PathLocation.CACHE, PathType.FOLDER),

            # Config paths
            ('MY_THEME', 'theme', PathLocation.CONFIG, PathType.FOLDER),

        ]

        for path in paths:
            self.add(*path)


_paths = ConfigPaths()
