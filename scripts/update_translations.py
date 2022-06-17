#!/usr/bin/env python3

# File needs to stay compatible to Python 3.7
# because its run on the Gajim webserver

import argparse
import re
import subprocess
from pathlib import Path


TRANS_DIR = Path('po')
TRANS_TEMPLATE = TRANS_DIR / 'gajim.pot'
REPO_DIR = Path(__file__).resolve().parent.parent


TRANSLATABLE_FILES = [
    'gajim/**/*.py',
    'gajim/**/*.ui',
    'data/org.gajim.Gajim.desktop.in',
    'data/org.gajim.Gajim.appdata.xml.in',
]


def template_is_equal(old_template_path: Path, new_template: str) -> bool:
    with open(old_template_path, 'r', encoding='utf8') as f:
        old_template = f.read()

    pattern = r'"POT-Creation-Date: .*\n"'

    old_template = re.sub(pattern, '', old_template, count=1)
    new_template = re.sub(pattern, '', new_template, count=1)

    return old_template == new_template


def update_translation_template() -> bool:
    paths: list[Path] = []
    for file_path in TRANSLATABLE_FILES:
        paths += list(REPO_DIR.rglob(file_path))

    cmd = [
        'xgettext',
        '-o', '-',
        '-c#',
        '--from-code=utf-8',
        '--keyword=Q_',
        '--keyword=P_:1c,2',
        '--no-location',
        '--sort-output',
        '--package-name=Gajim'
    ]

    for path in paths:
        cmd.append(str(path))

    result = subprocess.run(cmd,
                            cwd=REPO_DIR,
                            text=True,
                            check=True,
                            capture_output=True)

    template = result.stdout

    if (TRANS_TEMPLATE.exists() and
            template_is_equal(TRANS_TEMPLATE, template)):
        # No new strings were discovered
        return False

    with open(TRANS_TEMPLATE, 'w', encoding='utf8') as f:
        f.write(template)
    return True


def update_translation_files() -> None:
    for file in TRANS_DIR.glob('*.po'):
        subprocess.run(['msgmerge',
                        '-U',
                        '--sort-output',
                        str(file),
                        TRANS_TEMPLATE],
                       cwd=REPO_DIR,
                       check=True)


def cleanup_translations() -> None:
    for po_file in TRANS_DIR.glob('*.po'):
        subprocess.run(['msgattrib',
                        '--output-file',
                        str(po_file),
                        '--no-obsolete',
                        str(po_file)],
                       cwd=REPO_DIR,
                       check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update Translations')
    parser.add_argument('command', choices=['update', 'build', 'cleanup'])
    args = parser.parse_args()

    if args.command == 'cleanup':
        cleanup_translations()

    elif args.command == 'update':
        update_translation_template()
        update_translation_files()
