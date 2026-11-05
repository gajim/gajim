# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from pathlib import Path

from gajim.common.util.image import create_thumbnail_with_pillow
from gajim.common.util.image import create_thumbnail_with_pixbuf
from gajim.common.util.image import UnknownImageFormat


def create_thumbnail(
    input_: bytes | Path, output: Path | None, size: int
) -> tuple[bytes, dict[str, Any]]:
    try:
        thumbnail_bytes = create_thumbnail_with_pillow(input_, size)
    except UnknownImageFormat:
        thumbnail_bytes = create_thumbnail_with_pixbuf(input_, size)

    if output is not None:
        output.write_bytes(thumbnail_bytes)
    return thumbnail_bytes, {}
