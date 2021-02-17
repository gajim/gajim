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

# XEP-0191: Blocking Command

import nbxmpp
from nbxmpp.protocol import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.util import raise_if_error

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


class Blocking(BaseModule):

    _nbxmpp_extends = 'Blocking'
    _nbxmpp_methods = [
        'block',
        'unblock',
        'request_blocking_list',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.blocked = []

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._blocking_push_received,
                          typ='set',
                          ns=Namespace.BLOCKING),
        ]

        self.supported = False

    def pass_disco(self, info):
        if Namespace.BLOCKING not in info.features:
            return

        self.supported = True
        app.nec.push_incoming_event(
            NetworkEvent('feature-discovered',
                         account=self._account,
                         feature=Namespace.BLOCKING))

        self._log.info('Discovered blocking: %s', info.jid)

    @as_task
    def get_blocking_list(self):
        _task = yield

        blocking_list = yield self._nbxmpp('Blocking').request_blocking_list()

        raise_if_error(blocking_list)

        self.blocked = list(blocking_list)
        app.nec.push_incoming_event(NetworkEvent('blocking',
                                                 conn=self._con,
                                                 changed=self.blocked))
        yield blocking_list

    @as_task
    def update_blocking_list(self, block, unblock):
        _task = yield

        if block:
            result = yield self.block(block)
            raise_if_error(result)

        if unblock:
            result = yield self.unblock(unblock)
            raise_if_error(result)

        yield True

    def _blocking_push_received(self, _con, _stanza, properties):
        if not properties.is_blocking:
            return

        changed_list = []

        if properties.blocking.unblock_all:
            self.blocked = []
            for jid in self.blocked:
                self._presence_probe(jid)
            self._log.info('Unblock all Push')

        for jid in properties.blocking.unblock:
            changed_list.append(jid)
            if jid not in self.blocked:
                continue
            self.blocked.remove(jid)
            self._presence_probe(jid)
            self._log.info('Unblock Push: %s', jid)

        for jid in properties.blocking.block:
            if jid in self.blocked:
                continue
            changed_list.append(jid)
            self.blocked.append(jid)
            self._set_contact_offline(str(jid))
            self._log.info('Block Push: %s', jid)

        app.nec.push_incoming_event(NetworkEvent('blocking',
                                                 conn=self._con,
                                                 changed=changed_list))

        raise nbxmpp.NodeProcessed

    def _set_contact_offline(self, jid: str) -> None:
        # TODO
        return
        # contact_list = app.contacts.get_contacts(self._account, jid)
        # for contact in contact_list:
        #     contact.show = 'offline'

    def _presence_probe(self, jid: JID) -> None:
        self._log.info('Presence probe: %s', jid)
        # Send a presence Probe to get the current Status
        probe = nbxmpp.Presence(jid, 'probe', frm=self._con.get_own_jid())
        self._nbxmpp().send(probe)


def get_instance(*args, **kwargs):
    return Blocking(*args, **kwargs), 'Blocking'
