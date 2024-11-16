# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.util.status import get_client_status
from gajim.common.util.status import get_global_show
from gajim.common.util.status import get_uf_show
from gajim.common.util.status import statuses_unified

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.util import convert_surface_to_texture
from gajim.gtk.util import SignalManager


class StatusSelector(Gtk.MenuButton, EventHelper, SignalManager):
    def __init__(self, account: str | None = None, compact: bool = False):
        Gtk.MenuButton.__init__(self, direction=Gtk.ArrowType.UP)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._compact = compact
        self._status_popover = self._create_popover()
        self.set_popover(self._status_popover)

        self._current_show_icon = Gtk.Image(pixel_size=AvatarSize.SHOW_CIRCLE)
        surface = get_show_circle(
            "offline", AvatarSize.SHOW_CIRCLE, self.get_scale_factor()
        )
        self._current_show_icon.set_from_paintable(convert_surface_to_texture(surface))

        box = Gtk.Box(spacing=6)
        box.append(self._current_show_icon)
        if not self._compact:
            self._current_show_label = Gtk.Label(label=get_uf_show("offline"))
            self._current_show_label.set_ellipsize(Pango.EllipsizeMode.END)
            self._current_show_label.set_halign(Gtk.Align.START)
            self._current_show_label.set_xalign(0)
            box.append(self._current_show_label)

        self.set_child(box)

        self.register_events(
            [
                ("our-show", ged.GUI1, self._on_our_show),
                ("account-enabled", ged.GUI1, self._on_account_enabled),
            ]
        )

        for client in app.get_clients():
            client.connect_signal("state-changed", self._on_client_state_changed)

    def do_unroot(self) -> None:
        Gtk.MenuButton.do_unroot(self)
        self.unregister_events()
        self._disconnect_all()
        for client in app.get_clients():
            client.disconnect_all_from_obj(self)

        del self._status_popover
        app.check_finalize(self)

    def _on_our_show(self, _event: events.ShowChanged) -> None:
        self.update()

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        client = app.get_client(event.account)
        client.connect_signal("state-changed", self._on_client_state_changed)

    def _on_client_state_changed(
        self, _client: Client, _signal_name: str, _state: SimpleClientState
    ) -> None:
        self.update()

    def _create_popover(self) -> Gtk.Popover:
        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popover_box.add_css_class("m-3")
        popover_items = [
            "online",
            "away",
            "xa",
            "dnd",
            "separator",
            "offline",
        ]

        for item in popover_items:
            if item == "separator":
                popover_box.append(Gtk.Separator())
                continue

            show_icon = Gtk.Image(pixel_size=AvatarSize.SHOW_CIRCLE)
            show_label = Gtk.Label()
            show_label.set_halign(Gtk.Align.START)

            surface = get_show_circle(
                item, AvatarSize.SHOW_CIRCLE, self.get_scale_factor()
            )
            show_icon.set_from_paintable(convert_surface_to_texture(surface))
            show_label.set_text_with_mnemonic(get_uf_show(item, use_mnemonic=True))

            show_box = Gtk.Box(spacing=6)
            show_box.append(show_icon)
            show_box.append(show_label)

            button = Gtk.Button()
            button.add_css_class("flat")
            button.set_name(item)
            button.set_child(show_box)
            self._connect(button, "clicked", self._on_change_status)
            popover_box.append(button)

        status_popover = Gtk.Popover()
        status_popover.set_child(popover_box)
        return status_popover

    def _on_change_status(self, button: Gtk.Button) -> None:
        self._status_popover.popdown()
        new_status = button.get_name()
        app.app.change_status(status=new_status, account=self._account)

    def update(self) -> None:
        if self._account is None:
            show = get_global_show()
        else:
            show = get_client_status(self._account)

        surface = get_show_circle(show, AvatarSize.SHOW_CIRCLE, self.get_scale_factor())
        self._current_show_icon.set_from_paintable(convert_surface_to_texture(surface))

        uf_show = get_uf_show(show)
        if statuses_unified():
            self._current_show_icon.set_tooltip_text(_("Status: %s") % uf_show)
            if not self._compact:
                self._current_show_label.set_text(uf_show)
        else:
            show_label = _("%s (desynced)") % uf_show
            self._current_show_icon.set_tooltip_text(_("Status: %s") % show_label)
            if not self._compact:
                self._current_show_label.set_text(show_label)
