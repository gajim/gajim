# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common.i18n import _


class ChatFilter(Gtk.Box):

    __gsignals__ = {
        'filter-changed': (GObject.SignalFlags.RUN_LAST,
                           None,
                           (str, )),
    }

    def __init__(self, icons: bool = False) -> None:
        Gtk.Box.__init__(self, halign=Gtk.Align.CENTER)

        toolbar = Gtk.Box(css_classes=['toolbar'])
        if icons:
            toolbar.add_css_class('chat-filter-icons')

        self._all_button = Gtk.ToggleButton()
        if icons:
            self._all_button.set_icon_name('feather-home-symbolic')
            self._all_button.set_tooltip_text(_('All'))
        else:
            self._all_button.set_label(_('All'))
        self._all_button.set_name('all')
        self._all_button.connect('clicked', self._on_button_clicked)
        toolbar.append(self._all_button)

        chats_button = Gtk.ToggleButton(group=self._all_button)
        if icons:
            chats_button.set_icon_name('feather-user-symbolic')
            chats_button.set_tooltip_text(_('Chats'))
        else:
            chats_button.set_label(_('Chats'))
        chats_button.set_name('chats')
        chats_button.connect('clicked', self._on_button_clicked)
        toolbar.append(chats_button)

        group_chats_button = Gtk.ToggleButton(group=self._all_button)
        if icons:
            group_chats_button.set_icon_name('feather-users-symbolic')
            group_chats_button.set_tooltip_text(_('Group Chats'))
        else:
            group_chats_button.set_label(_('Group Chats'))
        group_chats_button.set_name('group_chats')
        group_chats_button.connect('clicked', self._on_button_clicked)
        toolbar.append(group_chats_button)

        self.append(toolbar)

    def _on_button_clicked(self, button: Any) -> None:
        if button.get_active():
            self.emit('filter-changed', button.get_name())

    def reset(self) -> None:
        self._all_button.set_active(True)
        self.emit('filter-changed', 'all')
