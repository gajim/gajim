# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging

import gi
import objc
from AppKit import NSAppleEventManager
from AppKit import NSScreen
from Foundation import NSIntersectsRect
from Foundation import NSMakeRect
from Foundation import NSObject
from Foundation import NSUserDefaults
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app

gi.require_version("GdkMacos", "4.0")
from gi.repository import GdkMacos

log = logging.getLogger("gajim.gtk.util.macos")

# Four-character codes of the Apple Event Manager (CoreServices)
K_INTERNET_EVENT_CLASS = int.from_bytes(b"GURL", "big")
K_AE_GET_URL = int.from_bytes(b"GURL", "big")
KEY_DIRECT_OBJECT = int.from_bytes(b"----", "big")


class URLEventHandler(NSObject):
    def handleGetURLEvent_withReplyEvent_(  # noqa: N802
        self, event: Any, _reply_event: Any
    ) -> None:
        uri = event.paramDescriptorForKeyword_(KEY_DIRECT_OBJECT).stringValue()
        if uri:
            app.app.activate_action("handle-uri", GLib.Variant("as", [uri]))


def register_url_handler() -> URLEventHandler:
    """Forward URLs opened through the system (e.g. xmpp: links) to Gajim.

    macOS delivers them as GetURL Apple Event, which GTK does not handle.
    The returned handler must be kept alive by the caller.
    """
    handler = URLEventHandler.alloc().init()
    manager = NSAppleEventManager.sharedAppleEventManager()
    manager.setEventHandler_andSelector_forEventClass_andEventID_(
        handler,
        "handleGetURLEvent:withReplyEvent:",
        K_INTERNET_EVENT_CLASS,
        K_AE_GET_URL,
    )
    return handler


def remember_window_frame(window: Gtk.Window, name: str) -> None:
    """Let macOS save and restore the position and size of a window.

    GTK 4 has no API for window positions, but AppKit can store the frame
    of the native window under a name (frame autosave). The frame is
    restored when the window is mapped: after GTK has placed the window
    and before its first frame is drawn, so the window doesn't jump.
    """
    window.connect("map", _on_map_restore_frame, name)


def _on_map_restore_frame(window: Gtk.Window, name: str) -> None:
    surface = window.get_surface()
    if not isinstance(surface, GdkMacos.MacosSurface):
        return

    # The stubs declare the return type as None, it is the NSWindow pointer
    pointer = cast(int, surface.get_native_window())
    if not pointer:
        return

    nswindow: Any = objc.objc_object(c_void_p=pointer)
    frame = _get_saved_frame(name)
    if frame is None:
        nswindow.setFrameUsingName_(name)
    else:
        nswindow.setFrame_display_(frame, True)
        _restore_after_first_frame(window, nswindow, frame)
    nswindow.setFrameAutosaveName_(name)


def _get_saved_frame(name: str) -> Any | None:
    # With several screens, setFrameUsingName: can move the saved frame to
    # another screen. The first four values of the saved frame are global
    # coordinates, so they are applied directly if they are on a connected
    # screen.
    defaults = NSUserDefaults.standardUserDefaults()
    saved = defaults.stringForKey_(f"NSWindow Frame {name}")
    if not saved:
        return None

    try:
        x, y, width, height = (float(value) for value in saved.split()[:4])
    except ValueError:
        return None

    frame = NSMakeRect(x, y, width, height)
    if not any(
        NSIntersectsRect(frame, screen.visibleFrame()) for screen in NSScreen.screens()
    ):
        return None
    return frame


def _restore_after_first_frame(window: Gtk.Window, nswindow: Any, frame: Any) -> None:
    # Until its first frame is drawn, the window is not on screen yet, and
    # macOS keeps it on the screen it was created on. Apply the frame again
    # if it was moved to another screen in the meantime.
    frame_clock = window.get_frame_clock()
    if frame_clock is None:
        return

    def _on_after_paint(clock: Gdk.FrameClock) -> None:
        clock.disconnect(handler_id)
        current = nswindow.frame()
        if (current.origin.x, current.origin.y) != (frame.origin.x, frame.origin.y):
            nswindow.setFrame_display_(frame, True)

    handler_id = frame_clock.connect("after-paint", _on_after_paint)
