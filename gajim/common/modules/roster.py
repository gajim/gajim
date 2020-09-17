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
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._roster_push_received,
                          typ='set',
                          ns=Namespace.ROSTER),
            StanzaHandler(name='presence',
                          callback=self._presence_received),
        ]

        self._data = {}
        self._set = None

    def load_roster(self):
        self._log.info('Load from database')
        data = app.storage.cache.load_roster(self._account)
        if data:
            self.set_raw(data)
            for jid, item in self._data.items():
                self._log.debug('%s: %s', jid, item)
                app.nec.push_incoming_event(NetworkEvent(
                    'roster-info',
                    conn=self._con,
                    jid=jid,
                    nickname=item['name'],
                    sub=item['subscription'],
                    ask=item['ask'],
                    groups=item['groups'],
                    avatar_sha=item['avatar_sha']))
        else:
            self._log.info('Database empty, reset roster version')
            app.settings.set_account_setting(
                self._account, 'roster_version', '')

        app.nec.push_incoming_event(NetworkEvent(
            'roster-received',
            conn=self._con,
            roster=self._data.copy(),
            received_from_server=False))

    def _store_roster(self):
        app.storage.cache.store_roster(self._account, self._data)

    def request_roster(self):
        version = None
        features = self._con.connection.features
        if features.has_roster_version:
            version = app.settings.get_account_setting(self._account,
                                                       'roster_version')

        self._log.info('Requested from server')
        iq = nbxmpp.Iq('get', Namespace.ROSTER)
        if version is not None:
            iq.setTagAttr('query', 'ver', version)
        self._log.info('Request version: %s', version)
        self._con.connection.SendAndCallForResponse(
            iq, self._roster_received)

    def _roster_received(self, _nbxmpp_client, stanza):
        if not nbxmpp.isResultNode(stanza):
            self._log.warning('Unable to retrieve roster: %s',
                              stanza.getError())
        else:
            self._log.info('Received Roster')
            received_from_server = False
            if stanza.getTag('query') is not None:
                # clear Roster
                self._data = {}
                version = self._parse_roster(stanza)

                self._log.info('New version: %s', version)
                self._store_roster()
                app.settings.set_account_setting(self._account,
                                                 'roster_version',
                                                 version)

                received_from_server = True

            app.nec.push_incoming_event(NetworkEvent(
                'roster-received',
                conn=self._con,
                roster=self._data.copy(),
                received_from_server=received_from_server))

        self._con.connect_machine()

    def _roster_push_received(self, _con, stanza, _properties):
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

    def _parse_roster(self, stanza):
        query = stanza.getTag('query')
        version = query.getAttr('ver')

        for item in query.getTags('item'):
            jid = item.getAttr('jid')
            self._data[jid] = self._get_item_attrs(item)
            self._log.info('Item %s: %s', jid, self._data[jid])
        return version

    @staticmethod
    def _get_item_attrs(item, update=False):
        '''
        update: True
            Omit avatar_sha from the returned attrs

        update: False
            Include the default value from avatar_sha in the returned attrs
        '''

        default_attrs = {'name': None,
                         'ask': None,
                         'subscription': None,
                         'groups': []}

        if not update:
            default_attrs['avatar_sha'] = None

        attrs = item.getAttrs()
        del attrs['jid']
        groups = {group.getData() for group in item.getTags('group')}
        attrs['groups'] = list(groups)

        default_attrs.update(attrs)
        return default_attrs

    def _parse_push(self, stanza):
        query = stanza.getTag('query')
        version = query.getAttr('ver')
        push_items = []

        for item in query.getTags('item'):
            push_items.append(self._update_roster_item(item))
        for item in push_items:
            self._log.info('Push: %s', item)
        return push_items, version

    def _update_roster_item(self, item):
        jid = item.getAttr('jid')

        if item.getAttr('subscription') == 'remove':
            self._data.pop(jid, None)
            attrs = self._get_item_attrs(item)
            return RosterItem(jid, attrs)

        if jid not in self._data:
            self._data[jid] = self._get_item_attrs(item)
        else:
            self._data[jid].update(self._get_item_attrs(item, update=True))

        return RosterItem(jid, self._data[jid])

    def _ack_roster_push(self, stanza):
        iq = nbxmpp.Iq('result',
                       to=stanza.getFrom(),
                       frm=stanza.getTo(),
                       attrs={'id': stanza.getID()})
        self._con.connection.send(iq)

    def _presence_received(self, _con, pres, _properties):
        '''
        Add contacts that request subscription to our internal
        roster and also to the database. The contact is put into the
        'Not in contact list' group and because we save it to the database
        it is also after a restart available.
        '''

        if pres.getType() != 'subscribe':
            return

        jid = pres.getFrom().bare

        if jid in self._data:
            return

        self._log.info('Add Contact from presence %s', jid)
        self._data[jid] = {'name': None,
                           'ask': None,
                           'subscription':
                           'none',
                           'groups': ['Not in contact list']}

        self._store_roster()

    def _get_item_data(self, jid, dataname):
        """
        Return specific jid's representation in internal format.
        """
        jid = jid[:(jid + '/').find('/')]
        return self._data[jid][dataname]

    def del_item(self, jid):
        """
        Delete contact 'jid' from roster
        """
        self._con.connection.send(
            nbxmpp.Iq('set', Namespace.ROSTER, payload=[
                nbxmpp.Node('item', {'jid': jid, 'subscription': 'remove'})]))

    def get_groups(self, jid):
        """
        Return groups list that contact 'jid' belongs to
        """
        return self._get_item_data(jid, 'groups')

    def get_name(self, jid):
        """
        Return name of contact 'jid'
        """
        return self._get_item_data(jid, 'name')

    def update_contact(self, jid, name, groups):
        if app.account_is_available(self._account):
            self.set_item(jid=jid, name=name, groups=groups)

    def update_contacts(self, contacts):
        """
        Update multiple roster items
        """
        if app.account_is_available(self._account):
            self.set_item_multi(contacts)

    def set_item(self, jid, name=None, groups=None):
        """
        Rename contact 'jid' and sets the groups list that it now belongs to
        """
        iq = nbxmpp.Iq('set', Namespace.ROSTER)
        query = iq.getTag('query')
        attrs = {'jid': jid}
        if name:
            attrs['name'] = name
        item = query.setTag('item', attrs)
        if groups is not None:
            for group in groups:
                item.addChild(node=nbxmpp.Node('group', payload=[group]))
        self._con.connection.send(iq)

    def set_item_multi(self, items):
        """
        Rename multiple contacts and sets their group lists
        """
        for i in items:
            iq = nbxmpp.Iq('set', Namespace.ROSTER)
            query = iq.getTag('query')
            attrs = {'jid': i['jid']}
            if i['name']:
                attrs['name'] = i['name']
            item = query.setTag('item', attrs)
            for group in i['groups']:
                item.addChild(node=nbxmpp.Node('group', payload=[group]))
            self._con.connection.send(iq)

    def get_items(self):
        """
        Return list of all [bare] JIDs that the roster is currently tracks
        """
        return list(self._data.keys())

    def keys(self):
        """
        Same as get_items. Provided for the sake of dictionary interface
        """
        return list(self._data.keys())

    def __getitem__(self, item):
        """
        Get the contact in the internal format.
        Raises KeyError if JID 'item' is not in roster
        """
        return self._data[item]

    def get_item(self, item):
        """
        Get the contact in the internal format (or None if JID 'item' is not in
        roster)
        """
        if item in self._data:
            return self._data[item]
        return None

    def unsubscribe(self, jid):
        """
        Ask for removing our subscription for JID 'jid'
        """
        self._con.connection.send(nbxmpp.Presence(jid, 'unsubscribe'))

    def get_raw(self):
        """
        Return the internal data representation of the roster
        """
        return self._data

    def set_raw(self, data):
        """
        Set the internal data representation of the roster
        """
        own_jid = self._con.get_own_jid().bare
        self._data = data
        self._data[own_jid] = {
            'resources': {},
            'name': None,
            'ask': None,
            'subscription': None,
            'groups': None,
            'avatar_sha': None
        }

    def set_avatar_sha(self, jid, sha):
        if jid not in self._data:
            return

        self._data[jid]['avatar_sha'] = sha
        self._store_roster()


def get_instance(*args, **kwargs):
    return Roster(*args, **kwargs), 'Roster'
