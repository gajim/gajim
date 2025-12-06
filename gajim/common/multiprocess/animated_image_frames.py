# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import typing

import io
from pathlib import Path

from PIL import Image


def extract_frames(animated_image_path: Path) -> list[tuple[bytes, int]]:
    with Image.open(animated_image_path) as pil_img:
        frames: list[tuple[bytes, int]] = []
        n_frames: int = getattr(pil_img, "n_frames", 1)

        for i in range(n_frames):
            pil_img.seek(i)
            frame = pil_img.copy()
            with io.BytesIO() as byte_io:
                frame.save(
                    byte_io,
                    format="WEBP",
                    lossless=False,
                    method=0,
                    exact=False,
                    quality=50,
                    alpha_quality=50,
                )
                frame_bytes = byte_io.getvalue()
            duration_ms = typing.cast(int, frame.info.get("duration", 100))
            frames.append((frame_bytes, duration_ms))
            del frame

    return frames
