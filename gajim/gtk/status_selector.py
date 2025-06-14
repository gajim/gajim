# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.configpaths import get_ui_path
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.util.status import get_client_status
from gajim.common.util.status import get_uf_show

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.util.misc import convert_surface_to_texture


@Gtk.Template(filename=get_ui_path("status_selector.ui"))
class StatusSelector(Gtk.MenuButton, EventHelper):
    __gtype_name__ = "StatusSelector"

    _image: Gtk.Image = Gtk.Template.Child()
    _label: Gtk.Label = Gtk.Template.Child()

    def __init__(self):
        self._account: str | None = None

        Gtk.MenuButton.__init__(self)
        EventHelper.__init__(self)

        surface = get_show_circle(
            "offline", AvatarSize.SHOW_CIRCLE, self.get_scale_factor()
        )
        self._image.set_from_paintable(convert_surface_to_texture(surface))

        self.register_events(
            [
                ("our-show", ged.GUI1, self._on_our_show),
            ]
        )

    @GObject.Property(type=str)
    def account(self) -> str | None:  # pyright: ignore
        return self._account

    @account.setter
    def account(self, account: str | None) -> None:
        if self._account == account:
            return

        self._disconnect_signals(self._account)
        self._connect_signals(account)

        self._account = account
        self._update_status()

    def _connect_signals(self, account: str | None) -> None:
        if account is None:
            return
        client = app.get_client(account)
        client.connect_signal("state-changed", self._on_client_state_changed)

    def _disconnect_signals(self, account: str | None) -> None:
        if account is None:
            return
        client = app.get_client(account)
        client.disconnect_all_from_obj(self)

    def set_account(self, account: str | None) -> None:
        self.account = account

    @Gtk.Template.Callback()
    def _on_clicked(self, _button: Gtk.Button, status: str) -> None:
        app.app.change_status(status=status, account=self._account)

    def _on_our_show(self, event: events.ShowChanged) -> None:
        if event.account != self._account:
            return
        self._update_status()

    def _on_client_state_changed(
        self, _client: Client, _signal_name: str, _state: SimpleClientState
    ) -> None:
        self._update_status()

    def _update_status(self) -> None:
        if self._account is None:
            self._image.set_from_paintable(None)
            self._label.set_text("")
            return

        show = get_client_status(self._account)
        surface = get_show_circle(show, AvatarSize.SHOW_CIRCLE, self.get_scale_factor())
        self._image.set_from_paintable(convert_surface_to_texture(surface))
        self._label.set_text(get_uf_show(show))


@Gtk.Template(filename=get_ui_path("status_selector_popover.ui"))
class StatusSelectorPopover(Gtk.Popover):
    __gtype_name__ = "StatusSelectorPopover"

    __gsignals__ = {
        "clicked": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str,),
        )
    }

    _box: Gtk.Box = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def _on_clicked(self, button: StatusSelectorPopoverButton) -> None:
        self.emit("clicked", button.status)
        self.popdown()


@Gtk.Template(filename=get_ui_path("status_selector_popover_button.ui"))
class StatusSelectorPopoverButton(Gtk.Button):
    __gtype_name__ = "StatusSelectorPopoverButton"

    _image: Gtk.Image = Gtk.Template.Child()
    _label: Gtk.Label = Gtk.Template.Child()

    @GObject.Property(type=str)
    def status(self) -> str:  # pyright: ignore
        return self._status

    @status.setter
    def status(self, status: str) -> None:
        self._status = status
        self._label.set_text_with_mnemonic(get_uf_show(status, use_mnemonic=True))
        surface = get_show_circle(
            status, AvatarSize.SHOW_CIRCLE, self.get_scale_factor()
        )
        self._image.set_from_paintable(convert_surface_to_texture(surface))
