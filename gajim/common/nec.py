# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

'''
Network Events Controller.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 10th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:copyright: Copyright (2011) Yann Leboulanger <asterix@lagaule.org>
:license: GPL
'''

from __future__ import annotations

from typing import Any
from typing import Optional
from typing import Callable
from typing import Type

from gajim.common import app


EventHelperHandlersT = list[tuple[str, int, Callable[['NetworkEvent'], Any]]]

IncEventsGenT = dict[str, list[Type['NetworkIncomingEvent']]]
OutEventsGenT = dict[str, list[Type['NetworkOutgoingEvent']]]


class NetworkEventsController:
    def __init__(self):
        self.incoming_events_generators: IncEventsGenT = {}
        '''
        Keys: names of events
        Values: list of class objects that are subclasses
        of `NetworkIncomingEvent`
        '''
        self.outgoing_events_generators:OutEventsGenT = {}
        '''
        Keys: names of events
        Values: list of class objects that are subclasses
        of `NetworkOutgoingEvent`
        '''

    def register_incoming_event(self,
                                event_class: Type[NetworkIncomingEvent]
                                ) -> None:

        for base_event_name in event_class.base_network_events:
            event_list = self.incoming_events_generators.setdefault(
                base_event_name, [])
            if event_class not in event_list:
                event_list.append(event_class)

    def unregister_incoming_event(self,
                                  event_class: Type[NetworkIncomingEvent]
                                  ) -> None:

        for base_event_name in event_class.base_network_events:
            if base_event_name in self.incoming_events_generators:
                self.incoming_events_generators[base_event_name].remove(
                    event_class)

    def register_outgoing_event(self,
                                event_class: Type[NetworkOutgoingEvent]
                                ) -> None:

        for base_event_name in event_class.base_network_events:
            event_list = self.outgoing_events_generators.setdefault(
                base_event_name, [])
            if event_class not in event_list:
                event_list.append(event_class)

    def unregister_outgoing_event(self,
                                  event_class: Type[NetworkOutgoingEvent]
                                  ) -> None:

        for base_event_name in event_class.base_network_events:
            if base_event_name in self.outgoing_events_generators:
                self.outgoing_events_generators[base_event_name].remove(
                    event_class)

    def push_incoming_event(self, event_object: NetworkEvent) -> None:
        if event_object.generate():
            if not app.ged.raise_event(event_object.name, event_object):
                self._generate_events_based_on_incoming_event(event_object)

    def push_outgoing_event(self, event_object: NetworkEvent) -> None:
        if event_object.generate():
            if not app.ged.raise_event(event_object.name, event_object):
                self._generate_events_based_on_outgoing_event(event_object)

    def _generate_events_based_on_incoming_event(self,
                                                 event_object: NetworkEvent
                                                 ) -> None:
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
                new_event_object = new_event_class(
                    None, base_event=event_object)
                if new_event_object.generate():
                    if not app.ged.raise_event(new_event_object.name,
                                               new_event_object):
                        self._generate_events_based_on_incoming_event(
                            new_event_object)

    def _generate_events_based_on_outgoing_event(self,
                                                 event_object: NetworkEvent
                                                 ) -> None:
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
                new_event_object = new_event_class(
                    None, base_event=event_object)
                if new_event_object.generate():
                    if not app.ged.raise_event(new_event_object.name,
                                               new_event_object):
                        self._generate_events_based_on_outgoing_event(
                            new_event_object)


class EventHelper:
    def __init__(self):
        self.__event_handlers: EventHelperHandlersT = []

    def register_event(self,
                       event_name: str,
                       priority: int,
                       handler: Callable[[NetworkEvent], Any]) -> None:

        self.__event_handlers.append((event_name, priority, handler))
        app.ged.register_event_handler(event_name, priority, handler)

    def register_events(self, events: EventHelperHandlersT) -> None:

        for handler in events:
            self.__event_handlers.append(handler)
            app.ged.register_event_handler(*handler)

    def unregister_event(self,
                         event_name: str,
                         priority: int,
                         handler: Callable[[NetworkEvent], Any]) -> None:

        self.__event_handlers.remove((event_name, priority, handler))
        app.ged.register_event_handler(event_name, priority, handler)

    def unregister_events(self) -> None:
        for handler in self.__event_handlers:
            app.ged.remove_event_handler(*handler)
        self.__event_handlers.clear()


class NetworkEvent:
    name: str = ''

    def __init__(self, new_name: Optional[str], **kwargs: Any) -> None:
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

        Reference to base event object is stored in `self.base_event`
        attribute.

        Note that this is a reference, so modifications to that event object
        are possible before dispatching to Global Events Dispatcher.

        :return: True if generated event should be dispatched, False otherwise.
        '''
        return True

    def _set_kwargs_as_attributes(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if k not in ('name', 'base_network_events'):
                setattr(self, k, v)

    def _set_base_event_vars_as_attributes(self, event: NetworkEvent) -> None:
        for k, v in vars(event).items():
            if k not in ('name', 'base_network_events'):
                setattr(self, k, v)


class NetworkIncomingEvent(NetworkEvent):
    base_network_events: list[str] = []
    '''
    Names of base network events that new event is going to be generated on.
    '''


class NetworkOutgoingEvent(NetworkEvent):
    base_network_events: list[str] = []
    '''
    Names of base network events that new event is going to be generated on.
    '''
