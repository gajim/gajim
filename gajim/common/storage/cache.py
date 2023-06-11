# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import NamedTuple

import json
import logging
import sqlite3
import time
from collections import defaultdict
from collections import namedtuple

from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import RosterItem

from gajim.common import configpaths
from gajim.common.storage.base import Encoder
from gajim.common.storage.base import json_decoder
from gajim.common.storage.base import SqliteStorage
from gajim.common.storage.base import timeit

ContactCacheDictT = dict[tuple[str, JID], dict[str, Any]]

CURRENT_USER_VERSION = 10

CACHE_SQL_STATEMENT = '''
    CREATE TABLE caps_cache (
            hash_method TEXT,
            hash TEXT,
            data TEXT,
            last_seen INTEGER
    );
    CREATE TABLE last_seen_disco_info(
            jid TEXT PRIMARY KEY UNIQUE,
            disco_info TEXT,
            last_seen INTEGER
    );
    CREATE TABLE roster(
            account TEXT PRIMARY KEY UNIQUE,
            roster TEXT
    );
    CREATE TABLE muc(
            account TEXT,
            jid TEXT,
            avatar TEXT,
            PRIMARY KEY (account, jid)
    );
    CREATE TABLE contact(
            account TEXT,
            jid TEXT,
            avatar TEXT,
            avatar_ts INTEGER,
            nickname TEXT,
            nickname_ts INTEGER,
            PRIMARY KEY (account, jid)
    );
    CREATE TABLE unread(
            account TEXT,
            jid TEXT,
            count INTEGER,
            message_id TEXT,
            timestamp INTEGER,
            PRIMARY KEY (account, jid)
    );

    CREATE INDEX idx_unread ON unread(account, jid);
    CREATE INDEX idx_contact ON contact(jid);
    CREATE INDEX idx_muc ON muc(jid);

    PRAGMA user_version=%s;
    ''' % CURRENT_USER_VERSION

log = logging.getLogger('gajim.c.storage.cache')


class UnreadTableRow(NamedTuple):
    account: str
    jid: JID
    count: int  # pyright: ignore
    message_id: str
    timestamp: float


class CacheStorage(SqliteStorage):
    def __init__(self, in_memory: bool = False):
        path = None if in_memory else configpaths.get('CACHE_DB')
        SqliteStorage.__init__(self,
                               log,
                               path,
                               CACHE_SQL_STATEMENT)

        self._entity_caps_cache: dict[tuple[str, str], DiscoInfo] = {}
        self._disco_info_cache: dict[JID, DiscoInfo] = {}
        self._muc_cache: ContactCacheDictT = defaultdict(dict)
        self._contact_cache: ContactCacheDictT = defaultdict(dict)

    def init(self, **kwargs: Any) -> None:
        SqliteStorage.init(self,
                           detect_types=sqlite3.PARSE_COLNAMES)
        self._set_journal_mode('WAL')
        self._con.row_factory = self._namedtuple_factory

        self._fill_disco_info_cache()
        self._clean_caps_table()
        self._load_caps_data()

    @staticmethod
    def _namedtuple_factory(cursor: sqlite3.Cursor,
                            row: tuple[Any, ...]) -> NamedTuple:

        assert cursor.description is not None
        fields = [col[0] for col in cursor.description]
        Row = namedtuple('Row', fields)  # pyright: ignore
        return Row(*row)

    def _migrate(self) -> None:
        try:
            user_version = self.user_version
        except sqlite3.DatabaseError as error:
            log.error('Database error: %s', error)
            self._reinit_storage()
            return

        if user_version > CURRENT_USER_VERSION:
            # Gajim was downgraded, reinit the storage
            self._reinit_storage()
            return

        if user_version < 10:
            self._reinit_storage()
            return

    @timeit
    def _load_caps_data(self) -> None:
        rows = self._con.execute(
            'SELECT hash_method, hash, data as "data [disco_info]" '
            'FROM caps_cache')

        for row in rows:
            self._entity_caps_cache[(row.hash_method, row.hash)] = row.data

    @timeit
    def add_caps_entry(self,
                       jid: JID,
                       hash_method: str,
                       hash_: str,
                       caps_data: DiscoInfo) -> None:
        self._entity_caps_cache[(hash_method, hash_)] = caps_data

        self._disco_info_cache[jid] = caps_data

        self._con.execute('''
            INSERT INTO caps_cache (hash_method, hash, data, last_seen)
            VALUES (?, ?, ?, ?)
            ''', (hash_method, hash_, caps_data, int(time.time())))
        self._delayed_commit()

    def get_caps_entry(self, hash_method: str, hash_: str):
        return self._entity_caps_cache.get((hash_method, hash_))

    @timeit
    def update_caps_time(self, method: str, hash_: str) -> None:
        sql = '''UPDATE caps_cache SET last_seen = ?
                 WHERE hash_method = ? and hash = ?'''
        self._con.execute(sql, (int(time.time()), method, hash_))
        self._delayed_commit()

    @timeit
    def _clean_caps_table(self) -> None:
        '''
        Remove caps which was not seen for 3 months
        '''
        timestamp = int(time.time()) - 3 * 30 * 24 * 3600
        self._con.execute('DELETE FROM caps_cache WHERE last_seen < ?',
                          (timestamp,))
        self._delayed_commit()

    @timeit
    def _fill_disco_info_cache(self) -> None:
        sql = '''SELECT disco_info as "disco_info [disco_info]",
                 jid as "jid [jid]", last_seen FROM
                 last_seen_disco_info'''
        rows = self._con.execute(sql).fetchall()
        for row in rows:
            disco_info = row.disco_info._replace(timestamp=row.last_seen)
            self._disco_info_cache[row.jid] = disco_info
        log.info('%d DiscoInfo entries loaded', len(rows))

    def get_last_disco_info(self,
                            jid: JID,
                            max_age: int = 0) -> DiscoInfo | None:
        '''
        Get last disco info from jid

        :param jid:         The jid

        :param max_age:     max age in seconds of the DiscoInfo record

        '''

        disco_info = self._disco_info_cache.get(jid)
        if disco_info is not None:
            max_timestamp = time.time() - max_age if max_age else 0
            if max_timestamp > disco_info.timestamp:  # pyright: ignore
                return None
        return disco_info

    @timeit
    def set_last_disco_info(self,
                            jid: JID,
                            disco_info: DiscoInfo,
                            cache_only: bool = False) -> None:
        '''
        Get last disco info from jid

        :param jid:          The jid

        :param disco_info:   A DiscoInfo object

        '''

        log.info('Save disco info from %s', jid)

        if cache_only:
            self._disco_info_cache[jid] = disco_info
            return

        disco_exists = self.get_last_disco_info(jid) is not None
        if disco_exists:
            sql = '''UPDATE last_seen_disco_info SET
                     disco_info = ?, last_seen = ?
                     WHERE jid = ?'''

            self._con.execute(sql, (disco_info, disco_info.timestamp, str(jid)))

        else:
            sql = '''INSERT INTO last_seen_disco_info
                     (jid, disco_info, last_seen)
                     VALUES (?, ?, ?)'''

            self._con.execute(sql, (str(jid), disco_info, disco_info.timestamp))

        self._disco_info_cache[jid] = disco_info
        self._delayed_commit()

    @timeit
    def store_roster(self, account: str, roster: dict[JID, RosterItem]) -> None:
        serialized = json.dumps(list(roster.values()), cls=Encoder)

        insert_sql = 'INSERT INTO roster(account, roster) VALUES(?, ?)'
        update_sql = 'UPDATE roster SET roster = ? WHERE account = ?'

        try:
            self._con.execute(insert_sql, (account, serialized))
        except sqlite3.IntegrityError:
            self._con.execute(update_sql, (serialized, account))

        self._delayed_commit()

    @timeit
    def load_roster(self, account: str) -> dict[JID, RosterItem] | None:
        select_sql = 'SELECT roster FROM roster WHERE account = ?'
        result = self._con.execute(select_sql, (account,)).fetchone()
        if result is None:
            return None

        roster: dict[JID, RosterItem] = {}
        data = json.loads(result.roster, object_hook=json_decoder)
        for item in data:
            roster[item.jid] = item
        return roster

    @timeit
    def remove_roster(self, account: str) -> None:
        delete_sql = 'DELETE FROM roster WHERE account = ?'
        self._con.execute(delete_sql, (account,))
        self._commit()

    @timeit
    def set_muc(self,
                account: str,
                jid: JID,
                prop: str,
                value: Any
                ) -> None:

        sql = f'''INSERT INTO muc (account, jid, {prop}) VALUES (?, ?, ?)'''

        try:
            self._con.execute(sql, (account, jid, value))
        except sqlite3.IntegrityError:
            sql = f'UPDATE muc SET {prop} = ? WHERE account = ? AND jid = ?'
            self._con.execute(sql, (value, account, jid))

        self._muc_cache[(account, jid)][prop] = value

        self._delayed_commit()

    @timeit
    def get_muc(self, account: str, jid: JID, prop: str) -> Any:
        try:
            return self._muc_cache[(account, jid)][prop]
        except KeyError:
            sql = f'''SELECT jid as "jid [jid]", {prop}
                      FROM muc WHERE account = ? AND jid = ?'''
            row = self._con.execute(sql, (account, jid)).fetchone()
            value = None if row is None else getattr(row, prop)

            self._muc_cache[(account, jid)][prop] = value
            return value

    @timeit
    def set_contact(self,
                    account: str,
                    jid: JID,
                    prop: str,
                    value: Any
                    ) -> None:

        sql = f'''INSERT INTO contact (account, jid, {prop}, {prop}_ts)
                  VALUES (?, ?, ?, ?)'''

        prop_ts = time.time()

        try:
            self._con.execute(sql, (account, jid, value, prop_ts))
        except sqlite3.IntegrityError:
            sql = f'''UPDATE contact SET {prop} = ?, {prop}_ts = ?
                      WHERE account = ? AND jid = ?'''
            self._con.execute(sql, (value, prop_ts, account, jid))

        self._contact_cache[(account, jid)][prop] = (value, prop_ts)

        self._delayed_commit()

    def get_contact(self, account: str, jid: JID, prop: str) -> Any:
        try:
            value, prop_ts = self._contact_cache[(account, jid)][prop]
        except KeyError:
            sql = f'''SELECT jid as "jid [jid]", {prop}, {prop}_ts
                      FROM contact WHERE account = ? AND jid = ?'''
            row = self._con.execute(sql, (account, jid)).fetchone()
            value = None if row is None else getattr(row, prop)
            prop_ts = 0 if row is None else getattr(row, f'{prop}_ts')

            self._contact_cache[(account, jid)][prop] = (value, prop_ts)
            return value

        else:
            # TODO: Expire entries
            return value

    @timeit
    def get_unread(self) -> list[UnreadTableRow]:
        sql = 'SELECT * FROM unread'
        return self._con.execute(sql).fetchall()

    @timeit
    def get_unread_count(self, account: str, jid: JID) -> int | None:
        sql = '''SELECT count, message_id, timestamp FROM unread
                 WHERE account = ? AND jid = ?'''
        return self._con.execute(sql, (account, jid)).fetchone()

    @timeit
    def set_unread_count(self,
                         account: str,
                         jid: JID,
                         count: int,
                         message_id: str,
                         timestamp: float) -> None:

        if self.get_unread_count(account, jid) is not None:
            self.update_unread_count(account, jid, count)
        else:
            sql = '''INSERT INTO unread
                     (account, jid, count, message_id, timestamp)
                     VALUES (?, ?, ?, ?, ?)'''
            self._con.execute(sql, (account, jid, count, message_id, timestamp))
            self._delayed_commit()

    @timeit
    def update_unread_count(self, account: str, jid: JID, count: int) -> None:
        sql = 'UPDATE unread SET count = ? WHERE account = ? AND jid = ?'
        self._con.execute(sql, (count, account, jid))
        self._delayed_commit()

    @timeit
    def reset_unread_count(self, account: str, jid: JID) -> None:
        sql = 'DELETE FROM unread WHERE account = ? AND jid = ?'
        self._con.execute(sql, (account, jid))
        self._delayed_commit()
