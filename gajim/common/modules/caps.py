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

from __future__ import annotations

from typing import Any
from typing import Callable
from typing import Optional

import weakref
from collections import defaultdict

from nbxmpp.errors import StanzaError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Presence
from nbxmpp.structs import DiscoIdentity
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PresenceProperties
from nbxmpp.task import Task as nbxmpp_Task
from nbxmpp.util import compute_caps_hash

from gajim.common import app
from gajim.common import types
from gajim.common.const import COMMON_FEATURES
from gajim.common.const import Entity
from gajim.common.helpers import get_optional_features
from gajim.common.task_manager import Task
from gajim.common.modules.base import BaseModule


class Caps(BaseModule):

    _nbxmpp_extends = 'EntityCaps'
    _nbxmpp_methods = [
        'caps',
        'set_caps'
    ]

    def __init__(self, con: types.Client) -> None:
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

        self._queued_tasks_by_hash: defaultdict[
            str, set[EntityCapsTask]] = defaultdict(set)
        self._queued_tasks_by_jid: dict[JID, EntityCapsTask] = {}

    def _queue_task(self, task: EntityCapsTask) -> None:
        old_task = self._get_task(task.entity.jid)
        if old_task is not None:
            self._remove_task(old_task)

        self._log.info('Queue query for hash %s', task.entity.hash)
        self._queued_tasks_by_hash[task.entity.hash].add(task)
        self._queued_tasks_by_jid[task.entity.jid] = task
        app.task_manager.add_task(task)

    def _get_task(self, jid: JID) -> Optional[EntityCapsTask]:
        return self._queued_tasks_by_jid.get(jid)

    def _get_similar_tasks(self, task: EntityCapsTask) -> set[EntityCapsTask]:
        return self._queued_tasks_by_hash.pop(task.entity.hash)

    def _remove_task(self, task: EntityCapsTask) -> None:
        task.set_obsolete()
        del self._queued_tasks_by_jid[task.entity.jid]
        self._queued_tasks_by_hash[task.entity.hash].discard(task)

    def _remove_all_tasks(self) -> None:
        for task in self._queued_tasks_by_jid.values():
            task.set_obsolete()
        self._queued_tasks_by_jid.clear()
        self._queued_tasks_by_hash.clear()

    def _entity_caps(self,
                     _con: types.xmppClient,
                     _stanza: Presence,
                     properties: PresenceProperties
                     ) -> None:
        if properties.type.is_error or properties.type.is_unavailable:
            return

        if properties.is_self_presence:
            return

        if properties.entity_caps is None:
            return

        task = EntityCapsTask(self._account, properties, self._execute_task)

        self._log.info('Received %s', task.entity)

        disco_info = app.storage.cache.get_caps_entry(task.entity.method,
                                                      task.entity.hash)
        if disco_info is None:
            self._queue_task(task)
            return

        app.storage.cache.set_last_disco_info(properties.jid,
                                              disco_info,
                                              cache_only=True)

        contact = self._con.get_module('Contacts').get_contact(properties.jid)
        contact.notify('caps-update')

    def _execute_task(self, task: EntityCapsTask) -> None:
        self._log.info('Request %s from %s', task.entity.hash, task.entity.jid)
        self._con.get_module('Discovery').disco_info(
            task.entity.jid,
            node=f'{task.entity.node}#{task.entity.hash}',
            callback=self._on_disco_info,
            user_data=task.entity.jid)

    def _on_disco_info(self, nbxmpp_task: nbxmpp_Task) -> None:
        jid = nbxmpp_task.get_user_data()
        task = self._get_task(jid)
        if task is None:
            self._log.info('Task not found for %s', jid)
            return

        self._remove_task(task)

        try:
            disco_info = nbxmpp_task.finish()
        except StanzaError as error:
            self._log.warning(error)
            return

        self._log.info('Disco Info received: %s', disco_info.jid)

        try:
            compute_caps_hash(disco_info)
        except Exception as error:
            self._log.warning('Disco info malformed: %s %s',
                              disco_info.jid, error)
            return

        app.storage.cache.add_caps_entry(
            disco_info.jid,
            task.entity.method,
            disco_info.get_caps_hash(),
            disco_info)

        self._log.info('Finished query for %s', task.entity.hash)

        tasks = self._get_similar_tasks(task)

        for task in tasks:
            self._remove_task(task)
            self._log.info('Update %s', task.entity.jid)
            contact = self._con.get_module('Contacts').get_contact(
                task.entity.jid)
            contact.notify('caps-update')

    def update_caps(self) -> None:
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

    def cleanup(self) -> None:
        self._remove_all_tasks()
        BaseModule.cleanup(self)


class EntityCapsTask(Task):
    def __init__(self,
                 account: str,
                 properties: PresenceProperties,
                 callback: Callable[..., Any]
                 ) -> None:
        Task.__init__(self)
        self._account = account
        self._callback = weakref.WeakMethod(callback)

        self.entity = Entity(jid=properties.jid,
                             node=properties.entity_caps.node,
                             hash=properties.entity_caps.ver,
                             method=properties.entity_caps.hash)

        self._from_muc = properties.from_muc

    def execute(self) -> None:
        callback = self._callback()
        if callback is not None:
            callback(self)

    def preconditions_met(self) -> bool:
        try:
            client = app.get_client(self._account)
        except Exception:
            return False

        if self._from_muc:
            contact = client.get_module('Contacts').get_contact(
                self.entity.jid.bare,
                groupchat=True)

            if not contact.is_joined:
                self.set_obsolete()
                return False

        return client.state.is_available

    def __repr__(self) -> str:
        return f'Entity Caps ({self.entity.jid} {self.entity.hash})'

    def __hash__(self) -> int:
        return hash(self.entity)
