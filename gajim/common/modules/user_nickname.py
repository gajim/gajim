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

# XEP-0172: User Nickname

from typing import Any
from typing import List  # pylint: disable=unused-import
from typing import Optional
from typing import Tuple

import logging

import nbxmpp

from gajim.common import app
from gajim.common.const import PEPEventType
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule, AbstractPEPData
from gajim.common.types import ConnectionT

log = logging.getLogger('gajim.c.m.user_nickname')


class UserNicknameData(AbstractPEPData):

    type_ = PEPEventType.NICKNAME

    def __init__(self, nickname: Optional[str]) -> None:
        self.data = nickname

    def get_nick(self) -> str:
        return self.data or ''


class UserNickname(AbstractPEPModule):

    name = 'nick'
    namespace = nbxmpp.NS_NICK
    pep_class = UserNicknameData
    store_publish = True
    _log = log

    def __init__(self, con: ConnectionT) -> None:
        AbstractPEPModule.__init__(self, con, con.name)

        self.handlers = []  # type: List[Tuple[Any, ...]]

    def _extract_info(self, item: nbxmpp.Node) -> Optional[str]:
        nick = ''
        child = item.getTag('nick', namespace=nbxmpp.NS_NICK)
        if child is None:
            raise StanzaMalformed('No nick node')
        nick = child.getData()

        return nick or None

    def _build_node(self, data: Optional[str]) -> Optional[nbxmpp.Node]:
        item = nbxmpp.Node('nick', {'xmlns': nbxmpp.NS_NICK})
        if data is None:
            return None
        item.addData(data)
        return item

    def _notification_received(self,
                               jid: nbxmpp.JID,
                               user_pep: UserNicknameData) -> None:
        for contact in app.contacts.get_contacts(self._account, str(jid)):
            contact.contact_name = user_pep.get_nick()

        if jid == self._con.get_own_jid().getStripped():
            if user_pep:
                app.nicks[self._account] = user_pep.get_nick()
            else:
                app.nicks[self._account] = app.config.get_per(
                    'accounts', self._account, 'name')


def parse_nickname(stanza: nbxmpp.Node) -> str:
    nick = stanza.getTag('nick', namespace=nbxmpp.NS_NICK)
    if nick is None:
        return ''
    return nick.getData()


def get_instance(*args: Any, **kwargs: Any) -> Tuple[UserNickname, str]:
    return UserNickname(*args, **kwargs), 'UserNickname'
