# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import cast

import time

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import FTState
from gajim.common.i18n import _
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.util.datetime import utc_now
from gajim.common.util.text import format_eta

from gajim.gtk.builder import get_builder
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.dialogs import SimpleDialog


class FileTransferRow(BaseRow):
    def __init__(self, account: str, transfer: HTTPFileTransfer) -> None:
        BaseRow.__init__(self, account)

        self.type = "file-transfer"
        timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self.db_timestamp = timestamp.timestamp()

        self._destroyed: bool = False

        if app.settings.get("use_kib_mib"):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._start_time = time.time()
        self._pulse = GLib.timeout_add(100, self._pulse_progressbar)

        self._transfer = transfer
        self._transfer.connect("state-changed", self._on_transfer_state_change)
        self._transfer.connect("progress", self._on_transfer_progress)

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_halign(Gtk.Align.START)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 1, 0, 1, 1)

        self._ui = get_builder("file_transfer.ui")
        self.grid.attach(self._ui.transfer_box, 1, 1, 1, 1)

        self._connect(self._ui.cancel_button, "clicked", self._on_cancel_clicked)

        self._ui.file_name.set_text(transfer.filename)
        self._ui.transfer_description.set_text(transfer.get_state_description())

    def do_unroot(self) -> None:
        self._destroyed = True

        self._transfer.disconnect_all_from_obj(self)
        del self._transfer
        if self._pulse is not None:
            GLib.source_remove(self._pulse)

        BaseRow.do_unroot(self)

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        if self._transfer.state.is_active:
            self._transfer.cancel()

        cast(Gtk.ListBox, self.get_parent()).remove(self)

    def _on_transfer_state_change(
        self, transfer: HTTPFileTransfer, _signal_name: str, state: FTState
    ) -> None:
        if self._destroyed:
            return

        if state.is_error:
            SimpleDialog(_("Error"), transfer.error_text, transient_for=app.window)
            cast(Gtk.ListBox, self.get_parent()).remove(self)

        if state.is_finished or state.is_cancelled:
            cast(Gtk.ListBox, self.get_parent()).remove(self)
            return

        description = transfer.get_state_description()
        if description:
            self._ui.transfer_description.set_text(description)

    def _pulse_progressbar(self):
        self._ui.progress_bar.pulse()
        return True

    def _on_transfer_progress(
        self, transfer: HTTPFileTransfer, _signal_name: str
    ) -> None:
        if self._destroyed:
            return
        if self._pulse is not None:
            GLib.source_remove(self._pulse)
            self._pulse = None

        time_now = time.time()

        size_total = GLib.format_size_full(transfer.size, self._units)
        self._ui.file_size.set_text(size_total)

        progress = transfer.get_progress()
        seen = transfer.size * progress

        bytes_sec = int(round(seen / (time_now - self._start_time), 1))
        speed = f"{GLib.format_size_full(bytes_sec, self._units)}/s"
        self._ui.transfer_progress.set_tooltip_text(_("Speed: %s") % speed)

        if bytes_sec == 0:
            eta = "∞"
        else:
            eta = format_eta(round((transfer.size - seen) / bytes_sec))

        self._ui.transfer_progress.set_text(
            _("%(progress)s %% (%(time)s remaining)")
            % {"progress": round(progress * 100), "time": eta}
        )

        self._ui.progress_bar.set_fraction(progress)
