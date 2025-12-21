# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common.const import Display
from gajim.common.const import IMAGE_MIME_TYPES
from gajim.common.helpers import load_file_async
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.multiprocess.thumbnail import create_thumbnail
from gajim.common.util.preview import get_icon_for_mime_type
from gajim.common.util.preview import guess_mime_type
from gajim.common.util.uri import get_file_path_from_uri

from gajim.gtk.builder import get_builder
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.resource_selector import ResourceSelector
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import gi_gui_package_version
from gajim.gtk.util.misc import iterate_listbox_children

PREVIEW_SIZE = 72

log = logging.getLogger("gajim.gtk.file_transfer_selector")


class FileTransferSelector(Gtk.Box, SignalManager):
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self, contact: types.ChatContactT, method: str | None = None) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._contact = contact
        self._method = method or app.window.get_preferred_ft_method(contact)

        client = app.get_client(contact.account)
        self._max_http_file_size = client.get_module("HTTPUpload").max_file_size

        self._ui = get_builder("file_transfer_selector.ui", widgets=["stack"])
        self.append(self._ui.stack)

        last_dir = app.settings.get("last_send_dir") or None
        if last_dir is not None:
            last_dir = Path(last_dir)

        self._file_chooser_button = FileChooserButton(
            path=last_dir, multiple=True, label=_("Add Files…")
        )
        self._file_chooser_button.set_halign(Gtk.Align.CENTER)
        self._ui.box.append(self._file_chooser_button)

        self._connect(
            self._file_chooser_button, "path-picked", self._on_choose_files_clicked
        )

        # TODO Jingle FT
        # self._resource_selector = None

        # if isinstance(contact, BareContact):
        #     # No jingle file transfers in group chats
        #     self._resource_selector = ResourceSelector(
        #         contact,
        #         constraints=[Namespace.JINGLE_FILE_TRANSFER_5])
        #     self._connect(
        #         self._resource_selector,
        #         'selection-changed',
        #         self._on_resource_selection
        #     )
        #     self._ui.resource_box.prepend(
        #         self._resource_selector)

        #     self._ui.resource_instructions.set_text(
        #         _('%s is online with multiple devices.\n'
        #           'Choose the device you would like to send the '
        #           'files to.') % self._contact.name)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        self._connect(drop_target, "accept", self._on_drop_accept)
        self._connect(drop_target, "drop", self._on_file_drop)
        self.add_controller(drop_target)

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        self._disconnect_all()
        del self._file_chooser_button
        app.check_finalize(self)

    def _is_over_max_http_file_size(self, path: Path) -> bool:
        if self._max_http_file_size is None:
            return False

        if not path.exists():
            # Non-existing files are handled in the send_file method
            return False

        return path.stat().st_size > self._max_http_file_size

    def transfer_resource_required(self) -> bool:
        if not isinstance(self._contact, BareContact):
            # No jingle file transfer for group chats
            return False

        if self._method is None:
            log.error("No file transfer method available")
            return False

        current_page = self._ui.stack.get_visible_child_name()
        if self._method == "httpupload":
            for path in self._get_file_paths():
                if self._is_over_max_http_file_size(path):
                    if current_page == "resource-selection":
                        return False

                    self._ui.stack.set_visible_child_name("resource-selection")
                    self.emit("changed", False)
                    return True
            return False

        if current_page == "resource-selection":
            return False

        self._ui.stack.set_visible_child_name("resource-selection")
        self.emit("changed", False)
        return True

    def get_catalog(self) -> list[tuple[Path, str, JID]]:
        # catalog: list[(file Path, transfer method, recipient JID)]
        catalog: list[tuple[Path, str, JID]] = []

        file_paths = self._get_file_paths()
        for path in file_paths:
            # if (self._method == 'jingle' or
            #         self._is_over_max_http_file_size(path)):
            #     assert self._resource_selector is not None
            #     item = (path, 'jingle', self._resource_selector.get_jid())
            if self._method == "httpupload":
                item = (path, "httpupload", self._contact.jid)
            else:
                # No file transfer method available
                continue

            catalog.append(item)

        return catalog

    def add_files(self, uris: list[str]) -> None:
        for uri in uris:
            path = get_file_path_from_uri(uri)
            if path is None:
                self._add_warning_message("Could not add %s" % uri)
                continue

            size_warning = bool(
                self._method == "httpupload" and self._is_over_max_http_file_size(path)
            )
            jingle_warning = bool(self._method == "jingle")

            row = FileRow(path, size_warning, jingle_warning)
            self._connect(row, "removed", self._on_row_removed)
            self._ui.listbox.append(row)
            app.settings.set("last_send_dir", str(path.parent))

        self._on_files_changed()

    def _on_row_removed(self, row: FileRow) -> None:
        self._disconnect_object(row)
        self._ui.listbox.remove(row)
        self._on_files_changed()

    def _add_warning_message(self, msg: str) -> None:
        log.warning(msg)  # TODO: replace with UI

    def _get_file_paths(self) -> list[Path]:
        paths: list[Path] = []
        for row in cast(list[FileRow], iterate_listbox_children(self._ui.listbox)):
            paths.append(row.file_path)

        return paths

    def _on_drop_accept(self, _target: Gtk.DropTarget, drop: Gdk.Drop) -> bool:
        # DND on X11 freezes due to a GTK bug:
        # https://dev.gajim.org/gajim/gajim/-/issues/12313
        if app.is_display(Display.X11) and not gi_gui_package_version("Gtk>=4.20.1"):
            return False

        formats = drop.get_formats()
        return bool(formats.contain_gtype(Gdk.FileList))

    def _on_file_drop(
        self, _target: Gtk.DropTarget, value: Gdk.FileList | None, _x: float, _y: float
    ) -> bool:
        if value is None:
            log.debug("Drop received, but value is None")
            return False

        files = value.get_files()
        if not files:
            return False

        self.add_files([file.get_uri() for file in files])
        return True

    def _on_files_changed(self) -> None:
        file_paths = self._get_file_paths()
        if not file_paths:
            self.emit("changed", False)
            return

        # if self._method == 'httpupload' and self._contact.is_groupchat:
        #     # Enforce HTTPUpload file size limit for group chats
        #     for path in file_paths:
        #         if self._is_over_max_http_file_size(path):
        #             self.emit('changed', False)
        #             return

        if self._method == "httpupload":
            # Enforce HTTPUpload file size limit
            for path in file_paths:
                if self._is_over_max_http_file_size(path):
                    self.emit("changed", False)
                    return

        self.emit("changed", True)

    def _on_resource_selection(self, _selector: ResourceSelector, state: bool) -> None:
        self.emit("changed", state)

    def _on_choose_files_clicked(
        self, _button: FileChooserButton, paths: list[Path]
    ) -> None:
        self.add_files([p.as_uri() for p in paths])
        self._file_chooser_button.reset()


class FileRow(Gtk.ListBoxRow, SignalManager):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, path: Path, size_warning: bool, jingle_warning: bool) -> None:
        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)

        self.file_path = path

        self._ui = get_builder("file_transfer_selector.ui", widgets=["file_box"])
        self.set_child(self._ui.file_box)

        self._connect(self._ui.remove_file_button, "clicked", self._on_remove_clicked)

        self._ui.file_name_label.set_text(path.name)

        if app.settings.get("use_kib_mib"):
            units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            units = GLib.FormatSizeFlags.DEFAULT

        file_size_string = GLib.format_size_full(path.stat().st_size, units)
        self._ui.file_size_label.set_text(file_size_string)

        # if size_warning:
        #     self._ui.warning_label.set_text(
        #         _('File too big, will use direct transfer (not encrypted)'))
        #     self._ui.warning_label.set_visible(True)

        if size_warning:
            self._ui.warning_label.set_text(_("File too big"))
            self._ui.warning_label.set_visible(True)

        # if jingle_warning:
        #     self._ui.warning_label.set_text(
        #         _('Direct transfer (not encrypted)'))
        #     self._ui.warning_label.set_visible(True)

        self._ui.preview_image_box.set_size_request(PREVIEW_SIZE, -1)
        self._set_preview(path)

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def _set_preview(self, path: Path) -> None:
        mime_type = guess_mime_type(path)
        if mime_type not in IMAGE_MIME_TYPES:
            self._set_icon_for_mime_type(mime_type)
            return

        load_file_async(self.file_path, self._on_load_finished, mime_type)

    def _on_load_finished(
        self, data: bytes | None, _error: GLib.Error | None, mime_type: Any
    ) -> None:
        if data is None:
            self._set_icon_for_mime_type(mime_type)
            return

        try:
            thumbnail_bytes, _metadata = create_thumbnail(
                data, None, PREVIEW_SIZE, mime_type
            )
        except Exception as error:
            log.error("Failed to create thumbnail: %s", error)
            self._set_icon_for_mime_type(mime_type)
            return

        texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(thumbnail_bytes))

        self._ui.preview_image.set_from_paintable(texture)

    def _set_icon_for_mime_type(self, mime_type: str) -> None:
        icon = get_icon_for_mime_type(mime_type)
        self._ui.preview_image.set_from_gicon(icon)

    def _on_remove_clicked(self, _button: Gtk.Button) -> None:
        self.emit("removed")
