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

import time
import sqlite3
from collections import namedtuple

from axolotl.state.axolotlstore import AxolotlStore
from axolotl.state.signedprekeyrecord import SignedPreKeyRecord
from axolotl.state.sessionrecord import SessionRecord
from axolotl.state.prekeyrecord import PreKeyRecord
from axolotl.invalidkeyidexception import InvalidKeyIdException
from axolotl.ecc.djbec import DjbECPrivateKey
from axolotl.ecc.djbec import DjbECPublicKey
from axolotl.identitykeypair import IdentityKeyPair
from axolotl.util.medium import Medium
from axolotl.util.keyhelper import KeyHelper

from gajim.common import app

from gajim.common.modules.util import Trust
from gajim.common.modules.util import IdentityKeyExtended
from gajim.common.modules.util import DEFAULT_PREKEY_AMOUNT


def _convert_to_string(text):
    return text.decode()


def _convert_identity_key(key):
    if not key:
        return
    return IdentityKeyExtended(DjbECPublicKey(key[1:]))


def _convert_record(record):
    return SessionRecord(serialized=record)


sqlite3.register_converter('pk', _convert_identity_key)
sqlite3.register_converter('session_record', _convert_record)


class LiteAxolotlStore(AxolotlStore):
    def __init__(self, account: str, db_path, log):
        self._log = log
        self._account = account
        self._con = sqlite3.connect(db_path,
                                    detect_types=sqlite3.PARSE_COLNAMES)
        self._con.row_factory = self._namedtuple_factory
        self.createDb()
        self.migrateDb()

        self._con.execute("PRAGMA secure_delete=1")
        self._con.execute("PRAGMA synchronous=NORMAL;")
        mode = self._con.execute("PRAGMA journal_mode;").fetchone()[0]

        # WAL is a persistent DB mode, don't override it if user has set it
        if mode != 'wal':
            self._con.execute("PRAGMA journal_mode=MEMORY;")
        self._con.commit()

        if not self.getLocalRegistrationId():
            self._log.info("Generating OMEMO keys")
            self._generate_axolotl_keys()

    def _is_blind_trust_enabled(self):
        return app.settings.get_account_setting(self._account,
                                                'omemo_blind_trust')

    @staticmethod
    def _namedtuple_factory(cursor, row):
        fields = []
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
        return namedtuple("Row", fields)(*row)

    def _generate_axolotl_keys(self):
        identity_key_pair = KeyHelper.generateIdentityKeyPair()
        registration_id = KeyHelper.getRandomSequence(2147483647)
        pre_keys = KeyHelper.generatePreKeys(
            KeyHelper.getRandomSequence(4294967296),
            DEFAULT_PREKEY_AMOUNT)
        self.storeLocalData(registration_id, identity_key_pair)

        signed_pre_key = KeyHelper.generateSignedPreKey(
            identity_key_pair, KeyHelper.getRandomSequence(65536))

        self.storeSignedPreKey(signed_pre_key.getId(), signed_pre_key)

        for pre_key in pre_keys:
            self.storePreKey(pre_key.getId(), pre_key)

    def user_version(self):
        return self._con.execute('PRAGMA user_version').fetchone()[0]

    def createDb(self):
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

            create_db_sql = """
                BEGIN TRANSACTION;
                %s
                PRAGMA user_version=12;
                END TRANSACTION;
                """ % (create_tables)
            self._con.executescript(create_db_sql)

    def migrateDb(self):
        """ Migrates the DB
        """

        # Find all double entries and delete them
        if self.user_version() < 2:
            delete_dupes = """ DELETE FROM identities WHERE _id not in (
                                SELECT MIN(_id)
                                FROM identities
                                GROUP BY
                                recipient_id, public_key
                                );
                            """

            self._con.executescript(
                """ BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=2;
                    END TRANSACTION;
                """ % (delete_dupes))

        if self.user_version() < 3:
            # Create a UNIQUE INDEX so every public key/recipient_id tuple
            # can only be once in the db
            add_index = """ CREATE UNIQUE INDEX IF NOT EXISTS
                            public_key_index
                            ON identities (public_key, recipient_id);
                        """

            self._con.executescript(
                """ BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=3;
                    END TRANSACTION;
                """ % (add_index))

        if self.user_version() < 4:
            # Adds column "active" to the sessions table
            add_active = """ ALTER TABLE sessions
                             ADD COLUMN active INTEGER DEFAULT 1;
                         """

            self._con.executescript(
                """ BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=4;
                    END TRANSACTION;
                """ % (add_active))

        if self.user_version() < 5:
            # Adds DEFAULT Timestamp
            add_timestamp = """
                DROP TABLE signed_prekeys;
                CREATE TABLE IF NOT EXISTS signed_prekeys (
                    _id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prekey_id INTEGER UNIQUE,
                    timestamp NUMERIC DEFAULT CURRENT_TIMESTAMP, record BLOB);
                ALTER TABLE identities ADD COLUMN shown INTEGER DEFAULT 0;
                UPDATE identities SET shown = 1;
            """

            self._con.executescript(
                """ BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=5;
                    END TRANSACTION;
                """ % (add_timestamp))

        if self.user_version() < 6:
            # Move secret data into own table
            # We add +1 to registration id because we did that in other code in
            # earlier versions. On this migration we correct this mistake now.
            move = """
                CREATE TABLE IF NOT EXISTS secret (
                    device_id INTEGER, public_key BLOB, private_key BLOB);
                INSERT INTO secret (device_id, public_key, private_key)
                SELECT registration_id + 1, public_key, private_key
                FROM identities
                WHERE recipient_id = -1;
            """

            self._con.executescript(
                """ BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=6;
                    END TRANSACTION;
                """ % move)

        if self.user_version() < 7:
            # Convert old device ids to integer
            convert = """
                UPDATE secret SET device_id = device_id % 2147483646;
            """

            self._con.executescript(
                """ BEGIN TRANSACTION;
                    %s
                    PRAGMA user_version=7;
                    END TRANSACTION;
                """ % convert)

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

    def loadSignedPreKey(self, signedPreKeyId):
        query = 'SELECT record FROM signed_prekeys WHERE prekey_id = ?'
        result = self._con.execute(query, (signedPreKeyId, )).fetchone()
        if result is None:
            raise InvalidKeyIdException("No such signedprekeyrecord! %s " %
                                        signedPreKeyId)
        return SignedPreKeyRecord(serialized=result.record)

    def loadSignedPreKeys(self):
        query = 'SELECT record FROM signed_prekeys'
        results = self._con.execute(query).fetchall()
        return [SignedPreKeyRecord(serialized=row.record) for row in results]

    def storeSignedPreKey(self, signedPreKeyId, signedPreKeyRecord):
        query = 'INSERT INTO signed_prekeys (prekey_id, record) VALUES(?,?)'
        self._con.execute(query, (signedPreKeyId,
                                  signedPreKeyRecord.serialize()))
        self._con.commit()

    def containsSignedPreKey(self, signedPreKeyId):
        query = 'SELECT record FROM signed_prekeys WHERE prekey_id = ?'
        result = self._con.execute(query, (signedPreKeyId,)).fetchone()
        return result is not None

    def removeSignedPreKey(self, signedPreKeyId):
        query = 'DELETE FROM signed_prekeys WHERE prekey_id = ?'
        self._con.execute(query, (signedPreKeyId,))
        self._con.commit()

    def getNextSignedPreKeyId(self):
        result = self.getCurrentSignedPreKeyId()
        if result is None:
            return 1  # StartId if no SignedPreKeys exist
        return (result % (Medium.MAX_VALUE - 1)) + 1

    def getCurrentSignedPreKeyId(self):
        query = 'SELECT MAX(prekey_id) FROM signed_prekeys'
        result = self._con.execute(query).fetchone()
        return result.max_prekey_id if result is not None else None

    def getSignedPreKeyTimestamp(self, signedPreKeyId):
        query = '''SELECT strftime('%s', timestamp) FROM
                   signed_prekeys WHERE prekey_id = ?'''

        result = self._con.execute(query, (signedPreKeyId,)).fetchone()
        if result is None:
            raise InvalidKeyIdException('No such signedprekeyrecord! %s' %
                                        signedPreKeyId)

        return result.formated_time

    def removeOldSignedPreKeys(self, timestamp):
        query = '''DELETE FROM signed_prekeys
                   WHERE timestamp < datetime(?, "unixepoch")'''
        self._con.execute(query, (timestamp,))
        self._con.commit()

    def loadSession(self, recipientId, deviceId):
        query = '''SELECT record as "record [session_record]"
                   FROM sessions WHERE recipient_id = ? AND device_id = ?'''
        result = self._con.execute(query, (recipientId, deviceId)).fetchone()
        return result.record if result is not None else SessionRecord()

    def getJidFromDevice(self, device_id):
        query = '''SELECT recipient_id
                   FROM sessions WHERE device_id = ?'''
        result = self._con.execute(query, (device_id, )).fetchone()
        return result.recipient_id if result is not None else None

    def getActiveDeviceTuples(self):
        query = '''SELECT recipient_id, device_id
                   FROM sessions WHERE active = 1'''
        return self._con.execute(query).fetchall()

    def storeSession(self, recipientId, deviceId, sessionRecord):
        query = '''INSERT INTO sessions(recipient_id, device_id, record)
                   VALUES(?,?,?)'''
        try:
            self._con.execute(query, (recipientId,
                                      deviceId,
                                      sessionRecord.serialize()))
        except sqlite3.IntegrityError:
            query = '''UPDATE sessions SET record = ?
                       WHERE recipient_id = ? AND device_id = ?'''
            self._con.execute(query, (sessionRecord.serialize(),
                                      recipientId,
                                      deviceId))

        self._con.commit()

    def containsSession(self, recipientId, deviceId):
        query = '''SELECT record FROM sessions
                   WHERE recipient_id = ? AND device_id = ?'''
        result = self._con.execute(query, (recipientId, deviceId)).fetchone()
        return result is not None

    def deleteSession(self, recipientId, deviceId):
        self._log.info('Delete session for %s %s', recipientId, deviceId)
        query = "DELETE FROM sessions WHERE recipient_id = ? AND device_id = ?"
        self._con.execute(query, (recipientId, deviceId))
        self._con.commit()

    def deleteAllSessions(self, recipientId):
        query = 'DELETE FROM sessions WHERE recipient_id = ?'
        self._con.execute(query, (recipientId,))
        self._con.commit()

    def getSessionsFromJid(self, recipientId):
        query = '''SELECT recipient_id,
                          device_id,
                          record as "record [session_record]",
                          active
                   FROM sessions WHERE recipient_id = ?'''
        return self._con.execute(query, (recipientId,)).fetchall()

    def getSessionsFromJids(self, recipientIds):
        query = '''SELECT recipient_id,
                          device_id,
                          record as "record [session_record]",
                          active
                   FROM sessions
                   WHERE recipient_id IN ({})'''.format(
                       ', '.join(['?'] * len(recipientIds)))
        return self._con.execute(query, recipientIds).fetchall()

    def setActiveState(self, jid, devicelist):
        query = '''UPDATE sessions SET active = 1
                   WHERE recipient_id = ? AND device_id IN ({})'''.format(
                       ', '.join(['?'] * len(devicelist)))
        self._con.execute(query, (jid,) + tuple(devicelist))

        query = '''UPDATE sessions SET active = 0
                   WHERE recipient_id = ? AND device_id NOT IN ({})'''.format(
                       ', '.join(['?'] * len(devicelist)))
        self._con.execute(query, (jid,) + tuple(devicelist))
        self._con.commit()

    def setInactive(self, jid, device_id):
        query = '''UPDATE sessions SET active = 0
                   WHERE recipient_id = ? AND device_id = ?'''
        self._con.execute(query, (jid, device_id))
        self._con.commit()

    def getInactiveSessionsKeys(self, recipientId):
        query = '''SELECT record as "record [session_record]" FROM sessions
                   WHERE active = 0 AND recipient_id = ?'''
        results = self._con.execute(query, (recipientId,)).fetchall()

        keys = []
        for result in results:
            key = result.record.getSessionState().getRemoteIdentityKey()
            keys.append(IdentityKeyExtended(key.getPublicKey()))
        return keys

    def loadPreKey(self, preKeyId):
        query = '''SELECT record FROM prekeys WHERE prekey_id = ?'''

        result = self._con.execute(query, (preKeyId,)).fetchone()
        if result is None:
            raise Exception("No such prekeyRecord!")
        return PreKeyRecord(serialized=result.record)

    def loadPendingPreKeys(self):
        query = '''SELECT record FROM prekeys'''
        result = self._con.execute(query).fetchall()
        return [PreKeyRecord(serialized=row.record) for row in result]

    def storePreKey(self, preKeyId, preKeyRecord):
        query = 'INSERT INTO prekeys (prekey_id, record) VALUES(?,?)'
        self._con.execute(query, (preKeyId, preKeyRecord.serialize()))
        self._con.commit()

    def containsPreKey(self, preKeyId):
        query = 'SELECT record FROM prekeys WHERE prekey_id = ?'
        result = self._con.execute(query, (preKeyId,)).fetchone()
        return result is not None

    def removePreKey(self, preKeyId):
        query = 'DELETE FROM prekeys WHERE prekey_id = ?'
        self._con.execute(query, (preKeyId,))
        self._con.commit()

    def getCurrentPreKeyId(self):
        query = 'SELECT MAX(prekey_id) FROM prekeys'
        return self._con.execute(query).fetchone().max_prekey_id

    def getPreKeyCount(self):
        query = 'SELECT COUNT(prekey_id) FROM prekeys'
        return self._con.execute(query).fetchone().count_prekey_id

    def generateNewPreKeys(self, count):
        prekey_id = self.getCurrentPreKeyId() or 0
        pre_keys = KeyHelper.generatePreKeys(prekey_id + 1, count)
        for pre_key in pre_keys:
            self.storePreKey(pre_key.getId(), pre_key)

    def getIdentityKeyPair(self):
        query = '''SELECT public_key as "public_key [pk]", private_key
                   FROM secret LIMIT 1'''
        result = self._con.execute(query).fetchone()

        return IdentityKeyPair(result.public_key,
                               DjbECPrivateKey(result.private_key))

    def getLocalRegistrationId(self):
        query = 'SELECT device_id FROM secret LIMIT 1'
        result = self._con.execute(query).fetchone()
        return result.device_id if result is not None else None

    def storeLocalData(self, device_id, identityKeyPair):
        query = 'SELECT * FROM secret'
        result = self._con.execute(query).fetchone()
        if result is not None:
            self._log.error('Trying to save secret key into '
                            'non-empty secret table')
            return

        query = '''INSERT INTO secret(device_id, public_key, private_key)
                   VALUES(?, ?, ?)'''

        public_key = identityKeyPair.getPublicKey().getPublicKey().serialize()
        private_key = identityKeyPair.getPrivateKey().serialize()
        self._con.execute(query, (device_id, public_key, private_key))
        self._con.commit()

    def saveIdentity(self, recipientId, identityKey):
        query = '''INSERT INTO identities (recipient_id, public_key, trust, shown)
                   VALUES(?, ?, ?, ?)'''
        if not self.containsIdentity(recipientId, identityKey):
            trust = self.getDefaultTrust(recipientId)
            self._con.execute(query, (recipientId,
                                      identityKey.getPublicKey().serialize(),
                                      trust,
                                      1 if trust == Trust.BLIND else 0))
            self._con.commit()

    def containsIdentity(self, recipientId, identityKey):
        query = '''SELECT * FROM identities WHERE recipient_id = ?
                   AND public_key = ?'''

        public_key = identityKey.getPublicKey().serialize()
        result = self._con.execute(query, (recipientId,
                                           public_key)).fetchone()

        return result is not None

    def deleteIdentity(self, recipientId, identityKey):
        query = '''DELETE FROM identities
                   WHERE recipient_id = ? AND public_key = ?'''
        public_key = identityKey.getPublicKey().serialize()
        self._con.execute(query, (recipientId, public_key))
        self._con.commit()

    def isTrustedIdentity(self, recipientId, identityKey):
        return True

    def getTrustForIdentity(self, recipientId, identityKey):
        query = '''SELECT trust FROM identities WHERE recipient_id = ?
                   AND public_key = ?'''
        public_key = identityKey.getPublicKey().serialize()
        result = self._con.execute(query, (recipientId, public_key)).fetchone()
        return result.trust if result is not None else None

    def getFingerprints(self, jid):
        query = '''SELECT recipient_id,
                          public_key as "public_key [pk]",
                          trust,
                          timestamp
                   FROM identities
                   WHERE recipient_id = ? ORDER BY trust ASC'''
        return self._con.execute(query, (jid,)).fetchall()

    def getMucFingerprints(self, jids):
        query = '''
            SELECT recipient_id,
                   public_key as "public_key [pk]",
                   trust,
                   timestamp
            FROM identities
            WHERE recipient_id IN ({}) ORDER BY trust ASC
            '''.format(', '.join(['?'] * len(jids)))

        return self._con.execute(query, jids).fetchall()

    def hasUndecidedFingerprints(self, jid):
        query = '''SELECT public_key as "public_key [pk]" FROM identities
                   WHERE recipient_id = ? AND trust = ?'''
        result = self._con.execute(query, (jid, Trust.UNDECIDED)).fetchall()
        undecided = [row.public_key for row in result]

        inactive = self.getInactiveSessionsKeys(jid)
        undecided = set(undecided) - set(inactive)
        return bool(undecided)

    def getDefaultTrust(self, jid):
        if not self._is_blind_trust_enabled():
            return Trust.UNDECIDED

        query = '''SELECT * FROM identities
                   WHERE recipient_id = ? AND trust IN (0, 1)'''
        result = self._con.execute(query, (jid,)).fetchone()
        if result is None:
            return Trust.BLIND
        return Trust.UNDECIDED

    def getTrustedFingerprints(self, jid):
        query = '''SELECT public_key as "public_key [pk]" FROM identities
                   WHERE recipient_id = ? AND trust IN(1, 3)'''
        result = self._con.execute(query, (jid,)).fetchall()
        return [row.public_key for row in result]

    def getNewFingerprints(self, jid):
        query = '''SELECT _id FROM identities WHERE shown = 0
                   AND recipient_id = ?'''

        result = self._con.execute(query, (jid,)).fetchall()
        return [row.id for row in result]

    def setShownFingerprints(self, fingerprints):
        query = 'UPDATE identities SET shown = 1 WHERE _id IN ({})'.format(
            ', '.join(['?'] * len(fingerprints)))
        self._con.execute(query, fingerprints)
        self._con.commit()

    def setTrust(self, recipient_id, identityKey, trust):
        query = '''UPDATE identities SET trust = ? WHERE public_key = ?
                   AND recipient_id = ?'''
        public_key = identityKey.getPublicKey().serialize()
        self._con.execute(query, (trust, public_key, recipient_id))
        self._con.commit()

    def isTrusted(self, recipient_id, device_id):
        record = self.loadSession(recipient_id, device_id)
        if record.isFresh():
            return False
        identity_key = record.getSessionState().getRemoteIdentityKey()
        return self.getTrustForIdentity(
            recipient_id, identity_key) in (Trust.VERIFIED, Trust.BLIND)

    def getIdentityLastSeen(self, recipient_id, identity_key):
        identity_key = identity_key.getPublicKey().serialize()
        query = '''SELECT timestamp FROM identities
                   WHERE recipient_id = ? AND public_key = ?'''
        result = self._con.execute(query, (recipient_id,
                                           identity_key)).fetchone()
        return result.timestamp if result is not None else None

    def setIdentityLastSeen(self, recipient_id, identity_key):
        timestamp = int(time.time())
        identity_key = identity_key.getPublicKey().serialize()
        self._log.info('Set last seen for %s %s', recipient_id, timestamp)
        query = '''UPDATE identities SET timestamp = ?
                   WHERE recipient_id = ? AND public_key = ?'''
        self._con.execute(query, (timestamp, recipient_id, identity_key))
        self._con.commit()

    def getUnacknowledgedCount(self, recipient_id, device_id):
        record = self.loadSession(recipient_id, device_id)
        if record.isFresh():
            return 0
        state = record.getSessionState()
        return state.getSenderChainKey().getIndex()
