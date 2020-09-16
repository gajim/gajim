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

@unique
class Theme(IntEnum):
    NOT_DARK = 0
    DARK = 1
    SYSTEM = 2


class GajimIconSet(Enum):
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
    'HistorySyncAssistant': 'gajim.gtk.history_sync',
    'ServerInfo': 'gajim.gtk.server_info',
    'MamPreferences': 'gajim.gtk.mam_preferences',
    'Preferences': 'gajim.gtk.preferences',
    'CreateGroupchatWindow': 'gajim.gtk.groupchat_creation',
    'StartChatDialog': 'gajim.gtk.start_chat',
    'AddNewContactWindow': 'gajim.gtk.add_contact',
    'SingleMessageWindow': 'gajim.gtk.single_message',
    'Bookmarks': 'gajim.gtk.bookmarks',
    'AccountWizard': 'gajim.gtk.account_wizard',
    'HistoryWindow': 'gajim.gtk.history',
    'ManageProxies': 'gajim.gtk.proxies',
    'ManageSounds': 'gajim.gtk.manage_sounds',
    'ServiceDiscoveryWindow': 'gajim.gtk.discovery',
    'BlockingList': 'gajim.gtk.blocking',
    'XMLConsoleWindow': 'gajim.gtk.xml_console',
    'GroupchatJoin': 'gajim.gtk.groupchat_join',
    'PEPConfig': 'gajim.gtk.pep_config',
    'HistoryManager': 'gajim.history_manager',
    'GroupchatConfig': 'gajim.gtk.groupchat_config',
    'ProfileWindow': 'gajim.gtk.profile',
    'SSLErrorDialog': 'gajim.gtk.ssl_error_dialog',
    'Themes': 'gajim.gtk.themes',
    'AdvancedConfig': 'gajim.gtk.advanced_config',
    'CertificateDialog': 'gajim.gtk.dialogs',
    'SubscriptionRequest': 'gajim.gtk.subscription_request',
    'RemoveAccount': 'gajim.gtk.remove_account',
    'ChangePassword': 'gajim.gtk.change_password',
    'PluginsWindow': 'gajim.plugins.gui',
    'Features': 'gajim.gtk.features',
    'StatusChange': 'gajim.gtk.status_change',
}
