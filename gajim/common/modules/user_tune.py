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

# XEP-0118: User Tune

from typing import Any
from typing import Tuple

from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import store_publish
from gajim.common.const import PEPEventType


class UserTune(BaseModule):

    _nbxmpp_extends = 'Tune'
    _nbxmpp_methods = [
        'set_tune',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._tune_received)

    @event_node(Namespace.TUNE)
    def _tune_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        for contact in app.contacts.get_contacts(self._account,
                                                 str(properties.jid)):
            if data is not None:
                contact.pep[PEPEventType.TUNE] = data
            else:
                contact.pep.pop(PEPEventType.TUNE, None)

        if properties.is_self_message:
            if data is not None:
                self._con.pep[PEPEventType.TUNE] = data
            else:
                self._con.pep.pop(PEPEventType.TUNE, None)

        app.nec.push_incoming_event(
            NetworkEvent('tune-received',
                         account=self._account,
                         jid=properties.jid.getBare(),
                         tune=data,
                         is_self_message=properties.is_self_message))

    @store_publish
    def set_tune(self, tune):
        self._log.info('Send %s', tune)
        self._nbxmpp('Tune').set_tune(tune)


def get_instance(*args: Any, **kwargs: Any) -> Tuple[UserTune, str]:
    return UserTune(*args, **kwargs), 'UserTune'
