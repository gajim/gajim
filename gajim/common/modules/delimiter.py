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

# XEP-0083: Nested Roster Groups


from nbxmpp.errors import is_error

from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


class Delimiter(BaseModule):

    _nbxmpp_extends = 'Delimiter'
    _nbxmpp_methods = [
        'request_delimiter',
        'set_delimiter'
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self.available = False
        self.delimiter = '::'

    @as_task
    def get_roster_delimiter(self):
        _task = yield

        delimiter = yield self.request_delimiter()
        if is_error(delimiter) or delimiter is None:
            result = yield self.set_delimiter(self.delimiter)
            if is_error(result):
                self._con.connect_machine()
                return

            delimiter = self.delimiter

        self.delimiter = delimiter
        self.available = True
        self._con.connect_machine()


def get_instance(*args, **kwargs):
    return Delimiter(*args, **kwargs), 'Delimiter'
