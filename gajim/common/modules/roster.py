# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Roster

from __future__ import annotations

from typing import cast

from collections.abc import Iterable
from collections.abc import Iterator

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
from gajim.common.events import RosterPush
from gajim.common.events import RosterReceived
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
            version, callback=self._on_request_roster)  # type: ignore

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
                             _con: types.NBXMPPClient,
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

    def get_item(self, jid: JID) -> RosterItem | None:
        return self._roster.get(jid)

    def set_groups(self, jid: JID, groups: Iterable[str] | None) -> None:
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
            new_groups = item.groups - {group}
            self.set_groups(item.jid, new_groups)

    def rename_group(self, group: str, new_group: str) -> None:
        items = self._get_items_with_group(group)
        for item in items:
            new_groups = item.groups - {group}
            new_groups.add(new_group)
            self.set_groups(item.jid, new_groups)

    def change_group(self, jid: JID, old_group: str, new_group: str) -> None:
        item = self.get_item(jid)
        assert item is not None
        groups = set(item.groups)
        groups.discard(old_group)
        groups.add(new_group)
        self._nbxmpp('Roster').set_item(jid, item.name, groups)

    def add_to_group(self, jid: JID, group: str) -> None:
        item = self.get_item(jid)
        assert item is not None
        new_groups = item.groups | {group}
        self._nbxmpp('Roster').set_item(jid, item.name, new_groups)

    def remove_from_group(self, jid: JID, group: str) -> None:
        item = self.get_item(jid)
        assert item is not None
        new_groups = item.groups - {group}
        self._nbxmpp('Roster').set_item(jid, item.name, new_groups)

    def change_name(self, jid: JID, name: str | None) -> None:
        item = self.get_item(jid)
        assert item is not None
        self._nbxmpp('Roster').set_item(jid, name, item.groups)

    def iter(self) -> Iterator[tuple[JID, RosterItem]]:
        yield from self._roster.items()

    def iter_contacts(self) -> Iterator[BareContact]:
        for jid in self._roster:
            yield cast(BareContact, self._get_contact(jid))
