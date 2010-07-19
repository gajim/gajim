# Copyright (C) 2009-2010  Alexander Cherniuk <ts33kr@gmail.com>
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

class BaseError(Exception):
    """
    Common base for errors which relate to a specific command.
    Encapsulates everything needed to identify a command, by either its
    object or name.
    """

    def __init__(self, message, command=None, name=None):
        self.message = message

        self.command = command
        self.name = name

        if command and not name:
            self.name = command.first_name

        super(BaseError, self).__init__()

    def __str__(self):
        return self.message

class DefinitionError(BaseError):
    """
    Used to indicate errors occured on command definition.
    """
    pass

class CommandError(BaseError):
    """
    Used to indicate errors occured during command execution.
    """
    pass

class NoCommandError(BaseError):
    """
    Used to indicate an inability to find the specified command.
    """
    pass
