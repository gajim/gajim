# Copyright (C) 2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from typing import Any
from typing import Union

import sys
import logging

from gi.repository import Gtk
from gi.repository import GLib

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common import events
from gajim.common.client import Client
from gajim.common.const import Display
from gajim.common.const import SimpleClientState
from gajim.common.i18n import _
from gajim.common.helpers import get_global_show
from gajim.common.helpers import get_uf_show
from gajim.common.ged import EventHelper

from .builder import get_builder
from .util import get_icon_name
from .util import save_main_window_position
from .util import restore_main_window_position
from .util import open_window

if app.is_installed('APPINDICATOR'):
    from gi.repository import AppIndicator3 as appindicator  # pylint: disable=ungrouped-imports

elif app.is_installed('AYATANA_APPINDICATOR'):
    from gi.repository import AyatanaAppIndicator3 as appindicator  # pylint: disable=ungrouped-imports


log = logging.getLogger('gajim.gui.statusicon')


class StatusIcon:
    def __init__(self) -> None:
        if self._can_use_libindicator():
            app.settings.connect_signal('show_trayicon',
                                        self._on_setting_changed)
            self._backend = AppIndicator()
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
        count = app.window.get_total_unread_count()
        self._backend.update_state(count=count)

    def connect_unread_widget(self, widget: Gtk.Widget, signal: str) -> None:
        widget.connect(signal, self._on_unread_count_changed)

    def _on_unread_count_changed(self, *args: Any) -> None:
        if not app.settings.get('trayicon_notification_on_events'):
            return
        count = app.window.get_total_unread_count()
        self._backend.update_state(count=count)

    def is_visible(self) -> bool:
        return self._backend.is_visible()

    def shutdown(self) -> None:
        self._backend.shutdown()


class NoneBackend:
    def update_state(self, count: int = 0) -> None:
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

    def update_state(self, count: int = 0) -> None:
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

    def _on_account_state(self,
                          _event: Union[events.AccountConnected,
                                        events.AccountDisonnected]
                          ) -> None:
        account_connected = bool(app.get_number_of_connected_accounts() > 0)
        self._ui.start_chat_menuitem.set_sensitive(account_connected)

    @staticmethod
    def _on_new_chat(_widget: Gtk.MenuItem) -> None:
        app.app.activate_action('start-chat', GLib.Variant('s', ''))

    @staticmethod
    def _on_sounds_mute(widget: Gtk.CheckMenuItem) -> None:
        app.settings.set('sounds_on', not widget.get_active())

    def _on_toggle_window(self, _widget: Gtk.MenuItem) -> None:
        self._on_activate()

    def _on_activate(self, *args: Any) -> None:
        if app.settings.get('last_main_window_visible'):
            save_main_window_position()
            app.window.hide()
            return

        if not app.window.get_property('visible'):
            # Window was minimized
            restore_main_window_position()

        if not app.settings.get('main_window_skip_taskbar'):
            app.window.set_property('skip-taskbar-hint', False)
        app.window.present_with_time(Gtk.get_current_event_time())

    @staticmethod
    def _on_preferences(_widget: Gtk.MenuItem) -> None:
        open_window('Preferences')

    @staticmethod
    def _on_quit(_widget: Gtk.MenuItem) -> None:
        app.window.quit()

    @staticmethod
    def _on_show(_widget: Gtk.MenuItem, show: str) -> None:
        app.interface.change_status(status=show)


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

        self.update_state()

    def update_state(self, count: int = 0) -> None:
        if self._shutdown:
            # Shutdown in progress, don't update icon
            return

        if not app.settings.get('show_trayicon'):
            self._status_icon.set_visible(False)
            return

        self._status_icon.set_visible(True)

        if count > 0:
            self._status_icon.set_from_icon_name('dcraven-message-new')
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
                       _status_icon: Gtk.StatusIcon,
                       button: int,
                       activate_time: int) -> None:
        if button == 1:
            self._on_activate()
        elif button == 2:
            self._on_activate()
        elif button == 3:
            self._build_menu(activate_time)

    def _build_menu(self, event_time: int) -> None:
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
            None, None, None, None, 0, event_time)


class AppIndicator(GtkMenuBackend):
    def __init__(self) -> None:
        GtkMenuBackend.__init__(self)

        self._status_icon = appindicator.Indicator.new(
            'Gajim',
            'dcraven-online',
            appindicator.IndicatorCategory.COMMUNICATIONS)
        self._status_icon.set_icon_theme_path(str(configpaths.get('ICONS')))
        self._status_icon.set_status(appindicator.IndicatorStatus.ACTIVE)
        self._status_icon.set_menu(self._ui.systray_context_menu)
        self._status_icon.set_secondary_activate_target(
            self._ui.toggle_window_menuitem)

        self.update_state()

    def update_state(self, count: int = 0) -> None:
        if not app.settings.get('show_trayicon'):
            self._status_icon.set_status(appindicator.IndicatorStatus.PASSIVE)
            return

        self._status_icon.set_status(appindicator.IndicatorStatus.ACTIVE)

        if count > 0:
            icon_name = 'dcraven-message-new'
            self._status_icon.set_icon_full(icon_name, _('Pending Event'))
            return

        show = get_global_show()
        icon_name = get_icon_name(show)
        self._status_icon.set_icon_full(icon_name, show)

    def is_visible(self) -> bool:
        status = self._status_icon.get_status()
        return status == appindicator.IndicatorStatus.ACTIVE

    def shutdown(self) -> None:
        pass
