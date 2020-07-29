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

from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from typing import TYPE_CHECKING

import nbxmpp

from gajim.common.const import PathType, PathLocation

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from gajim.common.client import Client
    from gajim.common.zeroconf.connection_zeroconf import ConnectionZeroconf
    from gajim.common.contacts import Contact
    from gajim.common.contacts import GC_Contact
    from gajim.common.contacts import LegacyContactsAPI
    from gajim.common.nec import NetworkEvent
    from gajim.common.nec import NetworkEventsController
    from gajim.common.logger import Logger

    from gajim.gui_interface import Interface
    from gajim.common.settings import _Settings


NetworkEventsControllerT = Union['NetworkEventsController']
InterfaceT = Union['Interface']
LoggerT = Union['Logger']

ConnectionT = Union['Client', 'ConnectionZeroconf']
ContactsT = Union['Contact', 'GC_Contact']
ContactT = Union['Contact']
LegacyContactsAPIT = Union['LegacyContactsAPI']

# PEP
PEPNotifyCallback = Callable[[nbxmpp.JID, nbxmpp.Node], None]
PEPHandlersDict = Dict[str, List[PEPNotifyCallback]]

# Configpaths
PathTuple = Tuple[Optional[PathLocation], str, Optional[PathType]]

# Plugins
PluginExtensionPoints = Dict[str, Tuple[Optional[Callable[..., None]],
                                        Optional[Callable[..., None]]]]
EventHandlersDict = Dict[str, Tuple[int, Callable[['NetworkEvent'], Optional[bool]]]]
PluginEvents = List['NetworkEvent']

SettingsT = Union['_Settings']
