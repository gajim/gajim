# -*- coding:utf-8 -*-
## src/common/message_archiving.py
##
## Copyright (C) 2009 Anaël Verrier <elghinn AT free.fr>
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


class ArchivingPreferences:
	def __init__(self):
		self.auto_save = None
		self.method_auto = None
		self.method_local = None
		self.method_manual = None
		self.default = None
		self.items = {}
		
	def set(self, auto_save, method_auto, method_local, method_manual):
		self.auto_save = auto_save
		self.method_auto = method_auto
		self.method_local = method_local
		self.method_manual = method_manual

	def set_default(self, otr, save, expire=None, unset=False):
		self.default = {'expire': expire, 'otr': otr, 'save': save, 'unset': unset}

	def append_or_update_item(self, jid, expire, otr, save):
		self.items[jid] = {'expire': expire, 'otr': otr, 'save': save}

	def remove_item(self, jid):
		del self.items[jid]
