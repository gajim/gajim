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

from plugins.helpers import log_calls

class GajimPlugin(object):
	'''
	Base class for implementing Gajim plugins.
	'''
	name = ''
	'''
	Name of plugin.
	
	Will be shown in plugins management GUI.
	
	:type: unicode
	'''
	short_name = ''
	'''
	Short name of plugin.
	
	Used for quick indentification of plugin.

	:type: unicode
	
	:todo: decide whether we really need this one, because class name (with
		module name) can act as such short name		
	'''
	version = ''
	'''
	Version of plugin.
	
	:type: unicode
	
	:todo: decide how to compare version between each other (which one
		is higher). Also rethink: do we really need to compare versions
		of plugins between each other? This would be only useful if we detect
		same plugin class but with different version and we want only the newest
		one to be active - is such policy good?
	'''
	description = ''
	'''
	Plugin description.
	
	:type: unicode
	
	:todo: should be allow rich text here (like HTML or reStructuredText)?
	'''
	authors = []
	'''
	Plugin authors.
	
	:type: [] of unicode
	
	:todo: should we decide on any particular format of author strings?
		Especially: should we force format of giving author's e-mail?
	'''
	gui_extension_points = {}
	'''
	Extension points that plugin wants to connect with.
	'''
	
	@log_calls('GajimPlugin')
	def __init__(self):
		pass