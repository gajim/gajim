# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import gi
from gi.repository import GLib
from gi.repository import GObject

from gajim.common.enum import AudioPlayerState
from gajim.common.ged import EventHelper

try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst

from gajim.gtk.util.classes import SignalManager

AudioSampleT = list[tuple[float, float]]

SEEK_BAR_PADDING = 11

log = logging.getLogger("gajim.gtk.preview.audio_player")


@dataclass
class AudioPreviewState:
    duration: float = 0.0
    position: float = 0.0
    pipeline_state: AudioPlayerState = AudioPlayerState.NULL
    speed: float = 1.0
    is_timestamp_positive: bool = True
    samples: AudioSampleT = field(default_factory=list[tuple[float, float]])
    is_audio_analyzed = False


class AudioPlayer(GObject.GObject, SignalManager, EventHelper):
    __gtype_name__ = "AudioPlayer"
    __gsignals__ = {
        "audio-playback-changed": (GObject.SignalFlags.RUN_LAST, None, (int, int)),
        "audio-playback-progressed": (GObject.SignalFlags.RUN_LAST, None, (int, int)),
    }

    def __init__(self) -> None:
        super().__init__()
        SignalManager.__init__(self)
        EventHelper.__init__(self)

        self._file_path = None
        self._state = None
        self._preview_id = -1

        self._speed_min = 0.25
        self._speed_max = 2.00

        self._playbin = Gst.ElementFactory.make("playbin", "bin")
        self._query = Gst.Query.new_position(Gst.Format.TIME)
        self._bus_watch_id: int = 0

        self._do_broadcasting = False
        self._switch_track = False
        self._play_new_track = False
        self._seek_track_position = False
        self._setup_pipeline()

        # Holds active audio preview sessions
        # for resuming after switching chats
        self._audio_sessions: dict[int, AudioPreviewState] = {}

    def destroy(self) -> None:
        if self._playbin is not None:
            self._playbin.set_state(Gst.State.NULL)
            bus = self._playbin.get_bus()

            if bus is not None:
                bus.remove_signal_watch()
                bus.disconnect(self._bus_watch_id)

    @property
    def preview_id(self) -> int:
        return self._preview_id

    def get_audio_state(self, preview_id: int) -> AudioPreviewState:
        state = self._audio_sessions.get(preview_id)
        if state is not None:
            return state
        self._audio_sessions[preview_id] = AudioPreviewState()
        return self._audio_sessions[preview_id]

    def toggle_playback(self) -> None:
        assert self._playbin is not None

        if self._is_playing():
            self._playbin.set_state(Gst.State.PAUSED)
        else:
            if self._is_eos():
                # Treat re-playing same as playing a new track
                self._switch_track = True
                self._seek_track_position = True
                self._play_new_track = True
                self._set_playback_position(0.0)
            else:
                self._playbin.set_state(Gst.State.PLAYING)

    def play_audio_file(self, file_path: Path, preview_id: int) -> None:
        assert self._playbin is not None
        assert preview_id != self._preview_id

        self._do_broadcasting = False
        self._playbin.set_state(Gst.State.READY)

        self._preview_id = preview_id

        state = self._audio_sessions.get(preview_id)
        assert state is not None
        self._state = state
        self._file_path = file_path

        self._switch_track = True
        self._seek_track_position = True
        self._play_new_track = True

        self._playbin.set_property("uri", self._file_path.as_uri())

        if self._is_eos():
            self._state.position = 0.0
        self._playbin.set_state(Gst.State.PLAYING)

    def pause(self) -> None:
        assert self._playbin is not None
        self._playbin.set_state(Gst.State.PAUSED)

    def stop(self, preview_id: int) -> None:
        assert self._playbin is not None

        if self._preview_id != preview_id:
            return

        self.stop_any()

    def stop_any(self):
        assert self._playbin is not None

        self._do_broadcasting = False
        self._preview_id = -1
        self._playbin.set_state(Gst.State.NULL)
        if self._state is not None:
            self._state.pipeline_state = AudioPlayerState.NULL
        self.emit(
            "audio-playback-changed",
            -1,
            AudioPlayerState.NULL.value,
        )

    def set_playback_position(self, preview_id: int, position: float) -> None:
        assert self._playbin is not None

        if preview_id != self._preview_id or self._state is None:
            return

        self._set_playback_position(position)

    def set_playback_speed(self, speed: float) -> bool:
        assert self._state is not None

        if self._speed_min <= speed <= self._speed_max:
            self._state.speed = speed

        assert self._playbin is not None
        self._playbin.seek(
            self._state.speed,
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,
            Gst.SeekType.SET,
            int(self._state.position),
            Gst.SeekType.NONE,
            0,
        )
        return True

    def _is_eos(self) -> bool:
        assert self._state is not None
        return abs(self._state.position - self._state.duration) < 0.1e9

    def _query_position(self) -> float:
        assert self._playbin is not None
        assert self._state is not None

        if self._playbin.query(self._query) and (
            self._is_paused() or self._is_playing()
        ):
            _fmt, position = self._query.parse_position()
            return position

        return self._state.position

    def _map_gst_state_to_audio_state(self, gst_state: Gst.State) -> AudioPlayerState:
        if gst_state == Gst.State.NULL:
            return AudioPlayerState.NULL
        elif gst_state == Gst.State.READY:
            return AudioPlayerState.READY
        elif gst_state == Gst.State.PAUSED:
            return AudioPlayerState.PAUSED
        else:
            return AudioPlayerState.PLAYING

    def _setup_pipeline(self) -> None:
        assert self._playbin is not None
        # Set up the whole pipeline
        # For reference see
        # https://gstreamer.freedesktop.org/
        # documentation/audiofx/scaletempo.html
        audio_sink = Gst.Bin.new("audiosink")
        audioconvert = Gst.ElementFactory.make("audioconvert", "audioconvert")
        scaletempo = Gst.ElementFactory.make("scaletempo", "scaletempo")
        audioresample = Gst.ElementFactory.make("audioresample", "audioresample")
        autoaudiosink = Gst.ElementFactory.make("autoaudiosink", "autoaudiosink")

        pipeline_elements = [
            audio_sink,
            audioconvert,
            scaletempo,
            audioresample,
            autoaudiosink,
        ]

        if any(element is None for element in pipeline_elements):
            # If it fails there will be
            # * a delay until playback starts
            # * a chipmunk effect when speeding up the playback
            log.error("Could not set up full audio preview pipeline.")
        else:
            assert autoaudiosink is not None
            assert audioconvert is not None
            assert scaletempo is not None
            assert audioresample is not None

            # On Windows the first fraction of an audio
            # would not play if not synced.
            # On Linux there can be a delay before playback starts with sync,
            # which is however not the case on Windows.
            if sys.platform == "win32":
                autoaudiosink.set_property("sync", True)
            else:
                autoaudiosink.set_property("sync", False)

            audio_sink.add(audioconvert)
            audio_sink.add(scaletempo)
            audio_sink.add(audioresample)
            audio_sink.add(autoaudiosink)

            audioconvert.link(scaletempo)
            scaletempo.link(audioresample)
            audioresample.link(autoaudiosink)

            sink_pad = audioconvert.get_static_pad("sink")
            assert sink_pad is not None
            ghost_pad = Gst.GhostPad.new("sink", sink_pad)
            assert ghost_pad is not None
            audio_sink.add_pad(ghost_pad)
            self._playbin.set_property("audio-sink", audio_sink)

        self._playbin.no_more_pads()

        state_return = self._playbin.set_state(Gst.State.READY)
        if state_return == Gst.StateChangeReturn.FAILURE:
            log.error("Could not setup GST playbin.")
            return

        bus = self._playbin.get_bus()
        if bus is None:
            log.error("Could not get GST Bus.")
            return

        bus.add_signal_watch()
        self._bus_watch_id = bus.connect("message", self._on_bus_message)
        self._pipeline_is_setup = True

    def _is_paused(self) -> bool:
        assert self._playbin is not None
        _, state, _ = self._playbin.get_state(timeout=40)
        return state == Gst.State.PAUSED

    def _is_playing(self) -> bool:
        assert self._playbin is not None
        _, state, _ = self._playbin.get_state(timeout=40)
        return state == Gst.State.PLAYING

    def _clip_position(self, pos: float) -> float:
        assert self._state is not None
        if pos >= self._state.duration:
            return self._state.duration
        if pos < 0:
            return 0.0
        return pos

    def _set_playback_position(self, position: float) -> None:
        assert self._state is not None
        assert self._playbin is not None

        self._state.position = self._clip_position(position)
        self._query.set_position(Gst.Format.TIME, int(self._state.position))
        self._playbin.seek(
            self._state.speed,
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,
            Gst.SeekType.SET,
            int(self._state.position),
            Gst.SeekType.NONE,
            0,
        )

    def _broadcast_playback_progression(self):
        if not self._do_broadcasting:
            return False

        assert self._state is not None
        self._state.position = self._query_position()
        self.emit(
            "audio-playback-progressed",
            self._preview_id,
            self._state.pipeline_state.value,
        )
        return True

    def _on_bus_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        assert self._playbin is not None

        if (
            message.type == Gst.MessageType.ASYNC_DONE
            and self._file_path is not None
            and self._state is not None
        ):
            if self._switch_track:
                self._playbin.set_state(Gst.State.READY)
                self._playbin.set_property("uri", self._file_path.as_uri())
                self._query.set_position(Gst.Format.TIME, int(self._state.position))
                self._switch_track = False
                self._playbin.set_state(Gst.State.PAUSED)
            elif self._seek_track_position:
                self._set_playback_position(self._state.position)
                self._seek_track_position = False
            elif self._play_new_track:
                self._play_new_track = False
                self._playbin.set_state(Gst.State.PLAYING)

        if message.type == Gst.MessageType.STATE_CHANGED:
            old_state, new_state, _pending_state = message.parse_state_changed()
            if message.src == self._playbin and old_state != new_state:
                if self._state is None:
                    return

                self._state.pipeline_state = self._map_gst_state_to_audio_state(
                    new_state
                )
                self.emit(
                    "audio-playback-changed",
                    self._preview_id,
                    self._state.pipeline_state.value,
                )
                log.debug(
                    "State changed: %s → %s",
                    Gst.Element.state_get_name(old_state),
                    Gst.Element.state_get_name(new_state),
                )

                if new_state == Gst.State.PLAYING:
                    self._do_broadcasting = True
                    GLib.timeout_add(20, self._broadcast_playback_progression)
                    self.emit(
                        "audio-playback-changed",
                        self._preview_id,
                        self._state.pipeline_state.value,
                    )
                    return
                self._do_broadcasting = False
            return

        if message.type == Gst.MessageType.EOS and self._state is not None:
            self._state.position = self._state.duration
            self._playbin.set_state(Gst.State.PAUSED)
            self._do_broadcasting = False
            return

        if message.type == Gst.MessageType.ERROR:
            self._handle_error_on_playback(message)

    def _error_info(self, message: Gst.Message) -> tuple[str, int]:
        structure = message.get_structure()
        assert structure is not None
        gerror = structure.get_value("gerror")
        assert gerror is not None
        return gerror.domain, gerror.code

    def _handle_error_on_playback(self, message: Gst.Message):
        assert self._playbin is not None
        domain, code = self._error_info(message)
        if domain == "gst-resource-error-quark":
            if code == 10:
                # On Windows: AUDCLNT_E_DEVICE_INVALIDATED (10)
                # GST_RESOURCE_ERROR_WRITE (10)
                # used when the resource can't be written to.
                self._playbin.set_state(Gst.State.READY)
