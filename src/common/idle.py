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

try:
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
	libXss = ctypes.cdll.LoadLibrary(libXsspath)
	libXss.XScreenSaverQueryExtension.argtypes = display_p, c_int_p, c_int_p
	libXss.XScreenSaverAllocInfo.restype = XScreenSaverInfo_p
	libXss.XScreenSaverQueryInfo.argtypes = (display_p, xid, XScreenSaverInfo_p)

	dpy_p = libX11.XOpenDisplay(None)
	if dpy_p == None:
		raise OSError('Could not open X Display.')

	_event_basep = ctypes.c_int()
	_error_basep = ctypes.c_int()
	if libXss.XScreenSaverQueryExtension(dpy_p, ctypes.byref(_event_basep),
			ctypes.byref(_error_basep)) == 0:
		raise OSError('XScreenSaver Extension not available on display.')

	xss_info_p = libXss.XScreenSaverAllocInfo()
	if xss_info_p == None:
		raise OSError('XScreenSaverAllocInfo: Out of Memory.')

	rootwindow = libX11.XDefaultRootWindow(dpy_p)
	xss_available = True
except OSError, e:
	# Logging?
	xss_available = False

def getIdleSec():
	"""Returns the idle time in seconds"""
	if not xss_available:
		return 0
	if libXss.XScreenSaverQueryInfo(dpy_p, rootwindow, xss_info_p) == 0:
		return 0
	else:
		return int(xss_info_p.contents.idle) / 1000

def close():
	global xss_available
	if xss_available:
		libX11.XFree(xss_info_p)
		libX11.XCloseDisplay(dpy_p)
		xss_available = False

if __name__ == '__main__':
	import time
	time.sleep(2.1)
	print getIdleSec()
	close()
	print getIdleSec()
