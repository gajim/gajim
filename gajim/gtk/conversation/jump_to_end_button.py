# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

ContactT = BareContact | GroupchatContact | GroupchatParticipant


class JumpToEndButton(Gtk.Overlay):

    __gsignals__ = {
        'clicked': (
            GObject.SignalFlags.RUN_LAST,
            None,
            ()),
    }

    def __init__(self) -> None:
        Gtk.Overlay.__init__(self)
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.END)
        self.set_margin_end(6)
        self.set_margin_bottom(12)

        icon = Gtk.Image.new_from_icon_name(
            'go-bottom-symbolic', Gtk.IconSize.BUTTON)
        icon.set_margin_start(4)
        icon.set_margin_end(4)

        button = Gtk.Button()
        button.set_margin_top(6)
        button.set_margin_end(6)
        button.get_style_context().add_class('circular')
        button.add(icon)
        button.connect('clicked', self._on_jump_clicked)
        self.add(button)

        self._unread_label = Gtk.Label()
        self._unread_label.get_style_context().add_class('unread-counter')
        self._unread_label.set_no_show_all(True)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)
        self.add_overlay(self._unread_label)

        self.show_all()

        self._count = 0
        self.set_no_show_all(True)

    def switch_contact(self, contact: ContactT) -> None:
        if isinstance(contact, GroupchatContact) and not contact.can_notify():
            self._unread_label.get_style_context().add_class(
                'unread-counter-silent')
        else:
            self._unread_label.get_style_context().remove_class(
                'unread-counter-silent')

    def _on_jump_clicked(self, _button: Gtk.Button) -> None:
        self.reset_unread_count()
        self.emit('clicked')

    def toggle(self, visible: bool) -> None:
        if visible:
            self.show()
        else:
            self.hide()
            self.reset_unread_count()

    def reset_unread_count(self) -> None:
        self._count = 0
        self._unread_label.hide()

    def add_unread_count(self) -> None:
        self._count += 1
        if self._count > 0:
            self._unread_label.set_text(str(self._count))
            self._unread_label.show()
        else:
            self._unread_label.hide()
