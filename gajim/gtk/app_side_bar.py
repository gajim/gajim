# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.app_page import AppPage
from gajim.gtk.util import load_icon_surface


class AppSideBar(Gtk.ListBox):
    def __init__(self, app_page: AppPage) -> None:
        Gtk.ListBox.__init__(self)
        self.set_valign(Gtk.Align.START)
        self.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.get_style_context().add_class('workspace-sidebar')

        self.connect('row-activated', self._on_app_row_activated)

        app_page.connect('unread-count-changed', self._on_unread_count_changed)

        self._app_row = AppRow()
        self.add(self._app_row)

        self.show_all()

        # Use idle_add to unselect listbox selection on startup
        GLib.idle_add(self.unselect_all)

    @staticmethod
    def _on_app_row_activated(_listbox: Gtk.ListBox,
                              _row: Gtk.ListBoxRow
                              ) -> None:
        app.window.show_app_page()

    def _on_unread_count_changed(self, _app_page: AppPage, count: int) -> None:
        self._app_row.set_unread_count(count)


class AppRow(Gtk.ListBoxRow):
    def __init__(self) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class('workspace-sidebar-item')
        self.get_style_context().add_class('app-sidebar-item')

        self._unread_label = Gtk.Label()
        self._unread_label.get_style_context().add_class(
            'unread-counter')
        self._unread_label.set_no_show_all(True)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)

        surface = load_icon_surface('org.gajim.Gajim', 32)
        image = Gtk.Image.new_from_surface(surface)

        selection_bar = Gtk.Box()
        selection_bar.set_size_request(6, -1)
        selection_bar.get_style_context().add_class('selection-bar')

        item_box = Gtk.Box()
        item_box.add(selection_bar)
        item_box.add(image)

        overlay = Gtk.Overlay()
        overlay.add(item_box)
        overlay.add_overlay(self._unread_label)

        self.add(overlay)
        self.show_all()

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text('999+')
        self._unread_label.set_visible(bool(count))
