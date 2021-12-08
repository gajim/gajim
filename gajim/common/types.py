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

from pathlib import Path
import weakref

from gi.repository import GdkPixbuf

import nbxmpp
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData

from gajim.common.const import PathType, PathLocation

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from gajim.common.client import Client
    from gajim.common.zeroconf.connection_zeroconf import ConnectionZeroconf
    from gajim.common.contacts import Contact
    from gajim.common.contacts import GC_Contact
    from gajim.common.contacts import LegacyContactsAPI
    from gajim.common.modules.contacts import CommonContact
    from gajim.common.modules.contacts import BareContact
    from gajim.common.modules.contacts import ResourceContact
    from gajim.common.modules.contacts import GroupchatContact
    from gajim.common.modules.contacts import GroupchatParticipant
    from gajim.common.nec import NetworkEvent
    from gajim.common.nec import NetworkEventsController

    from gajim.gui_interface import Interface
    from gajim.common.settings import Settings
    from gajim.gtk.css_config import CSSConfig


NetworkEventsControllerT = Union['NetworkEventsController']
InterfaceT = Union['Interface']

ConnectionT = Union['Client', 'ConnectionZeroconf']
ContactsT = Union['Contact', 'GC_Contact']
ContactT = Union['Contact']
CSSConfigT = Union['CSSConfig']

# PEP
PEPNotifyCallback = Callable[[nbxmpp.JID, nbxmpp.Node], None]
PEPHandlersDict = Dict[str, List[PEPNotifyCallback]]

# Configpaths
PathTuple = Tuple[Optional[PathLocation], Path, Optional[PathType]]

# Plugins
PluginExtensionPoints = Dict[str, Tuple[Optional[Callable[..., None]],
                                        Optional[Callable[..., None]]]]
EventHandlersDict = Dict[
    str, Tuple[int, Callable[['NetworkEvent'], Optional[bool]]]]
PluginEvents = List['NetworkEvent']

SettingsT = Union['Settings']

BookmarksDict = Dict[JID, BookmarkData]

GdkPixbufType = Union[GdkPixbuf.Pixbuf, GdkPixbuf.PixbufAnimation]

AnyCallableT = Callable[..., Any]
ObservableCbDict = dict[str, list[weakref.WeakMethod[AnyCallableT]]]
