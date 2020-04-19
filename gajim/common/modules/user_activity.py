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

# XEP-0108: User Activity

from typing import Any
from typing import Tuple

from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import store_publish
from gajim.common.const import PEPEventType


class UserActivity(BaseModule):

    _nbxmpp_extends = 'Activity'
    _nbxmpp_methods = [
        'set_activity',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._activity_received)

    @event_node(Namespace.ACTIVITY)
    def _activity_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        for contact in app.contacts.get_contacts(self._account,
                                                 str(properties.jid)):
            if data is not None:
                contact.pep[PEPEventType.ACTIVITY] = data
            else:
                contact.pep.pop(PEPEventType.ACTIVITY, None)

        if properties.is_self_message:
            if data is not None:
                self._con.pep[PEPEventType.ACTIVITY] = data
            else:
                self._con.pep.pop(PEPEventType.ACTIVITY, None)

        app.nec.push_incoming_event(
            NetworkEvent('activity-received',
                         account=self._account,
                         jid=properties.jid.getBare(),
                         activity=data,
                         is_self_message=properties.is_self_message))

    @store_publish
    def set_activity(self, activity):
        self._log.info('Send %s', activity)
        self._nbxmpp('Activity').set_activity(activity)


def get_instance(*args: Any, **kwargs: Any) -> Tuple[UserActivity, str]:
    return UserActivity(*args, **kwargs), 'UserActivity'
