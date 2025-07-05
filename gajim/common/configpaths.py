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
import shutil
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


def get_temp_dir() -> Path:
    return _paths.get_temp_dir()


def get_plugin_dirs() -> list[Path]:
    if gajim.IS_FLATPAK:
        return [Path(_paths['PLUGINS_BASE']),
                Path('/app/plugins')]
    return [Path(_paths['PLUGINS_BASE']),
            Path(_paths['PLUGINS_USER'])]


def get_ui_path(filename: str) -> Path:
    return _paths['GUI'] / filename


def get_paths(type_: PathType) -> Generator[Path, None, None]:
    # pylint: disable=unnecessary-dict-index-lookup
    for key, value in _paths.items():
        path_type = value[2]
        if type_ != path_type:
            continue
        yield _paths[key]


def set_separation(active: bool) -> None:
    # Deprecated in Gajim 2.3.0
    _paths.profile_separation = active


def set_profile(profile: str) -> None:
    # Deprecated in Gajim 2.3.0
    _paths.profile = profile


def set_user_profile(user_profile: str) -> None:
    _paths.user_profile = user_profile


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


def cleanup_temp() -> None:
    tmpdir = _paths.get_temp_dir().parent
    for path in tmpdir.glob('gajim-*'):
        if not path.is_dir():
            continue
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass


class ConfigPaths:
    def __init__(self) -> None:
        self._paths: dict[str, PathTupleT] = {}
        self._temp_dir: Path | None = None

        self.profile = ''
        self.user_profile = ''
        self.profile_separation = False
        self.custom_config_root: Path | None = None


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

        if location != PathLocation.NONE:
            path = self._prepare(path, unique)
        self._paths[name] = (location, path, path_type)

    def init(self):

        root_folder = 'gajim'
        if self.user_profile:
            root_folder = f'gajim.{self.user_profile}'

        if sys.platform == 'win32':
            if gajim.IS_PORTABLE:

                root_folder = 'UserData'
                if self.user_profile:
                    root_folder = f'UserData.{self.user_profile}'

                application_path = Path(sys.executable).parent
                self.config_root = self.cache_root = self.data_root = \
                    application_path.parent / root_folder
            else:
                # Documents and Settings\[User Name]\Application Data\Gajim
                self.config_root = self.cache_root = self.data_root = \
                    Path(os.environ['APPDATA']) / root_folder.capitalize()
        else:
            self.config_root = Path(GLib.get_user_config_dir()) / root_folder
            self.cache_root = Path(GLib.get_user_cache_dir()) / root_folder
            self.data_root = Path(GLib.get_user_data_dir()) / root_folder

        if self.custom_config_root:
            self.config_root = self.custom_config_root
            self.cache_root = self.custom_config_root
            self.data_root = self.custom_config_root

        user_dir_paths = [
            ('MY_CONFIG', Path(), PathLocation.CONFIG, PathType.FOLDER),
            ('MY_CACHE', Path(), PathLocation.CACHE, PathType.FOLDER),
            ('MY_DATA', Path(), PathLocation.DATA, PathType.FOLDER),
        ]

        for path in user_dir_paths:
            self.add(*path)

        # These paths are unique per profile
        unique_profile_paths: list[tuple[str, str | Path, PathLocation, PathType]] = [
            # Data paths
            ('CERT_STORE', 'cert_store', PathLocation.DATA, PathType.FOLDER),
            ('DEBUG', 'debug', PathLocation.DATA, PathType.FOLDER),
            ('PLUGINS_DATA', 'plugins_data',
             PathLocation.DATA, PathType.FOLDER),

            # Cache paths
            ('DOWNLOADS_THUMB', 'downloads.thumb', PathLocation.CACHE, PathType.FOLDER),

            # Config paths
            ('SETTINGS', 'settings.sqlite', PathLocation.CONFIG, PathType.FILE),
            ('PLUGINS_CONFIG_DIR',
             'pluginsconfig', PathLocation.CONFIG, PathType.FOLDER),
            ('MY_SHORTCUTS', 'shortcuts.json',
             PathLocation.CONFIG, PathType.FILE),
        ]

        # Determine downloads dir
        path = ('DOWNLOADS', 'downloads', PathLocation.DATA, PathType.FOLDER)
        if sys.platform == 'win32' and not gajim.IS_PORTABLE:
            download_dir = GLib.get_user_special_dir(
                GLib.UserDirectory.DIRECTORY_DOWNLOAD)
            assert download_dir is not None
            path = ('DOWNLOADS', Path(download_dir) / 'Gajim',
                    PathLocation.NONE, PathType.FOLDER)

        unique_profile_paths.append(path)

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

    def get_temp_dir(self) -> Path:
        if self._temp_dir is None or not self._temp_dir.exists():
            self._temp_dir = Path(tempfile.mkdtemp(prefix='gajim-'))
        return self._temp_dir


_paths = ConfigPaths()
