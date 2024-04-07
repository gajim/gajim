# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

from gi.repository import Gtk

try:
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst


def create_gtk_widget() -> tuple[Gst.Element, Gtk.Widget, str] | None:
    gtkglsink = Gst.ElementFactory.make('gtkglsink', None)
    if gtkglsink is not None:
        glsinkbin = Gst.ElementFactory.make('glsinkbin', None)
        if glsinkbin is None:
            return None
        glsinkbin.set_property('sink', gtkglsink)
        sink = glsinkbin
        widget = gtkglsink.get_property('widget')
        name = 'gtkglsink'
    else:
        sink = Gst.ElementFactory.make('gtksink', None)
        if sink is None:
            return None
        widget = sink.get_property('widget')
        name = 'gtksink'
    widget.set_visible(True)
    widget.set_property('expand', True)
    return sink, widget, name
