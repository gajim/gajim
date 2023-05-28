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

from __future__ import annotations

from typing import Any
from typing import cast

import sys
from datetime import datetime

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import open_uri
from gajim.common.i18n import _
from gajim.plugins.manifest import PluginManifest

from gajim.gtk.builder import get_builder
from gajim.gtk.status_message_selector import StatusMessageSelector
from gajim.gtk.status_selector import StatusSelector


class AppPage(Gtk.Box):

    __gsignals__ = {
        'unread-count-changed': (GObject.SignalFlags.RUN_LAST,
                                 None,
                                 (int, )),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.get_style_context().add_class('app-page')
        self._unread_count: int = 0

        status_header = Gtk.Label(label=_('Status'))
        status_header.get_style_context().add_class('large-header')
        self.add(status_header)
        status_label = Gtk.Label(
            label=_('Status and status message for all accounts'))
        status_label.get_style_context().add_class('dim-label')
        self.add(status_label)

        self._status_selector = StatusSelector()
        self._status_selector.set_halign(Gtk.Align.CENTER)
        self.add(self._status_selector)

        self._status_message_selector = StatusMessageSelector()
        self._status_message_selector.set_halign(Gtk.Align.CENTER)
        self.add(self._status_message_selector)

        update_label = Gtk.Label(label=_('Updates'))
        update_label.get_style_context().add_class('large-header')
        update_label.get_style_context().add_class('margin-top12')
        self.add(update_label)

        self._app_message_listbox = AppMessageListBox()
        self.add(self._app_message_listbox)

        self.show_all()

    def add_app_message(self,
                        category: str,
                        new_version: str | None = None,
                        new_setup_url: str | None = None
                        ) -> None:

        self._app_message_listbox.add_app_message(
            category, new_version, new_setup_url)
        self._unread_count += 1
        self.emit('unread-count-changed', self._unread_count)

    def add_plugin_update_message(self,
                                  manifests: list[PluginManifest]
                                  ) -> None:
        self._app_message_listbox.add_plugin_update_message(manifests)
        self._unread_count += 1
        self.emit('unread-count-changed', self._unread_count)

    def remove_app_message(self) -> None:
        self._unread_count -= 1
        self.emit('unread-count-changed', self._unread_count)


class AppMessageListBox(Gtk.ListBox):
    def __init__(self) -> None:
        Gtk.ListBox.__init__(self)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_halign(Gtk.Align.CENTER)
        self.set_size_request(400, -1)
        self.get_style_context().add_class('app-message-listbox')

        self._placeholder = Gtk.Label(label=self._get_update_text())
        self._placeholder.get_style_context().add_class('dim-label')
        self._placeholder.show()
        self.set_placeholder(self._placeholder)

        app.settings.connect_signal('last_update_check', self._on_update_check)

        self.show_all()

    def add_app_message(self,
                        category: str,
                        new_version: str | None = None,
                        new_setup_url: str | None = None
                        ) -> None:

        row = AppMessageRow(category, new_version, new_setup_url)
        self.add(row)

    def add_plugin_update_message(self,
                                  manifests: list[PluginManifest]
                                  ) -> None:
        row = AppMessageRow('plugin-updates', plugin_manifests=manifests)
        self.add(row)

    def remove_app_message(self, row: Gtk.ListBoxRow) -> None:
        self.remove(row)
        app_page = cast(AppPage, self.get_parent())
        app_page.remove_app_message()

    def _on_update_check(self, *args: Any) -> None:
        self._placeholder.set_text(self._get_update_text())

    @staticmethod
    def _get_update_text() -> str:
        gajim = ''
        plugins = _('Plugins: No updates available')
        if not app.settings.get('check_for_update'):
            gajim = _('Gajim: Update check disabled in preferences')

        if not app.settings.get('plugins_update_check'):
            plugins = _('Plugins: Update check disabled in preferences')

        if any(gajim and plugins):
            return f'{gajim}\n{plugins}'

        last_check = app.settings.get('last_update_check')
        if not last_check:
            gajim = _('Gajim: No updates available (last check: never)')
            return f'{gajim}\n{plugins}'

        date = datetime.strptime(last_check, '%Y-%m-%d %H:%M')
        format_string = app.settings.get('date_format')
        gajim = _('Gajim: No updates available '
                  '(last check: %s)') % date.strftime(format_string)
        return f'{gajim}\n{plugins}'


class AppMessageRow(Gtk.ListBoxRow):
    def __init__(self,
                 category: str,
                 new_version: str | None = None,
                 new_setup_url: str | None = None,
                 plugin_manifests: list[PluginManifest] | None = None
                 ) -> None:

        Gtk.ListBoxRow.__init__(self)
        self._plugin_manifests = plugin_manifests
        self._new_setup_url = new_setup_url

        self._ui = get_builder('app_page.ui')

        if category == 'allow-gajim-update-check':
            self.add(self._ui.gajim_update_check)

        if category == 'gajim-update-available':
            self.add(self._ui.gajim_update)
            text = _('Gajim %s is available') % new_version
            self._ui.update_message.set_text(text)

        if category == 'plugin-updates':
            self.add(self._ui.plugin_updates)

        if category == 'plugin-updates-finished':
            self.add(self._ui.plugin_updates_finished)

        self._ui.connect_signals(self)
        self.show_all()

    def _remove_app_message(self) -> None:
        list_box = cast(AppMessageListBox, self.get_parent())
        list_box.remove_app_message(self)

    def _on_activate_check_clicked(self, _button: Gtk.Button) -> None:
        app.app.check_for_gajim_updates()
        self._remove_app_message()

    def _on_dismiss_check_clicked(self, _button: Gtk.Button) -> None:
        app.settings.set('check_for_update', False)
        self._remove_app_message()

    def _on_download_update_clicked(self, _button: Gtk.Button) -> None:
        assert self._new_setup_url is not None
        if sys.platform == 'win32':
            open_uri(self._new_setup_url)
        else:
            open_uri('https://gajim.org/download/')
        self._remove_app_message()

    def _on_dismiss_clicked(self, _button: Gtk.Button) -> None:
        self._remove_app_message()

    def _on_update_plugins_clicked(self, _button: Gtk.Button) -> None:
        if self._ui.auto_update_plugins.get_active():
            app.settings.set('plugins_auto_update', True)
        assert self._plugin_manifests is not None
        app.plugin_repository.download_plugins(self._plugin_manifests)
        self._remove_app_message()

    def _on_dismiss_update_notification(self, _button: Gtk.Button) -> None:
        if self._ui.notify_after_plugin_updates.get_active():
            app.settings.set('plugins_notify_after_update', False)
        self._remove_app_message()

    def _on_open_plugins(self, _button: Gtk.Button) -> None:
        app.app.activate_action('plugins', None)
        self._remove_app_message()
