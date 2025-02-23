# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import time
from pathlib import Path

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.events import FileCompleted
from gajim.common.events import FileError
from gajim.common.events import FileHashError
from gajim.common.events import FileProgress
from gajim.common.events import FileRequestError
from gajim.common.events import FileRequestReceivedEvent
from gajim.common.events import FileRequestSent
from gajim.common.events import FileSendError
from gajim.common.events import JingleErrorReceived
from gajim.common.events import JingleFtCancelledReceived
from gajim.common.file_props import FileProp
from gajim.common.file_props import FilesProp
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.util.datetime import utc_now
from gajim.common.util.text import format_eta
from gajim.common.util.uri import open_file
from gajim.common.util.uri import show_in_folder

from gajim.gtk.builder import get_builder
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import NicknameLabel

TransferEventT = FileRequestReceivedEvent | FileRequestSent

log = logging.getLogger("gajim.gtk.conversation.rows.file_transfer_jingle")


class FileTransferJingleRow(BaseRow, EventHelper):
    def __init__(
        self,
        account: str,
        contact: BareContact,
        event: TransferEventT | None = None,
        message: mod.Message | None = None,
    ) -> None:
        BaseRow.__init__(self, account)
        EventHelper.__init__(self)

        self.type = "file-transfer"

        if message is not None:
            timestamp = message.timestamp
        else:
            timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self.db_timestamp = timestamp.timestamp()

        self._contact = contact

        if message is not None and message.filetransfers:
            # TODO: Handle filetransfers and sources specifically
            file_transfer = message.filetransfers[0]
            sources = file_transfer.source
            for source in sources:
                if isinstance(source, mod.JingleFT):
                    self._file_props = FilesProp.getFilePropBySid(source.sid)
                    if self._file_props is None:
                        log.debug("File prop not found for SID: %s", source.sid)
            self.pk = message.pk
        else:
            assert event is not None
            self._file_props = event.file_props
        self._start_time = 0

        if app.settings.get("use_kib_mib"):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        avatar_placeholder.set_valign(Gtk.Align.START)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        if message is not None:
            if message.direction == ChatDirection.INCOMING:
                contact = self._contact
                is_self = True
            else:
                bare_contact = self._client.get_module("Contacts").get_contact(
                    self._client.get_own_jid().bare
                )
                assert isinstance(bare_contact, BareContact)
                contact = bare_contact
                is_self = False
        else:
            if isinstance(event, FileRequestSent):
                bare_contact = self._client.get_module("Contacts").get_contact(
                    self._client.get_own_jid().bare
                )
                assert isinstance(bare_contact, BareContact)
                contact = bare_contact
                is_self = False
            else:
                contact = self._contact
                is_self = True

        scale = self.get_scale_factor()
        avatar = contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
        assert not isinstance(avatar, GdkPixbuf.Pixbuf)
        avatar_image = Gtk.Image.new_from_paintable(avatar)
        avatar_placeholder.append(avatar_image)

        name_widget = NicknameLabel(contact.name, is_self)
        name_widget.set_halign(Gtk.Align.START)
        name_widget.set_valign(Gtk.Align.START)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_hexpand(True)
        timestamp_widget.set_valign(Gtk.Align.START)

        meta_box = Gtk.Box()
        meta_box.set_spacing(6)
        meta_box.append(name_widget)
        meta_box.append(timestamp_widget)
        self.grid.attach(meta_box, 1, 0, 1, 1)

        self._ui = get_builder("file_transfer_jingle.ui")
        self.grid.attach(self._ui.transfer_box, 1, 1, 1, 1)
        self._ui.transfer_box.set_halign(Gtk.Align.START)

        self._connect(
            self._ui.accept_file_request, "clicked", self._on_accept_file_request
        )
        self._connect(
            self._ui.reject_file_request, "clicked", self._on_reject_file_request
        )
        self._connect(self._ui.open_folder, "clicked", self._on_open_folder)
        self._connect(self._ui.open_file, "clicked", self._on_open_file)
        self._connect(self._ui.error_show_transfers, "clicked", self._on_show_transfers)
        self._connect(self._ui.retry_bad_hash, "clicked", self._on_bad_hash_retry)
        self._connect(
            self._ui.rejected_show_transfers, "clicked", self._on_show_transfers
        )
        self._connect(self._ui.cancel_transfer, "clicked", self._on_cancel_transfer)

        if message is not None:
            self._reconstruct_transfer()
        else:
            assert event is not None
            self._display_transfer_info(event.name)

        if self._file_props is None:
            return

        self.register_events(
            [
                ("file-completed", ged.GUI1, self.process_event),
                ("file-hash-error", ged.GUI1, self.process_event),
                ("file-send-error", ged.GUI1, self.process_event),
                ("file-request-error", ged.GUI1, self.process_event),
                ("file-progress", ged.GUI1, self.process_event),
                ("file-error", ged.GUI1, self.process_event),
                ("jingle-error-received", ged.GUI1, self.process_event),
                ("jingle-ft-cancelled-received", ged.GUI1, self.process_event),
            ]
        )

    def do_unroot(self) -> None:
        self.unregister_events()
        BaseRow.do_unroot(self)

    def _reconstruct_transfer(self) -> None:
        self._show_file_infos()
        if self._file_props is None:
            self._ui.transfer_action.set_text(_("File Transfer"))
            self._ui.error_label.set_text(_("No info available"))
            self._ui.action_stack.set_visible_child_name("error")
            return

        if self._file_props.completed:
            self._show_completed()
            return

        if self._file_props.stopped:
            self._ui.action_stack.set_visible_child_name("error")
            self._ui.transfer_action.set_text(_("File Transfer Stopped"))
            self._ui.error_label.set_text("")
            return

        if self._file_props.error is not None:
            self._show_error(self._file_props)
            return

        self._ui.transfer_action.set_text(_("File Offered…"))

    def _display_transfer_info(self, event_name: str) -> None:
        if event_name == "file-request-sent":
            self._ui.action_stack.set_visible_child_name("progress")
            self._ui.progress_label.set_text(_("Waiting…"))

        self._ui.transfer_action.set_text(_("File Offered…"))
        self._show_file_infos()

    def _show_file_infos(self) -> None:
        if self._file_props is None:
            self._ui.file_name.set_visible(False)
            self._ui.file_description.set_visible(False)
            self._ui.file_size.set_visible(False)
            return

        file_name = GLib.markup_escape_text(str(self._file_props.name))
        if self._file_props.mime_type:
            file_name = f"{file_name} ({self._file_props.mime_type})"
        self._ui.file_name.set_text(file_name)
        self._ui.file_name.set_tooltip_text(file_name)

        if self._file_props.desc:
            desc = GLib.markup_escape_text(self._file_props.desc)
            self._ui.file_description.set_text(desc)
            self._ui.file_description.set_tooltip_text(desc)
        else:
            self._ui.file_description.set_visible(False)

        assert self._file_props.size is not None
        self._ui.file_size.set_text(
            GLib.format_size_full(self._file_props.size, self._units)
        )

    def process_event(self, event: TransferEventT) -> None:
        assert self._file_props is not None

        if isinstance(event, JingleErrorReceived):
            if event.sid != self._file_props.sid:
                return
            self._ui.action_stack.set_visible_child_name("error")
            self._ui.transfer_action.set_text(_("File Transfer Cancelled"))
            self._ui.error_label.set_text(event.reason)
            return

        if isinstance(event, JingleFtCancelledReceived):
            if event.sid != self._file_props.sid:
                return
            self._ui.action_stack.set_visible_child_name("error")
            self._ui.transfer_action.set_text(_("File Transfer Cancelled"))
            self._ui.error_label.set_text(
                _("%(name)s cancelled the transfer (%(reason)s)")
                % {"name": self._contact.name, "reason": event.reason}
            )
            return

        if event.file_props.sid != self._file_props.sid:
            return

        if isinstance(event, FileCompleted):
            self._show_completed()
        elif isinstance(event, FileError):
            self._show_error(event.file_props)
        elif isinstance(event, FileHashError):
            self._ui.action_stack.set_visible_child_name("hash-error")
            self._ui.transfer_action.set_text(_("File Verification Failed"))
        elif isinstance(event, FileRequestError | FileSendError):
            self._ui.action_stack.set_visible_child_name("error")
            self._ui.transfer_action.set_text(_("File Transfer Cancelled"))
            error_text = (
                _("Connection with %s could not be established.") % self._contact.name
            )
            if event.error_msg:
                error_text = f"{error_text} ({event.error_msg})"
            self._ui.error_label.set_text(error_text)

        elif isinstance(event, FileProgress):
            self._update_progress(event.file_props)

    def _update_progress(self, file_props: FileProp) -> None:
        self._ui.action_stack.set_visible_child_name("progress")
        self._ui.transfer_action.set_text(_("Transferring File…"))

        time_now = time.time()
        full_size = file_props.size
        assert full_size is not None

        if file_props.type_ == "s":
            # We're sending a file
            if self._start_time == 0:
                self._start_time = time_now
                return
            if not file_props.transferred_size:
                return
            transferred_size = file_props.transferred_size[-1][1]
        else:
            # We're receiving a file
            transferred_size = file_props.received_len
            assert transferred_size is not None

        if full_size == 0:
            return

        bytes_sec = int(round(transferred_size / (time_now - self._start_time), 1))
        speed = f"{GLib.format_size_full(bytes_sec, self._units)}/s"
        self._ui.progress_label.set_tooltip_text(_("Speed: %s") % speed)

        if bytes_sec == 0:
            eta = "∞"
        else:
            eta = format_eta(round((full_size - transferred_size) / bytes_sec))

        progress = float(transferred_size) / full_size
        self._ui.progress_label.set_text(
            _("%(progress)s %% (%(time)s remaining)")
            % {"progress": round(progress * 100), "time": eta}
        )

        self._ui.progress_bar.set_fraction(progress)

    def _show_error(self, file_props: FileProp) -> None:
        self._ui.action_stack.set_visible_child_name("error")
        self._ui.transfer_action.set_text(_("File Transfer Stopped"))
        if file_props.error == -1:
            self._ui.error_label.set_text(
                _("%s stopped the transfer") % self._contact.name
            )
        elif file_props.error == -6:
            self._ui.error_label.set_text(_("Error opening file"))
        elif file_props.error == -12:
            self._ui.error_label.set_text(_("SSL certificate error"))
        else:
            self._ui.error_label.set_text(_("An error occurred"))

    def _show_completed(self) -> None:
        self._ui.action_stack.set_visible_child_name("complete")
        self._ui.transfer_action.set_text(_("File Transfer Completed"))

    def _on_accept_file_request(self, _button: Gtk.Button) -> None:
        pass
        # app.interface.instances["file_transfers"].on_file_request_accepted(
        #     self._account, self._contact, self._file_props
        # )
        # self._start_time = time.time()

    def _on_reject_file_request(self, _button: Gtk.Button) -> None:
        assert self._file_props is not None
        self._client.get_module("Bytestream").send_file_rejection(self._file_props)
        assert self._file_props is not None
        self._file_props.stopped = True
        self._ui.action_stack.set_visible_child_name("rejected")
        self._ui.transfer_action.set_text(_("File Transfer Cancelled"))

    def _on_open_file(self, _button: Gtk.Button) -> None:
        assert self._file_props is not None
        assert self._file_props.file_name is not None
        open_file(Path(self._file_props.file_name))

    def _on_open_folder(self, _button: Gtk.Button) -> None:
        assert self._file_props is not None
        assert self._file_props.file_name is not None
        show_in_folder(Path(self._file_props.file_name))

    def _on_bad_hash_retry(self, _button: Gtk.Button) -> None:
        pass
        # app.interface.instances["file_transfers"].show_hash_error(
        #     self._contact.jid, self._file_props, self._account
        # )

    def _on_cancel_transfer(self, _button: Gtk.Button) -> None:
        pass
        # app.interface.instances["file_transfers"].cancel_transfer(self._file_props)

    def _on_show_transfers(self, _button: Gtk.Button) -> None:
        pass
        # file_transfers = app.interface.instances["file_transfers"]
        # if file_transfers.window.get_property("visible"):
        #     file_transfers.window.present()
        # else:
        #     file_transfers.window.show_all()
