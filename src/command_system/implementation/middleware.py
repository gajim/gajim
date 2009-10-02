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
between the two and a few utility methods so you don't need to dig up the code
itself code to write basic commands.
"""

from types import StringTypes
from traceback import print_exc

from common import gajim

from ..framework import CommandProcessor
from ..errors import CommandError

class ChatCommandProcessor(CommandProcessor):
    """
    A basic scaffolding to provide convenient interaction between the command
    system and chat controls.
    """

    def process_as_command(self, text):
        flag = super(ChatCommandProcessor, self).process_as_command(text)
        if flag:
            self.add_history(text)
            self.clear_input()
        return flag

    def execute_command(self, name, arguments):
        try:
            super(ChatCommandProcessor, self).execute_command(name, arguments)
        except CommandError, error:
            self.echo("%s: %s" %(error.name, error.message), 'error')
        except Exception:
            self.echo("An error occured while trying to execute the command", 'error')
            print_exc()

    def looks_like_command(self, text, body, name, arguments):
        # Command escape stuff ggoes here. If text was prepended by the command
        # prefix twice, like //not_a_command (if prefix is set to /) then it
        # will be escaped, that is sent just as a regular message with one (only
        # one) prefix removed, so message will be /not_a_command.
        if body.startswith(self.COMMAND_PREFIX):
            self.send(body)
            return True

    def command_preprocessor(self, command, name, arguments, args, kwargs):
        # If command argument contain h or help option - forward it to the /help
        # command. Dont forget to pass self, as all commands are unbound. And
        # also don't forget to print output.
        if 'h' in kwargs or 'help' in kwargs:
            help = self.get_command('help')
            self.echo(help(self, name))
            return True

    def command_postprocessor(self, command, name, arguments, args, kwargs, value):
        # If command returns a string - print it to a user. A convenient and
        # sufficient in most simple cases shortcut to a using echo.
        if value and isinstance(value, StringTypes):
            self.echo(value)

class CommandTools:
    """
    Contains a set of basic tools and shortcuts you can use in your commands to
    performe some simple operations.
    """

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
        buffer = self.msg_textview.get_buffer()
        buffer.set_text(text)

    def clear_input(self):
        """
        Clear input.
        """
        self.set_input(str())

    def add_history(self, text):
        """
        Add given text to the input history, so user can scroll through it using
        ctrl + up/down arrow keys.
        """
        self.save_sent_message(text)

    @property
    def connection(self):
        """
        Get the current connection object.
        """
        return gajim.connections[self.account]
