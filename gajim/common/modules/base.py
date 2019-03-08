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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from typing import Any  # pylint: disable=unused-import
from typing import Dict  # pylint: disable=unused-import
from typing import List  # pylint: disable=unused-import

import logging
from functools import partial
from unittest.mock import Mock

import nbxmpp
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.modules.util import LogAdapter

log = logging.getLogger('gajim.c.m.base')


class BaseModule:

    _nbxmpp_extends = ''
    _nbxmpp_methods = []  # type: List[str]

    def __init__(self, con, logger=None):
        self._con = con
        self._account = con.name
        if logger is not None:
            self._log = LogAdapter(logger, {'account': self._account})
        self._nbxmpp_callbacks = {}  # type: Dict[str, Any]
        self._stored_publish = None  # type: Callable
        self.handlers = []  # type: List[str]

    def __getattr__(self, key):
        if key not in self._nbxmpp_methods:
            raise AttributeError
        if not app.account_is_connected(self._account):
            log.warning('Account %s not connected, cant use %s',
                        self._account, key)
            return

        module = self._con.connection.get_module(self._nbxmpp_extends)

        callback = self._nbxmpp_callbacks.get(key)
        if callback is None:
            return getattr(module, key)
        return partial(getattr(module, key), callback=callback)

    def _nbxmpp(self, module_name=None):
        if not app.account_is_connected(self._account):
            log.warning('Account %s not connected, cant use nbxmpp method',
                        self._account)
            return Mock()

        if module_name is None:
            return self._con.connection
        return self._con.connection.get_module(module_name)

    def _register_callback(self, method, callback):
        self._nbxmpp_callbacks[method] = callback

    def _register_pubsub_handler(self, callback):
        handler = StanzaHandler(name='message',
                                callback=callback,
                                ns=nbxmpp.NS_PUBSUB_EVENT,
                                priority=49)
        self.handlers.append(handler)

    def send_stored_publish(self):
        if self._stored_publish is None:
            return
        log.info('Send stored publish')
        self._stored_publish()
