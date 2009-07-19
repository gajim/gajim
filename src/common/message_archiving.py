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


class ConnectionArchive:
	def __init__(self):
		self.archive_auto_supported = False
		self.archive_manage_supported = False
		self.archive_manual_supported = False
		self.archive_pref_supported = False
		self.auto_save = None
		self.method_auto = None
		self.method_local = None
		self.method_manual = None
		self.default = None
		self.items = {}
		
	def set_default(self, otr, save, expire=None, unset=False):
		self.default = {'expire': expire, 'otr': otr, 'save': save,
			'unset': unset}

	def append_or_update_item(self, jid, otr, save, expire):
		self.items[jid] = {'expire': expire, 'otr': otr, 'save': save}

	def remove_item(self, jid):
		del self.items[jid]

	def _ArchiveCB(self, con, iq_obj):
		print '_ArchiveCB', iq_obj.getType()
		if iq_obj.getType() not in ('result', 'set'):
			return
		if iq_obj.getTag('pref'):
			pref = iq_obj.getTag('pref')

			if pref.getTag('auto'):
				self.auto_save = pref.getTagAttr('auto', 'save')
				print 'auto_save:', self.auto_save

			method_auto = pref.getTag('method', attrs={'type': 'auto'})
			if method_auto:
				self.method_auto = method_auto.getAttr('use')

			method_local = pref.getTag('method', attrs={'type': 'local'})
			if method_local:
				self.method_local = method_local.getAttr('use')

			method_manual = pref.getTag('method', attrs={'type': 'manual'})
			if method_manual:
				self.method_manual = method_manual.getAttr('use')

			print 'method alm:', self.method_auto, self.method_local, self.method_manual

			if pref.getTag('default'):
				default = pref.getTag('default')
				print 'default oseu:', default.getAttr('otr'), default.getAttr('save'), default.getAttr('expire'), default.getAttr('unset')
				self.set_default(default.getAttr('otr'),
					default.getAttr('save'), default.getAttr('expire'),
					default.getAttr('unset'))
			for item in pref.getTags('item'):
				print item.getAttr('jid'), item.getAttr('otr'), item.getAttr('save'), item.getAttr('expire')
				self.append_or_update_item(item.getAttr('jid'),
					item.getAttr('otr'), item.getAttr('save'),
					item.getAttr('expire'))
		elif iq_obj.getTag('itemremove'):
			for item in pref.getTags('item'):
				print 'del', item.getAttr('jid')
				self.remove_item(item.getAttr('jid'))
