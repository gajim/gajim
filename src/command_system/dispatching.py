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
The backbone of the command system. Provides automatic dispatching which does
not require explicit registering commands or containers and remains active even
after everything is done, so new commands can be added during the runtime.
"""

from types import NoneType

class Dispatcher(type):

    containers = {}
    commands = {}

    @classmethod
    def register_host(klass, host):
        klass.containers[host] = []

    @classmethod
    def register_container(klass, container):
        for host in container.HOSTS:
            klass.containers[host].append(container)

    @classmethod
    def register_commands(klass, container):
        klass.commands[container] = {}
        for command in klass.traverse_commands(container):
            for name in command.names:
                klass.commands[container][name] = command

    @classmethod
    def get_command(klass, host, name):
        for container in klass.containers[host]:
            command = klass.commands[container].get(name)
            if command:
                return command

    @classmethod
    def list_commands(klass, host):
        for container in klass.containers[host]:
            commands = klass.commands[container]
            for name, command in commands.iteritems():
                yield name, command

    @classmethod
    def traverse_commands(klass, container):
        for name in dir(container):
            attribute = getattr(container, name)
            if klass.is_command(attribute):
                yield attribute

    @staticmethod
    def is_root(ns):
        meta = ns.get('__metaclass__', NoneType)
        return issubclass(meta, Dispatcher)

    @staticmethod
    def is_command(attribute):
        name = attribute.__class__.__name__
        return name == 'Command'

class HostDispatcher(Dispatcher):

    def __init__(klass, name, bases, ns):
        if not Dispatcher.is_root(ns):
            HostDispatcher.register_host(klass)
        super(HostDispatcher, klass).__init__(name, bases, ns)

class ContainerDispatcher(Dispatcher):

    def __init__(klass, name, bases, ns):
        if not Dispatcher.is_root(ns):
            ContainerDispatcher.register_container(klass)
            ContainerDispatcher.register_commands(klass)
        super(ContainerDispatcher, klass).__init__(name, bases, ns)
