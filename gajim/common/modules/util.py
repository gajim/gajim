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

# Util module

from __future__ import annotations

from typing import Any
from typing import Optional
from typing import Union

import logging
from functools import partial
from functools import wraps
from logging import LoggerAdapter

import nbxmpp
from nbxmpp.const import MessageType
from nbxmpp.protocol import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import EMEData
from nbxmpp.structs import MessageProperties
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import types
from gajim.common.const import EME_MESSAGES
from gajim.common.const import KindConstant
from gajim.common.events import MessageUpdated
from gajim.common.modules.misc import parse_correction


def from_xs_boolean(value: Union[str, bool]) -> bool:
    if isinstance(value, bool):
        return value

    if value in ('1', 'true', 'True'):
        return True

    if value in ('0', 'false', 'False', ''):
        return False

    raise ValueError(f'Cant convert {value} to python boolean')


def to_xs_boolean(value: Union[bool, None]) -> str:
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


def as_task(func):
    @wraps(func)
    def func_wrapper(self,
                     *args,
                     timeout=None,
                     callback=None,
                     user_data=None,
                     **kwargs):

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


def check_if_message_correction(properties: MessageProperties,
                                account: str,
                                jid: JID,
                                msgtxt: str,
                                kind: KindConstant,
                                timestamp: float,
                                logger: LoggerAdapter[logging.Logger]) -> bool:

    correct_id = parse_correction(properties)
    if correct_id is None:
        return False

    if properties.type not in (MessageType.GROUPCHAT, MessageType.CHAT):
        logger.warning('Ignore correction with message type: %s',
                       properties.type)
        return False

    nickname = None
    if properties.type.is_groupchat:
        if jid.is_bare:
            logger.warning(
                'Ignore correction from bare groupchat jid: %s', jid)
            return False

        nickname = jid.resource
        jid = jid.new_as_bare()

    elif not properties.is_muc_pm:
        jid = jid.new_as_bare()

    successful = app.storage.archive.try_message_correction(
        account,
        jid,
        nickname,
        msgtxt,
        correct_id,
        kind,
        timestamp)

    if not successful:
        logger.info('Message correction not successful')
        return False

    nickname = properties.muc_nickname or properties.nickname

    event = MessageUpdated(account=account,
                           jid=jid,
                           msgtxt=msgtxt,
                           nickname=nickname,
                           properties=properties,
                           correct_id=correct_id)

    app.ged.raise_event(event)
    return True


def prepare_stanza(stanza: Message, plaintext: str) -> None:
    delete_nodes(stanza, 'encrypted', Namespace.OMEMO_TEMP)
    delete_nodes(stanza, 'body')
    stanza.setBody(plaintext)


def delete_nodes(stanza: Message,
                 name: str,
                 namespace: Optional[str] = None
                 ) -> None:

    nodes = stanza.getTags(name, namespace=namespace)
    for node in nodes:
        stanza.delChild(node)
