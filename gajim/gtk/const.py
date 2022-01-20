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
from typing import Callable
from typing import NamedTuple
from typing import Optional
from typing import Union

from enum import Enum
from enum import IntEnum
from enum import unique

from gajim.common.setting_values import AllSettingsT


class Filter(NamedTuple):
    name: str
    pattern: Union[str, list[str]]
    default: bool


class Setting(NamedTuple):
    kind: SettingKind
    label: str
    type: SettingType
    value: Optional[AllSettingsT] = None
    name: Optional[str] = None
    callback: Optional[Callable[..., None]] = None
    data: Optional[Any] = None
    desc: Optional[str] = None
    bind: Optional[str] = None
    inverted: Optional[bool] = None
    enabled_func: Optional[Callable[..., bool]] = None
    props: Optional[dict[str, Any]] = None


DEFAULT_WORKSPACE_COLOR = 'rgb(191,15,167)'

# Drag and drop target type URI list (for dropped files)
TARGET_TYPE_URI_LIST = 80

UNLOAD_CHAT_TIME = 300  # seconds


@unique
class Theme(IntEnum):
    NOT_DARK = 0
    DARK = 1
    SYSTEM = 2


class GajimIconSet(Enum):
    BRUNO = 'bruno'
    DCRAVEN = 'dcraven'
    GNOME = 'gnome'
    GOOJIM = 'goojim'
    GOTA = 'gota'
    JABBERBULB = 'jabberbulb'
    SUN = 'sun'
    WROOP = 'wroop'


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
    'AccountsWindow': 'gajim.gui.accounts',
    'AccountWizard': 'gajim.gui.account_wizard',
    'AddContact': 'gajim.gui.add_contact',
    'AdhocMUC': 'gajim.gui.adhoc_muc',
    'AdvancedConfig': 'gajim.gui.advanced_config',
    'BlockingList': 'gajim.gui.blocking',
    'Bookmarks': 'gajim.gui.bookmarks',
    'CertificateDialog': 'gajim.gui.certificate_dialog',
    'ChangePassword': 'gajim.gui.change_password',
    'ContactInfo': 'gajim.gui.contact_info',
    'CreateGroupchatWindow': 'gajim.gui.groupchat_creation',
    'Features': 'gajim.gui.features',
    'GroupchatConfig': 'gajim.gui.groupchat_config',
    'GroupChatInvitation': 'gajim.gui.groupchat_invitation',
    'GroupchatJoin': 'gajim.gui.groupchat_join',
    'HistoryExport': 'gajim.gui.history_export',
    'HistorySyncAssistant': 'gajim.gui.history_sync',
    'MamPreferences': 'gajim.gui.mam_preferences',
    'ManageProxies': 'gajim.gui.proxies',
    'ManageSounds': 'gajim.gui.manage_sounds',
    'PasswordDialog': 'gajim.gui.password_dialog',
    'PEPConfig': 'gajim.gui.pep_config',
    'PluginsWindow': 'gajim.plugins.gui',
    'Preferences': 'gajim.gui.preferences',
    'ProfileWindow': 'gajim.gui.profile',
    'RemoveAccount': 'gajim.gui.remove_account',
    'RosterItemExchange': 'gajim.gui.roster_item_exchange',
    'ServerInfo': 'gajim.gui.server_info',
    'ServiceDiscoveryWindow': 'gajim.gui.discovery',
    'ServiceRegistration': 'gajim.gui.service_registration',
    'SingleMessageWindow': 'gajim.gui.single_message',
    'SSLErrorDialog': 'gajim.gui.ssl_error_dialog',
    'StartChatDialog': 'gajim.gui.start_chat',
    'SynchronizeAccounts': 'gajim.gui.synchronize_accounts',
    'Themes': 'gajim.gui.themes',
    'WorkspaceDialog': 'gajim.gui.workspace_dialog',
    'XMLConsoleWindow': 'gajim.gui.xml_console',
}
