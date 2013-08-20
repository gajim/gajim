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
:since: 9th June 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys

from gi.repository import Gtk
from gi.repository import GObject

from plugins import GajimPlugin
from plugins.helpers import log, log_calls

class AcronymsExpanderPlugin(GajimPlugin):

    @log_calls('AcronymsExpanderPlugin')
    def init(self):
        self.description = _('Replaces acronyms (or other strings) '
            'with given expansions/substitutes.')
        self.config_dialog = None

        self.gui_extension_points = {
            'chat_control_base': (self.connect_with_chat_control_base,
                                  self.disconnect_from_chat_control_base)
        }

        self.config_default_values = {
            'INVOKER': (' ', ''),
            'ACRONYMS': ({'/slap': '/me slaps',
                          'PS-': 'plug-in system',
                          'G-': 'Gajim',
                          'GNT-': 'http://trac.gajim.org/newticket',
                          'GW-': 'http://trac.gajim.org/',
                          'GTS-': 'http://trac.gajim.org/report',
                         },
                         ''),
        }
        if 'ACRONYMS' not in self.config:
            myAcronyms = self.get_own_acronyms_list()
            self.config['ACRONYMS'].update(myAcronyms)

    @log_calls('AcronymsExpanderPlugin')
    def get_own_acronyms_list(self):
        data_file = self.local_file_path('acronyms')
        data = open(data_file, 'r')
        acronyms = eval(data.read())
        data.close()
        return acronyms

    @log_calls('AcronymsExpanderPlugin')
    def textbuffer_live_acronym_expander(self, tb):
        """
        @param tb gtk.TextBuffer
        """
        #assert isinstance(tb,gtk.TextBuffer)
        ACRONYMS = self.config['ACRONYMS']
        INVOKER = self.config['INVOKER']
        t = tb.get_text(tb.get_start_iter(), tb.get_end_iter(), True)
        #log.debug('%s %d'%(t, len(t)))
        if t and t[-1] == INVOKER:
            #log.debug('changing msg text')
            base, sep, head=t[:-1].rpartition(INVOKER)
            log.debug('%s | %s | %s'%(base, sep, head))
            if head in ACRONYMS:
                head = ACRONYMS[head]
                #log.debug('head: %s'%(head))
                t = ''.join((base, sep, head, INVOKER))
                #log.debug("setting text: '%s'"%(t))
                GObject.idle_add(tb.set_text, t)

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
