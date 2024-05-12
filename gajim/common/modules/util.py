# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Util module

from __future__ import annotations

from typing import Any

from collections.abc import Callable
from functools import partial
from functools import wraps
from logging import LoggerAdapter

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import EMEData
from nbxmpp.structs import MessageProperties
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import types
from gajim.common.const import EME_MESSAGES
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.structs import MUCData


def from_xs_boolean(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value

    if value in ('1', 'true', 'True'):
        return True

    if value in ('0', 'false', 'False', ''):
        return False

    raise ValueError(f'Cant convert {value} to python boolean')


def to_xs_boolean(value: bool | None) -> str:
    # Convert to xs:boolean ('true', 'false')
    # from a python boolean (True, False) or None
    if value is True:
        return 'true'

    if value is False:
        return 'false'

    if value is None:
        return 'false'

    raise ValueError(f'Cant convert {value} to xs:boolean')


def event_node(node: nbxmpp.Node) -> Any:
    def event_node_decorator(func: Any):
        @wraps(func)
        def func_wrapper(self: Any,
                         _con: types.xmppClient,
                         _stanza: Message,
                         properties: MessageProperties
                         ) -> Any:
            if not properties.is_pubsub_event:
                return
            if properties.pubsub_event.node != node:
                return
            func(self, _con, _stanza, properties)

        return func_wrapper
    return event_node_decorator


def store_publish(func: Any):
    @wraps(func)
    def func_wrapper(self: Any, *args: Any, **kwargs: Any):
        # pylint: disable=protected-access
        if not app.account_is_connected(self._account):
            self._stored_publish = partial(func, self, *args, **kwargs)
            return None
        return func(self, *args, **kwargs)
    return func_wrapper


def get_eme_message(eme_data: EMEData) -> str:
    try:
        return EME_MESSAGES[eme_data.namespace]
    except KeyError:
        return EME_MESSAGES['fallback'] % eme_data.name


class LogAdapter(LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        return f'({self.extra["account"]}) {msg}', kwargs


def as_task(func: Any) -> Any:
    @wraps(func)
    def func_wrapper(self: Any,
                     *args: Any,
                     timeout: int | None =None,
                     callback: Callable[..., Any] | None = None,
                     user_data: Any = None,
                     **kwargs: Any):

        task_ = Task(func(self, *args, **kwargs))
        task_.set_timeout(timeout)
        app.register_task(self, task_)
        task_.set_finalize_func(app.remove_task, id(self))
        task_.set_user_data(user_data)
        if callback is not None:
            task_.add_done_callback(callback)
        task_.start()
        return task_
    return func_wrapper


def prepare_stanza(stanza: Message, plaintext: str) -> None:
    delete_nodes(stanza, 'encrypted', Namespace.OMEMO_TEMP)
    delete_nodes(stanza, 'body')
    stanza.setBody(plaintext)


def delete_nodes(stanza: Message,
                 name: str,
                 namespace: str | None = None
                 ) -> None:

    nodes = stanza.getTags(name, namespace=namespace)
    for node in nodes:
        stanza.delChild(node)


def convert_message_type(type_: MessageType) -> str:
    if type_ in (MessageType.CHAT, MessageType.PM):
        return 'chat'
    return 'groupchat'


def get_chat_type_and_direction(
    muc_data: MUCData | None, own_jid: JID, properties: MessageProperties
) -> tuple[MessageType, ChatDirection]:

    if properties.type.is_groupchat:
        assert muc_data is not None
        direction = ChatDirection.INCOMING
        if muc_data.occupant_id is not None:
            if muc_data.occupant_id == properties.occupant_id:
                direction = ChatDirection.OUTGOING

        elif muc_data.nick == properties.jid.resource:
            direction = ChatDirection.OUTGOING

        return MessageType.GROUPCHAT, direction

    assert properties.from_ is not None
    if properties.from_.bare_match(own_jid):
        direction = ChatDirection.OUTGOING
    else:
        direction = ChatDirection.INCOMING

    if properties.is_muc_pm:
        return MessageType.PM, direction

    if not properties.type.is_chat:
        raise ValueError('Invalid message type', properties.type)

    return MessageType.CHAT, direction
