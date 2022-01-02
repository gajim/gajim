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

from gajim.common import app


EventHelperHandlersT = list[tuple[str, int, Callable[['NetworkEvent'], Any]]]


class NetworkEventsController:

    def push_incoming_event(self, event_object: NetworkEvent) -> None:
        if event_object.generate():
            app.ged.raise_event(event_object.name, event_object)

    def push_outgoing_event(self, event_object: NetworkEvent) -> None:
        if event_object.generate():
            app.ged.raise_event(event_object.name, event_object)


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
            if k != 'name':
                setattr(self, k, v)

    def _set_base_event_vars_as_attributes(self, event: NetworkEvent) -> None:
        for k, v in vars(event).items():
            if k != 'name':
                setattr(self, k, v)
