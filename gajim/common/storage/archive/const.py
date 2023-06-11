# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from enum import IntEnum


class MessageState(IntEnum):
    PENDING = 1
    ACKNOWLEDGED = 2


class MessageType(IntEnum):
    CHAT = 1
    GROUPCHAT = 2
    PM = 3


class ChatDirection(IntEnum):
    INCOMING = 1
    OUTGOING = 2
