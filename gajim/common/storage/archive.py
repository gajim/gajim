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

import time
import datetime
import calendar
import json
import logging
import sqlite3 as sqlite
from collections import namedtuple

from gajim.common import app
from gajim.common import configpaths
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import ShowConstant
from gajim.common.const import KindConstant
from gajim.common.const import JIDConstant

from gajim.common.storage.base import SqliteStorage
from gajim.common.storage.base import timeit


CURRENT_USER_VERSION = 6

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


class MessageArchiveStorage(SqliteStorage):
    def __init__(self):
        SqliteStorage.__init__(self,
                               log,
                               configpaths.get('LOG_DB'),
                               ARCHIVE_SQL_STATEMENT)

        self._jid_ids = {}
        self._jid_ids_reversed = {}

    def init(self, **kwargs):
        SqliteStorage.init(self,
                           detect_types=sqlite.PARSE_COLNAMES)

        self._set_journal_mode('WAL')
        self._enable_secure_delete()

        self._con.row_factory = self._namedtuple_factory

        self._con.create_function("like", 1, self._like)
        self._con.create_function("get_timeout", 0, self._get_timeout)

        self._get_jid_ids_from_db()
        self._cleanup_chat_history()

    def _namedtuple_factory(self, cursor, row):
        fields = [col[0] for col in cursor.description]
        Row = namedtuple("Row", fields)
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

    def _migrate(self):
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
                'ALTER TABLE last_archive_message ADD COLUMN "sync_threshold" INTEGER',
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
                'CREATE INDEX idx_logs_message_id ON logs (message_id)',
                'PRAGMA user_version=5'
            ]
            self._execute_multiple(statements)

    @staticmethod
    def dispatch(event, error):
        app.ged.raise_event(event, None, str(error))

    @staticmethod
    def _get_timeout():
        """
        returns the timeout in epoch
        """
        timeout = app.settings.get('restore_timeout')

        now = int(time.time())
        if timeout > 0:
            timeout = now - (timeout * 60)
        return timeout

    @staticmethod
    def _like(search_str):
        return '%{}%'.format(search_str)

    @timeit
    def _get_jid_ids_from_db(self):
        """
        Load all jid/jid_id tuples into a dict for faster access
        """
        rows = self._con.execute(
            'SELECT jid_id, jid, type FROM jids').fetchall()
        for row in rows:
            self._jid_ids[row.jid] = row
            self._jid_ids_reversed[row.jid_id] = row

    def get_jids_in_db(self):
        return self._jid_ids.keys()

    def jid_is_from_pm(self, jid):
        """
        If jid is gajim@conf/nkour it's likely a pm one, how we know gajim@conf
        is not a normal guy and nkour is not his resource?  we ask if gajim@conf
        is already in jids (with type room jid) this fails if user disables
        logging for room and only enables for pm (so highly unlikely) and if we
        fail we do not go chaos (user will see the first pm as if it was message
        in room's public chat) and after that all okay
        """
        if jid.find('/') > -1:
            possible_room_jid = jid.split('/', 1)[0]
            return self.jid_is_room_jid(possible_room_jid)
        # it's not a full jid, so it's not a pm one
        return False

    def jid_is_room_jid(self, jid):
        """
        Return True if it's a room jid, False if it's not, None if we don't know
        """
        jid_ = self._jid_ids.get(jid)
        if jid_ is None:
            return None
        return jid_.type == JIDConstant.ROOM_TYPE

    @staticmethod
    def _get_family_jids(account, jid):
        """
        Get all jids of the metacontacts family

        :param account: The account

        :param jid:     The JID

        returns a list of JIDs'
        """
        family = app.contacts.get_metacontacts_family(account, jid)
        if family:
            return [user['jid'] for user in family]
        return [jid]

    def get_account_id(self, account, type_=JIDConstant.NORMAL_TYPE):
        jid = app.get_jid_from_account(account)
        return self.get_jid_id(jid, type_=type_)

    @timeit
    def get_jid_id(self, jid, kind=None, type_=None):
        """
        Get the jid id from a jid.
        In case the jid id is not found create a new one.

        :param jid:     The JID

        :param kind:    The KindConstant

        :param type_:   The JIDConstant

        return the jid id
        """

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
        Row = namedtuple('Row', 'jid_id jid type')
        self._jid_ids[jid] = Row(lastrowid, jid, type_)
        self._delayed_commit()
        return lastrowid

    @staticmethod
    def convert_show_values_to_db_api_values(show):
        """
        Convert from string style to constant ints for db
        """

        if show == 'online':
            return ShowConstant.ONLINE
        if show == 'chat':
            return ShowConstant.CHAT
        if show == 'away':
            return ShowConstant.AWAY
        if show == 'xa':
            return ShowConstant.XA
        if show == 'dnd':
            return ShowConstant.DND
        if show == 'offline':
            return ShowConstant.OFFLINE
        if show is None:
            return ShowConstant.ONLINE
        # invisible in GC when someone goes invisible
        # it's a RFC violation .... but we should not crash
        return None

    @timeit
    def get_conversation_before(self, account, jid, end_timestamp, n_lines):
        """
        Load n_lines lines of conversation with jid before end_timestamp

        :param account:         The account

        :param jid:             The jid for which we request the conversation

        :param end_timestamp:   end timestamp / datetime.datetime instance

        returns a list of namedtuples
        """
        jids = self._get_family_jids(account, jid)
        account_id = self.get_account_id(account)

        sql = '''
            SELECT contact_name, time, kind, show, message, subject,
                   additional_data, log_line_id, message_id,
                   error as "error [common_error]",
                   marker as "marker [marker]"
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND time < ?
            ORDER BY time DESC, log_line_id DESC
            LIMIT ?
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id)

        return self._con.execute(
            sql,
            tuple(jids) + (end_timestamp.timestamp(), n_lines)).fetchall()

    @timeit
    def get_conversation_muc_before(self, account, jid, end_timestamp,
                                    n_lines):
        """
        Load n_lines lines of conversation with jid before end_timestamp

        :param account:         The account

        :param jid:             The jid for which we request the conversation

        :param end_timestamp:   end timestamp / datetime.datetime instance

        returns a list of namedtuples
        """
        jids = self._get_family_jids(account, jid)
        # TODO: this does not load messages correctly when account_id is set
        # account_id = self.get_account_id(account, type_=JIDConstant.ROOM_TYPE)

        sql = '''
            SELECT contact_name, time, kind, show, message, subject,
                   additional_data, log_line_id, message_id,
                   error as "error [common_error]",
                   marker as "marker [marker]"
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND kind = {kind}
            AND time < ?
            ORDER BY time DESC, log_line_id DESC
            LIMIT ?
            '''.format(jids=', '.join('?' * len(jids)),
                       kind=KindConstant.GC_MSG)

        return self._con.execute(
            sql,
            tuple(jids) + (end_timestamp.timestamp(), n_lines)).fetchall()

    @timeit
    def get_last_conversation_line(self, account, jid):
        """
        Load the last line of a conversation with jid for account.
        Loads messages, but no status messages or error messages.

        :param account:         The account

        :param jid:             The jid for which we request the conversation

        returns a list of namedtuples
        """
        jids = self._get_family_jids(account, jid)
        account_id = self.get_account_id(account)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS,
                          KindConstant.ERROR])

        sql = '''
            SELECT contact_name, time, kind, message
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND kind NOT IN ({kinds})
            ORDER BY time DESC
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id,
                       kinds=', '.join(kinds))

        return self._con.execute(sql, tuple(jids)).fetchone()

    @timeit
    def get_messages_for_date(self, account, jid, date):
        """
        Load the complete conversation with a given jid on a specific date

        :param account: The account

        :param jid:     The jid for which we request the conversation

        :param date:    datetime.datetime instance
                        example: datetime.datetime(year, month, day)

        returns a list of namedtuples
        """

        jids = self._get_family_jids(account, jid)
        account_id = self.get_account_id(account)

        delta = datetime.timedelta(
            hours=23, minutes=59, seconds=59, microseconds=999999)
        date_ts = date.timestamp()
        delta_ts = (date + delta).timestamp()

        sql = '''
            SELECT contact_name, time, kind, show, message, subject,
                   additional_data, log_line_id
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND account_id = {account_id}
            AND time BETWEEN ? AND ?
            ORDER BY time DESC, log_line_id DESC
            '''.format(jids=', '.join('?' * len(jids)),
                       account_id=account_id)

        return self._con.execute(
            sql,
            tuple(jids) + (date_ts, delta_ts)).fetchall()

    @timeit
    def search_log(self, account, jid, query, date=None):
        """
        Search the conversation log for messages containing the `query` string.

        The search can either span the complete log for the given
        `account` and `jid` or be restricted to a single day by
        specifying `date`.

        :param account: The account

        :param jid:     The jid for which we request the conversation

        :param query:   A search string

        :param date:    datetime.datetime instance
                        example: datetime.datetime(year, month, day)

        returns a list of namedtuples
        """
        jids = self._get_family_jids(account, jid)

        if date:
            delta = datetime.timedelta(
                hours=23, minutes=59, seconds=59, microseconds=999999)

            between = '''
                AND time BETWEEN {start} AND {end}
                '''.format(start=date.timestamp(),
                           end=(date + delta).timestamp())

        sql = '''
        SELECT contact_name, time, kind, show, message, subject,
               additional_data, log_line_id
        FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
        AND message LIKE like(?) {date_search}
        ORDER BY time DESC, log_line_id
        '''.format(jids=', '.join('?' * len(jids)),
                   date_search=between if date else '')

        return self._con.execute(sql, tuple(jids) + (query,)).fetchall()

    @timeit
    def get_days_with_logs(self, account, jid, year, month):
        """
        Request the days in a month where we received messages
        for a given `jid`.

        :param account: The account

        :param jid:     The jid for which we request the days

        :param year:    The year

        :param month:   The month

        returns a list of namedtuples
        """
        jids = self._get_family_jids(account, jid)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        # Calculate the start and end datetime of the month
        date = datetime.datetime(year, month, 1)
        days = calendar.monthrange(year, month)[1] - 1
        delta = datetime.timedelta(
            days=days, hours=23, minutes=59, seconds=59, microseconds=999999)

        sql = """
            SELECT DISTINCT 
            CAST(strftime('%d', time, 'unixepoch', 'localtime') AS INTEGER)
            AS day FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND time BETWEEN ? AND ?
            AND kind NOT IN ({kinds})
            ORDER BY time
            """.format(jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        return self._con.execute(sql, tuple(jids) +
                                      (date.timestamp(),
                                      (date + delta).timestamp())).fetchall()

    @timeit
    def get_last_date_that_has_logs(self, account, jid):
        """
        Get the timestamp of the last message we received for the jid.

        :param account: The account

        :param jid:     The jid for which we request the last timestamp

        returns a timestamp or None
        """
        jids = self._get_family_jids(account, jid)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        sql = '''
            SELECT MAX(time) as time FROM logs
            NATURAL JOIN jids WHERE jid IN ({jids})
            AND kind NOT IN ({kinds})
            '''.format(jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        # fetchone() returns always at least one Row with all
        # attributes set to None because of the MAX() function
        return self._con.execute(sql, tuple(jids)).fetchone().time

    @timeit
    def get_first_date_that_has_logs(self, account, jid):
        """
        Get the timestamp of the first message we received for the jid.

        :param account: The account

        :param jid:     The jid for which we request the first timestamp

        returns a timestamp or None
        """
        jids = self._get_family_jids(account, jid)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        sql = '''
            SELECT MIN(time) as time FROM logs
            NATURAL JOIN jids WHERE jid IN ({jids})
            AND kind NOT IN ({kinds})
            '''.format(jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        # fetchone() returns always at least one Row with all
        # attributes set to None because of the MIN() function
        return self._con.execute(sql, tuple(jids)).fetchone().time

    @timeit
    def get_date_has_logs(self, account, jid, date):
        """
        Get single timestamp of a message we received for the jid
        in the time range of one day.

        :param account: The account

        :param jid:     The jid for which we request the first timestamp

        :param date:    datetime.datetime instance
                        example: datetime.datetime(year, month, day)

        returns a timestamp or None
        """
        jids = self._get_family_jids(account, jid)

        delta = datetime.timedelta(
            hours=23, minutes=59, seconds=59, microseconds=999999)

        start = date.timestamp()
        end = (date + delta).timestamp()

        sql = '''
            SELECT time
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND time BETWEEN ? AND ?
            '''.format(jids=', '.join('?' * len(jids)))

        return self._con.execute(
            sql, tuple(jids) + (start, end)).fetchone()

    @timeit
    def deduplicate_muc_message(self, account, jid, resource,
                                timestamp, message_id):
        """
        Check if a message is already in the `logs` table

        :param account:     The account

        :param jid:         The muc jid as string

        :param resource:    The resource

        :param timestamp:   The timestamp in UTC epoch

        :param message_id:  The message-id
        """

        # Add 60 seconds around the timestamp
        start_time = timestamp - 60
        end_time = timestamp + 60

        account_id = self.get_account_id(account)
        log.debug('Search for MUC duplicate')
        log.debug('start: %s, end: %s, jid: %s, resource: %s, message-id: %s',
                  start_time, end_time, jid, resource, message_id)

        sql = '''
            SELECT * FROM logs
            NATURAL JOIN jids WHERE
            jid = ? AND
            contact_name = ? AND
            message_id = ? AND
            account_id = ? AND
            time BETWEEN ? AND ?
            '''

        result = self._con.execute(sql, (jid,
                                         resource,
                                         message_id,
                                         account_id,
                                         start_time,
                                         end_time)).fetchone()

        if result is not None:
            log.debug('Found duplicate')
            return True
        return False

    @timeit
    def find_stanza_id(self, account, archive_jid, stanza_id, origin_id=None,
                       groupchat=False):
        """
        Checks if a stanza-id is already in the `logs` table

        :param account:     The account

        :param archive_jid: The jid of the archive the stanza-id belongs to
                            only used if groupchat=True

        :param stanza_id:   The stanza-id

        :param origin_id:   The origin-id

        :param groupchat:   stanza-id is from a groupchat

        return True if the stanza-id was found
        """
        ids = []
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
                WHERE stanza_id IN ({values}) AND account_id = ? AND kind != ? LIMIT 1
                '''.format(values=', '.join('?' * len(ids)))
            result = self._con.execute(
                sql, tuple(ids) + (account_id, KindConstant.GC_MSG)).fetchone()

        if result is not None:
            log.info('Found duplicated message, stanza-id: %s, origin-id: %s, '
                     'archive-jid: %s, account: %s', stanza_id, origin_id, archive_jid, account_id)
            return True
        return False

    def insert_jid(self, jid, kind=None, type_=JIDConstant.NORMAL_TYPE):
        """
        Insert a new jid into the `jids` table.
        This is an alias of get_jid_id() for better readablility.

        :param jid:     The jid as string

        :param kind:    A KindConstant

        :param type_:   A JIDConstant
        """
        return self.get_jid_id(jid, kind, type_)

    @timeit
    def insert_into_logs(self, account, jid, time_, kind, **kwargs):
        """
        Insert a new message into the `logs` table

        :param jid:     The jid as string

        :param time_:   The timestamp in UTC epoch

        :param kind:    A KindConstant

        :param unread:  If True the message is added to the`unread_messages`
                        table. Only if kind == CHAT_MSG_RECV

        :param kwargs:  Every additional named argument must correspond to
                        a field in the `logs` table
        """
        jid_id = self.get_jid_id(jid, kind=kind)
        account_id = self.get_account_id(account)

        if 'additional_data' in kwargs:
            if not kwargs['additional_data']:
                del kwargs['additional_data']
            else:
                serialized_dict = json.dumps(kwargs["additional_data"].data)
                kwargs['additional_data'] = serialized_dict

        sql = '''
              INSERT INTO logs (account_id, jid_id, time, kind, {columns})
              VALUES (?, ?, ?, ?, {values})
              '''.format(columns=', '.join(kwargs.keys()),
                         values=', '.join('?' * len(kwargs)))

        lastrowid = self._con.execute(
            sql, (account_id, jid_id, time_, kind) + tuple(kwargs.values())).lastrowid

        log.info('Insert into DB: jid: %s, time: %s, kind: %s, stanza_id: %s',
                 jid, time_, kind, kwargs.get('stanza_id', None))

        self._delayed_commit()

        return lastrowid

    @timeit
    def set_message_error(self, account_jid, jid, message_id, error):
        """
        Update the corresponding message with the error

        :param account_jid: The jid of the account

        :param jid:         The jid that belongs to the avatar

        :param message_id:  The id of the message

        :param error:       The error stanza as string

        """

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
    def set_marker(self, account_jid, jid, message_id, state):
        """
        Update the marker state of the corresponding message

        :param account_jid: The jid of the account

        :param jid:         The jid that belongs to the avatar

        :param message_id:  The id of the message

        :param state:       The state, 'received' or 'displayed'

        """
        if state not in ('received', 'displayed'):
            raise ValueError('Invalid marker state')

        account_id = self.get_jid_id(account_jid)
        try:
            jid_id = self.get_jid_id(str(jid))
        except ValueError:
            # Unknown JID
            return

        state = 0 if state == 'received' else 1

        sql = '''
            UPDATE logs SET marker = ?
            WHERE account_id = ? AND jid_id = ? AND message_id = ?
            '''
        self._con.execute(sql, (state, account_id, jid_id, message_id))
        self._delayed_commit()

    @timeit
    def get_archive_infos(self, jid):
        """
        Get the archive infos

        :param jid:     The jid that belongs to the avatar

        """
        jid_id = self.get_jid_id(jid, type_=JIDConstant.ROOM_TYPE)
        sql = '''SELECT * FROM last_archive_message WHERE jid_id = ?'''
        return self._con.execute(sql, (jid_id,)).fetchone()

    @timeit
    def set_archive_infos(self, jid, **kwargs):
        """
        Set archive infos

        :param jid:                     The jid that belongs to the avatar

        :param last_mam_id:             The last MAM result id

        :param oldest_mam_timestamp:    The oldest date we requested MAM
                                        history for

        :param last_muc_timestamp:      The timestamp of the last message we
                                        received in a MUC

        :param sync_threshold:          The max days that we request from a
                                        MUC archive

        """
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
    def reset_archive_infos(self, jid):
        """
        Set archive infos

        :param jid:                     The jid of the archive

        """
        jid_id = self.get_jid_id(jid)
        sql = '''UPDATE last_archive_message
                 SET last_mam_id = NULL, oldest_mam_timestamp = NULL,
                 last_muc_timestamp = NULL
                 WHERE jid_id = ?'''
        self._con.execute(sql, (jid_id,))
        log.info('Reset message archive info: %s', jid)
        self._delayed_commit()

    def _cleanup_chat_history(self):
        """
        Remove messages from account where messages are older than max_age
        """
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
