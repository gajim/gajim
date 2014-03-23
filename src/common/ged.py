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
Global Events Dispatcher module.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 8th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:copyright: Copyright (2011) Yann Leboulanger <asterix@lagaule.org>
:license: GPL
'''

import traceback

from nbxmpp import NodeProcessed
import logging
log = logging.getLogger('gajim.c.ged')

PRECORE = 10
CORE = 20
POSTCORE = 30
PREGUI = 40
PREGUI1 = 50
GUI1 = 60
POSTGUI1 = 70
PREGUI2 = 80
GUI2 = 90
POSTGUI2 = 100
POSTGUI = 110

OUT_PREGUI = 10
OUT_PREGUI1 = 20
OUT_GUI1 = 30
OUT_POSTGUI1 = 40
OUT_PREGUI2 = 50
OUT_GUI2 = 60
OUT_POSTGUI2 = 70
OUT_POSTGUI = 80
OUT_PRECORE = 90
OUT_CORE = 100
OUT_POSTCORE = 110

class GlobalEventsDispatcher(object):

    def __init__(self):
        self.handlers = {}

    def register_event_handler(self, event_name, priority, handler):
        if event_name in self.handlers:
            handlers_list = self.handlers[event_name]
            i = 0
            for i, h in enumerate(handlers_list):
                if priority < h[0]:
                    break
            else:
                # no event with smaller prio found, put it at the end
                i += 1

            handlers_list.insert(i, (priority, handler))
        else:
            self.handlers[event_name] = [(priority, handler)]

    def remove_event_handler(self, event_name, priority, handler):
        if event_name in self.handlers:
            try:
                self.handlers[event_name].remove((priority, handler))
            except ValueError:
                log.warning('''Function (%s) with priority "%s" never registered
                as handler of event "%s". Couldn\'t remove. Error: %s'''
                                  %(handler, priority, event_name, error))

    def raise_event(self, event_name, *args, **kwargs):
        log.debug('%s\nArgs: %s'%(event_name, str(args)))
        if event_name in self.handlers:
            node_processed = False
            for priority, handler in self.handlers[event_name]:
                try:
                    if handler(*args, **kwargs):
                        return True
                except NodeProcessed:
                    node_processed = True
                except Exception:
                    log.error('Error while running an even handler: %s' % \
                        handler)
                    traceback.print_exc()
            if node_processed:
                raise NodeProcessed
