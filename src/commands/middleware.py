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
Provides a glue to tie command system framework and the actual code where it
would be dropped in. Defines a little bit of scaffolding to support interaction
between the two and a few utility methods so you don't need to dig up the host
code to write basic commands.
"""
from common import gajim

from types import StringTypes
from framework import CommandProcessor, CommandError
from traceback import print_exc

class ChatMiddleware(CommandProcessor):
    """
    Provides basic scaffolding for the convenient interaction with ChatControl.
    Also provides some few basic utilities for the same purpose.
    """

    def execute_command(self, text, name, arguments):
        try:
            super(ChatMiddleware, self).execute_command(text, name, arguments)
        except CommandError, exception:
            self.echo("%s: %s" %(exception.name, exception.message), 'error')
        except Exception:
            self.echo("An error occured while trying to execute the command", 'error')
            print_exc()
        finally:
            self.add_history(text)
            self.clear_input()

    def looks_like_command(self, text, name, arguments):
        # Command escape stuff ggoes here. If text was prepended by the command
        # prefix twice, like //not_a_command (if prefix is set to /) then it
        # will be escaped, that is sent just as a regular message with one (only
        # one) prefix removed, so message will be /not_a_command.
        if name.startswith(self.COMMAND_PREFIX):
            self._say_(self, text)
            return True

    def command_preprocessor(self, name, command, arguments, args, kwargs):
        if 'h' in kwargs or 'help' in kwargs:
            # Forwarding to the /help command. Dont forget to pass self, as
            # all commands are unbound. And also don't forget to print output.
            self.echo(self._help_(self, name))
            return True

    def command_postprocessor(self, name, command, arguments, args, kwargs, value):
        if value and isinstance(value, StringTypes):
            self.echo(value)

    def echo(self, text, kind='info'):
        """
        Print given text to the user.
        """
        self.print_conversation(str(text), kind)

    def send(self, text):
        """
        Send a message to the contact.
        """
        self.send_message(text, process_commands=False)

    def set_input(self, text):
        """
        Set given text into the input.
        """
        message_buffer = self.msg_textview.get_buffer()
        message_buffer.set_text(text)

    def clear_input(self):
        """
        Clear input.
        """
        self.set_input(str())

    def add_history(self, text):
        """
        Add given text to the input history, so user can scroll through it
        using ctrl + up/down arrow keys.
        """
        self.save_sent_message(text)

    @property
    def connection(self):
        """
        Get the current connection object.
        """
        return gajim.connections[self.account]
