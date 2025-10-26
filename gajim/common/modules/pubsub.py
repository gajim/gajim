# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0060: Publish-Subscribe

from __future__ import annotations

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import DiscoInfo

from gajim.common import types
from gajim.common.modules.base import BaseModule


class PubSub(BaseModule):

    _nbxmpp_extends = 'PubSub'
    _nbxmpp_methods = [
        'publish',
        'delete',
        'set_node_configuration',
        'get_node_configuration',
        'get_access_model',
        'request_items',
        'subscribe',
        'unsubscribe',
        'get_subscriptions',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.publish_options = False

    def pass_disco(self, info: DiscoInfo) -> None:
        if Namespace.PUBSUB_PUBLISH_OPTIONS in info.features:
            self._log.info('Discovered Pubsub publish options: %s', info.jid)
            self.publish_options = True
