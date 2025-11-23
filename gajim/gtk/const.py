# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Constants for the gtk module

from __future__ import annotations

from typing import Any
from typing import NamedTuple

import sys
from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from enum import IntEnum
from enum import unique

from gi.repository import Gdk

from gajim.common.i18n import _
from gajim.common.setting_values import AllSettingsT

if sys.byteorder == "little":
    gdk_memory_default = Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED
else:
    gdk_memory_default = Gdk.MemoryFormat.A8R8G8B8_PREMULTIPLIED
GDK_MEMORY_DEFAULT = gdk_memory_default


class Setting(NamedTuple):
    kind: SettingKind
    label: str
    type: SettingType
    value: AllSettingsT | None = None
    name: str | None = None
    callback: Callable[..., None] | None = None
    data: Any | None = None
    desc: str | None = None
    bind: str | None = None
    inverted: bool | None = None
    enabled_func: Callable[..., bool] | None = None
    props: dict[str, Any] | None = None


DEFAULT_WORKSPACE_COLOR = "rgb(191,15,167)"

MAX_MESSAGE_LENGTH = 1000


@unique
class MuteState(IntEnum):
    UNMUTE = 0
    MIN_30 = 30
    MIN_60 = 60
    MIN_120 = 120
    MIN_480 = 480
    PERM = 100000000

    @classmethod
    def iter(cls) -> Iterator[tuple[int, str]]:
        yield from cls._labels.items()  # pyright: ignore


MuteState._labels = {  # pyright: ignore
    MuteState.MIN_30: _("30 minutes"),
    MuteState.MIN_60: _("1 hour"),
    MuteState.MIN_120: _("2 hours"),
    MuteState.MIN_480: _("8 hours"),
    MuteState.PERM: _("Permanently"),
}


@unique
class Theme(IntEnum):
    NOT_DARK = 0
    DARK = 1
    SYSTEM = 2


@unique
class SettingKind(IntEnum):
    ENTRY = 0
    SWITCH = 1
    SPIN = 2
    ACTION = 3
    DIALOG = 5
    CALLBACK = 6
    FILECHOOSER = 10
    COMBO = 12
    COLOR = 13
    DROPDOWN = 19
    GENERIC = 20
    SUBPAGE = 21


@unique
class SettingType(IntEnum):
    CONFIG = 0
    ACCOUNT_CONFIG = 1
    CONTACT = 2
    GROUP_CHAT = 3
    VALUE = 4
    ACTION = 5
    DIALOG = 6


class ControlType(Enum):
    CHAT = "chat"
    GROUPCHAT = "gc"
    PRIVATECHAT = "pm"

    @property
    def is_chat(self):
        return self == ControlType.CHAT

    @property
    def is_groupchat(self):
        return self == ControlType.GROUPCHAT

    @property
    def is_privatechat(self):
        return self == ControlType.PRIVATECHAT

    def __str__(self):
        return self.value


WINDOW_MODULES = {
    "AccountWizard": "gajim.gtk.account_wizard",
    "AddContact": "gajim.gtk.add_contact",
    "AdHocCommands": "gajim.gtk.adhoc",
    "AdvancedConfig": "gajim.gtk.advanced_config",
    "DBMigration": "gajim.gtk.db_migration",
    "DebugConsoleWindow": "gajim.gtk.debug_console",
    "CertificateDialog": "gajim.gtk.certificate_dialog",
    "ChangePassword": "gajim.gtk.change_password",
    "ContactInfo": "gajim.gtk.contact_info",
    "CreateGroupchatWindow": "gajim.gtk.groupchat_creation",
    "Features": "gajim.gtk.features",
    "GroupchatDetails": "gajim.gtk.groupchat_details",
    "GroupChatInvitationDialog": "gajim.gtk.groupchat_invitation",
    "GroupchatJoin": "gajim.gtk.groupchat_join",
    "HistoryExport": "gajim.gtk.history_export",
    "HistorySyncAssistant": "gajim.gtk.history_sync",
    "ManageProxies": "gajim.gtk.proxies",
    "ManageSounds": "gajim.gtk.manage_sounds",
    "PasswordDialog": "gajim.gtk.password_dialog",
    "PEPConfig": "gajim.gtk.pep_config",
    "Preferences": "gajim.gtk.preference.dialog",
    "ProfileWindow": "gajim.gtk.profile",
    "QuitDialog": "gajim.gtk.quit",
    "RemoveAccount": "gajim.gtk.remove_account",
    "RosterItemExchange": "gajim.gtk.roster_item_exchange",
    "ServiceDiscoveryWindow": "gajim.gtk.discovery",
    "ServiceRegistration": "gajim.gtk.service_registration",
    "SSLErrorDialog": "gajim.gtk.ssl_error_dialog",
    "StartChatDialog": "gajim.gtk.start_chat",
    "Themes": "gajim.gtk.themes",
    "WorkspaceDialog": "gajim.gtk.workspace_dialog",
}


APP_ACTIONS = [
    ("about", None),
    ("accounts", "s"),
    ("add-account", None),
    ("add-contact", "s"),
    ("content", None),
    ("copy-text", "s"),
    ("create-groupchat", "s"),
    ("faq", None),
    ("privacy-policy", None),
    ("features", None),
    ("forget-groupchat", "a{sv}"),
    ("join-support-chat", None),
    ("manage-proxies", None),
    ("open-link", "s"),
    ("plugins", None),
    ("preferences", None),
    ("quit", None),
    ("export-history", "a{sv}"),
    ("remove-history", "a{sv}"),
    ("shortcuts", None),
    ("show", None),
    ("start-chat", "as"),
    ("open-chat", "as"),
    ("mute-chat", "a{sv}"),
    ("xml-console", None),
    ("handle-uri", "as"),
    ("save-file-as", "s"),
    ("open-file", "s"),
    ("open-folder", "s"),
]


MAIN_WIN_ACTIONS = [
    # action name, variant type, enabled
    ("input-bold", None, True),
    ("input-italic", None, True),
    ("input-strike", None, True),
    ("input-clear", None, True),
    ("insert-emoji", "s", True),
    ("show-emoji-chooser", None, True),
    ("activate-message-selection", "u", True),
    ("delete-message-locally", "a{sv}", True),
    ("correct-message", None, False),
    ("retract-message", "a{sv}", False),
    ("copy-message", "s", True),
    ("moderate-message", "a{sv}", False),
    ("moderate-all-messages", "a{sv}", False),
    ("paste-as-quote", None, True),
    ("paste-as-code-block", None, True),
    ("quote", "s", True),
    ("quote-next", None, True),
    ("quote-prev", None, True),
    ("reply", "u", True),
    ("jump-to-message", "au", True),
    ("mention", "s", True),
    ("send-file-httpupload", "as", False),
    # ('send-file-jingle', 'as', False),
    ("send-file", "as", False),
    ("start-voice-call", None, False),
    ("start-video-call", None, False),
    ("show-contact-info", None, True),
    ("chat-contact-info", "a{sv}", True),
    ("send-message", None, False),
    ("muc-change-nickname", None, False),
    ("muc-invite", None, False),
    ("muc-contact-info", "s", False),
    ("muc-execute-command", "s", False),
    ("muc-ban", "s", False),
    ("muc-kick", "s", False),
    ("muc-change-role", "as", False),
    ("muc-change-affiliation", "as", False),
    ("muc-request-voice", None, False),
    ("muc-user-block", "a{sv}", True),
    ("muc-user-unblock", "a{sv}", True),
    ("scroll-view-up", None, True),
    ("scroll-view-down", None, True),
    ("change-nickname", None, True),
    ("change-subject", None, True),
    ("escape", None, True),
    ("close-chat", None, True),
    ("restore-chat", None, True),
    ("switch-next-chat", None, True),
    ("switch-prev-chat", None, True),
    ("switch-next-unread-chat", None, True),
    ("switch-prev-unread-chat", None, True),
    ("switch-chat-1", None, True),
    ("switch-chat-2", None, True),
    ("switch-chat-3", None, True),
    ("switch-chat-4", None, True),
    ("switch-chat-5", None, True),
    ("switch-chat-6", None, True),
    ("switch-chat-7", None, True),
    ("switch-chat-8", None, True),
    ("switch-chat-9", None, True),
    ("switch-workspace-1", None, True),
    ("switch-workspace-2", None, True),
    ("switch-workspace-3", None, True),
    ("switch-workspace-4", None, True),
    ("switch-workspace-5", None, True),
    ("switch-workspace-6", None, True),
    ("switch-workspace-7", None, True),
    ("switch-workspace-8", None, True),
    ("switch-workspace-9", None, True),
    ("increase-app-font-size", None, True),
    ("decrease-app-font-size", None, True),
    ("reset-app-font-size", None, True),
    ("add-workspace", "s", True),
    ("edit-workspace", "s", True),
    ("remove-workspace", "s", True),
    ("activate-workspace", "s", True),
    ("mark-workspace-as-read", "s", True),
    ("add-chat", "a{sv}", True),
    ("add-group-chat", "as", True),
]


ACCOUNT_ACTIONS = [
    ("add-contact", "a{sv}"),
    ("block-contact", "a{sv}"),
    ("remove-contact", "as"),
    ("execute-command", "(sas)"),
    ("mark-as-read", "a{sv}"),
    ("open-event", "a{sv}"),
    ("pep-config", "s"),
    ("profile", "s"),
    ("services", "s"),
    ("sync-history", "s"),
    ("subscription-accept", "a{sv}"),
    ("subscription-deny", "a{sv}"),
    ("subscription-deny-all", None),
]


ALWAYS_ACCOUNT_ACTIONS = {
    "open-event",
}


ONLINE_ACCOUNT_ACTIONS = {
    "add-contact",
    "remove-contact",
    "execute-command",
    "pep-config",
    "profile",
    "services",
    "sync-history",
    "mark-as-read",
    "subscription-accept",
    "subscription-deny",
    "subscription-deny-all",
}


FEATURE_ACCOUNT_ACTIONS = {
    "block-contact",
}


@dataclass
class ShortcutData:
    label: str
    category: str
    accelerators: list[str]
    allow_rebind: bool = True


SHORTCUT_CATEGORIES = {
    "general": _("General"),
    "chats": _("Chats"),
    "messages": _("Messages"),
}
SHORTCUTS = {
    # general
    "app.start-chat(['', ''])": ShortcutData(
        label=_("Start / Join Chat"), category="general", accelerators=["<Primary>N"]
    ),
    "app.create-groupchat::": ShortcutData(
        label=_("Create New Group Chat"),
        category="general",
        accelerators=["<Primary>G"],
    ),
    "app.preferences": ShortcutData(
        label=_("Preferences"), category="general", accelerators=["<Primary>P"]
    ),
    "app.plugins": ShortcutData(
        label=_("Plugins"), category="general", accelerators=["<Primary>E"]
    ),
    "app.shortcuts": ShortcutData(
        label=_("Manage Shortcuts"),
        category="general",
        accelerators=["<Primary>question"],
    ),
    "app.xml-console": ShortcutData(
        label=_("Debug Console"),
        category="general",
        accelerators=["<Primary><Shift>X"],
    ),
    "app.quit": ShortcutData(
        label=_("Quit Gajim"), category="general", accelerators=["<Primary>Q"]
    ),
    "win.increase-app-font-size": ShortcutData(
        label=_("Increase Font Size"),
        category="general",
        accelerators=["<Primary>plus"],
    ),
    "win.decrease-app-font-size": ShortcutData(
        label=_("Decrease Font Size"),
        category="general",
        accelerators=["<Primary>minus"],
    ),
    "win.reset-app-font-size": ShortcutData(
        label=_("Reset Font Size"), category="general", accelerators=["<Primary>0"]
    ),
    # chats
    "win.focus-search": ShortcutData(
        label=_("Focus Search"), category="chats", accelerators=["<Primary>K"]
    ),
    "win.search-history": ShortcutData(
        label=_("Search Chat History"), category="chats", accelerators=["<Primary>F"]
    ),
    "win.show-contact-info": ShortcutData(
        label=_("Contact Details"), category="chats", accelerators=["<Primary>I"]
    ),
    "win.change-nickname": ShortcutData(
        label=_("Change Nickname"),
        category="chats",
        accelerators=["<Primary><Shift>N"],
    ),
    "win.change-subject": ShortcutData(
        label=_("Change Subject"),
        category="chats",
        accelerators=["<Primary><Shift>S"],
    ),
    "win.escape": ShortcutData(
        label="Escape", category="chats", accelerators=["Escape"], allow_rebind=False
    ),
    "win.close-chat": ShortcutData(
        label=_("Close Chat"), category="chats", accelerators=["<Primary>W"]
    ),
    "win.restore-chat": ShortcutData(
        label=_("Restore Closed Chat"),
        category="chats",
        accelerators=["<Primary><Shift>W"],
    ),
    "win.chat-list-visible": ShortcutData(
        label=_("Toggle Chat List"), category="chats", accelerators=["<Primary>R"]
    ),
    "win.switch-next-chat": ShortcutData(
        label=_("Switch to Next Chat"),
        category="chats",
        accelerators=["<Primary>Page_Down"],
    ),
    "win.switch-prev-chat": ShortcutData(
        label=_("Switch to Previous Chat"),
        category="chats",
        accelerators=["<Primary>Page_Up"],
    ),
    "win.switch-next-unread-chat": ShortcutData(
        label=_("Switch to Next Unread Chat"),
        category="chats",
        accelerators=["<Primary>Tab"],
    ),
    "win.switch-prev-unread-chat": ShortcutData(
        label=_("Switch to Previous Unread Chat"),
        category="chats",
        accelerators=["<Primary>ISO_Left_Tab"],
    ),
    "win.switch-chat-1": ShortcutData(
        label=_("Switch to Chat 1"), category="chats", accelerators=["<Alt>1"]
    ),
    "win.switch-chat-2": ShortcutData(
        label=_("Switch to Chat 2"), category="chats", accelerators=["<Alt>2"]
    ),
    "win.switch-chat-3": ShortcutData(
        label=_("Switch to Chat 3"), category="chats", accelerators=["<Alt>3"]
    ),
    "win.switch-chat-4": ShortcutData(
        label=_("Switch to Chat 4"), category="chats", accelerators=["<Alt>4"]
    ),
    "win.switch-chat-5": ShortcutData(
        label=_("Switch to Chat 5"), category="chats", accelerators=["<Alt>5"]
    ),
    "win.switch-chat-6": ShortcutData(
        label=_("Switch to Chat 6"), category="chats", accelerators=["<Alt>6"]
    ),
    "win.switch-chat-7": ShortcutData(
        label=_("Switch to Chat 7"), category="chats", accelerators=["<Alt>7"]
    ),
    "win.switch-chat-8": ShortcutData(
        label=_("Switch to Chat 8"), category="chats", accelerators=["<Alt>8"]
    ),
    "win.switch-chat-9": ShortcutData(
        label=_("Switch to Chat 9"), category="chats", accelerators=["<Alt>9"]
    ),
    "win.switch-workspace-1": ShortcutData(
        label=_("Switch to Workspace 1"), category="chats", accelerators=["<Primary>1"]
    ),
    "win.switch-workspace-2": ShortcutData(
        label=_("Switch to Workspace 2"), category="chats", accelerators=["<Primary>2"]
    ),
    "win.switch-workspace-3": ShortcutData(
        label=_("Switch to Workspace 3"), category="chats", accelerators=["<Primary>3"]
    ),
    "win.switch-workspace-4": ShortcutData(
        label=_("Switch to Workspace 4"), category="chats", accelerators=["<Primary>4"]
    ),
    "win.switch-workspace-5": ShortcutData(
        label=_("Switch to Workspace 5"), category="chats", accelerators=["<Primary>5"]
    ),
    "win.switch-workspace-6": ShortcutData(
        label=_("Switch to Workspace 6"), category="chats", accelerators=["<Primary>6"]
    ),
    "win.switch-workspace-7": ShortcutData(
        label=_("Switch to Workspace 7"), category="chats", accelerators=["<Primary>7"]
    ),
    "win.switch-workspace-8": ShortcutData(
        label=_("Switch to Workspace 8"), category="chats", accelerators=["<Primary>8"]
    ),
    "win.switch-workspace-9": ShortcutData(
        label=_("Switch to Workspace 9"), category="chats", accelerators=["<Primary>9"]
    ),
    # messages
    "win.show-emoji-chooser": ShortcutData(
        label=_("Choose Emoji"),
        category="messages",
        accelerators=["<Primary><Shift>M"],
    ),
    "win.input-clear": ShortcutData(
        label=_("Clear Input"), category="messages", accelerators=["<Primary>U"]
    ),
    "win.scroll-view-up": ShortcutData(
        label=_("Scroll Up"), category="messages", accelerators=["<Shift>Page_Up"]
    ),
    "win.scroll-view-down": ShortcutData(
        label=_("Scroll Down"),
        category="messages",
        accelerators=["<Shift>Page_Down"],
    ),
    "win.quote-prev": ShortcutData(
        label=_("Quote Previous Message"),
        category="messages",
        accelerators=["<Primary><Shift>Up"],
    ),
    "win.quote-next": ShortcutData(
        label=_("Quote Next Message"),
        category="messages",
        accelerators=["<Primary><Shift>Down"],
    ),
}
