# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.settings import GajimPreferencesGroup


class ContactSettings(GajimPreferencesGroup):
    def __init__(self, account: str, jid: JID) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="main",
            account=account,
            jid=str(jid),
            title=_("Privacy"),
        )

        chat_state = {
            "disabled": _("Disabled"),
            "composing_only": _("Composing Only"),
            "all": _("All Chat States"),
        }

        settings: list[Setting] = [
            Setting(
                SettingKind.DROPDOWN,
                _("Send Chat State"),
                SettingType.CONTACT,
                "send_chatstate",
                props={"data": chat_state},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Read Receipts"),
                SettingType.CONTACT,
                "send_marker",
                desc=_("Send and receive read receipts"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Link Preview"),
                SettingType.CONTACT,
                "enable_link_preview",
                callback=app.window.reload_view,
            ),
        ]

        for setting in settings:
            self.add_setting(setting)
