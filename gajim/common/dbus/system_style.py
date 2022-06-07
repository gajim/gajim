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
from typing import Callable
from typing import cast
from typing import Optional

import sys
import logging

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app
from gajim.common.events import StyleChanged

log = logging.getLogger('gajim.c.dbus.system_style')


class SystemStyleListener:
    def __init__(self, callback: Callable[..., None]) -> None:
        self._prefer_dark: Optional[bool] = None
        self._callback = callback

        if sys.platform in ('win32', 'darwin'):
            return

        try:
            self.dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                'org.freedesktop.portal.Desktop',
                '/org/freedesktop/portal/desktop',
                'org.freedesktop.portal.Settings',
                None
            )
        except GLib.Error as error:
            log.info('Settings portal not found: %s', error)
            return

        self.dbus_proxy.connect('g-signal', self._signal_setting_changed)
        self.read_color_scheme()

    def read_color_scheme(self) -> None:
        try:
            result = self.dbus_proxy.call_sync(
                'Read',
                GLib.Variant('(ss)', ('org.freedesktop.appearance',
                                      'color-scheme')),
                Gio.DBusCallFlags.NO_AUTO_START,
                -1,
                None)
            (self._prefer_dark,) = cast(tuple[bool], result)
        except GLib.Error as error:
            log.error('Couldn’t read the color-scheme setting: %s',
                      error.message)
            return

    def _signal_setting_changed(self,
                                _proxy: Gio.DBusProxy,
                                _sender_name: Optional[str],
                                signal_name: str,
                                parameters: GLib.Variant,
                                *_user_data: Any
                                ) -> None:
        if signal_name != 'SettingChanged':
            return

        namespace, name, value = parameters
        if (namespace == 'org.freedesktop.appearance' and
            name == 'color-scheme'):
            self._prefer_dark = (value == 1)
            self._callback()
            app.ged.raise_event(StyleChanged())

    @property
    def prefer_dark(self) -> Optional[bool]:
        return self._prefer_dark
