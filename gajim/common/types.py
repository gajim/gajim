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
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from typing import TYPE_CHECKING

import weakref

from gi.repository import GdkPixbuf

import nbxmpp
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from gajim.common.client import Client
    from nbxmpp.client import Client as xmppClient
    from gajim.common.zeroconf.connection_zeroconf import ConnectionZeroconf
    from gajim.common.modules.contacts import CommonContact
    from gajim.common.modules.contacts import BareContact
    from gajim.common.modules.contacts import ResourceContact
    from gajim.common.modules.contacts import GroupchatContact
    from gajim.common.modules.contacts import GroupchatParticipant

    from gajim.gui_interface import Interface
    from gajim.common.settings import Settings
    from gajim.gtk.css_config import CSSConfig


InterfaceT = Union['Interface']

ConnectionT = Union['Client', 'ConnectionZeroconf']
CSSConfigT = Union['CSSConfig']

# PEP
PEPNotifyCallback = Callable[[nbxmpp.JID, nbxmpp.Node], None]
PEPHandlersDict = Dict[str, List[PEPNotifyCallback]]

# Plugins
PluginExtensionPoints = Dict[str, Tuple[Optional[Callable[..., None]],
                                        Optional[Callable[..., None]]]]

SettingsT = Union['Settings']

BookmarksDict = Dict[JID, BookmarkData]

GdkPixbufType = Union[GdkPixbuf.Pixbuf, GdkPixbuf.PixbufAnimation]

AnyCallableT = Callable[..., Any]
ObservableCbDict = dict[str, list[weakref.WeakMethod[AnyCallableT]]]

ChatContactT = Union['BareContact', 'GroupchatContact', 'GroupchatParticipant']
GroupchatContactT = Union['GroupchatContact']
