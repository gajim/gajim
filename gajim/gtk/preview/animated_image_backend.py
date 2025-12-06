# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import sys
from pathlib import Path

from gi.repository import GObject
from gi.repository.Gdk import Paintable

from gajim.common import app

try:
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst

import logging

from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.preview_animated_image_backend")


class AnimatedImageBackend(GObject.Object, SignalManager):
    __gtype_name__ = "AnimatedImageBackend"
    __gsignals__ = {
        "pipeline-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        "playback-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self, orig_path: Path, max_loops: int = 3) -> None:
        super().__init__()
        SignalManager.__init__(self)

        self._orig_path = orig_path

        self._pipeline_is_setup = False
        self._pipeline_setup_failed = False

        self._paintable: Paintable | None = None
        self._pipeline: Gst.Pipeline | None = None
        self._src: Gst.Element | None = None
        self._bus: Gst.Bus | None = None

        # Workaround a regression of Gst or Gtk on Windows,
        # wglShareLists() called by GstGL would fail due to ERROR_BUSY (0xAA)
        self._use_gl = sys.platform != "win32"

        self._loop_counter = 0
        self._max_loop_counts = max_loops

    @property
    def pipeline_is_setup(self) -> bool:
        return self._pipeline_is_setup

    @property
    def pipeline_setup_failed(self) -> bool:
        return self._pipeline_setup_failed

    @property
    def paintable(self) -> Paintable | None:
        return self._paintable

    def cleanup(self) -> None:
        self._cleanup()
        self._disconnect_all()
        app.check_finalize(self)

    def is_playing(self) -> bool:
        if self._pipeline is None:
            return False
        _, state, _ = self._pipeline.get_state(timeout=100)
        return state == Gst.State.PLAYING

    def play(self) -> None:
        assert self._pipeline is not None
        self._pipeline.set_state(Gst.State.PLAYING)

    def pause(self) -> None:
        assert self._pipeline is not None
        self._loop_counter = 0
        self._pipeline.set_state(Gst.State.PAUSED)
        self._pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        self.emit("playback-changed", False)

    def setup_pipeline(self) -> None:
        try:
            self._setup_pipeline()
        except Exception:
            log.exception("Unable to play animated image")
            self._pipeline_setup_failed = True
            self.emit("pipeline-changed", False)
        else:
            self._pipeline_is_setup = True
            self.emit("pipeline-changed", True)

    def _setup_pipeline(self) -> None:
        if self._pipeline_is_setup:
            return

        pipeline_parts = {
            "src": "filesrc name=src",
            "decode": "decodebin name=decodebin",
            "gl": "glupload name=glupload ! glcolorconvert" if self._use_gl else "",
            "queue": "queue name=queue",
            "sink": "gtk4paintablesink name=sink",
        }
        pipeline = " ! ".join(filter(None, pipeline_parts.values()))
        try:
            self._pipeline = typing.cast(Gst.Pipeline, Gst.parse_launch(pipeline))
        except Exception as e:
            self._pipeline_setup_failed = True
            self.emit("pipeline-changed", False)
            log.warning("Failed to setup pipeline: %s", e)
            return

        decodebin = typing.cast(Gst.Element, self._pipeline.get_by_name("decodebin"))
        self._connect(decodebin, "pad-added", self._on_pad_added)

        self._src = self._pipeline.get_by_name("src")
        assert self._src is not None
        self._src.set_property("location", str(self._orig_path))

        self._bus = self._pipeline.get_bus()
        self._bus.add_signal_watch()
        self._connect(self._bus, "message::eos", self._on_eos)
        self._connect(self._bus, "message::state-changed", self._on_state_changed)

        sink = self._pipeline.get_by_name("sink")
        assert sink is not None
        self._paintable = sink.get_property("paintable")

    def _on_pad_added(self, _bin: Gst.Bin, pad: Gst.Pad) -> None:
        assert pad is not None
        caps = pad.get_current_caps()
        if caps is None:
            return

        log.debug("Link decodebin with glupload")
        assert self._pipeline is not None
        if self._use_gl:
            elem = self._pipeline.get_by_name("glupload")
        else:
            elem = self._pipeline.get_by_name("queue")
        assert elem is not None
        sink_pad = elem.get_static_pad("sink")
        assert sink_pad is not None
        if not sink_pad.is_linked():
            pad.link(sink_pad)

    def _on_eos(self, _bus: Gst.Bus, _msg: Gst.Message) -> None:
        assert self._pipeline is not None
        self._pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        self._loop_counter = (self._loop_counter + 1) % self._max_loop_counts
        if self._loop_counter == 0:
            self.pause()

    def _on_state_changed(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        assert self._pipeline is not None
        assert message is not None
        if message.src == self._pipeline:
            _, new, _ = message.parse_state_changed()
            if new == Gst.State.PLAYING:
                self.emit("playback-changed", True)

    def _cleanup(self) -> None:
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)

        if self._pipeline is not None:
            self._pipeline.run_dispose()
            self._pipeline = None

        if self._bus is not None:
            self._bus.remove_signal_watch()
            self._bus = None

        self._pipeline_setup = False
        self._paintable = None
