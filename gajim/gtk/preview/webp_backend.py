# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing
from typing import TYPE_CHECKING

import sys
from concurrent.futures import Future
from functools import partial
from pathlib import Path

from gi.repository import GLib
from gi.repository import GObject
from gi.repository.Gdk import Paintable

from gajim.common import app
from gajim.common.multiprocess.webp_frames import extract_webp_frames

try:
    from gi.repository import Gst
except Exception:
    if TYPE_CHECKING:
        from gi.repository import Gst

import logging

from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.preview_webp_backend")


class WebPBackend(GObject.Object, SignalManager):
    __gtype_name__ = "WebPBackend"
    __gsignals__ = {
        "pipeline-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        "playback-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self, orig_path: Path, max_loops: int = 3) -> None:
        super().__init__()
        SignalManager.__init__(self)

        self._orig_path = orig_path

        self._creating_pipeline = False
        self._pipeline_is_setup = False
        self._pipeline_setup_failed = False

        self._do_stop = True
        self._push_id = None

        self._paintable: Paintable | None = None
        self._pipeline: Gst.Element | None = None
        self._src: Gst.Element | None = None
        self._bus: Gst.Bus | None = None

        # Workaround a regression of Gst or Gtk on Windows,
        # wglShareLists() called by GstGL would fail due to ERROR_BUSY (0xAA)
        self._use_gl = sys.platform != "win32"

        self._buf: Gst.Buffer | None = None
        self._frames: list[tuple[bytes, int]] = []
        self._current_frame = 1

        self._loop_counter = 0
        self._max_loops = max_loops

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
        self._do_stop = False
        self._pipeline.set_state(Gst.State.PLAYING)
        self._push_frame()

    def pause(self) -> None:
        if self._pipeline is None:
            self._pipeline_is_setup = False
            return

        _, state, _ = self._pipeline.get_state(timeout=100)
        if state == Gst.State.PLAYING:
            if self._push_id is not None:
                GLib.source_remove(self._push_id)
                self._push_id = None

        self._loop_counter = 0
        self._current_frame = 1
        self._do_stop = True
        self._pipeline.set_state(Gst.State.PAUSED)
        self._pipeline.send_event(Gst.Event.new_flush_start())
        self._pipeline.send_event(Gst.Event.new_flush_stop(True))
        self.emit("playback-changed", False)

    def setup_pipeline(self) -> None:
        try:
            self._setup_pipeline()
        except Exception:
            log.exception("Unable to play animated image")
            self._pipeline_setup_failed = True
            self.emit("pipeline-changed", False)

    def _setup_pipeline(self) -> None:
        if (
            self._creating_pipeline
            or self._pipeline_is_setup
            or self._pipeline_setup_failed
        ):
            return

        self._creating_pipeline = True
        self._current_frame = 1
        self._loop_counter = 0
        self._do_stop = True

        pipeline_parts = {
            "src": "appsrc name=src is-live=true format=time block=false leaky-type=2 do-timestamp=true",
            "dec": "webpdec name=webpdec bypass-filtering=false no-fancy-upsampling=true use-threads=true",
            "convert": "videoconvert name=videoconvert",
            "gl": "glupload name=glupload ! glcolorconvert" if self._use_gl else "",
            "queue": "queue name=queue",
            "sink": "gtk4paintablesink name=sink",
        }
        pipeline = " ! ".join(filter(None, pipeline_parts.values()))
        try:
            self._pipeline = typing.cast(Gst.Pipeline, Gst.parse_launch(pipeline))
        except Exception as e:
            self._pipeline_setup_failed = False
            self.emit("pipeline-changed", False)
            log.warning("Failed to setup pipeline: %s", e)
            return

        self._bus = self._pipeline.get_bus()
        assert self._bus is not None
        self._bus.add_signal_watch()
        self._connect(self._bus, "message::eos", self._on_eos)
        self._connect(self._bus, "message::state-changed", self._on_state_changed)

        sink: Gst.Element | None = self._pipeline.get_by_name("sink")
        assert sink is not None
        self._paintable = sink.get_property("paintable")
        self._src = self._pipeline.get_by_name("src")

        self._get_frames()

    def _on_state_changed(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        assert self._pipeline is not None
        assert message is not None
        if message.src == self._pipeline:
            _, new, _ = message.parse_state_changed()
            if new == Gst.State.PLAYING:
                self.emit("playback-changed", True)

    def _get_frames(self) -> None:
        assert self._orig_path is not None
        try:
            future = app.process_pool.submit(extract_webp_frames, self._orig_path)
            future.add_done_callback(
                partial(GLib.idle_add, self._extracting_frames_finished)
            )
        except Exception as error:
            log.exception("Extracting frames failed for: %s %s", self._orig_path, error)
            self._pipeline_setup_failed = True
            self.emit("pipeline-changed", False)

    def _extracting_frames_finished(
        self, future: Future[list[tuple[bytes, int]]]
    ) -> bool:
        try:
            self._frames = future.result()
        except Exception as error:
            log.exception("Extracting frames failed for: %s %s", self._orig_path, error)
            self._pipeline_setup_failed = True
            self.emit("pipeline-changed", False)
            return GLib.SOURCE_REMOVE

        self._pipeline_is_setup = True
        self.emit("pipeline-changed", True)
        return GLib.SOURCE_REMOVE

    def _push_frame(self):
        if self._do_stop:
            self._push_id = None
            return False

        frame, duration = self._frames[self._current_frame]
        buf = Gst.Buffer.new_wrapped(frame)
        assert buf is not None
        buf.duration = duration * Gst.MSECOND
        assert self._src is not None
        self._src.emit("push-buffer", buf)
        self._current_frame = (self._current_frame + 1) % len(self._frames)
        del buf
        self._push_id = GLib.timeout_add(duration, self._push_frame)
        if self._current_frame == 0:
            self._loop_counter = (self._loop_counter + 1) % self._max_loops
            if self._loop_counter == 0:
                self.pause()
        return False

    def _on_eos(self, _bus: Gst.Bus, _msg: Gst.Message) -> None:
        assert self._pipeline is not None
        self._pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)

    def _cleanup(self) -> None:
        if self._push_id is not None:
            GLib.source_remove(self._push_id)

        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline.run_dispose()
            self._pipeline = None
        if self._src is not None:
            self._src.run_dispose()
        if self._bus is not None:
            self._bus.remove_signal_watch()
            self._bus = None

        self._paintable = None
        self._frames = []
