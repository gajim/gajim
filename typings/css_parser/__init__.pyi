from __future__ import annotations

from pathlib import Path

from . import css as css
from . import serialize as serialize
from . import stylesheets as stylesheets
from .serialize import CSSSerializer
from .stylesheets import MediaList

ser: CSSSerializer


def parseFile(filename: str | Path, href: str | None = ..., media: MediaList | list[str] | str | None = ..., title: str | None = ..., validate: bool | None = ...) -> None: ...
