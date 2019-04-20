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

Setting = namedtuple('Setting', 'kind label type value name callback data desc enabledif props')
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
    PROXY = 7
    HOSTNAME = 8
    PRIORITY = 9
    FILECHOOSER = 10
    CHANGEPASSWORD = 11


@unique
class SettingType(IntEnum):
    ACCOUNT_CONFIG = 0
    CONFIG = 1
    VALUE = 2
    ACTION = 3
    DIALOG = 4
