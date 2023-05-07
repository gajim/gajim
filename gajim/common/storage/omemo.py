# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
# Copyright (C) 2015 Tarek Galal <tare2.galal@gmail.com>
#
# This file is part of OMEMO Gajim Plugin.
#
# OMEMO Gajim Plugin is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# OMEMO Gajim Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OMEMO Gajim Plugin. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import NamedTuple
from typing import Optional

import sqlite3
import time
from collections import namedtuple
from pathlib import Path

from omemo_dr.const import OMEMOTrust
from omemo_dr.ecc.djbec import CurvePublicKey
from omemo_dr.ecc.djbec import DjbECPrivateKey
from omemo_dr.exceptions import InvalidKeyIdException
from omemo_dr.identitykey import IdentityKey
from omemo_dr.identitykeypair import IdentityKeyPair
from omemo_dr.state.prekeyrecord import PreKeyRecord
from omemo_dr.state.sessionrecord import SessionRecord
from omemo_dr.state.signedprekeyrecord import SignedPreKeyRecord
from omemo_dr.state.store import Store
from omemo_dr.structs import IdentityInfo
from omemo_dr.util.medium import Medium

from gajim.common import app
from gajim.common.modules.util import LogAdapter


def _convert_identity_key(key: bytes) -> Optional[IdentityKey]:
    if not key:
        return
    return IdentityKey(CurvePublicKey(key[1:]))


def _convert_record(record: bytes) -> SessionRecord:
    return SessionRecord(serialized=record)


sqlite3.register_converter('pk', _convert_identity_key)
sqlite3.register_converter('session_record', _convert_record)


class OMEMOStorage(Store):
    def __init__(self, account: str, db_path: Path, log: LogAdapter) -> None:
        self._log = log
        self._account = account
        self._con = sqlite3.connect(db_path,
                                    detect_types=sqlite3.PARSE_COLNAMES)
        self._con.row_factory = self._namedtuple_factory
        self.create_db()
        self.migrate_db()

        self._con.execute('PRAGMA secure_delete=1')
        self._con.execute('PRAGMA synchronous=NORMAL;')
        mode = self._con.execute('PRAGMA journal_mode;').fetchone()[0]

        # WAL is a persistent DB mode, don't override it if user has set it
        if mode != 'wal':
            self._con.execute('PRAGMA journal_mode=MEMORY;')
        self._con.commit()

    def _is_blind_trust_enabled(self) -> bool:
        return app.settings.get_account_setting(self._account,
                                                'omemo_blind_trust')

    @staticmethod
    def _namedtuple_factory(cursor: sqlite3.Cursor,
                            row: tuple[Any, ...]
                            ) -> NamedTuple:

        fields: list[str] = []
        for col in cursor.description:
            if col[0] == '_id':
                fields.append('id')
            elif 'strftime' in col[0]:
                fields.append('formated_time')
            elif 'MAX' in col[0] or 'COUNT' in col[0]:
                col_name = col[0].replace('(', '_')
                col_name = col_name.replace(')', '')
                fields.append(col_name.lower())
            else:
                fields.append(col[0])
        return namedtuple('Row', fields)(*row)  # pyright: ignore

    def user_version(self) -> int:
        return self._con.execute('PRAGMA user_version').fetchone()[0]

    def create_db(self) -> None:
        if self.user_version() == 0:

            create_tables = '''
                CREATE TABLE IF NOT EXISTS secret (
                    device_id INTEGER, public_key BLOB, private_key BLOB);

                CREATE TABLE IF NOT EXISTS identities (
                    _id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_id TEXT,
                    registration_id INTEGER, public_key BLOB,
                    timestamp INTEGER, trust INTEGER,
                    shown INTEGER DEFAULT 0);

                CREATE UNIQUE INDEX IF NOT EXISTS
                    public_key_index ON identities (public_key, recipient_id);

                CREATE TABLE IF NOT EXISTS prekeys(
                    _id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prekey_id INTEGER UNIQUE, sent_to_server BOOLEAN,
                    record BLOB);

                CREATE TABLE IF NOT EXISTS signed_prekeys (
                    _id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prekey_id INTEGER UNIQUE,
                    timestamp NUMERIC DEFAULT CURRENT_TIMESTAMP, record BLOB);

                CREATE TABLE IF NOT EXISTS sessions (
                    _id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient_id TEXT, device_id INTEGER,
                    record BLOB, timestamp INTEGER, active INTEGER DEFAULT 1,
                    UNIQUE(recipient_id, device_id));

                '''

            create_db_sql = '''
                BEGIN TRANSACTION;
                %s
                PRAGMA user_version=12;
                END TRANSACTION;
                ''' % (create_tables)
            self._con.executescript(create_db_sql)

    def migrate_db(self) -> None:
        ''' Migrates the DB
        '''

        # Find all double entries and delete them
        if self.user_version() < 2:
            delete_dupes = ''' DELETE FROM identities WHERE _id not in (
                                SELECT MIN(_id)
                                FROM identities
                                GROUP BY
                                recipient_id, public_key
                                );
                            '''

            self._con.executescript(
                ''' BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=2;
                    END TRANSACTION;
                ''' % (delete_dupes))

        if self.user_version() < 3:
            # Create a UNIQUE INDEX so every public key/recipient_id tuple
            # can only be once in the db
            add_index = ''' CREATE UNIQUE INDEX IF NOT EXISTS
                            public_key_index
                            ON identities (public_key, recipient_id);
                        '''

            self._con.executescript(
                ''' BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=3;
                    END TRANSACTION;
                ''' % (add_index))

        if self.user_version() < 4:
            # Adds column 'active' to the sessions table
            add_active = ''' ALTER TABLE sessions
                             ADD COLUMN active INTEGER DEFAULT 1;
                         '''

            self._con.executescript(
                ''' BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=4;
                    END TRANSACTION;
                ''' % (add_active))

        if self.user_version() < 5:
            # Adds DEFAULT Timestamp
            add_timestamp = '''
                DROP TABLE signed_prekeys;
                CREATE TABLE IF NOT EXISTS signed_prekeys (
                    _id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prekey_id INTEGER UNIQUE,
                    timestamp NUMERIC DEFAULT CURRENT_TIMESTAMP, record BLOB);
                ALTER TABLE identities ADD COLUMN shown INTEGER DEFAULT 0;
                UPDATE identities SET shown = 1;
            '''

            self._con.executescript(
                ''' BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=5;
                    END TRANSACTION;
                ''' % (add_timestamp))

        if self.user_version() < 6:
            # Move secret data into own table
            # We add +1 to registration id because we did that in other code in
            # earlier versions. On this migration we correct this mistake now.
            move = '''
                CREATE TABLE IF NOT EXISTS secret (
                    device_id INTEGER, public_key BLOB, private_key BLOB);
                INSERT INTO secret (device_id, public_key, private_key)
                SELECT registration_id + 1, public_key, private_key
                FROM identities
                WHERE recipient_id = -1;
            '''

            self._con.executescript(
                ''' BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=6;
                    END TRANSACTION;
                ''' % move)

        if self.user_version() < 7:
            # Convert old device ids to integer
            convert = '''
                UPDATE secret SET device_id = device_id % 2147483646;
            '''

            self._con.executescript(
                ''' BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=7;
                    END TRANSACTION;
                ''' % convert)

        if self.user_version() < 8:
            # Sanitize invalid BLOBs from the python2 days
            query_keys = '''SELECT recipient_id,
                            registration_id,
                            CAST(public_key as BLOB) as public_key,
                            CAST(private_key as BLOB) as private_key,
                            timestamp, trust, shown
                            FROM identities'''
            rows = self._con.execute(query_keys).fetchall()

            delete = 'DELETE FROM identities'
            self._con.execute(delete)

            insert = '''INSERT INTO identities (
                        recipient_id, registration_id, public_key, private_key,
                        timestamp, trust, shown)
                        VALUES (?, ?, ?, ?, ?, ?, ?)'''
            for row in rows:
                try:
                    self._con.execute(insert, row)
                except Exception as error:
                    self._log.warning(error)
            self._con.execute('PRAGMA user_version=8')
            self._con.commit()

        if self.user_version() < 9:
            # Sanitize invalid BLOBs from the python2 days
            query_keys = '''SELECT device_id,
                            CAST(public_key as BLOB) as public_key,
                            CAST(private_key as BLOB) as private_key
                            FROM secret'''
            rows = self._con.execute(query_keys).fetchall()

            delete = 'DELETE FROM secret'
            self._con.execute(delete)

            insert = '''INSERT INTO secret (device_id, public_key, private_key)
                        VALUES (?, ?, ?)'''
            for row in rows:
                try:
                    self._con.execute(insert, row)
                except Exception as error:
                    self._log.warning(error)
            self._con.execute('PRAGMA user_version=9')
            self._con.commit()

        if self.user_version() < 10:
            # Sanitize invalid BLOBs from the python2 days
            query_keys = '''SELECT _id,
                            recipient_id,
                            device_id,
                            CAST(record as BLOB) as record,
                            timestamp,
                            active
                            FROM sessions'''
            rows = self._con.execute(query_keys).fetchall()

            delete = 'DELETE FROM sessions'
            self._con.execute(delete)

            insert = '''INSERT INTO sessions (_id, recipient_id, device_id,
                                              record, timestamp, active)
                        VALUES (?, ?, ?, ?, ?, ?)'''
            for row in rows:
                try:
                    self._con.execute(insert, row)
                except Exception as error:
                    self._log.warning(error)
            self._con.execute('PRAGMA user_version=10')
            self._con.commit()

        if self.user_version() < 11:
            # Sanitize invalid BLOBs from the python2 days
            query_keys = '''SELECT _id,
                            prekey_id,
                            sent_to_server,
                            CAST(record as BLOB) as record
                            FROM prekeys'''
            rows = self._con.execute(query_keys).fetchall()

            delete = 'DELETE FROM prekeys'
            self._con.execute(delete)

            insert = '''INSERT INTO prekeys (
                        _id, prekey_id, sent_to_server, record)
                        VALUES (?, ?, ?, ?)'''
            for row in rows:
                try:
                    self._con.execute(insert, row)
                except Exception as error:
                    self._log.warning(error)
            self._con.execute('PRAGMA user_version=11')
            self._con.commit()

        if self.user_version() < 12:
            # Sanitize invalid BLOBs from the python2 days
            query_keys = '''SELECT _id,
                            prekey_id,
                            timestamp,
                            CAST(record as BLOB) as record
                            FROM signed_prekeys'''
            rows = self._con.execute(query_keys).fetchall()

            delete = 'DELETE FROM signed_prekeys'
            self._con.execute(delete)

            insert = '''INSERT INTO signed_prekeys (
                        _id, prekey_id, timestamp, record)
                        VALUES (?, ?, ?, ?)'''
            for row in rows:
                try:
                    self._con.execute(insert, row)
                except Exception as error:
                    self._log.warning(error)
            self._con.execute('PRAGMA user_version=12')
            self._con.commit()

    def load_signed_pre_key(self, signed_pre_key_id: int) -> SignedPreKeyRecord:
        query = 'SELECT record FROM signed_prekeys WHERE prekey_id = ?'
        result = self._con.execute(query, (signed_pre_key_id, )).fetchone()
        if result is None:
            raise InvalidKeyIdException('No such signedprekeyrecord! %s ' %
                                        signed_pre_key_id)
        return SignedPreKeyRecord.from_bytes(result.record)

    def load_signed_pre_keys(self) -> list[SignedPreKeyRecord]:
        query = 'SELECT record FROM signed_prekeys'
        results = self._con.execute(query).fetchall()
        return [SignedPreKeyRecord.from_bytes(row.record) for row in results]

    def store_signed_pre_key(self,
                             signed_pre_key_id: int,
                             signed_pre_key_record: SignedPreKeyRecord
                             ) -> None:

        query = 'INSERT INTO signed_prekeys (prekey_id, record) VALUES(?,?)'
        self._con.execute(query, (signed_pre_key_id,
                                  signed_pre_key_record.serialize()))
        self._con.commit()

    def contains_signed_pre_key(self, signed_pre_key_id: int) -> bool:
        query = 'SELECT record FROM signed_prekeys WHERE prekey_id = ?'
        result = self._con.execute(query, (signed_pre_key_id,)).fetchone()
        return result is not None

    def remove_signed_pre_key(self, signed_pre_key_id: int) -> None:
        query = 'DELETE FROM signed_prekeys WHERE prekey_id = ?'
        self._con.execute(query, (signed_pre_key_id,))
        self._con.commit()

    def get_next_signed_pre_key_id(self) -> int:
        result = self.get_current_signed_pre_key_id()
        return (result % (Medium.MAX_VALUE - 1)) + 1

    def get_current_signed_pre_key_id(self) -> int:
        query = 'SELECT MAX(prekey_id) FROM signed_prekeys'
        result = self._con.execute(query).fetchone()
        assert result is not None
        return result.max_prekey_id

    def get_signed_pre_key_timestamp(self, signed_pre_key_id: int) -> int:
        query = '''SELECT strftime('%s', timestamp) FROM
                   signed_prekeys WHERE prekey_id = ?'''

        result = self._con.execute(query, (signed_pre_key_id,)).fetchone()
        if result is None:
            raise InvalidKeyIdException('No such signedprekeyrecord! %s' %
                                        signed_pre_key_id)

        return result.formated_time

    def remove_old_signed_pre_keys(self, timestamp: int) -> None:
        query = '''DELETE FROM signed_prekeys
                   WHERE timestamp < datetime(?, "unixepoch")'''
        self._con.execute(query, (timestamp,))
        self._con.commit()

    def load_session(self, recipient_id: str, device_id: int) -> SessionRecord:
        query = '''SELECT record as "record [session_record]"
                   FROM sessions WHERE recipient_id = ? AND device_id = ?'''
        result = self._con.execute(query, (recipient_id, device_id)).fetchone()
        return result.record if result is not None else SessionRecord()

    def get_jid_from_device(self, device_id: int) -> Optional[str]:
        query = '''SELECT recipient_id
                   FROM sessions WHERE device_id = ?'''
        result = self._con.execute(query, (device_id, )).fetchone()
        return result.recipient_id if result is not None else None

    def get_active_device_tuples(self):
        query = '''SELECT recipient_id, device_id
                   FROM sessions WHERE active = 1'''
        return self._con.execute(query).fetchall()

    def store_session(self,
                      recipient_id: str,
                      device_id: int,
                      session_record: SessionRecord
                      ) -> None:

        query = '''INSERT INTO sessions(recipient_id, device_id, record)
                   VALUES(?,?,?)'''
        try:
            self._con.execute(query, (recipient_id,
                                      device_id,
                                      session_record.serialize()))
        except sqlite3.IntegrityError:
            query = '''UPDATE sessions SET record = ?
                       WHERE recipient_id = ? AND device_id = ?'''
            self._con.execute(query, (session_record.serialize(),
                                      recipient_id,
                                      device_id))

        self._con.commit()

    def contains_session(self, recipient_id: str, device_id: int) -> bool:
        query = '''SELECT record FROM sessions
                   WHERE recipient_id = ? AND device_id = ?'''
        result = self._con.execute(query, (recipient_id, device_id)).fetchone()
        return result is not None

    def delete_session(self, recipient_id: str, device_id: int) -> None:
        self._log.info('Delete session for %s %s', recipient_id, device_id)
        query = 'DELETE FROM sessions WHERE recipient_id = ? AND device_id = ?'
        self._con.execute(query, (recipient_id, device_id))
        self._con.commit()

    def delete_all_sessions(self, recipient_id: str) -> None:
        query = 'DELETE FROM sessions WHERE recipient_id = ?'
        self._con.execute(query, (recipient_id,))
        self._con.commit()

    def get_identity_infos(self,
                           recipient_ids: str | list[str]
                           ) -> list[IdentityInfo]:

        if isinstance(recipient_ids, str):
            recipient_ids = [recipient_ids]

        query = '''SELECT recipient_id,
                          public_key as "public_key [pk]",
                          trust,
                          timestamp
                   FROM identities
                   WHERE recipient_id IN ({})'''.format(
                    ', '.join(['?'] * len(recipient_ids)))
        i_results = self._con.execute(query, recipient_ids).fetchall()

        query = '''SELECT device_id,
                          record as "record [session_record]",
                          active
                   FROM sessions WHERE recipient_id IN ({})'''.format(
                    ', '.join(['?'] * len(recipient_ids)))
        s_results = self._con.execute(query, recipient_ids).fetchall()

        sessions: dict[IdentityKey, Any] = {}
        for s_result in s_results:
            if s_result.record.is_fresh():
                continue
            ik = s_result.record.get_session_state().get_remote_identity_key()
            sessions[ik] = s_result

        identity_infos: list[IdentityInfo] = []
        for i_result in i_results:
            session = sessions.get(i_result.public_key)
            if session is None:
                continue

            info = IdentityInfo(active=session.active,
                                address=i_result.recipient_id,
                                device_id=session.device_id,
                                public_key=i_result.public_key,
                                label='',
                                last_seen=i_result.timestamp,
                                trust=OMEMOTrust(i_result.trust))
            identity_infos.append(info)

        return identity_infos

    def set_active_state(self, address: str, devicelist: list[int]) -> None:
        query = '''
        UPDATE sessions SET active = 1
        WHERE recipient_id = ? AND device_id IN ({})'''.format(
            ', '.join(['?'] * len(devicelist)))
        self._con.execute(query, (address,) + tuple(devicelist))

        query = '''
        UPDATE sessions SET active = 0
        WHERE recipient_id = ? AND device_id NOT IN ({})'''.format(
            ', '.join(['?'] * len(devicelist)))
        self._con.execute(query, (address,) + tuple(devicelist))
        self._con.commit()

    def set_inactive(self, address: str, device_id: int) -> None:
        query = '''UPDATE sessions SET active = 0
                   WHERE recipient_id = ? AND device_id = ?'''
        self._con.execute(query, (address, device_id))
        self._con.commit()

    def get_inactive_sessions_keys(self,
                                   recipient_id: str
                                   ) -> list[IdentityKey]:

        query = '''SELECT record as "record [session_record]" FROM sessions
                   WHERE active = 0 AND recipient_id = ?'''
        results = self._con.execute(query, (recipient_id,)).fetchall()

        keys: list[IdentityKey] = []
        for result in results:
            key = result.record.get_session_state().get_remote_identity_key()
            keys.append(IdentityKey(key.get_public_key()))
        return keys

    def load_pre_key(self, pre_key_id: int) -> PreKeyRecord:
        query = '''SELECT record FROM prekeys WHERE prekey_id = ?'''

        result = self._con.execute(query, (pre_key_id,)).fetchone()
        if result is None:
            raise Exception('No such prekeyRecord!')
        return PreKeyRecord.from_bytes(result.record)

    def load_pending_pre_keys(self) -> list[PreKeyRecord]:
        query = '''SELECT record FROM prekeys'''
        result = self._con.execute(query).fetchall()
        return [PreKeyRecord.from_bytes(row.record) for row in result]

    def store_pre_key(self,
                      pre_key_id: int,
                      pre_key_record: PreKeyRecord
                      ) -> None:
        query = 'INSERT INTO prekeys (prekey_id, record) VALUES(?,?)'
        self._con.execute(query, (pre_key_id, pre_key_record.serialize()))
        self._con.commit()

    def contains_pre_key(self, pre_key_id: int) -> bool:
        query = 'SELECT record FROM prekeys WHERE prekey_id = ?'
        result = self._con.execute(query, (pre_key_id,)).fetchone()
        return result is not None

    def remove_pre_key(self, pre_key_id: int) -> None:
        query = 'DELETE FROM prekeys WHERE prekey_id = ?'
        self._con.execute(query, (pre_key_id,))
        self._con.commit()

    def get_current_pre_key_id(self) -> Optional[int]:
        query = 'SELECT MAX(prekey_id) FROM prekeys'
        result = self._con.execute(query).fetchone()
        return result.max_prekey_id if result is not None else None

    def get_pre_key_count(self) -> int:
        query = 'SELECT COUNT(prekey_id) FROM prekeys'
        return self._con.execute(query).fetchone().count_prekey_id

    def get_identity_key_pair(self) -> IdentityKeyPair:
        query = '''SELECT public_key as "public_key [pk]", private_key
                   FROM secret LIMIT 1'''
        result = self._con.execute(query).fetchone()

        return IdentityKeyPair.new(result.public_key,
                                   DjbECPrivateKey(result.private_key))

    def get_our_device_id(self) -> int:
        query = 'SELECT device_id FROM secret LIMIT 1'
        result = self._con.execute(query).fetchone()
        assert result is not None
        return result.device_id

    def set_our_identity(self,
                         device_id: int,
                         identity_key_pair: IdentityKeyPair
                         ) -> None:

        query = 'SELECT * FROM secret'
        result = self._con.execute(query).fetchone()
        if result is not None:
            self._log.error('Trying to save secret key into '
                            'non-empty secret table')
            return

        query = '''INSERT INTO secret(device_id, public_key, private_key)
                   VALUES(?, ?, ?)'''

        public_key = identity_key_pair.get_public_key().get_public_key().\
            serialize()
        private_key = identity_key_pair.get_private_key().serialize()
        self._con.execute(query, (device_id, public_key, private_key))
        self._con.commit()

    def save_identity(self,
                      recipient_id: str,
                      identity_key: IdentityKey
                      ) -> None:
        query = '''INSERT INTO identities
                   (recipient_id, public_key, trust, shown)
                   VALUES(?, ?, ?, ?)'''
        if not self.contains_identity(recipient_id, identity_key):
            trust = self.get_default_trust(recipient_id)
            self._con.execute(query, (recipient_id,
                                      identity_key.get_public_key().serialize(),
                                      trust,
                                      1 if trust == OMEMOTrust.BLIND else 0))
            self._con.commit()

    def contains_identity(self,
                          recipient_id: str,
                          identity_key: IdentityKey
                          ) -> bool:

        query = '''SELECT * FROM identities WHERE recipient_id = ?
                   AND public_key = ?'''

        public_key = identity_key.get_public_key().serialize()
        result = self._con.execute(query, (recipient_id,
                                           public_key)).fetchone()

        return result is not None

    def delete_identity(self,
                        recipient_id: str,
                        identity_key: IdentityKey
                        ) -> None:

        query = '''DELETE FROM identities
                   WHERE recipient_id = ? AND public_key = ?'''
        public_key = identity_key.get_public_key().serialize()
        self._con.execute(query, (recipient_id, public_key))
        self._con.commit()

    def is_trusted_identity(self,
                            recipient_id: str,
                            identity_key: IdentityKey
                            ) -> bool:

        return True

    def get_trust_for_identity(self,
                               recipient_id: str,
                               identity_key: IdentityKey
                               ) -> Optional[OMEMOTrust]:

        query = '''SELECT trust FROM identities WHERE recipient_id = ?
                   AND public_key = ?'''
        public_key = identity_key.get_public_key().serialize()
        result = self._con.execute(query, (recipient_id, public_key)).fetchone()
        return result.trust if result is not None else None

    def get_fingerprints(self, jid: str):
        query = '''SELECT recipient_id,
                          public_key as "public_key [pk]",
                          trust,
                          timestamp
                   FROM identities
                   WHERE recipient_id = ? ORDER BY trust ASC'''
        return self._con.execute(query, (jid,)).fetchall()

    def get_muc_fingerprints(self, jids: list[str]):
        query = '''
            SELECT recipient_id,
                   public_key as "public_key [pk]",
                   trust,
                   timestamp
            FROM identities
            WHERE recipient_id IN ({}) ORDER BY trust ASC
            '''.format(', '.join(['?'] * len(jids)))

        return self._con.execute(query, jids).fetchall()

    def get_default_trust(self, jid: str) -> OMEMOTrust:
        if not self._is_blind_trust_enabled():
            return OMEMOTrust.UNDECIDED

        query = '''SELECT * FROM identities
                   WHERE recipient_id = ? AND trust IN (0, 1)'''
        result = self._con.execute(query, (jid,)).fetchone()
        if result is None:
            return OMEMOTrust.BLIND
        return OMEMOTrust.UNDECIDED

    def set_trust(self,
                  recipient_id: str,
                  identity_key: IdentityKey,
                  trust: OMEMOTrust
                  ) -> None:

        query = '''UPDATE identities SET trust = ? WHERE public_key = ?
                   AND recipient_id = ?'''
        public_key = identity_key.get_public_key().serialize()
        self._con.execute(query, (trust, public_key, recipient_id))
        self._con.commit()

    def is_trusted(self, recipient_id: str, device_id: int) -> bool:
        record = self.load_session(recipient_id, device_id)
        if record.is_fresh():
            return False
        identity_key = record.get_session_state().get_remote_identity_key()
        return self.get_trust_for_identity(
            recipient_id, identity_key) in (OMEMOTrust.VERIFIED,
                                            OMEMOTrust.BLIND)

    def get_identity_last_seen(self,
                               recipient_id: str,
                               identity_key: IdentityKey
                               ) -> Optional[int]:

        serialized = identity_key.get_public_key().serialize()
        query = '''SELECT timestamp FROM identities
                   WHERE recipient_id = ? AND public_key = ?'''
        result = self._con.execute(query, (recipient_id,
                                           serialized)).fetchone()
        return result.timestamp if result is not None else None

    def set_identity_last_seen(self,
                               recipient_id: str,
                               identity_key: IdentityKey
                               ) -> None:

        timestamp = int(time.time())
        serialized = identity_key.get_public_key().serialize()
        self._log.info('Set last seen for %s %s', recipient_id, timestamp)
        query = '''UPDATE identities SET timestamp = ?
                   WHERE recipient_id = ? AND public_key = ?'''
        self._con.execute(query, (timestamp, recipient_id, serialized))
        self._con.commit()

    def get_unacknowledged_count(self,
                                 recipient_id: str,
                                 device_id: int
                                 ) -> int:
        record = self.load_session(recipient_id, device_id)
        if record.is_fresh():
            return 0
        state = record.get_session_state()
        return state.get_sender_chain_key().get_index()

    def needs_init(self) -> bool:
        try:
            self.get_our_device_id()
        except AssertionError:
            return True
        return False
