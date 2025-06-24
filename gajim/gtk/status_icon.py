# Copyright (C) 2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging
import sys

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import SimpleClientState
from gajim.common.dbus.menu import DBusMenu
from gajim.common.dbus.menu import DBusMenuItem
from gajim.common.dbus.statusnotifieritem import StatusNotifierItemService
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.util.status import get_global_show
from gajim.common.util.status import get_uf_show

from gajim.gtk.util.icons import get_status_icon_name
from gajim.gtk.util.window import open_window

log = logging.getLogger("gajim.gtk.statusicon")

if sys.platform == "win32":
    import pystray
    from PIL import Image


class StatusIcon:
    def __init__(self) -> None:

        app.settings.connect_signal("show_trayicon", self._on_setting_changed)

        if sys.platform == "win32":
            self._backend = WindowsStatusIcon()
        elif sys.platform == "darwin":
            self._backend = NoneBackend()
        else:
            self._backend = LinuxStatusIcon()

    def _on_setting_changed(self, value: bool, *args: Any) -> None:
        self._backend.set_enabled(value)

    def connect_unread_widget(self, widget: Gtk.Widget, signal: str) -> None:
        widget.connect(signal, self._on_unread_count_changed)

    def _on_unread_count_changed(self, *args: Any) -> None:
        if not app.settings.get("trayicon_notification_on_events"):
            return
        self._backend.update_state()

    def is_visible(self) -> bool:
        return self._backend.is_visible()

    def shutdown(self) -> None:
        self._backend.shutdown()


class NoneBackend:
    def update_state(self, init: bool = False) -> None:
        pass

    def set_enabled(self, enabled: bool) -> None:
        pass

    def is_visible(self) -> bool:
        return False

    def shutdown(self) -> None:
        pass


class StatusIconBackend(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)

        self.register_events(
            [
                ("our-show", ged.GUI1, self._on_our_show),
                ("account-enabled", ged.GUI1, self._on_account_enabled),
            ]
        )

        for client in app.get_clients():
            client.connect_signal("state-changed", self._on_client_state_changed)

    def update_state(self, init: bool = False) -> None:
        raise NotImplementedError

    def is_visible(self) -> bool:
        raise NotImplementedError

    def set_enabled(self, enabled: bool) -> None:
        raise NotImplementedError

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        client = app.get_client(event.account)
        client.connect_signal("state-changed", self._on_client_state_changed)

    def _on_client_state_changed(
        self, _client: Client, _signal_name: str, _state: SimpleClientState
    ) -> None:
        self.update_state()

    def _on_our_show(self, _event: events.ShowChanged) -> None:
        self.update_state()

    @staticmethod
    def _on_start_chat() -> None:
        app.app.activate_action("start-chat", GLib.Variant("as", ["", ""]))

    @staticmethod
    def _on_sounds_mute() -> None:
        current_state = app.settings.get("sounds_on")
        app.settings.set("sounds_on", not current_state)

    def _on_show_hide(self) -> None:
        if not app.window.is_visible() or app.window.is_suspended():
            app.window.show_window()
        else:
            app.window.hide_window()

    @staticmethod
    def _on_preferences() -> None:
        open_window("Preferences")

    @staticmethod
    def _on_quit() -> None:
        app.window.quit()

    @staticmethod
    def _on_status_changed(status: str) -> None:
        app.app.change_status(status=status)

    def _on_activate(self) -> None:
        self._on_show_hide()


class WindowsStatusIcon(StatusIconBackend):
    def __init__(self) -> None:
        StatusIconBackend.__init__(self)
        self._status_icon = self._create_status_icon()
        self._status_icon.run_detached()

    def update_state(self, init: bool = False) -> None:
        if not init and app.window.get_total_unread_count():
            self._status_icon.icon = self._get_icon("message-new")
            return

        show = get_global_show()
        self._status_icon.icon = self._get_icon(show)

    def set_enabled(self, enabled: bool) -> None:
        self._status_icon.stop()

        if enabled:
            self._status_icon = self._create_status_icon()
            self._status_icon.run_detached()

    def is_visible(self) -> bool:
        return self._status_icon.visible

    def shutdown(self) -> None:
        self._status_icon.stop()

    def _create_status_icon(self) -> pystray.Icon:
        assert pystray  # type: ignore
        menu_items: list[pystray.MenuItem] = [
            pystray.MenuItem(
                text=_("Show/Hide Window"),
                action=lambda: GLib.idle_add(self._on_show_hide),
                default=True,
            ),
            pystray.MenuItem(
                _("Status"),
                pystray.Menu(
                    pystray.MenuItem(
                        text=get_uf_show("online"),
                        action=lambda: GLib.idle_add(self._on_status_changed, "online"),
                    ),
                    pystray.MenuItem(
                        text=get_uf_show("away"),
                        action=lambda: GLib.idle_add(self._on_status_changed, "away"),
                    ),
                    pystray.MenuItem(
                        text=get_uf_show("xa"),
                        action=lambda: GLib.idle_add(self._on_status_changed, "xa"),
                    ),
                    pystray.MenuItem(
                        text=get_uf_show("dnd"),
                        action=lambda: GLib.idle_add(self._on_status_changed, "dnd"),
                    ),
                    pystray.MenuItem(
                        text=get_uf_show("offline"),
                        action=lambda: GLib.idle_add(
                            self._on_status_changed, "offline"
                        ),
                    ),
                ),
            ),
            pystray.MenuItem(
                text=_("Start Chat…"),
                action=lambda: GLib.idle_add(self._on_start_chat),
            ),
            pystray.MenuItem(
                text=_("Mute Sounds"),
                action=lambda: GLib.idle_add(self._on_sounds_mute),
                checked=self._get_sound_toggle_state,
            ),
            pystray.MenuItem(
                text=_("Preferences"),
                action=lambda: GLib.idle_add(self._on_preferences),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                text=_("Quit"),
                action=lambda: GLib.idle_add(self._on_quit),
            ),
        ]

        return pystray.Icon(
            "Gajim", icon=self._get_icon("online"), menu=pystray.Menu(*menu_items)
        )

    @staticmethod
    def _get_sound_toggle_state(_item_name: str) -> bool:
        return not app.settings.get("sounds_on")

    @staticmethod
    def _get_icon(icon_name: str) -> Image.Image:
        status_icon_name = get_status_icon_name(icon_name)
        path = (
            configpaths.get("ICONS")
            / "hicolor"
            / "32x32"
            / "status"
            / f"{status_icon_name}.png"
        )
        return Image.open(path)  # type: ignore


class LinuxStatusIcon(StatusIconBackend):
    def __init__(self) -> None:
        StatusIconBackend.__init__(self)

        self._shutdown = False
        self._status_icon: StatusNotifierItemService | None = None

        self._theme_path = None
        if not app.is_flatpak():
            self._theme_path = str(configpaths.get("ICONS"))

        Gio.bus_get(Gio.BusType.SESSION, callback=self._on_finish)

    def _on_finish(self, obj: Any, res: Gio.AsyncResult) -> None:
        try:
            connection = Gio.bus_get_finish(res)
        except Exception as error:
            log.error(error)
            return

        self._status_icon = StatusNotifierItemService(
            connection, self._get_menu(), self._theme_path, self._on_activate
        )

        log.info("Status icon init successful")

        if app.settings.get("show_trayicon"):
            self._status_icon.register()
            self.update_state(init=True)

    def _get_menu(self) -> DBusMenu:
        toogle_state = int(not app.settings.get("sounds_on"))
        return DBusMenu(
            items=[
                DBusMenuItem(
                    id=1, label=_("Show/Hide Window"), callback=self._on_show_hide
                ),
                DBusMenuItem(
                    id=2,
                    label=_("Status"),
                    children_display="submenu",
                    children=[
                        DBusMenuItem(
                            id=3,
                            label=get_uf_show("online"),
                            callback=lambda: self._on_status_changed("online"),
                        ),
                        DBusMenuItem(
                            id=4,
                            label=get_uf_show("away"),
                            callback=lambda: self._on_status_changed("away"),
                        ),
                        DBusMenuItem(
                            id=5,
                            label=get_uf_show("xa"),
                            callback=lambda: self._on_status_changed("xa"),
                        ),
                        DBusMenuItem(
                            id=6,
                            label=get_uf_show("dnd"),
                            callback=lambda: self._on_status_changed("dnd"),
                        ),
                        DBusMenuItem(id=7, type="separator"),
                        DBusMenuItem(
                            id=8,
                            label=get_uf_show("offline"),
                            callback=lambda: self._on_status_changed("offline"),
                        ),
                    ],
                ),
                DBusMenuItem(
                    id=9, label=_("Start Chat…"), callback=self._on_start_chat
                ),
                DBusMenuItem(
                    id=10,
                    label=_("Mute Sounds"),
                    toggle_type="checkmark",
                    toggle_state=toogle_state,
                    callback=self._on_sounds_mute,
                ),
                DBusMenuItem(
                    id=11, label=_("Preferences"), callback=self._on_preferences
                ),
                DBusMenuItem(id=12, type="separator"),
                DBusMenuItem(id=13, label=_("Quit"), callback=self._on_quit),
            ]
        )

    def update_state(self, init: bool = False) -> None:
        if self._status_icon is None:
            # Status icon is not initialized
            return

        if self._shutdown:
            # Shutdown in progress, don't update icon
            return

        if not init and app.window.get_total_unread_count():
            icon_name = get_status_icon_name("message-new")
            self._status_icon.set_icon(icon_name)
            return

        show = get_global_show()
        icon_name = get_status_icon_name(show)
        self._status_icon.set_icon(icon_name)

    def set_enabled(self, enabled: bool) -> None:
        if self._status_icon is None:
            return

        log.info("Set status icon enabled: %s", enabled)

        if enabled:
            self._status_icon.register()
            self.update_state(init=True)
        else:
            self._status_icon.unregister()

    def is_visible(self) -> bool:
        if self._status_icon is None:
            return False
        return self._status_icon.get_visible()

    def shutdown(self) -> None:
        if self._status_icon is None:
            return
        self._shutdown = True
        self._status_icon.unregister()
