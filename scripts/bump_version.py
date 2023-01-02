#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent


INIT = REPO_DIR / 'gajim' / '__init__.py'
FLATPAK = REPO_DIR / 'flatpak' / 'org.gajim.Gajim.yaml'
APPDATA = REPO_DIR / 'data' / 'org.gajim.Gajim.appdata.xml.in'
CHANGELOG = REPO_DIR / 'ChangeLog'

VERSION_RX = r'\d+\.\d+\.\d+'


def get_current_version() -> str:
    with INIT.open('r') as f:
        content = f.read()

    match = re.search(VERSION_RX, content)
    if match is None:
        sys.exit('Unable to find current version')
    return match[0]


def bump_init(current_version: str, new_version: str) -> None:
    with INIT.open('r', encoding='utf8') as f:
        content = f.read()

    content = content.replace(current_version, new_version, 1)

    with INIT.open('w', encoding='utf8') as f:
        f.write(content)


def bump_flatpak(current_version: str, new_version: str) -> None:
    with FLATPAK.open('r', encoding='utf8') as f:
        content = f.read()

    content = content.replace(f'tag: {current_version}',
                              f'tag: {new_version}', 1)

    with FLATPAK.open('w', encoding='utf8') as f:
        f.write(content)


def bump_appdata(new_version: str) -> None:
    with APPDATA.open('r', encoding='utf8') as f:
        lines = f.readlines()

    date = datetime.today().strftime('%Y-%m-%d')
    release_string = f'    <release version="{new_version}" date="{date}" />'

    with APPDATA.open('w', encoding='utf8') as f:
        for line in lines:
            f.write(line)
            if '<releases>' in line:
                f.write(release_string)
                f.write('\n')


def make_changelog(new_version: str) -> None:

    cmd = [
        'git-chglog',
        '--next-tag',
        new_version
    ]

    result = subprocess.run(cmd,
                            cwd=REPO_DIR,
                            text=True,
                            check=True,
                            capture_output=True)

    changes = result.stdout
    changes = changes.removeprefix('\n')

    current_changelog = CHANGELOG.read_text()

    with CHANGELOG.open('w') as f:
        f.write(changes + current_changelog)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bump Version')
    parser.add_argument('version', help='The new version, e.g. 1.5.0')
    args = parser.parse_args()

    current_version = get_current_version()
    bump_init(current_version, args.version)
    bump_flatpak(current_version, args.version)
    bump_appdata(args.version)
    make_changelog(args.version)
