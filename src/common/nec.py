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
Network Events Controller.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 10th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:copyright: Copyright (2011) Yann Leboulanger <asterix@lagaule.org>
:license: GPL
'''

#from plugins.helpers import log
from common import gajim

class NetworkEventsController(object):

    def __init__(self):
        self.incoming_events_generators = {}
        '''
        Keys: names of events
        Values: list of class objects that are subclasses
        of `NetworkIncomingEvent`
        '''
        self.outgoing_events_generators = {}
        '''
        Keys: names of events
        Values: list of class objects that are subclasses
        of `NetworkOutgoingEvent`
        '''

    def register_incoming_event(self, event_class):
        for base_event_name in event_class.base_network_events:
            event_list = self.incoming_events_generators.setdefault(
                base_event_name, [])
            if not event_class in event_list:
                event_list.append(event_class)

    def unregister_incoming_event(self, event_class):
        for base_event_name in event_class.base_network_events:
            if base_event_name in self.incoming_events_generators:
                self.incoming_events_generators[base_event_name].remove(
                    event_class)

    def register_outgoing_event(self, event_class):
        for base_event_name in event_class.base_network_events:
            event_list = self.outgoing_events_generators.setdefault(
                base_event_name, [])
            if not event_class in event_list:
                event_list.append(event_class)

    def unregister_outgoing_event(self, event_class):
        for base_event_name in event_class.base_network_events:
            if base_event_name in self.outgoing_events_generators:
                self.outgoing_events_generators[base_event_name].remove(
                    event_class)

    def push_incoming_event(self, event_object):
        if event_object.generate():
            if not gajim.ged.raise_event(event_object.name, event_object):
                self._generate_events_based_on_incoming_event(event_object)

    def push_outgoing_event(self, event_object):
        if event_object.generate():
            if not gajim.ged.raise_event(event_object.name, event_object):
                self._generate_events_based_on_outgoing_event(event_object)

    def _generate_events_based_on_incoming_event(self, event_object):
        '''
        :return: True if even_object should be dispatched through Global
        Events Dispatcher, False otherwise. This can be used to replace
        base events with those that more data computed (easier to use
        by handlers).
        :note: replacing mechanism is not implemented currently, but will be
        based on attribute in new network events object.
        '''
        base_event_name = event_object.name
        if base_event_name in self.incoming_events_generators:
            for new_event_class in self.incoming_events_generators[
            base_event_name]:
                new_event_object = new_event_class(None,
                    base_event=event_object)
                if new_event_object.generate():
                    if not gajim.ged.raise_event(new_event_object.name,
                    new_event_object):
                        self._generate_events_based_on_incoming_event(
                            new_event_object)

    def _generate_events_based_on_outgoing_event(self, event_object):
        '''
        :return: True if even_object should be dispatched through Global
        Events Dispatcher, False otherwise. This can be used to replace
        base events with those that more data computed (easier to use
        by handlers).
        :note: replacing mechanism is not implemented currently, but will be
        based on attribute in new network events object.
        '''
        base_event_name = event_object.name
        if base_event_name in self.outgoing_events_generators:
            for new_event_class in self.outgoing_events_generators[
            base_event_name]:
                new_event_object = new_event_class(None,
                    base_event=event_object)
                if new_event_object.generate():
                    if not gajim.ged.raise_event(new_event_object.name,
                    new_event_object):
                        self._generate_events_based_on_outgoing_event(
                            new_event_object)

class NetworkEvent(object):
    name = ''

    def __init__(self, new_name, **kwargs):
        if new_name:
            self.name = new_name

        self.init()

        self._set_kwargs_as_attributes(**kwargs)

    def init(self):
        pass


    def generate(self):
        '''
        Generates new event (sets it's attributes) based on event object.

        Base event object name is one of those in `base_network_events`.

        Reference to base event object is stored in `self.base_event` attribute.

        Note that this is a reference, so modifications to that event object
        are possible before dispatching to Global Events Dispatcher.

        :return: True if generated event should be dispatched, False otherwise.
        '''
        return True

    def _set_kwargs_as_attributes(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class NetworkIncomingEvent(NetworkEvent):
    base_network_events = []
    '''
    Names of base network events that new event is going to be generated on.
    '''


class NetworkOutgoingEvent(NetworkEvent):
    base_network_events = []
    '''
    Names of base network events that new event is going to be generated on.
    '''
