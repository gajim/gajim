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

import sys
import math
import time
import sqlite3

from gi.repository import GLib

from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import CommonError
from nbxmpp.modules.discovery import parse_disco_info


def timeit(func):
    def func_wrapper(self, *args, **kwargs):
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


def _convert_common_error(common_error):
    return CommonError.from_string(common_error)

def _adapt_common_error(common_error):
    return common_error.serialize()

sqlite3.register_converter('common_error', _convert_common_error)
sqlite3.register_adapter(CommonError, _adapt_common_error)


def _convert_marker(marker):
    return 'received' if int(marker) == 0 else 'displayed'


sqlite3.register_converter('marker', _convert_marker)

def _jid_adapter(jid):
    return str(jid)

def _jid_converter(jid):
    return JID.from_string(jid.decode())

sqlite3.register_converter('jid', _jid_converter)
sqlite3.register_adapter(JID, _jid_adapter)

def _convert_disco_info(disco_info):
    return parse_disco_info(Iq(node=disco_info))

def _adapt_disco_info(disco_info):
    return str(disco_info.stanza)

sqlite3.register_converter('disco_info', _convert_disco_info)
sqlite3.register_adapter(DiscoInfo, _adapt_disco_info)


class SqliteStorage:
    '''
    Base Storage Class
    '''

    def __init__(self,
                 log,
                 path,
                 create_statement,
                 commit_delay=500):

        self._log = log
        self._path = path
        self._create_statement = create_statement
        self._commit_delay = commit_delay
        self._con = None
        self._commit_source_id = None

    def init(self, **kwargs):
        if self._path.exists():
            if not self._path.is_file():
                sys.exit('%s must be a file', self._path)
            self._con = self._connect(**kwargs)

        else:
            self._con = self._create_storage(**kwargs)

        self._migrate_storage()

    def _set_journal_mode(self, mode):
        self._con.execute(f'PRAGMA journal_mode={mode}')

    def _set_synchronous(self, mode):
        self._con.execute(f'PRAGMA synchronous={mode}')

    def _enable_secure_delete(self):
        self._con.execute('PRAGMA secure_delete=1')

    @property
    def user_version(self) -> int:
        return self._con.execute('PRAGMA user_version').fetchone()[0]

    def _connect(self, **kwargs):
        return sqlite3.connect(self._path, **kwargs)

    def _create_storage(self, **kwargs):
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

    def _reinit_storage(self):
        if self._con is not None:
            self._con.close()
        self._path.unlink()
        self.init()

    def _migrate_storage(self):
        try:
            self._migrate()
        except Exception:
            self._con.close()
            self._log.exception('Error')
            sys.exit()

    def _migrate(self):
        raise NotImplementedError

    def _execute_multiple(self, statements):
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
    def _commit(self):
        self._commit_source_id = None
        self._con.commit()
        return False

    def _delayed_commit(self):
        if self._commit_source_id is not None:
            return

        self._commit_source_id = GLib.timeout_add(self._commit_delay,
                                                  self._commit)

    def shutdown(self):
        if self._commit_source_id is not None:
            GLib.source_remove(self._commit_source_id)

        self._commit()
        self._con.close()
        self._con = None
