#!/usr/bin/env python3

from __future__ import annotations

from typing import cast

import os
import sys

if sys.version_info < (3, 9):
    sys.exit('Gajim needs Python 3.9+')

import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build
from setuptools.command.install import install as _install


DataFilesT = list[tuple[str, list[str]]]


MAN_FILES = [
    'gajim.1',
    'gajim-remote.1'
]
META_FILES = [
    ('data/org.gajim.Gajim.desktop', 'share/applications', '--desktop'),
    ('data/org.gajim.Gajim.appdata.xml', 'share/metainfo', '--xml')]


TRANS_DIR = Path('po')
TRANS_TEMPLATE = TRANS_DIR / 'gajim.pot'
REPO_DIR = Path(__file__).resolve().parent
BUILD_DIR = REPO_DIR / 'build'

ALL_LINGUAS = sorted([lang.stem for lang in TRANS_DIR.glob('*.po')])


def newer(source: Path, target: Path) -> bool:
    if not source.exists():
        raise ValueError('file "%s" does not exist' % source.resolve())
    if not target.exists():
        return True

    from stat import ST_MTIME
    mtime1 = source.stat()[ST_MTIME]
    mtime2 = target.stat()[ST_MTIME]

    return mtime1 > mtime2


def build_translation() -> None:
    for lang in ALL_LINGUAS:
        po_file = TRANS_DIR / f'{lang}.po'
        mo_file = BUILD_DIR / 'mo' / lang / 'LC_MESSAGES' / 'gajim.mo'
        mo_dir = mo_file.parent
        if not (mo_dir.is_dir() or mo_dir.is_symlink()):
            mo_dir.mkdir(parents=True)

        if newer(po_file, mo_file):
            subprocess.run(['msgfmt',
                            str(po_file),
                            '-o',
                            str(mo_file)],
                           cwd=REPO_DIR,
                           check=True)

            print('Compiling %s >> %s' % (po_file, mo_file))


def install_trans(data_files: DataFilesT) -> None:
    for lang in ALL_LINGUAS:
        mo_file = str(BUILD_DIR / 'mo' / lang / 'LC_MESSAGES' / 'gajim.mo')
        target = f'share/locale/{lang}/LC_MESSAGES'
        data_files.append((target, [mo_file]))


def build_man() -> None:
    '''
    Compress Gajim manual files
    '''
    newdir = BUILD_DIR / 'man'
    if not (newdir.is_dir() or newdir.is_symlink()):
        newdir.mkdir()

    for man in MAN_FILES:
        filename = Path('data') / man
        man_file_gz = newdir / (man + '.gz')
        if man_file_gz.exists():
            if newer(filename, man_file_gz):
                man_file_gz.unlink()
            else:
                continue

        import gzip
        # Binary io, so open is OK
        with open(filename, 'rb') as f_in,\
                gzip.open(man_file_gz, 'wb') as f_out:
            f_out.writelines(f_in)
            print('Compiling %s >> %s' % (filename, man_file_gz))


def install_man(data_files: DataFilesT) -> None:
    man_dir = BUILD_DIR / 'man'
    target = 'share/man/man1'

    for man in MAN_FILES:
        man_file_gz = str(man_dir / (man + '.gz'))
        data_files.append((target, [man_file_gz]))


def build_intl() -> None:
    '''
    Merge translation files into desktop and mime files
    '''
    base = BUILD_DIR

    for filename, _, option in META_FILES:
        newfile = base / filename
        newdir = newfile.parent
        if not(newdir.is_dir() or newdir.is_symlink()):
            newdir.mkdir()
        merge(Path(filename + '.in'), newfile, option)


def install_intl(data_files: DataFilesT) -> None:
    for filename, target, _ in META_FILES:
        data_files.append((target, [str(BUILD_DIR / filename)]))


def merge(in_file: Path,
          out_file: Path,
          option: str,
          po_dir: str = 'po') -> None:
    '''
    Run the msgfmt command.
    '''
    if in_file.exists():
        cmd = (('msgfmt %(opt)s -d %(po_dir)s --template %(in_file)s '
                '-o %(out_file)s') %
               {'opt': option,
                'po_dir': po_dir,
                'in_file': in_file,
                'out_file': out_file})
        if os.system(cmd) != 0:
            msg = ('ERROR: %s was not merged into the translation files!\n' %
                   out_file)
            raise SystemExit(msg)
        print('Compiling %s >> %s' % (in_file, out_file))


class build(_build):
    def run(self):
        build_translation()
        if sys.platform != 'win32':
            build_man()
            build_intl()
        _build.run(self)


class install(_install):
    def run(self):
        data_files = cast(DataFilesT, self.distribution.data_files)  # pyright: ignore  # noqa: E501
        install_trans(data_files)
        if sys.platform != 'win32':
            install_man(data_files)
            install_intl(data_files)
        _install.run(self)  # pyright: ignore


# only install subdirectories of data
data_files_app_icon = [
    ('share/icons/hicolor/scalable/apps',
     ['gajim/data/icons/hicolor/scalable/apps/org.gajim.Gajim.svg']),
    ('share/icons/hicolor/scalable/apps',
     ['gajim/data/icons/hicolor/scalable/apps/org.gajim.Gajim-symbolic.svg'])
]

data_files: DataFilesT = data_files_app_icon

setup(
    cmdclass={
        'build_py': build,
        'install': install,
    },
    entry_points={
        'console_scripts': [
            'gajim-remote = gajim.gajim_remote:main',
        ],
        'gui_scripts': [
            'gajim = gajim.gajim:main',
        ]
    },
    data_files=data_files
)
