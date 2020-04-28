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
from gajim.common import ged
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import store_publish
from gajim.common.const import PEPEventType
from gajim.common.dbus.music_track import MusicTrackListener
from gajim.common.helpers import event_filter


class UserTune(BaseModule):

    _nbxmpp_extends = 'Tune'
    _nbxmpp_methods = [
        'set_tune',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._tune_received)
        self._tune_data = None

        self.register_events([
            ('music-track-changed', ged.CORE, self._on_music_track_changed),
            ('signed-in', ged.CORE, self._on_signed_in),
        ])

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
        if not self._con.get_module('PEP').supported:
            return

        if not app.config.get_per('accounts',
                                  self._account,
                                  'publish_tune'):
            return
        self._log.info('Send %s', tune)
        self._nbxmpp('Tune').set_tune(tune)

    def set_enabled(self, enable):
        if enable:
            app.config.set_per('accounts',
                               self._account,
                               'publish_tune',
                               True)
            self._publish_current_tune()

        else:
            self.set_tune(None)
            app.config.set_per('accounts',
                               self._account,
                               'publish_tune',
                               False)

    def _publish_current_tune(self):
        self.set_tune(MusicTrackListener.get().current_tune)

    @event_filter(['account'])
    def _on_signed_in(self, _event):
        self._publish_current_tune()

    def _on_music_track_changed(self, event):
        if self._tune_data == event.info:
            return
        self._tune_data = event.info
        self.set_tune(event.info)


def get_instance(*args: Any, **kwargs: Any) -> Tuple[UserTune, str]:
    return UserTune(*args, **kwargs), 'UserTune'
