#!/usr/bin/env python3

import os
import sys
from argparse import ArgumentParser
from subprocess import run, check_output, CalledProcessError

if __name__ == '__main__':
    if not os.path.isdir('mac'):
        sys.exit("can't find the 'mac' directory. make sure you run "
                 "this script from the project root")

    parser = ArgumentParser(description='Create a macOS .app bundle. '
                            'Requires PyInstaller and hdiutil (macOS).')
    parser.add_argument('--version', help='version number of the .app bundle')
    args = parser.parse_args()

    if args.version:
        version = args.version
    else:
        try:
            version = check_output(['git', 'describe', '--tags'])
            version = version.decode().strip()
        except CalledProcessError:
            version = 'unknown'
    dmg_name = 'gajim-{}.dmg'.format(version)

    # the .spec has to be in the project root
    run(['cp', 'mac/gajim.spec', 'gajim.spec'], check=True)
    run(['pyinstaller', 'gajim.spec'], check=True)
    # we only want Gajim.app in the dmg
    run(['rm', '-rf', 'dist/launch'])
    run(['hdiutil',
         'create',
         '-volname',
         'Gajim',
         '-srcfolder',
         'dist',
         '-ov',
         '-format',
         'UDZO',
         dmg_name],
        check=True)
