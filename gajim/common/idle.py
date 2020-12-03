# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2008 Mateusz Biliński <mateusz AT bilinski.it>
# Copyright (C) 2008 Thorsten P. 'dGhvcnN0ZW5wIEFUIHltYWlsIGNvbQ==\n'.decode("base64")
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import sys
import time
import ctypes
import ctypes.util
import logging
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject

from gajim.common import app
from gajim.common.const import Display
from gajim.common.const import IdleState

log = logging.getLogger('gajim.c.idle')


class DBusFreedesktopIdleMonitor:

    def __init__(self):
        self.last_idle_time = 0
        self._extended_away = False

        log.debug('Connecting to D-Bus')
        self.dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            'org.freedesktop.ScreenSaver',
            '/org/freedesktop/ScreenSaver',
            'org.freedesktop.ScreenSaver',
            None
        )
        log.debug('D-Bus connected')

        # Only the following call will trigger exceptions if the D-Bus
        # interface/method/... does not exist. Using the failing method
        # for class init to allow other idle monitors to be used on failure.
        self._get_idle_sec_fail()
        log.debug('D-Bus call test successful')

    def _get_idle_sec_fail(self):
        (idle_time,) = self.dbus_proxy.call_sync(
            'GetSessionIdleTime',
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            -1,
            None
        )
        return idle_time//1000

    def get_idle_sec(self):
        try:
            self.last_idle_time = self._get_idle_sec_fail()
        except GLib.Error as error:
            log.warning(
                'org.freedesktop.ScreenSaver.GetSessionIdleTime() failed: %s',
                error)

        return self.last_idle_time

    def set_extended_away(self, state):
        self._extended_away = state

    def is_extended_away(self):
        return self._extended_away


class DBusGnomeIdleMonitor:

    def __init__(self):
        self.last_idle_time = 0
        self._extended_away = False

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
        except GLib.Error as error:
            log.warning(
                'org.gnome.Mutter.IdleMonitor.GetIdletime() failed: %s',
                error)

        return self.last_idle_time

    def set_extended_away(self, state):
        self._extended_away = state

    def is_extended_away(self):
        return self._extended_away


class XssIdleMonitor:
    def __init__(self):

        self._extended_away = False

        class XScreenSaverInfo(ctypes.Structure):
            _fields_ = [
                ('window', ctypes.c_ulong),
                ('state', ctypes.c_int),
                ('kind', ctypes.c_int),
                ('til_or_since', ctypes.c_ulong),
                ('idle', ctypes.c_ulong),
                ('eventMask', ctypes.c_ulong)
            ]

        XScreenSaverInfo_p = ctypes.POINTER(XScreenSaverInfo)

        display_p = ctypes.c_void_p
        xid = ctypes.c_ulong
        c_int_p = ctypes.POINTER(ctypes.c_int)

        libX11path = ctypes.util.find_library('X11')
        if libX11path is None:
            raise OSError('libX11 could not be found.')
        libX11 = ctypes.cdll.LoadLibrary(libX11path)
        libX11.XOpenDisplay.restype = display_p
        libX11.XOpenDisplay.argtypes = (ctypes.c_char_p,)
        libX11.XDefaultRootWindow.restype = xid
        libX11.XDefaultRootWindow.argtypes = (display_p,)

        libXsspath = ctypes.util.find_library('Xss')
        if libXsspath is None:
            raise OSError('libXss could not be found.')
        self.libXss = ctypes.cdll.LoadLibrary(libXsspath)
        self.libXss.XScreenSaverQueryExtension.argtypes = display_p, c_int_p, c_int_p
        self.libXss.XScreenSaverAllocInfo.restype = XScreenSaverInfo_p
        self.libXss.XScreenSaverQueryInfo.argtypes = (
            display_p, xid, XScreenSaverInfo_p)

        self.dpy_p = libX11.XOpenDisplay(None)
        if self.dpy_p is None:
            raise OSError('Could not open X Display.')

        _event_basep = ctypes.c_int()
        _error_basep = ctypes.c_int()
        extension = self.libXss.XScreenSaverQueryExtension(
            self.dpy_p, ctypes.byref(_event_basep), ctypes.byref(_error_basep))
        if extension == 0:
            raise OSError('XScreenSaver Extension not available on display.')

        self.xss_info_p = self.libXss.XScreenSaverAllocInfo()
        if self.xss_info_p is None:
            raise OSError('XScreenSaverAllocInfo: Out of Memory.')

        self.rootwindow = libX11.XDefaultRootWindow(self.dpy_p)

    def get_idle_sec(self):
        info = self.libXss.XScreenSaverQueryInfo(
            self.dpy_p, self.rootwindow, self.xss_info_p)
        if info == 0:
            return info
        return int(self.xss_info_p.contents.idle / 1000)

    def set_extended_away(self, state):
        self._extended_away = state

    def is_extended_away(self):
        return False


class WindowsIdleMonitor:
    def __init__(self):
        self.OpenInputDesktop = ctypes.windll.user32.OpenInputDesktop
        self.CloseDesktop = ctypes.windll.user32.CloseDesktop
        self.SystemParametersInfo = ctypes.windll.user32.SystemParametersInfoW
        self.GetTickCount = ctypes.windll.kernel32.GetTickCount
        self.GetLastInputInfo = ctypes.windll.user32.GetLastInputInfo

        self._locked_time = None

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]

        self.lastInputInfo = LASTINPUTINFO()
        self.lastInputInfo.cbSize = ctypes.sizeof(self.lastInputInfo)

    def get_idle_sec(self):
        self.GetLastInputInfo(ctypes.byref(self.lastInputInfo))
        return float(self.GetTickCount() - self.lastInputInfo.dwTime) / 1000

    def is_extended_away(self):
        # Check if Screen Saver is running
        # 0x72 is SPI_GETSCREENSAVERRUNNING
        saver_runing = ctypes.c_int(0)
        info = self.SystemParametersInfo(
            0x72, 0, ctypes.byref(saver_runing), 0)
        if info and saver_runing.value:
            return True

        # Check if Screen is locked
        # Also a UAC prompt counts as locked
        # So just return True if we are more than 10 seconds locked
        desk = self.OpenInputDesktop(0, False, 0)
        unlocked = bool(desk)
        self.CloseDesktop(desk)

        if unlocked:
            self._locked_time = None
            return False

        if self._locked_time is None:
            self._locked_time = time.time()
            return False

        threshold = time.time() - 10
        if threshold > self._locked_time:
            return True


class IdleMonitor(GObject.GObject):

    __gsignals__ = {
        'state-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None, # return value
            () # arguments
        )}

    def __init__(self):
        GObject.GObject.__init__(self)
        self.set_interval()
        self._state = IdleState.AWAKE
        self._idle_monitor = self._get_idle_monitor()

        if self.is_available():
            GLib.timeout_add_seconds(1, self._poll)

    def set_interval(self, away_interval=60, xa_interval=120):
        log.info('Set interval: away: %s, xa: %s',
                 away_interval, xa_interval)
        self._away_interval = away_interval
        self._xa_interval = xa_interval

    def set_extended_away(self, state):
        self._idle_monitor.set_extended_away(state)

    def is_available(self):
        return self._idle_monitor is not None

    @property
    def state(self):
        if not self.is_available():
            return IdleState.UNKNOWN
        return self._state

    def is_xa(self):
        return self.state == IdleState.XA

    def is_away(self):
        return self.state == IdleState.AWAY

    def is_awake(self):
        return self.state == IdleState.AWAKE

    def is_unknown(self):
        return self.state == IdleState.UNKNOWN

    @staticmethod
    def _get_idle_monitor():
        if sys.platform == 'win32':
            return WindowsIdleMonitor()

        try:
            return DBusFreedesktopIdleMonitor()
        except GLib.Error as error:
            log.info('Idle time via D-Bus not available: %s', error)

        try:
            return DBusGnomeIdleMonitor()
        except GLib.Error as error:
            log.info('Idle time via D-Bus (GNOME) not available: %s', error)

        if app.is_display(Display.WAYLAND):
            return

        try:
            return XssIdleMonitor()
        except OSError as error:
            log.info('Idle time via XScreenSaverInfo not available: %s', error)

    def get_idle_sec(self):
        return self._idle_monitor.get_idle_sec()

    def _poll(self):
        """
        Check to see if we should change state
        """
        if self._idle_monitor.is_extended_away():
            log.info('Extended Away: Screensaver or Locked Screen')
            self._set_state(IdleState.XA)
            return True

        idle_time = self.get_idle_sec()

        # xa is stronger than away so check for xa first
        if idle_time > self._xa_interval:
            self._set_state(IdleState.XA)
        elif idle_time > self._away_interval:
            self._set_state(IdleState.AWAY)
        else:
            self._set_state(IdleState.AWAKE)
        return True

    def _set_state(self, state):
        if self._state == state:
            return

        self._state = state
        log.info('State changed: %s', state)
        self.emit('state-changed')


Monitor = IdleMonitor()
