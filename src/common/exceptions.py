## exceptions.py
##
## Copyright (C) 2005-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
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

class PysqliteNotAvailable(Exception):
	'''sqlite2 is not installed or python bindings are missing'''
	def __init__(self):
		Exception.__init__(self)

	def __str__(self):
		return _('pysqlite2 (aka python-pysqlite2) dependency is missing. Exiting...')

class PysqliteOperationalError(Exception):
	'''sqlite2 raised pysqlite2.dbapi2.OperationalError'''
	def __init__(self, text=''):
		Exception.__init__(self)
		self.text = text

	def __str__(self):
		return self.text

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
		return _('Session bus is not available.\nTry reading http://trac.gajim.org/wiki/GajimDBus')

class NegotiationError(Exception):
	'''A session negotiation failed'''
	pass

class DecryptionError(Exception):
	'''A message couldn't be decrypted into usable XML'''
	pass

class GajimGeneralException(Exception):
	'''This exception is our general exception'''
	def __init__(self, text=''):
		Exception.__init__(self)
		self.text = text

	def __str__(self):
		return self.text
