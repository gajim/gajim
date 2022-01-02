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

import nbxmpp
from nbxmpp.structs import StanzaHandler
from nbxmpp.namespaces import Namespace
from nbxmpp.modules.receipts import build_receipt

from gajim.common import app
from gajim.common.events import ReceiptReceived
from gajim.common.modules.base import BaseModule


class Receipts(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_receipt,
                          ns=Namespace.RECEIPTS,
                          priority=46),
        ]

    def _process_message_receipt(self, _con, stanza, properties):
        if not properties.is_receipt:
            return

        if properties.type.is_error:
            if properties.receipt.is_request:
                return
            # Don't propagate this event further
            raise nbxmpp.NodeProcessed

        if (properties.type.is_groupchat or
                properties.is_self_message or
                properties.is_mam_message or
                properties.is_carbon_message and properties.carbon.is_sent):

            if properties.receipt.is_received:
                # Don't propagate this event further
                raise nbxmpp.NodeProcessed
            return

        if properties.receipt.is_request:
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

            jid = properties.jid
            if not properties.is_muc_pm:
                jid = jid.new_as_bare()

            app.storage.archive.set_marker(
                app.get_jid_from_account(self._account),
                jid,
                properties.receipt.id,
                'received')

            app.ged.raise_event(
                ReceiptReceived(
                    account=self._account,
                    jid=jid,
                    receipt_id=properties.receipt.id))

            raise nbxmpp.NodeProcessed

    def _should_answer(self, properties):
        if properties.is_muc_pm:
            return True

        contact = self._get_contact(properties.jid.bare)
        if contact.subscription not in ('to', 'none'):
            return True
        return False
