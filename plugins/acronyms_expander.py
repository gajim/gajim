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
Acronyms expander plugin.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 06/10/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys

import gtk

from plugins import GajimPlugin
from plugins.helpers import log, log_calls

class AcronymsExpanderPlugin(GajimPlugin):
	name = u'Acronyms Expander'
	short_name = u'acronyms_expander'
	version = u'0.1'
	description = u'''Replaces acronyms (or other strings) with given expansions/substitutes.'''
	authors = [u'Mateusz Biliński <mateusz@bilinski.it>']
	homepage = u'http://blog.bilinski.it'

	@log_calls('AcronymsExpanderPlugin')
	def __init__(self):
		super(AcronymsExpanderPlugin, self).__init__()

		self.__class__.gui_extension_points = {
			'chat_control_base' : (self.connect_with_chat_control_base,
								   self.disconnect_from_chat_control_base)
		}		

		self.INVOKER = ' '
		self.ACRONYMS = {'RTFM' : 'Read The Friendly Manual',
						 '/slap' : '/me slaps',
						 'PS-' : 'plug-in system',
						 'G-' : 'Gajim',
						 'GNT-' : 'http://trac.gajim.org/newticket',
						 'GW-' : 'http://trac.gajim.org/',
						 'GTS-' : 'http://trac.gajim.org/report'
						}

	@log_calls('AcronymsExpanderPlugin')
	def textbuffer_live_acronym_expander(self, tb):
		"""
		@param tb gtk.TextBuffer
		"""
		assert isinstance(tb,gtk.TextBuffer)
		t = tb.get_text(tb.get_start_iter(), tb.get_end_iter())
		log.debug('%s %d'%(t, len(t)))
		if t and t[-1] == self.INVOKER:
			log.debug("changing msg text")
			base,sep,head=t[:-1].rpartition(self.INVOKER)
			log.debug('%s | %s | %s'%(base, sep, head))
			if head in self.ACRONYMS:
				head = self.ACRONYMS[head]
				log.debug("head: %s"%(head))
				t = "".join((base, sep, head, self.INVOKER))
				log.debug("turning off notify")
				tb.freeze_notify()
				log.debug("setting text: '%s'"%(t))
				tb.set_text(t)
				log.debug("turning on notify")
				tb.thaw_notify()
		
	@log_calls('AcronymsExpanderPlugin')
	def connect_with_chat_control_base(self, chat_control):
		d = {}
		tv = chat_control.msg_textview
		tb = tv.get_buffer()
		h_id = tb.connect('changed', self.textbuffer_live_acronym_expander)
		d['h_id'] = h_id

		chat_control.acronyms_expander_plugin_data = d

		return True

	@log_calls('AcronymsExpanderPlugin')
	def disconnect_from_chat_control_base(self, chat_control):
		d = chat_control.acronyms_expander_plugin_data
		tv = chat_control.msg_textview
		tv.get_buffer().disconnect(d['h_id'])
		