"""
This type stub file was generated by pyright.
"""

import typing

import Foundation
import objc

from . import _base

class Icon(_base.Icon):
    _ACTION_SELECTOR: typing.Any = ...
    _MENU_ITEM_SELECTOR: typing.Any = ...
    HAS_DEFAULT_ACTION: bool = ...
    HAS_MENU_RADIO: bool = ...
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None: ...

class IconDelegate(Foundation.NSObject):
    @objc.namedSelector(Icon._ACTION_SELECTOR)
    def activate_button(self, sender: typing.Any) -> None: ...
    @objc.namedSelector(Icon._MENU_ITEM_SELECTOR)
    def activate_menu_item(self, sender: typing.Any) -> None: ...
