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

import logging
import weakref

import nbxmpp

from gajim.common import app
from gajim.common import helpers
from gajim.common.caps_cache import muc_caps_cache
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.connection_handlers_events import InformationEvent

log = logging.getLogger('gajim.c.m.discovery')


class Discovery:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('iq', self._answer_disco_info, 'get', nbxmpp.NS_DISCO_INFO),
            ('iq', self._answer_disco_items, 'get', nbxmpp.NS_DISCO_ITEMS),
        ]

    def disco_contact(self, jid, node=None):
        success_cb = self._con.get_module('Caps').contact_info_received
        self._disco(nbxmpp.NS_DISCO_INFO, jid, node, success_cb, None)

    def disco_items(self, jid, node=None, success_cb=None, error_cb=None):
        self._disco(nbxmpp.NS_DISCO_ITEMS, jid, node, success_cb, error_cb)

    def disco_info(self, jid, node=None, success_cb=None, error_cb=None):
        self._disco(nbxmpp.NS_DISCO_INFO, jid, node, success_cb, error_cb)

    def _disco(self, namespace, jid, node, success_cb, error_cb):
        if success_cb is None:
            raise ValueError('success_cb is required')
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq(typ='get', to=jid, queryNS=namespace)
        if node:
            iq.setQuerynode(node)

        log_str = 'Request info: %s %s'
        if namespace == nbxmpp.NS_DISCO_ITEMS:
            log_str = 'Request items: %s %s'
        log.info(log_str, jid, node or '')

        # Create weak references so we can pass GUI object methods
        weak_success_cb = weakref.WeakMethod(success_cb)
        if error_cb is not None:
            weak_error_cb = weakref.WeakMethod(error_cb)
        else:
            weak_error_cb = None
        self._con.connection.SendAndCallForResponse(
            iq, self._disco_response, {'success_cb': weak_success_cb,
                                       'error_cb': weak_error_cb})

    def _disco_response(self, _con, stanza, success_cb, error_cb):
        if not nbxmpp.isResultNode(stanza):
            if error_cb is not None:
                error_cb()(stanza.getFrom(), stanza.getError())
            else:
                log.info('Error: %s', stanza.getError())
            return

        from_ = stanza.getFrom()
        node = stanza.getQuerynode()
        if stanza.getQueryNS() == nbxmpp.NS_DISCO_INFO:
            identities, features, data, node = self.parse_info_response(stanza)
            success_cb()(from_, identities, features, data, node)

        elif stanza.getQueryNS() == nbxmpp.NS_DISCO_ITEMS:
            items = self.parse_items_response(stanza)
            success_cb()(from_, node, items)
        else:
            log.warning('Wrong query namespace: %s', stanza)

    @classmethod
    def parse_items_response(cls, stanza):
        payload = stanza.getQueryPayload()
        items = []
        for item in payload:
            # CDATA payload is not processed, only nodes
            if not isinstance(item, nbxmpp.simplexml.Node):
                continue
            attr = item.getAttrs()
            if 'jid' not in attr:
                log.warning('No jid attr in disco items: %s', stanza)
                continue
            try:
                attr['jid'] = helpers.parse_jid(attr['jid'])
            except helpers.InvalidFormat:
                log.warning('Invalid jid attr in disco items: %s', stanza)
                continue
            items.append(attr)
        return items

    @classmethod
    def parse_info_response(cls, stanza):
        identities, features, data, node = [], [], [], None
        query = stanza.getTag('query')
        node = query.getAttr('node')
        if not node:
            node = ''

        childs = stanza.getQueryChildren()
        if not childs:
            childs = []

        for i in childs:
            if i.getName() == 'identity':
                attr = {}
                for key in i.getAttrs().keys():
                    attr[key] = i.getAttr(key)
                identities.append(attr)
            elif i.getName() == 'feature':
                var = i.getAttr('var')
                if var:
                    features.append(var)
            elif i.getName() == 'x' and i.getNamespace() == nbxmpp.NS_DATA:
                data.append(nbxmpp.DataForm(node=i))

        return identities, features, data, node

    def discover_server_items(self):
        server = self._con.get_own_jid().getDomain()
        self.disco_items(server, success_cb=self._server_items_received)

    def _server_items_received(self, _from, _node, items):
        log.info('Server items received')
        for item in items:
            if 'node' in item:
                # Only disco components
                continue
            self.disco_info(item['jid'],
                            success_cb=self._server_items_info_received)

    def _server_items_info_received(self, from_, *args):
        from_ = from_.getStripped()
        log.info('Server item info received: %s', from_)
        self._parse_transports(from_, *args)
        try:
            self._con.get_module('MUC').pass_disco(from_, *args)
            self._con.get_module('HTTPUpload').pass_disco(from_, *args)
            self._con.pass_bytestream_disco(from_, *args)
        except nbxmpp.NodeProcessed:
            pass

        app.nec.push_incoming_event(
            NetworkIncomingEvent('server-disco-received'))

    def discover_account_info(self):
        own_jid = self._con.get_own_jid().getStripped()
        self.disco_info(own_jid, success_cb=self._account_info_received)

    def _account_info_received(self, from_, *args):
        from_ = from_.getStripped()
        log.info('Account info received: %s', from_)

        self._con.get_module('MAM').pass_disco(from_, *args)
        self._con.get_module('PEP').pass_disco(from_, *args)
        self._con.get_module('PubSub').pass_disco(from_, *args)

        features = args[1]
        if 'urn:xmpp:pep-vcard-conversion:0' in features:
            self._con.avatar_conversion = True

    def discover_server_info(self):
        # Calling this method starts the connect_maschine()
        server = self._con.get_own_jid().getDomain()
        self.disco_info(server, success_cb=self._server_info_received)

    def _server_info_received(self, from_, *args):
        log.info('Server info received: %s', from_)

        self._con.get_module('SecLabels').pass_disco(from_, *args)
        self._con.get_module('Blocking').pass_disco(from_, *args)
        self._con.get_module('VCardTemp').pass_disco(from_, *args)
        self._con.get_module('Carbons').pass_disco(from_, *args)
        self._con.get_module('PrivacyLists').pass_disco(from_, *args)
        self._con.get_module('HTTPUpload').pass_disco(from_, *args)

        features = args[1]
        if nbxmpp.NS_REGISTER in features:
            self._con.register_supported = True

        if nbxmpp.NS_ADDRESS in features:
            self._con.addressing_supported = True

        self._con.connect_machine(restart=True)

    def _parse_transports(self, from_, identities, _features, _data, _node):
        for identity in identities:
            category = identity.get('category')
            if category not in ('gateway', 'headline'):
                continue
            transport_type = identity.get('type')
            log.info('Found transport: %s %s %s',
                     from_, category, transport_type)
            jid = str(from_)
            if jid not in app.transport_type:
                app.transport_type[jid] = transport_type
            app.logger.save_transport_type(jid, transport_type)

            if transport_type in self._con.available_transports:
                self._con.available_transports[transport_type].append(jid)
            else:
                self._con.available_transports[transport_type] = [jid]

    def _answer_disco_items(self, _con, stanza):
        from_ = stanza.getFrom()
        log.info('Answer disco items to %s', from_)

        if self._con.get_module('AdHocCommands').command_items_query(stanza):
            raise nbxmpp.NodeProcessed

        node = stanza.getTagAttr('query', 'node')
        if node is None:
            result = stanza.buildReply('result')
            self._con.connection.send(result)
            raise nbxmpp.NodeProcessed

        if node == nbxmpp.NS_COMMANDS:
            self._con.get_module('AdHocCommands').command_list_query(stanza)
            raise nbxmpp.NodeProcessed

    def _answer_disco_info(self, _con, stanza):
        from_ = stanza.getFrom()
        log.info('Answer disco info %s', from_)
        if str(from_).startswith('echo.'):
            # Service that echos all stanzas, ignore it
            raise nbxmpp.NodeProcessed

        if self._con.get_module('AdHocCommands').command_info_query(stanza):
            raise nbxmpp.NodeProcessed

        node = stanza.getQuerynode()
        iq = stanza.buildReply('result')
        query = iq.setQuery()
        if node:
            query.setAttr('node', node)
        query.addChild('identity', attrs=app.gajim_identity)
        client_version = 'http://gajim.org#' + app.caps_hash[self._account]

        if node in (None, client_version):
            for feature in app.gajim_common_features:
                query.addChild('feature', attrs={'var': feature})
            for feature in app.gajim_optional_features[self._account]:
                query.addChild('feature', attrs={'var': feature})

        self._con.connection.send(iq)
        raise nbxmpp.NodeProcessed

    def disco_muc(self, jid, callback, update=False):
        if not app.account_is_connected(self._account):
            return
        if muc_caps_cache.is_cached(jid) and not update:
            callback()
            return

        iq = nbxmpp.Iq(typ='get', to=jid, queryNS=nbxmpp.NS_DISCO_INFO)
        log.info('Request MUC info %s', jid)

        self._con.connection.SendAndCallForResponse(
            iq, self._muc_info_response, {'callback': callback})

    @staticmethod
    def _muc_info_response(_con, stanza, callback):
        if not nbxmpp.isResultNode(stanza):
            error = stanza.getError()
            if error == 'item-not-found':
                # Groupchat does not exist
                log.info('MUC does not exist: %s', stanza.getFrom())
                callback()
            else:
                log.info('MUC disco error: %s', error)
                app.nec.push_incoming_event(
                    InformationEvent(
                        None, dialog_name='unable-join-groupchat', args=error))
            return

        log.info('MUC info received: %s', stanza.getFrom())
        muc_caps_cache.append(stanza)
        callback()


def get_instance(*args, **kwargs):
    return Discovery(*args, **kwargs), 'Discovery'
