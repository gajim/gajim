# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0292: vCard4 Over XMPP

from __future__ import annotations

from gajim.common import types
from gajim.common.modules.base import BaseModule


class VCard4(BaseModule):

    _nbxmpp_extends = 'VCard4'
    _nbxmpp_methods = [
        'request_vcard',
        'set_vcard',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
