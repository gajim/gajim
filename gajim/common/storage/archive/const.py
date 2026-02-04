# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal

from enum import IntEnum


class MessageState(IntEnum):
    PENDING = 1
    ACKNOWLEDGED = 2


class MessageType(IntEnum):
    CHAT = 1
    GROUPCHAT = 2
    PM = 3

    @classmethod
    def from_str(cls, string: str) -> MessageType:
        return cls[string.upper()]

    def to_str(self) -> Literal["chat", "groupchat", "pm"]:
        return self.name.lower()  # type: ignore


class ChatDirection(IntEnum):
    INCOMING = 1
    OUTGOING = 2
