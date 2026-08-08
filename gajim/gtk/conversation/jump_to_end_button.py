# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

ContactT = BareContact | GroupchatContact | GroupchatParticipant


class JumpToEndButton(Gtk.Revealer):
    __gsignals__ = {
        "clicked": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Gtk.Revealer.__init__(self)
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.END)
        self.set_margin_end(24)
        self.set_margin_bottom(12)
        self.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.set_transition_duration(150)

        overlay = Gtk.Overlay()
        self.set_child(overlay)

        self._icon = Gtk.Image()
        self._icon.set_margin_start(4)
        self._icon.set_margin_end(4)

        self._button = Gtk.Button(margin_top=6)
        self._button.add_css_class("circular")
        self._button.set_child(self._icon)
        self._button.connect("clicked", self._on_jump_clicked)
        overlay.set_child(self._button)

        self._unread_label = Gtk.Label()
        self._unread_label.add_css_class("unread-counter")
        self._unread_label.set_visible(False)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)
        overlay.add_overlay(self._unread_label)

        self._count = 0
        self._new_messages = False
        self._set_new_messages(False)

    def switch_contact(self, contact: ContactT) -> None:
        if isinstance(contact, GroupchatContact) and not contact.can_notify():
            self._unread_label.add_css_class("unread-counter-silent")
        else:
            self._unread_label.remove_css_class("unread-counter-silent")

    def _on_jump_clicked(self, _button: Gtk.Button) -> None:
        self.reset_unread_count()
        self.emit("clicked")

    def toggle(self, visible: bool) -> None:
        self.set_reveal_child(visible)
        if not visible:
            self.reset_unread_count()

    def show_new_messages(self) -> None:
        self._set_new_messages(True)
        self.set_reveal_child(True)

    def show_end(self) -> None:
        if not self._new_messages:
            return
        self.reset_unread_count()
        self.set_reveal_child(False)
        self._set_new_messages(False)

    def reset(self) -> None:
        self._set_new_messages(False)
        self.set_reveal_child(False)
        self.reset_unread_count()

    def _set_new_messages(self, enabled: bool) -> None:
        self._new_messages = enabled
        if enabled:
            self._icon.set_from_icon_name("lucide-chevron-down-symbolic")
            self._button.set_tooltip_text(_("Jump to New Messages"))
            self._button.add_css_class("suggested-action")
            return

        self._icon.set_from_icon_name("lucide-chevrons-down-symbolic")
        self._button.set_tooltip_text(_("Jump to Bottom"))
        self._button.remove_css_class("suggested-action")

    def reset_unread_count(self) -> None:
        self._count = 0
        self._unread_label.set_visible(False)

    def add_unread_count(self) -> None:
        self._count += 1
        if self._count > 0:
            self._unread_label.set_text(str(self._count))
            self._unread_label.set_visible(True)
        else:
            self._unread_label.set_visible(False)
