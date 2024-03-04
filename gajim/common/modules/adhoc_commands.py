# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gajim.common import types
from gajim.common.modules.base import BaseModule


class AdHocCommands(BaseModule):

    _nbxmpp_extends = 'AdHoc'
    _nbxmpp_methods = [
        'request_command_list',
        'execute_command',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
