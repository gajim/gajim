# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from AppKit import NSAppleEventManager
from Foundation import NSObject
from gi.repository import GLib

from gajim.common import app

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
