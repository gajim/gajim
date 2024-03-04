# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

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

        label = Gtk.Label(label=_('Click messages to select them\n'
                                  '(Ctrl + Double Click to deselect)'))
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
