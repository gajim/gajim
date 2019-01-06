#!/usr/bin/env python3
import os
import shutil
import sys
from string import Template
from os.path import join
import argparse

EXEC_TEMPLATE = 'mac/launch.sh.template'
PLIST_TEMPLATE = 'mac/Info.plist.template'
ICNS_FILE = 'mac/Gajim.icns'


def fill_template(in_path, out_path, vars):
    with open(in_path, 'r') as f:
        templ = Template(f.read())
    filled_templ = templ.substitute(vars)
    with open(out_path, 'w') as f:
        f.write(filled_templ)


def create_executable(exec_path, bin_path):
    fill_template(EXEC_TEMPLATE, exec_path, {
        'bin_path': bin_path
    })
    os.chmod(exec_path, 0o755)


def create_plist(plist_path, version):
    fill_template(PLIST_TEMPLATE, plist_path, {
        'version': version,
        'short_version_string': version
    })


if __name__ == '__main__':
    if not os.path.isdir('mac'):
        sys.exit("can't find the 'mac' directory. make sure you run "
                 "this script from the project root")

    parser = argparse.ArgumentParser(description='Create a macOS .app bundle.')
    parser.add_argument('bundle', help='bundle output location')
    parser.add_argument('--version', default='0.0.1',
                        help='version number of the .app bundle')
    parser.add_argument('--bin-path', default='/usr/local/bin/gajim',
                        help='location of the actual executable')
    args = parser.parse_args()

    bundle = args.bundle

    os.mkdir(bundle)
    os.mkdir(join(bundle, 'Contents'))
    os.mkdir(join(bundle, 'Contents/MacOS'))
    os.mkdir(join(bundle, 'Contents/Resources'))

    create_executable(join(bundle, 'Contents/MacOS/launch.sh'), bin_path=args.bin_path)
    create_plist(join(bundle, 'Contents/Info.plist'), version=args.version)
    shutil.copy(ICNS_FILE, join(bundle, 'Contents/Resources/Gajim.icns'))
