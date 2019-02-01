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

from functools import wraps
from functools import partial

from gajim.common import app


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
        if not app.account_is_connected(self._account):
            self._stored_publish = partial(func, self, *args, **kwargs)
            return
        return func(self, *args, **kwargs)
    return func_wrapper
