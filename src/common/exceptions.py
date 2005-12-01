## exceptions.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
##      Copyright (C) 2003-2005 Gajim Team
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

from common import i18n
_ = i18n._

class PysqliteNotAvailable(Exception):
	'''sqlite2 is not installed or python bindings are missing'''
	def __init__(self):
		Exception.__init__(self)

	def __str__(self):
		return _('pysqlite2 (aka python-pysqlite2) dependency is missing. '\
		'After you install pysqlite3, if you want to migrate your logs '\
		'to the new database, please read: http://trac.gajim.org/wiki/MigrateLogToDot9DB '\
		'Exiting...')

class ServiceNotAvailable(Exception):
	'''This exception is raised when we cannot use Gajim remotely'''
	def __init__(self):
		Exception.__init__(self)

	def __str__(self):
		return _('Service not available: Gajim is not running, or remote_control is False')

class DbusNotSupported(Exception):
	'''D-Bus is not installed or python bindings are missing'''
	def __init__(self):
		Exception.__init__(self)

	def __str__(self):
		return _('D-Bus is not present on this machine or python module is missing')

class SessionBusNotPresent(Exception):
	'''This exception indicates that there is no session daemon'''
	def __init__(self):
		Exception.__init__(self)

	def __str__(self):
		return _('Session bus is not available')
