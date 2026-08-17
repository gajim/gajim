# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal

import sys

from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common.events import StyleChanged
from gajim.common.events import ThemeUpdate
from gajim.common.i18n import _
from gajim.common.settings.types import AppBoolSettings

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.plugins import Plugins
from gajim.gtk.settings.page import GajimPreferencePage
from gajim.gtk.settings.page import GajimPreferencesGroup
from gajim.gtk.settings.row import DropDownSetting
from gajim.gtk.settings.row import GenericSetting
from gajim.gtk.settings.row import register_rows
from gajim.gtk.settings.row import SpinSetting
from gajim.gtk.settings.row import SwitchSetting
from gajim.gtk.util.misc import open_file
from gajim.gtk.util.window import get_app_window
from gajim.gtk.util.window import open_window


class ShowInTaskbar(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_show_in_taskbar

    @staticmethod
    def _on_show_in_taskbar(value: bool, *args: Any) -> None:
        app.window.set_skip_taskbar_hint(not value)


class ShowHeaderBar(SwitchSetting):
    def __post_init__(self) -> None:
        self.enabled_func = lambda: sys.platform not in ("win32", "darwin")


class WindowBehaviourGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="window-behaviour",
            title=_("Behaviour of Application Window"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("window-behaviour"))


class PluginSettingsGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="plugin-settings",
            title=_("Plugin Settings"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("plugin-settings"))


class UseSpeller(SwitchSetting):
    def __post_init__(self) -> None:
        self.enabled_func = self._speller_available

    @staticmethod
    def _speller_available() -> bool:
        return app.is_installed("SPELLING")


class GeneralGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="general",
            title=_("General"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("general"))


class EnableLinkPreview(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = (app.window.reload_view,)


class ChatsGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="chats",
            title=_("Chats"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("chats"))


class SortByShowInMuc(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_sort_by_show_in_muc

    @staticmethod
    def _on_sort_by_show_in_muc(_value: bool, *args: Any) -> None:
        roster = app.window.get_control().get_group_chat_roster()
        roster.invalidate_sort()


class ShowStatusMsgInRoster(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_show_status_in_roster

    @staticmethod
    def _on_show_status_in_roster(_value: bool, *args: Any) -> None:
        roster = app.window.get_control().get_group_chat_roster()
        roster.invalidate_sort()


class PrintJoinLeft(SwitchSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Reset"),
            "button-tooltip": _("Reset all group chats to the current default value"),
            "button-style": "destructive-action",
            "button-callback": self._reset_join_left,
        }

        self._add_action_button(props)

    @staticmethod
    def _reset_join_left(button: Gtk.Button) -> None:
        button.set_sensitive(False)

        def _context_match_func(account: str, jid: JID) -> Literal["public"]:
            # print_join_left has no context dependent setting
            # so the context does not matter
            return "public"

        app.settings.set_group_chat_settings(
            None, "print_join_left", None, _context_match_func
        )


class PrintStatus(SwitchSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Reset"),
            "button-tooltip": _("Reset all group chats to the current default value"),
            "button-style": "destructive-action",
            "button-callback": self._reset_print_status,
        }

        self._add_action_button(props)

    @staticmethod
    def _reset_print_status(button: Gtk.Button) -> None:
        button.set_sensitive(False)

        def _context_match_func(account: str, jid: JID) -> Literal["public"]:
            # print_status has no context dependent setting
            # so the context does not matter
            return "public"

        app.settings.set_group_chat_settings(
            None, "print_status", None, _context_match_func
        )


class GroupChatsGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="group-chats",
            title=_("Group Chats"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("group-chats"))


class FilePreviewGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="file-preview",
            title=_("File Preview"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("file-preview"))


class SystemNotificationsGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="system-notifications",
            title=_("System"),
        )

        self.bind_settings_model(
            app.app.settings.get_single_model("system-notifications")
        )


class NotificationsChatsGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="notifications-chats",
            title=_("Chats"),
        )

        self.bind_settings_model(
            app.app.settings.get_single_model("notifications-chats")
        )


class NotificationsGroupChatsGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="notifications-group-chats",
            title=_("Group Chats"),
        )

        self.bind_settings_model(
            app.app.settings.get_single_model("notifications-group-chats")
        )


class EnableSounds(SwitchSetting):
    def __post_init__(self) -> None:
        props = {
            "button-icon-name": "lucide-settings-symbolic",
            "button-callback": self._on_manage_sounds,
        }

        self._add_action_button(props)

    @staticmethod
    def _on_manage_sounds(_button: Gtk.Button) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("ManageSounds", transient_for=window)


class SoundsGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="sounds",
            title=_("Sounds"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("sounds"))


class StatusMessageGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="status-message",
            title=_("Ask For Status Message on…"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("status-message"))


class AutomaticStatusGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="automatic-status",
            title=_("Automatic Status Change"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("automatic-status"))


class AutoAwayGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(self, key="auto-away")

        self.bind_settings_model(app.app.settings.get_single_model("auto-away"))


class AutoExtendedAwayGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(self, key="auto-extended-away")

        self.bind_settings_model(
            app.app.settings.get_single_model("auto-extended-away")
        )


class AppFontSize(SpinSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_app_font_size_changed

    @staticmethod
    def _on_app_font_size_changed(_value: float, *args: Any) -> None:
        app.css_config.apply_app_font_size()


class DarkTheme(DropDownSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_dark_theme

    @staticmethod
    def _on_dark_theme(value: str, *args: Any) -> None:
        app.css_config.set_dark_theme(int(value))
        app.css_config.reload_css()
        app.ged.raise_event(StyleChanged())


class RosterTheme(DropDownSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_theme_changed
        props = {
            "button-icon-name": "lucide-settings-symbolic",
            "button-callback": self._on_edit_themes,
        }

        self._add_action_button(props)

    def _on_edit_themes(self, _button: Gtk.Button) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("Themes", transient=window)

    def _on_theme_changed(self, value: str, *args: Any) -> None:
        app.ged.remove_event_handler("theme-update", ged.GUI1, self._on_theme_update)

        app.css_config.change_theme(value)
        app.ged.raise_event(ThemeUpdate())

        app.ged.register_event_handler("theme-update", ged.GUI1, self._on_theme_update)

    def _on_theme_update(self, *args: Any) -> None:
        dropdown_row = cast(DropDownSetting, self.get_setting("roster_theme"))
        dropdown_row.update_entries(self._get_theme_items())
        dropdown_row.select_key(app.settings.get("roster_theme"))


class ThemesGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="themes",
            title=_("Themes"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("themes"))


class AudioGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="audio",
            title=_("Audio"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("audio"))


class GlobalProxy(DropDownSetting):
    def __post_init__(self) -> None:
        props = {
            "button-icon-name": "lucide-settings-symbolic",
            "button-callback": self._on_proxy_edit,
        }
        self._add_action_button(props)

    @staticmethod
    def _on_proxy_edit(*args: Any) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("ManageProxies", transient_for=window)


class ResetHints(GenericSetting):
    def __post_init__(self) -> None:

        self._hints_list: list[AppBoolSettings] = [
            "show_help_start_chat",
        ]

        props = {
            "button-text": _("Reset"),
            "button-style": "destructive-action",
            "button-callback": self._on_reset_hints,
            "button-sensitive": self._check_hints_reset(),
        }
        self._add_action_button(props)

    def _on_reset_hints(self, button: Gtk.Button) -> None:
        for hint in self._hints_list:
            app.settings.set(hint, True)
        button.set_sensitive(False)

    def _check_hints_reset(self) -> bool:
        return any(app.settings.get(hint) is False for hint in self._hints_list)


class PurgeChatHistory(GenericSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Purge"),
            "button-style": "destructive-action",
            "button-callback": self._on_purge_history_clicked,
        }
        self._add_action_button(props)

    @staticmethod
    def _on_purge_history_clicked(button: Gtk.Button) -> None:
        def _on_response() -> None:
            button.set_sensitive(False)
            app.storage.archive.remove_all_history()
            app.app.start_shutdown()

        ConfirmationAlertDialog(
            _("Purge all Chat History?"),
            _(
                "Do you really want to remove all chat messages from Gajim?\n"
                "Warning: This can’t be undone!\n"
                "Gajim will quit afterwards."
            ),
            confirm_label=_("_Purge"),
            appearance="destructive",
            callback=_on_response,
        )


class MiscellaneousGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="miscellaneous",
            title=_("Miscellaneous"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("miscellaneous"))

    @staticmethod
    def _get_proxies() -> dict[str, str]:
        proxies = {"": _("System")}
        proxies.update({proxy: proxy for proxy in app.settings.get_proxies()})
        proxies["no-proxy"] = _("No Proxy")
        return proxies

    def update_proxy_list(self) -> None:
        dropdown_row = cast(DropDownSetting, self.get_setting("global_proxy"))
        dropdown_row.update_entries(self._get_proxies())


class DebugLogging(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = (self._on_debug_logging,)
        props = {
            "button-icon-name": "lucide-folder-symbolic",
            "button-callback": self._on_open_debug_logs,
        }
        self._add_action_button(props)

    @staticmethod
    def _on_debug_logging(value: bool, *args: Any) -> None:
        app.set_debug_mode(value)

    @staticmethod
    def _on_open_debug_logs(*args: Any) -> None:
        open_file(configpaths.get("DEBUG"))


class DebugConsole(GenericSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Open"),
            "button-callback": self._on_debug,
        }
        self._add_action_button(props)

    @staticmethod
    def _on_debug(*args: Any) -> None:
        open_window("DebugConsoleWindow")


class AdvancedConfigEditor(GenericSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Open"),
            "button-callback": self._on_advanced_config_editor,
        }
        self._add_action_button(props)

    @staticmethod
    def _on_advanced_config_editor(*args: Any) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("AdvancedConfig", transient_for=window)


class AdvancedGroup(GajimPreferencesGroup):
    def __init__(self) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="advanced",
            title=_("Advanced Settings"),
        )

        self.bind_settings_model(app.app.settings.get_single_model("advanced"))


class GeneralPage(GajimPreferencePage):
    key = "general"
    icon_name = "lucide-app-window-symbolic"
    label = _("General")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("General"),
            groups=[WindowBehaviourGroup],
        )


class ChatsPage(GajimPreferencePage):
    key = "chats"
    icon_name = "lucide-message-circle-symbolic"
    label = _("Chats")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Chats"),
            groups=[
                GeneralGroup,
                ChatsGroup,
                GroupChatsGroup,
                FilePreviewGroup,
            ],
        )


class VisualNotificationsPage(GajimPreferencePage):
    key = "system-notifications"
    icon_name = "lucide-bell-symbolic"
    label = _("Notifications")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Notifications"),
            groups=[
                SystemNotificationsGroup,
                NotificationsChatsGroup,
                NotificationsGroupChatsGroup,
                SoundsGroup,
            ],
        )


class StatusPage(GajimPreferencePage):
    key = "status"
    icon_name = "lucide-megaphone-symbolic"
    label = _("Status")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Status"),
            groups=[
                StatusMessageGroup,
                AutomaticStatusGroup,
            ],
        )


class StylePage(GajimPreferencePage):
    key = "style"
    icon_name = "lucide-palette-symbolic"
    label = _("Style")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Style"),
            groups=[ThemesGroup],
        )


class AudioVideoPage(GajimPreferencePage):
    key = "audio-video"
    icon_name = "lucide-mic-symbolic"
    label = _("Audio")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Audio"),
            groups=[
                AudioGroup,
            ],
        )


class PluginsPage(GajimPreferencePage):
    key = "plugins"
    icon_name = "lucide-package-symbolic"
    label = _("Plugins")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Plugins"),
            groups=[
                PluginSettingsGroup,
                Plugins,
            ],
        )


class AdvancedPage(GajimPreferencePage):
    key = "advanced"
    icon_name = "lucide-wrench-symbolic"
    label = _("Advanced")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Advanced"),
            groups=[
                MiscellaneousGroup,
                AdvancedGroup,
            ],
        )


class AutoAwayPage(GajimPreferencePage):
    key = "auto-away"

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Auto Away"),
            groups=[AutoAwayGroup],
        )


class AutoExtendedAwayPage(GajimPreferencePage):
    key = "auto-extended-away"

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Auto Not Available"),
            groups=[AutoExtendedAwayGroup],
        )


register_rows(
    {
        "show-in-taskbar": ShowInTaskbar,
        "show-header-bar": ShowHeaderBar,
        "use-speller": UseSpeller,
        "enable-link-preview": EnableLinkPreview,
        "sort_by_show_in_muc": SortByShowInMuc,
        "show_status_msgs_in_roster": ShowStatusMsgInRoster,
        "gc_print_join_left_default": PrintJoinLeft,
        "gc_print_status_default": PrintStatus,
        "gc_enable_link_preview_default": EnableLinkPreview,
        "enable-sounds": EnableSounds,
        "app-font-size": AppFontSize,
        "dark-theme": DarkTheme,
        "roster-theme": RosterTheme,
        "global-proxy": GlobalProxy,
        "reset-hints": ResetHints,
        "purge-chat-history": PurgeChatHistory,
        "debug-logging": DebugLogging,
        "debug-console": DebugConsole,
        "advanced-config-editor": AdvancedConfigEditor,
    }
)
