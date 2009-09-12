# Copyright (C) 2009  red-agent <hell.director@gmail.com>
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
Provides an actual implementation of the standard commands.
"""

from common import gajim

from framework import command, CommandError
from middleware import ChatMiddleware

class CommonCommands(ChatMiddleware):
    """
    Here defined commands will be common to all, chat, private chat and group
    chat. Keep in mind that self is set to an instance of either ChatControl,
    PrivateChatControl or GroupchatControl when command is being called.
    """

    IS_COMMAND_PROCESSOR = True

    @command
    def clear(self):
        """
        Clear the text window
        """
        self.conv_textview.clear()

    @command
    def compact(self):
        """
        Hide the chat buttons
        """
        self.chat_buttons_set_visible(not self.hide_chat_buttons)

    @command
    def help(self, command=None, all=False):
        """
        Show help on a given command or a list of available commands if -(-a)ll is
        given
        """
        if command:
            command = self.retrieve_command(command)

            doc = _(command.extract_doc())
            usage = command.extract_arg_usage()

            if doc:
                return (doc + '\n\n' + usage) if command.usage else doc
            else:
                return usage
        elif all:
            for command in self.list_commands():
                names = ', '.join(command.names)
                description = command.extract_description()

                self.echo("%s - %s" % (names, description))
        else:
            self.echo(self._help_(self, 'help'))

    @command(raw=True)
    def say(self, message):
        """
        Send a message to the contact
        """
        self.send(message)

    @command(raw=True)
    def me(self, action):
        """
        Send action (in the third person) to the current chat
        """
        self.send("/me %s" % action)

class ChatCommands(CommonCommands):
    """
    Here defined commands will be unique to a chat. Use it as a hoster to provide
    commands which should be unique to a chat. Keep in mind that self is set to
    an instance of ChatControl when command is being called.
    """

    IS_COMMAND_PROCESSOR = True
    INHERITED = True

    @command
    def ping(self):
        """
        Send a ping to the contact
        """
        if self.account == gajim.ZEROCONF_ACC_NAME:
            raise CommandError(_('Command is not supported for zeroconf accounts'))
        gajim.connections[self.account].sendPing(self.contact)

class PrivateChatCommands(CommonCommands):
    """
    Here defined commands will be unique to a private chat. Use it as a hoster to
    provide commands which should be unique to a private chat. Keep in mind that
    self is set to an instance of PrivateChatControl when command is being called.
    """

    IS_COMMAND_PROCESSOR = True
    INHERITED = True

class GroupChatCommands(CommonCommands):
    """
    Here defined commands will be unique to a group chat. Use it as a hoster to
    provide commands which should be unique to a group chat. Keep in mind that
    self is set to an instance of GroupchatControl when command is being called.
    """

    IS_COMMAND_PROCESSOR = True
    INHERITED = True
