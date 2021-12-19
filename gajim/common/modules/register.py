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

# XEP-0077: In-Band Registration


from nbxmpp.namespaces import Namespace

from gajim.common.modules.base import BaseModule


class Register(BaseModule):

    _nbxmpp_extends = 'Register'
    _nbxmpp_methods = [
        'unregister',
        'change_password',
        'change_password_with_form',
        'request_register_form',
        'submit_register_form',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.supported = False

    def pass_disco(self, info):
        self.supported = Namespace.REGISTER in info.features
