# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import NamedTuple

import dataclasses
import json
import logging
import sqlite3
from collections import namedtuple

from nbxmpp.protocol import JID

from gajim.common import events
from gajim.common.storage.base import Encoder
from gajim.common.storage.base import SqliteStorage
from gajim.common.types import ChatContactT

EVENTS_SQL_STATEMENT = '''
    CREATE TABLE events (
            account TEXT,
            jid TEXT,
            event TEXT,
            timestamp REAL,
            data TEXT);

    CREATE INDEX idx_account_jid ON events(account, jid);

    PRAGMA user_version=1;
    '''

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


class EventRow(NamedTuple):
    account: str
    jid: JID
    event: str
    timestamp: float
    data: dict[str, Any]


class EventStorage(SqliteStorage):
    def __init__(self):
        SqliteStorage.__init__(self,
                               log,
                               None,
                               EVENTS_SQL_STATEMENT)

    def init(self, **kwargs: Any) -> None:
        SqliteStorage.init(self,
                           detect_types=sqlite3.PARSE_COLNAMES)
        self._con.row_factory = self._namedtuple_factory

    @staticmethod
    def _namedtuple_factory(cursor: sqlite3.Cursor,
                            row: tuple[Any, ...]) -> NamedTuple:

        assert cursor.description is not None
        fields = [col[0] for col in cursor.description]  # pyright: ignore
        Row = namedtuple('Row', fields)  # pyright: ignore
        return Row(*row)

    def _migrate(self) -> None:
        pass

    def store(self,
              contact: ChatContactT,
              event: Any
              ) -> None:

        event_dict = dataclasses.asdict(event)
        name = event_dict.pop('name')
        timestamp = event_dict.pop('timestamp')

        insert_sql = '''
            INSERT INTO events(account, jid, event, timestamp, data)
            VALUES(?, ?, ?, ?, ?)'''

        self._con.execute(insert_sql, (contact.account,
                                       contact.jid,
                                       name,
                                       timestamp,
                                       json.dumps(event_dict, cls=Encoder)))

    def load(self,
             contact: ChatContactT,
             before: bool,
             timestamp: float,
             n_lines: int,
             ) -> list[events.ApplicationEvent]:

        if before:
            time_order = 'AND timestamp < ? ORDER BY timestamp DESC'
        else:
            time_order = 'AND timestamp > ? ORDER BY timestamp ASC'

        insert_sql = '''
            SELECT account, jid, event, timestamp, data as "data [JSON]"
            FROM events WHERE account=? AND jid=? {time_order}
            LIMIT ?'''.format(time_order=time_order)  # noqa: UP032

        event_list: list[events.ApplicationEvent] = []
        for row in self._con.execute(insert_sql, (contact.account,
                                                  contact.jid,
                                                  timestamp,
                                                  n_lines)).fetchall():
            event_class = EVENT_CLASSES[row.event]
            event_list.append(event_class(**row.data,
                                          timestamp=row.timestamp))
        return event_list
