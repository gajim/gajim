# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common.const import THRESHOLD_OPTIONS
from gajim.common.i18n import _

from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.settings import SettingsBox


class GroupChatSettings(SettingsBox):
    def __init__(self, account: str, jid: JID) -> None:
        SettingsBox.__init__(self, account, str(jid))
        self.add_css_class("border")
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_size_request(700, -1)
        self.set_valign(Gtk.Align.START)
        self.set_halign(Gtk.Align.CENTER)

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
                _("Send Chat Markers"),
                SettingType.GROUP_CHAT,
                "send_marker",
                desc=_("Let others know if you read up to this point"),
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Sync Threshold"),
                SettingType.GROUP_CHAT,
                "sync_threshold",
                props={"data": THRESHOLD_OPTIONS},
            ),
        ]

        for setting in settings:
            self.add_setting(setting)
        self.update_states()
