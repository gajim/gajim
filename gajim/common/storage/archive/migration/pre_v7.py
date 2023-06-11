# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

log = logging.getLogger('gajim.c.storage.archive.migration')


class Migration:
    def __init__(self, path: Path) -> None:
        con = sqlite3.connect(path)
        try:
            self._migrate(con)
        except Exception:
            log.exception('Migration error')
            con.close()
            sys.exit()

        con.close()

    @staticmethod
    def _execute_multiple(con: sqlite3.Connection, statements: list[str]) -> None:
        '''
        Execute multiple statements with the option to fail on duplicates
        but still continue
        '''
        for sql in statements:
            try:
                con.execute(sql)
            except sqlite3.OperationalError as error:
                if str(error).startswith('duplicate column name:'):
                    log.info(error)
                else:
                    raise

        con.commit()

    @staticmethod
    def _get_user_version(con: sqlite3.Connection) -> int:
        return con.execute('PRAGMA user_version').fetchone()[0]

    def _migrate(self, con: sqlite3.Connection) -> None:
        user_version = self._get_user_version(con)
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
                'PRAGMA user_version=1',
            ]

            self._execute_multiple(con, statements)

        if user_version < 2:
            statements = [
                (
                    'ALTER TABLE last_archive_message '
                    'ADD COLUMN "sync_threshold" INTEGER'
                ),
                'PRAGMA user_version=2',
            ]
            self._execute_multiple(con, statements)

        if user_version < 3:
            statements = [
                'ALTER TABLE logs ADD COLUMN "message_id" TEXT',
                'PRAGMA user_version=3',
            ]
            self._execute_multiple(con, statements)

        if user_version < 4:
            statements = [
                'ALTER TABLE logs ADD COLUMN "error" TEXT',
                'PRAGMA user_version=4',
            ]
            self._execute_multiple(con, statements)

        if user_version < 7:
            statements = [
                'ALTER TABLE logs ADD COLUMN "real_jid" TEXT',
                'ALTER TABLE logs ADD COLUMN "occupant_id" TEXT',
                'PRAGMA user_version=7',
            ]
            self._execute_multiple(con, statements)


def run(path: Path) -> None:
    Migration(path)
