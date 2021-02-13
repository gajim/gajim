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

from typing import Any
from typing import Dict  # pylint: disable=unused-import
from typing import Tuple

from gajim.common.helpers import Observable

from gajim.common.types import ConnectionT
from gajim.common.modules.base import BaseModule


class Contacts(BaseModule):
    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self._contacts = {}

    def add_contact(self, jid):
        contact = Contact(jid, self._account)
        self._contacts[jid] = contact


class CommonContact(Observable):
    def __init__(self, jid, account):
        Observable.__init__(self)
        self._jid = jid
        self._account = account

        self._show = None
        self._status = None
        self._priority = 0
        self._idle_time = None
        self._is_available = False
        self._chatstate = None

    def _module(self, name):
        return self.get_client(self._account).get_module(name)

    def emit_changed(name):
        self.notify(name, self)

    @property
    def jid(self):
        return self._jid

    @property
    def account(self):
        return self._account

    @property
    def is_available(self):
        return self._is_available

    @property
    def show(self):
        if not self._is_available:
            return 'offline'
        return self._show.value

    @property
    def status(self):
        return self._status

    @property
    def priority(self):
        return self._priority
    
    @property
    def idle_time(self):
        return self._idle_time

    @property
    def chatstate(self):
        return self._chatstate

    def update_chatstate(self, value):
        pass

    def update_from_presence(self, properties):
        self._is_available = properties.type.is_available
        if not self._is_available:
            self._chatstate = None
        self._show = properties.show
        self._status = properties.status
        self._priority = properties.priority
        self._idle_time = properties.idle_timestamp
        self.notify('presence-update')


class Contact(CommonContact):
    def __init__(self, jid, account):
        CommonContact.__init__(self, jid, account)
        self._show = None

    @property
    def show(self):
        return self._show

    @property
    def presence(self):
        pass

    @property
    def groups(self):
        return self._module('Roster').get_groups(self._jid)
    


account=self._account,
                    name=item['name'],
                    groups=item['groups'],
                    show='offline',
                    sub=item['subscription'],
                    ask=item['ask'],
                    avatar_sha=item['avatar_sha'])



class Groupchat(CommonContact):
    def __init__(self, jid, account):
        CommonContact.__init__(self, jid, account)
        self.jid = jid
        self.account = account


class GroupchatParticipant(CommonContact):
    def __init__(self, jid, account):
        CommonContact.__init__(self, jid, account)
        self.jid = jid
        self.account = account


def get_instance(*args: Any, **kwargs: Any) -> Tuple[Contacts, str]:
    return Contacts(*args, **kwargs), 'Contacts'
