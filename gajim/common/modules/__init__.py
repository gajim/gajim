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

from typing import Any
from typing import Dict  # pylint: disable=unused-import
from typing import List
from typing import Tuple

import logging
from importlib import import_module
from pathlib import Path
from unittest.mock import MagicMock

from gajim.common.types import ConnectionT

log = logging.getLogger('gajim.c.m')

ZEROCONF_MODULES = ['adhoc_commands',
                    'receipts',
                    'discovery',
                    'chatstates']

_imported_modules = []  # type: List[tuple]
_modules = {}  # type: Dict[str, Dict[str, Any]]

for file in Path(__file__).parent.iterdir():
    if file.stem == '__init__':
        continue

    _module = import_module('.%s' % file.stem, package='gajim.common.modules')
    if hasattr(_module, 'get_instance'):
        log.info('Load module: %s', file.stem)
        if file.stem == 'pep':
            # Register the PEP module first, because other modules
            # depend on it
            _imported_modules.insert(0, (_module, file.stem))
        else:
            _imported_modules.append((_module, file.stem))


class ModuleMock:
    def __init__(self, name: str) -> None:
        self._name = name

        # HTTPUpload, ..
        self.available = False

        # Blocking
        self.blocked = []  # type: List[Any]

        # Privacy Lists
        self.blocked_contacts = []  # type: List[Any]
        self.blocked_groups = []  # type: List[Any]
        self.blocked_all = False

        # Delimiter
        self.delimiter = '::'

        # Bookmarks
        self.bookmarks = {}  # type: Dict[Any, Any]

        # Various Modules
        self.supported = False

    def __getattr__(self, key: str) -> MagicMock:
        return MagicMock()


def register(con: ConnectionT, *args: Any, **kwargs: Any) -> None:
    if con in _modules:
        return
    _modules[con.name] = {}
    for module in _imported_modules:
        mod, name = module
        if con.name == 'Local':
            if name not in ZEROCONF_MODULES:
                continue
        instance, name = mod.get_instance(con, *args, **kwargs)
        _modules[con.name][name] = instance


def register_single(con: ConnectionT, instance: Any, name: str) -> None:
    if con.name not in _modules:
        raise ValueError('Unknown account name: %s' % con.name)
    _modules[con.name][name] = instance


def unregister(con: ConnectionT) -> None:
    for instance in _modules[con.name].values():
        if hasattr(instance, 'cleanup'):
            instance.cleanup()
    del _modules[con.name]


def unregister_single(con: ConnectionT, name: str) -> None:
    if con.name not in _modules:
        return
    if name not in _modules[con.name]:
        return
    del _modules[con.name][name]


def get(account: str, name: str) -> Any:
    try:
        return _modules[account][name]
    except KeyError:
        return ModuleMock(name)


def get_handlers(con: ConnectionT) -> List[Tuple[Any, ...]]:
    handlers = []  # type: List[Tuple[Any, ...]]
    for module in _modules[con.name].values():
        handlers += module.handlers
    return handlers
