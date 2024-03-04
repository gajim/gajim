# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0191: Blocking Command

from __future__ import annotations

from collections.abc import Generator

import nbxmpp
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import BlockingProperties
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import FeatureDiscovered
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


class Blocking(BaseModule):

    _nbxmpp_extends = 'Blocking'
    _nbxmpp_methods = [
        'block',
        'unblock',
        'request_blocking_list',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.blocked: set[JID] = set()

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._blocking_push_received,
                          typ='set',
                          ns=Namespace.BLOCKING),
        ]

        self.supported = False

    def pass_disco(self, info: DiscoInfo) -> None:
        if Namespace.BLOCKING not in info.features:
            return

        self.supported = True
        app.ged.raise_event(
            FeatureDiscovered(account=self._account,
                              feature=Namespace.BLOCKING))

        self._log.info('Discovered blocking: %s', info.jid)

    def is_blocked(self, jid: JID) -> bool:
        return jid in self.blocked

    @as_task
    def get_blocking_list(self) -> Generator[set[JID], None, None]:
        _task = yield  # noqa: F841

        blocking_list = yield self._nbxmpp('Blocking').request_blocking_list()

        raise_if_error(blocking_list)

        self.blocked = blocking_list
        for contact in self._get_contacts_from_jids(blocking_list):
            contact.set_blocked()

        yield blocking_list

    @as_task
    def update_blocking_list(self,
                             block: set[JID],
                             unblock: set[JID]
                             ) -> Generator[bool, None, None]:
        _task = yield  # noqa: F841

        if block:
            result = yield self.block(block)
            raise_if_error(result)

        if unblock:
            result = yield self.unblock(unblock)
            raise_if_error(result)

        yield True

    def _blocking_push_received(self,
                                _con: types.xmppClient,
                                _stanza: Iq,
                                properties: BlockingProperties
                                ) -> None:
        if not properties.is_blocking:
            return

        if properties.blocking.unblock_all:
            unblock = set(self.blocked)
            self.blocked = set()
            self._unblock_jids(unblock)
            raise nbxmpp.NodeProcessed

        if properties.blocking.unblock:
            self.blocked -= properties.blocking.unblock
            self._unblock_jids(properties.blocking.unblock)

        if properties.blocking.block:
            block = properties.blocking.block
            self.blocked.update(block)
            for contact in self._get_contacts_from_jids(block):
                self._log.info('Block Push: %s', contact.jid)
                contact.set_blocked()

        raise nbxmpp.NodeProcessed

    def _unblock_jids(self, jids: set[JID]) -> None:
        for contact in self._get_contacts_from_jids(jids):
            contact.set_unblocked()
            self._presence_probe(contact.jid)
            self._log.info('Unblock Push: %s', contact.jid)

    def _get_contacts_from_jids(self,
                                jids: set[JID]
                                ) -> Generator[types.BareContactT, None, None]:
        for jid in jids:
            if jid.resource is not None:
                # Currently not supported by GUI
                continue

            if jid.is_domain:
                module = self._con.get_module('Contacts')
                contacts = module.get_contacts_with_domain(jid.domain)
                for contact in contacts:
                    if contact.is_groupchat:
                        # Currently not supported by GUI
                        continue

                    yield contact

                continue

            yield self._get_contact(jid)

    def _presence_probe(self, jid: JID) -> None:
        self._log.info('Presence probe: %s', jid)
        # Send a presence Probe to get the current Status
        probe = nbxmpp.Presence(jid, 'probe', frm=self._con.get_own_jid())
        self._nbxmpp().send(probe)
