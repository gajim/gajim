# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

from typing import Any
from typing import Literal
from typing import NamedTuple

import calendar
import datetime
import json
import logging
import sqlite3 as sqlite
import time
from collections import namedtuple
from collections.abc import Iterator
from collections.abc import KeysView

from nbxmpp import JID
from nbxmpp.structs import CommonError
from nbxmpp.structs import MessageProperties

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import JIDConstant
from gajim.common.const import KindConstant
from gajim.common.const import MAX_MESSAGE_CORRECTION_DELAY
from gajim.common.helpers import AdditionalDataDict
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.base import SqliteStorage
from gajim.common.storage.base import timeit

CURRENT_USER_VERSION = 7

ARCHIVE_SQL_STATEMENT = '''
    CREATE TABLE jids(
            jid_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            jid TEXT UNIQUE,
            type INTEGER
    );
    CREATE TABLE logs(
            log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            account_id INTEGER,
            jid_id INTEGER,
            contact_name TEXT,
            occupant_id TEXT,
            real_jid TEXT,
            time INTEGER,
            kind INTEGER,
            show INTEGER,
            message TEXT,
            error TEXT,
            subject TEXT,
            additional_data TEXT,
            stanza_id TEXT,
            message_id TEXT,
            encryption TEXT,
            encryption_state TEXT,
            marker INTEGER
    );
    CREATE TABLE last_archive_message(
            jid_id INTEGER PRIMARY KEY UNIQUE,
            last_mam_id TEXT,
            oldest_mam_timestamp TEXT,
            last_muc_timestamp TEXT
    );
    CREATE INDEX idx_logs_jid_id_time ON logs (jid_id, time DESC);
    CREATE INDEX idx_logs_stanza_id ON logs (stanza_id);
    CREATE INDEX idx_logs_message_id ON logs (message_id);
    PRAGMA user_version=%s;
    ''' % CURRENT_USER_VERSION

log = logging.getLogger('gajim.c.storage.archive')


class JidsTableRow(NamedTuple):
    jid_id: int
    jid: JID
    type: JIDConstant


class ConversationRow(NamedTuple):
    log_line_id: int
    contact_name: str | None
    occupant_id: str | None
    real_jid: JID | None
    time: float
    kind: int
    show: int
    message: str
    error: CommonError
    subject: str
    additional_data: AdditionalDataDict | None
    stanza_id: str
    message_id: str
    marker: str


class LastConversationRow(NamedTuple):
    contact_name: str
    time: float
    kind: int
    message: str | None
    additional_data: AdditionalDataDict | None
    message_id: str
    stanza_id: str


class SearchLogRow(NamedTuple):
    account_id: int
    jid_id: int
    contact_name: str
    time: float
    kind: int
    show: int
    message: str
    subject: str
    additional_data: AdditionalDataDict
    log_line_id: int


class HistoryDayRow(NamedTuple):
    day: int


class MessageMetaRow(NamedTuple):
    log_line_id: int
    time: float


class LastArchiveMessageRow(NamedTuple):
    id: int
    last_mam_id: str
    oldest_mam_timestamp: str | None
    last_muc_timestamp: str


class MessageExportRow(NamedTuple):
    jid: str
    contact_name: str
    time: float
    kind: int
    message: str


class MessageArchiveStorage(SqliteStorage):
    def __init__(self, in_memory: bool = False):
        path = None if in_memory else configpaths.get('LOG_DB')
        SqliteStorage.__init__(self,
                               log,
                               path,
                               ARCHIVE_SQL_STATEMENT)

        self._jid_ids: dict[JID, JidsTableRow] = {}
        self._jid_ids_reversed: dict[int, JidsTableRow] = {}

    def init(self, **kwargs: Any) -> None:
        SqliteStorage.init(self,
                           detect_types=sqlite.PARSE_COLNAMES)

        self._set_journal_mode('WAL')
        self._enable_secure_delete()

        self._con.row_factory = self._namedtuple_factory

        self._con.create_function('like', 1, self._like)

        self._get_jid_ids_from_db()

    def _namedtuple_factory(self,
                            cursor: sqlite.Cursor,
                            row: tuple[Any, ...]) -> NamedTuple:

        assert cursor.description is not None
        fields = [col[0] for col in cursor.description]
        Row = namedtuple('Row', fields)  # pyright: ignore
        named_row = Row(*row)
        if 'additional_data' in fields:
            _dict = json.loads(named_row.additional_data or '{}')
            named_row = named_row._replace(
                additional_data=AdditionalDataDict(_dict))

        # if an alias `account` for the field `account_id` is used for the
        # query, the account_id is converted to the account jid
        if 'account' in fields:
            if named_row.account:
                jid = self._jid_ids_reversed[named_row.account].jid
                named_row = named_row._replace(account=jid)
        return named_row

    def _migrate(self) -> None:
        user_version = self.user_version
        if user_version == 0:
            # All migrations from 0.16.9 until 1.0.0
            statements = [
                'ALTER TABLE logs ADD COLUMN "account_id" INTEGER',
                'ALTER TABLE logs ADD COLUMN "stanza_id" TEXT',
                'ALTER TABLE logs ADD COLUMN "encryption" TEXT',
                'ALTER TABLE logs ADD COLUMN "encryption_state" TEXT',
                'ALTER TABLE logs ADD COLUMN "marker" INTEGER',
                'ALTER TABLE logs ADD COLUMN "additional_data" TEXT',
                '''CREATE TABLE IF NOT EXISTS last_archive_message(
                    jid_id INTEGER PRIMARY KEY UNIQUE,
                    last_mam_id TEXT,
                    oldest_mam_timestamp TEXT,
                    last_muc_timestamp TEXT
                    )''',

                '''CREATE INDEX IF NOT EXISTS idx_logs_stanza_id
                   ON logs(stanza_id)''',
                'PRAGMA user_version=1'
            ]

            self._execute_multiple(statements)

        if user_version < 2:
            statements = [
                ('ALTER TABLE last_archive_message '
                 'ADD COLUMN "sync_threshold" INTEGER'),
                'PRAGMA user_version=2'
            ]
            self._execute_multiple(statements)

        if user_version < 3:
            statements = [
                'ALTER TABLE logs ADD COLUMN "message_id" TEXT',
                'PRAGMA user_version=3'
            ]
            self._execute_multiple(statements)

        if user_version < 4:
            statements = [
                'ALTER TABLE logs ADD COLUMN "error" TEXT',
                'PRAGMA user_version=4'
            ]
            self._execute_multiple(statements)

        if user_version < 5:
            statements = [
                '''CREATE INDEX IF NOT EXISTS idx_logs_message_id
                   ON logs (message_id)''',
                'PRAGMA user_version=5'
            ]
            self._execute_multiple(statements)

        if user_version < 7:
            statements = [
                'ALTER TABLE logs ADD COLUMN "real_jid" TEXT',
                'ALTER TABLE logs ADD COLUMN "occupant_id" TEXT',
                'PRAGMA user_version=7'
            ]
            self._execute_multiple(statements)

    @staticmethod
    def _like(search_str: str) -> str:
        return f'%{search_str}%'

    @timeit
    def _get_jid_ids_from_db(self) -> None:
        '''
        Load all jid/jid_id tuples into a dict for faster access
        '''
        rows = self._con.execute(
            'SELECT jid_id, jid, type FROM jids').fetchall()
        for row in rows:
            self._jid_ids[row.jid] = row
            self._jid_ids_reversed[row.jid_id] = row

    def get_jid_from_id(self, jid_id: int) -> JidsTableRow | None:
        # Use get as a fail-safe for cases where the JID ID table is incomplete
        return self._jid_ids_reversed.get(jid_id)

    def get_jids_in_db(self) -> KeysView[JID]:
        return self._jid_ids.keys()

    def get_account_id(self,
                       account: str,
                       type_: JIDConstant = JIDConstant.NORMAL_TYPE
                       ) -> int:
        jid = app.get_jid_from_account(account)
        return self.get_jid_id(jid, type_=type_)

    def get_active_account_ids(self) -> list[int]:
        account_ids: list[int] = []
        for account in app.settings.get_active_accounts():
            account_ids.append(self.get_account_id(account))
        return account_ids

    @timeit
    def get_jid_id(self,
                   jid: JID,
                   kind: KindConstant | None = None,
                   type_: JIDConstant | None = None
                   ) -> int:
        '''
        Get the jid id from a jid.
        In case the jid id is not found create a new one.

        :param jid:     The JID

        :param kind:    The KindConstant

        :param type_:   The JIDConstant

        return the jid id
        '''

        if kind in (KindConstant.GC_MSG, KindConstant.GCSTATUS):
            type_ = JIDConstant.ROOM_TYPE
        elif kind is not None:
            type_ = JIDConstant.NORMAL_TYPE

        result = self._jid_ids.get(jid, None)
        if result is not None:
            return result.jid_id

        sql = 'SELECT jid_id, jid, type FROM jids WHERE jid = ?'
        row = self._con.execute(sql, [jid]).fetchone()
        if row is not None:
            self._jid_ids[jid] = row
            return row.jid_id

        if type_ is None:
            raise ValueError(
                'Unable to insert new JID because type is missing')

        sql = 'INSERT INTO jids (jid, type) VALUES (?, ?)'
        lastrowid = self._con.execute(sql, (jid, type_)).lastrowid
        assert lastrowid is not None
        self._jid_ids[jid] = JidsTableRow(jid_id=lastrowid,
                                          jid=jid,
                                          type=type_)
        self._delayed_commit()
        return lastrowid

    @timeit
    def get_conversation_before_after(self,
                                      account: str,
                                      jid: JID,
                                      before: bool,
                                      timestamp: float,
                                      n_lines: int
                                      ) -> list[ConversationRow]:
        '''
        Load n_lines lines of conversation with jid before or after timestamp

        :param account:         The account

        :param jid:             The jid for which we request the conversation

        :param before:          bool for direction (before or after timestamp)

        :param timestamp:       timestamp

        returns a list of namedtuples
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        kinds = map(str, [KindConstant.ERROR,
                          KindConstant.STATUS])

        if before:
            time_order = 'AND time < ? ORDER BY time DESC, log_line_id DESC'
        else:
            time_order = 'AND time > ? ORDER BY time ASC, log_line_id ASC'

        sql = '''
            SELECT
                log_line_id,
                contact_name,
                occupant_id,
                real_jid as "real_jid [jid]",
                time,
                kind,
                show,
                message,
                error as "error [common_error]",
                subject,
                additional_data,
                stanza_id,
                message_id,
                marker as "marker [marker]"
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            {time_order}
            LIMIT ?
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds),
                       time_order=time_order)

        return self._con.execute(
            sql,
            tuple(jids) + (timestamp, n_lines)).fetchall()

    @timeit
    def get_last_conversation_line(self,
                                   account: str,
                                   jid: JID
                                   ) -> LastConversationRow | None:
        '''
        Load the last line of a conversation with jid for account.
        Loads messages, but no status messages or error messages.

        :param account:         The account

        :param jid:             The jid for which we request the conversation

        returns a list of namedtuples
        '''
        jids = [jid]
        account_id = self.get_account_id(account)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS,
                          KindConstant.ERROR])

        sql = '''
            SELECT contact_name, time, kind, message, stanza_id, message_id,
            additional_data
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            ORDER BY time DESC
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))

        return self._con.execute(sql, tuple(jids)).fetchone()

    @timeit
    def get_conversation_around(self,
                                account: str,
                                jid: JID,
                                timestamp: float
                                ) -> tuple[list[ConversationRow],
                                           list[ConversationRow]]:
        '''
        Load all lines of conversation with jid around a specific timestamp

        :param account:         The account

        :param jid:             The jid for which we request the conversation

        :param timestamp:       Timestamp around which to fetch messages

        returns a list of namedtuples
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        kinds = map(str, [KindConstant.ERROR])
        n_lines = 50

        sql_before = '''
            SELECT
                log_line_id,
                contact_name,
                occupant_id,
                real_jid as "real_jid [jid]",
                time,
                kind,
                show,
                message,
                error as "error [common_error]",
                subject,
                additional_data,
                stanza_id,
                message_id,
                marker as "marker [marker]"
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            AND time < ?
            ORDER BY time DESC, log_line_id DESC
            LIMIT ?
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))
        sql_at_after = '''
            SELECT
                log_line_id,
                contact_name,
                occupant_id,
                real_jid as "real_jid [jid]",
                time,
                kind,
                show,
                message,
                error as "error [common_error]",
                subject,
                additional_data,
                stanza_id,
                message_id,
                marker as "marker [marker]"
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            AND time >= ?
            ORDER BY time ASC, log_line_id ASC
            LIMIT ?
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))
        before = self._con.execute(
            sql_before,
            tuple(jids) + (timestamp, n_lines)).fetchall()
        at_after = self._con.execute(
            sql_at_after,
            tuple(jids) + (timestamp, n_lines)).fetchall()
        return before, at_after

    @timeit
    def get_conversation_between(self,
                                 account: str,
                                 jid: str,
                                 before: float,
                                 after: float) -> list[ConversationRow]:
        '''
        Load all lines of conversation with jid between two timestamps

        :param account:         The account

        :param jid:             The jid for which we request the conversation

        :param before:          latest timestamp

        :param after:           earliest timestamp

        returns a list of namedtuples
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        kinds = map(str, [KindConstant.ERROR])

        sql = '''
            SELECT
                log_line_id,
                contact_name,
                occupant_id,
                real_jid as "real_jid [jid]",
                time,
                kind,
                show,
                message,
                error as "error [common_error]",
                subject,
                additional_data,
                stanza_id,
                message_id,
                marker as "marker [marker]"
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            AND time < ? AND time >= ?
            ORDER BY time DESC, log_line_id DESC
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))

        return self._con.execute(
            sql,
            tuple(jids) + (before, after)).fetchall()

    @timeit
    def search_log(self,
                   account: str,
                   jid: JID,
                   query: str,
                   from_users: list[str] | None = None,
                   before: datetime.datetime | None = None,
                   after: datetime.datetime | None = None
                   ) -> Iterator[SearchLogRow]:
        '''
        Search the conversation log for messages containing the `query` string.

        The search can either span the complete log for the given
        `account` and `jid` or be restricted to a single day by
        specifying `date`.

        :param account: The account

        :param jid: The jid for which we request the conversation

        :param query: A search string

        :param from_users: A list of usernames or None

        :param before: A datetime.datetime instance or None

        :param after: A datetime.datetime instance or None

        returns a list of namedtuples
        '''
        account_id = self.get_account_id(account)
        jids = [jid]

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        if before is None:
            before_ts = datetime.datetime.now().timestamp()
        else:
            before_ts = before.timestamp()

        after_ts = 0
        if after is not None:
            after_ts = after.timestamp()

        if from_users is None:
            users_query_string = ''
        else:
            users_query_string = 'AND UPPER(contact_name) IN (?)'

        sql = '''
            SELECT account_id, jid_id, contact_name, time, kind, show, message,
                   subject, additional_data, log_line_id
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND message LIKE like(?)
            AND kind NOT IN ({kinds})
            {users_query}
            AND time BETWEEN ? AND ?
            ORDER BY time DESC, log_line_id
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds),
                       users_query=users_query_string)

        if from_users is None:

            cursor = self._con.execute(
                sql, tuple(jids) + (query, after_ts, before_ts))
            while True:
                results = cursor.fetchmany(25)
                if not results:
                    break
                for result in results:
                    yield result
            return

        users = ','.join([user.upper() for user in from_users])

        cursor = self._con.execute(
            sql, tuple(jids) + (query, users, after_ts, before_ts))
        while True:
            results = cursor.fetchmany(25)
            if not results:
                break
            for result in results:
                yield result

    @timeit
    def search_all_logs(self,
                        query: str,
                        from_users: list[str] | None = None,
                        before: datetime.datetime | None = None,
                        after: datetime.datetime | None = None
                        ) -> Iterator[SearchLogRow]:
        '''
        Search all conversation logs for messages containing the `query`
        string.

        :param query: A search string

        :param from_users: A list of usernames or None

        :param before: A datetime.datetime instance or None

        :param after: A datetime.datetime instance or None

        returns a list of namedtuples
        '''
        account_ids = self.get_active_account_ids()
        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        if before is None:
            before_ts = datetime.datetime.now().timestamp()
        else:
            before_ts = before.timestamp()

        after_ts = 0
        if after is not None:
            after_ts = after.timestamp()

        if from_users is None:
            users_query_string = ''
        else:
            users_query_string = 'AND UPPER(contact_name) IN (?)'

        sql = '''
            SELECT account_id, jid_id, contact_name, time, kind, show, message,
                   subject, additional_data, log_line_id
            FROM logs WHERE message LIKE like(?)
            AND account_id IN ({account_ids})
            AND kind NOT IN ({kinds})
            {users_query}
            AND time BETWEEN ? AND ?
            ORDER BY time DESC, log_line_id
            '''.format(account_ids=', '.join(map(str, account_ids)),
                       kinds=', '.join(kinds),
                       users_query=users_query_string)

        if from_users is None:
            cursor = self._con.execute(sql, (query, after_ts, before_ts))
            while True:
                results = cursor.fetchmany(25)
                if not results:
                    break
                for result in results:
                    yield result
            return

        users = ','.join([user.upper() for user in from_users])
        cursor = self._con.execute(sql, (query, users, after_ts, before_ts))
        while True:
            results = cursor.fetchmany(25)
            if not results:
                break
            for result in results:
                yield result

    @timeit
    def get_days_with_history(self,
                              account: str,
                              jid: str,
                              year: int,
                              month: int
                              ) -> list[HistoryDayRow]:
        '''
        Get days in month where messages for 'jid' exist
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        # Calculate the start and end datetime of the month
        date = datetime.datetime(year, month, 1)
        days = calendar.monthrange(year, month)[1] - 1
        delta = datetime.timedelta(
            days=days, hours=23, minutes=59, seconds=59, microseconds=999999)

        sql = '''
            SELECT DISTINCT
            CAST(strftime('%d', time, 'unixepoch', 'localtime') AS INTEGER)
            AS day FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND time BETWEEN ? AND ?
            AND kind NOT IN ({kinds})
            ORDER BY time
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))

        return self._con.execute(
            sql,
            tuple(jids) + (date.timestamp(),
                           (date + delta).timestamp())).fetchall()

    @timeit
    def get_last_history_timestamp(self,
                                   account: str,
                                   jid: str
                                   ) -> float | None:
        '''
        Get the timestamp of the last message we received for the jid
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        sql = '''
            SELECT MAX(time) as time FROM logs
            NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            '''.format(account_id=account_id,
                       jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        # fetchone() returns always at least one Row with all
        # attributes set to None because of the MAX() function
        return self._con.execute(sql, tuple(jids)).fetchone().time

    @timeit
    def get_first_history_timestamp(self,
                                    account: str,
                                    jid: str
                                    ) -> float | None:
        '''
        Get the timestamp of the first message we received for the jid
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        sql = '''
            SELECT MIN(time) as time FROM logs
            NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))

        # fetchone() returns always at least one Row with all
        # attributes set to None because of the MIN() function
        return self._con.execute(sql, tuple(jids)).fetchone().time

    @timeit
    def date_has_history(self,
                         account: str,
                         jid: str,
                         date: datetime.datetime
                         ) -> float | None:
        '''
        Get a single timestamp of a message for 'jid'
        in time range of one day
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        delta = datetime.timedelta(
            hours=23, minutes=59, seconds=59, microseconds=999999)

        start = date.timestamp()
        end = (date + delta).timestamp()

        sql = '''
            SELECT time
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND time BETWEEN ? AND ?
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id)

        return self._con.execute(
            sql, tuple(jids) + (start, end)).fetchone()

    @timeit
    def get_first_message_meta_for_date(self,
                                        account: str,
                                        jid: str,
                                        date: datetime.datetime
                                        ) -> MessageMetaRow | None:
        '''
        Load meta data for the first message of a specific date
        '''
        jids = [jid]
        account_id = self.get_account_id(account)

        delta = datetime.timedelta(
            hours=23, minutes=59, seconds=59, microseconds=999999)
        date_ts = date.timestamp()
        delta_ts = (date + delta).timestamp()

        sql = '''
            SELECT time, log_line_id
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND time BETWEEN ? AND ?
            ORDER BY time ASC, log_line_id ASC
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id)

        return self._con.execute(
            sql,
            tuple(jids) + (date_ts, delta_ts)).fetchone()

    @timeit
    def get_recent_muc_nicks(self, contact: GroupchatContact) -> list[str]:
        '''
        Queries the last 50 message rows and gathers nicknames in a list
        '''
        jids = [contact.jid]
        account_id = self.get_account_id(contact.account)
        kinds = map(str, [KindConstant.GC_MSG])

        sql = '''
            SELECT contact_name
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind IN ({kinds})
            ORDER BY time DESC
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))


        result = self._con.execute(sql, (tuple(jids))).fetchmany(50)

        nicknames: list[str] = []
        for row in result:
            if (row.contact_name not in nicknames and
                    row.contact_name is not None):
                nicknames.append(row.contact_name)

        return nicknames

    @timeit
    def find_stanza_id(self,
                       account: str,
                       archive_jid: str,
                       stanza_id: str | None,
                       origin_id: str | None = None,
                       groupchat: bool = False
                       ) -> bool:
        '''
        Checks if a stanza-id is already in the `logs` table

        :param account:     The account

        :param archive_jid: The jid of the archive the stanza-id belongs to
                            only used if groupchat=True

        :param stanza_id:   The stanza-id

        :param origin_id:   The origin-id

        :param groupchat:   stanza-id is from a groupchat

        return True if the stanza-id was found
        '''
        ids: list[str] = []
        if stanza_id is not None:
            ids.append(stanza_id)
        if origin_id is not None:
            ids.append(origin_id)

        if not ids:
            return False

        type_ = JIDConstant.NORMAL_TYPE
        if groupchat:
            type_ = JIDConstant.ROOM_TYPE

        archive_id = self.get_jid_id(archive_jid, type_=type_)
        account_id = self.get_account_id(account)

        if groupchat:
            # Stanza ID is only unique within a specific archive.
            # So a Stanza ID could be repeated in different MUCs, so we
            # filter also for the archive JID which is the bare MUC jid.

            # Use Unary-"+" operator for "jid_id", otherwise the
            # idx_logs_jid_id_time index is used instead of the much better
            # idx_logs_stanza_id index
            sql = '''
                SELECT stanza_id FROM logs
                WHERE stanza_id IN ({values})
                AND +jid_id = ? AND account_id = ? LIMIT 1
                '''.format(values=', '.join('?' * len(ids)))
            result = self._con.execute(
                sql, tuple(ids) + (archive_id, account_id)).fetchone()
        else:
            sql = '''
                SELECT stanza_id FROM logs
                WHERE stanza_id IN ({values}) AND account_id = ? AND
                kind != ? LIMIT 1
                '''.format(values=', '.join('?' * len(ids)))
            result = self._con.execute(
                sql, tuple(ids) + (account_id, KindConstant.GC_MSG)).fetchone()

        if result is not None:
            log.info('Found duplicated message, stanza-id: %s, origin-id: %s, '
                     'archive-jid: %s, account: %s', stanza_id, origin_id,
                     archive_jid, account_id)
            return True
        return False

    @timeit
    def get_last_correctable_message(self,
                                     account: str,
                                     jid: JID,
                                     message_id: str
                                     ) -> LastConversationRow | None:
        '''
        Load the last correctable message of a conversation by message_id.
        Conditions: max 5 min old
        '''
        jids = [jid]
        account_id = self.get_account_id(account)
        min_time = time.time() - MAX_MESSAGE_CORRECTION_DELAY

        sql = '''
            SELECT contact_name, time, kind, message, stanza_id, message_id,
            additional_data
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND message_id = ?
            AND time > ?
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id)

        return self._con.execute(
            sql,
            tuple(jids) + (message_id, min_time)).fetchone()

    @timeit
    def try_message_correction(self,
                               account: str,
                               jid: JID,
                               nickname: str | None,
                               corrected_text: str,
                               correct_id: str,
                               kind: KindConstant,
                               timestamp: float) -> bool:

        '''Try to correct a message

        :param jid:  This can be a full jid or bare jid. A full jid only if the
                     message is a MUC PM, otherwise a bare jid needs to be
                     passed. `nickname` should only be passed if the message
                     is a group chat message.
        '''

        account_id = self.get_account_id(account)
        max_timestamp = timestamp - MAX_MESSAGE_CORRECTION_DELAY

        self._log.debug(
            'Check if message is correctable, parameters: %s %s %s %s %s',
            jid, account_id, nickname, correct_id, max_timestamp)

        sql = '''SELECT log_line_id, message, additional_data
                 FROM logs
                 NATURAL JOIN jids jid_id
                 WHERE +jid = ?
                 AND account_id = ?
                 AND contact_name IS ?
                 AND message_id = ?
                 AND kind = ?
                 AND time > ?
                 '''

        rows = self._con.execute(sql, (jid,
                                       account_id,
                                       nickname,
                                       correct_id,
                                       kind,
                                       max_timestamp
                                       )).fetchall()

        if not rows:
            self._log.debug('No correctable messages found')
            return False

        if len(rows) != 1:
            self._log.warning('More than one correctable message found')
            return False

        row = rows[0]

        if row.additional_data is None:
            additional_data = AdditionalDataDict()
        else:
            additional_data = row.additional_data

        original_text = additional_data.get_value(
            'corrected', 'original_text')
        if original_text is None:
            # Only set original_text for the first correction
            additional_data.set_value(
                'corrected', 'original_text', row.message)
        serialized_dict = json.dumps(additional_data.data)

        sql = '''
            UPDATE logs SET message = ?, additional_data = ?
            WHERE log_line_id = ?
            '''
        self._con.execute(
            sql, (corrected_text, serialized_dict, row.log_line_id))

        return True

    @timeit
    def update_additional_data(self,
                               account: str,
                               stanza_id: str,
                               properties: MessageProperties) -> None:
        is_groupchat = properties.type.is_groupchat
        type_ = JIDConstant.NORMAL_TYPE
        if is_groupchat:
            type_ = JIDConstant.ROOM_TYPE

        assert properties.jid is not None
        archive_id = self.get_jid_id(properties.jid.bare, type_=type_)
        account_id = self.get_account_id(account)

        if is_groupchat:
            # Stanza ID is only unique within a specific archive.
            # So a Stanza ID could be repeated in different MUCs, so we
            # filter also for the archive JID which is the bare MUC jid.

            # Use Unary-"+" operator for "jid_id", otherwise the
            # idx_logs_jid_id_time index is used instead of the much better
            # idx_logs_stanza_id index
            sql = '''
                SELECT additional_data FROM logs
                WHERE stanza_id = ?
                AND +jid_id = ?
                AND account_id = ?
                LIMIT 1
                '''
            result = self._con.execute(
                sql, (stanza_id, archive_id, account_id)).fetchone()
        else:
            sql = '''
                SELECT additional_data FROM logs
                WHERE stanza_id = ?
                AND account_id = ?
                AND kind != ?
                LIMIT 1
                '''
            result = self._con.execute(
                sql, (stanza_id, account_id, KindConstant.GC_MSG)).fetchone()

        if result is None:
            return

        if result.additional_data is None:
            additional_data = AdditionalDataDict()
        else:
            additional_data = result.additional_data

        if properties.is_moderation:
            assert properties.moderation is not None
            additional_data.set_value(
                'retracted', 'by', properties.moderation.moderator_jid)
            additional_data.set_value(
                'retracted', 'timestamp', properties.moderation.timestamp)
            additional_data.set_value(
                'retracted', 'reason', properties.moderation.reason)
        serialized_dict = json.dumps(additional_data.data)

        if is_groupchat:
            sql = '''
                UPDATE logs SET additional_data = ?
                WHERE stanza_id = ?
                AND account_id = ?
                AND +jid_id = ?
                '''
            self._con.execute(
                sql, (serialized_dict, stanza_id, account_id, archive_id))
        else:
            sql = '''
                UPDATE logs SET additional_data = ?
                WHERE stanza_id = ?
                AND account_id = ?
                AND kind != ?
                '''
            self._con.execute(
                sql, (serialized_dict, stanza_id, account_id,
                      KindConstant.GC_MSG))

    def insert_jid(self,
                   jid: str,
                   kind: KindConstant | None = None,
                   type_: JIDConstant = JIDConstant.NORMAL_TYPE
                   ) -> int:
        '''
        Insert a new jid into the `jids` table.
        This is an alias of get_jid_id() for better readablility.

        :param jid:     The jid as string

        :param kind:    A KindConstant

        :param type_:   A JIDConstant
        '''
        return self.get_jid_id(jid, kind, type_)

    @timeit
    def insert_into_logs(self,
                         account: str,
                         jid: str,
                         time_: float,
                         kind: KindConstant,
                         **kwargs: Any
                         ) -> int:
        '''
        Insert a new message into the `logs` table

        :param jid:     The jid as string

        :param time_:   The timestamp in UTC epoch

        :param kind:    A KindConstant

        :param unread:  If True the message is added to the`unread_messages`
                        table. Only if kind == CHAT_MSG_RECV

        :param kwargs:  Every additional named argument must correspond to
                        a field in the `logs` table
        '''
        jid_id = self.get_jid_id(jid, kind=kind)
        account_id = self.get_account_id(account)

        if 'additional_data' in kwargs:
            if not kwargs['additional_data']:
                del kwargs['additional_data']
            else:
                serialized_dict = json.dumps(kwargs['additional_data'].data)
                kwargs['additional_data'] = serialized_dict

        sql = '''
              INSERT INTO logs (account_id, jid_id, time, kind, {columns})
              VALUES (?, ?, ?, ?, {values})
              '''.format(columns=', '.join(kwargs.keys()),
                         values=', '.join('?' * len(kwargs)))

        lastrowid = self._con.execute(
            sql, (account_id,
                  jid_id, time_,
                  kind) + tuple(kwargs.values())).lastrowid
        assert lastrowid is not None

        log.info('Insert into DB: jid: %s, time: %s, kind: %s, stanza_id: %s',
                 jid, time_, kind, kwargs.get('stanza_id', None))

        self._delayed_commit()

        return lastrowid

    @timeit
    def delete_message_from_logs(self, log_line_id: int) -> None:
        '''
        Delete a message from the `logs` table

        :param log_line_id: The message's log_line_id
        '''
        sql = 'DELETE FROM logs WHERE log_line_id = ?'
        self._con.execute(sql, (log_line_id, ))

        self._delayed_commit()
        log.info('Deleted message with log_line_id %s', log_line_id)

    @timeit
    def set_message_error(self,
                          account_jid: str,
                          jid: JID,
                          message_id: str,
                          error: str
                          ) -> None:
        '''
        Update the corresponding message with the error

        :param account_jid: The jid of the account

        :param jid:         The jid that belongs to the avatar

        :param message_id:  The id of the message

        :param error:       The error stanza as string

        '''

        account_id = self.get_jid_id(account_jid)
        try:
            jid_id = self.get_jid_id(str(jid))
        except ValueError:
            # Unknown JID
            return

        sql = '''
            UPDATE logs SET error = ?
            WHERE account_id = ? AND jid_id = ? AND message_id = ?
            '''
        self._con.execute(sql, (error, account_id, jid_id, message_id))
        self._delayed_commit()

    @timeit
    def set_marker(self,
                   account_jid: str,
                   jid: str,
                   message_id: str,
                   state: Literal['received', 'displayed']
                   ) -> None:
        '''
        Update the marker state of the corresponding message
        '''

        if state not in ('received', 'displayed'):
            raise ValueError('Invalid marker state')

        account_id = self.get_jid_id(account_jid)
        try:
            jid_id = self.get_jid_id(str(jid))
        except ValueError:
            # Unknown JID
            return

        state_int = 0 if state == 'received' else 1

        sql = '''
            UPDATE logs SET marker = ?
            WHERE account_id = ? AND jid_id = ? AND message_id = ?
            '''
        self._con.execute(sql, (state_int, account_id, jid_id, message_id))
        self._delayed_commit()

    @timeit
    def get_archive_infos(self, jid: str) -> LastArchiveMessageRow | None:
        '''
        Get the archive infos

        :param jid:     The jid that belongs to the avatar

        '''
        jid_id = self.get_jid_id(jid, type_=JIDConstant.ROOM_TYPE)
        sql = '''SELECT * FROM last_archive_message WHERE jid_id = ?'''
        return self._con.execute(sql, (jid_id,)).fetchone()

    @timeit
    def set_archive_infos(self, jid: str, **kwargs: Any) -> None:
        '''
        Set archive infos

        :param jid:                     The jid that belongs to the avatar

        :param last_mam_id:             The last MAM result id

        :param oldest_mam_timestamp:    The oldest date we requested MAM
                                        history for

        :param last_muc_timestamp:      The timestamp of the last message we
                                        received in a MUC

        :param sync_threshold:          The max days that we request from a
                                        MUC archive

        '''
        jid_id = self.get_jid_id(jid)
        exists = self.get_archive_infos(jid)
        if not exists:
            sql = '''INSERT INTO last_archive_message
                     (jid_id, last_mam_id, oldest_mam_timestamp,
                      last_muc_timestamp)
                      VALUES (?, ?, ?, ?)'''
            self._con.execute(sql, (
                jid_id,
                kwargs.get('last_mam_id', None),
                kwargs.get('oldest_mam_timestamp', None),
                kwargs.get('last_muc_timestamp', None),
            ))
        else:
            for key, value in list(kwargs.items()):
                if value is None:
                    del kwargs[key]

            args = ' = ?, '.join(kwargs.keys()) + ' = ?'
            sql = '''UPDATE last_archive_message SET {}
                     WHERE jid_id = ?'''.format(args)
            self._con.execute(sql, tuple(kwargs.values()) + (jid_id,))
        log.info('Set message archive info: %s %s', jid, kwargs)
        self._delayed_commit()

    @timeit
    def reset_archive_infos(self, jid: str) -> None:
        '''
        Set archive infos

        :param jid:                     The jid of the archive

        '''
        jid_id = self.get_jid_id(jid)
        sql = '''UPDATE last_archive_message
                 SET last_mam_id = NULL, oldest_mam_timestamp = NULL,
                 last_muc_timestamp = NULL
                 WHERE jid_id = ?'''
        self._con.execute(sql, (jid_id,))
        log.info('Reset message archive info: %s', jid)
        self._delayed_commit()

    def get_conversation_jids(self, account: str) -> list[JID]:
        account_id = self.get_account_id(account)
        sql = '''SELECT DISTINCT jid as "jid [jid]"
                 FROM logs
                 NATURAL JOIN jids jid_id
                 WHERE account_id = ?'''
        rows = self._con.execute(sql, (account_id, )).fetchall()
        return [row.jid for row in rows]

    def get_messages_for_export(self,
                                account: str,
                                jid: JID
                                ) -> Iterator[MessageExportRow]:

        kinds = map(str, [KindConstant.CHAT_MSG_RECV,
                          KindConstant.SINGLE_MSG_SENT,
                          KindConstant.CHAT_MSG_SENT,
                          KindConstant.GC_MSG])

        account_id = self.get_account_id(account)
        sql = '''SELECT jid, time, kind, message, contact_name
                 FROM logs
                 NATURAL JOIN jids jid_id
                 WHERE account_id = ? AND kind in ({kinds}) AND jid = ?
                 ORDER BY time'''.format(kinds=', '.join(kinds))

        cursor = self._con.execute(sql, (account_id, jid))
        while True:
            results = cursor.fetchmany(10)
            if not results:
                break
            yield from results

    def remove_history(self, account: str, jid: JID) -> None:
        '''
        Remove history for a specific chat.
        If it's a group chat, remove last MAM ID as well.
        '''
        account_id = self.get_account_id(account)
        try:
            jid_id = self.get_jid_id(jid)
        except ValueError:
            log.info('No history entries for: %s', jid)
            return
        sql = 'DELETE FROM logs WHERE account_id = ? AND jid_id = ?'
        self._con.execute(sql, (account_id, jid_id))

        self._delayed_commit()
        log.info('Removed history for: %s', jid)

    def remove_all_history(self) -> None:
        '''
        Remove all messages for all accounts
        '''
        statements = [
            'DELETE FROM logs',
            'DELETE FROM jids',
            'DELETE FROM last_archive_message'
        ]
        self._execute_multiple(statements)
        log.info('Removed all chat history')

    def cleanup_chat_history(self) -> None:
        '''
        Remove messages from account where messages are older than max_age
        '''
        for account in app.settings.get_accounts():
            max_age = app.settings.get_account_setting(
                account, 'chat_history_max_age')
            if max_age == -1:
                continue
            account_id = self.get_account_id(account)
            now = time.time()
            point_in_time = now - int(max_age)

            sql = 'DELETE FROM logs WHERE account_id = ? AND time < ?'

            cursor = self._con.execute(sql, (account_id, point_in_time))
            self._delayed_commit()
            log.info('Removed %s old messages for %s', cursor.rowcount, account)
