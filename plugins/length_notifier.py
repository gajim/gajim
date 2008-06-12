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
Message length notifier plugin.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 06/01/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys

import gtk

from plugins import GajimPlugin
from plugins.helpers import log, log_calls

class LengthNotifierPlugin(GajimPlugin):
	name = u'Message Length Notifier'
	short_name = u'length_notifier'
	version = u'0.1'
	description = u'''Highlights message entry field in chat window when given length of message is exceeded.'''
	authors = [u'Mateusz Biliński <mateusz@bilinski.it>']
	homepage = u'http://blog.bilinski.it'

	@log_calls('LengthNotifierPlugin')
	def __init__(self):
		super(LengthNotifierPlugin, self).__init__()
		
		self.gui_extension_points = {
			'chat_control' : (self.connect_with_chat_control,
							  self.disconnect_from_chat_control)
		}		
		
		self.MESSAGE_WARNING_LENGTH = 140
		self.WARNING_COLOR = gtk.gdk.color_parse('#F0DB3E')
		self.JIDS = []
		
	@log_calls('LengthNotifierPlugin')
	def textview_length_warning(self, tb, chat_control):
		tv = chat_control.msg_textview
		d = chat_control.length_notifier_plugin_data
		t = tb.get_text(tb.get_start_iter(), tb.get_end_iter())
		if t:
			len_t = len(t)
			#print("len_t: %d"%(len_t))
			if len_t>self.MESSAGE_WARNING_LENGTH:
				if not d['prev_color']:
					d['prev_color'] = tv.style.copy().base[gtk.STATE_NORMAL]
				tv.modify_base(gtk.STATE_NORMAL, self.WARNING_COLOR)
			elif d['prev_color']:
				tv.modify_base(gtk.STATE_NORMAL, d['prev_color'])
				d['prev_color'] = None
	
	@log_calls('LengthNotifierPlugin')
	def connect_with_chat_control(self, chat_control):
		jid = chat_control.contact.jid
		if self.jid_is_ok(jid):
			d = {'prev_color' : None}
			tv = chat_control.msg_textview
			tb = tv.get_buffer()
			h_id = tb.connect('changed', self.textview_length_warning, chat_control)
			d['h_id'] = h_id
			
			t = tb.get_text(tb.get_start_iter(), tb.get_end_iter())
			if t:
				len_t = len(t)
				if len_t>self.MESSAGE_WARNING_LENGTH:
					d['prev_color'] = tv.style.copy().base[gtk.STATE_NORMAL]
					tv.modify_base(gtk.STATE_NORMAL, self.WARNING_COLOR)
				
			chat_control.length_notifier_plugin_data = d
			
			return True
		
		return False
	
	@log_calls('LengthNotifierPlugin')
	def disconnect_from_chat_control(self, chat_control):
		d = chat_control.length_notifier_plugin_data
		tv = chat_control.msg_textview
		tv.get_buffer().disconnect(d['h_id'])
		if d['prev_color']:
			tv.modify_base(gtk.STATE_NORMAL, d['prev_color'])
	
	@log_calls('LengthNotifierPlugin')
	def jid_is_ok(self, jid):
		return True