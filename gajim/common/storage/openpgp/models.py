# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import datetime

import pysequoia as pys
import sqlalchemy as sa
from nbxmpp import JID
from sqlalchemy import Index
from sqlalchemy import types
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.types import TypeEngine

from gajim.common.storage.base import EpochTimestampType
from gajim.common.storage.base import JIDType


class CertType(sa.types.TypeDecorator[pys.Cert]):
    impl = sa.types.BLOB
    cache_ok = True

    def process_bind_param(self, value: pys.Cert | None, dialect: Any) -> bytes | None:
        if value is None:
            return None

        if hasattr(value, "decryptor"):
            # SecretCert
            return str(value).encode()
        return bytes(value)

    def process_result_value(
        self, value: bytes | None, dialect: Any
    ) -> pys.Cert | None:
        if value is None:
            return value
        return pys.Cert.from_bytes(value)


class Base(DeclarativeBase):
    type_annotation_map: dict[type[Any], TypeEngine[Any]] = {
        float: types.REAL(),
        str: types.TEXT(),
        int: types.INTEGER(),
    }


class Secret(MappedAsDataclass, Base, kw_only=True):
    __tablename__ = "secret"
    __table_args__ = (Index("idx_secret", "jid", unique=True),)

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)
    jid: Mapped[JID] = mapped_column(JIDType)
    key: Mapped[pys.Cert] = mapped_column(CertType)


class Public(MappedAsDataclass, Base, kw_only=True):
    __tablename__ = "public"
    __table_args__ = (
        Index("idx_public", "account", "jid"),
        Index("idx_public_fpr", "account", "jid", "fingerprint", unique=True),
    )

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)
    account: Mapped[str]
    jid: Mapped[JID] = mapped_column(JIDType)
    key: Mapped[pys.Cert] = mapped_column(CertType)
    fingerprint: Mapped[str]
    label: Mapped[str | None] = mapped_column(default=None)
    trust: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)
    last_seen: Mapped[datetime.datetime | None] = mapped_column(
        EpochTimestampType, default=None
    )
