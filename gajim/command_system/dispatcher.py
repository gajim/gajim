# Copyright (c) 2010, Alexander Cherniuk (ts33kr@gmail.com)
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
Backbone of the command system. Provides smart and controllable
dispatching mechanism with an auto-discovery functionality. In addition
to automatic discovery and dispatching, also features manual control
over the process.
"""

from typing import Any

from gajim.command_system.tools import remove

COMMANDS: dict[Any, Any] = {}
CONTAINERS: dict[Any, Any] = {}


def add_host(host):
    CONTAINERS[host] = []


def remove_host(host):
    remove(CONTAINERS, host)


def add_container(container):
    for host in container.HOSTS:
        CONTAINERS[host].append(container)


def remove_container(container):
    for host in container.HOSTS:
        remove(CONTAINERS[host], container)


def add_commands(container):
    commands = COMMANDS.setdefault(container, {})
    for command in traverse_commands(container):
        for name in command.names:
            commands[name] = command


def remove_commands(container):
    remove(COMMANDS, container)


def traverse_commands(container):
    for name in dir(container):
        attribute = getattr(container, name)
        if is_command(attribute):
            yield attribute


def is_command(attribute):
    from gajim.command_system.framework import Command
    return isinstance(attribute, Command)


def is_root(namespace):
    metaclass = namespace.get("__metaclass__", None)
    if not metaclass:
        return False
    return issubclass(metaclass, Dispatchable)


def get_command(host, name):
    for container in CONTAINERS[host]:
        command = COMMANDS[container].get(name)
        if command:
            return command


def list_commands(host):
    for container in CONTAINERS[host]:
        commands = COMMANDS[container]
        for name, command in commands.items():
            yield name, command


class Dispatchable(type):
    # pylint: disable=no-value-for-parameter
    def __init__(cls, name, bases, namespace):
        parents = super(Dispatchable, cls)
        parents.__init__(name, bases, namespace)
        if not is_root(namespace):
            cls.dispatch()

    def dispatch(cls):
        if cls.AUTOMATIC:
            cls.enable()


class Host(Dispatchable):

    def enable(cls):
        add_host(cls)

    def disable(cls):
        remove_host(cls)


class Container(Dispatchable):

    def enable(cls):
        add_container(cls)
        add_commands(cls)

    def disable(cls):
        remove_commands(cls)
        remove_container(cls)
