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

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common.i18n import _


class MessageSelection(Gtk.Grid):

    __gsignals__ = {
        'copy': (GObject.SignalFlags.RUN_LAST, None, ()),
        'cancel': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Gtk.Grid.__init__(self, row_spacing=18, column_spacing=6)
        self.set_no_show_all(True)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)

        self.get_style_context().add_class('floating-overlay-box')

        label = Gtk.Label(label=_('Click messages to select them'))
        self.attach(label, 0, 0, 2, 1)

        copy_button = Gtk.Button(label=_('Copy Text'))
        copy_button.get_style_context().add_class('suggested-action')
        copy_button.connect('clicked', self._on_copy_clicked)
        self.attach(copy_button, 0, 1, 1, 1)

        cancel_button = Gtk.Button(label=_('Cancel'))
        cancel_button.connect('clicked', self._on_cancel_clicked)
        self.attach(cancel_button, 1, 1, 1, 1)

    def _on_copy_clicked(self, _button: Gtk.Button) -> None:
        self.set_no_show_all(True)
        self.hide()
        self.emit('copy')

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.set_no_show_all(True)
        self.hide()
        self.emit('cancel')
