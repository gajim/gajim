# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging
import sys
from dataclasses import dataclass

from gi.repository import Adw
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common.const import THRESHOLD_OPTIONS
from gajim.common.events import StyleChanged
from gajim.common.events import ThemeUpdate
from gajim.common.i18n import _
from gajim.common.setting_values import BoolSettings

# from gajim.common.util.av import AudioOutputManager
from gajim.common.util.av import AudioInputManager

# from gajim.common.util.av import VideoInputManager
from gajim.common.util.uri import open_directory
from gajim.common.util.version import package_version

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.plugins import Plugins
from gajim.gtk.preview import PREVIEW_ACTIONS
from gajim.gtk.settings import DropDownSetting
from gajim.gtk.settings import SettingsBox
from gajim.gtk.settings import SettingsDialog
from gajim.gtk.sidebar_switcher import SideBarSwitcher
from gajim.gtk.util.window import get_app_window
from gajim.gtk.util.window import open_window

# from gajim.gtk.video_preview import VideoPreview
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.preferences")


@dataclass
class PreferencesPageData:
    name: str
    title: str
    icon_name: str
    groups: list[PreferencesGroupData | type[Adw.PreferencesGroup]]
    banner: PreferencesPageBannerData | None = None


@dataclass
class PreferencesPageBannerData:
    revealed: bool
    title: str
    button_label: str | None
    action_name: str | None


@dataclass
class PreferencesGroupData:
    name: str
    title: str
    widget: Any


class Preferences(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="Preferences",
            title=_("Preferences"),
            default_width=900,
            default_height=650,
            add_window_padding=False,
            header_bar=False,
        )

        # self._video_preview: VideoPreview | None = None
        self._prefs: dict[str, PreferenceBox] = {}

        preferences = [
            PreferencesPageData(
                name="general",
                title=_("General"),
                icon_name="computer-symbolic",
                groups=[
                    PreferencesGroupData(
                        name="window_behaviour",
                        title=_("Behaviour of Application Window"),
                        widget=WindowBehaviour,
                    ),
                ],
            ),
            PreferencesPageData(
                name="chats",
                title=_("Chats"),
                icon_name="user-available-symbolic",
                groups=[
                    PreferencesGroupData(
                        name="general", title=_("General"), widget=General
                    ),
                    PreferencesGroupData(name="chats", title=_("Chats"), widget=Chats),
                    PreferencesGroupData(
                        name="group_chats",
                        title=_("Group Chats"),
                        widget=GroupChats,
                    ),
                    PreferencesGroupData(
                        name="file_preview",
                        title=_("File Preview"),
                        widget=FilePreview,
                    ),
                ],
            ),
            PreferencesPageData(
                name="notifications",
                title=_("Notifications"),
                icon_name="mail-unread-symbolic",
                groups=[
                    PreferencesGroupData(
                        name="visual_notifications",
                        title=_("Visual Notifications"),
                        widget=VisualNotifications,
                    ),
                    PreferencesGroupData(
                        name="sounds", title=_("Sounds"), widget=Sounds
                    ),
                ],
            ),
            PreferencesPageData(
                name="status",
                title=_("Status"),
                icon_name="user-status-pending-symbolic",
                groups=[
                    PreferencesGroupData(
                        name="status_message",
                        title=_("Ask For Status Message on…"),
                        widget=StatusMessage,
                    ),
                    PreferencesGroupData(
                        name="automatic_status",
                        title=_("Automatic Status Change"),
                        widget=AutomaticStatus,
                    ),
                ],
            ),
            PreferencesPageData(
                name="style",
                title=_("Style"),
                icon_name="applications-graphics-symbolic",
                groups=[
                    PreferencesGroupData(
                        name="themes", title=_("Themes"), widget=Themes
                    ),
                ],
            ),
            PreferencesPageData(
                name="audio_video",
                title=_("Audio"),
                icon_name="audio-input-microphone-symbolic",
                banner=PreferencesPageBannerData(
                    revealed=bool(not app.is_installed("GST")),
                    title=_("Missing dependencies for audio support"),
                    button_label=_("Features"),
                    action_name="app.features",
                ),
                groups=[
                    # PreferencesGroupData(
                    #     name="server",
                    #     title=_("Server"),
                    #     widget=Server
                    # ),
                    PreferencesGroupData(name="audio", title=_("Audio"), widget=Audio),
                    # PreferencesGroupData(
                    #     name="video",
                    #     title=_("Video"),
                    #     widget=Video
                    # ),
                ],
            ),
            PreferencesPageData(
                name="plugins",
                title=_("Plugins"),
                icon_name="lucide-package-symbolic",
                groups=[
                    PreferencesGroupData(
                        name="plugin-settings",
                        title=_("Plugin Settings"),
                        widget=PluginSettings,
                    ),
                    Plugins,
                ],
            ),
            PreferencesPageData(
                name="advanced",
                title=_("Advanced"),
                icon_name="lucide-wrench-symbolic",
                groups=[
                    PreferencesGroupData(
                        name="miscellaneous",
                        title=_("Miscellaneous"),
                        widget=Miscellaneous,
                    ),
                    PreferencesGroupData(
                        name="advanced",
                        title=_("Advanced Settings"),
                        widget=Advanced,
                    ),
                ],
            ),
        ]

        stack = Gtk.Stack()

        for page in preferences:
            preferences_page = Adw.PreferencesPage()
            if page.banner is not None:
                page_banner = Adw.Banner(
                    revealed=page.banner.revealed,
                    title=page.banner.title,
                    button_label=page.banner.button_label,
                    action_name=page.banner.action_name,
                )
                preferences_page.set_banner(page_banner)

            stack_page = stack.add_named(preferences_page, page.name)
            stack_page.set_title(page.title)
            stack_page.set_icon_name(page.icon_name)

            for group in page.groups:
                if isinstance(group, PreferencesGroupData):
                    preferences_group = Adw.PreferencesGroup(
                        name=group.name, title=group.title
                    )
                    pref = group.widget(self)
                    self._prefs[group.name] = pref
                    preferences_group.add(pref)
                    preferences_page.add(preferences_group)
                else:
                    preferences_page.add(group())

        self._side_bar_switcher = SideBarSwitcher()

        toolbar = Adw.ToolbarView(content=self._side_bar_switcher)
        toolbar.add_top_bar(Adw.HeaderBar())

        sidebar_page = Adw.NavigationPage(
            title=_("Preferences"), tag="sidebar", child=toolbar
        )

        toolbar = Adw.ToolbarView(content=stack)
        toolbar.add_top_bar(Adw.HeaderBar())

        content_page = Adw.NavigationPage(title=" ", tag="content", child=toolbar)

        nav = Adw.NavigationSplitView(sidebar=sidebar_page, content=content_page)

        self.set_child(nav)

        self._side_bar_switcher.set_stack(stack)

        # self._add_video_preview()

    # def _add_video_preview(self) -> None:
    #     self._video_preview = VideoPreview()
    #     self._ui.video.attach(self._video_preview, 0, 1, 1, 1)

    # def get_video_preview(self) -> VideoPreview | None:
    #     return self._video_preview

    def update_proxy_list(self) -> None:
        miscellaneous = cast(Miscellaneous, self._prefs["miscellaneous"])
        miscellaneous.update_proxy_list()

    def _cleanup(self) -> None:
        # del self._video_preview
        self._prefs.clear()

    def show_page(self, name: str) -> None:
        self._side_bar_switcher.set_row("plugins")


class PreferenceBox(SettingsBox):
    def __init__(self, settings: list[Setting]) -> None:
        SettingsBox.__init__(self, None)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_hexpand(True)
        self.set_vexpand(False)
        self.set_valign(Gtk.Align.END)

        for setting in settings:
            self.add_setting(setting)
        self.update_states()


class WindowBehaviour(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        main_window_on_startup_items = {
            "always": _("Always"),
            "never": _("Never"),
            "last_state": _("Restore last state"),
        }

        action_on_close_items = {
            "hide": _("Hide"),
            "minimize": _("Minimize"),
            "quit": _("Quit"),
        }

        settings = [
            Setting(
                SettingKind.DROPDOWN,
                _("Show on Startup"),
                SettingType.CONFIG,
                "show_main_window_on_startup",
                props={"data": main_window_on_startup_items},
                desc=_("Show window when starting Gajim"),
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Action on Close"),
                SettingType.CONFIG,
                "action_on_close",
                props={"data": action_on_close_items},
                desc=_("Action when closing Gajim’s window"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show in Taskbar"),
                SettingType.CONFIG,
                "show_in_taskbar",
                desc=_("Show window in the taskbar"),
                callback=self._on_show_in_taskbar,
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Title Bar"),
                SettingType.CONFIG,
                "show_header_bar",
                desc=_("Show the window’s title bar"),
            ),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_show_in_taskbar(value: bool, *args: Any) -> None:
        app.window.set_skip_taskbar_hint(not value)


class PluginSettings(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Check for updates"),
                SettingType.CONFIG,
                "plugins_update_check",
                desc=_("Check for updates periodically"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Update automatically"),
                SettingType.CONFIG,
                "plugins_auto_update",
                desc=_("Update plugins automatically"),
                bind="plugins_update_check",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Notify after update"),
                SettingType.CONFIG,
                "plugins_notify_after_update",
                desc=_("Notify me when the automatic update was successful"),
                bind="plugins_auto_update",
            ),
        ]

        PreferenceBox.__init__(self, settings)


class General(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        speller_desc = None
        if not app.is_installed("SPELLING"):
            speller_desc = _("Needs libspelling to be installed")

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Close with Escape"),
                SettingType.CONFIG,
                "escape_key_closes",
                desc=_("Close a chat by pressing the Escape key"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Send Message Button"),
                SettingType.CONFIG,
                "show_send_message_button",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Voice Message Button"),
                SettingType.CONFIG,
                "show_voice_message_button",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Send Messages with Control+Enter"),
                SettingType.CONFIG,
                "send_on_ctrl_enter",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Spell Checking"),
                SettingType.CONFIG,
                "use_speller",
                desc=speller_desc,
                enabled_func=self._speller_available,
            ),
            Setting(
                SettingKind.SWITCH,
                _("Emoji Shortcodes"),
                SettingType.CONFIG,
                "enable_emoji_shortcodes",
                desc=_("Show suggestions for shortcodes, e.g. :+1:"),
            ),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _speller_available() -> bool:
        return app.is_installed("SPELLING")


class Chats(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Message Receipts (✔)"),
                SettingType.CONFIG,
                "positive_184_ack",
                desc=_("Add a checkmark to received messages"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Status Changes"),
                SettingType.CONFIG,
                "print_status_in_chats",
                desc=_('For example: "Julia is now online"'),
            ),
        ]

        PreferenceBox.__init__(self, settings)


class GroupChats(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(
                SettingKind.DROPDOWN,
                _("Default Sync Threshold"),
                SettingType.CONFIG,
                "gc_sync_threshold_public_default",
                desc=_("Default for new public group chats"),
                props={"data": THRESHOLD_OPTIONS},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Direct Messages"),
                SettingType.CONFIG,
                "muc_prefer_direct_msg",
                desc=_("Prefer direct messages in private group chats "),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Sort Participant List by Status"),
                SettingType.CONFIG,
                "sort_by_show_in_muc",
                callback=self._on_sort_by_show_in_muc,
            ),
            Setting(
                SettingKind.SWITCH,
                _("Status Messages in Participants List"),
                SettingType.CONFIG,
                "show_status_msgs_in_roster",
                callback=self._on_show_status_in_roster,
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Subject"),
                SettingType.CONFIG,
                "show_subject_on_join",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Joined / Left"),
                SettingType.CONFIG,
                "gc_print_join_left_default",
                desc=_("Default for new group chats"),
                props={
                    "button-text": _("Reset"),
                    "button-tooltip": _(
                        "Reset all group chats to the current default value"
                    ),
                    "button-style": "destructive-action",
                    "button-callback": self._reset_join_left,
                },
            ),
            Setting(
                SettingKind.SWITCH,
                _("Show Status Changes"),
                SettingType.CONFIG,
                "gc_print_status_default",
                desc=_("Default for new group chats"),
                props={
                    "button-text": _("Reset"),
                    "button-tooltip": _(
                        "Reset all group chats to the current default value"
                    ),
                    "button-style": "destructive-action",
                    "button-callback": self._reset_print_status,
                },
            ),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_sort_by_show_in_muc(_value: bool, *args: Any) -> None:
        roster = app.window.get_control().get_group_chat_roster()
        roster.invalidate_sort()

    @staticmethod
    def _on_show_status_in_roster(_value: bool, *args: Any) -> None:
        roster = app.window.get_control().get_group_chat_roster()
        roster.invalidate_sort()

    @staticmethod
    def _reset_join_left(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_group_chat_settings("print_join_left", None)

    @staticmethod
    def _reset_print_status(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_group_chat_settings("print_status", None)


class FilePreview(PreferenceBox):
    def __init__(self, *args: Any) -> None:
        sizes = {
            0: _("No automatic preview"),
            262144: "256 KiB",
            524288: "512 KiB",
            1048576: "1 MiB",
            5242880: "5 MiB",
            10485760: "10 MiB",
            26214400: "25 MiB",
        }

        preview_actions = {}
        for action, data in PREVIEW_ACTIONS.items():
            if action == "download":
                continue
            preview_actions[action] = data[0]

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("File Preview"),
                SettingType.CONFIG,
                "enable_file_preview",
                desc=_("Show previews for files"),
            ),
            Setting(
                SettingKind.SPIN,
                _("Preview Size"),
                SettingType.CONFIG,
                "preview_size",
                desc=_("Size of preview images in pixels"),
                bind="enable_file_preview",
                props={"range_": (100, 1000, 1)},
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("File Size Limit"),
                SettingType.CONFIG,
                "preview_max_file_size",
                desc=_("Maximum file size for preview downloads"),
                bind="enable_file_preview",
                props={"data": sizes},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Preview in Public Group Chats"),
                SettingType.CONFIG,
                "preview_anonymous_muc",
                desc=_(
                    "Show previews automatically in public "
                    "group chats (may disclose your data)"
                ),
                bind="enable_file_preview",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Preview all Image URLs"),
                SettingType.CONFIG,
                "preview_allow_all_images",
                desc=_("Show previews for any URLs containing images (may be unsafe)"),
                bind="enable_file_preview",
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Left Click Action"),
                SettingType.CONFIG,
                "preview_leftclick_action",
                desc=_("Action for left-clicking a preview"),
                bind="enable_file_preview",
                props={"data": preview_actions},
            ),
            Setting(
                SettingKind.SWITCH,
                _("HTTPS Verification"),
                SettingType.CONFIG,
                "preview_verify_https",
                desc=_(
                    "Whether to check for a valid certificate before "
                    "downloading (not safe to disable)"
                ),
                bind="enable_file_preview",
            ),
        ]

        PreferenceBox.__init__(self, settings)


class VisualNotifications(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Notification Area Icon"),
                SettingType.CONFIG,
                "show_trayicon",
            ),
            Setting(
                SettingKind.NOTIFICATIONS,
                _("Show Notifications"),
                SettingType.DIALOG,
                props={"dialog": NotificationsDialog},
            ),
        ]

        PreferenceBox.__init__(self, settings)


class NotificationsDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Show Notifications"),
                SettingType.CONFIG,
                "show_notifications",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Notifications When Away"),
                SettingType.CONFIG,
                "show_notifications_away",
                desc=_("Show notifications even if you are Away, Busy, etc."),
                bind="show_notifications",
            ),
        ]

        SettingsDialog.__init__(
            self, parent, _("Notifications"), Gtk.DialogFlags.MODAL, settings, account
        )


class Sounds(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Play Sounds"),
                SettingType.CONFIG,
                "sounds_on",
                desc=_("Play sounds to notify about events"),
                props={
                    "button-icon-name": "lucide-settings-symbolic",
                    "button-callback": self._on_manage_sounds,
                },
            ),
            Setting(
                SettingKind.SWITCH,
                _("Sounds When Away"),
                SettingType.CONFIG,
                "sounddnd",
                desc=_("Play sounds even when you are Away, Busy, etc."),
                bind="sounds_on",
            ),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_manage_sounds(_button: Gtk.Button) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("ManageSounds", transient_for=window.window)


class StatusMessage(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Sign In"),
                SettingType.CONFIG,
                "ask_online_status",
            ),
        ]

        PreferenceBox.__init__(self, settings)


class AutomaticStatus(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(
                SettingKind.AUTO_AWAY,
                _("Auto Away"),
                SettingType.DIALOG,
                desc=_(
                    'Change your status to "Away" after a certain ' "amount of time"
                ),
                props={"dialog": AutoAwayDialog},
            ),
            Setting(
                SettingKind.AUTO_EXTENDED_AWAY,
                _("Auto Not Available"),
                SettingType.DIALOG,
                desc=_(
                    'Change your status to "Not Available" after a '
                    "certain amount of time"
                ),
                props={"dialog": AutoExtendedAwayDialog},
            ),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _get_auto_away() -> bool:
        return app.settings.get("autoaway")

    @staticmethod
    def _get_auto_xa() -> bool:
        return app.settings.get("autoxa")


class AutoAwayDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        settings = [
            Setting(SettingKind.SWITCH, _("Auto Away"), SettingType.CONFIG, "autoaway"),
            Setting(
                SettingKind.SPIN,
                _("Time Until Away"),
                SettingType.CONFIG,
                "autoawaytime",
                desc=_("Minutes until your status gets changed"),
                props={"range_": (1, 720, 1)},
                bind="autoaway",
            ),
            Setting(
                SettingKind.ENTRY,
                _("Status Message"),
                SettingType.CONFIG,
                "autoaway_message",
                bind="autoaway",
            ),
        ]

        SettingsDialog.__init__(
            self,
            parent,
            _("Auto Away Settings"),
            Gtk.DialogFlags.MODAL,
            settings,
            account,
        )


class AutoExtendedAwayDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Auto Not Available"),
                SettingType.CONFIG,
                "autoxa",
            ),
            Setting(
                SettingKind.SPIN,
                _("Time Until Not Available"),
                SettingType.CONFIG,
                "autoxatime",
                desc=_("Minutes until your status gets changed"),
                props={"range_": (1, 720, 1)},
                bind="autoxa",
            ),
            Setting(
                SettingKind.ENTRY,
                _("Status Message"),
                SettingType.CONFIG,
                "autoxa_message",
                bind="autoxa",
            ),
        ]

        SettingsDialog.__init__(
            self,
            parent,
            _("Auto Extended Away Settings"),
            Gtk.DialogFlags.MODAL,
            settings,
            account,
        )


class Themes(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        theme_items = self._get_theme_items()

        dark_theme_items = {
            0: _("Disabled"),
            1: _("Enabled"),
            2: _("System"),
        }

        settings = [
            Setting(
                SettingKind.SPIN,
                _("User Interface Font Size"),
                SettingType.CONFIG,
                "app_font_size",
                props={"range_": (1.0, 1.5, 0.125)},
                callback=self._on_app_font_size_changed,
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Dark Theme"),
                SettingType.CONFIG,
                "dark_theme",
                props={"data": dark_theme_items},
                callback=self._on_dark_theme,
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Theme"),
                SettingType.CONFIG,
                "roster_theme",
                name="roster_theme",
                props={
                    "data": theme_items,
                    "button-icon-name": "lucide-settings-symbolic",
                    "button-callback": self._on_edit_themes,
                },
                callback=self._on_theme_changed,
            ),
        ]

        PreferenceBox.__init__(self, settings)

        app.ged.register_event_handler("theme-update", ged.GUI1, self._on_theme_update)

    def do_unroot(self) -> None:
        app.ged.remove_event_handler("theme-update", ged.GUI1, self._on_theme_update)
        PreferenceBox.do_unroot(self)

    @staticmethod
    def _on_app_font_size_changed(_value: float, *args: Any) -> None:
        app.css_config.apply_app_font_size()

    @staticmethod
    def _get_theme_items() -> list[str]:
        return ["default", *app.css_config.themes]

    def _on_theme_update(self, *args: Any) -> None:
        dropdown_row = cast(DropDownSetting, self.get_setting("roster_theme"))
        dropdown_row.update_entries(self._get_theme_items())
        dropdown_row.select_key(app.settings.get("roster_theme"))

    def _on_edit_themes(self, _button: Gtk.Button) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("Themes", transient=window.window)

    def _on_theme_changed(self, value: str, *args: Any) -> None:
        app.ged.remove_event_handler("theme-update", ged.GUI1, self._on_theme_update)

        app.css_config.change_theme(value)
        app.ged.raise_event(ThemeUpdate())

        app.ged.register_event_handler("theme-update", ged.GUI1, self._on_theme_update)

    @staticmethod
    def _on_dark_theme(value: str, *args: Any) -> None:
        app.css_config.set_dark_theme(int(value))
        app.css_config.reload_css()
        app.ged.raise_event(StyleChanged())


# class Server(PreferenceBox):
#     def __init__(self, *args: Any) -> None:

#         settings = [
#             Setting(
#                 SettingKind.USE_STUN_SERVER,
#                 _("Use STUN Server"),
#                 SettingType.DIALOG,
#                 desc=_("Helps to establish calls through firewalls"),
#                 props={"dialog": StunServerDialog},
#             ),
#         ]

#         PreferenceBox.__init__(self, settings)

#         self.set_sensitive(app.is_installed("AV"))


# class StunServerDialog(SettingsDialog):
#     def __init__(self, account: str, parent: Gtk.Window) -> None:

#         settings = [
#             Setting(
#                 SettingKind.SWITCH,
#                 _("Use STUN Server"),
#                 SettingType.CONFIG,
#                 "use_stun_server",
#             ),
#             Setting(
#                 SettingKind.ENTRY,
#                 _("STUN Server"),
#                 SettingType.CONFIG,
#                 "stun_server",
#                 bind="use_stun_server",
#             ),
#         ]

#         SettingsDialog.__init__(
#             self,
#             parent,
#             _("STUN Server Settings"),
#             Gtk.DialogFlags.MODAL,
#             settings,
#             account,
#         )


class Audio(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        deps_installed = app.is_installed("GST")

        audio_input_devices = {}
        # audio_output_devices = {}
        if deps_installed:
            audio_input_devices = AudioInputManager().get_devices()
            # audio_output_devices = AudioOutputManager().get_devices()

        audio_input_items = self._create_av_combo_items(audio_input_devices)
        # audio_output_items = self._create_av_combo_items(audio_output_devices)

        settings = [
            Setting(
                SettingKind.DROPDOWN,
                _("Audio Input Device"),
                SettingType.CONFIG,
                "audio_input_device",
                desc=_("Select your audio input (e.g. microphone)"),
                props={"data": audio_input_items},
            ),
            # Setting(
            #     SettingKind.DROPDOWN,
            #     _("Audio Output Device"),
            #     SettingType.CONFIG,
            #     "audio_output_device",
            #     desc=_("Select an audio output (e.g. speakers, headphones)"),
            #     props={"data": audio_output_items},
            # ),
        ]

        PreferenceBox.__init__(self, settings)

        self.set_sensitive(deps_installed)

    @staticmethod
    def _create_av_combo_items(items_dict: dict[str, str]) -> dict[str, str]:
        items = enumerate(
            sorted(
                items_dict.items(),
                key=lambda x: "" if x[1].startswith("auto") else x[0].lower(),
            )
        )
        combo_items: dict[str, str] = {}
        for _index, (name, value) in items:
            combo_items[value] = name
        return combo_items


# class Video(PreferenceBox):
#     def __init__(self, *args: Any) -> None:

#         deps_installed = app.is_installed("AV")

#         video_input_devices = {}
#         if deps_installed:
#             video_input_devices = VideoInputManager().get_devices()

#         video_input_items = self._create_av_combo_items(video_input_devices)

#         video_framerates = {
#             "": _("Default"),
#             "15/1": "15 fps",
#             "10/1": "10 fps",
#             "5/1": "5 fps",
#             "5/2": "2.5 fps",
#         }

#         video_sizes = {
#             "": _("Default"),
#             "800x600": "800x600",
#             "640x480": "640x480",
#             "320x240": "320x240",
#         }

#         settings = [
#             Setting(
#                 SettingKind.DROPDOWN,
#                 _("Video Input Device"),
#                 SettingType.CONFIG,
#                 "video_input_device",
#                 props={"data": video_input_items},
#                 desc=_("Select your video input device (e.g. webcam, screen capture)"),  # noqa: E501
#                 callback=self._on_video_input_changed,
#             ),
#             Setting(
#                 SettingKind.DROPDOWN,
#                 _("Video Framerate"),
#                 SettingType.CONFIG,
#                 "video_framerate",
#                 props={"data": video_framerates},
#             ),
#             Setting(
#                 SettingKind.DROPDOWN,
#                 _("Video Resolution"),
#                 SettingType.CONFIG,
#                 "video_size",
#                 props={"data": video_sizes},
#             ),
#             Setting(
#                 SettingKind.SWITCH,
#                 _("Show My Video Stream"),
#                 SettingType.CONFIG,
#                 "video_see_self",
#                 desc=_("Show your own video stream in calls"),
#             ),
#             Setting(
#                 SettingKind.SWITCH,
#                 _("Live Preview"),
#                 SettingType.VALUE,
#                 desc=_("Show a live preview to test your video source"),
#                 callback=self._toggle_live_preview,
#             ),
#         ]

#         PreferenceBox.__init__(self, settings)

#         self.set_sensitive(deps_installed)

#     @staticmethod
#     def _on_video_input_changed(_value: str, *args: Any) -> None:
#         window = get_app_window("Preferences")
#         assert window is not None
#         preview = window.get_video_preview()
#         if preview is None or not preview.is_active:
#             # changed signal gets triggered when we fill the combobox
#             return
#         preview.refresh()

#     @staticmethod
#     def _toggle_live_preview(value: bool, *args: Any) -> None:
#         window = get_app_window("Preferences")
#         assert window is not None
#         preview = window.get_video_preview()
#         if preview is not None:
#             preview.toggle_preview(value)

#     @staticmethod
#     def _create_av_combo_items(items_dict: dict[str, str]) -> dict[str, str]:
#         items = enumerate(
#             sorted(
#                 items_dict.items(),
#                 key=lambda x: "" if x[1].startswith("auto") else x[0].lower(),
#             )
#         )
#         combo_items: dict[str, str] = {}
#         for _index, (name, value) in items:
#             combo_items[value] = name
#         return combo_items


class Miscellaneous(PreferenceBox):
    def __init__(self, pref_window: Preferences) -> None:
        self._hints_list: list[BoolSettings] = [
            "show_help_start_chat",
        ]

        settings = [
            Setting(
                SettingKind.DROPDOWN,
                _("Global Proxy"),
                SettingType.CONFIG,
                "global_proxy",
                name="global_proxy",
                props={
                    "data": self._get_proxies(),
                    "button-icon-name": "lucide-settings-symbolic",
                    "button-callback": self._on_proxy_edit,
                },
            ),
            Setting(
                SettingKind.SWITCH,
                _("Use System Keyring"),
                SettingType.CONFIG,
                "use_keyring",
                desc=_("Use your system’s keyring to store passwords"),
            ),
        ]

        if sys.platform not in ("win32", "darwin") and package_version(
            "keyring>=23.8.1"
        ):
            settings.append(
                Setting(
                    SettingKind.SWITCH,
                    _("Enable KeepassXC Integration"),
                    SettingType.CONFIG,
                    "enable_keepassxc_integration",
                )
            )

        if sys.platform in ("win32", "darwin"):
            settings.append(
                Setting(
                    SettingKind.SWITCH,
                    _("Check For Updates"),
                    SettingType.CONFIG,
                    "check_for_update",
                    desc=_("Check for Gajim updates periodically"),
                )
            )

        settings.append(
            Setting(
                SettingKind.GENERIC,
                _("Reset Hints"),
                SettingType.VALUE,
                None,
                desc=_("This will reset all introduction hints"),
                props={
                    "button-text": _("Reset"),
                    "button-style": "destructive-action",
                    "button-callback": self._on_reset_hints,
                    "button-sensitive": self._check_hints_reset(),
                },
            ),
        )

        settings.append(
            Setting(
                SettingKind.GENERIC,
                _("Purge Chat History"),
                SettingType.VALUE,
                None,
                desc=_("This will purge all locally stored chat history"),
                props={
                    "button-text": _("Purge"),
                    "button-style": "destructive-action",
                    "button-callback": self._on_purge_history_clicked,
                },
            ),
        )

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _get_proxies() -> dict[str, str]:
        proxies = {"": _("System")}
        proxies.update({proxy: proxy for proxy in app.settings.get_proxies()})
        proxies["no-proxy"] = _("No Proxy")
        return proxies

    @staticmethod
    def _on_proxy_edit(*args: Any) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("ManageProxies", transient_for=window.window)

    def update_proxy_list(self) -> None:
        dropdown_row = cast(DropDownSetting, self.get_setting("global_proxy"))
        dropdown_row.update_entries(self._get_proxies())

    def _check_hints_reset(self) -> bool:
        return any(app.settings.get(hint) is False for hint in self._hints_list)

    def _on_reset_hints(self, button: Gtk.Button) -> None:
        for hint in self._hints_list:
            app.settings.set(hint, True)
        button.set_sensitive(False)

    @staticmethod
    def _on_purge_history_clicked(button: Gtk.Button) -> None:
        def _on_response() -> None:
            button.set_sensitive(False)
            app.storage.archive.remove_all_history()
            app.window.quit()

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


class Advanced(PreferenceBox):
    def __init__(self, pref_window: Preferences) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Debug Logging"),
                SettingType.VALUE,
                app.get_debug_mode(),
                props={
                    "button-icon-name": "folder-symbolic",
                    "button-callback": self._on_open_debug_logs,
                },
                callback=self._on_debug_logging,
            ),
            Setting(
                SettingKind.GENERIC,
                _("Debug Console"),
                SettingType.VALUE,
                None,
                props={
                    "button-text": _("Open"),
                    "button-callback": self._on_debug,
                },
            ),
            Setting(
                SettingKind.SWITCH,
                _("D-Bus Interface"),
                SettingType.CONFIG,
                "remote_control",
                desc=_(
                    "Allow Gajim to broadcast useful information via "
                    "D-Bus. It also allows other applications to "
                    "control Gajim remotely."
                ),
            ),
            Setting(
                SettingKind.GENERIC,
                _("Advanced Configuration Editor"),
                SettingType.VALUE,
                None,
                desc=_("Please use these settings with caution!"),
                props={
                    "button-text": _("Open"),
                    "button-callback": self._on_advanced_config_editor,
                },
            ),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_debug_logging(value: bool, *args: Any) -> None:
        app.set_debug_mode(value)

    @staticmethod
    def _on_open_debug_logs(*args: Any) -> None:
        open_directory(configpaths.get("DEBUG"))

    @staticmethod
    def _on_advanced_config_editor(*args: Any) -> None:
        window = get_app_window("Preferences")
        assert window is not None
        open_window("AdvancedConfig", transient_for=window.window)

    @staticmethod
    def _on_debug(*args: Any) -> None:
        open_window("DebugConsoleWindow")
