# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.preview import GeoPreview

from gajim.gtk.menus import get_preview_menu
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.widgets import GajimPopover


@Gtk.Template.from_string(string=get_ui_string("preview/geo.ui"))
class GeoPreviewWidget(Gtk.Box, SignalManager):
    __gtype_name__ = "GeoPreviewWidget"

    _image_button: Gtk.Button = Gtk.Template.Child()
    _location_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, preview: GeoPreview) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._uri = preview.uri
        self._location_label.set_text(preview.text)
        self._image_button.set_tooltip_text(_("Location at %s") % preview.text)
        self._image_button.set_action_target_value(GLib.Variant("s", preview.uri))

        self._menu_popover = GajimPopover(None)
        self.append(self._menu_popover)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_preview_clicked)
        self.add_controller(gesture_secondary_click)

    def get_text(self) -> str:
        return self._uri

    def do_unroot(self) -> None:
        self._disconnect_all()
        del self._menu_popover
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _on_preview_clicked(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)
        menu = get_preview_menu(self._uri)
        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x, y)
        self._menu_popover.popup()
