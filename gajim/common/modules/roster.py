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

# Roster

from __future__ import annotations

from typing import Iterable
from typing import Iterator
from typing import Optional
from typing import cast

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import IqProperties
from nbxmpp.structs import RosterData
from nbxmpp.structs import RosterItem
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import types
from gajim.common.events import RosterReceived
from gajim.common.events import RosterPush
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact


class Roster(BaseModule):

    _nbxmpp_extends = 'Roster'
    _nbxmpp_methods = [
        'delete_item',
        'set_item',
    ]

    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self.handlers = [
            # StanzaHandler(name='presence',
            #               callback=self._presence_received),
            StanzaHandler(name='iq',
                          callback=self._process_roster_push,
                          typ='set',
                          ns=Namespace.ROSTER),
        ]

        self._roster: dict[JID, RosterItem] = {}

        # Groups cache for performance
        self._groups = None

    def load_roster(self) -> None:
        self._log.info('Load from database')
        roster = app.storage.cache.load_roster(self._account)
        if not roster:
            self._log.info('Database empty, reset roster version')
            app.settings.set_account_setting(
                self._account, 'roster_version', '')
            return

        for jid in roster:
            self._con.get_module('Contacts').add_contact(jid)

        self._roster = roster

    def _store_roster(self) -> None:
        app.storage.cache.store_roster(self._account, self._roster)

    def get_size(self) -> int:
        return len(self._roster)

    def request_roster(self) -> None:
        version = app.settings.get_account_setting(self._account,
                                                   'roster_version')

        self._log.info('Request version: %s', version)
        self._nbxmpp('Roster').request_roster(
            version, callback=self._on_request_roster)

    def _on_request_roster(self, task: Task) -> None:
        try:
            roster = cast(RosterData, task.finish())
        except Exception as error:
            self._log.warning(error)
            return

        self._log.info('Received Roster, version: %s', roster.version)

        if roster.version is None or roster.items is not None:
            # version is None:
            # ---------------
            # No Roster versioning supported this
            # means we got the complete roster
            #
            # items is not None:
            # ---------------
            # Roster versioning supported but
            # server opted to send us the whole roster
            assert roster.items is not None
            self._set_roster_from_data(roster.items)

        app.settings.set_account_setting(self._account,
                                         'roster_version',
                                         roster.version)

        app.ged.raise_event(RosterReceived(account=self._account))

        self._con.connect_machine()

    def _set_roster_from_data(self, items: list[RosterItem]) -> None:
        self._roster.clear()
        self._groups = None

        for item in items:
            self._log.info(item)
            self._con.get_module('Contacts').add_contact(item.jid)
            self._roster[item.jid] = item

        self._store_roster()

    def _process_roster_push(self,
                             _con: types.xmppClient,
                             _stanza: Iq,
                             properties: IqProperties
                             ) -> None:
        self._log.info('Push received')

        assert properties.roster is not None
        item = properties.roster.item
        if item.subscription == 'remove':
            self._roster.pop(item.jid)
        else:
            self._roster[item.jid] = item

        self._groups = None
        self._store_roster()

        self._log.info('New version: %s', properties.roster.version)
        app.settings.set_account_setting(self._account,
                                         'roster_version',
                                         properties.roster.version)

        app.ged.raise_event(RosterPush(account=self._account,
                                       item=item))

        raise nbxmpp.NodeProcessed

    def get_item(self, jid: JID) -> Optional[RosterItem]:
        return self._roster.get(jid)

    def set_groups(self, jid: JID, groups: Optional[Iterable[str]]) -> None:
        if groups is not None:
            groups = set(groups)
        item = self.get_item(jid)
        assert item is not None
        self._nbxmpp('Roster').set_item(jid, item.name, groups)

    def get_groups(self) -> set[str]:
        if self._groups is not None:
            return set(self._groups)

        groups: set[str] = set()
        for item in self._roster.values():
            groups.update(item.groups)
        self._groups = groups
        return set(groups)

    def _get_items_with_group(self, group: str) -> list[RosterItem]:
        return list(filter(lambda item: group in item.groups,
                           self._roster.values()))

    def remove_group(self, group: str) -> None:
        items = self._get_items_with_group(group)
        for item in items:
            new_groups = item.groups - set([group])
            self.set_groups(item.jid, new_groups)

    def rename_group(self, group: str, new_group: str) -> None:
        items = self._get_items_with_group(group)
        for item in items:
            new_groups = item.groups - set([group])
            new_groups.add(new_group)
            self.set_groups(item.jid, new_groups)

    def change_group(self, jid: JID, old_group: str, new_group: str) -> None:
        item = self.get_item(jid)
        assert item is not None
        groups = set(item.groups)
        groups.discard(old_group)
        groups.add(new_group)
        self._nbxmpp('Roster').set_item(jid, item.name, groups)

    def iter(self) -> Iterator[tuple[JID, RosterItem]]:
        for jid, data in self._roster.items():
            yield jid, data

    def iter_contacts(self) -> Iterator[BareContact]:
        for jid in self._roster:
            yield self._get_contact(jid)
