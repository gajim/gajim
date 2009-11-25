# -*- coding:utf-8 -*-
## src/groups.py
##
## Copyright (C) 2006 Yann Leboulanger <asterix AT lagaule.org>
##                    Tomasz Melcer <liori AT exroot.org>
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

'''Window to create new post for discussion groups service.'''

from common import gajim, xmpp
import gtkgui_helpers

class GroupsPostWindow:
	def __init__(self, account, servicejid, groupid):
		"""
		Open new 'create post' window to create message for groupid on servicejid
		service
		"""
		assert isinstance(servicejid, basestring)
		assert isinstance(groupid, basestring)

		self.account = account
		self.servicejid = servicejid
		self.groupid = groupid

		self.xml = gtkgui_helpers.get_glade('groups_post_window.glade')
		self.window = self.xml.get_widget('groups_post_window')
		for name in ('from_entry', 'subject_entry', 'contents_textview'):
			self.__dict__[name] = self.xml.get_widget(name)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_cancel_button_clicked(self, w):
		"""
		Close window
		"""
		self.window.destroy()

	def on_send_button_clicked(self, w):
		"""
		Gather info from widgets and send it as a message
		"""
		# constructing item to publish... that's atom:entry element
		item = xmpp.Node('entry', {'xmlns':'http://www.w3.org/2005/Atom'})
		author = item.addChild('author')
		author.addChild('name', {}, [self.from_entry.get_text()])
		item.addChild('generator', {}, ['Gajim'])
		item.addChild('title', {}, [self.subject_entry.get_text()])
		item.addChild('id', {}, ['0'])

		buf = self.contents_textview.get_buffer()
		item.addChild('content', {}, [buf.get_text(buf.get_start_iter(), buf.get_end_iter())])

		# publish it to node
		gajim.connections[self.account].send_pb_publish(self.servicejid, self.groupid, item, '0')

		# close the window
		self.window.destroy()

# vim: se ts=3:
