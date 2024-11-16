# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Types for typechecking

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import TypeVar

import cairo

if TYPE_CHECKING:
    from gajim.gtk.control import ChatControl
    from gajim.gtk.conversation.message_widget import MessageWidget
    from gajim.gtk.conversation.rows.call import CallRow
    from gajim.gtk.conversation.rows.command_output import CommandOutputRow
    from gajim.gtk.conversation.rows.date import DateRow
    from gajim.gtk.conversation.rows.file_transfer import FileTransferRow
    from gajim.gtk.conversation.rows.file_transfer_jingle import FileTransferJingleRow
    from gajim.gtk.conversation.rows.info import InfoMessage
    from gajim.gtk.conversation.rows.message import MessageRow
    from gajim.gtk.conversation.rows.muc_join_left import MUCJoinLeft
    from gajim.gtk.conversation.rows.muc_subject import MUCSubject
    from gajim.gtk.conversation.rows.read_marker import ReadMarkerRow
    from gajim.gtk.conversation.rows.scroll_hint import ScrollHintRow
    from gajim.gtk.conversation.rows.user_status import UserStatus
    from gajim.gtk.conversation.view import ConversationView


SomeSurface = TypeVar("SomeSurface", bound=cairo.Surface)
