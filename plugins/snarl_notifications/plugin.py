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
    name = u'Snarl Notifications'
    short_name = u'snarl_notifications'
    version = u'0.1'
    description = u'''Shows events notification using Snarl (http://www.fullphat.net/) under Windows. Snarl needs to be installed in system.
PySnarl bindings are used (http://code.google.com/p/pysnarl/).'''
    authors = [u'Mateusz Biliński <mateusz@bilinski.it>']
    homepage = u'http://blog.bilinski.it'

    @log_calls('SnarlNotificationsPlugin')
    def init(self):
        self.config_dialog = None
        #self.gui_extension_points = {}
        #self.config_default_values = {}

        self.events_handlers = {'NewMessage' : (ged.POSTCORE, self.newMessage)}

    @log_calls('SnarlNotificationsPlugin')
    def activate(self):
        pass

    @log_calls('SnarlNotificationsPlugin')
    def deactivate(self):
        pass

    @log_calls('SnarlNotificationsPlugin')
    def newMessage(self, args):
        event_name = "NewMessage"
        data = args
        account = data[0]
        jid = data[1][0]
        jid_without_resource = gajim.get_jid_without_resource(jid)
        msg = data[1][1]
        msg_type = data[1][4]
        if msg_type == 'chat':
            nickname = gajim.get_contact_name_from_jid(account,
                                                                                       jid_without_resource)
        elif msg_type == 'pm':
            nickname = gajim.get_resource_from_jid(jid)

        print "Event '%s' occured. Arguments: %s\n\n===\n"%(event_name, pformat(args))
        print "Event '%s' occured. Arguments: \naccount = %s\njid = %s\nmsg = %s\nnickname = %s"%(
                event_name, account, jid, msg, nickname)


        #if PySnarl.snGetVersion() != False:
            #(major, minor) = PySnarl.snGetVersion()
            #print "Found Snarl version",str(major)+"."+str(minor),"running."
            #PySnarl.snShowMessage(nickname, msg[:20]+'...')
        #else:
            #print "Sorry Snarl does not appear to be running"
