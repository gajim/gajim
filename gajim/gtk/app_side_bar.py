# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.app_page import AppPage
from gajim.gtk.util.classes import SignalManager


class AppSideBar(Gtk.ListBox, SignalManager):
    def __init__(self, app_page: AppPage) -> None:
        Gtk.ListBox.__init__(
            self, valign=Gtk.Align.START, selection_mode=Gtk.SelectionMode.SINGLE
        )
        SignalManager.__init__(self)

        self.add_css_class("workspace-sidebar")

        self._connect(self, "row-activated", self._on_app_row_activated)

        self._connect(app_page, "unread-count-changed", self._on_unread_count_changed)

        self._app_row = AppRow()
        self.append(self._app_row)

        # Use idle_add to unselect listbox selection on startup
        GLib.idle_add(self.unselect_all)

    def do_unroot(self) -> None:
        self._disconnect_all()
        app.check_finalize(self)

    @staticmethod
    def _on_app_row_activated(_listbox: Gtk.ListBox, _row: Gtk.ListBoxRow) -> None:
        app.window.show_app_page()

    def _on_unread_count_changed(self, _app_page: AppPage, count: int) -> None:
        self._app_row.set_unread_count(count)


class AppRow(Gtk.ListBoxRow):
    def __init__(self) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.add_css_class("workspace-sidebar-item")
        self.add_css_class("app-sidebar-item")

        self._unread_label = Gtk.Label()
        self._unread_label.add_css_class("unread-counter")
        self._unread_label.set_visible(False)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)

        image = Gtk.Image(icon_name="gajim", pixel_size=32)

        selection_bar = Gtk.Box()
        selection_bar.set_size_request(6, -1)
        selection_bar.add_css_class("selection-bar")

        item_box = Gtk.Box()
        item_box.append(selection_bar)
        item_box.append(image)

        overlay = Gtk.Overlay()
        overlay.set_child(item_box)
        overlay.add_overlay(self._unread_label)

        self.set_child(overlay)

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text("999+")
        self._unread_label.set_visible(bool(count))
