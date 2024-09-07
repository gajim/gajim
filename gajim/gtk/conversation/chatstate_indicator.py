# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.const import Chatstate

from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact


class ChatstateIndicator(Gtk.Button):
    def __init__(self) -> None:
        Gtk.Button.__init__(
            self,
            halign=Gtk.Align.START,
            valign=Gtk.Align.END,
            margin_start=12,
            margin_bottom=12,
            no_show_all=True,
        )

        self._contact: types.ChatContactT | None = None

        self.get_style_context().add_class('chatstate-indicator-button')
        self.connect('clicked', self._on_clicked)

        self._box = Gtk.Box(spacing=12)
        self.add(self._box)

        self._composing_icon = Gtk.Image.new_from_icon_name(
            'content-loading-symbolic', Gtk.IconSize.BUTTON
        )
        self._composing_icon.set_no_show_all(True)
        self._composing_icon.get_style_context().add_class('chatstate-icon')
        self._box.add(self._composing_icon)

        self._label = Gtk.Label(
            no_show_all=True,
            max_width_chars=52,
            ellipsize=Pango.EllipsizeMode.END,
        )
        self._label.get_style_context().add_class('dim-label')
        self._label.get_style_context().add_class('small-label')
        self._box.add(self._label)

        self.show_all()

    def switch_contact(self, contact: types.ChatContactT) -> None:
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = contact
        self._contact.connect('chatstate-update', self._on_chatstate_update)

        self._update_state()

    def _on_chatstate_update(
        self, _contact: types.BareContact, _signal_name: str
    ) -> None:
        self._update_state()

    def _on_clicked(self, _button: ChatstateIndicator) -> None:
        self._label.set_visible(not self._label.get_visible())

    def _update_state(self) -> None:
        assert self._contact is not None

        if isinstance(self._contact, GroupchatContact):
            visible = bool(self._contact.get_composers())
            text = self._get_muc_composing_text()

            self._composing_icon.get_style_context().add_class('chatstate-icon')
        else:
            visible = self._contact.chatstate in (Chatstate.COMPOSING, Chatstate.PAUSED)
            text = f'{self._contact.name} {self._contact.chatstate_string}'

            if self._contact.chatstate == Chatstate.COMPOSING:
                self._composing_icon.get_style_context().add_class('chatstate-icon')
            else:
                self._composing_icon.get_style_context().remove_class('chatstate-icon')

        self.set_visible(visible)
        self._box.set_visible(visible)
        self._composing_icon.set_visible(visible)

        self._label.set_text(text)

    def _get_muc_composing_text(self) -> str:
        assert isinstance(self._contact, GroupchatContact)
        composers = tuple(c.name for c in self._contact.get_composers())
        count = len(composers)
        if count == 1:
            return _('%s is typing…') % composers[0]
        if count == 2:
            return _('%s and %s are typing…') % composers

        return _('%s participants are typing…') % count
