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
from gi.repository import Gtk
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
from gajim.common.events import DBMigrationProgress
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType

log = logging.getLogger('gajim.c.storage.archive.migration')


class MigrationBase(DeclarativeBase):
    pass


class LastArchiveMessage(MappedAsDataclass, MigrationBase, kw_only=True):
    __tablename__ = 'last_archive_message'

    jid_id: Mapped[int] = mapped_column(primary_key=True)
    last_mam_id: Mapped[str]
    oldest_mam_timestamp: Mapped[float]
    last_muc_timestamp: Mapped[float]


class Jids(MappedAsDataclass, MigrationBase, kw_only=True):
    __tablename__ = 'jids'

    jid_id: Mapped[int] = mapped_column(primary_key=True)
    jid: Mapped[str]
    type: Mapped[int]


class Logs(MappedAsDataclass, MigrationBase, kw_only=True):
    __tablename__ = 'logs'

    log_line_id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(sa.ForeignKey('jids.jid_id'))
    account: Mapped[Jids] = relationship(
        lazy='joined', foreign_keys=[account_id], viewonly=True, init=False
    )

    jid_id: Mapped[int] = mapped_column(sa.ForeignKey('jids.jid_id'))
    remote: Mapped[Jids] = relationship(
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
    def __init__(self, archive: Any) -> None:
        self._archive = archive
        self._engine = archive._engine

        self._account_pks: dict[JID, int] = {}
        self._remote_pks: dict[JID, int] = {}
        self._encryption_pks: dict[tuple[str | Trust, ...], int] = {}

        self._accounts: dict[str, str] = {}
        for account_name in app.settings.get_accounts():
            jid = app.get_jid_from_account(account_name)
            self._accounts[jid] = account_name

        mod.Base.metadata.create_all(archive._engine)

        stmt = (
            sa.select(Logs)
            .where(Logs.kind.in_([2, 4, 6]))
            .execution_options(yield_per=1000)
        )

        with self._engine.connect() as conn:
            for i, log_row in enumerate(self._archive.get_session().scalars(stmt)):
                try:
                    self._process_row(conn, log_row)
                except Exception:
                    log.exception('Error')
                    raise

                if i % 1000 == 0:
                    app.ged.raise_event(DBMigrationProgress(message=str(i)))
                    conn.commit()

            conn.execute(sa.text('PRAGMA user_version=8'))
            conn.commit()

        self._drop_tables()

    def _process_row(self, conn: sa.Connection, log_row: Logs) -> None:
        m_type, direction = KIND_MAPPING[log_row.kind]

        if log_row.time is None:
            raise ValueError('Empty timestamp')

        account_jid = JID.from_string(log_row.account.jid)
        remote_jid = JID.from_string(log_row.remote.jid)

        account_pk = self._get_account_pk(conn, account_jid)
        remote_pk = self._get_remote_pk(conn, remote_jid)

        try:
            additional_data = json.loads(log_row.additional_data or '{}')
        except Exception as error:
            raise ValueError(
                f'failed to parse additional_data, skipping record: {error} - {log_row.additional_data}'
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

            try:
                pk = conn.execute(
                    sa.insert(mod.Message).returning(mod.Message.pk), [message_data]
                ).scalar()
            except Exception:
                raise

        except Exception as error:
            print(error)
            raise

        assert pk is not None

        self._insert_oob_data(conn, pk, additional_data)
        self._insert_error_data(conn, account_pk, remote_pk, log_row, timestamp)

    def _get_account_pk(self, conn: sa.Connection, jid: JID) -> int:
        pk = self._account_pks.get(jid)
        if pk is not None:
            return pk

        try:
            pk = conn.execute(
                sa.insert(mod.Account).values(jid=jid).returning(mod.Account.pk)
            ).scalar()
        except Exception as error:
            log.warning('Failed to insert remote: %s', error)
            raise

        if pk is None:
            raise ValueError('Failed to insert remote')

        self._account_pks[jid] = pk
        return pk

    def _get_remote_pk(self, conn: sa.Connection, jid: JID) -> int:
        pk = self._remote_pks.get(jid)
        if pk is not None:
            return pk

        try:
            pk = conn.execute(
                sa.insert(mod.Remote).values(jid=jid).returning(mod.Remote.pk)
            ).scalar()
        except Exception as error:
            log.warning('Failed to insert remote: %s', error)
            raise

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

        try:
            conn.execute(sa.insert(mod.OOB), [oob_data])
        except Exception as error:
            print(error)
            raise

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
        except Exception as error:
            print(error)
            raise

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

        try:
            pk = conn.execute(
                sa.insert(mod.Encryption).returning(mod.Encryption.pk),
                [encryption_data],
            ).scalar()
        except Exception as error:
            print(error)
            raise

        if pk is None:
            return None

        data_tp = tuple(encryption_data.values())
        self._encryption_pks[data_tp] = pk
        return pk

    def _drop_tables(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(sa.text('DROP TABLE jids'))
            conn.execute(sa.text('DROP TABLE logs'))
            conn.commit()

    def run(self) -> None:
        pass


def run(archive: Any) -> None:
    Migration(archive)
