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
from nbxmpp.structs import ActivityData

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.const import PEPEventType


class UserActivity(BaseModule):

    _nbxmpp_extends = 'Activity'
    _nbxmpp_methods = [
        'set_activity',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._activity_received)

        self._current_activity = None
        self._activities = {}

    def get_current_activity(self):
        return self._current_activity

    @event_node(Namespace.ACTIVITY)
    def _activity_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        if properties.is_self_message:
            self._current_activity = data
        else:
            self._activities[properties.jid] = data

        app.nec.push_incoming_event(
            NetworkEvent('activity-received',
                         account=self._account,
                         jid=properties.jid.bare,
                         activity=data,
                         is_self_message=properties.is_self_message))

    def set_activity(self, activity):
        if activity is not None:
            activity = ActivityData(*activity, None)

        if activity == self._current_activity:
            return

        self._current_activity = activity

        if activity is None:
            self._log.info('Remove user activity')
        else:
            self._log.info('Set %s', activity)

        self._nbxmpp('Activity').set_activity(activity)


def get_instance(*args: Any, **kwargs: Any) -> Tuple[UserActivity, str]:
    return UserActivity(*args, **kwargs), 'UserActivity'
