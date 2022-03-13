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

# XEP-0092: Software Version

from gajim.common import app
from gajim.common.helpers import get_os_info
from gajim.common.modules.base import BaseModule


class SoftwareVersion(BaseModule):

    _nbxmpp_extends = 'SoftwareVersion'
    _nbxmpp_methods = [
        'set_software_version',
        'request_software_version',
        'disable',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

    def set_enabled(self, enabled):
        if enabled and app.settings.get_account_setting(self._account,
                                                        'send_os_info'):
            os_info = get_os_info()
        else:
            os_info = None
        self._nbxmpp('SoftwareVersion').set_software_version(
            'Gajim', app.version, os_info)
        self._nbxmpp('SoftwareVersion').set_allow_reply_func(self._allow_reply)

    def _allow_reply(self, jid):
        item = self._con.get_module('Roster').get_item(jid.bare)
        if item is None:
            return False

        contact = self._get_contact(jid.bare)
        return contact.is_subscribed
