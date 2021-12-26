#!/usr/bin/env python

# Creates links from gui folder to all files in the gtk folder
# This is needed for pyright to work correctly with the dynamic gui imports

from pathlib import Path

IGNORED_FILES = ['__init__.py']
IGNORED_DIRS = ['__pycache__']

cwd = Path.cwd()

if cwd.name != 'gajim':
    exit('Script needs to be excecuted from gajim repository root directory')

gui_path = cwd / 'gajim' / 'gui'
gtk_path = cwd / 'gajim' / 'gtk'


def link(target):
    source = str(target)
    source = source.replace('gajim/gtk', 'gajim/gui')
    source = Path(source)
    source.symlink_to(target)
    print('create symlink from', source, 'to', target)

for path in gtk_path.iterdir():
    if path.is_dir():
        if path.name not in IGNORED_DIRS:
            link(path)

    elif path.name not in IGNORED_FILES:
        link(path)
