# Copyright (C) 2009  Alexander Cherniuk <ts33kr@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
The module defines a set of command hosts, which are bound to a different
command processors, which are the source of commands.
"""

from ..framework import CommandHost

class ChatCommands(CommandHost):
    """
    This command host is bound to the command processor which processes commands
    from a chat.
    """
    pass

class PrivateChatCommands(CommandHost):
    """
    This command host is bound to the command processor which processes commands
    from a private chat.
    """
    pass

class GroupChatCommands(CommandHost):
    """
    This command host is bound to the command processor which processes commands
    from a group chat.
    """
    pass
