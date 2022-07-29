# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# Types for typechecking

from typing import Any
from typing import Callable
from typing import Optional
from typing import Union
from typing import TYPE_CHECKING

import weakref

from gi.repository import GdkPixbuf

import nbxmpp
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData

if TYPE_CHECKING:
    from gajim.common.client import Client
    from nbxmpp.client import Client as xmppClient  # noqa: F401
    from gajim.common.modules.contacts import CommonContact  # noqa: F401
    from gajim.common.modules.contacts import BareContact
    from gajim.common.modules.contacts import ResourceContact
    from gajim.common.modules.contacts import GroupchatContact
    from gajim.common.modules.contacts import GroupchatParticipant

    from gajim.gui_interface import Interface
    from gajim.common.settings import Settings
    from gajim.gtk.css_config import CSSConfig

    from gajim.plugins.pluginmanager import PluginManager
    from gajim.plugins.repository import PluginRepository

    ContactT = Union[BareContact,
                     ResourceContact,
                     GroupchatContact,
                     GroupchatParticipant]


InterfaceT = Union['Interface']
PluginManagerT = Union['PluginManager']
PluginRepositoryT = Union['PluginRepository']

ConnectionT = Union['Client']
CSSConfigT = Union['CSSConfig']

# PEP
PEPNotifyCallback = Callable[[nbxmpp.JID, nbxmpp.Node], None]
PEPHandlersDict = dict[str, list[PEPNotifyCallback]]

# Plugins
PluginExtensionPoints = dict[str, tuple[Optional[Callable[..., None]],
                                        Optional[Callable[..., None]]]]

SettingsT = Union['Settings']

BookmarksDict = dict[JID, BookmarkData]

GdkPixbufType = Union[GdkPixbuf.Pixbuf, GdkPixbuf.PixbufAnimation]

AnyCallableT = Callable[..., Any]
ObservableCbDict = dict[str, list[weakref.WeakMethod[AnyCallableT]]]

BareContactT = Union['BareContact']
ChatContactT = Union['BareContact', 'GroupchatContact', 'GroupchatParticipant']
OneOnOneContactT = Union['BareContact', 'GroupchatParticipant']
GroupchatContactT = Union['GroupchatContact']
