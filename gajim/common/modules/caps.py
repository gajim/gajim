# Copyright (C) 2009 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

# XEP-0115: Entity Capabilities

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import DiscoIdentity
from nbxmpp.util import is_error_result
from nbxmpp.util import compute_caps_hash

from gajim.common import app
from gajim.common.const import COMMON_FEATURES
from gajim.common.helpers import get_optional_features
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule


class Caps(BaseModule):

    _nbxmpp_extends = 'EntityCaps'
    _nbxmpp_methods = [
        'caps',
        'set_caps'
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._entity_caps,
                          ns=Namespace.CAPS,
                          priority=51),
        ]

        self._identities = [
            DiscoIdentity(category='client', type='pc', name='Gajim')
        ]

    def _entity_caps(self, _con, _stanza, properties):
        if properties.type.is_error or properties.type.is_unavailable:
            return

        if properties.is_self_presence:
            return

        if properties.entity_caps is None:
            return

        jid = str(properties.jid)

        hash_method = properties.entity_caps.hash
        node = properties.entity_caps.node
        caps_hash = properties.entity_caps.ver

        self._log.info(
            'Received from %s, type: %s, method: %s, node: %s, hash: %s',
            jid, properties.type, hash_method, node, caps_hash)

        disco_info = app.logger.get_caps_entry(hash_method, caps_hash)
        if disco_info is None:
            self._con.get_module('Discovery').disco_info(
                jid,
                '%s#%s' % (node, caps_hash),
                callback=self._on_disco_info,
                user_data=hash_method)

        else:
            app.logger.set_last_disco_info(jid, disco_info, cache_only=True)
            app.nec.push_incoming_event(
                NetworkEvent('caps-update',
                             account=self._account,
                             fjid=jid,
                             jid=properties.jid.getBare()))

    def _on_disco_info(self, disco_info, hash_method):
        if is_error_result(disco_info):
            self._log.info(disco_info)
            return

        bare_jid = disco_info.jid.getBare()

        try:
            compute_caps_hash(disco_info)
        except Exception as error:
            self._log.warning('Disco info malformed: %s %s',
                              disco_info.jid, error)
            return

        app.logger.add_caps_entry(
            str(disco_info.jid),
            hash_method,
            disco_info.get_caps_hash(),
            disco_info)

        app.nec.push_incoming_event(
            NetworkEvent('caps-update',
                         account=self._account,
                         fjid=str(disco_info.jid),
                         jid=bare_jid))

    def update_caps(self):
        if not app.account_is_connected(self._account):
            return

        optional_features = get_optional_features(self._account)
        self.set_caps(self._identities,
                      COMMON_FEATURES + optional_features,
                      'https://gajim.org')

        if not app.account_is_available(self._account):
            return

        app.connections[self._account].change_status(
            app.connections[self._account].status,
            app.connections[self._account].status_message)


def get_instance(*args, **kwargs):
    return Caps(*args, **kwargs), 'Caps'
