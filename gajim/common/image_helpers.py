# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging
from io import BytesIO

from gi.repository import GdkPixbuf
from gi.repository import GLib
from PIL import Image
from PIL import ImageFile

log = logging.getLogger('gajim.c.image_helpers')

ImageFile.LOAD_TRUNCATED_IMAGES = True


def get_pixbuf_from_data(data: bytes) -> GdkPixbuf.Pixbuf | None:
    '''
    Load data into PixbufLoader and return GdkPixbuf.Pixbuf if possible.
    Pillow is used as fallback mechanism.
    '''
    pixbufloader = GdkPixbuf.PixbufLoader()
    try:
        pixbufloader.write(data)
        pixbufloader.close()
        pixbuf = pixbufloader.get_pixbuf()
    except GLib.Error:
        pixbufloader.close()

        log.warning(
            'Loading image data using PixbufLoader failed. '
            'Trying to convert image data using Pillow.'
        )
        try:
            image = Image.open(BytesIO(data)).convert('RGBA')  # pyright: ignore
            array = GLib.Bytes.new(image.tobytes())  # pyright: ignore
            width, height = image.size
            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                array, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4
            )
            image.close()
        except Exception:
            log.warning(
                'Could not use Pillow to convert image data. '
                'Image cannot be displayed',
                exc_info=True,
            )
            return None

    if pixbuf is None:
        return None

    pixbuf = pixbuf.apply_embedded_orientation()
    return pixbuf
