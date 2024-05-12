# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import NamedTuple
from typing import TypeVar

import dataclasses
from dataclasses import dataclass
from dataclasses import fields
from datetime import datetime

from gi.repository import GLib
from nbxmpp.const import Affiliation
from nbxmpp.const import PresenceShow
from nbxmpp.const import Role
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.security_labels import SecurityLabel
from nbxmpp.protocol import JID
from nbxmpp.structs import EncryptionData
from nbxmpp.structs import MucSubject
from nbxmpp.structs import PresenceProperties
from nbxmpp.util import generate_id

from gajim.common import types
from gajim.common.const import MUCJoinedState
from gajim.common.const import PresenceShowExt
from gajim.common.const import URIType
from gajim.common.storage.archive.const import MessageType
from gajim.common.util.datetime import convert_epoch_to_local_datetime
from gajim.common.util.datetime import utc_now

_T = TypeVar('_T')


class URI(NamedTuple):
    type: URIType
    source: str
    query_type: str = ''
    query_params: dict[str, str] = {}
    data: dict[str, str] = {}


class MUCData:
    def __init__(self,
                 room_jid: str,
                 nick: str,
                 occupant_id: str | None,
                 password: str | None,
                 config: dict[str, Any] | None = None
                 ) -> None:

        self._room_jid = JID.from_string(room_jid)
        self._config = config
        self.nick = nick
        self.password = password
        self.occupant_id = occupant_id
        self.state = MUCJoinedState.NOT_JOINED
        # Message id of the captcha challenge
        self.captcha_id: str | None = None
        self.captcha_form: SimpleDataForm | None = None
        self.error: str | None = None
        self.error_text: str | None = None
        self.subject: MucSubject | None = None
        self.last_subject_timestamp: float | None = None

    @property
    def jid(self) -> JID:
        return self._room_jid

    @property
    def occupant_jid(self) -> JID:
        return self._room_jid.new_with(resource=self.nick)

    @property
    def config(self) -> dict[str, Any] | None:
        return self._config


@dataclass(slots=True)
class OutgoingMessage:
    account: str
    contact: types.ChatContactT
    text: dataclasses.InitVar[str | None] = None
    chatstate: str | None = None
    marker: tuple[str, str] | None = None
    sec_label: SecurityLabel | None = None
    control: Any | None = None
    correct_id: str | None = None
    reply_data: ReplyData | None = None
    oob_url: str | None = None
    play_sound: bool = True

    type: MessageType = dataclasses.field(init=False)
    message_id: str = dataclasses.field(init=False)
    timestamp: datetime = dataclasses.field(init=False)

    _text: str | None = dataclasses.field(init=False)
    _encryption_data: EncryptionData | None = dataclasses.field(
        init=False, default=None)
    _stanza: Any = dataclasses.field(init=False, default=None)

    def __post_init__(self, text: str | None) -> None:
        self._text = text
        self.timestamp = utc_now()
        self.message_id = generate_id()
        self.type = MessageType.from_str(self.contact.type_string)

    @property
    def is_groupchat(self) -> bool:
        return self.type == MessageType.GROUPCHAT

    @property
    def is_pm(self) -> bool:
        return self.type == MessageType.CHAT

    def get_text(self, with_fallback: bool = True) -> str | None:
        if not with_fallback:
            return self._text

        if self.reply_data is None:
            return self._text
        assert self._text is not None
        return f'{self.reply_data.fallback_text}{self._text}'

    def has_text(self) -> bool:
        return bool(self._text)

    def set_encryption(self, data: EncryptionData) -> None:
        self._encryption_data = data

    def get_encryption(self) -> EncryptionData | None:
        return self._encryption_data

    @property
    def is_encrypted(self) -> bool:
        return self._encryption_data is not None

    def set_stanza(self, stanza: Any) -> None:
        self._stanza = stanza

    def get_stanza(self) -> Any:
        return self._stanza


@dataclass(frozen=True)
class PresenceData:
    show: PresenceShow
    status: str
    priority: int
    idle_datetime: datetime | None
    available: bool

    @classmethod
    def from_presence(cls, properties: PresenceProperties) -> PresenceData:
        idle_datetime = None
        if properties.idle_timestamp is not None:
            idle_datetime = convert_epoch_to_local_datetime(
                properties.idle_timestamp)

        return cls(show=properties.show,
                   status=properties.status,
                   priority=properties.priority,
                   idle_datetime=idle_datetime,
                   available=properties.type.is_available)


UNKNOWN_PRESENCE = PresenceData(show=PresenceShowExt.OFFLINE,
                                status='',
                                priority=0,
                                idle_datetime=None,
                                available=False)


@dataclass(frozen=True)
class MUCPresenceData:
    show: PresenceShow
    status: str
    idle_datetime: datetime | None
    available: bool
    affiliation: Affiliation
    role: Role
    real_jid: JID | None
    occupant_id: str | None

    @classmethod
    def from_presence(cls,
                      properties: PresenceProperties,
                      occupant_id: str | None
                      ) -> MUCPresenceData:

        idle_datetime = None
        if properties.idle_timestamp is not None:
            idle_datetime = convert_epoch_to_local_datetime(
                properties.idle_timestamp)

        return cls(show=properties.show,
                   status=properties.status,
                   idle_datetime=idle_datetime,
                   available=properties.type.is_available,
                   affiliation=properties.muc_user.affiliation,
                   role=properties.muc_user.role,
                   real_jid=properties.muc_user.jid,
                   occupant_id=occupant_id)


UNKNOWN_MUC_PRESENCE = MUCPresenceData(show=PresenceShowExt.OFFLINE,
                                       status='',
                                       idle_datetime=None,
                                       available=False,
                                       affiliation=Affiliation.NONE,
                                       role=Role.NONE,
                                       real_jid=None,
                                       occupant_id=None)


class VariantMixin:

    _type_to_variant_funcs = {
        JID: str,
    }

    _variant_to_type_funcs = {
        'JID': JID.from_string,
    }

    def _get_type_and_variant_string(self,
                                     field_type: str) -> tuple[type[Any], str]:
        variant_str = ''
        if 'Optional' in field_type:
            variant_str = 'm'

        if 'str' in field_type:
            return str, f'{variant_str}s'

        if 'int' in field_type:
            return int, f'{variant_str}i'

        if 'bool' in field_type:
            return bool, f'{variant_str}b'

        if 'JID' in field_type:
            return JID, f'{variant_str}s'

        raise ValueError(f'unknown type: {field_type}')

    def to_variant(self) -> GLib.Variant:
        __types = {}
        vdict = {}
        for field in fields(self):
            value = getattr(self, field.name)
            field_t, variant_str = self._get_type_and_variant_string(field.type)
            if value is None:
                vdict[field.name] = GLib.Variant(variant_str, value)
                continue

            if not isinstance(value, field_t):
                raise ValueError(f'invalid type: {value} is not a {field_t}')

            conversion_func = self._type_to_variant_funcs.get(field_t)
            if conversion_func is not None:
                value = conversion_func(value)
                __types[field.name] = field_t.__name__

            vdict[field.name] = GLib.Variant(variant_str, value)

        if __types:
            vdict['__types'] = GLib.Variant('a{ss}', __types)
        return GLib.Variant('a{sv}', vdict)

    @classmethod
    def from_variant(cls: type[_T], variant: GLib.Variant) -> _T:
        vdict = variant.unpack()
        __types = vdict.pop('__types', None)
        if __types is not None:
            for field_name, value_t_name in __types.items():
                value = vdict[field_name]
                conversion_func = cls._variant_to_type_funcs.get(value_t_name)
                if conversion_func is None:
                    raise ValueError(f'no conversion for: {value_t_name}')
                vdict[field_name] = conversion_func(value)
        return cls(**vdict)


@dataclass
class ReplyData:
    pk: int
    to: JID
    id: str
    fallback_start: int
    fallback_end: int
    fallback_text: str
