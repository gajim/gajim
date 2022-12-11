#!/usr/bin/env python3
import os
import shutil
from argparse import ArgumentParser
from subprocess import run

ICON_SVG = 'gajim/data/icons/hicolor/scalable/apps/org.gajim.Gajim.svg'


def create_icns(icon_path: str) -> None:
    tmpdir = 'Gajim.iconset'
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    os.mkdir(tmpdir)

    for size_pt in [16, 32, 128, 256, 512]:
        for scale in [1, 2]:
            size_px = scale * size_pt
            scale_txt = '@{}'.format(scale) if scale != 1 else ''
            png_fn = 'icon_{}x{}{}.png'.format(size_pt, size_pt, scale_txt)
            png_path = os.path.join(tmpdir, png_fn)
            run(['inkscape', '-z', '-e', png_path,
                 '-w', str(size_px), '-h', str(size_px), '-y', '0',
                 ICON_SVG])
    run(['iconutil', '-c', 'icns', '-o', icon_path, tmpdir])

    shutil.rmtree(tmpdir)


if __name__ == '__main__':
    parser = ArgumentParser(description='Create a macOS .icns icon. '
                            'Requires Inkscape and iconutil (macOS).')
    parser.add_argument('output', help='bundle output location')
    args = parser.parse_args()

    create_icns(args.output)
