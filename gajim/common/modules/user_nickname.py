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

# XEP-0172: User Nickname

from typing import Any
from typing import Tuple

import logging

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node

log = logging.getLogger('gajim.c.m.user_nickname')


class UserNickname(BaseModule):

    _nbxmpp_extends = 'Nickname'
    _nbxmpp_methods = [
        'set_nickname',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._nickname_received)

    @event_node(nbxmpp.NS_NICK)
    def _nickname_received(self, _con, _stanza, properties):
        nick = properties.pubsub_event.data
        if properties.self_message:
            if nick is None:
                nick = app.config.get_per('accounts', self._account, 'name')
            app.nicks[self._account] = nick

        for contact in app.contacts.get_contacts(self._account,
                                                 str(properties.jid)):
            contact.contact_name = nick

        app.nec.push_incoming_event(
            NetworkEvent('nickname-received',
                         account=self._account,
                         jid=properties.jid.getBare(),
                         nickname=nick))


def parse_nickname(stanza: nbxmpp.Node) -> str:
    nick = stanza.getTag('nick', namespace=nbxmpp.NS_NICK)
    if nick is None:
        return ''
    return nick.getData()


def get_instance(*args: Any, **kwargs: Any) -> Tuple[UserNickname, str]:
    return UserNickname(*args, **kwargs), 'UserNickname'
