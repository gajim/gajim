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

"""
The backbone of the command system. Provides automatic dispatching which
does not require explicit registering commands or containers and remains
active even after everything is done, so new commands can be added
during the runtime.
"""

from types import NoneType

class Dispatcher(type):

    containers = {}
    commands = {}

    @classmethod
    def register_host(cls, host):
        cls.containers[host] = []

    @classmethod
    def register_container(cls, container):
        for host in container.HOSTS:
            cls.containers[host].append(container)

    @classmethod
    def register_commands(cls, container):
        cls.commands[container] = {}
        for command in cls.traverse_commands(container):
            for name in command.names:
                cls.commands[container][name] = command

    @classmethod
    def get_command(cls, host, name):
        for container in cls.containers[host]:
            command = cls.commands[container].get(name)
            if command:
                return command

    @classmethod
    def list_commands(cls, host):
        for container in cls.containers[host]:
            commands = cls.commands[container]
            for name, command in commands.iteritems():
                yield name, command

    @classmethod
    def traverse_commands(cls, container):
        for name in dir(container):
            attribute = getattr(container, name)
            if cls.is_command(attribute):
                yield attribute

    @staticmethod
    def is_root(ns):
        metaclass = ns.get('__metaclass__', NoneType)
        return issubclass(metaclass, Dispatcher)

    @staticmethod
    def is_command(attribute):
        from framework import Command
        return isinstance(attribute, Command)

class HostDispatcher(Dispatcher):

    def __init__(self, name, bases, ns):
        if not Dispatcher.is_root(ns):
            HostDispatcher.register_host(self)
        super(HostDispatcher, self).__init__(name, bases, ns)

class ContainerDispatcher(Dispatcher):

    def __init__(self, name, bases, ns):
        if not Dispatcher.is_root(ns):
            ContainerDispatcher.register_container(self)
            ContainerDispatcher.register_commands(self)
        super(ContainerDispatcher, self).__init__(name, bases, ns)
