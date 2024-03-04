# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0172: User Nickname

from __future__ import annotations

from typing import Any

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MessageProperties

from gajim.common import app
from gajim.common import types
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node


class UserNickname(BaseModule):

    _nbxmpp_extends = 'Nickname'
    _nbxmpp_methods = [
        'set_nickname',
        'set_access_model',
    ]

    def __init__(self, con: types.Client):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._nickname_received)

    @event_node(Namespace.NICK)
    def _nickname_received(self,
                           _con: types.xmppClient,
                           _stanza: Any,
                           properties: MessageProperties
                           ) -> None:
        if properties.pubsub_event.retracted:
            return

        nick = properties.pubsub_event.data
        if properties.is_self_message:
            if nick is None:
                nick = app.settings.get_account_setting(self._account, 'name')
            app.nicks[self._account] = nick
            return

        app.storage.cache.set_contact(
            self._account, properties.jid, 'nickname', nick)

        self._log.info('Nickname for %s: %s', properties.jid, nick)

        contact = self._con.get_module('Contacts').get_contact(properties.jid)
        if contact is None:
            return

        contact.notify('nickname-update')
