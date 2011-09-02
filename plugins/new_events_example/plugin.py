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
New Events Example plugin.

Demonstrates how to use Network Events Controller to generate new events
based on existing one.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 15th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import new
from pprint import pformat

from common import helpers
from common import gajim

from plugins import GajimPlugin
from plugins.helpers import log_calls, log
from common import ged
from common import nec

class NewEventsExamplePlugin(GajimPlugin):

    @log_calls('NewEventsExamplePlugin')
    def init(self):
        self.description = _('Shows how to generate new network events based '
            'on existing one using Network Events Controller.')
        self.config_dialog = None
        #self.gui_extension_points = {}
        #self.config_default_values = {}

        self.events_handlers = {'raw-message-received' :
                (ged.POSTCORE, self.raw_message_received),
            'customized-message-received' :
                (ged.POSTCORE, self.customized_message_received),
            'enriched-chat-message-received' :
                (ged.POSTCORE, self.enriched_chat_message_received)}

        self.events = [CustomizedMessageReceivedEvent,
            MoreCustomizedMessageReceivedEvent,
            ModifyOnlyMessageReceivedEvent,
            EnrichedChatMessageReceivedEvent]

    def enriched_chat_message_received(self, event_object):
        pass
        # print "Event '%s' occured. Event object: %s\n\n===\n" % \
        # (event_object.name, event_object)

    def raw_message_received(self, event_object):
        pass
        # print "Event '%s' occured. Event object: %s\n\n===\n" % \
        # (event_object.name,event_object)

    def customized_message_received(self, event_object):
        pass
        # print "Event '%s' occured. Event object: %s\n\n===\n" % \
        # (event_object.name, event_object

    @log_calls('NewEventsExamplePlugin')
    def activate(self):
        pass

    @log_calls('NewEventsExamplePlugin')
    def deactivate(self):
        pass

class CustomizedMessageReceivedEvent(nec.NetworkIncomingEvent):
    name = 'customized-message-received'
    base_network_events = ['raw-message-received']

    def generate(self):
        return True

class MoreCustomizedMessageReceivedEvent(nec.NetworkIncomingEvent):
    '''
    Shows chain of custom created events.

    This one is based on custom 'customized-messsage-received'.
    '''
    name = 'more-customized-message-received'
    base_network_events = ['customized-message-received']

    def generate(self):
        return True

class ModifyOnlyMessageReceivedEvent(nec.NetworkIncomingEvent):
    name = 'modify-only-message-received'
    base_network_events = ['raw-message-received']

    def generate(self):
        msg_type = self.base_event.stanza.attrs.get('type', None)
        if msg_type == u'chat':
            msg_text = ''.join(self.base_event.stanza.kids[0].data)
            self.base_event.stanza.kids[0].setData(
                u'%s [MODIFIED BY CUSTOM NETWORK EVENT]' % (msg_text))

        return False

class EnrichedChatMessageReceivedEvent(nec.NetworkIncomingEvent):
    '''
    Generates more friendly (in use by handlers) network event for
    received chat message.
    '''
    name = 'enriched-chat-message-received'
    base_network_events = ['raw-message-received']

    def generate(self):
        msg_type = self.base_event.stanza.attrs.get('type', None)
        if msg_type == u'chat':
            self.stanza = self.base_event.stanza
            self.conn = self.base_event.conn
            self.from_jid = helpers.get_full_jid_from_iq(self.stanza)
            self.from_jid_without_resource = gajim.get_jid_without_resource(
                self.from_jid)
            self.account = self.conn.name
            self.from_nickname = gajim.get_contact_name_from_jid( self.account,
                self.from_jid_without_resource)
            self.msg_text = ''.join(self.stanza.kids[0].data)

            return True

        return False
