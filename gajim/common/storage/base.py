# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Concatenate
from typing import ParamSpec
from typing import TypeVar

import json
import logging
import math
import os
import pprint
import sqlite3
import sys
import time
from collections.abc import Callable
from datetime import datetime
from datetime import timezone
from pathlib import Path

import nbxmpp.const
import sqlalchemy as sa
import sqlalchemy.exc
from gi.repository import GLib
from nbxmpp.const import Affiliation
from nbxmpp.const import Role
from nbxmpp.const import StatusCode
from nbxmpp.modules.discovery import parse_disco_info
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import CommonError
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import RosterItem
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from gajim.common.helpers import python_version

log = logging.getLogger('gajim.c.storage')

P = ParamSpec('P')
R = TypeVar('R')


class ValueMissingT:
    pass


VALUE_MISSING = ValueMissingT()


def timeit(func: Callable[P, R]) -> Callable[P, R]:
    def func_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if log.getEffectiveLevel() != logging.DEBUG:
            return func(*args, **kwargs)

        start = time.time()
        result = func(*args, **kwargs)
        exec_time = (time.time() - start) * 1e3
        log.debug('Execution time for %s: %s ms',
                  func.__name__, math.ceil(exec_time))
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
    return parse_disco_info(Iq(node=disco_info))  # pyright: ignore


def _adapt_disco_info(disco_info: DiscoInfo) -> str:
    return str(disco_info.stanza)


sqlite3.register_converter('disco_info', _convert_disco_info)
sqlite3.register_adapter(DiscoInfo, _adapt_disco_info)


def _convert_json(json_string: bytes) -> dict[str, Any]:
    return json.loads(json_string, object_hook=json_decoder)


sqlite3.register_converter('JSON', _convert_json)


def _datetime_converter(data: bytes) -> datetime:
    return datetime.fromisoformat(data.decode())


sqlite3.register_converter('datetime', _datetime_converter)


sqlite3.register_adapter(ValueMissingT, lambda _val: None)


class Encoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return list(o)  # pyright: ignore

        if isinstance(o, JID):
            return {'__type': 'JID', 'value': str(o)}

        if isinstance(o, RosterItem):
            dct = o.asdict()
            dct['__type'] = 'RosterItem'
            return dct

        if isinstance(o, Affiliation | Role | StatusCode):
            return {'value': o.value, '__type': o.__class__.__name__}

        return json.JSONEncoder.default(self, o)


def json_decoder(dct: dict[str, Any]) -> Any:
    type_ = dct.get('__type')
    if type_ is None:
        return dct

    if type_ == 'JID':
        return JID.from_string(dct['value'])

    if type_ == 'RosterItem':
        return RosterItem(
            jid=dct['jid'],
            name=dct['name'],
            ask=dct['ask'],
            subscription=dct['subscription'],
            approved=dct['approved'],
            groups=set(dct['groups']),
        )

    if type_ in ('Affiliation', 'Role', 'StatusCode'):
        return getattr(nbxmpp.const, type_)(dct['value'])

    return dct


class SqliteStorage:
    '''
    Base Storage Class
    '''

    def __init__(
        self,
        log: logging.Logger,
        path: Path | None,
        create_statement: str,
        commit_delay: int = 500,
    ) -> None:
        self._log = log
        self._path = path
        self._create_statement = create_statement
        self._commit_delay = commit_delay
        self._con = cast(sqlite3.Connection, None)
        self._commit_source_id = None

    def init(self, **kwargs: Any) -> None:
        if self._path is None or not self._path.exists():
            self._con = self._create_storage(**kwargs)

        else:
            if not self._path.is_file():
                sys.exit('%s must be a file' % self._path)
            self._con = self._connect(**kwargs)

        self._migrate_storage()

    def get_connection(self) -> sqlite3.Connection:
        # Use this only for unittests
        return self._con

    def _enable_foreign_keys(self) -> None:
        self._con.execute('PRAGMA foreign_keys=ON')

    def _set_journal_mode(self, mode: str) -> None:
        self._con.execute(f'PRAGMA journal_mode={mode}')

    def _set_synchronous(self, mode: str) -> None:
        self._con.execute(f'PRAGMA synchronous={mode}')

    def _enable_secure_delete(self) -> None:
        self._con.execute('PRAGMA secure_delete=1')

    def _run_analyze(self) -> None:
        self._con.execute('PRAGMA analysis_limit=400')
        self._con.execute('PRAGMA optimize')

    @property
    def user_version(self) -> int:
        return self._con.execute('PRAGMA user_version').fetchone()[0]

    def _connect(self, **kwargs: Any) -> sqlite3.Connection:
        self._log.info('Connect to %s', self._path)
        return sqlite3.connect(self._path or ':memory:', **kwargs)

    def _create_storage(self, **kwargs: Any) -> sqlite3.Connection:
        self._log.info('Creating %s', self._path or 'in memory')

        con = self._connect(**kwargs)

        if self._path is not None:
            self._path.chmod(0o600)

        try:
            con.executescript(self._create_statement)
        except Exception:
            self._log.exception('Error')
            con.close()
            if self._path is not None:
                self._path.unlink()
            sys.exit('Failed creating storage')

        con.commit()
        return con

    def _reinit_storage(self) -> None:
        self._con.close()
        if self._path is not None:
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
        '''
        Execute multiple statements with the option to fail on duplicates
        but still continue
        '''
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

        self._commit_source_id = GLib.timeout_add(self._commit_delay, self._commit)

    def shutdown(self) -> None:
        if self._commit_source_id is not None:
            GLib.source_remove(self._commit_source_id)

        self._commit()
        self._run_analyze()
        self._con.close()
        del self._con


class AlchemyStorage:
    def __init__(
        self,
        log: logging.Logger,
        path: Path | None,
        pragma: dict[str, str] | None = None,
    ) -> None:
        self._log = log
        self._path = path
        self._engine = self._create_engine()
        self._session = self._create_session()
        self._commit_source_id = None
        self._pragma = pragma or {}

    def init(self) -> None:
        if self._path is None or not self._path.exists():
            self._create_storage()

        elif not self._path.is_file():
            sys.exit('%s must be a file' % self._path)

        self._migrate_storage()

    def get_session(self) -> Session:
        return self._session

    def get_engine(self) -> Engine:
        return self._engine

    def _set_sqlite_pragma(
        self, dbapi_connection: DBAPIConnection, _connection_record: Any
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')

        for key, value in self._pragma.items():
            cursor.execute(f'PRAGMA {key}={value}')
        cursor.close()

    def _run_analyze(self) -> None:
        with self._session as s:
            connection = s.connection().connection.dbapi_connection
            assert connection is not None
            cursor = connection.cursor()
            cursor.execute('PRAGMA analysis_limit=400')
            cursor.execute('PRAGMA optimize')
            cursor.execute('VACUUM')

    def _get_user_version(self) -> int:
        with self._session as s:
            return s.scalar(sa.text('PRAGMA user_version'))

    def _create_engine(self) -> Engine:
        self._log.info('Create engine')

        con_str = 'sqlite://'
        if self._path is not None:
            con_str += f'/{self._path}'

        engine = sa.create_engine(
            con_str, connect_args={'check_same_thread': False}, echo=False
        )
        event.listen(engine, 'connect', self._set_sqlite_pragma)
        return engine

    def _create_session(self) -> Session:
        return sessionmaker(
            expire_on_commit=False, autoflush=False, bind=self._engine
        )()

    def _create_storage(self) -> None:
        self._log.info('Creating %s', self._path or 'in memory')

        with self._session as s:
            try:
                self._create_table(s, self._engine)
            except Exception:
                self._log.exception('Error')
                if self._path is not None:
                    self._path.unlink()
                sys.exit('Failed creating storage')

        if self._path is not None:
            self._path.chmod(0o600)

    def _create_table(self, session: Session, engine: Engine) -> None:
        raise NotImplementedError

    def _reinit_storage(self) -> None:
        self._engine.dispose()
        if self._path is not None:
            self._path.unlink()
        self._engine = self._create_engine()
        self._session = self._create_session()
        self.init()

    def _migrate_storage(self) -> None:
        try:
            self._migrate()
        except Exception:
            self._log.exception('Migration error')
            raise

    def _migrate(self) -> None:
        raise NotImplementedError

    def _explain(self, session: Session, stmt: Any) -> None:
        if not os.environ.get('GAJIM_EXPLAIN'):
            return

        stmt = stmt.compile(
            compile_kwargs={'literal_binds': True}, dialect=sa.dialects.sqlite.dialect()
        )

        res = session.execute(sa.text(f'EXPLAIN QUERY PLAN {stmt}')).all()
        explanation = pprint.pformat(res)
        log.debug('\n%s\n%s', stmt, explanation)

    def shutdown(self) -> None:
        self._run_analyze()
        self._engine.dispose()
        del self._session
        del self._engine


def with_session(
    func: Callable[Concatenate[Any, Session, P], R]
) -> Callable[Concatenate[Any, P], R]:
    def wrapper(self: Any, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._create_session() as session, session.begin():
            return func(self, session, *args, **kwargs)

    return wrapper


class JIDType(sa.types.TypeDecorator[JID]):
    impl = sa.types.TEXT
    cache_ok = True

    def process_bind_param(self, value: JID | None, dialect: Any) -> str | None:
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value: str | None, dialect: Any) -> JID | None:
        if value is None:
            return value
        return JID.from_string(value)


class StrValueMissingType(sa.types.TypeDecorator[Any]):
    impl = sa.types.TEXT
    cache_ok = True

    def process_bind_param(
        self, value: str | None | ValueMissingT, dialect: Any
    ) -> str | None:
        if isinstance(value, ValueMissingT):
            return None
        return value


class EpochTimestampType(sa.types.TypeDecorator[Any]):
    impl = sa.types.FLOAT
    cache_ok = True

    def process_bind_param(
        self, value: datetime | ValueMissingT | None, dialect: Any
    ) -> float | None:
        if value is None or isinstance(value, ValueMissingT):
            return None

        if value.tzinfo != timezone.utc:
            raise ValueError('DateTime must be UTC')
        return value.timestamp()

    def process_result_value(
        self, value: float | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value, timezone.utc)


class JSONType(sa.types.TypeDecorator[Any]):
    impl = sa.types.TEXT
    cache_ok = True

    def process_bind_param(self, value: dict[str, Any] | None, dialect: Any):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value: str | None, dialect: Any):
        if value is not None:
            return json.loads(value)
        return value


def is_unique_constraint_error(error: sqlalchemy.exc.DatabaseError) -> bool:
    if not isinstance(error, sqlalchemy.exc.IntegrityError):
        return False

    if python_version('<3.11'):
        return 'UNIQUE constraint failed' in error.args[0]
    return (
        error.orig.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE  # pyright: ignore
    )
