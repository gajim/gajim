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

# Roster

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule


class Roster(BaseModule):

    _nbxmpp_extends = 'Roster'
    _nbxmpp_methods = [
        'delete_item',
        'set_item',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            # StanzaHandler(name='presence',
            #               callback=self._presence_received),
            StanzaHandler(name='iq',
                          callback=self._process_roster_push,
                          typ='set',
                          ns=Namespace.ROSTER),
        ]

        self._roster = {}

    def load_roster(self):
        self._log.info('Load from database')
        roster = app.storage.cache.load_roster(self._account)
        if not roster:
            self._log.info('Database empty, reset roster version')
            app.settings.set_account_setting(
                self._account, 'roster_version', '')
            return

        for jid in roster:
            self._con.get_module('Contacts').add_contact(jid)

        self._roster = roster

    def _store_roster(self):
        app.storage.cache.store_roster(self._account, self._roster)

    def request_roster(self):
        version = app.settings.get_account_setting(self._account,
                                                   'roster_version')

        self._log.info('Request version: %s', version)
        self._nbxmpp('Roster').request_roster(
            version, callback=self._on_request_roster)

    def _on_request_roster(self, task):
        try:
            roster = task.finish()
        except Exception as error:
            self._log.warning(error)
            return

        self._log.info('Received Roster, version: %s', roster.version)

        if roster.version is None or roster.items is not None:
            # version is None:
            # ---------------
            # No Roster versioning supported this
            # means we got the complete roster
            #
            # items is not None:
            # ---------------
            # Roster versioning supported but
            # server opted to send us the whole roster
            self._set_roster_from_data(roster.items)

        app.settings.set_account_setting(self._account,
                                         'roster_version',
                                         roster.version)

        self._con.connect_machine()

    def _set_roster_from_data(self, items):
        self._roster.clear()
        for item in items:
            self._log.info(item)
            self._con.get_module('Contacts').add_contact(item.jid)
            self._roster[item.jid] = item

        self._store_roster()

    def _process_roster_push(self, _con, _stanza, properties):
        self._log.info('Push received')

        item = properties.roster.item
        self._roster[item.jid] = item

        self._store_roster()

        self._log.info('New version: %s', properties.roster.version)
        app.settings.set_account_setting(self._account,
                                         'roster_version',
                                         properties.roster.version)

        app.nec.push_incoming_event(NetworkEvent('roster-info',
                                                 account=self._account,
                                                 item=item))

        raise nbxmpp.NodeProcessed

    def get_item(self, jid):
        return self._roster.get(jid)

    def iter(self):
        for jid, data in self._roster.items():
            yield jid, data

    def iter_contacts(self):
        for jid in self._roster:
            yield self._get_contact(jid)


def get_instance(*args, **kwargs):
    return Roster(*args, **kwargs), 'Roster'
