# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0144: Roster Item Exchange

from __future__ import annotations

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import RosterItemExchangeEvent
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule
from gajim.common.util.jid import InvalidFormat
from gajim.common.util.jid import parse_jid


class RosterItemExchange(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self.received_item,
                          typ='set',
                          ns=Namespace.ROSTERX),
            StanzaHandler(name='message',
                          callback=self.received_item,
                          ns=Namespace.ROSTERX,
                          priority=48),
        ]

    def received_item(self,
                      _con: types.xmppClient,
                      stanza: Iq,
                      properties: IqProperties
                      ) -> None:
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
                jid = parse_jid(item.getAttr('jid'))
            except InvalidFormat:
                self._log.warning('Invalid JID: %s, ignoring it',
                                  item.getAttr('jid'))
                continue
            name = item.getAttr('name')
            contact = self._get_contact(JID.from_string(jid))
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
                if contact.subscription in ('both', 'to') and same_groups:
                    continue
            exchange_items_list[jid] = [name, groups]

        if not exchange_items_list:
            return

        self._log.info('Items: %s', exchange_items_list)

        app.ged.raise_event(RosterItemExchangeEvent(
            client=self._con,
            jid=properties.jid,
            exchange_items_list=exchange_items_list,
            action=action))

    def send_contacts(self,
                      contacts: list[types.ChatContactT],
                      fjid: str,
                      type_: str = 'message'
                      ) -> None:
        if not app.account_is_available(self._account):
            return

        if type_ == 'message':
            if len(contacts) == 1:
                msg = _('Sent contact: "%(jid)s" (%(name)s)') % {
                    'jid': contacts[0].jid,
                    'name': contacts[0].name}
            else:
                msg = _('Sent contacts:')
                for contact in contacts:
                    msg += f'\n "{contact.jid}" ({contact.name})'
            stanza = nbxmpp.Message(to=app.get_jid_without_resource(fjid),
                                    body=msg)
        elif type_ == 'iq':
            stanza = nbxmpp.Iq(to=fjid, typ='set')
        else:
            raise ValueError

        xdata = stanza.addChild(name='x', namespace=Namespace.ROSTERX)
        for contact in contacts:
            name = contact.name
            xdata.addChild(name='item', attrs={'action': 'add',
                                               'jid': str(contact.jid),
                                               'name': name})
            self._log.info('Send contact: %s %s', contact.jid, name)
        self._con.connection.send(stanza)
