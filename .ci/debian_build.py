#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import logging
import shutil
import subprocess
from datetime import datetime
from datetime import timezone
from pathlib import Path

LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'
logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
log = logging.getLogger()

ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT_DIR / 'debian_build'

DATE = datetime.now().strftime('%Y%m%d')
DATE_TIME = datetime.now(tz=timezone.utc).strftime('%a, %d %b %Y %T %z')


@dataclasses.dataclass
class ReleaseContext:
    app: str
    pkg_name: str
    rev: str
    release_name: str
    release_dir: Path
    tarball: Path

    @classmethod
    def from_tarball(cls, path: str, prefix: str, rev: str) -> ReleaseContext:
        tarball = Path(path)
        app = tarball.name.split('-', maxsplit=1)[0]
        pkg_name = f'{prefix}{app}-nightly'
        release_name = f'{pkg_name}_{DATE}'
        release_dir = BUILD_DIR / release_name
        return cls(app=app,
                   pkg_name=pkg_name,
                   rev=rev,
                   release_name=release_name,
                   release_dir=release_dir,
                   tarball=tarball)


def clean_build_dir() -> None:
    log.info('Cleanup build directory')
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()


def prepare_package_dir(context: ReleaseContext) -> None:
    log.info('Extract tarball')
    tarball = Path(shutil.copy(context.tarball, BUILD_DIR))
    tarball = tarball.rename(BUILD_DIR / f'{context.release_name}.orig.tar.gz')
    shutil.unpack_archive(tarball, BUILD_DIR)

    log.info('Rename dir to: %s', context.release_name)
    folder = list(BUILD_DIR.glob(f'{context.app}-?.?.?'))[0]
    folder.rename(context.release_dir)

    log.info('Copy debian folder into release directory')
    shutil.copytree(ROOT_DIR / 'debian', context.release_dir / 'debian')


def prepare_changelog(context: ReleaseContext) -> None:
    log.info('Prepare Changelog')
    changelog = context.release_dir / 'debian' / 'changelog'
    content = changelog.read_text()
    content = content.replace('{DATE}', f'{DATE}-{context.rev}')
    content = content.replace('{DATE_TIME}', DATE_TIME)
    changelog.write_text(content)


def build(context: ReleaseContext) -> None:
    log.info('Start package build')
    subprocess.run(
        [
            'dpkg-buildpackage',
            '--no-sign'
        ],
        cwd=context.release_dir,
        check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build debian package')
    parser.add_argument('tarball', help='Path to tarball e.g. app.tar.gz')
    parser.add_argument('rev', help='The package revision e.g. 1')
    parser.add_argument('--pkgprefix', default='', required=False,
                        help='Prefix for the package name e.g. python3-')
    args = parser.parse_args()

    context = ReleaseContext.from_tarball(args.tarball,
                                          args.pkgprefix,
                                          args.rev)

    clean_build_dir()
    prepare_package_dir(context)
    prepare_changelog(context)
    build(context)
