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

import common.xmpp


class ConnectionArchive:
	def __init__(self):
		self.archive_auto_supported = False
		self.archive_manage_supported = False
		self.archive_manual_supported = False
		self.archive_pref_supported = False
		self.auto = None
		self.method_auto = None
		self.method_local = None
		self.method_manual = None
		self.default = None
		self.items = {}

	def request_message_archiving_preferences(self):
		iq_ = common.xmpp.Iq('get')
		iq_.setTag('pref', namespace=common.xmpp.NS_ARCHIVE)
		print iq_
		self.connection.send(iq_)

	def set_pref(self, name, **data):
		'''
		data contains names and values of pref name attributes.
		'''
		iq_ = common.xmpp.Iq('set')
		pref = iq_.setTag('pref', namespace=common.xmpp.NS_ARCHIVE)
		tag = pref.setTag(name)
		for key, value in data.items():
			if value is not None:
				tag.setAttr(key, value)
		print iq_
		self.connection.send(iq_)

	def set_auto(self, save):
		self.set_pref('auto', save=save)

	def set_method(self, type, use):
		self.set_pref('method', type=type, use=use)

	def set_default(self, otr, save, expire=None):
		self.set_pref('default', otr=otr, save=save, expire=expire)

	def append_or_update_item(self, jid, otr, save, expire):
		self.set_pref('item', jid=jid, otr=otr, save=save)
		
	def remove_item(self, jid):
		iq_ = common.xmpp.Iq('set')
		itemremove = iq_.setTag('itemremove', namespace=common.xmpp.NS_ARCHIVE)
		item = itemremove.setTag('item')
		item.setAttr('jid', jid)
		print iq_
		self.connection.send(iq_)

	def _ArchiveCB(self, con, iq_obj):
		print '_ArchiveCB', iq_obj.getType()
		if iq_obj.getType() == 'error':
			self.dispatch('ARCHIVING_ERROR', iq_obj.getErrorMsg())
			return
		elif iq_obj.getType() not in ('result', 'set'):
			print iq_obj
			return
		
		if iq_obj.getTag('pref'):
			pref = iq_obj.getTag('pref')

			if pref.getTag('auto'):
				self.auto = pref.getTagAttr('auto', 'save')
				print 'auto:', self.auto
				self.dispatch('ARCHIVING_CHANGED', ('auto',
					self.auto))

			method_auto = pref.getTag('method', attrs={'type': 'auto'})
			if method_auto:
				self.method_auto = method_auto.getAttr('use')
				self.dispatch('ARCHIVING_CHANGED', ('method_auto',
					self.method_auto))

			method_local = pref.getTag('method', attrs={'type': 'local'})
			if method_local:
				self.method_local = method_local.getAttr('use')
				self.dispatch('ARCHIVING_CHANGED', ('method_local',
					self.method_local))

			method_manual = pref.getTag('method', attrs={'type': 'manual'})
			if method_manual:
				self.method_manual = method_manual.getAttr('use')
				self.dispatch('ARCHIVING_CHANGED', ('method_manual',
					self.method_manual))

			print 'method alm:', self.method_auto, self.method_local, self.method_manual

			if pref.getTag('default'):
				default = pref.getTag('default')
				print 'default oseu:', default.getAttr('otr'), default.getAttr('save'), default.getAttr('expire'), default.getAttr('unset')
				self.default = {
					'expire': default.getAttr('expire'),
					'otr': default.getAttr('otr'),
					'save': default.getAttr('save'),
					'unset': default.getAttr('unset')}
				self.dispatch('ARCHIVING_CHANGED', ('default',
					self.default))
			for item in pref.getTags('item'):
				print item.getAttr('jid'), item.getAttr('otr'), item.getAttr('save'), item.getAttr('expire')
				self.items[item.getAttr('jid')] = {
					'expire': item.getAttr('expire'),
					'otr': item.getAttr('otr'), 'save': item.getAttr('save')}
				self.dispatch('ARCHIVING_CHANGED', ('item',
					item.getAttr('jid'), self.items[item.getAttr('jid')]))
		elif iq_obj.getTag('itemremove'):
			for item in pref.getTags('item'):
				print 'del', item.getAttr('jid')
				del self.items[item.getAttr('jid')]
				self.dispatch('ARCHIVING_CHANGED', ('itemremove',
					item.getAttr('jid')))
