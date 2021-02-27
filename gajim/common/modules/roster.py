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

from collections import namedtuple

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule

RosterItem = namedtuple('RosterItem', 'jid data')


class Roster(BaseModule):

    _nbxmpp_extends = 'Roster'
    _nbxmpp_methods = []

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

    def _store_roster(self):
        app.storage.cache.store_roster(self._account, self._data)

    def request_roster(self):
        version = None
        if self._con.features.has_roster_version:
            version = app.settings.get_account_setting(
                self._account, 'roster_version') or None

        self._log.info('Request version: %s', version)
        self._nbxmpp('Roster').request_roster(
            version, callback=self._on_request_roster)

    def _on_request_roster(self, task):
        try:
            roster = task.finish()
        except Exception as error:
            self._log.warning(error)
            return

        self._roster.clear()

        self._log.info('Received Roster, version: %s', roster.version)
        for item in roster.items:
            self._con.get_module('Contacts').add_contact(item.jid)
            self._roster[item.jid] = item.data

        app.storage.cache.store_roster(self._account, self._roster)
        app.settings.set_account_setting(self._account,
                                         'roster_version',
                                         roster.version)

        self._con.connect_machine()

    def _process_roster_push(self, _con, stanza, _properties):
        return
        # TODO
        self._log.info('Push received')

        sender = stanza.getFrom()
        if sender is not None:
            if not self._con.get_own_jid().bare_match(sender):
                self._log.warning('Wrong JID %s', stanza.getFrom())
                return

        push_items, version = self._parse_push(stanza)

        self._ack_roster_push(stanza)

        for item in push_items:
            attrs = item.data
            app.nec.push_incoming_event(NetworkEvent(
                'roster-info',
                conn=self._con,
                jid=item.jid,
                nickname=attrs['name'],
                sub=attrs['subscription'],
                ask=attrs['ask'],
                groups=attrs['groups'],
                avatar_sha=None))

            self._store_roster()

        self._log.info('New version: %s', version)
        app.settings.set_account_setting(self._account,
                                         'roster_version',
                                         version)

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
