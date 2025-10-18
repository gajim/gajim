# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0172: User Nickname

from __future__ import annotations

from typing import Any

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.util import event_node


class UserNickname(BaseModule):

    _nbxmpp_extends = 'Nickname'
    _nbxmpp_methods = [
        'set_nickname',
        'set_access_model',
    ]

    def __init__(self, con: types.Client):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._message_nickname_received,
                          typ='chat',
                          priority=51),
        ]

        self._register_pubsub_handler(self._nickname_received)

    def _message_nickname_received(
        self,
        _con: types.NBXMPPClient,
        _stanza: Any,
        properties: MessageProperties
    ) -> None:

        if properties.nickname is None:
            return

        remote_jid = properties.remote_jid
        assert remote_jid is not None

        contact = self._client.get_module('Contacts').get_contact(remote_jid)
        if not isinstance(contact, BareContact):
            return

        if contact.subscription in ('both', 'to'):
            # When we are subscripted to this contact we can
            # get the nickname via pubsub
            return

        if contact.name == properties.nickname:
            return

        app.storage.cache.set_contact(
            self._account,
            remote_jid,
            'nickname',
            f'{properties.nickname} ({remote_jid})'
        )

        contact.notify('nickname-update')

    @event_node(Namespace.NICK)
    def _nickname_received(self,
                           _con: types.NBXMPPClient,
                           _stanza: Any,
                           properties: MessageProperties
                           ) -> None:
        assert properties.pubsub_event is not None
        if properties.pubsub_event.retracted:
            return

        nick = properties.pubsub_event.data
        if properties.is_self_message:
            if nick is None:
                nick = app.get_default_nick(self._account)
            app.nicks[self._account] = nick
            return

        assert properties.jid is not None
        app.storage.cache.set_contact(
            self._account, properties.jid, 'nickname', nick)

        self._log.info('Nickname for %s: %s', properties.jid, nick)

        contact = self._con.get_module('Contacts').get_contact(properties.jid)
        contact.notify('nickname-update')
