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

import time
from collections import namedtuple
from dataclasses import dataclass

from nbxmpp.protocol import JID

from gajim.common.const import MUCJoinedState
from gajim.common.const import KindConstant

URI = namedtuple('URI', 'type action data')
URI.__new__.__defaults__ = (None, None)  # type: ignore


class MUCData:
    def __init__(self, room_jid, nick, password, config=None):
        self._room_jid = JID.from_string(room_jid)
        self._config = config
        self.nick = nick
        self.password = password
        self.state = MUCJoinedState.NOT_JOINED
        # Message id of the captcha challenge
        self.captcha_id = None

    @property
    def jid(self):
        return self._room_jid

    @property
    def occupant_jid(self):
        return self._room_jid.new_with(resource=self.nick)

    @property
    def config(self):
        return self._config


class OutgoingMessage:
    def __init__(self,
                 account,
                 contact,
                 message,
                 type_,
                 subject=None,
                 chatstate=None,
                 marker=None,
                 resource=None,
                 user_nick=None,
                 label=None,
                 control=None,
                 attention=None,
                 correct_id=None,
                 oob_url=None,
                 xhtml=None,
                 nodes=None,
                 play_sound=True):

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
    def jid(self):
        return self.contact.jid

    @property
    def is_groupchat(self):
        return self.type_ == 'groupchat'

    @property
    def is_chat(self):
        return self.type_ == 'chat'

    @property
    def is_normal(self):
        return self.type_ == 'normal'

    def set_sent_timestamp(self):
        if self.is_groupchat:
            return
        self.timestamp = time.time()

    @property
    def is_encrypted(self):
        return bool(self.additional_data.get_value('encrypted', 'name', False))

    @property
    def msg_iq(self):
        # Backwards compatibility for plugins
        return self.stanza

    @msg_iq.setter
    def msg_iq(self, value):
        # Backwards compatibility for plugins
        self.stanza = value


@dataclass(frozen=True)
class PresenceData:
    show: str
    status: str
    priority: int
    idle_time: str
    available: bool

    @classmethod
    def from_presence(cls, properties):
        return cls(show=properties.show,
                   status=properties.status,
                   priority=properties.priority,
                   idle_time=properties.idle_timestamp,
                   available=properties.type.is_available)


UNKNOWN_PRESENCE = PresenceData(show=None,
                                status='',
                                priority=0,
                                idle_time=0,
                                available=False)
