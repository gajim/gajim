# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0199: XMPP Ping

from __future__ import annotations

import time
from collections.abc import Generator

from nbxmpp.errors import is_error
from nbxmpp.structs import CommonResult

from gajim.common import app
from gajim.common import types
from gajim.common.events import PingError
from gajim.common.events import PingReply
from gajim.common.events import PingSent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


class Ping(BaseModule):

    _nbxmpp_extends = 'Ping'
    _nbxmpp_methods = [
        'ping',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = []

    @as_task
    def send_ping(self,
                  contact: types.ContactT
                  ) -> Generator[CommonResult, None, None]:
        _task = yield  # noqa: F841

        if not app.account_is_available(self._account):
            return

        jid = contact.jid

        self._log.info('Send ping to %s', str(jid))

        app.ged.raise_event(PingSent(account=self._account, contact=contact))

        ping_time = time.time()

        response = yield self.ping(jid, timeout=10)
        if is_error(response):
            app.ged.raise_event(PingError(
                account=self._account,
                contact=contact,
                error=str(response)))
            return

        diff = round(time.time() - ping_time, 2)
        self._log.info('Received pong from %s after %s seconds',
                       response.jid, diff)

        app.ged.raise_event(PingReply(account=self._account,
                                      contact=contact,
                                      seconds=diff))
