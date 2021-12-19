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
from typing import Dict
from typing import Union
from typing import Optional

from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.structs import AnnotationNote
from nbxmpp.protocol import JID

from gajim.common.types import ConnectionT
from gajim.common.modules.base import BaseModule


class Annotations(BaseModule):

    _nbxmpp_extends = 'Annotations'
    _nbxmpp_methods = [
        'request_annotations',
        'set_annotations',
    ]

    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self._annotations: Dict[Union[JID, str], AnnotationNote] = {}

    def request_annotations(self) -> None:
        self._nbxmpp('Annotations').request_annotations(
            callback=self._annotations_received)

    def _annotations_received(self, task: Any) -> None:
        try:
            annotations = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._log.warning(error)
            self._annotations = {}
            return

        for note in annotations:
            self._annotations[note.jid] = note

    def get_note(self, jid: str) -> Optional[AnnotationNote]:
        return self._annotations.get(jid)

    def set_note(self, note: AnnotationNote) -> None:
        self._annotations[note.jid] = note
        self.set_annotations(self._annotations.values())
