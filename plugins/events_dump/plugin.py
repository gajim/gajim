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
Events Dump plugin.

Dumps info about selected events to console.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 10th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import new
from pprint import pformat

from plugins import GajimPlugin
from plugins.helpers import log_calls, log
from common import ged

class EventsDumpPlugin(GajimPlugin):

    @log_calls('EventsDumpPlugin')
    def init(self):
        self.description = _('Dumps info about selected events to console.')
        self.config_dialog = None
        #self.gui_extension_points = {}
        #self.config_default_values = {}
        events_from_old_dbus_support = [
                'Roster', 'AccountPresence', 'ContactPresence',
                'ContactAbsence', 'ContactStatus', 'NewMessage',
                'Subscribe', 'Subscribed', 'Unsubscribed',
                'NewAccount', 'VcardInfo', 'LastStatusTime',
                'OsInfo', 'GCPresence', 'GCMessage', 'RosterInfo',
                'NewGmail']

        events_from_src_gajim = [
                'ROSTER', 'WARNING', 'ERROR',
                'INFORMATION',  'ERROR_ANSWER', 'STATUS',
                'NOTIFY', 'MSGERROR', 'MSGSENT', 'MSGNOTSENT',
                'SUBSCRIBED', 'UNSUBSCRIBED', 'SUBSCRIBE',
                'AGENT_ERROR_INFO', 'AGENT_ERROR_ITEMS',
                'AGENT_REMOVED', 'REGISTER_AGENT_INFO',
                'AGENT_INFO_ITEMS', 'AGENT_INFO_INFO',
                'QUIT', 'NEW_ACC_CONNECTED',
                'NEW_ACC_NOT_CONNECTED', 'ACC_OK',      'ACC_NOT_OK',
                'MYVCARD', 'VCARD', 'LAST_STATUS_TIME', 'OS_INFO',
                'GC_NOTIFY', 'GC_MSG',  'GC_SUBJECT', 'GC_CONFIG',
                'GC_CONFIG_CHANGE', 'GC_INVITATION',
                'GC_AFFILIATION', 'GC_PASSWORD_REQUIRED',
                'BAD_PASSPHRASE', 'ROSTER_INFO', 'BOOKMARKS',
                'CON_TYPE', 'CONNECTION_LOST',  'FILE_REQUEST',
                'GMAIL_NOTIFY', 'FILE_REQUEST_ERROR',
                'FILE_SEND_ERROR', 'STANZA_ARRIVED', 'STANZA_SENT',
                'HTTP_AUTH', 'VCARD_PUBLISHED',
                'VCARD_NOT_PUBLISHED',  'ASK_NEW_NICK', 'SIGNED_IN',
                'METACONTACTS', 'ATOM_ENTRY', 'FAILED_DECRYPT',
                'PRIVACY_LISTS_RECEIVED', 'PRIVACY_LIST_RECEIVED',
                'PRIVACY_LISTS_ACTIVE_DEFAULT',
                'PRIVACY_LIST_REMOVED', 'ZC_NAME_CONFLICT',
                'PING_SENT', 'PING_REPLY',      'PING_ERROR',
                'SEARCH_FORM',  'SEARCH_RESULT',
                'RESOURCE_CONFLICT', 'PEP_CONFIG',
                'UNIQUE_ROOM_ID_UNSUPPORTED',
                'UNIQUE_ROOM_ID_SUPPORTED', 'SESSION_NEG',
                'GPG_PASSWORD_REQUIRED', 'SSL_ERROR',
                'FINGERPRINT_ERROR', 'PLAIN_CONNECTION',
                'PUBSUB_NODE_REMOVED',  'PUBSUB_NODE_NOT_REMOVED']

        network_events_from_core = ['raw-message-received',
                                                                'raw-iq-received',
                                                                'raw-pres-received']

        network_events_generated_in_nec = [
                'customized-message-received',
                'more-customized-message-received',
                'modify-only-message-received',
                'enriched-chat-message-received']

        self.events_names = []
        self.events_names += network_events_from_core
        self.events_names += network_events_generated_in_nec

        self.events_handlers = {}
        self._set_handling_methods()

    @log_calls('EventsDumpPlugin')
    def activate(self):
        pass

    @log_calls('EventsDumpPlugin')
    def deactivate(self):
        pass

    @log_calls('EventsDumpPlugin')
    def _set_handling_methods(self):
        for event_name in self.events_names:
            setattr(self, event_name,
                            new.instancemethod(
                                    self._generate_handling_method(event_name),
                                    self,
                                    EventsDumpPlugin))
            self.events_handlers[event_name] = (ged.POSTCORE,
                                                                               getattr(self, event_name))

    def _generate_handling_method(self, event_name):
        def handler(self, *args):
            print "Event '%s' occured. Arguments: %s\n\n===\n"%(event_name, pformat(args))

        return handler
