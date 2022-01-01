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

from __future__ import annotations

from typing import Any
from typing import Callable
from typing import TypeVar
from typing import cast

import sys
import math
import time
import sqlite3
import json
import logging
from pathlib import Path

from gi.repository import GLib

from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import RosterItem
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import CommonError
from nbxmpp.modules.discovery import parse_disco_info

_T = TypeVar('_T')

def timeit(func: Callable[..., _T]) -> Callable[..., _T]:
    def func_wrapper(self: Any, *args: Any, **kwargs: Any) -> _T:
        start = time.time()
        result = func(self, *args, **kwargs)
        exec_time = (time.time() - start) * 1e3
        level = 30 if exec_time > 50 else 10
        self._log.log(level,
                      'Execution time for %s: %s ms',
                      func.__name__,
                      math.ceil(exec_time))
        return result
    return func_wrapper


def _convert_common_error(common_error: bytes) -> CommonError:
    return CommonError.from_string(common_error)

def _adapt_common_error(common_error: CommonError) -> str:
    return common_error.serialize()

sqlite3.register_converter('common_error', _convert_common_error)
sqlite3.register_adapter(CommonError, _adapt_common_error)


def _convert_marker(marker: bytes):
    return 'received' if int(marker) == 0 else 'displayed'


sqlite3.register_converter('marker', _convert_marker)

def _jid_adapter(jid: JID) -> str:
    return str(jid)

def _jid_converter(jid: bytes) -> JID:
    return JID.from_string(jid.decode())

sqlite3.register_converter('jid', _jid_converter)
sqlite3.register_adapter(JID, _jid_adapter)

def _convert_disco_info(disco_info: bytes) -> DiscoInfo:
    return parse_disco_info(Iq(node=disco_info))  # type: ignore

def _adapt_disco_info(disco_info: DiscoInfo) -> str:
    return str(disco_info.stanza)

sqlite3.register_converter('disco_info', _convert_disco_info)
sqlite3.register_adapter(DiscoInfo, _adapt_disco_info)


class Encoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return list(o)  # type: ignore

        if isinstance(o, JID):
            return {'__type': 'JID', 'value': str(o)}

        if isinstance(o, RosterItem):
            dct = o.asdict()
            dct['__type'] = 'RosterItem'
            return dct

        return json.JSONEncoder.default(self, o)


def json_decoder(dct: dict[str, Any]) -> Any:
    type_ = dct.get('__type')
    if type_ is None:
        return dct
    if type_ == 'JID':
        return JID.from_string(dct['value'])
    if type_ == 'RosterItem':
        return RosterItem(jid=dct['jid'],
                          name=dct['name'],
                          ask=dct['ask'],
                          subscription=dct['subscription'],
                          groups=set(dct['groups']))
    return dct


class SqliteStorage:
    '''
    Base Storage Class
    '''

    def __init__(self,
                 log: logging.Logger,
                 path: Path,
                 create_statement: str,
                 commit_delay: int = 500) -> None:

        self._log = log
        self._path = path
        self._create_statement = create_statement
        self._commit_delay = commit_delay
        self._con = cast(sqlite3.Connection, None)
        self._commit_source_id = None

    def init(self, **kwargs: Any) -> None:
        if self._path.exists():
            if not self._path.is_file():
                sys.exit('%s must be a file' % self._path)
            self._con = self._connect(**kwargs)

        else:
            self._con = self._create_storage(**kwargs)

        self._migrate_storage()

    def _set_journal_mode(self, mode: str) -> None:
        self._con.execute(f'PRAGMA journal_mode={mode}')

    def _set_synchronous(self, mode: str) -> None:
        self._con.execute(f'PRAGMA synchronous={mode}')

    def _enable_secure_delete(self):
        self._con.execute('PRAGMA secure_delete=1')

    @property
    def user_version(self) -> int:
        return self._con.execute('PRAGMA user_version').fetchone()[0]

    def _connect(self, **kwargs: Any) -> sqlite3.Connection:
        return sqlite3.connect(self._path, **kwargs)

    def _create_storage(self, **kwargs: Any) -> sqlite3.Connection:
        self._log.info('Creating %s', self._path)
        con = self._connect(**kwargs)
        self._path.chmod(0o600)

        try:
            con.executescript(self._create_statement)
        except Exception:
            self._log.exception('Error')
            con.close()
            self._path.unlink()
            sys.exit('Failed creating storage')

        con.commit()
        return con

    def _reinit_storage(self) -> None:
        if self._con is not None:
            self._con.close()
        self._path.unlink()
        self.init()

    def _migrate_storage(self) -> None:
        try:
            self._migrate()
        except Exception:
            self._con.close()
            self._log.exception('Error')
            sys.exit()

    def _migrate(self) -> None:
        raise NotImplementedError

    def _execute_multiple(self, statements: list[str]) -> None:
        """
        Execute multiple statements with the option to fail on duplicates
        but still continue
        """
        for sql in statements:
            try:
                self._con.execute(sql)
                self._con.commit()
            except sqlite3.OperationalError as error:
                if str(error).startswith('duplicate column name:'):
                    self._log.info(error)
                else:
                    self._con.close()
                    self._log.exception('Error')
                    sys.exit()

    @timeit
    def _commit(self) -> bool:
        self._commit_source_id = None
        self._con.commit()
        return False

    def _delayed_commit(self) -> None:
        if self._commit_source_id is not None:
            return

        self._commit_source_id = GLib.timeout_add(self._commit_delay,
                                                  self._commit)

    def shutdown(self) -> None:
        if self._commit_source_id is not None:
            GLib.source_remove(self._commit_source_id)

        self._commit()
        self._con.close()
        del self._con
