# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from pathlib import Path

import sqlalchemy as sa

from gajim.common import app
from gajim.common.settings import Settings
from gajim.common.storage.archive import migration
from gajim.common.storage.archive.storage import CURRENT_USER_VERSION
from gajim.common.storage.archive.storage import MessageArchiveStorage


class TestMigration(unittest.TestCase):
    def setUp(self) -> None:
        self._init_settings()

    def tearDown(self) -> None:
        Path("test.db").unlink(missing_ok=True)
        Path("test.db-shm").unlink(missing_ok=True)
        Path("test.db-wal").unlink(missing_ok=True)

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account("testacc1")
        app.settings.set_account_setting("testacc1", "address", "user@domain.org")

    def test_migration(self) -> None:
        # Database schema for Gajim 0.16.9
        DATABASE_SCHEMA = """
            CREATE TABLE jids(
                    jid_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                    jid TEXT UNIQUE,
                    type INTEGER
            );

            CREATE TABLE unread_messages(
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                    jid_id INTEGER,
                    shown BOOLEAN default 0
            );

            CREATE INDEX idx_unread_messages_jid_id ON unread_messages (jid_id);

            CREATE TABLE logs(
                    log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                    jid_id INTEGER,
                    contact_name TEXT,
                    time INTEGER,
                    kind INTEGER,
                    show INTEGER,
                    message TEXT,
                    subject TEXT
            );

            CREATE INDEX idx_logs_jid_id_time ON logs (jid_id, time DESC);"""

        dbpath = Path("test.db")
        engine = sa.create_engine(f"sqlite:///{dbpath}", echo=False)

        with engine.connect() as connection:
            for stmt in DATABASE_SCHEMA.split(";"):
                connection.execute(sa.text(stmt))
                connection.commit()

        engine.dispose()

        archive = MessageArchiveStorage(path=dbpath)
        migration.run(archive, 0)

        version = archive.get_user_version()
        self.assertEqual(version, CURRENT_USER_VERSION)

        archive.shutdown()


if __name__ == "__main__":
    unittest.main()
