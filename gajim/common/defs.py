# -*- coding:utf-8 -*-
## src/common/defs.py
##
## Copyright (C) 2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
##                    Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import subprocess
import sys
import os.path

docdir = '../'
basedir = './'
localedir = '../po'
version = '0.16.11'

try:
    node = subprocess.Popen('git rev-parse --short=12 HEAD', shell=True,
        stdout=subprocess.PIPE).communicate()[0]
    if node:
        version += '-' + node.decode('utf-8').strip()
except Exception:
    pass

for base in ('.', 'common'):
    sys.path.append(os.path.join(base, '.libs'))
