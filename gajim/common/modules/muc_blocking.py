# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

from collections import defaultdict

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import MessageProperties

from gajim.common import app
from gajim.common import types
from gajim.common.events import MucUserBlockChanged
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node

GAJIM_BLOCKING_NS = "urn:gajim:blocking:1"

BlockedMucUsersT = dict[JID, set[str]]


class MucBlocking(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._bookmark_1_event_received)

        self._blocked_muc_users: BlockedMucUsersT = defaultdict(set)
        occupants = app.storage.archive.get_blocked_occupants(self._account)
        for occupant in occupants:
            self._blocked_muc_users[occupant.remote.jid].add(occupant.id)

    def _sync_muc_blocks(self) -> bool:
        if not self._client.get_module("Bookmarks").nativ_bookmarks_used:
            return False

        return app.settings.get_account_setting(self._account, "sync_muc_blocks")

    @event_node(Namespace.BOOKMARKS_1)
    def _bookmark_1_event_received(
        self, _con: types.NBXMPPClient, stanza: Any, properties: MessageProperties
    ) -> None:

        if not self._sync_muc_blocks():
            return

        event = properties.pubsub_event
        assert event is not None
        if event.deleted or event.purged:
            self._log.info("Node deleted or purged")
            self._blocked_muc_users.clear()
            app.storage.archive.set_block_occupant(self._account, None, [], False)
            app.ged.raise_event(MucUserBlockChanged(account=self._account))
            return

        if event.retracted:
            self._log.info("Retracted: %s", event.id)
            assert event.id is not None
            try:
                jid = JID.from_string(event.id)
            except Exception as error:
                self._log.warning(
                    "Unable to parse retracted id: %s %s", event.id, error
                )
                self._log.warning(stanza)
                return

            self._blocked_muc_users.pop(jid, None)
            app.storage.archive.set_block_occupant(self._account, jid, [], False)
            app.ged.raise_event(MucUserBlockChanged(account=self._account, jid=jid))
            return

        self._log.info("Update received: %s", event.id)
        bookmark = cast(BookmarkData, event.data)
        if self._act_on_changed_blocks(bookmark):
            app.ged.raise_event(
                MucUserBlockChanged(account=self._account, jid=bookmark.jid)
            )

    def get_blocking_list(self, jid: JID) -> set[str]:
        return self._blocked_muc_users.get(jid) or set()

    def is_blocked(self, jid: JID, occupant_id: str | None) -> bool:
        if not occupant_id:
            return False

        return occupant_id in self._blocked_muc_users[jid]

    def pass_bookmarks(self, bookmarks: list[BookmarkData]) -> None:
        if not self._sync_muc_blocks():
            return

        self._log.info("Received bookmarks")
        self._blocked_muc_users.clear()
        blocks_changed = False
        for bookmark in bookmarks:
            blocks_changed |= self._act_on_changed_blocks(bookmark)

        if blocks_changed:
            app.ged.raise_event(MucUserBlockChanged(account=self._account))

    def _act_on_changed_blocks(self, bookmark: BookmarkData) -> bool:
        try:
            new_occupant_ids = parse_blocked_occupants(bookmark.extensions)
        except Exception as error:
            self._log.warning("Unable to parse blocking extension:%s", error)
            self._log.warning(bookmark)
            return False

        if new_occupant_ids is None:
            # None means there was never blocking information published
            # to this bookmark, this is different from an empty blocking list
            return False

        jid = bookmark.jid
        old_occupant_ids = self._blocked_muc_users[jid]
        if new_occupant_ids == old_occupant_ids:
            self._log.info("%s: no changes found", jid)
            return False

        self._blocked_muc_users[jid] = new_occupant_ids

        added = new_occupant_ids - old_occupant_ids
        removed = old_occupant_ids - new_occupant_ids

        if added:
            app.storage.archive.set_block_occupant(
                self._account, jid, list(added), True
            )
        if removed:
            app.storage.archive.set_block_occupant(
                self._account, jid, list(removed), False
            )

        self._log.info(
            "Received blocks for %s, added: %s, removed: %s", jid, added, removed
        )
        return True

    def set_block_occupants(
        self, jid: JID, occupant_ids: list[str], block: bool
    ) -> None:
        if not occupant_ids:
            self._log.warning(
                "Unable to block contact because occupant id is not available"
            )
            return

        for occupant_id in occupant_ids:
            self._log.info(
                "%s user: %s %s", "Block" if block else "Unblock", jid, occupant_id
            )

        bookmark = self._client.get_module("Bookmarks").get_bookmark(jid)
        if bookmark is None:
            self._log.warning("Unable to block user, no bookmark found")
            return

        current_blocks = self._blocked_muc_users[jid]
        if block:
            current_blocks.update(occupant_ids)
        else:
            current_blocks.difference_update(occupant_ids)

        app.storage.archive.set_block_occupant(self._account, jid, occupant_ids, block)

        app.ged.raise_event(MucUserBlockChanged(account=self._account, jid=jid))

        if not self._sync_muc_blocks():
            return

        extensions = create_extensions_node(bookmark.extensions, current_blocks)
        print(extensions)
        self._client.get_module("Bookmarks").modify(jid, extensions=extensions)

    def merge_blocks(self) -> None:
        if not self._client.get_module("Bookmarks").nativ_bookmarks_used:
            return

        for bookmark in self._client.get_module("Bookmarks").bookmarks:
            local_occupant_ids = self.get_blocking_list(bookmark.jid)

            try:
                remote_occupant_ids = (
                    parse_blocked_occupants(bookmark.extensions) or set()
                )
            except Exception as error:
                self._log.warning("Unable to parse blocking extension:%s", error)
                self._log.warning(bookmark)
                continue

            remote_occupant_ids.update(local_occupant_ids)
            if not remote_occupant_ids:
                # Nothing to sync
                continue

            extensions = create_extensions_node(
                bookmark.extensions, remote_occupant_ids
            )
            self._client.get_module("Bookmarks").modify(
                bookmark.jid, extensions=extensions
            )

    def cleanup(self) -> None:
        BaseModule.cleanup(self)
        self._blocked_muc_users.clear()


def create_extensions_node(
    extensions: nbxmpp.Node | None, blocked_occupants: set[str]
) -> nbxmpp.Node:
    if extensions is None:
        extensions = nbxmpp.Node("extensions", attrs={"xmlns": "urn:xmpp:bookmarks:1"})
    else:
        extensions = nbxmpp.Node(
            node=str(extensions), attrs={"xmlns": "urn:xmpp:bookmarks:1"}
        )

    nodes = list(extensions.iterTags("blocking", namespace=GAJIM_BLOCKING_NS))
    for node in nodes:
        extensions.delChild(node)

    blocking = build_blocking_node(blocked_occupants)
    extensions.addChild(node=blocking)
    return extensions


def build_blocking_node(occupant_ids: set[str]) -> nbxmpp.Node:
    blocking = nbxmpp.Node(tag="blocking", attrs={"xmlns": GAJIM_BLOCKING_NS})
    for occupant_id in occupant_ids:
        blocking.addChild("occupant", attrs={"id": occupant_id})
    return blocking


def parse_blocked_occupants(extension: nbxmpp.Node | None) -> set[str] | None:
    if extension is None:
        return None

    blocking = extension.getTag("blocking", namespace=GAJIM_BLOCKING_NS)
    if blocking is None:
        return None

    occupant_ids: set[str] = set()
    for occupant in blocking.getTags("occupant"):
        occupant_id = occupant.getAttr("id")
        if not occupant_id:
            continue
        occupant_ids.add(occupant_id)

    return occupant_ids
