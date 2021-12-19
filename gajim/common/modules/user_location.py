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

from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import store_publish


class UserLocation(BaseModule):

    _nbxmpp_extends = 'Location'
    _nbxmpp_methods = [
        'set_location',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._location_received)

        self._current_location = None
        self._locations = {}

    def get_current_location(self):
        return self._current_location

    @event_node(Namespace.LOCATION)
    def _location_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        if properties.is_self_message:
            self._current_location = data
        else:
            self._locations[properties.jid] = data

        app.nec.push_incoming_event(
            NetworkEvent('location-received',
                         account=self._account,
                         jid=properties.jid.bare,
                         location=data,
                         is_self_message=properties.is_self_message))

    @store_publish
    def set_location(self, location):
        self._current_location = location
        self._log.info('Send %s', location)
        self._nbxmpp('Location').set_location(location)
