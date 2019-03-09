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

# XEP-0145: Annotations

from typing import Any
from typing import Dict  # pylint: disable=unused-import
from typing import Tuple

from nbxmpp.util import is_error_result

from gajim.common.types import ConnectionT
from gajim.common.modules.base import BaseModule


class Annotations(BaseModule):

    _nbxmpp_extends = 'Annotations'
    _nbxmpp_methods = [
        'request_annotations',
        'set_annotations',
    ]

    def __init__(self, con: ConnectionT):
        BaseModule.__init__(self, con)

        self._register_callback('request_annotations',
                                self._annotations_received)
        self._annotations = {}  # type: Dict[str, Any]

    def set_annotations(self):
        self._nbxmpp('Annotations').set_annotations(self._annotations.values())

    def _annotations_received(self, result):
        if is_error_result(result):
            self._annotations = {}
            return
        for note in result:
            self._annotations[note.jid] = note

    def get_note(self, jid):
        return self._annotations.get(jid)

    def set_note(self, note):
        self._annotations[note.jid] = note
        self.set_annotations()


def get_instance(*args: Any, **kwargs: Any) -> Tuple[Annotations, str]:
    return Annotations(*args, **kwargs), 'Annotations'
