# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

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

    def get(self, contact: types.ChatContactT) -> str | None:
        return self._drafts.get(contact)

    def remove(self, contact: types.ChatContactT) -> None:
        self._drafts.pop(contact, None)
        self.notify('draft-update', contact, None)
