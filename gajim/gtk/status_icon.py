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

import typing
from typing import Any

import logging
import sys

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import Display
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.util.status import get_global_show
from gajim.common.util.status import get_uf_show

from gajim.gtk.builder import get_builder
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import open_window

if app.is_installed('APPINDICATOR'):
    from gi.repository import AppIndicator3 as AppIndicator

elif app.is_installed('AYATANA_APPINDICATOR'):
    from gi.repository import AyatanaAppIndicator3 as AppIndicator

if typing.TYPE_CHECKING:
    from gi.repository import AyatanaAppIndicator3 as AppIndicator


log = logging.getLogger('gajim.gtk.statusicon')


class StatusIcon:
    def __init__(self) -> None:
        if self._can_use_libindicator():
            app.settings.connect_signal('show_trayicon',
                                        self._on_setting_changed)
            self._backend = AppIndicatorIcon()
            log.info('Use AppIndicator3 backend')
        elif app.is_display(Display.WAYLAND):
            self._backend = NoneBackend()
            log.info('libappindicator not found or disabled')
        else:
            app.settings.connect_signal('show_trayicon',
                                        self._on_setting_changed)
            self._backend = GtkStatusIcon()
            log.info('Use GtkStatusIcon backend')

    @staticmethod
    def _can_use_libindicator() -> bool:
        if not app.settings.get('use_libappindicator'):
            return False
        return (app.is_installed('APPINDICATOR') or
                app.is_installed('AYATANA_APPINDICATOR'))

    def _on_setting_changed(self, *args: Any) -> None:
        self._backend.update_state()

    def connect_unread_widget(self, widget: Gtk.Widget, signal: str) -> None:
        widget.connect(signal, self._on_unread_count_changed)

    def _on_unread_count_changed(self, *args: Any) -> None:
        if not app.settings.get('trayicon_notification_on_events'):
            return
        self._backend.update_state()

    def is_visible(self) -> bool:
        return self._backend.is_visible()

    def shutdown(self) -> None:
        self._backend.shutdown()


class NoneBackend:
    def update_state(self, init: bool = False) -> None:
        pass

    def is_visible(self) -> bool:
        return False

    def shutdown(self) -> None:
        pass


class GtkMenuBackend(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)
        self._popup_menus: list[Gtk.Menu] = []

        self._ui = get_builder('systray_context_menu.ui')
        self._ui.sounds_mute_menuitem.set_active(
            not app.settings.get('sounds_on'))
        self._add_status_menu()

        self._ui.connect_signals(self)

        self.register_events([
            ('our-show', ged.GUI1, self._on_our_show),
            ('account-enabled', ged.GUI1, self._on_account_enabled),
            ('account-connected', ged.CORE, self._on_account_state),
            ('account-disconnected', ged.CORE, self._on_account_state),
        ])

        for client in app.get_clients():
            client.connect_signal('state-changed',
                                  self._on_client_state_changed)

    def update_state(self, init: bool = False) -> None:
        raise NotImplementedError

    def is_visible(self) -> bool:
        raise NotImplementedError

    def _add_status_menu(self) -> None:
        sub_menu = Gtk.Menu()

        for show in ('online', 'away', 'xa', 'dnd'):
            uf_show = get_uf_show(show, use_mnemonic=True)
            item = Gtk.MenuItem.new_with_mnemonic(uf_show)
            sub_menu.append(item)
            item.connect('activate', self._on_show, show)

        sub_menu.append(Gtk.SeparatorMenuItem())

        uf_show = get_uf_show('offline', use_mnemonic=True)
        item = Gtk.MenuItem.new_with_mnemonic(uf_show)
        item.connect('activate', self._on_show, 'offline')
        sub_menu.append(item)
        sub_menu.show_all()

        self._popup_menus.append(sub_menu)
        self._ui.status_menu.set_submenu(sub_menu)

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        client = app.get_client(event.account)
        client.connect_signal('state-changed', self._on_client_state_changed)

    def _on_client_state_changed(self,
                                 _client: Client,
                                 _signal_name: str,
                                 _state: SimpleClientState) -> None:
        self.update_state()

    def _on_our_show(self, _event: events.ShowChanged) -> None:
        self.update_state()

    def _on_account_state(
        self,
        _event: events.AccountConnected | events.AccountDisconnected
    ) -> None:
        account_connected = bool(app.get_number_of_connected_accounts() > 0)
        self._ui.start_chat_menuitem.set_sensitive(account_connected)

    @staticmethod
    def _on_new_chat(_widget: Gtk.MenuItem) -> None:
        app.app.activate_action('start-chat', GLib.Variant('as', ['', '']))

    @staticmethod
    def _on_sounds_mute(widget: Gtk.CheckMenuItem) -> None:
        app.settings.set('sounds_on', not widget.get_active())

    def _on_toggle_window(self, _widget: Gtk.MenuItem) -> None:
        if app.window.is_minimized():
            app.window.unminimize()
        elif app.window.is_withdrawn():
            app.window.show()
        else:
            app.window.hide()

    @staticmethod
    def _on_preferences(_widget: Gtk.MenuItem) -> None:
        open_window('Preferences')

    @staticmethod
    def _on_quit(_widget: Gtk.MenuItem) -> None:
        app.window.quit()

    @staticmethod
    def _on_show(_widget: Gtk.MenuItem, show: str) -> None:
        app.app.change_status(status=show)


class GtkStatusIcon(GtkMenuBackend):
    def __init__(self) -> None:
        GtkMenuBackend.__init__(self)
        self._hide_menuitem_added = False
        self._shutdown = False

        self._status_icon = Gtk.StatusIcon()
        self._status_icon.set_tooltip_text('Gajim')  # Needed for Windows
        self._status_icon.connect('activate', self._on_activate)
        self._status_icon.connect('popup-menu', self._on_popup_menu)
        self._status_icon.connect('size-changed', self._on_size_changed)

        self.update_state(init=True)

    def update_state(self, init: bool = False) -> None:
        if self._shutdown:
            # Shutdown in progress, don't update icon
            return

        if not app.settings.get('show_trayicon'):
            self._status_icon.set_visible(False)
            return

        self._status_icon.set_visible(True)

        if not init and app.window.get_total_unread_count():
            icon_name = 'dcraven-message-new'
            if app.is_flatpak():
                icon_name = 'mail-message-new'
            self._status_icon.set_from_icon_name(icon_name)
            return

        show = get_global_show()
        icon_name = get_icon_name(show)
        self._status_icon.set_from_icon_name(icon_name)

    def is_visible(self) -> bool:
        return self._status_icon.get_visible()

    def shutdown(self) -> None:
        # Necessary on Windows in order to remove icon from tray on shutdown
        self._shutdown = True
        self._status_icon.set_visible(False)

    def _on_size_changed(self,
                         _status_icon: Gtk.StatusIcon,
                         size: int) -> None:
        self.update_state()

    def _on_popup_menu(self,
                       status_icon: Gtk.StatusIcon,
                       button: int,
                       activate_time: int) -> None:

        if button in (1, 2):
            self._on_activate(status_icon)
        elif button == 3:
            self._build_menu(button, activate_time)

    def _on_activate(self, _status_icon: Gtk.StatusIcon) -> None:
        if app.window.has_toplevel_focus():
            app.window.hide()
        else:
            app.window.show()

    def _build_menu(self, button: int, event_time: int) -> None:
        for menu in self._popup_menus:
            menu.destroy()

        self._add_status_menu()

        self._ui.sounds_mute_menuitem.set_active(
            not app.settings.get('sounds_on'))

        if sys.platform == 'win32':
            # Workaround for popup menu on Windows
            if not self._hide_menuitem_added:
                self._ui.systray_context_menu.prepend(
                    Gtk.SeparatorMenuItem())
                item = Gtk.MenuItem.new_with_label(
                    _('Hide this menu'))
                self._ui.systray_context_menu.prepend(item)
                self._hide_menuitem_added = True

        self._ui.systray_context_menu.show_all()
        self._ui.systray_context_menu.popup(
            None, None, None, None, button, event_time)


class AppIndicatorIcon(GtkMenuBackend):
    def __init__(self) -> None:
        GtkMenuBackend.__init__(self)

        assert AppIndicator is not None
        self._status_icon = AppIndicator.Indicator.new(
            'Gajim',
            'org.gajim.Gajim',
            AppIndicator.IndicatorCategory.COMMUNICATIONS)
        if not app.is_flatpak():
            self._status_icon.set_icon_theme_path(str(configpaths.get('ICONS')))
        self._status_icon.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._status_icon.set_menu(self._ui.systray_context_menu)
        self._status_icon.set_secondary_activate_target(
            self._ui.toggle_window_menuitem)

        self.update_state(init=True)

    def update_state(self, init: bool = False) -> None:
        if not app.settings.get('show_trayicon'):
            self._status_icon.set_status(AppIndicator.IndicatorStatus.PASSIVE)
            return

        self._status_icon.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        if not init and app.window.get_total_unread_count():
            icon_name = 'dcraven-message-new'
            if app.is_flatpak():
                icon_name = 'mail-message-new'
            self._status_icon.set_icon_full(icon_name, _('Pending Event'))
            return

        if app.is_flatpak():
            self._status_icon.set_icon_full('org.gajim.Gajim', 'online')
            return

        show = get_global_show()
        icon_name = get_icon_name(show)
        self._status_icon.set_icon_full(icon_name, show)

    def is_visible(self) -> bool:
        assert AppIndicator is not None
        status = self._status_icon.get_status()
        return status == AppIndicator.IndicatorStatus.ACTIVE

    def shutdown(self) -> None:
        pass
