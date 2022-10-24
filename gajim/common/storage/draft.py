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

from __future__ import annotations

from typing import Optional

from gajim.common import types
from gajim.common.helpers import Observable


class DraftStorage(Observable):
    def __init__(self) -> None:
        Observable.__init__(self)

        self._drafts: dict[types.ChatContactT, str] = {}

    def set(self, contact: types.ChatContactT, text: str) -> None:
        if not text:
            self.remove(contact)
            return

        self._drafts[contact] = text
        self.notify('draft-update', contact, text)

    def get(self, contact: types.ChatContactT) -> Optional[str]:
        return self._drafts.get(contact)

    def remove(self, contact: types.ChatContactT) -> None:
        self._drafts.pop(contact, None)
        self.notify('draft-update', contact, None)
