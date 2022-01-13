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
from typing import Dict
from typing import Type
from typing import TypeVar
from typing import NamedTuple
from typing import Optional
from typing import Union

import time
from dataclasses import dataclass
from dataclasses import fields

from gi.repository import GLib

from nbxmpp.protocol import JID
from nbxmpp.const import Role
from nbxmpp.const import Affiliation
from nbxmpp.const import PresenceShow

from gajim.common.const import MUCJoinedState
from gajim.common.const import KindConstant
from gajim.common.const import PresenceShowExt
from gajim.common.const import URIType
from gajim.common.const import URIAction


_T = TypeVar('_T')


class URI(NamedTuple):
    type: URIType
    action: Optional[URIAction] = None
    data: Optional[Union[Dict[str, str], str]] = None


class MUCData:
    def __init__(self,
                 room_jid: str,
                 nick: str,
                 password: str,
                 config=None) -> None:

        self._room_jid = JID.from_string(room_jid)
        self._config = config
        self.nick = nick
        self.password = password
        self.state = MUCJoinedState.NOT_JOINED
        # Message id of the captcha challenge
        self.captcha_id = None
        self.subject = None

    @property
    def jid(self) -> JID:
        return self._room_jid

    @property
    def occupant_jid(self) -> JID:
        return self._room_jid.new_with(resource=self.nick)

    @property
    def config(self):
        return self._config


class OutgoingMessage:
    def __init__(self,
                 account: str,
                 contact,
                 message: Optional[str],
                 type_: str,
                 subject: Optional[str] = None,
                 chatstate=None,
                 marker: Optional[tuple[str, str]] = None,
                 resource: Optional[str] = None,
                 user_nick: Optional[str] = None,
                 label: Optional[str] = None,
                 control=None,
                 attention: Optional[bool] = None,
                 correct_id: Optional[str] = None,
                 oob_url: Optional[str] = None,
                 xhtml=None,
                 nodes=None,
                 play_sound: bool = True):

        if type_ not in ('chat', 'groupchat', 'normal', 'headline'):
            raise ValueError('Unknown message type: %s' % type_)

        if not message and chatstate is None and marker is None:
            raise ValueError('Trying to send message without content')

        self.account = account
        self.contact = contact
        self.message = message
        self.type_ = type_

        if type_ == 'chat':
            self.kind = KindConstant.CHAT_MSG_SENT
        elif type_ == 'groupchat':
            self.kind = KindConstant.GC_MSG
        elif type_ == 'normal':
            self.kind = KindConstant.SINGLE_MSG_SENT
        else:
            raise ValueError('Unknown message type')

        from gajim.common.helpers import AdditionalDataDict
        self.additional_data = AdditionalDataDict()

        self.subject = subject
        self.chatstate = chatstate
        self.marker = marker
        self.resource = resource
        self.user_nick = user_nick
        self.label = label
        self.control = control
        self.attention = attention
        self.correct_id = correct_id

        self.oob_url = oob_url

        if oob_url is not None:
            self.additional_data.set_value('gajim', 'oob_url', oob_url)

        self.xhtml = xhtml

        if xhtml is not None:
            self.additional_data.set_value('gajim', 'xhtml', xhtml)

        self.nodes = nodes
        self.play_sound = play_sound

        self.timestamp = None
        self.message_id = None
        self.stanza = None
        self.session = None
        self.delayed = None # TODO never set

        self.is_loggable = True

    def copy(self):
        message = OutgoingMessage(self.account,
                                  self.contact,
                                  self.message,
                                  self.type_)
        for name, value in vars(self).items():
            setattr(message, name, value)
        message.additional_data = self.additional_data.copy()
        return message

    @property
    def jid(self) -> JID:
        return self.contact.jid

    @property
    def is_groupchat(self) -> bool:
        return self.type_ == 'groupchat'

    @property
    def is_chat(self) -> bool:
        return self.type_ == 'chat'

    @property
    def is_normal(self) -> bool:
        return self.type_ == 'normal'

    def set_sent_timestamp(self) -> None:
        if self.is_groupchat:
            return
        self.timestamp = time.time()

    @property
    def is_encrypted(self) -> bool:
        return bool(self.additional_data.get_value('encrypted', 'name', False))

    @property
    def msg_iq(self) -> Any:
        # Backwards compatibility for plugins
        return self.stanza

    @msg_iq.setter
    def msg_iq(self, value: Any) -> None:
        # Backwards compatibility for plugins
        self.stanza = value


@dataclass(frozen=True)
class PresenceData:
    show: str
    status: str
    priority: int
    idle_time: Optional[float]
    available: bool

    @classmethod
    def from_presence(cls, properties):
        return cls(show=properties.show,
                   status=properties.status,
                   priority=properties.priority,
                   idle_time=properties.idle_timestamp,
                   available=properties.type.is_available)


UNKNOWN_PRESENCE = PresenceData(show=PresenceShowExt.OFFLINE,
                                status='',
                                priority=0,
                                idle_time=0,
                                available=False)


@dataclass(frozen=True)
class MUCPresenceData:
    show: PresenceShow
    status: str
    idle_time: Optional[float]
    available: bool
    affiliation: Affiliation
    role: Role
    real_jid: Optional[JID]

    @classmethod
    def from_presence(cls, properties):
        return cls(show=properties.show,
                   status=properties.status,
                   idle_time=properties.idle_timestamp,
                   available=properties.type.is_available,
                   affiliation=properties.muc_user.affiliation,
                   role=properties.muc_user.role,
                   real_jid=properties.muc_user.jid)


UNKNOWN_MUC_PRESENCE = MUCPresenceData(show=PresenceShowExt.OFFLINE,
                                       status='',
                                       idle_time=0,
                                       available=False,
                                       affiliation=Affiliation.NONE,
                                       role=Role.NONE,
                                       real_jid=None)


class VariantMixin:

    _type_to_variant_funcs = {
        JID: str,
    }

    _variant_to_type_funcs = {
        'JID': JID.from_string,
    }

    def _get_type_and_variant_string(self,
                                     field_type: str) -> tuple[Type[Any], str]:
        variant_str = ''
        if 'Optional' in field_type:
            variant_str = 'm'

        if 'str' in field_type:
            return str, f'{variant_str}s'

        if 'int' in field_type:
            return str, f'{variant_str}i'

        if 'bool' in field_type:
            return bool, f'{variant_str}b'

        if 'JID' in field_type:
            return JID, f'{variant_str}s'

        raise ValueError('unknown type: %s' % field_type)

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
                raise ValueError('invalid type: %s is not a %s' % (value,
                                                                   field_t))

            conversion_func = self._type_to_variant_funcs.get(field_t)
            if conversion_func is not None:
                value = conversion_func(value)
                __types[field.name] = field_t.__name__

            vdict[field.name] = GLib.Variant(variant_str, value)

        if __types:
            vdict['__types'] = GLib.Variant('a{ss}', __types)
        return GLib.Variant('a{sv}', vdict)

    @classmethod
    def from_variant(cls: Type[_T], variant: GLib.Variant) -> _T:
        vdict = variant.unpack()
        __types = vdict.pop('__types', None)
        if __types is not None:
            for field_name, value_t_name in __types.items():
                value = vdict[field_name]
                conversion_func = cls._variant_to_type_funcs.get(value_t_name)
                if conversion_func is None:
                    raise ValueError('no conversion for: %s' % value_t_name)
                vdict[field_name] = conversion_func(value)
        return cls(**vdict)
