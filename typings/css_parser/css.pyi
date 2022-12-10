from __future__ import annotations

from typing import Any


class CSSRule:

    STYLE_RULE: int


class CSSStyleSheet:

    cssText: bytes

    def __iter__(self) -> CSSStyleRule: ...
    def add(self, rule: CSSStyleRule) -> None: ...


class CSSStyleRule(CSSRule):

    style: CSSStyleDeclaration
    type: int
    selectorText: str

    def __init__(self, selectorText: str) -> None: ...
    def __next__(self) -> CSSStyleRule: ...


class CSSStyleDeclaration:

    def __getitem__(self, cssname: str) -> str: ...
    def __setitem__(self, cssname: str, value: Any) -> None: ...
    def getPropertyValue(self, property: str) -> Any: ...
    def removeProperty(self, property: str) -> None: ...
