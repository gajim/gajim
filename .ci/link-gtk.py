#!/usr/bin/env python

# Creates links from gui folder to all files in the gtk folder
# This is needed for pyright to work correctly with the dynamic gui imports

import logging
from pathlib import Path
import sys

IGNORED_FILES = ['__init__.py']
IGNORED_DIRS = ['__pycache__']

cwd = Path.cwd()

if cwd.name != 'gajim':
    sys.exit('Script needs to be executed from gajim repository '
             'root directory')

gui_path = cwd / 'gajim' / 'gui'
gtk_path = cwd / 'gajim' / 'gtk'


logging.basicConfig(level='INFO', format='%(levelname)s: %(message)s')
log = logging.getLogger()


def cleanup_dir(target_dir: Path) -> None:
    for path in target_dir.iterdir():
        if path.name in IGNORED_FILES:
            continue
        if path.name in IGNORED_DIRS:
            continue
        path.unlink()


def link(target: Path) -> None:
    source = str(target)
    source = source.replace('gajim/gtk', 'gajim/gui')
    source = Path(source)
    source.symlink_to(target)
    log.info('create symlink from %s -> %s', source, target)


def link_files(source_dir: Path) -> None:
    for path in source_dir.iterdir():
        if path.is_dir():
            if path.name not in IGNORED_DIRS:
                link(path)

        elif path.name not in IGNORED_FILES:
            link(path)


cleanup_dir(gui_path)
link_files(gtk_path)
