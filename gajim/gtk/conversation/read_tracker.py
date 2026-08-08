# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import logging

from gi.repository import GLib

from gajim.common.storage.archive.const import ChatDirection

from gajim.gtk.conversation.rows.message import MessageRow
from gajim.gtk.conversation.rows.read_marker import ReadMarkerOverlay

if TYPE_CHECKING:
    from gajim.gtk.conversation.view import ConversationView

log = logging.getLogger("gajim.gtk.conversation.read_tracker")

READ_DWELL_MS = 3000


class ReadTracker:
    """Viewport dwell → MDS, plus open-time read-marker visibility.

    `_open_marker_id` represents a pending marker and `_marker` a visible one.
    """

    def __init__(self, view: ConversationView) -> None:
        self._view = view
        self._last_read_id: str | None = None
        self._open_marker_id: str | None = None
        self._marker: ReadMarkerOverlay | None = None
        self._dwell: dict[int, int] = {}  # orig_pk → timeout source
        self._emitted_pks: set[int] = set()
        self._idle_id: int | None = None

    def reset(self) -> None:
        self._cancel_all()
        self._emitted_pks.clear()
        self._last_read_id = None
        self._open_marker_id = None
        marker = self._marker
        self._marker = None
        if marker is not None:
            # Tear down immediately; never leave a fade callback alive across
            # chat switches / shutdown.
            self._view.remove_read_marker(marker)

    def bind(self, last_read_id: str | None) -> None:
        """Capture open-time marker id from persisted MDS when switching chats."""
        self.reset()
        self._last_read_id = last_read_id
        self._open_marker_id = last_read_id

    def update_last_read(self, marker_id: str) -> None:
        """Live MDS position advanced (does not move the open-time visual marker)."""
        self._last_read_id = marker_id
        row = self._view.get_message_row_by_marker_id(marker_id)
        if row is not None:
            self._emitted_pks.add(row.orig_pk)
            self._cancel_dwell(row.orig_pk)

    def schedule(self) -> None:
        if self._idle_id is None:
            self._idle_id = GLib.idle_add(self._on_idle)

    def message_added(self, row: MessageRow, show_marker: bool) -> None:
        if (
            show_marker
            and row.direction == ChatDirection.INCOMING
            and not row.is_retracted
            and self._last_read_id is not None
            and self._open_marker_id is None
        ):
            self._dismiss()
            self._open_marker_id = self._last_read_id
        self.schedule()

    def flush(self) -> None:
        """Cancel timers; persist the newest in-flight dwell first."""
        self._cancel_idle()
        self._flush_in_flight_dwell()
        self._cancel_dwells()

    def _flush_in_flight_dwell(self) -> None:
        """Emit read-up-to for the newest message that had a dwell timer running."""
        if not self._dwell:
            return

        best: MessageRow | None = None
        for pk in self._dwell:
            row = self._view.get_message_row_by_pk(pk)
            if (
                row is None
                or row.direction != ChatDirection.INCOMING
                or row.orig_stanza_id is None
            ):
                continue
            if best is None or (row.timestamp, row.orig_pk) > (
                best.timestamp,
                best.orig_pk,
            ):
                best = row

        if best is not None:
            self._emit_read_up_to(best)

    def _on_idle(self) -> bool:
        self._idle_id = None
        self._finalize_pending_marker()
        self._update_dwell()
        return GLib.SOURCE_REMOVE

    def _finalize_pending_marker(self) -> None:
        """Evaluate the marker after a complete row-insertion cycle.

        History is added one row at a time. Evaluating synchronously
        would dismiss the marker when the last-read row is inserted, before
        the unread rows that follow it have been added.
        """
        if self._open_marker_id is None or self._marker is not None:
            return

        view = self._view
        reference = view.get_read_marker_reference_row(self._open_marker_id)
        if reference is None:
            return

        if not view.has_incoming_after_message(reference):
            if view.get_lower_complete():
                self._open_marker_id = None
            return

        log.debug("Show read marker after message %s", self._open_marker_id)
        marker = ReadMarkerOverlay(self._dismiss)
        view.show_read_marker(marker, reference.orig_pk)
        marker.fade_in()
        self._marker = marker
        self._open_marker_id = None

    def _update_dwell(self) -> None:
        view = self._view
        if not view.can_track_reads():
            return

        view_height = view.get_height()
        if view_height <= 0:
            return

        last_read = (
            view.get_message_row_by_marker_id(self._last_read_id)
            if self._last_read_id is not None
            else None
        )
        last_read_position = (
            (last_read.timestamp, last_read.orig_pk) if last_read is not None else None
        )

        seen: set[int] = set()
        for row in view.iter_rows():
            if (
                not isinstance(row, MessageRow)
                or row.direction != ChatDirection.INCOMING
                or row.orig_stanza_id is None
            ):
                continue

            pk = row.orig_pk
            seen.add(pk)
            if pk in self._emitted_pks or (
                last_read_position is not None
                and (row.timestamp, pk) <= last_read_position
            ):
                self._emitted_pks.add(pk)
                self._cancel_dwell(pk)
                continue

            if view.get_row_visibility(row, view_height) == "full":
                if pk not in self._dwell:
                    self._dwell[pk] = GLib.timeout_add(
                        READ_DWELL_MS, self._on_dwell_completed, pk
                    )
                continue

            self._cancel_dwell(pk)

        for pk in self._dwell.keys() - seen:
            GLib.source_remove(self._dwell.pop(pk))

    def _on_dwell_completed(self, orig_pk: int) -> bool:
        self._dwell.pop(orig_pk, None)
        view = self._view
        if not view.can_track_reads():
            return GLib.SOURCE_REMOVE

        row = view.get_message_row_by_pk(orig_pk)
        if (
            row is None
            or row.direction != ChatDirection.INCOMING
            or row.orig_stanza_id is None
        ):
            return GLib.SOURCE_REMOVE
        if view.get_row_visibility(row, view.get_height()) != "full":
            return GLib.SOURCE_REMOVE

        self._emit_read_up_to(row)
        return GLib.SOURCE_REMOVE

    def _emit_read_up_to(self, row: MessageRow) -> None:
        assert row.orig_stanza_id is not None
        assert row.direction == ChatDirection.INCOMING
        if self._last_read_id in {row.orig_stanza_id, row.stanza_id}:
            self._emitted_pks.add(row.orig_pk)
            return

        if self._last_read_id is not None:
            current = self._view.get_message_row_by_marker_id(self._last_read_id)
            if current is not None and (row.timestamp, row.orig_pk) <= (
                current.timestamp,
                current.orig_pk,
            ):
                self._emitted_pks.add(row.orig_pk)
                return

        self._emitted_pks.add(row.orig_pk)
        self._last_read_id = row.orig_stanza_id
        log.debug(
            "Read up to %s (message id: %s)",
            row.orig_stanza_id,
            row.message_id,
        )
        self._view.clear_new_messages_target()
        self._view.emit(
            "read-up-to",
            row.orig_stanza_id,
            row.message_id or "",
        )

    def _dismiss(self) -> None:
        if self._marker is None:
            return

        marker = self._marker
        self._marker = None
        marker.fade_out(lambda: self._view.remove_read_marker(marker))

    def _cancel_all(self) -> None:
        self._cancel_idle()
        self._cancel_dwells()

    def _cancel_idle(self) -> None:
        if self._idle_id is not None:
            GLib.source_remove(self._idle_id)
            self._idle_id = None

    def _cancel_dwells(self) -> None:
        for source_id in self._dwell.values():
            GLib.source_remove(source_id)
        self._dwell.clear()

    def _cancel_dwell(self, pk: int) -> None:
        source_id = self._dwell.pop(pk, None)
        if source_id is not None:
            GLib.source_remove(source_id)
