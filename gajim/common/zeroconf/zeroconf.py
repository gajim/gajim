# Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
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

from typing import Any  # pylint: disable=unused-import

from enum import IntEnum, unique


@unique
class Constant(IntEnum):
    NAME = 0
    DOMAIN = 1
    RESOLVED_INFO = 2
    BARE_NAME = 3
    TXT = 4

@unique
class ConstantRI(IntEnum):
    INTERFACE = 0
    PROTOCOL = 1
    HOST = 2
    APROTOCOL = 3
    ADDRESS = 4
    PORT = 5

def test_avahi():
    try:
        import gi
        gi.require_version('Avahi', '0.6')
        from gi.repository import Avahi  # pylint: disable=unused-import
    except (ImportError, ValueError):
        return False
    return True

def test_bonjour():
    try:
        import pybonjour  # pylint: disable=unused-import
    except Exception:
        return False
    return True

def test_zeroconf():
    return test_avahi() or test_bonjour()

if test_avahi():
    from gajim.common.zeroconf import zeroconf_avahi
    Zeroconf = zeroconf_avahi.Zeroconf  # type: Any
elif test_bonjour():
    from gajim.common.zeroconf import zeroconf_bonjour
    Zeroconf = zeroconf_bonjour.Zeroconf
