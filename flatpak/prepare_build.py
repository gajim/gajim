#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logging.basicConfig(level='INFO', format='%(message)s')

REPLACE = [
    (Path('gajim/__init__.py'), 'IS_FLATPAK = False', 'IS_FLATPAK = True'),
]

NIGHTLY_REPLACE = [
    (
        Path('gajim/__init__.py'),
        'IS_FLATPAK_NIGHTLY = False',
        'IS_FLATPAK_NIGHTLY = True',
    ),
    (
        Path('data/org.gajim.Gajim.metainfo.xml.in'),
        'org.gajim.Gajim',
        'org.gajim.Gajim.Devel',
    ),
    (
        Path('data/org.gajim.Gajim.metainfo.xml.in'),
        '<name>Gajim</name>',
        '<name>Gajim (Nightly)</name>',
    ),
]


def replace_string_in_file(path: Path, old_string: str, new_string: str) -> None:
    content = path.read_text()
    content = content.replace(old_string, new_string)
    path.write_text(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepare Flatpak Build')
    parser.add_argument(
        '--nightly', action='store_true', help='If this is a nightly build'
    )

    args = parser.parse_args()

    for path, old, new in REPLACE:
        replace_string_in_file(path, old, new)

    if args.nightly:
        for path, old, new in NIGHTLY_REPLACE:
            replace_string_in_file(path, old, new)
