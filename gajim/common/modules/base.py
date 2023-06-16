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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload

import logging
from functools import partial
from unittest.mock import Mock

from nbxmpp.modules.activity import Activity
from nbxmpp.modules.adhoc import AdHoc
from nbxmpp.modules.annotations import Annotations
from nbxmpp.modules.attention import Attention
from nbxmpp.modules.blocking import Blocking
from nbxmpp.modules.bookmarks.native_bookmarks import NativeBookmarks
from nbxmpp.modules.bookmarks.pep_bookmarks import PEPBookmarks
from nbxmpp.modules.bookmarks.private_bookmarks import PrivateBookmarks
from nbxmpp.modules.captcha import Captcha
from nbxmpp.modules.chat_markers import ChatMarkers
from nbxmpp.modules.chatstates import Chatstates
from nbxmpp.modules.correction import Correction
from nbxmpp.modules.delay import Delay
from nbxmpp.modules.delimiter import Delimiter
from nbxmpp.modules.discovery import Discovery
from nbxmpp.modules.eme import EME
from nbxmpp.modules.entity_caps import EntityCaps
from nbxmpp.modules.entity_time import EntityTime
from nbxmpp.modules.http_auth import HTTPAuth
from nbxmpp.modules.http_upload import HTTPUpload
from nbxmpp.modules.ibb import IBB
from nbxmpp.modules.idle import Idle
from nbxmpp.modules.iq import BaseIq
from nbxmpp.modules.last_activity import LastActivity
from nbxmpp.modules.location import Location
from nbxmpp.modules.mam import MAM
from nbxmpp.modules.message import BaseMessage
from nbxmpp.modules.mood import Mood
from nbxmpp.modules.muc.moderation import Moderation
from nbxmpp.modules.muc.muc import MUC
from nbxmpp.modules.muclumbus import Muclumbus
from nbxmpp.modules.nickname import Nickname
from nbxmpp.modules.omemo import OMEMO
from nbxmpp.modules.oob import OOB
from nbxmpp.modules.openpgp import OpenPGP
from nbxmpp.modules.pgplegacy import PGPLegacy
from nbxmpp.modules.ping import Ping
from nbxmpp.modules.presence import BasePresence
from nbxmpp.modules.pubsub import PubSub
from nbxmpp.modules.reactions import Reactions
from nbxmpp.modules.receipts import Receipts
from nbxmpp.modules.register.register import Register
from nbxmpp.modules.replies import Replies
from nbxmpp.modules.roster import Roster
from nbxmpp.modules.security_labels import SecurityLabels
from nbxmpp.modules.software_version import SoftwareVersion
from nbxmpp.modules.tune import Tune
from nbxmpp.modules.user_avatar import UserAvatar
from nbxmpp.modules.vcard4 import VCard4
from nbxmpp.modules.vcard_avatar import VCardAvatar
from nbxmpp.modules.vcard_temp import VCardTemp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.ged import EventHelper
from gajim.common.modules.util import LogAdapter


class BaseModule(EventHelper):

    _nbxmpp_extends = ''
    _nbxmpp_methods: list[str] = []

    def __init__(self,
                 con: types.Client,
                 *args: Any,
                 plugin: bool = False,
                 **kwargs: Any) -> None:

        EventHelper.__init__(self)
        self._con = con
        self._client = con
        self._account = con.account
        self._log = self._set_logger(plugin)
        self._nbxmpp_callbacks: dict[str, Any] = {}
        self._stored_publish: types.AnyCallableT | None = None
        self.handlers: list[StanzaHandler] = []

    @classmethod
    def get_instance(cls, client: types.Client) -> BaseModule:
        return cls(client)

    def _set_logger(self, plugin: bool) -> LogAdapter:
        logger_name = 'gajim.c.m.%s'
        if plugin:
            logger_name = 'gajim.p.%s'
        logger_name = logger_name % self.__class__.__name__.lower()
        logger = logging.getLogger(logger_name)
        return LogAdapter(logger, {'account': self._account})

    def __getattr__(self, key: str) -> Any:
        if key not in self._nbxmpp_methods:
            raise AttributeError(
                f'attribute "{key}" is neither part of object '
                f'"{self.__class__.__name__}" nor declared in '
                '"_nbxmpp_methods"')

        if not app.account_is_connected(self._account):
            self._log.warning('Account not connected, can’t use %s', key)
            return None

        module = self._con.connection.get_module(self._nbxmpp_extends)

        callback = self._nbxmpp_callbacks.get(key)
        if callback is None:
            return getattr(module, key)
        return partial(getattr(module, key), callback=callback)

    def _register_callback(self, method, callback) -> None:
        self._nbxmpp_callbacks[method] = callback

    def _register_pubsub_handler(self, callback: types.AnyCallableT):
        handler = StanzaHandler(name='message',
                                callback=callback,
                                ns=Namespace.PUBSUB_EVENT,
                                priority=49)
        self.handlers.append(handler)

    def send_stored_publish(self) -> None:
        if self._stored_publish is None:
            return
        self._log.info('Send stored publish')
        self._stored_publish()  # pylint: disable=not-callable

    def _get_contact(self,
                     jid: JID,
                     groupchat: bool = False) -> types.ContactT:
        return self._con.get_module('Contacts').get_contact(
            jid, groupchat=groupchat)

    def cleanup(self) -> None:
        self.unregister_events()
        self._client.disconnect_all_from_obj(self)

    @overload
    def _nbxmpp(self, name: Literal['Activity']) -> Activity: ...
    @overload
    def _nbxmpp(self, name: Literal['AdHoc']) -> AdHoc: ...
    @overload
    def _nbxmpp(self, name: Literal['Annotations']) -> Annotations: ...
    @overload
    def _nbxmpp(self, name: Literal['Attention']) -> Attention: ...
    @overload
    def _nbxmpp(self, name: Literal['Blocking']) -> Blocking: ...
    @overload
    def _nbxmpp(self, name: Literal['NativeBookmarks'] ) -> NativeBookmarks: ...  # noqa: E501
    @overload
    def _nbxmpp(self, name: Literal['PEPBookmarks']) -> PEPBookmarks: ...
    @overload
    def _nbxmpp(self, name: Literal['PrivateBookmarks']) -> PrivateBookmarks: ...  # noqa: E501
    @overload
    def _nbxmpp(self, name: Literal['Captcha']) -> Captcha: ...
    @overload
    def _nbxmpp(self, name: Literal['ChatMarkers']) -> ChatMarkers: ...
    @overload
    def _nbxmpp(self, name: Literal['Chatstates']) -> Chatstates: ...
    @overload
    def _nbxmpp(self, name: Literal['Correction']) -> Correction: ...
    @overload
    def _nbxmpp(self, name: Literal['Delay']) -> Delay: ...
    @overload
    def _nbxmpp(self, name: Literal['Delimiter']) -> Delimiter: ...
    @overload
    def _nbxmpp(self, name: Literal['Discovery']) -> Discovery: ...
    @overload
    def _nbxmpp(self, name: Literal['EME']) -> EME: ...
    @overload
    def _nbxmpp(self, name: Literal['EntityCaps']) -> EntityCaps: ...
    @overload
    def _nbxmpp(self, name: Literal['EntityTime']) -> EntityTime: ...
    @overload
    def _nbxmpp(self, name: Literal['HTTPAuth']) -> HTTPAuth: ...
    @overload
    def _nbxmpp(self, name: Literal['HTTPUpload']) -> HTTPUpload: ...
    @overload
    def _nbxmpp(self, name: Literal['IBB']) -> IBB: ...
    @overload
    def _nbxmpp(self, name: Literal['Idle']) -> Idle: ...
    @overload
    def _nbxmpp(self, name: Literal['BaseIq']) -> BaseIq: ...
    @overload
    def _nbxmpp(self, name: Literal['LastActivity']) -> LastActivity: ...
    @overload
    def _nbxmpp(self, name: Literal['Location']) -> Location: ...
    @overload
    def _nbxmpp(self, name: Literal['MAM']) -> MAM: ...
    @overload
    def _nbxmpp(self, name: Literal['BaseMessage']) -> BaseMessage: ...
    @overload
    def _nbxmpp(self, name: Literal['Mood']) -> Mood: ...
    @overload
    def _nbxmpp(self, name: Literal['MUC']) -> MUC: ...
    @overload
    def _nbxmpp(self, name: Literal['Moderation']) ->Moderation : ...
    @overload
    def _nbxmpp(self, name: Literal['Muclumbus']) -> Muclumbus: ...
    @overload
    def _nbxmpp(self, name: Literal['Nickname']) -> Nickname: ...
    @overload
    def _nbxmpp(self, name: Literal['OMEMO']) -> OMEMO: ...
    @overload
    def _nbxmpp(self, name: Literal['OOB']) -> OOB: ...
    @overload
    def _nbxmpp(self, name: Literal['OpenPGP']) -> OpenPGP: ...
    @overload
    def _nbxmpp(self, name: Literal['PGPLegacy']) -> PGPLegacy: ...
    @overload
    def _nbxmpp(self, name: Literal['Ping']) -> Ping: ...
    @overload
    def _nbxmpp(self, name: Literal['BasePresence']) -> BasePresence: ...
    @overload
    def _nbxmpp(self, name: Literal['PubSub']) -> PubSub: ...
    @overload
    def _nbxmpp(self, name: Literal['Reactions']) -> Reactions: ...
    @overload
    def _nbxmpp(self, name: Literal['Receipts']) -> Receipts: ...
    @overload
    def _nbxmpp(self, name: Literal['Register']) -> Register: ...
    @overload
    def _nbxmpp(self, name: Literal['Replies']) -> Replies: ...
    @overload
    def _nbxmpp(self, name: Literal['Roster']) -> Roster: ...
    @overload
    def _nbxmpp(self, name: Literal['SecurityLabels']) -> SecurityLabels: ...
    @overload
    def _nbxmpp(self, name: Literal['SoftwareVersion']) -> SoftwareVersion: ...
    @overload
    def _nbxmpp(self, name: Literal['Tune']) -> Tune: ...
    @overload
    def _nbxmpp(self, name: Literal['UserAvatar']) -> UserAvatar: ...
    @overload
    def _nbxmpp(self, name: Literal['VCard4']) -> VCard4: ...
    @overload
    def _nbxmpp(self, name: Literal['VCardAvatar']) -> VCardAvatar: ...
    @overload
    def _nbxmpp(self, name: Literal['VCardTemp']) -> VCardTemp: ...
    @overload
    def _nbxmpp(self) -> types.Client: ...

    def _nbxmpp(self,
                name: str | None = None
                ) -> Mock | types.Client | BaseModule:

        if not app.account_is_connected(self._client.account):
            self._log.warning('Account not connected, can’t use nbxmpp method')
            return Mock()

        if name is None:
            return self._client.connection

        return self._client.connection.get_module(name)
