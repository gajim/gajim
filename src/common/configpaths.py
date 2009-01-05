# -*- coding:utf-8 -*-
## src/common/configpaths.py
##
## Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
##                    Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
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

import os
import sys
import tempfile

# Note on path and filename encodings:
#
# In general it is very difficult to do this correctly.
# We may pull information from environment variables, and what encoding that is
# in is anyone's guess. Any information we request directly from the file
# system will be in filesystemencoding, and (parts of) paths that we write in
# this source code will be in whatever encoding the source is in. (I hereby
# declare this file to be UTF-8 encoded.)
#
# To make things more complicated, modern Windows filesystems use UTF-16, but
# the API tends to hide this from us.
#
# I tried to minimize problems by passing Unicode strings to OS functions as
# much as possible. Hopefully this makes the function return an Unicode string
# as well. If not, we get an 8-bit string in filesystemencoding, which we can
# happily pass to functions that operate on files and directories, so we can
# just leave it as is. Since these paths are meant to be internal to Gajim and
# not displayed to the user, Unicode is not really necessary here.

def fse(s):
	'''Convert from filesystem encoding if not already Unicode'''
	return unicode(s, sys.getfilesystemencoding())

def windowsify(s):
	if os.name == 'nt':
		return s.capitalize()
	return s

class ConfigPaths:
	def __init__(self, root=None):
		self.root = root
		self.paths = {}

		if self.root is None:
			if os.name == 'nt':
				try:
					# Documents and Settings\[User Name]\Application Data\Gajim

					# How are we supposed to know what encoding the environment
					# variable 'appdata' is in? Assuming it to be in filesystem
					# encoding.
					self.root = os.path.join(fse(os.environ[u'appdata']), u'Gajim')
				except KeyError:
					# win9x, in cwd
					self.root = u'.'
			else: # Unices
				# Pass in an Unicode string, and hopefully get one back.
				self.root = os.path.expanduser(u'~/.gajim')

	def add_from_root(self, name, path):
		self.paths[name] = (True, path)

	def add(self, name, path):
		self.paths[name] = (False, path)

	def __getitem__(self, key):
		relative, path = self.paths[key]
		if not relative:
			return path
		return os.path.join(self.root, path)

	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default

	def iteritems(self):
		for key in self.paths.iterkeys():
			yield (key, self[key])

	def init(self, root = None):
		if root is not None:
			self.root = root

		# LOG is deprecated
		k = ( 'LOG',   'LOG_DB',   'VCARD',   'AVATAR',   'MY_EMOTS',
			'MY_ICONSETS', 'MY_MOOD_ICONSETS',
			'MY_ACTIVITY_ICONSETS', 'MY_CACERTS')
		v = (u'logs', u'logs.db', u'vcards', u'avatars', u'emoticons',
			u'iconsets',  u'moods', u'activities', u'cacerts.pem')

		if os.name == 'nt':
			v = [x.capitalize() for x in v]

		for n, p in zip(k, v):
			self.add_from_root(n, p)

		datadir = ''
		if u'datadir' in os.environ:
			datadir = fse(os.environ[u'datadir'])
		if not datadir:
			datadir = u'..'
		self.add('DATA', os.path.join(datadir, windowsify(u'data')))
		self.add('HOME', fse(os.path.expanduser('~')))
		self.add('TMP', fse(tempfile.gettempdir()))

		try:
			import svn_config
			svn_config.configure(self)
		except (ImportError, AttributeError):
			pass

		# for k, v in paths.iteritems():
		# 	print "%s: %s" % (repr(k), repr(v))

	def init_profile(self, profile = ''):
		conffile = windowsify(u'config')
		pidfile = windowsify(u'gajim')
		secretsfile = windowsify(u'secrets')

		if len(profile) > 0:
			conffile += u'.' + profile
			pidfile += u'.' + profile
			secretsfile += u'.' + profile
		pidfile += u'.pid'
		self.add_from_root('CONFIG_FILE', conffile)
		self.add_from_root('PID_FILE', pidfile)
		self.add_from_root('SECRETS_FILE', secretsfile)

		# for k, v in paths.iteritems():
		# 	print "%s: %s" % (repr(k), repr(v))

gajimpaths = ConfigPaths()

# vim: se ts=3:
