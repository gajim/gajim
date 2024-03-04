# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal
from typing import overload
from typing import TYPE_CHECKING

from gajim.common import modules

if TYPE_CHECKING:
    from gajim.common.modules.adhoc_commands import AdHocCommands
    from gajim.common.modules.annotations import Annotations
    from gajim.common.modules.base import BaseModule
    from gajim.common.modules.bits_of_binary import BitsOfBinary
    from gajim.common.modules.blocking import Blocking
    from gajim.common.modules.bookmarks import Bookmarks
    from gajim.common.modules.bytestream import Bytestream
    from gajim.common.modules.caps import Caps
    from gajim.common.modules.carbons import Carbons
    from gajim.common.modules.chat_markers import ChatMarkers
    from gajim.common.modules.chatstates import Chatstate
    from gajim.common.modules.contacts import Contacts
    from gajim.common.modules.delimiter import Delimiter
    from gajim.common.modules.discovery import Discovery
    from gajim.common.modules.entity_time import EntityTime
    from gajim.common.modules.gateway import Gateway
    from gajim.common.modules.http_auth import HTTPAuth
    from gajim.common.modules.httpupload import HTTPUpload
    from gajim.common.modules.ibb import IBB
    from gajim.common.modules.iq import Iq
    from gajim.common.modules.jingle import Jingle
    from gajim.common.modules.last_activity import LastActivity
    from gajim.common.modules.mam import MAM
    from gajim.common.modules.message import Message
    from gajim.common.modules.muc import MUC
    from gajim.common.modules.omemo import OMEMO
    from gajim.common.modules.pep import PEP
    from gajim.common.modules.ping import Ping
    from gajim.common.modules.presence import Presence
    from gajim.common.modules.pubsub import PubSub
    from gajim.common.modules.receipts import Receipts
    from gajim.common.modules.register import Register
    from gajim.common.modules.roster import Roster
    from gajim.common.modules.roster_item_exchange import RosterItemExchange
    from gajim.common.modules.search import Search
    from gajim.common.modules.security_labels import SecLabels
    from gajim.common.modules.software_version import SoftwareVersion
    from gajim.common.modules.user_avatar import UserAvatar
    from gajim.common.modules.user_location import UserLocation
    from gajim.common.modules.user_nickname import UserNickname
    from gajim.common.modules.user_tune import UserTune
    from gajim.common.modules.vcard4 import VCard4
    from gajim.common.modules.vcard_avatars import VCardAvatars
    from gajim.common.modules.vcard_temp import VCardTemp


class ClientModules:
    def __init__(self, account: str) -> None:
        self._account = account

    @overload
    def get_module(self, name: Literal['AdHocCommands']) -> AdHocCommands: ...
    @overload
    def get_module(self, name: Literal['Annotations']) -> Annotations: ...
    @overload
    def get_module(self, name: Literal['BitsOfBinary']) -> BitsOfBinary: ...
    @overload
    def get_module(self, name: Literal['Blocking']) -> Blocking: ...
    @overload
    def get_module(self, name: Literal['Bookmarks']) -> Bookmarks: ...
    @overload
    def get_module(self, name: Literal['Bytestream']) -> Bytestream: ...
    @overload
    def get_module(self, name: Literal['Caps']) -> Caps: ...
    @overload
    def get_module(self, name: Literal['Carbons']) -> Carbons: ...
    @overload
    def get_module(self, name: Literal['ChatMarkers']) -> ChatMarkers: ...
    @overload
    def get_module(self, name: Literal['Chatstate']) -> Chatstate: ...
    @overload
    def get_module(self, name: Literal['Contacts']) -> Contacts: ...
    @overload
    def get_module(self, name: Literal['Delimiter']) -> Delimiter: ...
    @overload
    def get_module(self, name: Literal['Discovery']) -> Discovery: ...
    @overload
    def get_module(self, name: Literal['EntityTime']) -> EntityTime: ...
    @overload
    def get_module(self, name: Literal['Gateway']) -> Gateway: ...
    @overload
    def get_module(self, name: Literal['HTTPAuth']) -> HTTPAuth: ...
    @overload
    def get_module(self, name: Literal['HTTPUpload']) -> HTTPUpload: ...
    @overload
    def get_module(self, name: Literal['IBB']) -> IBB: ...
    @overload
    def get_module(self, name: Literal['Iq']) -> Iq: ...
    @overload
    def get_module(self, name: Literal['Jingle']) -> Jingle: ...
    @overload
    def get_module(self, name: Literal['LastActivity']) -> LastActivity: ...
    @overload
    def get_module(self, name: Literal['MAM']) -> MAM: ...
    @overload
    def get_module(self, name: Literal['Message']) -> Message: ...
    @overload
    def get_module(self, name: Literal['MUC']) -> MUC: ...
    @overload
    def get_module(self, name: Literal['OMEMO']) -> OMEMO: ...
    @overload
    def get_module(self, name: Literal['PEP']) -> PEP: ...
    @overload
    def get_module(self, name: Literal['Ping']) -> Ping: ...
    @overload
    def get_module(self, name: Literal['Presence']) -> Presence: ...
    @overload
    def get_module(self, name: Literal['PubSub']) -> PubSub: ...
    @overload
    def get_module(self, name: Literal['Receipts']) -> Receipts: ...
    @overload
    def get_module(self, name: Literal['Register']) -> Register: ...
    @overload
    def get_module(self, name: Literal['RosterItemExchange']) -> RosterItemExchange: ...  # noqa: E501
    @overload
    def get_module(self, name: Literal['Roster']) -> Roster: ...
    @overload
    def get_module(self, name: Literal['Search']) -> Search: ...
    @overload
    def get_module(self, name: Literal['SecLabels']) -> SecLabels: ...
    @overload
    def get_module(self, name: Literal['SoftwareVersion']) -> SoftwareVersion: ...  # noqa: E501
    @overload
    def get_module(self, name: Literal['UserAvatar']) -> UserAvatar: ...
    @overload
    def get_module(self, name: Literal['UserLocation']) -> UserLocation: ...
    @overload
    def get_module(self, name: Literal['UserNickname']) -> UserNickname: ...
    @overload
    def get_module(self, name: Literal['UserTune']) -> UserTune: ...
    @overload
    def get_module(self, name: Literal['VCardAvatars']) -> VCardAvatars: ...
    @overload
    def get_module(self, name: Literal['VCardTemp']) -> VCardTemp: ...
    @overload
    def get_module(self, name: Literal['VCard4']) -> VCard4: ...

    def get_module(self, name: str) -> BaseModule:
        return modules.get(self._account, name)
