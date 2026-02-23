# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.open_graph_parser import OpenGraphData
from gajim.common.util.image import get_texture_from_data
from gajim.common.util.text import to_one_line

from gajim.gtk.menus import get_preview_menu
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import check_finalize
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.widgets import GajimPopover


@Gtk.Template.from_string(string=get_ui_string("preview/open_graph.ui"))
class OpenGraphPreviewWidget(Gtk.Box, SignalManager):
    __gtype_name__ = "OpenGraphPreviewWidget"
    __gsignals__ = {
        "remove": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    _content_box: Gtk.Box = Gtk.Template.Child()
    _placeholder_image: Gtk.Image = Gtk.Template.Child()
    _picture_clamp: Adw.Clamp = Gtk.Template.Child()
    _picture: Gtk.Picture = Gtk.Template.Child()
    _loading_spinner: Adw.Spinner = Gtk.Template.Child()
    _title_label: Gtk.Label = Gtk.Template.Child()
    _description_label: Gtk.Label = Gtk.Template.Child()
    _close_button: Gtk.Button = Gtk.Template.Child()

    def __init__(
        self,
        about_url: str,
        *,
        og_data: OpenGraphData | None = None,
        pk: int | None = None,
        minimal: bool = False,
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        self._about_url = about_url
        self._og_data = og_data

        self.set_open_graph(og_data, minimal=minimal)
        self.set_tooltip_text(_("Open %s") % self._about_url)

        self._menu_popover = GajimPopover(None)
        self.append(self._menu_popover)

        gesture_primary_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        self._connect(gesture_primary_click, "pressed", self._on_primary_clicked)
        self._content_box.add_controller(gesture_primary_click)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_secondary_clicked)
        self._content_box.add_controller(gesture_secondary_click)

        self._connect(self._close_button, "clicked", self._on_close_clicked)
        self._pk = pk

    def set_open_graph(self, og_data: OpenGraphData | None, *, minimal: bool) -> None:
        self._og_data = og_data

        if og_data is None:
            self._loading_spinner.set_visible(True)
            return

        self._loading_spinner.set_visible(False)
        self._title_label.set_text(og_data.title or "")

        if minimal:
            return

        if thumbnail := og_data.thumbnail:
            texture = get_texture_from_data(thumbnail.data)
            self._picture.set_paintable(texture)
            self._picture_clamp.set_visible(True)
            self._placeholder_image.set_visible(False)

        if description := og_data.description:
            if len(description) > 100:
                self._description_label.set_text(f"{to_one_line(description)[:100]}…")
                self._description_label.set_tooltip_text(description)
            else:
                self._description_label.set_text(to_one_line(description))
            self._description_label.set_visible(True)

    def get_open_graph(self) -> OpenGraphData | None:
        return self._og_data

    def set_error(self) -> None:
        self._loading_spinner.set_visible(False)
        self._title_label.set_text(_("Could not generate link preview"))

    def _on_primary_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:
        app.app.activate_action("open-link", GLib.Variant("s", self._about_url))
        return Gdk.EVENT_STOP

    def _on_secondary_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        assert self._about_url is not None
        menu = get_preview_menu(self._about_url)
        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x, y)
        self._menu_popover.popup()

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        if self._pk is not None:
            app.storage.archive.remove_og(self._pk)
            parent = self.get_parent()
            assert isinstance(parent, Gtk.Box)
            parent.remove(self)

        self.emit("remove")
        check_finalize(self)

    def do_unroot(self) -> None:
        del self._menu_popover
        self._disconnect_all()
