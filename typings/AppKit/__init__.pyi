
from __future__ import annotations

from typing import Any

class NSLocale:
    @classmethod
    def currentLocale(cls) -> Any: ...


class NSSound:
    @classmethod
    def alloc(cls) -> NSSound: ...
    def initWithContentsOfFile_byReference_(self, url: str, byref: bool) -> None: ...
    def play(self) -> None: ...
