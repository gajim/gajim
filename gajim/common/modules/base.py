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

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.nec import EventHelper
from gajim.common.modules.util import LogAdapter


class BaseModule(EventHelper):

    _nbxmpp_extends = ''
    _nbxmpp_methods = []  # type: List[str]

    def __init__(self, con, *args, plugin=False, **kwargs):
        EventHelper.__init__(self)
        self._con = con
        self._account = con.name
        self._log = self._set_logger(plugin)
        self._nbxmpp_callbacks = {}  # type: Dict[str, Any]
        self._stored_publish = None  # type: Callable
        self.handlers = []  # type: List[str]

    def _set_logger(self, plugin):
        logger_name = 'gajim.c.m.%s'
        if plugin:
            logger_name = 'gajim.p.%s'
        logger_name = logger_name % self.__class__.__name__.lower()
        logger = logging.getLogger(logger_name)
        return LogAdapter(logger, {'account': self._account})

    def __getattr__(self, key):
        if key not in self._nbxmpp_methods:
            raise AttributeError(
                "attribute '%s' is neither part of object '%s' "
                " nor declared in '_nbxmpp_methods'" % (
                    key, self.__class__.__name__))

        if not app.account_is_connected(self._account):
            self._log.warning('Account not connected, cant use %s', key)
            return None

        module = self._con.connection.get_module(self._nbxmpp_extends)

        callback = self._nbxmpp_callbacks.get(key)
        if callback is None:
            return getattr(module, key)
        return partial(getattr(module, key), callback=callback)

    def _nbxmpp(self, module_name=None):
        if not app.account_is_connected(self._account):
            self._log.warning('Account not connected, cant use nbxmpp method')
            return Mock()

        if module_name is None:
            return self._con.connection
        return self._con.connection.get_module(module_name)

    def _register_callback(self, method, callback):
        self._nbxmpp_callbacks[method] = callback

    def _register_pubsub_handler(self, callback):
        handler = StanzaHandler(name='message',
                                callback=callback,
                                ns=Namespace.PUBSUB_EVENT,
                                priority=49)
        self.handlers.append(handler)

    def send_stored_publish(self):
        if self._stored_publish is None:
            return
        self._log.info('Send stored publish')
        self._stored_publish()  # pylint: disable=not-callable

    def cleanup(self):
        self.unregister_events()
