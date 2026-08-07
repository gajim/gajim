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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import cast

from dataclasses import dataclass
from dataclasses import replace

from nbxmpp.errors import BaseError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import MDSData
from nbxmpp.structs import MessageProperties
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.events import MessageAcknowledged
from gajim.common.events import MessageReceived
from gajim.common.events import ReadStateSync
from gajim.common.events import SignedIn
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.util import event_node
from gajim.common.storage.archive.models import Message
from gajim.common.util.decorators import event_filter


@dataclass(frozen=True, slots=True)
class _PendingDisplayed:
    stanza_id: str
    message_id: str | None
    send_chat_marker: bool
    by: JID | None
    archive_jid: JID


@dataclass(frozen=True, slots=True)
class _PendingRemote:
    """Remote displayed state waiting for its target message in the archive."""

    marker_id: str
    by: JID | None
    archive_jid: JID


class MDS(BaseModule):
    _nbxmpp_extends = "MDS"
    _nbxmpp_methods = ["set_mds"]

    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)
        self._register_pubsub_handler(self._mds_received)
        self._pending_publish: dict[JID, _PendingDisplayed] = {}
        self._in_flight: dict[JID, str] = {}
        self._pending_remote: dict[JID, _PendingRemote] = {}
        # Snapshot of MDS roster after a successful get_mds (jid → stanza-id)
        self._remote_mds: dict[JID, str] = {}
        self._mds_roster_fetched = False
        self.register_events(
            [
                ("signed-in", ged.CORE, self._on_signed_in),
                ("message-acknowledged", ged.CORE, self._on_message_acknowledged),
                ("message-received", ged.CORE, self._on_message_received),
            ]
        )

    def cleanup(self) -> None:
        self._pending_publish.clear()
        self._in_flight.clear()
        self._pending_remote.clear()
        self._remote_mds.clear()
        self._mds_roster_fetched = False
        BaseModule.cleanup(self)

    def request_mds(self) -> None:
        self._log.info("Request MDS")
        self._nbxmpp("MDS").get_mds(callback=self._mds_items_received)

    def publish_displayed(
        self,
        contact: types.ChatContactT,
        stanza_id: str,
        message_id: str | None = None,
        *,
        send_chat_marker: bool = True,
    ) -> bool:
        """Persist displayed state locally; publish remotely when allowed.

        Local storage always runs so offline / MAM catch-up reading is not lost.
        Chat markers and MDS PEP are deferred until connected and catch-up finishes.
        """
        by = contact.jid if isinstance(contact, GroupchatContact) else None
        if not self.store_displayed(contact.jid, stanza_id, by):
            return False

        pending = _PendingDisplayed(
            stanza_id=stanza_id,
            message_id=message_id,
            send_chat_marker=send_chat_marker,
            by=by,
            archive_jid=self._archive_jid_for_contact(contact),
        )
        if not self._publish_remote(contact.jid, contact, pending):
            self._pending_publish[contact.jid] = pending
            self._log.info(
                "Defer MDS publish for %s until connected and catch-up finished",
                contact.jid,
            )
        return True

    def store_displayed(self, jid: JID, stanza_id: str, by: JID | None = None) -> bool:
        """Persist a new displayed state locally if it moves forward."""
        stanza_id_by = by or self._client.get_own_jid().new_as_bare()
        return (
            self._store_read_state(
                MDSData(jid=jid, stanza_id=stanza_id, stanza_id_by=stanza_id_by),
                allow_unresolved=True,
            )
            is True
        )

    def queue_remote_displayed(
        self, jid: JID, marker_id: str, *, by: JID | None = None
    ) -> None:
        """Apply a remote displayed marker, or queue it until the message exists."""
        if self._try_apply_remote_marker(jid, marker_id, by):
            return

        self._queue_remote(jid, marker_id, by)

    def _queue_remote(self, jid: JID, marker_id: str, by: JID | None) -> None:
        pending = _PendingRemote(
            marker_id=marker_id,
            by=by,
            archive_jid=self._archive_jid_for_remote(by),
        )
        if self._pending_remote.get(jid) == pending:
            return

        self._log.info(
            "Queue remote displayed for %s until message %s is in archive",
            jid,
            marker_id,
        )
        self._pending_remote[jid] = pending
        # Keep open chats live even before persistence
        self._emit_read_state(jid, marker_id)

    def _emit_read_state(self, jid: JID, marker_id: str) -> None:
        app.ged.raise_event(
            ReadStateSync(account=self._account, jid=jid, marker_id=marker_id)
        )

    def flush_pending_publishes(self, archive_jid: JID | None = None) -> None:
        """Publish deferred states and retry unresolved remote markers."""
        self.flush_pending_remote(archive_jid)
        read_states = app.storage.archive.iter_last_read_ids(self._account)
        self._queue_local_ahead_publishes(read_states, archive_jid)

        if app.account_is_connected(self._account):
            mam = self._client.get_module("MAM")
            for jid, pending in list(self._pending_publish.items()):
                if archive_jid is not None and pending.archive_jid != archive_jid:
                    continue
                if not mam.is_archive_catch_up_finished(pending.archive_jid):
                    continue

                contact = self._chat_contact(jid)
                self._publish_remote(jid, contact, pending)

        self._reconcile_unread(read_states, archive_jid)

    def _reconcile_unread(
        self, read_states: list[tuple[JID, str]], archive_jid: JID | None = None
    ) -> None:
        """Recompute chat-list unread from persisted last_read_id values.

        Called after MAM catch-up so badges match the archive regardless of
        whether MDS/MAM callbacks raced while messages were still arriving.
        """
        mam = self._client.get_module("MAM")
        own_archive = self._client.get_own_jid().new_as_bare()

        for jid, stanza_id in read_states:
            contact = self._chat_contact(jid)
            if contact is not None:
                contact_archive = self._archive_jid_for_contact(contact)
            elif archive_jid is not None and jid == archive_jid:
                contact_archive = jid
            else:
                contact_archive = own_archive

            if archive_jid is not None and contact_archive != archive_jid:
                continue
            if not mam.is_archive_catch_up_finished(contact_archive):
                continue

            self._emit_read_state(jid, stanza_id)

    def flush_pending_remote(self, archive_jid: JID | None = None) -> None:
        """Retry remote markers whose target messages may now be in the archive."""
        for pending_jid, pending in list(self._pending_remote.items()):
            if archive_jid is not None and pending.archive_jid != archive_jid:
                continue
            self._retry_remote_marker(pending_jid, pending)

    def _retry_remote_marker(self, jid: JID, pending: _PendingRemote) -> None:
        if (
            self._try_apply_remote_marker(jid, pending.marker_id, pending.by)
            and self._pending_remote.get(jid) is pending
        ):
            self._pending_remote.pop(jid, None)

    def _try_apply_remote_marker(
        self, jid: JID, marker_id: str, by: JID | None
    ) -> bool:
        """Apply a resolved remote marker.

        Returns True if applied or obsolete (pending can be dropped).
        """
        message = app.storage.archive.get_message_for_marker(
            self._account, jid, marker_id
        )
        if message is None or message.stanza_id is None:
            return False

        stanza_id_by = by or self._client.get_own_jid().new_as_bare()
        result = self._store_read_state(
            MDSData(jid=jid, stanza_id=message.stanza_id, stanza_id_by=stanza_id_by),
            resolved_message=message,
        )
        return result is not None

    @event_filter(["account"])
    def _on_signed_in(self, _event: SignedIn) -> None:
        self.flush_pending_publishes()

    @event_filter(["account"])
    def _on_message_received(self, event: MessageReceived) -> None:
        pending = self._pending_remote.get(event.jid)
        if pending is not None:
            self._retry_remote_marker(event.jid, pending)

    @event_filter(["account"])
    def _on_message_acknowledged(self, event: MessageAcknowledged) -> None:
        if event.stanza_id is None:
            return

        contact = self._chat_contact(event.jid)
        if contact is None:
            return

        self.publish_displayed(
            contact,
            event.stanza_id,
            send_chat_marker=False,
        )

    def _publish_remote(
        self,
        jid: JID,
        contact: types.ChatContactT | None,
        pending: _PendingDisplayed,
    ) -> bool:
        """Start remote publish. Returns True if a publish attempt was started.

        Pending state is only cleared after set_mds succeeds or PEP confirms it.
        """
        if not self._mds_roster_fetched or not app.account_is_connected(self._account):
            return False

        if not self._client.get_module("MAM").is_archive_catch_up_finished(
            pending.archive_jid
        ):
            return False

        # Keep / refresh pending until success callback
        self._pending_publish[jid] = pending

        if (
            pending.send_chat_marker
            and pending.message_id is not None
            and contact is not None
        ):
            mds_assist_sent = self._client.get_module(
                "ChatMarkers"
            ).send_displayed_marker(contact, pending.message_id, pending.stanza_id)
            if mds_assist_sent:
                # Keep a direct fallback until PEP confirms the assisted publish
                pending = replace(pending, send_chat_marker=False)
                self._pending_publish[jid] = pending

        # Serialize PEP publishes, but do not delay the immediate chat marker
        # for a newer displayed state while an older PEP update is in flight.
        if jid in self._in_flight:
            return True

        self._in_flight[jid] = pending.stanza_id
        self._nbxmpp("MDS").set_mds(
            jid,
            pending.stanza_id,
            pending.by,
            callback=self._on_mds_published,
            user_data=(jid, pending.stanza_id),
        )
        return True

    def _on_mds_published(self, task: Task) -> None:
        jid, stanza_id = cast(tuple[JID, str], task.get_user_data())
        if self._in_flight.get(jid) == stanza_id:
            self._in_flight.pop(jid, None)
        try:
            task.finish()
        except BaseError as error:
            self._log.warning("MDS publish failed for %s: %s", jid, error)
            return

        self._confirm_remote_state(jid, stanza_id)
        self._log.info("MDS published for %s", jid)

        pending = self._pending_publish.get(jid)
        if pending is not None:
            self._publish_remote(jid, self._chat_contact(jid), pending)

    def _confirm_remote_state(self, jid: JID, stanza_id: str) -> None:
        self._remote_mds[jid] = stanza_id
        pending = self._pending_publish.get(jid)
        if pending is not None and pending.stanza_id == stanza_id:
            self._pending_publish.pop(jid, None)

    def _archive_jid_for_contact(self, contact: types.ChatContactT) -> JID:
        if isinstance(contact, BareContact):
            return self._client.get_own_jid().new_as_bare()
        if isinstance(contact, GroupchatContact):
            return contact.jid
        return contact.room.jid

    def _chat_contact(self, jid: JID) -> types.ChatContactT | None:
        contact = self._get_contact_if_exists(jid)
        if isinstance(contact, BareContact | GroupchatContact | GroupchatParticipant):
            return contact
        return None

    def _mds_items_received(self, task: Task) -> None:
        try:
            data = cast(list[MDSData] | None, task.finish())
        except BaseError as error:
            self._log.info("Unable to request MDS: %s", error)
            return

        self._remote_mds.clear()
        self._mds_roster_fetched = True

        if not data:
            self._log.info("No MDS items found")
            self.flush_pending_publishes()
            return

        for mds_data in data:
            if mds_data.jid and mds_data.stanza_id:
                self._confirm_remote_state(mds_data.jid, mds_data.stanza_id)
            self._store_read_state(mds_data)

        self.flush_pending_publishes()

    @event_node(Namespace.MDS)
    def _mds_received(
        self, _client: types.Client, _stanza: Any, properties: MessageProperties
    ) -> None:
        if not properties.pubsub_event:
            return

        data = properties.pubsub_event.data
        if data is None:
            return

        assert isinstance(data, MDSData)
        if data.jid and data.stanza_id:
            self._confirm_remote_state(data.jid, data.stanza_id)
        self._store_read_state(data)

    def _queue_local_ahead_publishes(
        self,
        read_states: list[tuple[JID, str]],
        archive_jid: JID | None = None,
    ) -> None:
        """Republish local last_read_id values that are ahead of the MDS roster."""
        if not self._mds_roster_fetched or not app.account_is_connected(self._account):
            return

        mam = self._client.get_module("MAM")

        for jid, stanza_id in read_states:
            contact = self._chat_contact(jid)
            if contact is None:
                continue

            contact_archive = self._archive_jid_for_contact(contact)
            if archive_jid is not None and contact_archive != archive_jid:
                continue
            if not mam.is_archive_catch_up_finished(contact_archive):
                continue

            remote_id = self._remote_mds.get(jid)
            if remote_id == stanza_id or jid in self._pending_publish:
                continue

            local_msg = app.storage.archive.get_message_for_marker(
                self._account, jid, stanza_id
            )
            if local_msg is None:
                continue

            if remote_id is not None:
                remote_msg = app.storage.archive.get_message_for_marker(
                    self._account, jid, remote_id
                )
                if remote_msg is None or not self._is_newer(local_msg, remote_msg):
                    continue

            by = jid if isinstance(contact, GroupchatContact) else None
            self._log.info(
                "Queue MDS publish for local-ahead state %s (%s)", jid, stanza_id
            )
            self._pending_publish[jid] = _PendingDisplayed(
                stanza_id=stanza_id,
                message_id=local_msg.id,
                send_chat_marker=False,
                by=by,
                archive_jid=contact_archive,
            )

    def _store_read_state(
        self,
        data: MDSData,
        *,
        allow_unresolved: bool = False,
        resolved_message: Message | None = None,
    ) -> bool | None:
        if not data.jid or not data.stanza_id:
            self._log.warning("Received invalid MDS data: %s", data)
            return False

        current_id = app.storage.archive.get_contact_value(
            self._account, data.jid, "last_read_id"
        )
        if current_id == data.stanza_id:
            # Marker unchanged — still reconcile unread badges (e.g. after MAM)
            self._emit_read_state(data.jid, data.stanza_id)
            return False

        message = resolved_message
        if message is None and (current_id is not None or not allow_unresolved):
            message = app.storage.archive.get_message_for_marker(
                self._account, data.jid, data.stanza_id
            )
        if message is None and not allow_unresolved:
            self._queue_remote(data.jid, data.stanza_id, data.stanza_id_by)
            return None

        if current_id is not None and message is not None:
            current_message = app.storage.archive.get_message_for_marker(
                self._account, data.jid, current_id
            )
            if current_message is None:
                if not allow_unresolved:
                    self._queue_remote(data.jid, data.stanza_id, data.stanza_id_by)
                    return None
            elif not self._is_newer(message, current_message):
                # XEP-0490: displayed state only moves forward
                self._log.info(
                    "Ignore older MDS state: %s (current: %s)",
                    data.stanza_id,
                    current_id,
                )
                return False

        self._log.info("Read state (MDS): %s - %s", data.jid, data.stanza_id)
        app.storage.archive.set_read_state(self._account, data.jid, data.stanza_id)

        self._emit_read_state(data.jid, data.stanza_id)
        return True

    def _archive_jid_for_remote(self, by: JID | None) -> JID:
        if by is not None:
            return by
        return self._client.get_own_jid().new_as_bare()

    @staticmethod
    def _is_newer(message: Message, current: Message) -> bool:
        assert message.pk is not None and current.pk is not None
        return (message.timestamp, message.pk) > (current.timestamp, current.pk)
