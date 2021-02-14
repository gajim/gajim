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

from nbxmpp.const import PresenceShow
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.structs import UNKNOWN_PRESENCE
from gajim.common.helpers import Observable
from gajim.common.types import ConnectionT
from gajim.common.modules.base import BaseModule



class Contacts(BaseModule):
    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self._contacts = {}

    def add_contact(self, jid):
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        contact = self._contacts.get(jid)
        if contact is not None:
            return contact

        contact = BareContact(self._log, jid, self._account)
        self._contacts[jid] = contact
        return contact

    def get_contact(self, jid):
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        resource = jid.resource
        jid = jid.new_as_bare()

        contact = self._contacts.get(jid)
        if contact is None:
            contact = self.add_contact(jid)

        if resource is None:
            return contact

        contact = contact.get_resource(resource)
        return contact



class CommonContact(Observable):
    def __init__(self, logger, jid, account):
        Observable.__init__(self, logger)
        self._jid = jid
        self._account = account

    def _module(self, name):
        return app.get_client(self._account).get_module(name)

    @property
    def jid(self):
        return self._jid

    @property
    def account(self):
        return self._account

    @property
    def chatstate(self):
        return self._chatstate

    def update_chatstate(self, value):
        pass


class BareContact(CommonContact):
    def __init__(self, logger, jid, account):
        CommonContact.__init__(self, logger, jid, account)

        self._resources = {}

    def add_resource(self, resource):
        jid = self._jid.new_with(resource=resource)
        contact = ResourceContact(self._log, jid, self._account)
        self._resources[resource] = contact
        contact.connect('presence-update', self._on_signal)
        return contact

    def get_resource(self, resource):
        contact = self._resources.get(resource)
        if contact is None:
            contact = self.add_resource(resource)
        return contact

    def _on_signal(self, _contact, signal_name, *args, **kwargs):
        self.notify(signal_name, *args, **kwargs)

    # @property
    # def groups(self):
    #     return self._module('Roster').get_groups(self._jid)

    @property
    def is_available(self):
        return any([contact.is_available for contact in self._resources.values()])

    @property
    def show(self):
        show_values = [contact.show for contact in self._resources.values()]
        if not show_values:
            return PresenceShow.OFFLINE
        return max(show_values)


class ResourceContact(CommonContact):
    def __init__(self, logger, jid, account):
        CommonContact.__init__(self, logger, jid, account)

        self._presence = UNKNOWN_PRESENCE

    @property
    def is_available(self):
        return self._presence.available

    @property
    def show(self):
        if not self._presence.available:
            return PresenceShow.OFFLINE
        return self._presence.show

    @property
    def status(self):
        return self._presence.status

    @property
    def priority(self):
        return self._presence.priority

    @property
    def idle_time(self):
        return self._presence.idle_time

    def update_presence(self, presence_data):
        self._presence = presence_data
        self.notify('presence-update')


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
