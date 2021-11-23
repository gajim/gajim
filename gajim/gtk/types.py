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

from typing import Union

from .conversation.rows.call import CallRow
from .conversation.rows.command_output import CommandOutputRow
from .conversation.rows.date import DateRow
from .conversation.rows.file_transfer_jingle import FileTransferJingleRow
from .conversation.rows.file_transfer import FileTransferRow
from .conversation.rows.info import InfoMessage
from .conversation.rows.message import MessageRow
from .conversation.rows.muc_join_left import MUCJoinLeft
from .conversation.rows.muc_subject import MUCSubject
from .conversation.rows.muc_user_status import MUCUserStatus
from .conversation.rows.read_marker import ReadMarkerRow
from .conversation.rows.scroll_hint import ScrollHintRow


ConversationRowType = Union[
    CallRow,
    CommandOutputRow,
    DateRow,
    FileTransferJingleRow,
    FileTransferRow,
    InfoMessage,
    MessageRow,
    MUCJoinLeft,
    MUCSubject,
    MUCUserStatus,
    ReadMarkerRow,
    ScrollHintRow
]
