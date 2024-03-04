# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging
import sys
from collections.abc import Callable

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app
from gajim.common.events import StyleChanged

log = logging.getLogger('gajim.c.dbus.system_style')


class SystemStyleListener:
    def __init__(self, callback: Callable[..., None]) -> None:
        self._prefer_dark: bool | None = None
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
            self._prefer_dark = result[0] == 1
        except GLib.Error as error:
            log.error('Couldn’t read the color-scheme setting: %s',
                      error.message)
            return

    def _signal_setting_changed(self,
                                _proxy: Gio.DBusProxy,
                                _sender_name: str | None,
                                signal_name: str,
                                parameters: GLib.Variant,
                                *_user_data: Any
                                ) -> None:
        if signal_name != 'SettingChanged':
            return

        namespace, name, value = parameters
        if (namespace == 'org.freedesktop.appearance' and
                name == 'color-scheme'):
            self._prefer_dark = value == 1
            self._callback()
            app.ged.raise_event(StyleChanged())

    @property
    def prefer_dark(self) -> bool | None:
        return self._prefer_dark
