# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

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

log = logging.getLogger("gajim.gtk.preview_gif_backend")


class GifBackend(GObject.Object, SignalManager):
    __gtype_name__ = "GifBackend"
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

        self._paintable = None
        self._pipeline_elements = []
        self._pipeline = None
        self._src = None
        self._decodebin = None
        self._bus = None

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
        if self._pipeline_is_setup:
            return

        self._pipeline_is_setup = True
        self._pipeline = Gst.Pipeline.new()
        self._src = Gst.ElementFactory.make("filesrc")
        self._decodebin = Gst.ElementFactory.make("decodebin")
        self._glupload = Gst.ElementFactory.make("glupload")
        self._glcolorconvert = Gst.ElementFactory.make("glcolorconvert")
        self._queue = Gst.ElementFactory.make("queue")
        self._sink = Gst.ElementFactory.make("gtk4paintablesink")

        assert self._src is not None
        assert self._decodebin is not None
        assert self._glupload is not None
        assert self._glcolorconvert is not None
        assert self._queue is not None
        assert self._sink is not None

        self._pipeline_elements = [
            self._src,
            self._decodebin,
            self._glupload,
            self._glcolorconvert,
            self._queue,
            self._sink,
        ]

        for elem in self._pipeline_elements:
            self._pipeline.add(elem)

        self._src.link(self._decodebin)
        self._connect(self._decodebin, "pad-added", self._on_pad_added)
        self._glupload.link(self._glcolorconvert)
        self._glcolorconvert.link(self._queue)
        self._queue.link(self._sink)

        self._src.set_property("location", str(self._orig_path))
        self._bus = self._pipeline.get_bus()
        self._bus.add_signal_watch()
        assert self._bus is not None
        self._connect(self._bus, "message::eos", self._on_eos)
        self._connect(self._bus, "message::state-changed", self._on_state_changed)

        assert self._sink is not None
        self._paintable = self._sink.get_property("paintable")
        self.emit("pipeline-changed", True)

    def _on_pad_added(self, _bin: Gst.Bin, pad: Gst.Pad) -> None:
        assert pad is not None
        caps = pad.get_current_caps()
        if caps is None:
            return

        log.debug("Link decodebin with glupload")
        assert self._glupload is not None
        sink_pad = self._glupload.get_static_pad("sink")
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

        if self._decodebin is not None:
            self._disconnect_object(self._decodebin)

        if self._pipeline is not None:
            for elem in self._pipeline_elements:
                self._pipeline.remove(elem)
                elem.run_dispose()
            self._pipeline.run_dispose()
            self._pipeline = None

        self._pipeline_elements = []

        if self._bus is not None:
            self._bus.remove_signal_watch()
            self._bus = None

        self._pipeline_setup = False
        self._paintable = None
