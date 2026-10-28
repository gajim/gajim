# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import unittest

from nbxmpp import JID

from gajim.common.settings.backend import Settings
from gajim.common.settings.schema import BooleanSetting
from gajim.common.settings.schema import SettingSchema
from gajim.common.settings.schema import SettingType
from gajim.common.settings.schema import StringSetting

_SCHEMA_DEF = [
    StringSetting(
        key="encryption_default", type=SettingType.APP, default="app-default"
    ),
    StringSetting(
        key="encryption_default", type=SettingType.ACCOUNT, default="account-default"
    ),
    StringSetting(key="encryption", type=SettingType.CONTACT, context_default=True),
    BooleanSetting(key="send_marker_default", type=SettingType.APP, default=True),
    BooleanSetting(
        key="send_marker", type=SettingType.CONTACT, default=False, context_default=True
    ),
]


class SettingsTest(unittest.TestCase):
    def setUp(self) -> None:

        self._account = "testacc1"
        self._contact_jid = JID.from_string("jid@domain.net")

        self._schema = SettingSchema(_SCHEMA_DEF)

        self._settings = Settings(in_memory=True, schema=self._schema)
        self._settings.init()
        self._settings.add_account("testacc1")

    def test_default_fallback(self) -> None:
        value = self._settings.get_contact_setting(
            self._account, self._contact_jid, "encryption"
        )
        self.assertEqual(value, "account-default")

        value = self._settings.get_contact_setting(
            self._account, self._contact_jid, "send_marker"
        )
        self.assertIs(value, True)
