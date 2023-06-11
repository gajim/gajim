# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import dataclasses
import datetime as dt
import json
import logging

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from gajim.common import events
from gajim.common.storage.base import AlchemyStorage
from gajim.common.storage.base import Encoder
from gajim.common.storage.base import json_decoder
from gajim.common.storage.base import with_session
from gajim.common.storage.events import models as mod
from gajim.common.types import ChatContactT

EVENT_CLASSES: dict[str, Any] = {
    'muc-nickname-changed': events.MUCNicknameChanged,
    'muc-room-config-changed': events.MUCRoomConfigChanged,
    'muc-room-config-finished': events.MUCRoomConfigFinished,
    'muc-room-presence-error': events.MUCRoomPresenceError,
    'muc-room-kicked': events.MUCRoomKicked,
    'muc-room-destroyed': events.MUCRoomDestroyed,
    'muc-user-joined': events.MUCUserJoined,
    'muc-user-left': events.MUCUserLeft,
    'muc-user-role-changed': events.MUCUserRoleChanged,
    'muc-user-affiliation-changed': events.MUCUserAffiliationChanged,
    'muc-user-status-show-changed': events.MUCUserStatusShowChanged,
}

log = logging.getLogger('gajim.c.storage.events')


class EventStorage(AlchemyStorage):
    def __init__(self):
        AlchemyStorage.__init__(
            self,
            log,
            None,
        )

    def _create_table(self, session: Session, engine: Engine) -> None:
        mod.Base.metadata.create_all(engine)
        session.execute(sa.text('PRAGMA user_version=1'))

    def _migrate(self) -> None:
        pass

    @with_session
    def store(self, session: Session, contact: ChatContactT, event_: Any) -> None:
        event_dict = dataclasses.asdict(event_)
        name = event_dict.pop('name')
        timestamp = event_dict.pop('timestamp')

        event = mod.Event(
            account=contact.account,
            jid=contact.jid,
            event=name,
            timestamp=timestamp,
            data=json.dumps(event_dict, cls=Encoder),
        )

        session.add(event)

    @with_session
    def load(
        self,
        session: Session,
        contact: ChatContactT,
        before: bool,
        timestamp_: float,
        n_lines: int,
    ) -> list[events.ApplicationEvent]:
        timestamp = dt.datetime.fromtimestamp(timestamp_, dt.timezone.utc)

        stmt = sa.select(mod.Event).where(
            mod.Event.account == contact.account, mod.Event.jid == contact.jid
        )

        if before:
            stmt = stmt.where(mod.Event.timestamp < timestamp).order_by(
                sa.desc(mod.Event.timestamp)
            )
        else:
            stmt = stmt.where(mod.Event.timestamp > timestamp).order_by(
                mod.Event.timestamp
            )

        stmt = stmt.limit(n_lines)

        event_list: list[events.ApplicationEvent] = []

        for event_row in session.scalars(stmt).all():
            event_class = EVENT_CLASSES[event_row.event]
            data = json.loads(event_row.data, object_hook=json_decoder)
            event_ = event_class(**data, timestamp=event_row.timestamp)
            event_list.append(event_)

        return event_list
