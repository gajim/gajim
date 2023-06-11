# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import json
import sqlite3

import sqlalchemy as sa
from nbxmpp.structs import CommonError
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass

from gajim.common.const import Trust
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType


class MigrationBase(DeclarativeBase):
    pass


class LastArchiveMessage(MigrationBase, MappedAsDataclass, kw_only=True):
    __tablename__ = 'last_archive_message'

    jid_id: Mapped[int] = mapped_column(primary_key=True)
    last_mam_id: Mapped[str]
    oldest_mam_timestamp: Mapped[float]
    last_muc_timestamp: Mapped[float]


class Jids(MigrationBase, MappedAsDataclass, kw_only=True):
    __tablename__ = 'jids'

    jid_id: Mapped[int] = mapped_column(primary_key=True)
    jid: Mapped[str]
    type: Mapped[int]


class Logs(MigrationBase, MappedAsDataclass, kw_only=True):
    __tablename__ = 'logs'

    log_line_id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int]
    jid_id: Mapped[int]
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


class Migration:
    def __init__(self, session: sa.orm.Session) -> None:
        self._session = session
        self._account_eks: dict[str, int] = {}
        self._jid_eks: dict[str, int] = {}
        self._encryption_eks: dict[Any, int] = {}

    def _get_type_and_direction(self, kind: int) -> tuple[int, int]:
        match kind:
            case 2:
                return MessageType.GROUPCHAT, ChatDirection.INCOMING
            case 4:
                return MessageType.CHAT, ChatDirection.INCOMING
            case 6:
                return MessageType.CHAT, ChatDirection.OUTGOING
            case _:
                raise ValueError('Unknown kind: %s' % kind)

    def _get_account_ek(self, row: Any) -> int:
        account_ek = self._account_eks.get(row.account_jid)
        if account_ek is not None:
            return account_ek

        account_ek = self._con.execute(
            'INSERT INTO account(jid) VALUES(?)', row.account_jid
        ).lastrowid
        assert account_ek is not None
        self._account_eks[row.account_jid] = account_ek
        return account_ek

    def _get_jid_ek(self, row: Any) -> int:
        jid_ek = self._jid_eks.get(row.remote_jid)
        if jid_ek is not None:
            return jid_ek

        jid_ek = self._con.execute(
            'INSERT INTO jid(jid) VALUES(?)', row.remote_jid
        ).lastrowid
        assert jid_ek is not None
        self._jid_eks[row.account_jid] = jid_ek
        return jid_ek

    def _get_message_data(self, row: Any) -> dict[str, Any] | None:
        timestamp = row.time
        if timestamp is None:
            return None

        message = row.message
        if message is None:
            return None

        account_ek = self._get_account_ek(row)
        jid_ek = self._get_jid_ek(row)
        m_type, direction = self._get_type_and_direction(row.kind)
        data = {
            'account_ek': account_ek,
            'jid_ek': jid_ek,
            'm_type': m_type,
            'direction': direction,
            'stanza_id': row.stanza_id,
            'message_id': row.message_id,
            'message': message,
            'marker': row.marker,
            'error': row.error,
            'timestamp': timestamp,
            'resource': row.contact_name,
            'state': MessageState.ACKNOWLEDGED,
            'additional_data': json.loads(row.additional_data or '{}'),
        }
        return data

    def _migrate_correction(
        self,
        message_data: dict[str, Any],
        encryption_ek: int | None,
    ) -> str | None:
        additional_data = message_data['additional_data']
        if additional_data is None:
            return

        corrected = additional_data.get('corrected')
        if corrected is None:
            return None

        original_text = corrected.get('original_text')

        if message_data['message_id'] is None:
            return

        corrected_message = message_data['message']

        stmt = '''
            INSERT INTO correction(
                fk_account_ek,
                fk_jid_ek,
                resource,
                direction,
                timestamp,
                correction_id,
                corrected_message,
                fk_encryption_ek
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''

        self._con.execute(
            stmt,
            (
                message_data['account_ek'],
                message_data['jid_ek'],
                message_data['resource'],
                message_data['direction'],
                message_data['timestamp'] + 0.1,
                message_data['message_id'],
                corrected_message,
                encryption_ek,
            ),
        )

        return original_text

    def _migrate_message(
        self,
        message_data: dict[str, Any],
        original_text: str | None,
        encryption_ek: int | None,
    ) -> int:
        user_timestamp = None
        additional_data = message_data['additional_data']
        if additional_data is not None:
            gajim_data = additional_data.get('gajim')
            if gajim_data is not None:
                user_timestamp = gajim_data.get('user_timestamp')

        message = message_data['message']
        if original_text is not None:
            message = original_text

        stmt = '''
            INSERT INTO message(
                fk_account_ek,
                fk_jid_ek,
                resource,
                m_type,
                direction,
                timestamp,
                state,
                message_id,
                stanza_id,
                message,
                user_delay_ts,
                fk_encryption_ek
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        entitykey = self._con.execute(
            stmt,
            (
                message_data['account_ek'],
                message_data['jid_ek'],
                message_data['resource'],
                message_data['m_type'],
                message_data['direction'],
                message_data['timestamp'],
                message_data['state'],
                message_data['message_id'],
                message_data['stanza_id'],
                message,
                user_timestamp,
                encryption_ek,
            ),
        ).lastrowid

        assert entitykey is not None
        return entitykey

    def _migrate_oob(
        self,
        entitykey: int,
        message_data: dict[str, Any],
    ) -> None:
        additional_data = message_data['additional_data']
        if additional_data is None:
            return

        gajim_data = additional_data.get('gajim')
        if gajim_data is None:
            return None

        url = gajim_data.get('oob_url')
        description = gajim_data.get('oob_desc')

        if url is None:
            return None

        self._con.execute(
            'INSERT INTO oob(entitykey, url, description) VALUES (?, ?, ?)',
            (entitykey, url, description),
        )

    def _migrate_errors(
        self,
        message_data: dict[str, Any],
    ) -> None:
        error_node_serialized = message_data['error']
        if error_node_serialized is None:
            return None

        message_id = message_data['message_id']
        if message_id is None:
            return None

        try:
            error = CommonError.from_string(error_node_serialized)
        except Exception:
            return None

        by = error.by
        e_type = error.type  # pyright: ignore
        text = error.get_text() or None  # pyright: ignore
        condition = error.condition  # pyright: ignore
        condition_text = error.condition_data or None  # pyright: ignore

        if e_type is None or condition is None:
            return None

        stmt = '''
            INSERT INTO error(
                fk_account_ek,
                fk_jid_ek,
                message_id,
                by,
                e_type,
                text,
                condition,
                condition_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''

        try:
            self._con.execute(
                stmt,
                (
                    message_data['account_ek'],
                    message_data['jid_ek'],
                    message_id,
                    by,
                    e_type,
                    text,
                    condition,
                    condition_text,
                ),  # pyright: ignore
            )
        except sqlite3.IntegrityError:
            pass

    def _migrate_moderations(
        self,
        message_data: dict[str, Any],
    ) -> None:
        additional_data = message_data['additional_data']
        if additional_data is None:
            return None

        stanza_id = message_data['stanza_id']
        if stanza_id is None:
            return None

        retracted = additional_data.get('retracted')
        if retracted is None:
            return None

        by = retracted.get('by')
        timestamp = retracted.get('timestamp')
        reason = retracted.get('reason')

        if timestamp is None:
            timestamp = message_data['timestamp']

        stmt = '''
            INSERT INTO moderation(
                fk_account_ek,
                fk_jid_ek,
                timestamp,
                stanza_id,
                by,
                reason)
            VALUES (?, ?, ?, ?, ?, ?)
        '''

        try:
            self._con.execute(
                stmt,
                (
                    message_data['account_ek'],
                    message_data['jid_ek'],
                    timestamp,
                    stanza_id,
                    by,
                    reason,
                ),
            )
        except sqlite3.IntegrityError:
            pass

    def _migrate_encryption(self, message_data: dict[str, Any]) -> int | None:
        additional_data = message_data['additional_data']
        if additional_data is None:
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

        encryption_ek = self._encryption_eks.get((protocol, key, trust))
        if encryption_ek is not None:
            return encryption_ek

        stmt = 'INSERT INTO encryption(protocol, key, trust) VALUES (?, ?, ?)'

        encryption_ek = self._con.execute(stmt, (protocol, key, trust)).lastrowid
        assert encryption_ek is not None
        return encryption_ek

    def run(self) -> None:
        stmt = '''
            SELECT
                account.jid as account_jid,
                jids.jid as remote_jid,
                account_id,
                contact_name,
                time,
                kind,
                message,
                error,
                additional_data,
                stanza_id,
                message_id,
                marker
            FROM logs
            LEFT OUTER JOIN jids AS account ON logs.account_id = account.jid_id
            LEFT OUTER JOIN jids ON jids.jid_id = logs.jid_id
            WHERE kind IN (2, 4, 6)
        '''

        rows = self._con.execute(stmt).fetchall()
        for row in rows:
            message_data = self._get_message_data(row)
            if message_data is None:
                continue

            encryption_ek = self._migrate_encryption(message_data)
            original_text = self._migrate_correction(
                message_data,
                encryption_ek,
            )

            message_entity_key = self._migrate_message(
                message_data,
                original_text,
                encryption_ek,
            )

            assert message_entity_key is not None
            self._migrate_oob(message_entity_key, message_data)
            self._migrate_errors(message_data)
            self._migrate_moderations(message_data)


def run(session: sa.orm.Session) -> None:
    # TODO
    return
    Migration(session)
