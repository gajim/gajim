from __future__ import annotations

from typing import Optional
from typing import Union

from pathlib import Path

from . import css as css
from . import serialize as serialize
from . import stylesheets as stylesheets
from .stylesheets import MediaList
from .serialize import CSSSerializer


ser: CSSSerializer


def parseFile(filename: Union[str, Path], href: Optional[str] = ..., media: Union[MediaList, list[str], str, None] = ..., title: Optional[str] = ..., validate: Optional[bool] = ...) -> None: ...
