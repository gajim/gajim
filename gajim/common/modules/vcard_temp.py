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

# XEP-0054: vcard-temp

from nbxmpp.namespaces import Namespace

from gajim.common.modules.base import BaseModule


class VCardTemp(BaseModule):

    _nbxmpp_extends = 'VCardTemp'
    _nbxmpp_methods = [
        'request_vcard',
        'set_vcard',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self._own_vcard = None
        self.supported = False

    def pass_disco(self, info):
        if Namespace.VCARD not in info.features:
            return

        self.supported = True
        self._log.info('Discovered vcard-temp: %s', info.jid)


def get_instance(*args, **kwargs):
    return VCardTemp(*args, **kwargs), 'VCardTemp'
