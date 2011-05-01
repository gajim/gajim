# -*- coding: utf-8 -*-
##
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
Events notifications using Snarl

Fancy events notifications under Windows using Snarl infrastructure.

:note: plugin is at proof-of-concept state.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 15th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import new
from pprint import pformat

#import PySnarl

from common import gajim
from plugins import GajimPlugin
from plugins.helpers import log_calls, log
from common import ged

class SnarlNotificationsPlugin(GajimPlugin):

    @log_calls('SnarlNotificationsPlugin')
    def init(self):
        self.config_dialog = None
        #self.gui_extension_points = {}
        #self.config_default_values = {}

        self.events_handlers = {'notification' : (ged.POSTCORE, self.notif)}

    @log_calls('SnarlNotificationsPlugin')
    def activate(self):
        pass

    @log_calls('SnarlNotificationsPlugin')
    def deactivate(self):
        pass

    @log_calls('SnarlNotificationsPlugin')
    def notif(self, obj):
        print "Event '%s' occured.\n\n===\n" % obj.popup_event_type

        #if PySnarl.snGetVersion() != False:
            #(major, minor) = PySnarl.snGetVersion()
            #print "Found Snarl version",str(major)+"."+str(minor),"running."
            #PySnarl.snShowMessage(obj.popup_title, obj.popup_text)
        #else:
            #print "Sorry Snarl does not appear to be running"
