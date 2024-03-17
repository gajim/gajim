# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import datetime

from nbxmpp import JID
from sqlalchemy import types
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.types import TypeEngine

from gajim.common.storage.base import EpochTimestampType
from gajim.common.storage.base import JIDType


class Base(DeclarativeBase):
    type_annotation_map: dict[type[Any], TypeEngine[Any]] = {
        float: types.REAL(),
        str: types.TEXT(),
        int: types.INTEGER(),
    }


class Event(MappedAsDataclass, Base, kw_only=True):
    __tablename__ = 'event'

    pk: Mapped[int] = mapped_column(primary_key=True, init=False)
    account: Mapped[str] = mapped_column()
    jid: Mapped[JID] = mapped_column(JIDType)
    event: Mapped[str] = mapped_column()
    timestamp: Mapped[datetime.datetime] = mapped_column(EpochTimestampType)
    data: Mapped[str] = mapped_column()
