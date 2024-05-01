# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal

import calendar
import datetime as dt
import logging
import pprint
import shutil
from collections.abc import Iterator
from collections.abc import Sequence
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import sqlalchemy as sa
from nbxmpp import JID
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import MAX_MESSAGE_CORRECTION_DELAY
from gajim.common.events import DBMigration
from gajim.common.helpers import get_random_string
from gajim.common.storage.archive import migration
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Account
from gajim.common.storage.archive.models import Base
from gajim.common.storage.archive.models import MAMArchiveState
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import MessageError
from gajim.common.storage.archive.models import Moderation
from gajim.common.storage.archive.models import Remote
from gajim.common.storage.archive.models import Thread
from gajim.common.storage.base import AlchemyStorage
from gajim.common.storage.base import timeit
from gajim.common.storage.base import VALUE_MISSING
from gajim.common.storage.base import with_session
from gajim.common.util.datetime import FIRST_UTC_DATETIME

CURRENT_USER_VERSION = 9


log = logging.getLogger('gajim.c.storage.archive')


class MessageArchiveStorage(AlchemyStorage):
    def __init__(self, in_memory: bool = False, path: Path | None = None) -> None:
        if path is None:
            path = configpaths.get('LOG_DB')

        AlchemyStorage.__init__(
            self,
            log,
            None if in_memory else path,
            pragma={
                'journal_mode': 'wal',
                'secure_delete': 'on',
            },
        )

        self._account_pks: dict[str, int] = {}
        self._jid_pks: dict[JID, int] = {}

    def init(self) -> None:
        super().init()
        with self._session as s:
            self._load_jids(s)

    def _log_row(self, row: Any) -> None:
        if self._log.getEffectiveLevel() != logging.DEBUG:
            return
        self._log.debug('Object before query\n%s', pprint.pformat(row))

    def _create_table(self, session: Session, engine: Engine) -> None:
        Base.metadata.create_all(engine)
        session.execute(sa.text(f'PRAGMA user_version={CURRENT_USER_VERSION}'))

    def _make_backup(self) -> None:
        db_path = configpaths.get('LOG_DB')
        random_string = get_random_string(10)
        db_backup_path = db_path.parent / f'{db_path.name}.{random_string}.bak'
        shutil.copy(db_path, db_backup_path)

    def _migrate(self) -> None:
        user_version = self._get_user_version()
        if user_version < CURRENT_USER_VERSION:
            app.ged.raise_event(DBMigration())
            self._make_backup()
            migration.run(self, user_version)

    @timeit
    def _load_jids(self, session: Session) -> None:
        jids = session.scalars(select(Remote))
        self._jid_pks = {j.jid: j.pk for j in jids}

    def _get_account_pk(self, session: Session, account: str) -> int:
        pk = self._account_pks.get(account)
        if pk is not None:
            return pk

        jid_str = app.get_jid_from_account(account)
        jid = JID.from_string(jid_str)

        pk = session.scalar(select(Account.pk).where(Account.jid == jid))
        if pk is None:
            acc = Account(jid=jid)
            session.add(acc)
            session.flush()
            pk = acc.pk

        self._account_pks[account] = pk
        return pk

    def _get_jid_pk(self, session: Session, jid: JID) -> int:
        pk = self._jid_pks.get(jid)
        if pk is not None:
            return pk

        jid_row = Remote(jid=jid)
        session.add(jid_row)
        session.flush()

        pk = jid_row.pk
        self._jid_pks[jid] = pk
        return pk

    def _set_foreign_keys(self, session: Session, row: Any) -> None:
        fk_account_pk = None
        account = getattr(row, 'account_', None)
        if account is not None:
            fk_account_pk = self._get_account_pk(session, account)
            row.account_ = None
            row.fk_account_pk = fk_account_pk

        fk_remote_pk = None
        remote_jid = getattr(row, 'remote_jid_', None)
        if remote_jid is not None:
            row.remote_jid_ = None
            fk_remote_pk = self._get_jid_pk(session, remote_jid)
            row.fk_remote_pk = fk_remote_pk

        if hasattr(row, 'real_remote_jid_'):
            real_remote_jid = row.real_remote_jid_
            if real_remote_jid is not VALUE_MISSING:
                row.real_remote_jid_ = None
                if real_remote_jid is None:
                    row.fk_real_remote_pk = None
                else:
                    row.fk_real_remote_pk = self._get_jid_pk(session, real_remote_jid)

        security_label = getattr(row, 'security_label_', None)
        if security_label is not None:
            pk = self._upsert_row(session, row.security_label_)
            row.security_label_ = None
            row.fk_security_label_pk = pk

        encryption = getattr(row, 'encryption_', None)
        if encryption is not None:
            pk = self._insert_row(session, encryption, return_pk_on_conflict=True)
            row.encryption_ = None
            row.fk_encryption_pk = pk

        thread_id = getattr(row, 'thread_id_', None)
        if thread_id is not None:
            assert fk_account_pk is not None
            assert fk_remote_pk is not None
            thread = Thread(
                fk_account_pk=fk_account_pk,
                fk_remote_pk=fk_remote_pk,
                id=thread_id,
            )
            pk = self._insert_row(session, thread, return_pk_on_conflict=True)
            row.thread_ = None
            row.fk_thread_pk = pk

        occupant = getattr(row, 'occupant_', None)
        if occupant is not None:
            pk = self._upsert_row(session, occupant)
            row.occupant_ = None
            row.fk_occupant_pk = pk

    @with_session
    @timeit
    def insert_object(
        self, session: Session, obj: Any, ignore_on_conflict: bool = True
    ) -> int:
        self._set_foreign_keys(session, obj)
        self._log_row(obj)
        session.add(obj)

        try:
            session.commit()
        except Exception:
            if not ignore_on_conflict:
                raise
            return -1

        return obj.pk

    @with_session
    @timeit
    def insert_row(
        self,
        session: Session,
        row: Any,
        *,
        return_pk_on_conflict: bool = False,
        ignore_on_conflict: bool = False,
    ) -> int:
        return self._insert_row(
            session,
            row,
            return_pk_on_conflict=return_pk_on_conflict,
            ignore_on_conflict=ignore_on_conflict,
        )

    def _insert_row(
        self,
        session: Session,
        row: Any,
        *,
        return_pk_on_conflict: bool = False,
        ignore_on_conflict: bool = False,
    ) -> int:
        self._set_foreign_keys(session, row)
        self._log_row(row)
        table = row.__class__
        stmt = insert(table).values(**row.get_insert_values()).returning(table.pk)

        try:
            pk = session.scalar(stmt)
        except IntegrityError:
            if ignore_on_conflict:
                return -1

            if return_pk_on_conflict:
                stmt = row.get_select_stmt()
                return session.scalar(stmt).pk

            raise

        assert pk is not None
        return pk

    @with_session
    @timeit
    def upsert_row(self, session: Session, row: Any) -> int:
        return self._upsert_row(session, row)

    def _upsert_row(
        self,
        session: Session,
        row: Any,
    ) -> int:
        self._set_foreign_keys(session, row)
        self._log_row(row)
        table = row.__class__

        stmt = row.get_select_stmt()
        existing = session.scalar(stmt)

        if existing is None:
            stmt = insert(table).values(**row.get_insert_values()).returning(table.pk)
            pk = session.scalar(stmt)
            assert pk is not None
            return pk

        if not row.needs_update(existing):
            return existing.pk

        stmt = (
            update(table)
            .where(table.pk == existing.pk)
            .values(**row.get_upsert_values())
        )

        session.execute(stmt)
        return existing.pk

    @with_session
    @timeit
    def get_message_with_pk(
        self, session: Session, pk: int, options: Any = None
    ) -> Message | None:
        return self._get_message_with_pk(session, pk, options)

    def _get_message_with_pk(
        self, session: Session, pk: int, options: Any = None
    ) -> Message | None:
        stmt = select(Message).where(Message.pk == pk)
        if options is not None:
            stmt = stmt.options(*options)
        return session.scalar(stmt)

    @with_session
    @timeit
    def get_message_with_id(
        self,
        session: Session,
        account: str,
        jid: JID,
        message_id: str
    ) -> Message | None:

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = select(Message).where(
            Message.id == message_id,
            Message.fk_remote_pk == fk_remote_pk,
            Message.fk_account_pk == fk_account_pk,
        )

        result = session.scalars(stmt).all()
        if len(result) > 1:
            self._log.warning('Found >1 message with message id %s', message_id)
            return None
        return result[0]

    @with_session
    @timeit
    def get_message_with_stanza_id(
        self,
        session: Session,
        account: str,
        jid: JID,
        stanza_id: str
    ) -> Message | None:

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = select(Message).where(
            Message.stanza_id == stanza_id,
            Message.fk_remote_pk == fk_remote_pk,
            Message.fk_account_pk == fk_account_pk,
        )

        result = session.scalars(stmt).all()
        if len(result) > 1:
            self._log.warning('Found >1 message with stanza id %s', stanza_id)
            return None
        return result[0]

    @with_session
    @timeit
    def delete_message(self, session: Session, pk: int) -> None:
        message = self._get_message_with_pk(session, pk)
        if message is None:
            self._log.warning('Deletion failed, no message found with pk %s', pk)
            return

        self._delete_message(session, message)

    def _delete_message(self, session: Session, message: Message) -> None:
        if message.corrections:
            for correction in message.corrections:
                session.delete(correction)

        if message.error is not None:
            session.delete(message.error)

        if message.moderation is not None:
            session.delete(message.moderation)

        session.delete(message)

    @with_session
    @timeit
    def check_if_message_id_exists(
        self, session: Session, account: str, jid: JID, message_id: str
    ) -> bool:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        exists_criteria = select(Message.id).where(
            Message.id == message_id,
            Message.fk_remote_pk == fk_remote_pk,
            Message.fk_account_pk == fk_account_pk,
        ).exists()

        res = session.scalar(select(1).where(exists_criteria))
        return bool(res)

    @with_session
    @timeit
    def check_if_stanza_id_exists(
        self, session: Session, account: str, jid: JID, stanza_id: str
    ) -> bool:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        exists_criteria = select(Message.id).where(
            Message.stanza_id == stanza_id,
            Message.fk_remote_pk == fk_remote_pk,
            Message.fk_account_pk == fk_account_pk,
        ).exists()

        res = session.scalar(select(1).where(exists_criteria))
        return bool(res)

    @with_session
    @timeit
    def get_conversation_jids(self, session: Session, account: str) -> Sequence[JID]:
        fk_account_pk = self._get_account_pk(session, account)

        subq = (
            select(Message.fk_remote_pk)
            .distinct()
            .where(Message.fk_account_pk == fk_account_pk)
        ).subquery()

        stmt = select(Remote.jid).join(subq)
        self._explain(session, stmt)
        return session.scalars(stmt).all()

    @with_session
    @timeit
    def get_conversation_before_after(
        self,
        session: Session,
        account: str,
        jid: JID,
        before: bool,
        timestamp: datetime,
        n_lines: int,
    ) -> Sequence[Message]:
        '''
        Load n messages from jid before or after timestamp

        :param account:
            The account
        :param jid:
            The jid for which we request the conversation
        :param before:
            The search direction
        :param timestamp:
            The point in time from where to search
        :param nlines:
            The maximal count of Message returned
        '''

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = select(Message).where(
            Message.fk_remote_pk == fk_remote_pk,
            Message.fk_account_pk == fk_account_pk,
            Message.correction_id.is_(None),
        )

        if before:
            stmt = stmt.where(Message.timestamp < timestamp).order_by(
                sa.desc(Message.timestamp), sa.desc(Message.pk)
            )
        else:
            stmt = stmt.where(Message.timestamp > timestamp).order_by(
                Message.timestamp, Message.pk
            )

        stmt = stmt.limit(n_lines)

        self._explain(session, stmt)
        return session.scalars(stmt).all()

    @with_session
    @timeit
    def get_last_conversation_row(
        self, session: Session, account: str, jid: JID
    ) -> Message | None:
        '''
        Load the last line of a conversation with jid for account.
        Loads messages, but no status messages or error messages.

        :param account:         The account
        :param jid:             The jid for which we request the conversation

        returns a namedtuple or None
        '''

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = (
            select(Message)
            .where(
                Message.fk_remote_pk == fk_remote_pk,
                Message.fk_account_pk == fk_account_pk,
                Message.correction_id.is_(None),
            )
            .order_by(sa.desc(Message.timestamp), sa.desc(Message.pk))
            .limit(1)
        )

        self._explain(session, stmt)
        return session.scalar(stmt)

    @with_session
    @timeit
    def get_last_correctable_message(
        self, session: Session, account: str, jid: JID, message_id: str
    ) -> Message | None:
        '''
        Load the last correctable message of a conversation by message_id.
        Conditions: max 5 min old
        '''
        # TODO this could match multiple rows, better is to search with the pk

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        min_time = datetime.now(timezone.utc) - timedelta(
            seconds=MAX_MESSAGE_CORRECTION_DELAY
        )

        stmt = (
            select(Message)
            .where(
                Message.id == message_id,
                Message.fk_remote_pk == fk_remote_pk,
                Message.fk_account_pk == fk_account_pk,
                Message.timestamp > min_time,
                Message.state == MessageState.ACKNOWLEDGED,
            )
            .order_by(sa.desc(Message.timestamp), sa.desc(Message.pk))
            .limit(1)
        )

        self._explain(session, stmt)
        return session.scalar(stmt)

    @with_session
    @timeit
    def get_corrected_message(
        self, session: Session, correction: Message
    ) -> Message | None:
        stmt = select(Message).where(
            Message.id == correction.correction_id,
            Message.fk_remote_pk == correction.fk_remote_pk,
            Message.fk_account_pk == correction.fk_account_pk,
            Message.fk_occupant_pk.is_(correction.fk_occupant_pk),
            Message.direction == correction.direction,
        )

        if correction.type == 2 and correction.fk_occupant_pk is None:
            stmt = stmt.where(Message.resource == correction.resource)

        stmt = stmt.order_by(sa.desc(Message.timestamp)).limit(1)

        self._explain(session, stmt)
        return session.scalar(stmt)

    def get_referenced_message(
        self,
        account: str,
        jid: JID,
        message_type: MessageType | int,
        reply_id: str
    ) -> Message | None:

        if message_type == MessageType.GROUPCHAT:
            return app.storage.archive.get_message_with_stanza_id(
                account, jid, reply_id)

        return app.storage.archive.get_message_with_id(
            account, jid, reply_id)

    @with_session
    @timeit
    def search_archive(
        self,
        session: Session,
        account: str | None,
        jid: JID | None,
        query: str,
        from_users: list[str] | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
    ) -> Iterator[Message]:
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

        # TODO: Does not search in corrections

        if before is None:
            before = datetime.now(timezone.utc)

        if after is None:
            after = FIRST_UTC_DATETIME

        fk_account_pk = None
        if account is not None:
            fk_account_pk = self._get_account_pk(session, account)

        fk_remote_pk = None
        if jid is not None:
            fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = select(Message)

        if fk_account_pk is not None:
            stmt = stmt.where(Message.fk_account_pk == fk_account_pk)

        if fk_remote_pk is not None:
            stmt = stmt.where(Message.fk_remote_pk == fk_remote_pk)

        if from_users is not None:
            lowercase_users = list(map(str.lower, from_users))
            stmt = stmt.where(sa.func.lower(Message.resource).in_(lowercase_users))

        stmt = (
            stmt.where(
                Message.text.ilike(f'%{query}%'),
                Message.timestamp.between(after, before),
            )
            .order_by(sa.desc(Message.timestamp), sa.desc(Message.pk))
            .execution_options(yield_per=25)
        )

        self._explain(session, stmt)
        yield from session.scalars(stmt)

    @with_session
    @timeit
    def get_days_containing_messages(
        self, session: Session, account: str, jid: JID, year: int, month: int
    ) -> Sequence[int]:
        '''
        Get days in month of year where messages for account/jid exist
        '''

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        # The user wants all days which have messages within a month.
        # A message in the database with a timestamp 2024-01-01 00:00:01 UTC
        # should show up if a user is in the timezone -01:00 and passes
        # year=2023, month=12 to this function. Because for the user the message
        # happened 2023-12 localtime.
        #
        # astimezone(timezone.utc) applied to a naive datetime assumes that the
        # datetime is in localtime and converts to UTC.
        #
        # Example (Executed in a +01:00 timezone):
        #   >>> dt = datetime(2024, 1, 1).astimezone(timezone.utc)
        #   datetime.datetime(2023, 12, 31, 23, 0, tzinfo=datetime.timezone.utc)
        #
        # If we now search with this UTC timestamp in the database it will return
        # the day 31 although the user would want to see the day 1. To compensate
        # for this, the day selected is converted back by SQL to localtime.

        local_start = datetime(year, month, 1)
        _, days = calendar.monthrange(year, month)
        local_end = datetime.combine(datetime(year, month, days), dt.time.max)

        start = local_start.astimezone(timezone.utc)
        end = local_end.astimezone(timezone.utc)

        stmt = (
            select(
                sa.func.cast(
                    sa.func.strftime('%d', Message.timestamp, 'unixepoch', 'localtime'),
                    sa.INTEGER,
                )
            )
            .distinct()
            .where(
                Message.fk_remote_pk == fk_remote_pk,
                Message.fk_account_pk == fk_account_pk,
                Message.timestamp.between(start, end),
                Message.correction_id.is_(None),
            )
        )

        self._explain(session, stmt)
        return session.scalars(stmt).all()

    def _get_message_ts(
        self,
        session: Session,
        account: str,
        jid: JID,
        direction: Literal['first', 'last'],
    ) -> datetime | None:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = select(Message.timestamp).where(
            Message.fk_remote_pk == fk_remote_pk,
            Message.fk_account_pk == fk_account_pk,
            Message.correction_id.is_(None),
        )
        if direction == 'first':
            stmt = stmt.order_by(sa.desc(Message.timestamp), sa.desc(Message.pk))
        else:
            stmt = stmt.order_by(Message.timestamp, Message.pk)

        stmt = stmt.limit(1)

        self._explain(session, stmt)
        return session.scalar(stmt)

    @with_session
    @timeit
    def get_last_message_ts(
        self, session: Session, account: str, jid: JID
    ) -> datetime | None:
        '''
        Get the timestamp of the last message we received for the jid
        '''
        return self._get_message_ts(session, account, jid, direction='first')

    @with_session
    @timeit
    def get_first_message_ts(
        self, session: Session, account: str, jid: JID
    ) -> datetime | None:
        '''
        Get the timestamp of the first message we received for the jid
        '''
        return self._get_message_ts(session, account, jid, direction='last')

    @with_session
    @timeit
    def get_first_message_meta_for_date(
        self, session: Session, account: str, jid: JID, date: dt.date
    ) -> tuple[int, datetime] | None:
        '''
        Load meta data (pk, timestamp) for the first message of
        a specific date

        for details about finding start and end of a day see
        get_days_containing_messages()
        '''

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        start = datetime.combine(date, dt.time.min).astimezone(timezone.utc)
        end = datetime.combine(date, dt.time.max).astimezone(timezone.utc)

        stmt = (
            select(Message.pk, Message.timestamp)
            .where(
                Message.fk_remote_pk == fk_remote_pk,
                Message.fk_account_pk == fk_account_pk,
                Message.timestamp.between(start, end),
                Message.correction_id.is_(None),
            )
            .order_by(Message.timestamp, Message.pk)
            .limit(1)
        )

        self._explain(session, stmt)
        result = session.execute(stmt).one_or_none()
        if result is None:
            return None
        return result.pk, result.timestamp

    @with_session
    @timeit
    def get_recent_muc_nicks(
        self, session: Session, account: str, jid: JID
    ) -> set[str]:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        recent = datetime.now(timezone.utc) - timedelta(days=90)

        stmt = (
            select(Message.resource)
            .distinct()
            .where(
                Message.fk_remote_pk == fk_remote_pk,
                Message.fk_account_pk == fk_account_pk,
                Message.timestamp > recent,
                Message.resource.isnot(None),
                Message.correction_id.is_(None),
            )
        )

        self._explain(session, stmt)
        return set(session.scalars(stmt))

    @with_session
    @timeit
    def get_mam_archive_state(
        self, session: Session, account: str, jid: JID
    ) -> MAMArchiveState | None:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = select(MAMArchiveState).where(
            MAMArchiveState.fk_account_pk == fk_account_pk,
            MAMArchiveState.fk_remote_pk == fk_remote_pk,
        )

        self._explain(session, stmt)
        return session.scalar(stmt)

    @with_session
    @timeit
    def reset_mam_archive_state(self, session: Session, account: str, jid: JID) -> None:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = delete(MAMArchiveState).where(
            MAMArchiveState.fk_account_pk == fk_account_pk,
            MAMArchiveState.fk_remote_pk == fk_remote_pk,
        )

        session.execute(stmt)

    @with_session
    @timeit
    def update_pending_message(
        self,
        session: Session,
        account: str,
        jid: JID,
        message_id: str,
        stanza_id: str | None,
    ) -> int | None:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = (
            update(Message)
            .where(
                Message.id == message_id,
                Message.fk_remote_pk == fk_remote_pk,
                Message.fk_account_pk == fk_account_pk,
                Message.direction == ChatDirection.OUTGOING,
            )
            .values(state=MessageState.ACKNOWLEDGED, stanza_id=stanza_id)
            .returning(Message.pk)
        )

        self._explain(session, stmt)
        return session.scalar(stmt)

    @with_session
    @timeit
    def remove_history_for_jid(self, session: Session, account: str, jid: JID) -> None:
        '''
        Remove messages and metadata for a specific jid.
        '''

        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = delete(MessageError).where(
            MessageError.fk_account_pk == fk_account_pk,
            MessageError.fk_remote_pk == fk_remote_pk,
        )

        session.execute(stmt)

        stmt = delete(Moderation).where(
            Moderation.fk_account_pk == fk_account_pk,
            Moderation.fk_remote_pk == fk_remote_pk,
        )

        session.execute(stmt)

        stmt = delete(Message).where(
            Message.fk_account_pk == fk_account_pk, Message.fk_remote_pk == fk_remote_pk
        )

        session.execute(stmt)

        log.info('Removed history for: %s', jid)

    @with_session
    @timeit
    def remove_all_history(self, session: Session) -> None:
        '''
        Remove all messages for all accounts
        '''

        session.execute(delete(MessageError))
        session.execute(delete(Moderation))
        session.execute(delete(Message))

        log.info('Removed all chat history')

    @with_session
    @timeit
    def remove_account(self, session: Session, account: str) -> None:
        fk_account_pk = self._get_account_pk(session, account)

        session.execute(delete(Account).where(Account.pk == fk_account_pk))

        self._account_pks.pop(account)

    @with_session
    @timeit
    def cleanup_chat_history(self, session: Session) -> None:
        '''
        Remove messages from account where messages are older than max_age
        '''
        for account in app.settings.get_accounts():
            max_age = app.settings.get_account_setting(account, 'chat_history_max_age')
            if max_age == -1:
                continue

            fk_account_pk = self._get_account_pk(session, account)

            now = datetime.now(timezone.utc)
            threshold = now - timedelta(seconds=max_age)

            stmt = select(Message).where(
                Message.fk_account_pk == fk_account_pk, Message.timestamp < threshold
            )

            for message in session.scalars(stmt).unique().all():
                self._delete_message(session, message)

            log.info('Removed messages older then %s', threshold.isoformat())

    @with_session
    @timeit
    def get_messages_for_export(
        self, session: Session, account: str, jid: JID
    ) -> Iterator[Message]:
        fk_account_pk = self._get_account_pk(session, account)
        fk_remote_pk = self._get_jid_pk(session, jid)

        stmt = (
            select(Message)
            .where(
                Message.fk_account_pk == fk_account_pk,
                Message.fk_remote_pk == fk_remote_pk,
                Message.correction_id.is_(None),
            )
            .order_by(sa.desc(Message.timestamp), sa.desc(Message.pk))
            .execution_options(yield_per=25)
        )

        self._explain(session, stmt)
        yield from session.scalars(stmt)
