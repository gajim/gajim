from __future__ import annotations

import typing

import enum

import winrt.system
from winrt.windows.foundation import EventRegistrationToken
from winrt.windows.foundation import TypedEventHandler
from winrt.windows.ui import Color

class UIColorType(enum.IntEnum):
    BACKGROUND = 0
    FOREGROUND = 1
    ACCENT_DARK3 = 2
    ACCENT_DARK2 = 3
    ACCENT_DARK1 = 4
    ACCENT = 5
    ACCENT_LIGHT1 = 6
    ACCENT_LIGHT2 = 7
    ACCENT_LIGHT3 = 8
    COMPLEMENT = 9

@typing.final
class UISettings:
    def get_color_value(self, desired_color: UIColorType, /) -> Color: ...
    def add_color_values_changed(
        self, handler: TypedEventHandler[UISettings, winrt.system.Object], /
    ) -> EventRegistrationToken: ...
