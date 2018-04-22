# -*- coding:utf-8 -*-
## src/common/check_paths.py
##
## Copyright (C) 2005-2006 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2008 Jean-Marie Traissard <jim AT lapin.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import sys

from gajim.common import configpaths
from gajim.common.const import PathType


def check_and_possibly_create_paths():
    for path in configpaths.get_paths(PathType.FOLDER):
        if not os.path.exists(path):
            create_path(path)
        elif os.path.isfile(path):
            print(_('%s is a file but it should be a directory') % path)
            print(_('Gajim will now exit'))
            sys.exit()


def create_path(directory):
    head, tail = os.path.split(directory)
    if not os.path.exists(head):
        create_path(head)
    if os.path.exists(directory):
        return
    print(('creating %s directory') % directory)
    os.mkdir(directory, 0o700)
