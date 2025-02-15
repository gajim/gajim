# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0100: Gateway Interaction

from __future__ import annotations

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common.events import AgentRemoved
from gajim.common.events import GatewayPromptReceived
from gajim.common.modules.base import BaseModule


class Gateway(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

    def unsubscribe(self, agent: str) -> None:
        if not app.account_is_available(self._account):
            return
        iq = nbxmpp.Iq('set', Namespace.REGISTER, to=agent)
        iq.setQuery().setTag('remove')

        self._con.connection.SendAndCallForResponse(
            iq, self._on_unsubscribe_result)
        self._con.get_module('Roster').delete_item(agent)

    def _on_unsubscribe_result(self,
                               _nbxmpp_client: types.NBXMPPClient,
                               stanza: nbxmpp.Protocol
                               ) -> None:
        if not nbxmpp.isResultNode(stanza):
            self._log.info('Error: %s', stanza.getError())
            return

        agent = stanza.getFrom().bare
        jid_list: list[JID] = []
        for contact in self._client.get_module('Roster').iter_contacts():
            if contact.jid.domain == agent:
                jid_list.append(contact.jid)
                self._log.info(
                    'Removing contact %s due to unregistered transport %s',
                    contact.jid,
                    agent)
                self._con.get_module('Presence').unsubscribe(contact.jid)

                # Transport contacts can't have 2 resources
                if contact.jid in app.to_be_removed[self._account]:
                    # This way we'll really remove it
                    app.to_be_removed[self._account].remove(contact.jid)

        app.ged.raise_event(
            AgentRemoved(conn=self._con,
                         agent=agent,
                         jid_list=jid_list))

    def request_gateway_prompt(self,
                               jid: str,
                               prompt: str | None = None
                               ) -> None:
        typ_ = 'get'
        if prompt:
            typ_ = 'set'
        iq = nbxmpp.Iq(typ=typ_, to=jid)
        query = iq.addChild(name='query', namespace=Namespace.GATEWAY)
        if prompt:
            query.setTagData('prompt', prompt)
        self._con.connection.SendAndCallForResponse(iq, self._on_prompt_result)

    def _on_prompt_result(self,
                          _nbxmpp_client: types.NBXMPPClient,
                          stanza: Iq
                          ) -> None:
        jid = str(stanza.getFrom())
        fjid = stanza.getFrom().bare
        resource = stanza.getFrom().resource

        query = stanza.getTag('query')
        if query is not None:
            desc = query.getTagData('desc')
            prompt = query.getTagData('prompt')
            prompt_jid = query.getTagData('jid')
        else:
            desc = None
            prompt = None
            prompt_jid = None

        app.ged.raise_event(
            GatewayPromptReceived(conn=self._con,
                                  fjid=fjid,
                                  jid=jid,
                                  resource=resource,
                                  desc=desc,
                                  prompt=prompt,
                                  prompt_jid=prompt_jid,
                                  stanza=stanza))
