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

from __future__ import annotations

from typing import Any

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import TuneData

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.dbus.music_track import MusicTrackListener
from gajim.common.events import MusicTrackChanged
from gajim.common.events import SignedIn
from gajim.common.helpers import event_filter
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import store_publish


class UserTune(BaseModule):

    _nbxmpp_extends = 'Tune'
    _nbxmpp_methods = [
        'set_tune',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._tune_received)
        self._current_tune: TuneData | None = None
        self._contact_tunes: dict[JID, TuneData] = {}

    def get_current_tune(self) -> TuneData | None:
        return self._current_tune

    def get_contact_tune(self, jid: JID) -> TuneData | None:
        return self._contact_tunes.get(jid)

    @event_node(Namespace.TUNE)
    def _tune_received(self,
                       _con: types.xmppClient,
                       _stanza: Any,
                       properties: MessageProperties
                       ) -> None:
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        if properties.is_self_message:
            self._current_tune = data

        self._contact_tunes[properties.jid] = data

        contact = self._get_contact(properties.jid)
        contact.notify('tune-update', data)

    @store_publish
    def set_tune(self, tune: TuneData | None, force: bool = False) -> None:
        if not self._con.get_module('PEP').supported:
            return

        if not force and not app.settings.get_account_setting(
                self._account, 'publish_tune'):
            return

        if tune == self._current_tune:
            return

        self._current_tune = tune

        self._log.info('Send %s', tune)
        self._nbxmpp('Tune').set_tune(tune)

    def set_enabled(self, enable: bool) -> None:
        if enable:
            self.register_events([
                ('music-track-changed', ged.CORE, self._on_music_track_changed),
                ('signed-in', ged.CORE, self._on_signed_in),
            ])
            self._publish_current_tune()
        else:
            self.unregister_events()
            self.set_tune(None, force=True)

    def _publish_current_tune(self):
        self.set_tune(MusicTrackListener.get().current_tune)

    @event_filter(['account'])
    def _on_signed_in(self, _event: SignedIn) -> None:
        self._publish_current_tune()

    def _on_music_track_changed(self, event: MusicTrackChanged) -> None:
        if self._current_tune == event.info:
            return

        self.set_tune(event.info)
