# largely stolen from https://github.com/flavono123/identicon
import hashlib
from functools import lru_cache

from gi.overrides.GdkPixbuf import GdkPixbuf
from gi.repository import GLib
from PIL import Image
from PIL import ImageDraw

SIZE1 = 5
SIZE2 = 2


def render_identicon(code: str) -> Image.Image:
    hex_list = _to_hash_hex_list(code)
    color = _extract_color(hex_list)
    grid = _build_grid(hex_list)
    flatten_grid = _flat_to_list(grid)
    pixels = _set_pixels(flatten_grid)
    identicon_im = _draw_identicon(color, flatten_grid, pixels)
    return identicon_im


def _to_hash_hex_list(code: str) -> str:
    h = hashlib.md5(code.encode('utf8'))
    return h.hexdigest()


def _extract_color(hex_list):
    r, g, b = tuple(hex_list[i:i + 2]
                    for i in range(0, 2 * 3, 2))

    return f'#{r}{g}{b}'


def _set_pixels(flatten_grid):
    pixels = []
    for i in range(len(flatten_grid)):
        x = int(i % 5 * SIZE1) + SIZE2
        y = int(i // 5 * SIZE1) + SIZE2

        top_left = (x, y)
        bottom_right = (x + SIZE1, y + SIZE1)

        pixels.append([top_left, bottom_right])

    return pixels


def _build_grid(hex_list):
    # FIXME: does not return the same image as Cheogram Android
    # Tailing hex_list to rear 15 bytes
    hex_list_tail = hex_list[2:]

    # Make 3x5 grid, half of the symmetric grid(left side)
    hex_half_grid = [[hex_list_tail[col:col + 2]
                      for col in range(row, row + 2 * 3, 2)]
                     for row in range(0, 2 * 3 * 5, 2 * 3)]

    hex_grid = _mirror_row(hex_half_grid)

    int_grid = [[int(e, base=16) for e in row] for row in hex_grid]

    # TODO: Using more entropies, should be deprecated
    filtered_grid = [[byte if byte % 2 == 0 else 0 for byte in row]
                     for row in int_grid]

    return filtered_grid


def _mirror_row(half_grid):
    opposite_half_grid = [list(reversed(row)) for row in half_grid]
    # FIXME: just for odd(5) num column now
    grid = [row + mirrored_row[1:]
            for row, mirrored_row
            in zip(half_grid, opposite_half_grid, strict=True)]

    return grid


def _flat_to_list(nested_list):
    flatten_list = [e for row in nested_list for e in row]

    return flatten_list


def _draw_identicon(color, grid_list, pixels):
    identicon_im = Image.new(
        'RGBA',
        (SIZE1 * 5 + SIZE2 * 2, SIZE1 * 5 + SIZE2 * 2))
    draw = ImageDraw.Draw(identicon_im)
    for grid, pixel in zip(grid_list, pixels, strict=True):
        if grid != 0:  # for not zero
            draw.rectangle(pixel, fill=color)

    return identicon_im


@lru_cache(maxsize=128)
def get_identicon_pixbuf(thread_id: str, size: int) -> GdkPixbuf.Pixbuf:
    im = render_identicon(thread_id)
    # credit: https://stackoverflow.com/a/8892894
    width, height = im.size
    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(im.tobytes()),
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        width,
        height,
        width * 4,
    )
    # TODO: turn off antialiasing somehow?
    pixbuf = pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.TILES)
    return pixbuf
