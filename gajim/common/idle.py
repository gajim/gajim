## src/common/idle.py
##
## (C) 2008 Thorsten P. 'dGhvcnN0ZW5wIEFUIHltYWlsIGNvbQ==\n'.decode("base64")
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import ctypes
import ctypes.util
import logging
from gi.repository import Gio
from gi.repository import GLib

log = logging.getLogger('gajim.c.idle')

idle_monitor = None


class DBusGnomeIdleMonitor:

    def __init__(self):
        self.last_idle_time = 0

        log.debug('Connecting to D-Bus')
        self.dbus_gnome_proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            'org.gnome.Mutter.IdleMonitor',
            '/org/gnome/Mutter/IdleMonitor/Core',
            'org.gnome.Mutter.IdleMonitor',
            None
        )
        log.debug('D-Bus connected')

        # Only the following call will trigger exceptions if the D-Bus
        # interface/method/... does not exist. Using the failing method
        # for class init to allow other idle monitors to be used on failure.
        self._get_idle_sec_fail()
        log.debug('D-Bus call test successful')

    def _get_idle_sec_fail(self):
        (idle_time,) = self.dbus_gnome_proxy.call_sync(
                    'GetIdletime',
                    None,
                    Gio.DBusCallFlags.NO_AUTO_START,
                    -1,
                    None
                )
        return int(idle_time / 1000)

    def get_idle_sec(self):
        try:
            self.last_idle_time = self._get_idle_sec_fail()
        except GLib.Error as e:
            log.warning(
                'org.gnome.Mutter.IdleMonitor.GetIdletime() failed: %s',
                repr(e))

        return self.last_idle_time


class XScreenSaverInfo(ctypes.Structure):
    _fields_ = [
            ('window', ctypes.c_ulong),
            ('state', ctypes.c_int),
            ('kind', ctypes.c_int),
            ('til_or_since', ctypes.c_ulong),
            ('idle', ctypes.c_ulong),
            ('eventMask', ctypes.c_ulong)
    ]


class XssIdleMonitor:
    def __init__(self):
        XScreenSaverInfo_p = ctypes.POINTER(XScreenSaverInfo)

        display_p = ctypes.c_void_p
        xid = ctypes.c_ulong
        c_int_p = ctypes.POINTER(ctypes.c_int)

        libX11path = ctypes.util.find_library('X11')
        if libX11path == None:
            raise OSError('libX11 could not be found.')
        libX11 = ctypes.cdll.LoadLibrary(libX11path)
        libX11.XOpenDisplay.restype = display_p
        libX11.XOpenDisplay.argtypes = ctypes.c_char_p,
        libX11.XDefaultRootWindow.restype = xid
        libX11.XDefaultRootWindow.argtypes = display_p,

        libXsspath = ctypes.util.find_library('Xss')
        if libXsspath == None:
            raise OSError('libXss could not be found.')
        self.libXss = ctypes.cdll.LoadLibrary(libXsspath)
        self.libXss.XScreenSaverQueryExtension.argtypes = display_p, c_int_p, c_int_p
        self.libXss.XScreenSaverAllocInfo.restype = XScreenSaverInfo_p
        self.libXss.XScreenSaverQueryInfo.argtypes = (display_p, xid, XScreenSaverInfo_p)

        self.dpy_p = libX11.XOpenDisplay(None)
        if self.dpy_p == None:
            raise OSError('Could not open X Display.')

        _event_basep = ctypes.c_int()
        _error_basep = ctypes.c_int()
        if self.libXss.XScreenSaverQueryExtension(self.dpy_p, ctypes.byref(_event_basep),
                        ctypes.byref(_error_basep)) == 0:
            raise OSError('XScreenSaver Extension not available on display.')

        self.xss_info_p = self.libXss.XScreenSaverAllocInfo()
        if self.xss_info_p == None:
            raise OSError('XScreenSaverAllocInfo: Out of Memory.')

        self.rootwindow = libX11.XDefaultRootWindow(self.dpy_p)

    def get_idle_sec(self):
        if self.libXss.XScreenSaverQueryInfo(
                self.dpy_p,
                self.rootwindow,
                self.xss_info_p) == 0:
            return 0
        else:
            return int(self.xss_info_p.contents.idle / 1000)


def getIdleSec():
    """
    Return the idle time in seconds
    """
    if idle_monitor is None:
        return 0
    else:
        return idle_monitor.get_idle_sec()

try:
    idle_monitor = DBusGnomeIdleMonitor()
except GLib.Error as e:
    log.info("Idle time via D-Bus not available: %s", repr(e))

    try:
        idle_monitor = XssIdleMonitor()
    except OSError as e:
        log.info("Idle time via XScreenSaverInfo not available: %s", repr(e))
        raise Exception('No supported idle monitor found')

if __name__ == '__main__':
    import time
    time.sleep(2.1)
    print(getIdleSec())
