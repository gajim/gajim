#!/usr/bin/env python3

# Reads all .ui files and creates builder.pyi
# Execute this script from the repo root dir

import logging
import sys
from io import TextIOWrapper
from pathlib import Path
from xml.etree import ElementTree

logging.basicConfig(level='INFO', format='%(levelname)s: %(message)s')
log = logging.getLogger()

cwd = Path.cwd()

if cwd.name != 'gajim':
    sys.exit('Script needs to be executed from gajim repository '
             'root directory')

in_path = cwd / 'gajim' / 'data' / 'gui'
out_path = cwd / 'gajim' / 'gtk' / 'builder.pyi'

paths = list(in_path.iterdir())
paths.sort()

IMPORTS = '''
from typing import Literal
from typing import overload

from gi.repository import Atk
from gi.repository import Gtk
from gi.repository import GtkSource

class Builder(Gtk.Builder):
    ...

'''

CLASS_DEF = '\nclass %s(Builder):'
ATTR = '\n    %s: %s'

GET_BUILDER_OVERLOAD = '''
@overload
def get_builder(file_name: Literal['%s'], widgets: list[str] = ...) -> %s: ...  # noqa'''  # noqa: E501

GET_BUILDER = '''\n\n
def get_builder(file_name: str, widgets: list[str] = ...) -> Builder: ...'''


def make_class_name(path: Path) -> str:
    name = path.name.removesuffix('.ui')
    names = name.split('_')
    names = [name.capitalize() for name in names]
    return ''.join(names) + 'Builder'


def parse(path: Path, file: TextIOWrapper) -> str:
    log.info('Read %s', path)
    lines: list[str] = []
    tree = ElementTree.parse(path)
    for node in tree.iter(tag='object'):
        id_ = node.attrib.get('id')
        if id_ is None:
            continue
        klass = node.attrib['class']
        if klass.startswith('GtkSource'):
            klass = f'GtkSource.{klass.removeprefix("GtkSource")}'
        elif klass.startswith('Atk'):
            klass = f'Atk.{klass.removeprefix("Atk")}'
        else:
            klass = f'Gtk.{klass.removeprefix("Gtk")}'

        lines.append(ATTR % (id_.replace('-', '_'), klass))

    klass_name = make_class_name(path)
    file.write(CLASS_DEF % klass_name)

    if not lines:
        file.write('\n    pass')
    else:
        for line in lines:
            file.write(line)
    file.write('\n\n')
    return klass_name


builder_names: list[tuple[str, str]] = []

with out_path.open(mode='w', encoding='utf8') as file:
    file.write(IMPORTS)
    for path in paths:
        if path.name.endswith('~'):
            continue

        if path.name.startswith('#'):
            continue
        name = parse(path, file)
        builder_names.append((name, path.name))

    for name, file_name in builder_names:
        file.write(GET_BUILDER_OVERLOAD % (file_name, name))
    file.write(GET_BUILDER)
    file.write('\n')
