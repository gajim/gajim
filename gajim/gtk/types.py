# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Types for typechecking

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import TypeVar

import cairo

if TYPE_CHECKING:
    from gajim.gtk.control import ChatControl  # noqa: F401
    from gajim.gtk.conversation.message_widget import \
        MessageWidget  # noqa: F401
    from gajim.gtk.conversation.rows.call import CallRow  # noqa: F401
    from gajim.gtk.conversation.rows.command_output import \
        CommandOutputRow  # noqa: F401
    from gajim.gtk.conversation.rows.date import DateRow  # noqa: F401
    from gajim.gtk.conversation.rows.file_transfer import \
        FileTransferRow  # noqa: F401
    from gajim.gtk.conversation.rows.file_transfer_jingle import \
        FileTransferJingleRow  # noqa: E501, F401
    from gajim.gtk.conversation.rows.info import InfoMessage  # noqa: F401
    from gajim.gtk.conversation.rows.message import MessageRow  # noqa: F401
    from gajim.gtk.conversation.rows.muc_join_left import \
        MUCJoinLeft  # noqa: F401
    from gajim.gtk.conversation.rows.muc_subject import \
        MUCSubject  # noqa: F401
    from gajim.gtk.conversation.rows.read_marker import \
        ReadMarkerRow  # noqa: F401
    from gajim.gtk.conversation.rows.scroll_hint import \
        ScrollHintRow  # noqa: F401
    from gajim.gtk.conversation.rows.user_status import \
        UserStatus  # noqa: F401
    from gajim.gtk.conversation.view import ConversationView  # noqa: F401


SomeSurface = TypeVar('SomeSurface', bound=cairo.Surface)
