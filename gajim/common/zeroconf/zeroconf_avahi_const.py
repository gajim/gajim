# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.


from enum import IntEnum


DBUS_NAME = "org.freedesktop.Avahi"
DBUS_INTERFACE_SERVER = DBUS_NAME + ".Server"
DBUS_INTERFACE_ENTRY_GROUP = DBUS_NAME + ".EntryGroup"
DBUS_INTERFACE_DOMAIN_BROWSER = DBUS_NAME + ".DomainBrowser"


class ServerState(IntEnum):
    INVALID = 0
    REGISTERING = 1
    RUNNING = 2
    COLLISION = 3
    FAILURE = 4


class EntryGroup(IntEnum):
    UNCOMMITTED = 0
    REGISTERING = 1
    ESTABLISHED = 2
    COLLISION = 3
    FAILURE = 4


class DomainBrowser(IntEnum):
    BROWSE = 0
    BROWSE_DEFAULT = 1
    REGISTER = 2
    REGISTER_DEFAULT = 3
    BROWSE_LEGACY = 4


class Protocol(IntEnum):
    UNSPEC = -1
    INET = 0
    INET6 = 1


class Interface(IntEnum):
    UNSPEC = -1
