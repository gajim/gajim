# Copyright (c) 2009-2010, Alexander Cherniuk (ts33kr@gmail.com)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Provides a glue to tie command system framework and the actual code
where it would be dropped in. Defines a little bit of scaffolding to
support interaction between the two and a few utility methods so you
don't need to dig up the code itself to write basic commands.
"""

from traceback import print_exc

# from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _

from gajim.command_system.framework import CommandProcessor
from gajim.command_system.errors import CommandError
from gajim.command_system.errors import NoCommandError


class ChatCommandProcessor(CommandProcessor):
    """
    A basic scaffolding to provide convenient interaction between the
    command system and chat controls. It will be merged directly into
    the controls, by ChatCommandProcessor being among superclasses of
    the controls.
    """

    def process_as_command(self, text):
        self.command_succeeded = False
        parents = super(ChatCommandProcessor, self)
        flag = parents.process_as_command(text)
        if flag and self.command_succeeded:
            self.clear_input()
        return flag

    def execute_command(self, name, arguments):
        try:
            parents = super(ChatCommandProcessor, self)
            parents.execute_command(name, arguments)
        except NoCommandError as error:
            details = dict(name=error.name, message=error.message)
            message = "%(name)s: %(message)s\n" % details
            message += "Try using the //%(name)s or /say /%(name)s " % details
            message += "construct if you intended to send it as a text."
            self.echo_error(message)
        except CommandError as error:
            self.echo_error("%s: %s" % (error.name, error.message))
        except Exception:
            self.echo_error(_("Error during command execution!"))
            print_exc()
        else:
            self.command_succeeded = True

    def looks_like_command(self, text, body, name, arguments):
        # Command escape stuff goes here. If text was prepended by the
        # command prefix twice, like //not_a_command (if prefix is set
        # to /) then it will be escaped, that is sent just as a regular
        # message with one (only one) prefix removed, so message will be
        # /not_a_command.
        if body.startswith(self.COMMAND_PREFIX):
            self.send(body)
            return True

    def command_preprocessor(self, command, name, arguments, args, kwargs):
        # If command argument contain h or help option - forward it to
        # the /help command. Don't forget to pass self, as all commands
        # are unbound. And also don't forget to print output.
        if 'h' in kwargs or 'help' in kwargs:
            help_ = self.get_command('help')
            self.echo(help_(self, name))
            return True

    def command_postprocessor(self, command, name, arguments, args, kwargs,
                              value):
        # If command returns a string - print it to a user. A convenient
        # and sufficient in most simple cases shortcut to a using echo.
        if value and isinstance(value, str):
            self.echo(value)


class CommandTools:
    """
    Contains a set of basic tools and shortcuts you can use in your
    commands to perform some simple operations. These will be merged
    directly into the controls, by CommandTools being among superclasses
    of the controls.
    """

    def __init__(self):
        pass

    def echo(self, text, is_error=False):
        """
        Print given text to the user, as a regular command output.
        """
        self.conversation_view.add_command_output(text, is_error)

    def echo_error(self, text):
        """
        Print given text to the user, as an error command output.
        """
        self.echo(text, is_error=True)

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

    @property
    def connection(self):
        """
        Get the current connection object.
        """
        return app.connections[self.account]

    @property
    def full_jid(self):
        """
        Get a full JID of the contact.
        """
        return self.contact.jid
