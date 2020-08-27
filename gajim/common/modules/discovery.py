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

# XEP-0030: Service Discovery

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import is_error_result

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule


class Discovery(BaseModule):

    _nbxmpp_extends = 'Discovery'
    _nbxmpp_methods = [
        'disco_info',
        'disco_items',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_disco_info,
                          typ='get',
                          ns=Namespace.DISCO_INFO),
            StanzaHandler(name='iq',
                          callback=self._answer_disco_items,
                          typ='get',
                          ns=Namespace.DISCO_ITEMS),
        ]

        self._account_info = None
        self._server_info = None

    @property
    def account_info(self):
        return self._account_info

    @property
    def server_info(self):
        return self._server_info

    def discover_server_items(self):
        server = self._con.get_own_jid().domain
        self.disco_items(server, callback=self._server_items_received)

    def _server_items_received(self, result):
        if is_error_result(result):
            self._log.warning('Server disco failed')
            self._log.error(result)
            return

        self._log.info('Server items received')
        self._log.debug(result)
        for item in result.items:
            if item.node is not None:
                # Only disco components
                continue
            self.disco_info(item.jid, callback=self._server_items_info_received)

    def _server_items_info_received(self, result):
        if is_error_result(result):
            self._log.warning('Server item disco info failed')
            self._log.warning(result)
            return

        self._log.info('Server item info received: %s', result.jid)
        self._parse_transports(result)
        try:
            self._con.get_module('MUC').pass_disco(result)
            self._con.get_module('HTTPUpload').pass_disco(result)
            self._con.get_module('Bytestream').pass_disco(result)
        except nbxmpp.NodeProcessed:
            pass

        app.nec.push_incoming_event(
            NetworkIncomingEvent('server-disco-received'))

    def discover_account_info(self):
        own_jid = self._con.get_own_jid().bare
        self.disco_info(own_jid, callback=self._account_info_received)

    def _account_info_received(self, result):
        if is_error_result(result):
            self._log.warning('Account disco info failed')
            self._log.warning(result)
            return

        self._log.info('Account info received: %s', result.jid)

        self._account_info = result

        self._con.get_module('MAM').pass_disco(result)
        self._con.get_module('PEP').pass_disco(result)
        self._con.get_module('PubSub').pass_disco(result)
        self._con.get_module('Bookmarks').pass_disco(result)

        if 'urn:xmpp:pep-vcard-conversion:0' in result.features:
            self._con.avatar_conversion = True

        self._con.get_module('Caps').update_caps()

    def discover_server_info(self):
        # Calling this method starts the connect_maschine()
        server = self._con.get_own_jid().domain
        self.disco_info(server, callback=self._server_info_received)

    def _server_info_received(self, result):
        if is_error_result(result):
            self._log.error('Server disco info failed')
            self._log.error(result)
            return

        self._log.info('Server info received: %s', result.jid)

        self._server_info = result

        self._con.get_module('SecLabels').pass_disco(result)
        self._con.get_module('Blocking').pass_disco(result)
        self._con.get_module('VCardTemp').pass_disco(result)
        self._con.get_module('Carbons').pass_disco(result)
        self._con.get_module('HTTPUpload').pass_disco(result)
        self._con.get_module('Register').pass_disco(result)

        self._con.connect_machine(restart=True)

    def _parse_transports(self, info):
        for identity in info.identities:
            if identity.category not in ('gateway', 'headline'):
                continue

            self._log.info('Found transport: %s %s %s',
                           info.jid, identity.category, identity.type)

            jid = str(info.jid)
            if jid not in app.transport_type:
                app.transport_type[jid] = identity.type
            app.logger.save_transport_type(jid, identity.type)

            if identity.type in self._con.available_transports:
                self._con.available_transports[identity.type].append(jid)
            else:
                self._con.available_transports[identity.type] = [jid]

    def _answer_disco_items(self, _con, stanza, _properties):
        from_ = stanza.getFrom()
        self._log.info('Answer disco items to %s', from_)

        if self._con.get_module('AdHocCommands').command_items_query(stanza):
            raise nbxmpp.NodeProcessed

        node = stanza.getTagAttr('query', 'node')
        if node is None:
            result = stanza.buildReply('result')
            self._con.connection.send(result)
            raise nbxmpp.NodeProcessed

        if node == Namespace.COMMANDS:
            self._con.get_module('AdHocCommands').command_list_query(stanza)
            raise nbxmpp.NodeProcessed

    def _answer_disco_info(self, _con, stanza, _properties):
        from_ = stanza.getFrom()
        self._log.info('Answer disco info %s', from_)
        if str(from_).startswith('echo.'):
            # Service that echos all stanzas, ignore it
            raise nbxmpp.NodeProcessed

        if self._con.get_module('AdHocCommands').command_info_query(stanza):
            raise nbxmpp.NodeProcessed

    def disco_muc(self, jid, callback=None):
        if not app.account_is_available(self._account):
            return

        self._log.info('Request MUC info for %s', jid)

        self.disco_info(jid,
                        callback=self._muc_info_received,
                        user_data=callback)

    def _muc_info_received(self, result, callback=None):
        self._log.info('MUC info received: %s', result.jid)
        if not is_error_result(result):
            app.logger.set_last_disco_info(result.jid, result)
            self._con.get_module('VCardAvatars').muc_disco_info_update(result)
            app.nec.push_incoming_event(NetworkEvent(
                'muc-disco-update',
                account=self._account,
                room_jid=result.jid))

        if callback is not None:
            callback(result)


def get_instance(*args, **kwargs):
    return Discovery(*args, **kwargs), 'Discovery'
