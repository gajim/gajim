#!/usr/bin/env python3

# Reads all .ui files and creates builder.pyi
# Excecute this script from the repo root dir

from pathlib import Path
from xml.etree import ElementTree as ET


cwd = Path.cwd()

if cwd.name != 'gajim':
    exit('Script needs to be excecuted from gajim repository root directory')

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


class Builder(Gtk.Builder): ...
'''

CLASS_DEF = '\nclass %s(Builder):'
ATTR = '\n    %s: %s'

GET_BUILDER_OVERLOAD = '''
@overload
def get_builder(file_name: Literal['%s'], widgets: list[str] = ...) -> %s: ...'''

GET_BUILDER = '''
def get_builder(file_name: str, widgets: list[str] = ...) -> Builder: ...'''


def make_class_name(path):
    name = path.name.removesuffix('.ui')
    names = name.split('_')
    names = map(lambda x: x.capitalize(), names)
    return ''.join(names) + 'Builder'


def parse(path, file):
    print('read', path)
    lines = []
    tree = ET.parse(path)
    for node in tree.iter(tag='object'):
        id_ = node.attrib.get('id')
        if id_ is None:
            continue
        klass = node.attrib.get('class')
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


builder_names = []

with out_path.open(mode='w') as file:
    file.write(IMPORTS)
    for path in paths:
        if path.name.endswith('~'):
            continue
        name = parse(path, file)
        builder_names.append((name, path.name))

    for name, file_name in builder_names:
        file.write(GET_BUILDER_OVERLOAD % (file_name, name))
    file.write(GET_BUILDER)
    file.write('\n')
