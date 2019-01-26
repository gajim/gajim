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

import logging
from functools import partial
from unittest.mock import Mock

from gajim.common import app

log = logging.getLogger('gajim.c.m.base')


class BaseModule:

    _nbxmpp_extends = ''
    _nbxmpp_methods = []

    def __init__(self, con):
        self._con = con
        self._account = con.name
        self._nbxmpp_callbacks = {}
        self.handlers = []

    def __getattr__(self, key):
        if key not in self._nbxmpp_methods:
            raise AttributeError
        if not app.account_is_connected(self._account):
            log.warning('Account %s not connected, cant use %s',
                        self._account, key)
            return

        module = self._con.connection.get_module(self._nbxmpp_extends)

        return partial(getattr(module, key),
                       callback=self._nbxmpp_callbacks.get(key))

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
