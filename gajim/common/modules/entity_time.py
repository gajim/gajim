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

# XEP-0202: Entity Time

from gajim.common import app
from gajim.common.modules.base import BaseModule


class EntityTime(BaseModule):

    _nbxmpp_extends = 'EntityTime'
    _nbxmpp_methods = [
        'request_entity_time',
        'enable',
        'disable',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = []

    def set_enabled(self, enabled):
        if not enabled:
            self._nbxmpp('EntityTime').disable()
            return

        if app.settings.get_account_setting(self._account, 'send_time_info'):
            self._nbxmpp('EntityTime').enable()


def get_instance(*args, **kwargs):
    return EntityTime(*args, **kwargs), 'EntityTime'
