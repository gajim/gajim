#!/usr/bin/env python3

from __future__ import annotations

import argparse
import gzip
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level='INFO', format='%(message)s')

CONFIG_VALUES = {
    'APP_ID': 'org.gajim.Gajim',
    'APP_NAME': 'Gajim',
    'APP_ICON_NAME': 'org.gajim.Gajim',
    'FLATPAK': 'False',
    'FLATPAK_NIGHTLY': 'False',
}

CONFIG = Path('gajim/config.py.in')
METAINFO = Path('data/org.gajim.Gajim.metainfo.xml.in')
DESKTOP = Path('data/org.gajim.Gajim.desktop.in')
METADATA = Path('dist/metadata')

MAN_FILES = [Path('data/gajim.1'), Path('data/gajim-remote.1')]

META_FILES = [
    (Path('data/org.gajim.Gajim.desktop'), '--desktop'),
    (Path('data/org.gajim.Gajim.metainfo.xml'), '--xml'),
]

ICONS = [
    Path('gajim/data/icons/hicolor/scalable/apps/gajim.svg'),
    Path('gajim/data/icons/hicolor/scalable/apps/gajim-symbolic.svg'),
]

INSTALL_FILES = {
    'gajim-remote.1.gz': 'share/man/man1',
    'gajim.1.gz': 'share/man/man1',
    'org.gajim.Gajim.desktop': 'share/applications',
    'org.gajim.Gajim.metainfo.xml': 'share/metainfo',
    'org.gajim.Gajim-symbolic.svg': 'share/icons/hicolor/scalable/apps',
    'org.gajim.Gajim.svg': 'share/icons/hicolor/scalable/apps',
}


def configure_file(path: Path, values: dict[str, str]) -> None:
    logging.info('Configure %s', path)
    content = path.read_text()
    for old, new in values.items():
        content = content.replace(f'@{old}@', new)
    path = path.with_suffix('')
    path.write_text(content)


def configure_flatpak() -> None:
    CONFIG_VALUES['FLATPAK'] = 'True'


def configure_flatpak_nightly() -> None:
    CONFIG_VALUES['APP_ID'] = 'org.gajim.Gajim.Devel'
    CONFIG_VALUES['APP_NAME'] = 'Gajim (Nightly)'
    CONFIG_VALUES['APP_ICON_NAME'] = 'org.gajim.Gajim.Devel'
    CONFIG_VALUES['FLATPAK'] = 'True'
    CONFIG_VALUES['FLATPAK_NIGHTLY'] = 'True'


def build_man() -> None:
    # Build man files in target path

    for man_path in MAN_FILES:
        data = man_path.read_bytes()
        man_file_name = man_path.name

        man_out_path = METADATA / f'{man_file_name}.gz'
        logging.info('Compress %s >> %s', man_file_name, man_out_path)

        with gzip.open(man_out_path, 'wb') as f_out:
            f_out.write(data)


def build_meta() -> None:
    for file_path, option in META_FILES:
        out_path = METADATA / file_path.name

        logging.info('Compile %s >> %s', file_path, out_path)

        subprocess.run(
            [
                'msgfmt',
                option,
                '-d',
                'po',
                '--template',
                str(file_path),
                '-o',
                str(out_path),
            ],
            check=True,
        )


def build_app_icons() -> None:
    for file_path in ICONS:
        icon_name = file_path.name.replace('gajim', 'org.gajim.Gajim')
        out_path = METADATA / icon_name

        logging.info('Copy %s >> %s', file_path, out_path)
        shutil.copy2(file_path, out_path)


def build_translations() -> None:
    # Compile translation files and place them into "gajim/data/locale"

    source_dir = Path.cwd()
    translation_dir = source_dir / 'po'
    locale_dir = source_dir / 'gajim' / 'data' / 'locale'

    langs = sorted([lang.stem for lang in translation_dir.glob('*.po')])

    for lang in langs:
        po_file = source_dir / 'po' / f'{lang}.po'
        mo_file = locale_dir / lang / 'LC_MESSAGES' / 'gajim.mo'
        mo_file.parent.mkdir(parents=True, exist_ok=True)

        logging.info('Compile %s >> %s', po_file, mo_file)

        subprocess.run(['msgfmt', str(po_file), '-o', str(mo_file)], check=True)


def install(*, prefix: Path) -> None:
    for file, path in INSTALL_FILES.items():
        src = METADATA / file
        dest_dir = prefix / path
        logging.info('Copy %s to %s', src, dest_dir)
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True)
        shutil.copy(src, dest_dir / file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dist', choices=['flatpak', 'flatpak-nightly'], help='Distribution'
    )

    parser.add_argument(
        '--install', action='store_true', help='Install metadata files'
    )

    parser.add_argument(
        '--prefix',
        type=Path,
        default='/usr',
        help='The path prefix for installation (e.g. "/usr")',
    )

    args = parser.parse_args()
    METADATA.mkdir(parents=True, exist_ok=True)

    if args.install:
        install(prefix=args.prefix)
        sys.exit()

    if args.dist == 'flatpak':
        configure_flatpak()
    elif args.dist == 'flatpak-nightly':
        configure_flatpak_nightly()

    configure_file(CONFIG, CONFIG_VALUES)
    configure_file(METAINFO, CONFIG_VALUES)
    configure_file(DESKTOP, CONFIG_VALUES)

    build_man()
    build_meta()
    build_app_icons()
    build_translations()
