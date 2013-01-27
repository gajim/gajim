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

from .tools import remove

COMMANDS = {}
CONTAINERS = {}

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
    from .framework import Command
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

    def __init__(self, name, bases, namespace):
        parents = super(Dispatchable, self)
        parents.__init__(name, bases, namespace)
        if not is_root(namespace):
            self.dispatch()

    def dispatch(self):
        if self.AUTOMATIC:
            self.enable()

class Host(Dispatchable):

    def enable(self):
        add_host(self)

    def disable(self):
        remove_host(self)

class Container(Dispatchable):

    def enable(self):
        add_container(self)
        add_commands(self)

    def disable(self):
        remove_commands(self)
        remove_container(self)