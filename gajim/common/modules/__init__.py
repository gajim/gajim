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

import sys
import logging
from importlib import import_module
from unittest.mock import MagicMock

from gajim.common.types import ConnectionT

log = logging.getLogger('gajim.c.m')

ZEROCONF_MODULES = ['iq',
                    'adhoc_commands',
                    'receipts',
                    'discovery',
                    'chatstates']

MODULES = [
    'adhoc_commands',
    'annotations',
    'bits_of_binary',
    'blocking',
    'bookmarks',
    'caps',
    'carbons',
    'chat_markers',
    'chatstates',
    'delimiter',
    'discovery',
    'entity_time',
    'gateway',
    'httpupload',
    'http_auth',
    'iq',
    'last_activity',
    'mam',
    'message',
    'metacontacts',
    'muc',
    'pep',
    'ping',
    'presence',
    'pubsub',
    'receipts',
    'register',
    'roster',
    'roster_item_exchange',
    'search',
    'security_labels',
    'software_version',
    'user_activity',
    'user_avatar',
    'user_location',
    'user_mood',
    'user_nickname',
    'user_tune',
    'vcard4',
    'vcard_avatars',
    'vcard_temp',
    'announce',
    'ibb',
    'jingle',
    'bytestream',
]

_imported_modules = []  # type: List[tuple]
_modules = {}  # type: Dict[str, Dict[str, Any]]
_store_publish_modules = [
    'UserMood',
    'UserActivity',
    'UserLocation',
    'UserTune',
]  # type: List[str]


class ModuleMock:
    def __init__(self, name: str) -> None:
        self._name = name

        # HTTPUpload, ..
        self.available = False

        # Blocking
        self.blocked = []  # type: List[Any]

        # Delimiter
        self.delimiter = '::'

        # Bookmarks
        self.bookmarks = {}  # type: Dict[Any, Any]

        # Various Modules
        self.supported = False

    def __getattr__(self, key: str) -> MagicMock:
        return MagicMock()


def register_modules(con: ConnectionT, *args: Any, **kwargs: Any) -> None:
    if con in _modules:
        return
    _modules[con.name] = {}
    for module_name in MODULES:
        if con.name == 'Local':
            if module_name not in ZEROCONF_MODULES:
                continue
        instance, name = _load_module(module_name, con, *args, **kwargs)
        _modules[con.name][name] = instance


def register_single_module(con: ConnectionT, instance: Any, name: str) -> None:
    if con.name not in _modules:
        raise ValueError('Unknown account name: %s' % con.name)
    _modules[con.name][name] = instance


def unregister_modules(con: ConnectionT) -> None:
    for instance in _modules[con.name].values():
        if hasattr(instance, 'cleanup'):
            instance.cleanup()
    del _modules[con.name]


def unregister_single_module(con: ConnectionT, name: str) -> None:
    if con.name not in _modules:
        return
    if name not in _modules[con.name]:
        return
    del _modules[con.name][name]


def send_stored_publish(account: str) -> None:
    for name in _store_publish_modules:
        _modules[account][name].send_stored_publish()


def get(account: str, name: str) -> Any:
    try:
        return _modules[account][name]
    except KeyError:
        return ModuleMock(name)


def _load_module(name: str, con: ConnectionT, *args: Any, **kwargs: Any) -> Any:
    if name not in MODULES:
        raise ValueError('Module %s does not exist' % name)
    module = sys.modules.get(name)
    if module is None:
        module = import_module('.%s' % name, package='gajim.common.modules')
    return module.get_instance(con, *args, **kwargs)  # type: ignore


def get_handlers(con: ConnectionT) -> List[Tuple[Any, ...]]:
    handlers = []  # type: List[Tuple[Any, ...]]
    for module in _modules[con.name].values():
        handlers += module.handlers
    return handlers
