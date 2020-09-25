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

from typing import Union

from logging import LoggerAdapter
from functools import wraps
from functools import partial

from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import EME_MESSAGES


def from_xs_boolean(value: Union[str, bool]) -> bool:
    if isinstance(value, bool):
        return value

    if value in ('1', 'true', 'True'):
        return True

    if value in ('0', 'false', 'False', ''):
        return False

    raise ValueError('Cant convert %s to python boolean' % value)


def to_xs_boolean(value: Union[bool, None]) -> str:
    # Convert to xs:boolean ('true', 'false')
    # from a python boolean (True, False) or None
    if value is True:
        return 'true'

    if value is False:
        return 'false'

    if value is None:
        return 'false'

    raise ValueError(
        'Cant convert %s to xs:boolean' % value)


def event_node(node):
    def event_node_decorator(func):
        @wraps(func)
        def func_wrapper(self, _con, _stanza, properties):
            if not properties.is_pubsub_event:
                return
            if properties.pubsub_event.node != node:
                return
            func(self, _con, _stanza, properties)

        return func_wrapper
    return event_node_decorator


def store_publish(func):
    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        # pylint: disable=protected-access
        if not app.account_is_connected(self._account):
            self._stored_publish = partial(func, self, *args, **kwargs)
            return None
        return func(self, *args, **kwargs)
    return func_wrapper


def get_eme_message(eme_data):
    try:
        return EME_MESSAGES[eme_data.namespace]
    except KeyError:
        return EME_MESSAGES['fallback'] % eme_data.name


class LogAdapter(LoggerAdapter):
    def process(self, msg, kwargs):
        return '(%s) %s' % (self.extra['account'], msg), kwargs


def as_task(func):
    @wraps(func)
    def func_wrapper(self, *args, callback=None, user_data=None, **kwargs):
        task_ = Task(func(self, *args, **kwargs))
        app.register_task(self, task_)
        task_.set_finalize_func(app.remove_task, id(self))
        task_.set_user_data(user_data)
        if callback is not None:
            task_.add_done_callback(callback)
        task_.start()
        return task_
    return func_wrapper
