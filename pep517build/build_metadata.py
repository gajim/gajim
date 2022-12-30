#!/usr/bin/env python3

from __future__ import annotations

import argparse
import gzip
import logging
import shutil
import subprocess
from pathlib import Path

logging.basicConfig(level='INFO', format='%(message)s')

DEFAULT_METADATA_PATH = Path('dist/metadata')

MAN_FILES = [
    Path('data/gajim.1'),
    Path('data/gajim-remote.1')
]
META_FILES = [
    (Path('data/org.gajim.Gajim.desktop.in'), '--desktop'),
    (Path('data/org.gajim.Gajim.appdata.xml.in'), '--xml')
]
ICONS = [
    Path('gajim/data/icons/hicolor/scalable/apps/org.gajim.Gajim.svg'),
    Path('gajim/data/icons/hicolor/scalable/apps/org.gajim.Gajim-symbolic.svg'),
]


def build_man(target_path: Path) -> None:
    # Build man files in target path

    for man_path in MAN_FILES:
        data = man_path.read_bytes()
        man_file_name = man_path.name

        man_out_path = target_path / f'{man_file_name}.gz'
        logging.info('Compress %s >> %s', man_file_name, man_out_path)

        with gzip.open(man_out_path, 'wb') as f_out:
            f_out.write(data)



def build_intl(target_path: Path) -> None:
    # Merge translation files into desktop and metadata files

    for file_path, option in META_FILES:
        out_path = target_path / file_path.name
        out_path = out_path.with_suffix('')

        logging.info('Compile %s >> %s', file_path, out_path)

        subprocess.run(['msgfmt',
                        option,
                        '-d',
                        'po',
                        '--template',
                        str(file_path),
                        '-o',
                        str(out_path)],
                        check=True)


def build_app_icons(target_path: Path) -> None:
    for file_path in ICONS:
        out_path = target_path / file_path.name

        logging.info('Copy %s >> %s', file_path, out_path)
        shutil.copy2(file_path, out_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build metadata files')
    parser.add_argument('-o',
                        '--output-dir',
                        type=Path,
                        default=DEFAULT_METADATA_PATH)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    build_man(args.output_dir)
    build_intl(args.output_dir)
    build_app_icons(args.output_dir)
