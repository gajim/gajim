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

# XEP-0144: Roster Item Exchange

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import helpers
from gajim.common.events import RosterItemExchangeEvent
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule


class RosterItemExchange(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self.received_item,
                          typ='set',
                          ns=Namespace.ROSTERX),
            StanzaHandler(name='message',
                          callback=self.received_item,
                          ns=Namespace.ROSTERX),
        ]

    def received_item(self, _con, stanza, _properties):
        # stanza can be a message or a iq

        self._log.info('Received roster items from %s', stanza.getFrom())

        exchange_items_list = {}
        items_list = stanza.getTag(
            'x', namespace=Namespace.ROSTERX).getChildren()
        if items_list is None:
            raise nbxmpp.NodeProcessed

        action = items_list[0].getAttr('action')
        if not action:
            action = 'add'

        for item in items_list:
            try:
                jid = helpers.parse_jid(item.getAttr('jid'))
            except helpers.InvalidFormat:
                self._log.warning('Invalid JID: %s, ignoring it',
                                  item.getAttr('jid'))
                continue
            name = item.getAttr('name')
            contact = self._get_contact(jid)
            groups = []
            same_groups = True
            for group in item.getTags('group'):
                groups.append(group.getData())
                # check that all suggested groups are in the groups we have for
                # this contact
                if not contact or group not in contact.groups:
                    same_groups = False
            if contact:
                # check that all groups we have for this contact are in the
                # suggested groups
                for group in contact.groups:
                    if group not in groups:
                        same_groups = False
                if contact.sub in ('both', 'to') and same_groups:
                    continue
            exchange_items_list[jid] = [name, groups]

        if not exchange_items_list:
            raise nbxmpp.NodeProcessed

        self._log.info('Items: %s', exchange_items_list)

        app.ged.raise_event(RosterItemExchangeEvent(
            conn=self._con,
            fjid=str(stanza.getFrom()),
            exchange_items_list=exchange_items_list,
            action=action))

        raise nbxmpp.NodeProcessed

    def send_contacts(self, contacts, fjid, type_='message'):
        if not app.account_is_available(self._account):
            return

        if type_ == 'message':
            if len(contacts) == 1:
                msg = _('Sent contact: "%(jid)s" (%(name)s)') % {
                    'jid': contacts[0].jid, 'name': contacts[0].name}
            else:
                msg = _('Sent contacts:')
                for contact in contacts:
                    msg += '\n "%s" (%s)' % (contact.jid, contact.name)
            stanza = nbxmpp.Message(to=app.get_jid_without_resource(fjid),
                                    body=msg)
        elif type_ == 'iq':
            stanza = nbxmpp.Iq(to=fjid, typ='set')
        xdata = stanza.addChild(name='x', namespace=Namespace.ROSTERX)
        for contact in contacts:
            name = contact.name
            xdata.addChild(name='item', attrs={'action': 'add',
                                               'jid': str(contact.jid),
                                               'name': name})
            self._log.info('Send contact: %s %s', contact.jid, name)
        self._con.connection.send(stanza)
