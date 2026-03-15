# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0292: vCard4 Over XMPP

from __future__ import annotations

from typing import Any
from typing import cast

import inspect
import time
import weakref

from nbxmpp.errors import StanzaError
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.modules.vcard4 import TzProperty
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import types
from gajim.common.events import TimezoneChanged
from gajim.common.events import VCard4Received
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.util.datetime import get_local_timezone
from gajim.common.util.datetime import get_timezone_from_vcard

MAX_CACHE_SECONDS = 60


class VCard4(BaseModule):

    _nbxmpp_extends = 'VCard4'
    _nbxmpp_methods = [
        'set_vcard',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
        self._vcard_cache: dict[JID, tuple[float, VCard]] = {}
        self._own_vcard: VCard = VCard()
        self._register_pubsub_handler(self._vcard_event_received)

    @event_node(Namespace.VCARD4_PUBSUB)
    def _vcard_event_received(
        self,
        _client: types.NBXMPPClient,
        _stanza: Message,
        properties: MessageProperties
        ) -> None:

        assert properties.jid is not None
        if not properties.jid.bare_match(self._get_own_bare_jid()):
            self._log.info(
                "Ignore VCard4 event not from our account: %s", properties.jid)
            return

        assert properties.pubsub_event is not None
        if (properties.pubsub_event.deleted
                or properties.pubsub_event.purged
                or properties.pubsub_event.retracted):
            self._log.info('VCard4 node deleted/purged/retracted')
            self._own_vcard = VCard()

        else:
            self._log.info("Received VCard4 event from %s", properties.jid)
            self._own_vcard = cast(VCard, properties.pubsub_event.data)

        app.ged.raise_event(VCard4Received(self._account, self._own_vcard))

        self._check_for_timezone_change()

    def _check_for_timezone_change(self) -> None:
        if not app.settings.get_account_setting(self._account, "update_timezone"):
            return

        vcard_timezone = get_timezone_from_vcard(self._own_vcard)
        local_timezone = get_local_timezone()
        if local_timezone is None:
            self._log.warning("Unable to determine timezone")
            return

        if vcard_timezone == local_timezone:
            return

        self._log.info("Timezone change detected, vcard: %s, local: %s",
                       vcard_timezone, local_timezone)

        if app.settings.get_account_setting(self._account, "confirm_timezone_change"):
            app.ged.raise_event(
                TimezoneChanged(
                    self._account,
                    vcard=vcard_timezone,
                    local=local_timezone,
                )
            )
            return

        self.update_timezone()

    def update_timezone(self) -> None:
        local_timezone = get_local_timezone()
        if local_timezone is None:
            return

        for prop in self._own_vcard.get_properties():
            if isinstance(prop, TzProperty):
                self._own_vcard.remove_property(prop)

        self._own_vcard.add_property("tz", value_type="text", value=local_timezone)
        self._log.info("Update timezone to: %s", local_timezone)
        self.set_vcard(self._own_vcard)

    def subscribe_to_node(self) -> None:
        self._log.info("Subscribe to node")
        self._client.get_module('PubSub').subscribe(Namespace.VCARD4_PUBSUB)

        jid = self._get_own_bare_jid()

        self._nbxmpp('VCard4').request_vcard(
            jid,
            timeout=10,
            callback=self._on_vcard_received,
            user_data=(jid, None),
        )

    def get_own_vcard(self) -> VCard:
        return self._own_vcard

    def request_vcard(
        self, jid: JID, callback: Any, use_cache: bool = False
    ) -> None | VCard:
        if use_cache:
            self._expire_cache()
            cached_result = self._vcard_cache.get(jid)
            if cached_result is not None:
                _, vcard = cached_result
                return vcard

        if inspect.ismethod(callback):
            weak_callable = weakref.WeakMethod(callback)
        elif inspect.isfunction(callback):
            weak_callable = weakref.ref(callback)
        else:
            raise TypeError('Unknown callback type: %s' % callback)

        self._nbxmpp('VCard4').request_vcard(
            jid,
            timeout=10,
            callback=self._on_vcard_received,
            user_data=(jid, weak_callable),
        )

    def _expire_cache(self) -> None:
        for jid, data in list(self._vcard_cache.items()):
            cache_time, _ = data
            if time.time() - MAX_CACHE_SECONDS > cache_time:
                self._vcard_cache.pop(jid)

    def _on_vcard_received(self, task: Task) -> None:
        try:
            vcard = cast(VCard | None, task.finish())
        except (StanzaError, TimeoutStanzaError) as err:
            self._log.info('Error loading VCard: %s', err)
            vcard = None

        jid, weak_callable = task.get_user_data()

        if vcard is None:
            vcard = VCard()
        else:
            self._log.info('Received VCard for %s', jid)
            self._vcard_cache[jid] = (time.time(), vcard)

        if jid.bare_match(self._get_own_bare_jid()):
            self._own_vcard = vcard
            app.ged.raise_event(VCard4Received(self._account, self._own_vcard))

        if weak_callable is None:
            return

        callback = weak_callable()
        if callback is None:
            return

        callback(jid, vcard)
