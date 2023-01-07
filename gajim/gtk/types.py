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
