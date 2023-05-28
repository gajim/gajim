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

# Based on https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/apply-windows-themes

from __future__ import annotations

from typing import Callable

import logging

from winsdk.windows.ui import Color
from winsdk.windows.ui.viewmanagement import UIColorType
from winsdk.windows.ui.viewmanagement import UISettings

from gajim.common import app
from gajim.common.events import StyleChanged

log = logging.getLogger('gajim.c.winapi.system_style')


class SystemStyleListener:
    def __init__(self, callback: Callable[..., None]) -> None:
        self._prefer_dark: bool | None = None
        self._callback = callback

        try:
            self._ui_settings = UISettings()
        except OSError as err:
            log.warning('winsdk UISettings not available:%s', err)
            return

        self._ui_settings.add_color_values_changed(
            self._signal_color_values_changed)
        foreground_color = self._ui_settings.get_color_value(
            UIColorType.FOREGROUND)
        self._prefer_dark = self._is_color_light(foreground_color)

    @staticmethod
    def _is_color_light(clr: Color) -> bool:
        return ((5 * clr.g) + (2 * clr.r) + clr.b) > (8 * 128)

    def _signal_color_values_changed(self, ui_settings: UISettings, _) -> None:
        foreground_color = ui_settings.get_color_value(UIColorType.FOREGROUND)
        dark_theme = self._is_color_light(foreground_color)
        if dark_theme != self._prefer_dark:
            self._prefer_dark = dark_theme
            self._callback()
            app.ged.raise_event(StyleChanged())

    @property
    def prefer_dark(self) -> bool | None:
        return self._prefer_dark
