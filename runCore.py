#!/usr/bin/env python
##	runCore.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@@crans.org>
## 	- Vincent Hanquez <tab@@tuxfamily.org>
## 	- David Ferlier <david@@yazzy.org>
##
##	Copyright (C) 2003 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import logging
logging.basicConfig()
import sys

sys.path.append("..")

import common
import core

core.core.start()
