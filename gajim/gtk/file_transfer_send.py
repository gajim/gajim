# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
#
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

from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from nbxmpp import Namespace

from gajim.common import app
from gajim.common.i18n import _

from .filechoosers import FileChooserDialog
from .resource_selector import ResourceSelector
from .util import get_builder


class SendFileDialog(Gtk.ApplicationWindow):
    def __init__(self, contact, send_callback, transient_for):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_show_menubar(False)
        self.set_resizable(True)
        self.set_default_size(500, 350)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_transient_for(transient_for)
        self.set_title(_('Choose a File to Send…'))
        self.set_destroy_with_parent(True)

        self._contact = contact
        self._send_callback = send_callback

        self._ui = get_builder('file_transfer_send.ui')
        self.add(self._ui.send_stack)

        self._ui.resource_instructions.set_text(
            _('%s is online with multiple devices.\n'
              'Choose the device you would like to send the '
              'file to.') % self._contact.name)

        self._resource_selector = ResourceSelector(
            contact,
            constraints=[Namespace.JINGLE_FILE_TRANSFER_5])
        self._resource_selector.connect(
            'selection-changed', self._on_resource_selection)
        self._ui.resource_box.pack_start(self._resource_selector, 1, 0, 0)

        self.connect('key-press-event', self._key_press_event)
        self._ui.connect_signals(self)
        self.show_all()

    def _on_files_changed(self, _listbox, _row):
        sensitive = bool(len(self._ui.listbox.get_children()) > 0)
        self._ui.files_send.set_sensitive(sensitive)

    def _on_resource_selection(self, _selector, state):
        self._ui.resource_send.set_sensitive(state)

    def _on_send_to_resource(self, _button):
        resource_jid = self._resource_selector.get_jid()
        self._send_files(resource_jid)

    def _on_send_clicked(self, _button):
        count = len(self._contact.get_resources())
        if count == 0 or count > 1:
            self._ui.send_stack.set_visible_child_name('resource_selection')
            return

        resource_jid = self._contact.get_resources()[0].jid
        self._send_files(resource_jid)

    def _send_files(self, resource_jid):
        for file in self._ui.listbox.get_children():
            self._send_callback(
                resource_jid, str(file.path), self._get_description())
        self.destroy()

    def _select_files(self, _button):
        FileChooserDialog(self._set_files,
                          select_multiple=True,
                          transient_for=self,
                          path=app.settings.get('last_send_dir'))

    def _remove_files(self, _button):
        selected = self._ui.listbox.get_selected_rows()
        for item in selected:
            self._ui.listbox.remove(item)

    def _set_files(self, file_names):
        for file in file_names:
            row = FileRow(file)
            if row.path.is_dir():
                continue
            last_dir = row.path.parent
            self._ui.listbox.add(row)
        self._ui.listbox.show_all()
        app.settings.set('last_send_dir', str(last_dir))

    def _get_description(self):
        buffer_ = self._ui.description.get_buffer()
        start, end = buffer_.get_bounds()
        return buffer_.get_text(start, end, False)

    def _key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()


class FileRow(Gtk.ListBoxRow):
    def __init__(self, path):
        Gtk.ListBoxRow.__init__(self)
        self.path = Path(path)
        label = Gtk.Label(label=self.path.name)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_xalign(0)
        self.add(label)
