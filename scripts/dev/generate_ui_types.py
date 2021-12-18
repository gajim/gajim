#!/usr/bin/env python3

import sys
from pathlib import Path

from xml.etree import ElementTree as ET

try:
    path = sys.argv[1]
except Exception:
    print('path to file/folder missing')
    exit()

path = Path(path)

if path.is_dir():
    paths = list(path.iterdir())

elif path.is_file():
    paths = [path]

else:
    print('Path must be folder or file:', path)
    exit()


IMPORTS = '''
from typing import Literal
from typing import overload

from gi.repository import Atk
from gi.repository import Gtk
from gi.repository import GtkSource
from gi.repository import GObject


class Builder: ...
'''

CLASS_DEF = '''
class %s(Builder):
'''

OVERLOAD = '''
    @overload
    def get(self, name: Literal['%s']) -> %s: ...'''

METHOD = '''
    def get(self, name: str) -> GObject.Object: ...'''


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
    klass_name = make_class_name(path)
    file.write(CLASS_DEF % klass_name)
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
        file.write(OVERLOAD % (id_, klass))
    file.write(METHOD)
    file.write('\n\n')
    return klass_name


builder_names = []

current_dir = Path('./builder.pyi')
with current_dir.open(mode='w') as file:
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
