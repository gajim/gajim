# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import cast
from typing import Literal
from typing import TYPE_CHECKING
from typing import TypedDict

import logging

from nbxmpp.structs import StanzaHandler

from gajim.common import app
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
from gajim.common.modules.moderations import Moderations
from gajim.common.modules.muc import MUC
from gajim.common.modules.omemo import OMEMO
from gajim.common.modules.pep import PEP
from gajim.common.modules.ping import Ping
from gajim.common.modules.presence import Presence
from gajim.common.modules.pubsub import PubSub
from gajim.common.modules.reactions import Reactions
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

if TYPE_CHECKING:
    from gajim.common.types import Client

ModulesT = (
    AdHocCommands
    | Annotations
    | BitsOfBinary
    | Blocking
    | Bookmarks
    | Bytestream
    | Caps
    | Carbons
    | ChatMarkers
    | Chatstate
    | Contacts
    | Discovery
    | EntityTime
    | Gateway
    | HTTPAuth
    | HTTPUpload
    | IBB
    | Iq
    | Jingle
    | LastActivity
    | MAM
    | Message
    | Moderations
    | MUC
    | OMEMO
    | PEP
    | Ping
    | Presence
    | PubSub
    | Reactions
    | Receipts
    | Register
    | Roster
    | RosterItemExchange
    | Search
    | SecLabels
    | SoftwareVersion
    | UserAvatar
    | UserLocation
    | UserNickname
    | UserTune
    | VCard4
    | VCardAvatars
    | VCardTemp
)

ModulesLiteralT = Literal[
    'AdHocCommands',
    'Annotations',
    'BitsOfBinary',
    'Blocking',
    'Bookmarks',
    'Bytestream',
    'Caps',
    'Carbons',
    'ChatMarkers',
    'Chatstate',
    'Contacts',
    'Discovery',
    'EntityTime',
    'Gateway',
    'HTTPAuth',
    'HTTPUpload',
    'IBB',
    'Iq',
    'Jingle',
    'LastActivity',
    'MAM',
    'Message',
    'Moderations',
    'MUC',
    'OMEMO',
    'PEP',
    'Ping',
    'Presence',
    'PubSub',
    'Reactions',
    'Receipts',
    'Register',
    'Roster',
    'RosterItemExchange',
    'Search',
    'SecLabels',
    'SoftwareVersion',
    'UserAvatar',
    'UserLocation',
    'UserNickname',
    'UserTune',
    'VCard4',
    'VCardAvatars',
    'VCardTemp',
]

class ModuleDict(TypedDict):
    AdHocCommands: AdHocCommands
    Annotations: Annotations
    BitsOfBinary: BitsOfBinary
    Blocking: Blocking
    Bookmarks: Bookmarks
    Bytestream: Bytestream
    Caps: Caps
    Carbons: Carbons
    ChatMarkers: ChatMarkers
    Chatstate: Chatstate
    Contacts: Contacts
    Discovery: Discovery
    EntityTime: EntityTime
    Gateway: Gateway
    HTTPAuth: HTTPAuth
    HTTPUpload: HTTPUpload
    IBB: IBB
    Iq: Iq
    Jingle: Jingle
    LastActivity: LastActivity
    MAM: MAM
    Message: Message
    Moderations: Moderations
    MUC: MUC
    OMEMO: OMEMO
    PEP: PEP
    Ping: Ping
    Presence: Presence
    PubSub: PubSub
    Reactions: Reactions
    Receipts: Receipts
    Register: Register
    Roster: Roster
    RosterItemExchange: RosterItemExchange
    Search: Search
    SecLabels: SecLabels
    SoftwareVersion: SoftwareVersion
    UserAvatar: UserAvatar
    UserLocation: UserLocation
    UserNickname: UserNickname
    UserTune: UserTune
    VCard4: VCard4
    VCardAvatars: VCardAvatars
    VCardTemp: VCardTemp


_modules: dict[str, ModuleDict] = {}
_store_publish_modules = (
    'UserLocation',
    'UserTune',
)


log = logging.getLogger('gajim.c.m')


def register_modules(client: 'Client') -> None:
    if client.account in _modules:
        return

    _modules[client.account] = {}  # pyright: ignore

    for name, module_cls in ModuleDict.__annotations__.items():
        _modules[client.account][name] = module_cls.get_instance(client)


def register_single_module(client: 'Client',
                           instance: BaseModule,
                           name: str) -> None:

    if client.account not in _modules:
        raise ValueError('Unknown account name: %s' % client.account)
    _modules[client.account][name] = instance


def unregister_modules(client: 'Client') -> None:
    for instance in _modules[client.account].values():
        instance = cast(ModulesT, instance)
        if hasattr(instance, 'cleanup'):
            instance.cleanup()
        app.check_finalize(instance)
    del _modules[client.account]


def unregister_single_module(client: 'Client', name: str) -> None:
    if client.account not in _modules:
        return
    if name not in _modules[client.account]:
        return
    del _modules[client.account][name]


def send_stored_publish(account: str) -> None:
    for name in _store_publish_modules:
        _modules[account][name].send_stored_publish()


def get_module(account: str, name: ModulesLiteralT) -> ModulesT:
    return _modules[account][name]


def get_handlers(client: 'Client') -> list[StanzaHandler]:
    handlers: list[StanzaHandler] = []
    for module in _modules[client.account].values():
        module = cast(ModulesT, module)
        handlers += module.handlers
    return handlers
