# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gajim.common import types
from gajim.common.const import Draft
from gajim.common.helpers import Observable


class DraftStorage(Observable):
    def __init__(self) -> None:
        Observable.__init__(self)

        self._drafts: dict[types.ChatContactT, Draft] = {}

    def set(
        self,
        contact: types.ChatContactT,
        draft: Draft | None,
    ) -> None:

        if draft is None:
            self.remove(contact)
            return

        self._drafts[contact] = draft
        self.notify('draft-update', contact, draft)

    def get(
        self,
        contact: types.ChatContactT
    ) -> Draft | None:

        return self._drafts.get(contact)

    def remove(self, contact: types.ChatContactT) -> None:
        self._drafts.pop(contact, None)
        self.notify('draft-update', contact, None)
