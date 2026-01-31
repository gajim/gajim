# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.const import THRESHOLD_OPTIONS
from gajim.common.i18n import _

from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.settings import GajimPreferencesGroup


class GroupChatSettings(GajimPreferencesGroup):
    def __init__(self, account: str, jid: JID) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="main",
            account=account,
            jid=str(jid),
        )

        chat_state = {
            "disabled": _("Disabled"),
            "composing_only": _("Composing Only"),
            "all": _("All Chat States"),
        }

        settings: list[Setting] = [
            Setting(
                SettingKind.SWITCH,
                _("Show Join/Leave"),
                SettingType.GROUP_CHAT,
                "print_join_left",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Status Changes"),
                SettingType.GROUP_CHAT,
                "print_status",
                desc=_('For example: "Julia is now online"'),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Notify on all Messages"),
                SettingType.GROUP_CHAT,
                "notify_on_all_messages",
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Send Chat State"),
                SettingType.GROUP_CHAT,
                "send_chatstate",
                props={"data": chat_state},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Read Receipts"),
                SettingType.GROUP_CHAT,
                "send_marker",
                desc=_("Send and receive read receipts"),
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Sync Threshold"),
                SettingType.GROUP_CHAT,
                "sync_threshold",
                props={"data": THRESHOLD_OPTIONS},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Link Preview"),
                SettingType.GROUP_CHAT,
                "enable_link_preview",
                callback=app.window.reload_view,
            ),
        ]

        for setting in settings:
            self.add_setting(setting)
