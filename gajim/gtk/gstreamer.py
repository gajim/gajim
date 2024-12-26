# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging

from gi.repository import Gdk

from gajim.common import app

try:
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst

log = logging.getLogger("gajim.gtk.gstreamer")


def create_video_elements() -> tuple[Gst.Element, Gdk.Paintable, str] | None:
    if not app.is_installed("GST"):
        return None

    gtksink = Gst.ElementFactory.make("gtk4paintablesink", None)
    if gtksink is None:
        return None

    paintable = gtksink.get_property("paintable")
    if paintable.props.gl_context is not None:
        sink = Gst.ElementFactory.make("glsinkbin", None)
        if sink is None:
            return None

        log.info("Using GL")
        sink.set_property("sink", gtksink)
        name = "gtkglsink"

    else:
        sink = Gst.Bin.new()
        convert = Gst.ElementFactory.make("videoconvert", None)
        if convert is None:
            return None

        sink.add(convert)
        sink.add(gtksink)
        convert.link(gtksink)

        pad = convert.get_static_pad("sink")
        if pad is None:
            return None

        log.info("Not using GL")
        sink.add_pad(Gst.GhostPad.new("sink", pad))

        name = "gtksink"

    return sink, paintable, name
