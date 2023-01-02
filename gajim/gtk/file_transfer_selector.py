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
from typing import cast
from typing import Optional

import logging
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common.helpers import get_file_path_from_dnd_dropped_uri
from gajim.common.helpers import load_file_async
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.preview import PREVIEWABLE_MIME_TYPES
from gajim.common.preview_helpers import create_thumbnail
from gajim.common.preview_helpers import get_icon_for_mime_type
from gajim.common.preview_helpers import guess_mime_type
from gajim.common.preview_helpers import pixbuf_from_data

from .builder import get_builder
from .filechoosers import FileChooserDialog
from .resource_selector import ResourceSelector

PREVIEW_SIZE = 72

log = logging.getLogger('gajim.gui.file_transfer_selector')


class FileTransferSelector(Gtk.Box):

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self,
                 contact: types.ChatContactT,
                 method: Optional[str] = None
                 ) -> None:

        Gtk.Box.__init__(self)

        self._contact = contact
        self._method = method or app.window.get_preferred_ft_method(contact)

        client = app.get_client(contact.account)
        self._max_file_size = client.get_module('HTTPUpload').max_file_size or 0

        self._ui = get_builder('file_transfer_selector.ui')
        self.add(self._ui.stack)

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self._resource_selector = None
        if isinstance(contact, BareContact):
            # No jingle file transfers in group chats
            self._resource_selector = ResourceSelector(
                contact,
                constraints=[Namespace.JINGLE_FILE_TRANSFER_5])
            self._resource_selector.connect(
                'selection-changed', self._on_resource_selection)
            self._ui.resource_box.pack_start(
                self._resource_selector, True, False, 0)

            self._ui.resource_instructions.set_text(
                _('%s is online with multiple devices.\n'
                  'Choose the device you would like to send the '
                  'files to.') % self._contact.name)

        uri_entry = Gtk.TargetEntry.new(
            'text/uri-list', Gtk.TargetFlags.OTHER_APP, 80)
        dst_targets = Gtk.TargetList.new([uri_entry])

        self._ui.listbox.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [uri_entry],
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        self._ui.listbox.drag_dest_set_target_list(dst_targets)
        self._ui.listbox.connect(
            'drag-data-received', self._on_drag_data_received)

        self.show_all()

    def transfer_resource_required(self) -> bool:
        if not isinstance(self._contact, BareContact):
            # No jingle file transfer for group chats
            return False

        if self._method is None:
            log.error('No file transfer method available')
            return False

        current_page = self._ui.stack.get_visible_child_name()
        if self._method == 'httpupload':
            for path in self._get_file_paths():
                if path.stat().st_size > self._max_file_size:
                    if current_page == 'resource-selection':
                        return False

                    self._ui.stack.set_visible_child_name('resource-selection')
                    self.emit('changed', False)
                    return True
            return False

        if current_page == 'resource-selection':
            return False

        self._ui.stack.set_visible_child_name('resource-selection')
        self.emit('changed', False)
        return True

    def get_catalog(self) -> list[tuple[Path, str, JID]]:
        # catalog: list[(file Path, transfer method, recipient JID)]
        catalog: list[tuple[Path, str, JID]] = []

        file_paths = self._get_file_paths()
        for path in file_paths:
            if (self._method == 'jingle' or
                    path.stat().st_size > self._max_file_size):
                assert self._resource_selector is not None
                item = (path, 'jingle', self._resource_selector.get_jid())
            elif self._method == 'httpupload':
                item = (path, 'httpupload', self._contact.jid)
            else:
                # No file transfer method available
                continue

            catalog.append(item)

        return catalog

    def add_files(self, uris: list[str]) -> None:
        for uri in uris:
            path = get_file_path_from_dnd_dropped_uri(uri)
            if path is None or not path.is_file():
                self._add_warning_message(
                    'Could not add %s'
                    % (str(path) if path else uri))
                continue

            size_warning = bool(self._method == 'httpupload' and
                                path.stat().st_size > self._max_file_size)
            jingle_warning = bool(self._method == 'jingle')

            row = FileRow(path, size_warning, jingle_warning)
            self._ui.listbox.add(row)
            app.settings.set('last_send_dir', str(path.parent))

        self._ui.listbox.show_all()

    def _add_warning_message(self, msg: str) -> None:
        log.warning(msg)  # TODO: replace with UI

    def _on_destroy(self, _widget: FileTransferSelector) -> None:
        app.check_finalize(self)

    def _get_file_paths(self) -> list[Path]:
        paths: list[Path] = []
        for row in cast(list[FileRow], self._ui.listbox.get_children()):
            paths.append(row.file_path)

        return paths

    def _on_drag_data_received(self,
                               _widget: Gtk.Widget,
                               _context: Gdk.DragContext,
                               _x_coord: int,
                               _y_coord: int,
                               selection: Gtk.SelectionData,
                               target_type: int,
                               _timestamp: int
                               ) -> None:
        if not selection.get_data():
            return

        if target_type == 80:
            self.add_files(selection.get_uris())

    def _on_files_changed(self, _listbox: Gtk.ListBox, _row: FileRow) -> None:
        file_paths = self._get_file_paths()
        if not file_paths:
            self.emit('changed', False)
            return

        if self._method == 'httpupload' and self._contact.is_groupchat:
            # Enforce HTTPUpload file size limit for group chats
            for path in file_paths:
                if path.stat().st_size > self._max_file_size:
                    self.emit('changed', False)
                    return

        self.emit('changed', True)

    def _on_resource_selection(self,
                               _selector: ResourceSelector,
                               state: bool
                               ) -> None:

        self.emit('changed', state)

    def _on_choose_files_clicked(self, _button: Gtk.Button) -> None:
        def _on_chosen(paths: list[str]) -> None:
            self.add_files([Path(p).as_uri() for p in paths])
        FileChooserDialog(_on_chosen,
                          select_multiple=True,
                          transient_for=app.window,
                          path=app.settings.get('last_send_dir') or None)


class FileRow(Gtk.ListBoxRow):
    def __init__(self,
                 path: Path,
                 size_warning: bool,
                 jingle_warning: bool
                 ) -> None:

        Gtk.ListBoxRow.__init__(self)
        self.file_path = path

        self._ui = get_builder('file_transfer_selector.ui')
        self.add(self._ui.file_box)

        self._ui.remove_file_button.connect('clicked', self._on_remove_clicked)

        self._ui.file_name_label.set_text(path.name)

        if app.settings.get('use_kib_mib'):
            units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            units = GLib.FormatSizeFlags.DEFAULT

        file_size_string = GLib.format_size_full(path.stat().st_size, units)
        self._ui.file_size_label.set_text(file_size_string)

        if size_warning:
            self._ui.warning_label.set_text(
                _('File too big, will use direct transfer (not encrypted)'))
            self._ui.warning_label.show()

        if jingle_warning:
            self._ui.warning_label.set_text(
                _('Direct transfer (not encrypted)'))
            self._ui.warning_label.show()

        self._ui.preview_image_box.set_size_request(PREVIEW_SIZE, -1)
        self._set_preview(path)

    def _set_preview(self, path: Path) -> None:
        mime_type = guess_mime_type(path)
        if mime_type not in PREVIEWABLE_MIME_TYPES:
            self._set_icon_for_mime_type(mime_type)
            return

        load_file_async(self.file_path, self._on_load_finished, mime_type)

    def _on_load_finished(self,
                          data: Optional[bytes],
                          _error: Optional[GLib.Error],
                          mime_type: Any
                          ) -> None:

        if data is None:
            self._set_icon_for_mime_type(mime_type)
            return

        preview_bytes = create_thumbnail(data, PREVIEW_SIZE, mime_type)
        if preview_bytes is None:
            self._set_icon_for_mime_type(mime_type)
            return

        pixbuf = pixbuf_from_data(preview_bytes)
        if pixbuf is None:
            self._set_icon_for_mime_type(mime_type)
            return

        self._ui.preview_image.set_from_pixbuf(pixbuf)

    def _set_icon_for_mime_type(self, mime_type: str) -> None:
        icon = get_icon_for_mime_type(mime_type)
        self._ui.preview_image.set_from_gicon(icon, Gtk.IconSize.DIALOG)

    def _on_remove_clicked(self, _button: Gtk.Button) -> None:
        listbox = cast(Gtk.ListBox, self.get_parent())
        listbox.remove(self)
        self.destroy()
