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
        if enabled:
            if not app.settings.get_account_setting(self._account,
                                                    'send_os_info'):
                return
            self._nbxmpp('SoftwareVersion').set_software_version(
                'Gajim', app.version, get_os_info())
        else:
            self._nbxmpp('SoftwareVersion').disable()


def get_instance(*args, **kwargs):
    return SoftwareVersion(*args, **kwargs), 'SoftwareVersion'
