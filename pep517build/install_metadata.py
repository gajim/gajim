#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

logging.basicConfig(level='INFO', format='%(message)s')

DEFAULT_METADATA_PATH = Path('dist/metadata')

FILES = {
    'gajim-remote.1.gz': 'share/man/man1',
    'gajim.1.gz': 'share/man/man1',
    'org.gajim.Gajim.desktop': 'share/applications',
    'org.gajim.Gajim-symbolic.svg': 'share/icons/hicolor/scalable/apps',
    'org.gajim.Gajim.svg': 'share/icons/hicolor/scalable/apps',
    'org.gajim.Gajim.appdata.xml': 'share/metainfo',
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Install metadata files')
    parser.add_argument('input',
                        type=Path,
                        default=DEFAULT_METADATA_PATH,
                        help='Path to the metadata folder, '
                             'default: dist/metadata')
    parser.add_argument('--prefix',
                        type=Path,
                        required=True,
                        help='The path prefix, for example "/usr"')

    args = parser.parse_args()

    for file, path in FILES.items():
        src = args.input / file
        dest_dir = args.prefix / path
        logging.info('Copy %s to %s', src, dest_dir)
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True)
        shutil.copy(src, dest_dir / file)
