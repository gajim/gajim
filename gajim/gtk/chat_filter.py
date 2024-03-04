# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

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
        Gtk.Box.__init__(self)
        self.set_halign(Gtk.Align.CENTER)

        toolbar = Gtk.Toolbar()
        toolbar.set_icon_size(Gtk.IconSize.MENU)
        if icons:
            toolbar.get_style_context().add_class('chat-filter-icons')

        self._all_button = Gtk.RadioToolButton.new_from_widget(None)
        if icons:
            self._all_button.set_icon_name('feather-home-symbolic')
            self._all_button.set_tooltip_text(_('All'))
        else:
            self._all_button.set_label(_('All'))
        self._all_button.set_name('all')
        self._all_button.connect('clicked', self._on_button_clicked)
        toolbar.insert(self._all_button, 1)

        chats_button = Gtk.RadioToolButton.new_from_widget(self._all_button)
        if icons:
            chats_button.set_icon_name('feather-user-symbolic')
            chats_button.set_tooltip_text(_('Chats'))
        else:
            chats_button.set_label(_('Chats'))
        chats_button.set_name('chats')
        chats_button.connect('clicked', self._on_button_clicked)
        toolbar.insert(chats_button, 2)

        group_chats_button = Gtk.RadioToolButton.new_from_widget(
            self._all_button)
        if icons:
            group_chats_button.set_icon_name('feather-users-symbolic')
            group_chats_button.set_tooltip_text(_('Group Chats'))
        else:
            group_chats_button.set_label(_('Group Chats'))
        group_chats_button.set_name('group_chats')
        group_chats_button.connect('clicked', self._on_button_clicked)
        toolbar.insert(group_chats_button, 3)

        self.add(toolbar)
        self.show_all()

    def _on_button_clicked(self, button: Gtk.RadioToolButton) -> None:
        if button.get_active():
            self.emit('filter-changed', button.get_name())

    def reset(self) -> None:
        self._all_button.set_active(True)
        self.emit('filter-changed', 'all')
