# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# XEP-0107: User Mood

from typing import Any
from typing import Tuple

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MoodData

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node


class UserMood(BaseModule):

    _nbxmpp_extends = 'Mood'
    _nbxmpp_methods = [
        'set_mood',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._mood_received)

        self._current_mood = None
        self._moods = {}

    def get_current_mood(self):
        return self._current_mood

    @event_node(Namespace.MOOD)
    def _mood_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        if properties.is_self_message:
            self._current_mood = data
        else:
            self._moods[properties.jid] = data

        app.nec.push_incoming_event(
            NetworkEvent('mood-received',
                         account=self._account,
                         jid=properties.jid.bare,
                         mood=data,
                         is_self_message=properties.is_self_message))

    def set_mood(self, mood):
        if mood is not None:
            mood = MoodData(mood, None)

        if mood == self._current_mood:
            return

        self._current_mood = mood

        if mood is None:
            self._log.info('Remove user mood')
        else:
            self._log.info('Set %s', mood)

        self._nbxmpp('Mood').set_mood(mood)


def get_instance(*args: Any, **kwargs: Any) -> Tuple[UserMood, str]:
    return UserMood(*args, **kwargs), 'UserMood'
