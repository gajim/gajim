# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0184: Message Delivery Receipts

from __future__ import annotations

import datetime as dt

import nbxmpp
from nbxmpp.modules.receipts import build_receipt
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import ReceiptReceived
from gajim.common.modules.base import BaseModule
from gajim.common.storage.archive import models as mod


class Receipts(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_receipt,
                          ns=Namespace.RECEIPTS,
                          priority=46),
        ]

    def _process_message_receipt(self,
                                 _con: types.xmppClient,
                                 stanza: Message,
                                 properties: MessageProperties
                                 ) -> None:

        if not properties.is_receipt:
            return

        assert properties.receipt is not None
        if properties.type.is_error:
            if properties.receipt.is_request:
                return
            # Don't propagate this event further
            raise nbxmpp.NodeProcessed

        if (properties.type.is_groupchat or
                properties.is_self_message or
                properties.is_carbon_message and properties.carbon.is_sent):

            if properties.receipt.is_received:
                # Don't propagate this event further
                raise nbxmpp.NodeProcessed
            return

        if properties.receipt.is_request and not properties.is_mam_message:
            if not app.settings.get_account_setting(self._account,
                                                    'answer_receipts'):
                return

            if properties.eme is not None:
                # Don't send receipt for message which couldn't be decrypted
                if not properties.is_encrypted:
                    return

            if not self._should_answer(properties):
                return
            self._log.info('Send receipt: %s', properties.jid)
            self._con.connection.send(build_receipt(stanza))
            return

        if properties.receipt.is_received:
            self._log.info('Receipt from %s %s',
                           properties.jid,
                           properties.receipt.id)

            if properties.is_mam_message:
                timestamp = properties.mam.timestamp
            else:
                timestamp = properties.timestamp

            timestamp = dt.datetime.fromtimestamp(
                timestamp, dt.timezone.utc)

            receipt_data = mod.Receipt(
                account_=self._account,
                remote_jid_=properties.remote_jid,
                id=properties.receipt.id,
                timestamp=timestamp)
            app.storage.archive.insert_object(receipt_data)

            app.ged.raise_event(
                ReceiptReceived(
                    account=self._account,
                    jid=properties.remote_jid,
                    receipt_id=properties.receipt.id))

            raise nbxmpp.NodeProcessed

    def _should_answer(self, properties: MessageProperties) -> bool:
        if properties.is_muc_pm:
            return True

        contact = self._get_contact(JID.from_string(properties.jid.bare))
        return contact.is_subscribed
