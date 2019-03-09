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

# XEP-0163: Personal Eventing Protocol

from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import nbxmpp

from gajim.common.types import ConnectionT
from gajim.common.modules.base import BaseModule


class PEP(BaseModule):
    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self.supported = False

    def pass_disco(self,
                   from_: nbxmpp.JID,
                   identities: List[Dict[str, str]],
                   _features: List[str],
                   _data: List[nbxmpp.DataForm],
                   _node: str) -> None:
        for identity in identities:
            if identity['category'] == 'pubsub':
                if identity.get('type') == 'pep':
                    self._log.info('Discovered PEP support: %s', from_)
                    self.supported = True


def get_instance(*args: Any, **kwargs: Any) -> Tuple[PEP, str]:
    return PEP(*args, **kwargs), 'PEP'
