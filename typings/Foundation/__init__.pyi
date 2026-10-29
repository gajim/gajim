from __future__ import annotations

from typing import Any
from typing import Self

class NSURL:
    @classmethod
    def fileURLWithPath_(cls, path: str) -> Any: ...

class NSObject:
    @classmethod
    def alloc(cls) -> Self: ...
    def init(self) -> Self: ...
