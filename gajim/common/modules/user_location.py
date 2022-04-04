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

# XEP-0080: User Location

from __future__ import annotations

from typing import Optional

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import LocationData

from gajim.common import app
from gajim.common import ged
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import store_publish
from gajim.common.dbus.location import LocationListener
from gajim.common.helpers import event_filter


class UserLocation(BaseModule):

    _nbxmpp_extends = 'Location'
    _nbxmpp_methods = [
        'set_location',
    ]

    def __init__(self, con) -> None:
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._location_received)

        self._current_location: Optional[LocationData] = None
        self._contact_locations: dict[JID, LocationData] = {}

    def get_current_location(self) -> Optional[LocationData]:
        return self._current_location

    def get_contact_location(self, jid: JID) -> Optional[LocationData]:
        return self._contact_locations.get(jid)

    @event_node(Namespace.LOCATION)
    def _location_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        if properties.is_self_message:
            self._current_location = data

        self._contact_locations[properties.jid] = data

        contact = self._get_contact(properties.jid)
        contact.notify('location-update', data)

    @store_publish
    def set_location(self, location, force=False):
        if not self._con.get_module('PEP').supported:
            return

        if not force and not app.settings.get_account_setting(
                self._account, 'publish_location'):
            return

        if location == self._current_location:
            return

        self._current_location = location
        self._log.info('Send %s', location)
        self._nbxmpp('Location').set_location(location)

    def set_enabled(self, enable):
        if enable:
            self.register_events([
                ('location-changed', ged.CORE, self._on_location_changed),
                ('signed-in', ged.CORE, self._on_signed_in),
            ])
            self._publish_current_location()
        else:
            self.unregister_events()
            self.set_location(None, force=True)

    def _publish_current_location(self):
        self.set_location(LocationListener.get().current_location)

    @event_filter(['account'])
    def _on_signed_in(self, _event):
        self._publish_current_location()

    def _on_location_changed(self, event):
        if self._current_location == event.info:
            return

        self.set_location(event.info)
