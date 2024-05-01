# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import dataclasses
import datetime

import sqlalchemy as sa
from nbxmpp import JID
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy import types
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression as expr
from sqlalchemy.types import TypeEngine

from gajim.common import app
from gajim.common.storage.base import EpochTimestampType
from gajim.common.storage.base import JIDType
from gajim.common.storage.base import JSONType
from gajim.common.storage.base import StrValueMissingType
from gajim.common.storage.base import VALUE_MISSING
from gajim.common.storage.base import ValueMissingT


class Base(DeclarativeBase):
    type_annotation_map: dict[type[Any], TypeEngine[Any]] = {
        float: types.REAL(),
        str: types.TEXT(),
        int: types.INTEGER(),
    }


class UtilMixin:
    def get_upsert_values(self) -> dict[str, str]:
        values = {
            f.name: getattr(self, f.name)
            for f in dataclasses.fields(self)  # pyright: ignore
        }
        for key, value in list(values.items()):
            if value is VALUE_MISSING:
                values.pop(key)
                continue

            if key not in self.__upsert_cols__:  # pyright: ignore
                values.pop(key)
        return values

    def get_insert_values(self):
        values = {
            f.name: getattr(self, f.name)
            for f in dataclasses.fields(self)  # pyright: ignore
        }
        for key, value in list(values.items()):
            if value is VALUE_MISSING:
                values.pop(key)
                continue

            if key in self.__no_table_cols__:  # pyright: ignore
                values.pop(key)
        return values


class Account(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'account'
    __table_args__ = (Index('idx_account', 'jid', unique=True),)

    pk: Mapped[int] = mapped_column(init=False, primary_key=True)
    jid: Mapped[JID] = mapped_column(JIDType)


class Remote(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'remote'
    __table_args__ = (Index('idx_remote', 'jid', unique=True),)

    pk: Mapped[int] = mapped_column(init=False, primary_key=True)
    jid: Mapped[JID] = mapped_column(JIDType)


class Thread(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'thread'
    __index_cols__ = ['id', 'fk_remote_pk', 'fk_account_pk']
    __no_table_cols__ = []
    __table_args__ = (Index('idx_thread', *__index_cols__, unique=True),)

    pk: Mapped[int] = mapped_column(init=False, primary_key=True)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE')
    )
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'))

    id: Mapped[str]

    def get_select_stmt(self) -> Select[Any]:
        return select(Thread).where(
            Thread.id == self.id,
            Thread.fk_remote_pk == self.fk_remote_pk,
            Thread.fk_account_pk == self.fk_account_pk,
        )


class Occupant(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'occupant'
    __index_cols__ = ['id', 'fk_remote_pk', 'fk_account_pk']
    __upsert_cols__ = ['fk_real_remote_pk', 'nickname', 'avatar_sha', 'updated_at']
    __no_table_cols__ = ['account_', 'remote_jid_', 'real_remote_jid_', 'real_remote']
    __table_args__ = (Index('idx_occupant', *__index_cols__, unique=True),)

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    id: Mapped[str]

    real_remote_jid_: JID | None | ValueMissingT = dataclasses.field(
        default=VALUE_MISSING, repr=False
    )
    fk_real_remote_pk: Mapped[int | None] = mapped_column(
        StrValueMissingType, ForeignKey('remote.pk'), default=VALUE_MISSING, init=False
    )
    real_remote: Mapped[Remote | None] = relationship(
        lazy='joined',
        foreign_keys=fk_real_remote_pk,
        default=None,
        viewonly=True,
        init=False,
    )

    nickname: Mapped[str | None] = mapped_column(default=None)

    avatar_sha: Mapped[str | None] = mapped_column(
        StrValueMissingType, default=VALUE_MISSING
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)

    def needs_update(self, existing: Occupant) -> bool:
        return existing.updated_at < self.updated_at

    def get_select_stmt(self) -> Select[Any]:
        return select(Occupant).where(
            Occupant.id == self.id,
            Occupant.fk_remote_pk == self.fk_remote_pk,
            Occupant.fk_account_pk == self.fk_account_pk,
        )

    def get_upsert_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {'updated_at': self.updated_at}
        if self.nickname is not None:
            values['nickname'] = self.nickname

        if isinstance(self.fk_real_remote_pk, int):
            values['fk_real_remote_pk'] = sa.func.coalesce(
                Occupant.fk_real_remote_pk, self.fk_real_remote_pk
            )

        if self.avatar_sha is not VALUE_MISSING:
            values['avatar_sha'] = self.avatar_sha

        return values


class OOB(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'oob'

    pk: Mapped[int] = mapped_column(init=False, primary_key=True)
    fk_message_pk: Mapped[int] = mapped_column(
        ForeignKey('message.pk', ondelete='CASCADE'), init=False
    )
    url: Mapped[str]
    description: Mapped[str | None]


class Reply(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'reply'

    fk_message_pk: Mapped[int] = mapped_column(
        ForeignKey('message.pk', ondelete='CASCADE'), primary_key=True, init=False
    )
    id: Mapped[str]
    to: Mapped[JID | None] = mapped_column(JIDType)


class Call(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'call'

    fk_message_pk: Mapped[int] = mapped_column(
        ForeignKey('message.pk', ondelete='CASCADE'), primary_key=True, init=False
    )
    sid: Mapped[str]
    end_ts: Mapped[datetime.datetime | None] = mapped_column(
        EpochTimestampType, default=None
    )
    state: Mapped[int]


class Encryption(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'encryption'
    __index_cols__ = ['key', 'trust', 'protocol']
    __no_table_cols__ = []
    __table_args__ = (Index('idx_encryption', 'key', 'trust', 'protocol', unique=True),)

    pk: Mapped[int] = mapped_column(init=False, primary_key=True)
    protocol: Mapped[int]
    key: Mapped[str]
    trust: Mapped[int]

    def get_select_stmt(self) -> Select[Any]:
        return select(Encryption).where(
            Encryption.key == self.key,
            Encryption.trust == self.trust,
            Encryption.protocol == self.protocol,
        )


class SecurityLabel(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'securitylabel'
    __index_cols__ = ['label_hash', 'fk_remote_pk', 'fk_account_pk']
    __upsert_cols__ = ['displaymarking', 'fgcolor', 'bgcolor', 'updated_at']
    __no_table_cols__ = ['account_', 'remote_jid_']
    __table_args__ = (Index('idx_security_label', *__index_cols__, unique=True),)

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    label_hash: Mapped[str]
    displaymarking: Mapped[str]
    fgcolor: Mapped[str]
    bgcolor: Mapped[str]
    updated_at: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)

    def needs_update(self, existing: SecurityLabel) -> bool:
        return existing.updated_at < self.updated_at

    def get_select_stmt(self) -> Select[Any]:
        return select(SecurityLabel).where(
            SecurityLabel.label_hash == self.label_hash,
            SecurityLabel.fk_remote_pk == self.fk_remote_pk,
            SecurityLabel.fk_account_pk == self.fk_account_pk,
        )


class MessageError(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'error'
    __index_cols__ = ['message_id', 'fk_remote_pk', 'fk_account_pk']
    __no_table_cols__ = ['account_', 'remote_jid_']
    __table_args__ = (Index('idx_error', *__index_cols__, unique=True),)

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    message_id: Mapped[str]
    by: Mapped[JID | None] = mapped_column(JIDType)
    type: Mapped[str]
    text: Mapped[str | None]
    condition: Mapped[str]
    condition_text: Mapped[str | None]
    timestamp: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)


class Moderation(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'moderation'
    __index_cols__ = ['stanza_id', 'fk_remote_pk', 'fk_account_pk']
    __no_table_cols__ = ['account_', 'remote_jid_', 'occupant', 'occupant_']
    __table_args__ = (Index('idx_moderation', *__index_cols__, unique=True),)

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    occupant_: Occupant | None = dataclasses.field(repr=False)
    occupant: Mapped[Occupant | None] = relationship(
        lazy='joined', viewonly=True, init=False
    )
    fk_occupant_pk: Mapped[int | None] = mapped_column(
        ForeignKey('occupant.pk'), default=None, init=False
    )

    stanza_id: Mapped[str]
    by: Mapped[JID | None] = mapped_column(JIDType)
    reason: Mapped[str | None]
    timestamp: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)


class DisplayedMarker(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'displayed_marker'
    __no_table_cols__ = ['account_', 'remote_jid_', 'occupant', 'occupant_']

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    occupant_: Occupant | None = dataclasses.field(repr=False)
    occupant: Mapped[Occupant | None] = relationship(
        lazy='joined', viewonly=True, init=False
    )
    fk_occupant_pk: Mapped[int | None] = mapped_column(
        ForeignKey('occupant.pk'), default=None, init=False
    )

    id: Mapped[str] = mapped_column()
    timestamp: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)

    __table_args__ = (
        Index(
            'idx_displayed_marker',
            'id',
            'fk_remote_pk',
            'fk_account_pk',
            unique=True,
            sqlite_where=fk_occupant_pk.is_(None),
        ),
        Index(
            'idx_displayed_marker_gc',
            'id',
            'fk_remote_pk',
            'fk_occupant_pk',
            'fk_account_pk',
            unique=True,
            sqlite_where=fk_occupant_pk.isnot(None),
        ),
    )


class Receipt(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'receipt'
    __no_table_cols__ = ['account_', 'remote_jid_']
    __table_args__ = (
        Index(
            'idx_receipt',
            'id',
            'fk_remote_pk',
            'fk_account_pk',
            unique=True,
        ),
    )

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    id: Mapped[str] = mapped_column()
    timestamp: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)


class MAMArchiveState(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'mam_archive_state'
    __index_cols__ = ['fk_remote_pk', 'fk_account_pk']
    __upsert_cols__ = [
        'from_stanza_id',
        'from_stanza_ts',
        'to_stanza_id',
        'to_stanza_ts',
    ]
    __no_table_cols__ = ['account_', 'remote_jid_']
    __table_args__ = (Index('idx_mam_archive_state', *__index_cols__, unique=True),)

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    from_stanza_id: Mapped[str | None] = mapped_column(
        StrValueMissingType, default=VALUE_MISSING
    )
    from_stanza_ts: Mapped[datetime.datetime | None] = mapped_column(
        EpochTimestampType, default=VALUE_MISSING
    )
    to_stanza_id: Mapped[str | None] = mapped_column(
        StrValueMissingType, default=VALUE_MISSING
    )
    to_stanza_ts: Mapped[datetime.datetime | None] = mapped_column(
        EpochTimestampType, default=VALUE_MISSING
    )

    def get_select_stmt(self) -> Select[Any]:
        return select(MAMArchiveState).where(
            MAMArchiveState.fk_remote_pk == self.fk_remote_pk,
            MAMArchiveState.fk_account_pk == self.fk_account_pk,
        )

    def needs_update(self, _existing: MAMArchiveState) -> bool:
        return True


class FileTransferSource(MappedAsDataclass, Base, kw_only=True):
    __tablename__ = 'ft_source'

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)
    fk_filetransfer_pk: Mapped[int] = mapped_column(
        ForeignKey('filetransfer.pk', ondelete='CASCADE'), init=False
    )
    type: Mapped[str]

    __mapper_args__ = {
        'polymorphic_identity': 'source',
        'polymorphic_on': 'type',
    }


class UrlData(FileTransferSource):
    __tablename__ = 'ft_source_urldata'

    fk_ft_source_pk: Mapped[int] = mapped_column(
        ForeignKey('ft_source.pk', ondelete='CASCADE'), primary_key=True, init=False
    )
    target: Mapped[str]
    scheme_data: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    __mapper_args__ = {
        'polymorphic_load': 'selectin',
        'polymorphic_identity': 'urldata',
    }


class JingleFT(FileTransferSource):
    __tablename__ = 'ft_source_jingleft'

    fk_ft_source_pk: Mapped[int] = mapped_column(
        ForeignKey('ft_source.pk', ondelete='CASCADE'), primary_key=True, init=False
    )
    sid: Mapped[str]

    __mapper_args__ = {
        'polymorphic_load': 'selectin',
        'polymorphic_identity': 'jingleft',
    }


class JinglePub(FileTransferSource):
    __tablename__ = 'ft_source_jinglepub'

    fk_ft_source_pk: Mapped[int] = mapped_column(
        ForeignKey('ft_source.pk', ondelete='CASCADE'), primary_key=True, init=False
    )
    id: Mapped[str]

    __mapper_args__ = {
        'polymorphic_load': 'selectin',
        'polymorphic_identity': 'jinglepub',
    }


class FileTransfer(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'filetransfer'

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)
    fk_message_pk: Mapped[int] = mapped_column(
        ForeignKey('message.pk', ondelete='CASCADE'), init=False
    )

    date: Mapped[datetime.datetime | None] = mapped_column(
        EpochTimestampType, default=None
    )
    desc: Mapped[str | None] = mapped_column(default=None)
    hash: Mapped[str | None] = mapped_column(default=None)
    hash_algo: Mapped[str | None] = mapped_column(default=None)
    height: Mapped[int | None] = mapped_column(default=None)
    length: Mapped[int | None] = mapped_column(default=None)
    media_type: Mapped[str | None] = mapped_column(default=None)
    name: Mapped[str | None] = mapped_column(default=None)
    size: Mapped[int | None] = mapped_column(default=None)
    width: Mapped[int | None] = mapped_column(default=None)

    state: Mapped[int | None]
    path: Mapped[str | None] = mapped_column(default=None, init=False)

    source: Mapped[list[FileTransferSource]] = relationship(
        lazy='selectin',
        default_factory=list,
        cascade='all, delete',
        passive_deletes=True,
    )


class Message(MappedAsDataclass, Base, UtilMixin, kw_only=True):
    __tablename__ = 'message'

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)

    account_: str = dataclasses.field(repr=False)
    account: Mapped[Account] = relationship(lazy='joined', viewonly=True, init=False)
    fk_account_pk: Mapped[int] = mapped_column(
        ForeignKey('account.pk', ondelete='CASCADE'), init=False
    )

    remote_jid_: JID = dataclasses.field(repr=False)
    remote: Mapped[Remote] = relationship(lazy='joined', viewonly=True, init=False)
    fk_remote_pk: Mapped[int] = mapped_column(ForeignKey('remote.pk'), init=False)

    resource: Mapped[str | None] = mapped_column()
    type: Mapped[int] = mapped_column()
    direction: Mapped[int] = mapped_column()
    timestamp: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)
    state: Mapped[int]
    id: Mapped[str | None] = mapped_column(default=None)
    stanza_id: Mapped[str | None] = mapped_column(default=None)
    text: Mapped[str | None] = mapped_column(default=None)
    markup_type: Mapped[int | None] = mapped_column(default=None)
    markup: Mapped[str | None] = mapped_column(default=None)
    user_delay_ts: Mapped[datetime.datetime | None] = mapped_column(
        EpochTimestampType, default=None
    )

    thread_id_: str | None = dataclasses.field(repr=False, default=None)
    thread: Mapped[Thread | None] = relationship(
        lazy='joined', viewonly=True, init=False
    )
    fk_thread_pk: Mapped[int | None] = mapped_column(
        ForeignKey('thread.pk'), default=None, init=False
    )

    occupant_: Occupant | None = dataclasses.field(repr=False, default=None)
    occupant: Mapped[Occupant | None] = relationship(
        lazy='joined', viewonly=True, init=False
    )
    fk_occupant_pk: Mapped[int | None] = mapped_column(
        ForeignKey('occupant.pk'), default=None, init=False
    )

    encryption_: Encryption | None = dataclasses.field(repr=False, default=None)
    encryption: Mapped[Encryption | None] = relationship(
        lazy='joined', viewonly=True, init=False
    )
    fk_encryption_pk: Mapped[int | None] = mapped_column(
        ForeignKey('encryption.pk'), default=None, init=False
    )

    security_label_: SecurityLabel | None = dataclasses.field(repr=False, default=None)
    security_label: Mapped[SecurityLabel | None] = relationship(
        lazy='joined', viewonly=True, init=False
    )
    fk_security_label_pk: Mapped[int | None] = mapped_column(
        ForeignKey('securitylabel.pk'), default=None, init=False
    )

    correction_id: Mapped[str | None] = mapped_column(default=None)

    corrections: Mapped[list[Message]] = relationship(
        lazy='selectin',
        init=False,
        primaryjoin=sa.and_(
            sa.orm.foreign(id) == sa.orm.remote(correction_id),
            sa.orm.foreign(fk_remote_pk) == sa.orm.remote(fk_remote_pk),
            sa.orm.foreign(fk_account_pk) == sa.orm.remote(fk_account_pk),
            sa.orm.foreign(fk_occupant_pk).is_(sa.orm.remote(fk_occupant_pk)),
            sa.orm.foreign(direction) == sa.orm.remote(direction),
            expr.case(
                (
                    sa.and_(
                        sa.orm.foreign(type) == 2,  # Groupchat
                        sa.orm.foreign(fk_occupant_pk).is_(None),
                    ),
                    sa.orm.foreign(resource) == sa.orm.remote(resource),
                ),
                else_=1,
            ),
        ),
        join_depth=1,
        viewonly=True,
        uselist=True,
        order_by=timestamp,
    )

    markers: Mapped[list[DisplayedMarker]] = relationship(
        lazy='selectin',
        init=False,
        primaryjoin=sa.and_(
            expr.case(
                (
                    type == 2,  # Groupchat
                    sa.orm.foreign(stanza_id) == DisplayedMarker.id,
                ),
                else_=sa.orm.foreign(id) == DisplayedMarker.id,
            ),
            fk_remote_pk == DisplayedMarker.fk_remote_pk,
            fk_account_pk == DisplayedMarker.fk_account_pk,
        ),
        viewonly=True,
        uselist=True,
    )

    receipt: Mapped[Receipt | None] = relationship(
        lazy='selectin',
        init=False,
        primaryjoin=sa.and_(
            sa.orm.foreign(id) == Receipt.id,
            fk_remote_pk == Receipt.fk_remote_pk,
            fk_account_pk == Receipt.fk_account_pk,
        ),
        viewonly=True,
    )

    moderation: Mapped[Moderation | None] = relationship(
        lazy='joined',
        default=None,
        init=False,
        primaryjoin=sa.and_(
            sa.orm.foreign(stanza_id) == sa.orm.remote(Moderation.stanza_id),
            fk_remote_pk == Moderation.fk_remote_pk,
            fk_account_pk == Moderation.fk_account_pk,
        ),
        viewonly=True,
    )

    error: Mapped[MessageError | None] = relationship(
        lazy='joined',
        default=None,
        init=False,
        primaryjoin=sa.and_(
            sa.orm.foreign(id) == sa.orm.remote(MessageError.message_id),
            fk_remote_pk == MessageError.fk_remote_pk,
            fk_account_pk == MessageError.fk_account_pk,
        ),
        viewonly=True,
    )

    filetransfers: Mapped[list[FileTransfer]] = relationship(
        lazy='selectin',
        default_factory=list,
        cascade='all, delete',
        passive_deletes=True,
    )
    call: Mapped[Call | None] = relationship(
        lazy='joined',
        default=None,
        cascade='all, delete',
        passive_deletes=True,
    )
    oob: Mapped[list[OOB]] = relationship(
        lazy='selectin',
        default_factory=list,
        cascade='all, delete',
        passive_deletes=True,
    )
    reply: Mapped[Reply | None] = relationship(
        lazy='joined',
        default=None,
        cascade='all, delete',
        passive_deletes=True,
    )

    __table_args__ = (
        Index(
            'idx_message', 'fk_remote_pk', 'fk_account_pk', sa.text('timestamp DESC')
        ),
        Index(
            'idx_message_corrections',
            'correction_id',
            'fk_remote_pk',
            'fk_account_pk',
            sa.text('timestamp ASC'),
        ),
        Index(
            'idx_message_id',
            'id',
            'fk_remote_pk',
            'fk_account_pk',
        ),
    )

    def get_last_correction(self) -> Message:
        return self.corrections[-1]

    def get_referenced_message(self) -> Message | None:
        if self.reply is None:
            return None
        account = app.settings.get_account_from_jid(self.account.jid)
        return app.storage.archive.get_referenced_message(
            account,
            self.remote.jid,
            self.type,
            self.reply.id
        )
