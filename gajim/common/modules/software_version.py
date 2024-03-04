# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0092: Software Version

from __future__ import annotations

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common.helpers import get_os_info
from gajim.common.modules.base import BaseModule


class SoftwareVersion(BaseModule):

    _nbxmpp_extends = 'SoftwareVersion'
    _nbxmpp_methods = [
        'set_software_version',
        'request_software_version',
        'disable',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

    def set_enabled(self, enabled: bool) -> None:
        if enabled and app.settings.get_account_setting(self._account,
                                                        'send_os_info'):
            os_info = get_os_info()
        else:
            os_info = None
        self._nbxmpp('SoftwareVersion').set_software_version(
            'Gajim', app.version, os_info)
        self._nbxmpp('SoftwareVersion').set_allow_reply_func(self._allow_reply)

    def _allow_reply(self, jid: JID) -> bool:
        item = self._con.get_module('Roster').get_item(jid.bare)
        if item is None:
            return False

        contact = self._get_contact(JID.from_string(jid.bare))
        return contact.is_subscribed
