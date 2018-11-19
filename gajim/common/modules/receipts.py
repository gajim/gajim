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

# XEP-0184: Message Delivery Receipts

import logging

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.receipts')


class Receipts:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

    def delegate(self, event):
        request = event.stanza.getTag('request',
                                      namespace=nbxmpp.NS_RECEIPTS)
        if request is not None:
            self._answer_request(event)
            return

        received = event.stanza.getTag('received',
                                       namespace=nbxmpp.NS_RECEIPTS)
        if received is not None:
            self._receipt_received(event, received)
            raise nbxmpp.NodeProcessed

    def _answer_request(self, event):
        if not app.config.get_per('accounts', self._account,
                                  'answer_receipts'):
            return

        if event.mtype not in ('chat', 'normal'):
            return

        if event.sent:
            # Never answer messages that we sent from another device
            return

        from_ = event.stanza.getFrom()
        if self._con.get_own_jid().bareMatch(from_):
            # Dont answer receipts from our other resources
            return

        receipt_id = event.stanza.getID()

        contact = self._get_contact(event)
        if contact is None:
            return

        receipt = self._build_answer_receipt(from_, receipt_id)
        log.info('Answer %s', receipt_id)
        self._con.connection.send(receipt)

    def _get_contact(self, event):
        if event.mtype == 'chat':
            contact = app.contacts.get_contact(self._account, event.jid)
            if contact and contact.sub not in ('to', 'none'):
                return contact
        else:
            return app.contacts.get_gc_contact(self._account,
                                               event.jid,
                                               event.resource)

    @staticmethod
    def _build_answer_receipt(to, receipt_id):
        receipt = nbxmpp.Message(to=to, typ='chat')
        receipt.setTag('received',
                       namespace='urn:xmpp:receipts',
                       attrs={'id': receipt_id})
        return receipt

    def _receipt_received(self, event, received):
        receipt_id = received.getAttr('id')
        if receipt_id is None:
            log.warning('Receipt without ID: %s', event.stanza)
            return
        log.info('Received %s', receipt_id)
        app.nec.push_incoming_event(
            NetworkIncomingEvent('receipt-received',
                                 conn=self._con,
                                 receipt_id=receipt_id,
                                 jid=event.jid))


def get_instance(*args, **kwargs):
    return Receipts(*args, **kwargs), 'Receipts'
