# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Based on https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/apply-windows-themes

from __future__ import annotations

from typing import Any

import logging
from collections.abc import Callable

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
            self._ui_settings.add_color_values_changed(
                self._signal_color_values_changed)
            self._prefer_dark = self._get_prefer_dark()
        except Exception as error:
            log.warning('Failed to init winsdk.UISettings: %s', error)
            return

    def _get_prefer_dark(self) -> bool:
        foreground_color = self._ui_settings.get_color_value(
            UIColorType.FOREGROUND)
        return self._is_color_light(foreground_color)

    @staticmethod
    def _is_color_light(clr: Color) -> bool:
        return ((5 * clr.g) + (2 * clr.r) + clr.b) > (8 * 128)

    def _signal_color_values_changed(
        self,
        _ui_settings: UISettings | None,
        *args: Any
    ) -> None:

        prefer_dark = self._get_prefer_dark()
        if prefer_dark != self._prefer_dark:
            self._prefer_dark = prefer_dark
            self._callback()
            app.ged.raise_event(StyleChanged())

    @property
    def prefer_dark(self) -> bool | None:
        return self._prefer_dark
