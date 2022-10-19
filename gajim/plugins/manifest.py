# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import Optional

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version as V

import gajim

from .helpers import is_shipped_plugin
from .plugins_i18n import _ as p_

BLOCKED_PLUGINS = [
    'appindicator_integration',
    'omemo',
    'plugin_installer',
    'syntax_highlight',
    'url_image_preview'
]

GAJIM_VERSION = V(gajim.__version__.split('+', 1)[0]).base_version


@dataclass(frozen=True, eq=True)
class PluginManifest:
    name: str
    short_name: str
    description: str
    authors: list[str]
    homepage: str
    config_dialog: bool
    version: V
    requirements: list[Requirement]
    platforms: list[str]
    path: Optional[Path] = None

    def __hash__(self):
        return hash(f'{self.short_name}_{self.version}')

    @property
    def is_usable(self) -> bool:
        if self.short_name in BLOCKED_PLUGINS:
            return False

        if not self._check_requirements():
            return False

        platform = sys.platform
        if platform not in ('win32', 'darwin', 'linux'):
            # sys.platform can return an unknown amount of unix/linux derivates
            platform = 'others'

        return platform in self.platforms

    @property
    def is_shipped(self) -> bool:
        if self.path is None:
            return False
        return is_shipped_plugin(self.path)

    def get_remote_url(self, repository_url: str) -> str:
        filename = f'{self.short_name}_{self.version}.zip'
        return f'{repository_url}/{self.short_name}/{filename}'

    @classmethod
    def from_path(cls, path: Path) -> PluginManifest:
        manifest_path = path / 'plugin-manifest.json'
        if not manifest_path.exists():
            raise ValueError(f'Not a plugin path: {path}')

        if manifest_path.is_dir():
            raise ValueError(f'Not a plugin path: {path}')

        with manifest_path.open(encoding='utf8') as f:
            try:
                manifest = json.load(f)
            except Exception as error:
                raise ValueError(f'Error while parsing manifest: '
                                 f'{path}, {error}')
        return cls.from_manifest_json(manifest, manifest_path)

    def _check_requirements(self) -> bool:
        return any(GAJIM_VERSION in req.specifier for req in self.requirements)

    @classmethod
    def from_manifest_json(cls,
                           manifest: dict[str, Any],
                           path: Optional[Path] = None) -> PluginManifest:
        return cls(
            name=manifest['name'],
            short_name=manifest['short_name'],
            description=p_(manifest['description']),
            authors=manifest['authors'],
            homepage=manifest['homepage'],
            config_dialog=manifest['config_dialog'],
            version=V(manifest['version']),
            requirements=[Requirement(r) for r in manifest['requirements']],
            platforms=manifest['platforms'],
            path=path.parent if path is not None else path)
