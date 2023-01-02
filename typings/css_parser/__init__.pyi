from __future__ import annotations

from typing import Optional
from typing import Union

from pathlib import Path

from . import css as css
from . import serialize as serialize
from . import stylesheets as stylesheets
from .serialize import CSSSerializer
from .stylesheets import MediaList

ser: CSSSerializer


def parseFile(filename: Union[str, Path], href: Optional[str] = ..., media: Union[MediaList, list[str], str, None] = ..., title: Optional[str] = ..., validate: Optional[bool] = ...) -> None: ...
