# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import json
import logging
import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import sqlalchemy as sa
from nbxmpp.protocol import JID
from nbxmpp.structs import CommonError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import relationship

from gajim.common import app
from gajim.common.const import Trust
from gajim.common.events import DBMigrationFinished
from gajim.common.events import DBMigrationProgress
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.base import AlchemyStorage
from gajim.common.storage.base import is_unique_constraint_error

log = logging.getLogger('gajim.c.storage.archive.migration')


class MigrationBase(DeclarativeBase):
    pass


class LastArchiveMessage(MappedAsDataclass, MigrationBase, kw_only=True):
    __tablename__ = 'last_archive_message'

    jid_id: Mapped[int] = mapped_column(sa.ForeignKey('jids.jid_id'), primary_key=True)
    remote: Mapped[Jids | None] = relationship(lazy='joined', viewonly=True, init=False)
    last_mam_id: Mapped[str | None]
    oldest_mam_timestamp: Mapped[float | None]
    last_muc_timestamp: Mapped[float | None]


class Jids(MappedAsDataclass, MigrationBase, kw_only=True):
    __tablename__ = 'jids'

    jid_id: Mapped[int] = mapped_column(primary_key=True)
    jid: Mapped[str]
    type: Mapped[int]


class Logs(MappedAsDataclass, MigrationBase, kw_only=True):
    __tablename__ = 'logs'

    log_line_id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(sa.ForeignKey('jids.jid_id'))
    account: Mapped[Jids | None] = relationship(
        lazy='joined', foreign_keys=[account_id], viewonly=True, init=False
    )

    jid_id: Mapped[int] = mapped_column(sa.ForeignKey('jids.jid_id'))
    remote: Mapped[Jids | None] = relationship(
        lazy='joined', foreign_keys=[jid_id], viewonly=True, init=False
    )

    contact_name: Mapped[str | None]
    occupant_id: Mapped[str | None]
    real_jid: Mapped[str | None]
    time: Mapped[float | None]
    kind: Mapped[int]
    show: Mapped[int | None]
    message: Mapped[str]
    error: Mapped[str | None]
    subject: Mapped[str | None]
    additional_data: Mapped[str | None]
    stanza_id: Mapped[str | None]
    message_id: Mapped[str | None]
    encryption: Mapped[str | None]
    encryption_state: Mapped[str | None]
    marker: Mapped[int | None]


KIND_MAPPING = {
    2: (MessageType.GROUPCHAT, ChatDirection.INCOMING),
    4: (MessageType.CHAT, ChatDirection.INCOMING),
    6: (MessageType.CHAT, ChatDirection.OUTGOING),
}


class Migration:
    def __init__(self, archive: AlchemyStorage, user_version: int) -> None:
        self._archive = archive
        self._engine = archive.get_engine()

        self._account_pks: dict[JID, int] = {}
        self._remote_pks: dict[JID, int] = {}
        self._encryption_pks: dict[tuple[str | Trust, ...], int] = {}

        self._accounts: dict[str, str] = {}

        if user_version < 7:
            self._pre_v7(user_version)
        if user_version < 8:
            self._v8()
        if user_version < 9:
            self._v9()

        app.ged.raise_event(DBMigrationFinished())

    def _execute_multiple(self, statements: list[str]) -> None:
        with self._engine.begin() as conn:
            for stmt in statements:
                conn.execute(sa.text(stmt))

    def _pre_v7(self, user_version: int) -> None:
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

            self._execute_multiple(statements)

        if user_version < 2:
            statements = [
                (
                    'ALTER TABLE last_archive_message '
                    'ADD COLUMN "sync_threshold" INTEGER'
                ),
                'PRAGMA user_version=2',
            ]
            self._execute_multiple(statements)

        if user_version < 3:
            statements = [
                'ALTER TABLE logs ADD COLUMN "message_id" TEXT',
                'PRAGMA user_version=3',
            ]
            self._execute_multiple(statements)

        if user_version < 4:
            statements = [
                'ALTER TABLE logs ADD COLUMN "error" TEXT',
                'PRAGMA user_version=4',
            ]
            self._execute_multiple(statements)

        if user_version < 7:
            statements = [
                'ALTER TABLE logs ADD COLUMN "real_jid" TEXT',
                'ALTER TABLE logs ADD COLUMN "occupant_id" TEXT',
                'PRAGMA user_version=7',
            ]
            self._execute_multiple(statements)

    def _v8(self) -> None:
        for account_name in app.settings.get_accounts():
            jid = app.get_jid_from_account(account_name)
            self._accounts[jid] = account_name

        mod.Base.metadata.create_all(self._engine)

        count_stmt = sa.select(sa.func.count(Logs.log_line_id)).where(
            Logs.kind.in_([2, 4, 6])
        )
        stmt = (
            sa.select(Logs)
            .where(Logs.kind.in_([2, 4, 6]))
            .execution_options(yield_per=1000)
        )

        with self._engine.begin() as conn:
            count = conn.execute(count_stmt).scalar()
            assert count is not None
            for i, log_row in enumerate(self._archive.get_session().scalars(stmt)):
                self._process_message_row(conn, log_row)

                if i % 1000 == 0:
                    app.ged.raise_event(DBMigrationProgress(count=count, progress=i))

            app.ged.raise_event(DBMigrationProgress(count=count, progress=count))

            stmt = sa.select(LastArchiveMessage)

            accounts = app.settings.get_accounts()
            account_jids = [app.get_jid_from_account(account) for account in accounts]
            account_jids = [JID.from_string(a) for a in account_jids]
            account_pks = [self._get_account_pk(conn, j) for j in account_jids]

            for archive_row in self._archive.get_session().scalars(stmt):
                self._process_archive_row(conn, archive_row, account_pks)

            conn.execute(sa.text('DROP TABLE last_archive_message'))
            conn.execute(sa.text('DROP TABLE logs'))
            conn.execute(sa.text('DROP TABLE jids'))
            conn.execute(sa.text('DROP TABLE IF EXISTS unread_messages'))
            conn.execute(sa.text('PRAGMA user_version=8'))

    def _v9(self) -> None:
        statements = [
            'CREATE INDEX idx_stanza_id ON message(stanza_id, fk_remote_pk, fk_account_pk);',
            'PRAGMA user_version=9',
        ]

        self._execute_multiple(statements)

    def _process_archive_row(
        self,
        conn: sa.Connection,
        archive_row: LastArchiveMessage,
        account_pks: list[int],
    ) -> None:
        if archive_row.remote is None:
            log.warning(
                'Unable to migrate mam state because jid_id %s was not found',
                archive_row.jid_id,
            )
            return

        remote_jid = JID.from_string(archive_row.remote.jid)
        remote_pk = self._get_remote_pk(conn, remote_jid)

        to_stanza_id = archive_row.last_mam_id
        to_stanza_ts = archive_row.last_muc_timestamp
        if archive_row.last_mam_id is None or archive_row.last_muc_timestamp is None:
            to_stanza_id = None
            to_stanza_ts = None

        if to_stanza_ts is not None:
            to_stanza_ts = datetime.fromtimestamp(float(to_stanza_ts), tz=timezone.utc)

        from_stanza_ts = None
        if archive_row.oldest_mam_timestamp is not None:
            from_stanza_ts = datetime.fromtimestamp(
                float(archive_row.oldest_mam_timestamp), tz=timezone.utc
            )

        if (from_stanza_ts, to_stanza_id, to_stanza_ts) == (None, None, None):
            return

        for account_pk in account_pks:
            try:
                conn.execute(
                    sa.insert(mod.MAMArchiveState).values(
                        fk_account_pk=account_pk,
                        fk_remote_pk=remote_pk,
                        from_stanza_ts=from_stanza_ts,
                        to_stanza_id=to_stanza_id,
                        to_stanza_ts=to_stanza_ts,
                    )
                )
            except IntegrityError:
                log.warning(
                    'Unable to migrate mam archive state, because it was already migrated'
                )
                return

    def _process_message_row(self, conn: sa.Connection, log_row: Logs) -> None:
        m_type, direction = KIND_MAPPING[log_row.kind]

        if log_row.time is None:
            log.warning('Unable to migrate message because timestamp is empty')
            return

        if log_row.account is None:
            log.warning(
                'Unable to migrate message because account_id %s was not found',
                log_row.account_id,
            )
            return

        if log_row.remote is None:
            log.warning(
                'Unable to migrate message because jid_id %s was not found',
                log_row.jid_id,
            )
            return

        account_jid = JID.from_string(log_row.account.jid)
        remote_jid = JID.from_string(log_row.remote.jid)

        account_pk = self._get_account_pk(conn, account_jid)
        remote_pk = self._get_remote_pk(conn, remote_jid)

        try:
            additional_data = json.loads(log_row.additional_data or '{}')
        except Exception as error:
            raise ValueError(
                f'failed to parse additional_data: {error} - {log_row.additional_data}'
            )

        user_timestamp = additional_data.get('user_timestamp')
        user_delay_ts = None
        if user_timestamp is not None:
            user_delay_ts = datetime.fromtimestamp(user_timestamp, timezone.utc)

        timestamp = datetime.fromtimestamp(log_row.time, timezone.utc)

        encryption_pk = self._insert_encryption_data(conn, additional_data)

        text = log_row.message
        corrected = additional_data.get('corrected')
        if corrected is not None:
            text = corrected.get('original_text') or text

        message_data: dict[str, Any] = {
            'fk_account_pk': account_pk,
            'fk_remote_pk': remote_pk,
            'resource': log_row.contact_name,
            'type': m_type,
            'direction': direction,
            'timestamp': timestamp,
            'state': MessageState.ACKNOWLEDGED,
            'id': log_row.message_id,
            'stanza_id': log_row.stanza_id,
            'text': text,
            'user_delay_ts': user_delay_ts,
            'fk_encryption_pk': encryption_pk,
        }

        try:
            pk = conn.execute(
                sa.insert(mod.Message).returning(mod.Message.pk), [message_data]
            ).scalar()
        except IntegrityError as error:
            if 'message.stanza_id' not in error.args[0]:
                raise

            message_data['stanza_id'] = str(uuid.uuid4())

            pk = conn.execute(
                sa.insert(mod.Message).returning(mod.Message.pk), [message_data]
            ).scalar()

        assert pk is not None

        self._insert_oob_data(conn, pk, additional_data)
        self._insert_error_data(conn, account_pk, remote_pk, log_row, timestamp)

    def _get_account_pk(self, conn: sa.Connection, jid: JID) -> int:
        pk = self._account_pks.get(jid)
        if pk is not None:
            return pk

        pk = conn.execute(
            sa.insert(mod.Account).values(jid=jid).returning(mod.Account.pk)
        ).scalar()

        if pk is None:
            raise ValueError('Failed to insert account')

        self._account_pks[jid] = pk
        return pk

    def _get_remote_pk(self, conn: sa.Connection, jid: JID) -> int:
        pk = self._remote_pks.get(jid)
        if pk is not None:
            return pk

        pk = conn.execute(
            sa.insert(mod.Remote).values(jid=jid).returning(mod.Remote.pk)
        ).scalar()

        if pk is None:
            raise ValueError('Failed to insert remote')

        self._remote_pks[jid] = pk
        return pk

    def _insert_oob_data(
        self,
        conn: sa.Connection,
        fk_message_pk: int,
        additional_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not additional_data:
            return None

        gajim_data = additional_data.get('gajim')
        if gajim_data is None:
            return None

        url = gajim_data.get('oob_url')
        description = gajim_data.get('oob_desc')

        if url is None:
            return None

        oob_data = {
            'fk_message_pk': fk_message_pk,
            'url': url,
            'description': description,
        }

        conn.execute(sa.insert(mod.OOB), [oob_data])

    def _insert_error_data(
        self,
        conn: sa.Connection,
        fk_account_pk: int,
        fk_remote_pk: int,
        log_row: Logs,
        timestamp: datetime,
    ) -> dict[str, Any] | None:
        if log_row.error is None:
            return None

        try:
            error = CommonError.from_string(log_row.error)
        except Exception:
            return None

        assert log_row.message_id is not None

        by = error.by
        e_type = error.type  # pyright: ignore
        text = error.get_text() or None  # pyright: ignore
        condition = error.condition  # pyright: ignore
        condition_text = error.condition_data or None  # pyright: ignore

        if e_type is None or condition is None:
            return None

        error_data = {  # pyright: ignore
            'fk_account_pk': fk_account_pk,
            'fk_remote_pk': fk_remote_pk,
            'message_id': log_row.message_id,
            'by': by,
            'type': e_type,
            'text': text,
            'condition': condition,
            'condition_text': condition_text,
            'timestamp': timestamp + timedelta(seconds=1),
        }

        try:
            conn.execute(sa.insert(mod.MessageError), [error_data])  # pyright: ignore
        except IntegrityError as error:
            if is_unique_constraint_error(error):
                return

    def _insert_encryption_data(
        self, conn: sa.Connection, additional_data: dict[str, Any]
    ) -> int | None:
        if not additional_data:
            return None

        encrypted = additional_data.get('encrypted')
        if encrypted is None:
            return None

        protocol = encrypted.get('name')
        key = encrypted.get('fingerprint')
        trust = encrypted.get('trust')

        if protocol not in ('OpenPGP', 'OMEMO', 'PGP'):
            return None

        if key is None:
            key = 'Unknown'

        if trust is None:
            trust = Trust.VERIFIED

        else:
            try:
                trust = Trust(trust)
            except Exception:
                trust = Trust.UNTRUSTED

        encryption_data = {'protocol': protocol, 'key': key, 'trust': trust}
        encryption_pk = self._encryption_pks.get(tuple(encryption_data.values()))
        if encryption_pk is not None:
            return encryption_pk

        pk = conn.execute(
            sa.insert(mod.Encryption).returning(mod.Encryption.pk),
            [encryption_data],
        ).scalar()

        if pk is None:
            return None

        data_tp = tuple(encryption_data.values())
        self._encryption_pks[data_tp] = pk
        return pk


def run(archive: Any, user_version: int) -> None:
    Migration(archive, user_version)
