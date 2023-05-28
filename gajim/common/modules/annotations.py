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


from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.structs import AnnotationNote
from nbxmpp.task import Task

from gajim.common.modules.base import BaseModule
from gajim.common.types import ConnectionT


class Annotations(BaseModule):

    _nbxmpp_extends = 'Annotations'
    _nbxmpp_methods = [
        'request_annotations',
        'set_annotations',
    ]

    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self._annotations: dict[JID | str, AnnotationNote] = {}

    def request_annotations(self) -> None:
        self._nbxmpp('Annotations').request_annotations(
            callback=self._annotations_received)

    def _annotations_received(self, task: Task) -> None:
        try:
            annotations = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._log.warning(error)
            self._annotations = {}
            return

        for note in annotations:
            self._annotations[note.jid] = note

    def get_note(self, jid: str) -> AnnotationNote | None:
        return self._annotations.get(jid)

    def set_note(self, note: AnnotationNote) -> None:
        self._annotations[note.jid] = note
        self.set_annotations(self._annotations.values())
