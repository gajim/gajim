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

from collections import namedtuple
from enum import Enum
from enum import IntEnum
from enum import unique

Filter = namedtuple('Filter', 'name pattern default')

Setting = namedtuple('Setting', 'kind label type value name callback data desc '
                                'bind inverted enabled_func props')
Setting.__new__.__defaults__ = (None,) * len(Setting._fields)  # type: ignore


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
    'HistorySyncAssistant': 'gajim.gui.history_sync',
    'ServerInfo': 'gajim.gui.server_info',
    'MamPreferences': 'gajim.gui.mam_preferences',
    'Preferences': 'gajim.gui.preferences',
    'CreateGroupchatWindow': 'gajim.gui.groupchat_creation',
    'StartChatDialog': 'gajim.gui.start_chat',
    'AddContact': 'gajim.gui.add_contact',
    'SingleMessageWindow': 'gajim.gui.single_message',
    'Bookmarks': 'gajim.gui.bookmarks',
    'AccountWizard': 'gajim.gui.account_wizard',
    'ManageProxies': 'gajim.gui.proxies',
    'ManageSounds': 'gajim.gui.manage_sounds',
    'ServiceDiscoveryWindow': 'gajim.gui.discovery',
    'BlockingList': 'gajim.gui.blocking',
    'XMLConsoleWindow': 'gajim.gui.xml_console',
    'GroupchatJoin': 'gajim.gui.groupchat_join',
    'PEPConfig': 'gajim.gui.pep_config',
    'HistoryManager': 'gajim.history_manager',
    'GroupchatConfig': 'gajim.gui.groupchat_config',
    'ProfileWindow': 'gajim.gui.profile',
    'SSLErrorDialog': 'gajim.gui.ssl_error_dialog',
    'Themes': 'gajim.gui.themes',
    'AdvancedConfig': 'gajim.gui.advanced_config',
    'CertificateDialog': 'gajim.gui.certificate_dialog',
    'RemoveAccount': 'gajim.gui.remove_account',
    'ChangePassword': 'gajim.gui.change_password',
    'PluginsWindow': 'gajim.plugins.gui',
    'Features': 'gajim.gui.features',
    'GroupChatInvitation': 'gajim.gui.groupchat_invitation',
    'ContactInfo': 'gajim.gui.contact_info',
    'WorkspaceDialog': 'gajim.gui.workspace_dialog',
    'RosterItemExchange': 'gajim.gui.roster_item_exchange',
    'ServiceRegistration': 'gajim.gui.service_registration',
    'SynchronizeAccounts': 'gajim.gui.synchronize_accounts',
    'AdhocMUC': 'gajim.gui.adhoc_muc',
    'PasswordDialog': 'gajim.gui.password_dialog',
}
