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
    from gajim.common.connection import Connection
    from gajim.common.zeroconf.connection_zeroconf import ConnectionZeroconf
    from gajim.common.contacts import Contact
    from gajim.common.contacts import GC_Contact

ConnectionT = Union['Connection', 'ConnectionZeroconf']
ContactT = Union['Contact', 'GC_Contact']

UserTuneDataT = Optional[Tuple[str, str, str, str, str]]

# PEP
PEPNotifyCallback = Callable[[nbxmpp.JID, nbxmpp.Node], None]
PEPRetractCallback = Callable[[nbxmpp.JID, str], None]
PEPHandlersDict = Dict[str, List[Tuple[PEPNotifyCallback, PEPRetractCallback]]]

# Configpaths
PathTuple = Tuple[Optional[PathLocation], str, Optional[PathType]]
