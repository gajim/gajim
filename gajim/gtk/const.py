# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# Constants for the gtk module

from __future__ import annotations

from typing import Any
from typing import NamedTuple

from collections.abc import Callable
from collections.abc import Iterator
from enum import Enum
from enum import IntEnum
from enum import unique

from gajim.common.i18n import _
from gajim.common.setting_values import AllSettingsT


class Filter(NamedTuple):
    name: str
    pattern: str | list[str]
    default: bool


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


DEFAULT_WORKSPACE_COLOR = 'rgb(191,15,167)'

# Drag and drop target type URI list (for dropped files)
TARGET_TYPE_URI_LIST = 80

MAX_MESSAGE_LENGTH = 5000


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
        MuteState.MIN_30: _('30 minutes'),
        MuteState.MIN_60: _('1 hour'),
        MuteState.MIN_120: _('2 hours'),
        MuteState.MIN_480: _('8 hours'),
        MuteState.PERM: _('Permanently'),
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
    LOGIN = 4
    DIALOG = 5
    CALLBACK = 6
    HOSTNAME = 8
    PRIORITY = 9
    FILECHOOSER = 10
    CHANGEPASSWORD = 11
    COMBO = 12
    COLOR = 13
    POPOVER = 14
    AUTO_AWAY = 15
    AUTO_EXTENDED_AWAY = 16
    USE_STUN_SERVER = 17
    NOTIFICATIONS = 18


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
    CHAT = 'chat'
    GROUPCHAT = 'gc'
    PRIVATECHAT = 'pm'

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
    'AccountsWindow': 'gajim.gtk.accounts',
    'AccountWizard': 'gajim.gtk.account_wizard',
    'AddContact': 'gajim.gtk.add_contact',
    'AdHocCommands': 'gajim.gtk.adhoc',
    'AdvancedConfig': 'gajim.gtk.advanced_config',
    'BlockingList': 'gajim.gtk.blocking',
    'Bookmarks': 'gajim.gtk.bookmarks',
    'CertificateDialog': 'gajim.gtk.certificate_dialog',
    'ChangePassword': 'gajim.gtk.change_password',
    'ContactInfo': 'gajim.gtk.contact_info',
    'CreateGroupchatWindow': 'gajim.gtk.groupchat_creation',
    'Features': 'gajim.gtk.features',
    'GroupchatDetails': 'gajim.gtk.groupchat_details',
    'GroupChatInvitation': 'gajim.gtk.groupchat_invitation',
    'GroupchatJoin': 'gajim.gtk.groupchat_join',
    'HistoryExport': 'gajim.gtk.history_export',
    'HistorySyncAssistant': 'gajim.gtk.history_sync',
    'MamPreferences': 'gajim.gtk.mam_preferences',
    'ManageProxies': 'gajim.gtk.proxies',
    'ManageSounds': 'gajim.gtk.manage_sounds',
    'PasswordDialog': 'gajim.gtk.password_dialog',
    'PEPConfig': 'gajim.gtk.pep_config',
    'PluginsWindow': 'gajim.gtk.plugins',
    'Preferences': 'gajim.gtk.preferences',
    'ProfileWindow': 'gajim.gtk.profile',
    'RemoveAccount': 'gajim.gtk.remove_account',
    'RosterItemExchange': 'gajim.gtk.roster_item_exchange',
    'ServerInfo': 'gajim.gtk.server_info',
    'ServiceDiscoveryWindow': 'gajim.gtk.discovery',
    'ServiceRegistration': 'gajim.gtk.service_registration',
    'SSLErrorDialog': 'gajim.gtk.ssl_error_dialog',
    'StartChatDialog': 'gajim.gtk.start_chat',
    'SynchronizeAccounts': 'gajim.gtk.synchronize_accounts',
    'Themes': 'gajim.gtk.themes',
    'WorkspaceDialog': 'gajim.gtk.workspace_dialog',
    'XMLConsoleWindow': 'gajim.gtk.xml_console',
}


APP_ACTIONS = [
    ('about', None),
    ('accounts', 's'),
    ('add-account', None),
    ('add-contact', 's'),
    ('content', None),
    ('copy-text', 's'),
    ('create-groupchat', 's'),
    ('faq', None),
    ('privacy-policy', None),
    ('features', None),
    ('file-transfer', None),
    ('forget-groupchat', 'a{sv}'),
    ('join-support-chat', None),
    ('manage-proxies', None),
    ('open-link', 'as'),
    ('plugins', None),
    ('preferences', None),
    ('quit', None),
    ('remove-history', 'a{sv}'),
    ('shortcuts', None),
    ('show', None),
    ('start-chat', 'as'),
    ('open-chat', 'as'),
    ('mute-chat', 'a{sv}'),
    ('xml-console', None),
]


MAIN_WIN_ACTIONS = [
    # action name, variant type, enabled
    ('input-bold', None, True),
    ('input-italic', None, True),
    ('input-strike', None, True),
    ('input-clear', None, True),
    ('show-emoji-chooser', None, True),
    ('activate-message-selection', 'u', True),
    ('delete-message-locally', 'u', True),
    ('correct-message', None, False),
    ('copy-message', 's', True),
    ('retract-message', 'a{sv}', False),
    ('quote', 's', False),
    ('mention', 's', False),
    ('send-file-httpupload', 'as', False),
    ('send-file-jingle', 'as', False),
    ('send-file', 'as', False),
    ('add-to-roster', None, True),
    ('start-voice-call', None, False),
    ('start-video-call', None, False),
    ('show-contact-info', None, True),
    ('send-message', None, False),
    ('muc-change-nickname', None, False),
    ('muc-invite', None, False),
    ('muc-contact-info', 's', False),
    ('muc-execute-command', 's', False),
    ('muc-ban', 's', False),
    ('muc-kick', 's', False),
    ('muc-change-role', 'as', False),
    ('muc-change-affiliation', 'as', False),
    ('muc-request-voice', None, False),
    ('scroll-view-up', None, True),
    ('scroll-view-down', None, True),
    ('change-nickname', None, True),
    ('change-subject', None, True),
    ('escape', None, True),
    ('close-chat', None, True),
    ('restore-chat', None, True),
    ('switch-next-chat', None, True),
    ('switch-prev-chat', None, True),
    ('switch-next-unread-chat', None, True),
    ('switch-prev-unread-chat', None, True),
    ('switch-chat-1', None, True),
    ('switch-chat-2', None, True),
    ('switch-chat-3', None, True),
    ('switch-chat-4', None, True),
    ('switch-chat-5', None, True),
    ('switch-chat-6', None, True),
    ('switch-chat-7', None, True),
    ('switch-chat-8', None, True),
    ('switch-chat-9', None, True),
    ('switch-workspace-1', None, True),
    ('switch-workspace-2', None, True),
    ('switch-workspace-3', None, True),
    ('switch-workspace-4', None, True),
    ('switch-workspace-5', None, True),
    ('switch-workspace-6', None, True),
    ('switch-workspace-7', None, True),
    ('switch-workspace-8', None, True),
    ('switch-workspace-9', None, True),
    ('toggle-chat-list', None, True),
    ('add-workspace', 's', True),
    ('edit-workspace', 's', True),
    ('remove-workspace', 's', True),
    ('activate-workspace', 's', True),
    ('mark-workspace-as-read', 's', True),
    ('add-chat', 'a{sv}', True),
    ('add-group-chat', 'as', True),
    ('add-to-roster', 'a{sv}', True),
    ('preview-open', 's', True),
    ('preview-save-as', 's', True),
    ('preview-open-folder', 's', True),
    ('preview-copy-link', 's', True),
    ('preview-open-link', 's', True),
    ('preview-download', 's', True),
]


ACCOUNT_ACTIONS = [
    ('add-contact', 'as'),
    ('contact-info', 's'),
    ('block-contact', 's'),
    ('remove-contact', 's'),
    ('execute-command', 's'),
    ('modify-gateway', 's'),
    ('archive', 's'),
    ('blocking', 's'),
    ('bookmarks', 's'),
    ('export-history', 's'),
    ('import-contacts', 's'),
    ('mark-as-read', 'a{sv}'),
    ('open-event', 'a{sv}'),
    ('pep-config', 's'),
    ('profile', 's'),
    ('server-info', 's'),
    ('services', 's'),
    ('sync-history', 's'),
]


ALWAYS_ACCOUNT_ACTIONS = {
    'export-history',
    'import-contacts',
    'open-event',
}


ONLINE_ACCOUNT_ACTIONS = {
    'add-contact',
    'remove-contact',
    'contact-info',
    'execute-command',
    'modify-gateway',
    'bookmarks',
    'import-contacts',
    'pep-config',
    'profile',
    'server-info',
    'services',
    'sync-history',
    'mark-as-read',
}


FEATURE_ACCOUNT_ACTIONS = {
    'archive',
    'blocking',
    'block-contact',
}
