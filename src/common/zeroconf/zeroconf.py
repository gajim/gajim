##      common/zeroconf/zeroconf.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

C_NAME, C_DOMAIN, C_INTERFACE, C_PROTOCOL, C_HOST, \
C_ADDRESS, C_PORT, C_BARE_NAME, C_TXT = range(9)

def test_avahi():
    try:
        import avahi
    except ImportError:
        return False
    return True

def test_bonjour():
    try:
        import pybonjour
    except ImportError:
        return False
    except WindowsError:
        return False
    return True

def test_zeroconf():
    return test_avahi() or test_bonjour()

if test_avahi():
    from common.zeroconf import zeroconf_avahi
    Zeroconf = zeroconf_avahi.Zeroconf
elif test_bonjour():
    from common.zeroconf import zeroconf_bonjour
    Zeroconf = zeroconf_bonjour.Zeroconf
