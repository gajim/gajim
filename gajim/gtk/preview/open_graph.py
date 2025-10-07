# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

import gajim.common.storage.archive.models as mod
from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.menus import get_preview_menu
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.widgets import GajimPopover


@Gtk.Template.from_string(string=get_ui_string("preview/open_graph.ui"))
class OpenGraphPreviewWidget(Gtk.Box):

    __gtype_name__ = "OpenGraphPreviewWidget"

    _content_box: Gtk.Box = Gtk.Template.Child()
    _title_label: Gtk.Label = Gtk.Template.Child()
    _description_label: Gtk.Label = Gtk.Template.Child()
    _close_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, og_data: mod.OpenGraph) -> None:
        Gtk.Box.__init__(self)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        # TODO: use canonical URL instead?
        self._uri = og_data.url
        self._title_label.set_text(og_data.title)

        if description := og_data.description:
            self._description_label.set_text(description)
        else:
            self._description_label.set_visible(False)

        self.set_tooltip_text(_("Open %s") % self._uri)

        self._menu_popover = GajimPopover(None)
        self.append(self._menu_popover)

        gesture_primary_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        gesture_primary_click.connect("pressed", self._on_primary_clicked)
        self._content_box.add_controller(gesture_primary_click)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture_secondary_click.connect("pressed", self._on_secondary_clicked)
        self._content_box.add_controller(gesture_secondary_click)

        self._close_button.connect("clicked", self._on_close_clicked)

    def _on_primary_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:
        app.app.activate_action("open-link", GLib.Variant("s", self._uri))
        return Gdk.EVENT_STOP

    def _on_secondary_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        assert self._uri is not None
        menu = get_preview_menu(self._uri)
        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x, y)
        self._menu_popover.popup()

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        # TODO
        print("close")
