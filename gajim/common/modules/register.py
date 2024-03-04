# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0077: In-Band Registration

from __future__ import annotations

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import DiscoInfo

from gajim.common import types
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

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.supported = False

    def pass_disco(self, info: DiscoInfo) -> None:
        self.supported = Namespace.REGISTER in info.features
