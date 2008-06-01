# -*- coding: utf-8 -*-

## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

'''
Base class for implementing plugin.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 06/01/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys
from plugins.helpers import log, log_calls

class GajimPlugin(object):
	name = ''
	short_name = ''
	version = ''
	description = ''
	authors = []
	gui_extension_points = {}
	
	@log_calls('GajimPlugin')
	def __init__(self):
		pass