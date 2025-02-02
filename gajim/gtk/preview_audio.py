# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging
import sys
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

try:
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.preview import AudioSampleT
from gajim.common.util.text import format_duration

from gajim.gtk.builder import get_builder
from gajim.gtk.preview_audio_analyzer import AudioAnalyzer
from gajim.gtk.preview_audio_visualizer import AudioVisualizerWidget
from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.preview_audio")

# Padding to align the visualizer drawing with the seekbar
SEEK_BAR_PADDING = 11


class AudioWidget(Gtk.Box, SignalManager):
    def __init__(self, file_path: Path) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        SignalManager.__init__(self)

        if not app.is_installed("GST"):
            log.info("Could not create AudioWidget because GStreamer is not installed.")
            self._show_init_error()
            return

        self._playbin = Gst.ElementFactory.make("playbin", "bin")
        self._bus_watch_id: int = 0
        self._timeout_id: int = -1
        self._timeout_delay: int = 50  # in ms

        if self._playbin is None:
            log.error("Could not create GST playbin.")
            self._show_init_error()
            return

        self._file_path = file_path
        self._id = hash(self._file_path)

        app.preview_manager.register_audio_stop_func(self._id, self._set_ready)

        self._seek_pos = -1.0
        self._cursor_pos = 0.0
        self._offset_backward = -10e9  # in ns
        self._offset_forward = 10e9
        self._pause_seek = False
        self._is_ready = True
        self._next_state_is_playing = False
        self._pause_on_eos_delay = 100  # in ms

        # Constants which define player's behaviour
        self._speed_min = 0.25
        self._speed_max = 2.00
        self._speed_inc_step = 0.25
        self._speed_dec_step = 0.25

        self._query = Gst.Query.new_position(Gst.Format.TIME)
        self._setup_audio_player(file_path)

        self._ui = get_builder("preview_audio.ui")
        self._is_LTR = self._ui.seek_bar.get_direction() == Gtk.TextDirection.LTR
        self._enable_controls(False)

        cursor = Gdk.Cursor.new_from_name("pointer")
        self._ui.seek_bar.set_cursor(cursor)
        self._ui.progress_label.set_cursor(cursor)
        self._ui.speed_bar.set_cursor(cursor)

        self.append(self._ui.preview_box)
        self._setup_audio_visualizer()

        # Initialize with restored audio state or defaults
        self._state = app.preview_manager.get_audio_state(self._id)
        self._audio_analyzer = None

        if not self._state.is_audio_analyzed:
            # Analyze the audio to determine samples and duration,
            # calls self._update_audio_data when done.
            self._audio_analyzer = AudioAnalyzer(
                file_path, self._update_duration, self._update_samples
            )
        else:
            self._audio_visualizer.set_samples(self._state.samples)
            self._update_ui()

        self._ui.speed_bar_adj.configure(
            value=self._state.speed,
            lower=self._speed_min,
            upper=self._speed_max,
            step_increment=self._speed_inc_step,
            page_increment=self._speed_inc_step,
            page_size=0,
        )

        self._ui.speed_bar.set_value(self._state.speed)
        self._set_playback_speed(self._state.speed)

        self._ui.speed_bar.add_mark(0.25, Gtk.PositionType.BOTTOM, "0.25")
        self._ui.speed_bar.add_mark(0.5, Gtk.PositionType.BOTTOM, "")
        self._ui.speed_bar.add_mark(0.75, Gtk.PositionType.BOTTOM, "")
        self._ui.speed_bar.add_mark(1, Gtk.PositionType.BOTTOM, "1.0")
        self._ui.speed_bar.add_mark(1.25, Gtk.PositionType.BOTTOM, "")
        self._ui.speed_bar.add_mark(1.5, Gtk.PositionType.BOTTOM, "1.5")
        self._ui.speed_bar.add_mark(1.75, Gtk.PositionType.BOTTOM, "")
        self._ui.speed_bar.add_mark(2, Gtk.PositionType.BOTTOM, "2")

        self._ui.progress_label.set_xalign(1.0)

        self._connect(self._ui.seek_bar, "change-value", self._on_seek)
        self._connect(self._ui.seek_bar, "value-changed", self._on_seek_bar_moved)
        self._connect(self._ui.rewind_button, "clicked", self._on_rewind_clicked)
        self._connect(self._ui.play_pause_button, "clicked", self._on_play_clicked)
        self._connect(self._ui.forward_button, "clicked", self._on_forward_clicked)
        self._connect(self._ui.speed_dec_button, "clicked", self._on_speed_dec_clicked)
        self._connect(self._ui.speed_inc_button, "clicked", self._on_speed_inc_clicked)
        self._connect(self._ui.speed_bar, "change-value", self._on_speed_change)

        gesture_seek_click = Gtk.GestureClick(
            button=Gdk.BUTTON_PRIMARY, propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(gesture_seek_click, "pressed", self._on_seek_bar_button_pressed)
        self._connect(gesture_seek_click, "released", self._on_seek_bar_button_released)
        self._ui.seek_bar_box.add_controller(gesture_seek_click)

        gesture_visualizer_click = Gtk.GestureClick(
            button=Gdk.BUTTON_PRIMARY, propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(
            gesture_visualizer_click, "pressed", self._on_visualizer_button_pressed
        )
        self._audio_visualizer.add_controller(gesture_visualizer_click)

        controller_motion = Gtk.EventControllerMotion()
        self._connect(controller_motion, "motion", self._on_seek_bar_cursor_move)
        self._ui.seek_bar.add_controller(controller_motion)

        controller_scroll = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL
        )
        self._connect(controller_scroll, "scroll", self._on_seek_bar_scrolled)
        self._ui.seek_bar.add_controller(controller_scroll)

        gesture_timestamp_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        self._connect(
            gesture_timestamp_click, "pressed", self._on_timestamp_label_clicked
        )
        self._ui.progress_label.add_controller(gesture_timestamp_click)

    def do_unroot(self) -> None:
        self._disconnect_all()

        if self._playbin is not None:
            self._playbin.set_state(Gst.State.NULL)
            bus = self._playbin.get_bus()

            if bus is not None:
                bus.remove_signal_watch()
                bus.disconnect(self._bus_watch_id)

        if self._audio_analyzer is not None:
            self._audio_analyzer.destroy()

        self._remove_seek_bar_update_idle()

        app.preview_manager.unregister_audio_stop_func(self._id)
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def load_audio_file(self, file_path: Path) -> None:
        assert self._playbin is not None

        self._playbin.send_event(Gst.Event.new_eos())
        self._playbin.set_state(Gst.State.NULL)

        self._playbin.set_property("uri", file_path.as_uri())

        self._audio_analyzer = AudioAnalyzer(
            file_path, self._update_duration, self._update_samples
        )

        self._playbin.set_state(Gst.State.READY)
        self._is_ready = True
        self._next_state_is_playing = False
        self._seek(-1.0)
        self._query.set_position(Gst.Format.TIME, 0)

        self._ui.seek_bar.set_value(0.0)
        self._update_ui()

    def set_pause(self, paused: bool) -> None:
        assert Gst is not None
        assert self._playbin is not None
        if paused:
            self._playbin.set_state(Gst.State.PAUSED)
            self._remove_seek_bar_update_idle()
            self._ui.play_icon.set_from_icon_name("media-playback-start-symbolic")
        else:
            self._playbin.set_state(Gst.State.PLAYING)
            self._add_seek_bar_update_idle()
            self._ui.play_icon.set_from_icon_name("media-playback-pause-symbolic")

    def _show_init_error(self) -> None:
        self.append(Gtk.Label(label=_("Audio preview is not available")))

    def _enable_controls(self, status: bool) -> None:
        self._ui.seek_bar.set_sensitive(status)
        self._ui.progress_label.set_sensitive(status)
        self._ui.play_pause_button.set_sensitive(status)
        self._ui.rewind_button.set_sensitive(status)
        self._ui.forward_button.set_sensitive(status)
        self._ui.speed_dec_button.set_sensitive(status)
        self._ui.speed_inc_button.set_sensitive(status)
        self._ui.speed_menubutton.set_sensitive(status)

    def _update_ui(self) -> None:

        if not self._state.duration > 0:
            log.error("Could not successfully load audio. Duration is zero.")
            return

        self._enable_controls(True)

        self._audio_visualizer.render_static_graph(
            self._state.position / self._state.duration
        )

        self._ui.seek_bar_adj.configure(
            value=self._state.position,
            lower=0.0,
            upper=self._state.duration,
            step_increment=5e9,  # for hold+position left/right
            page_increment=0,  # determines scrolling and click behaviour
            page_size=0,
        )

        # Calculate max string length to prevent timestamp label from jumping
        formatted = format_duration(0.0, self._state.duration)
        self._ui.progress_label.set_width_chars(len(f"-{formatted}/{formatted}"))
        self._update_timestamp_label()

    def _update_samples(
        self,
        samples: AudioSampleT,
    ) -> None:
        self._state.samples = samples
        self._audio_visualizer.set_samples(self._state.samples)
        self._state.is_audio_analyzed = True
        self._update_ui()

    def _update_duration(self, duration: float):
        self._state.duration = duration
        self._update_ui()

    def _setup_audio_player(self, file_path: Path) -> None:
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

        if file_path.is_file():
            self._playbin.set_property("uri", file_path.as_uri())
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

    def _setup_audio_visualizer(self) -> None:
        width, _ = self._ui.seek_bar.get_size_request()
        _, height = self._ui.drawing_box.get_size_request()

        width -= 2 * SEEK_BAR_PADDING
        self._audio_visualizer = AudioVisualizerWidget(width, height, SEEK_BAR_PADDING)
        self._ui.drawing_box.append(self._audio_visualizer)

    def _update_timestamp_label(self) -> None:
        cur = self._state.position
        dur = self._state.duration

        dur_str = format_duration(dur, dur)
        ltr_char = "\u200E"

        if self._state.is_timestamp_positive:
            cur_str = f"{format_duration(cur, dur)}"
            self._ui.progress_label.set_text(f"{cur_str}/{dur_str}")
        else:
            cur_str = f"{format_duration(dur - cur, dur)}"
            self._ui.progress_label.set_text(f"{ltr_char}-{cur_str}/{dur_str}")

    def _update_seek_bar_and_visualisation(self) -> bool:
        assert self._playbin is not None
        if self._playbin.query(self._query):
            _fmt, position = self._query.parse_position()

            if not self._pause_seek:
                self._state.position = position
                self._ui.seek_bar.set_value(self._state.position)

            self._audio_visualizer.render_static_graph(
                position / self._state.duration, self._seek_pos / self._state.duration
            )

            if self._state.is_eos:
                self._audio_visualizer.render_static_graph(
                    self._state.position / self._state.duration
                )
                self._remove_seek_bar_update_idle()

        return True

    def _add_seek_bar_update_idle(self) -> None:
        if self._timeout_id != -1:
            return

        self._timeout_id = GLib.timeout_add(
            self._timeout_delay, self._update_seek_bar_and_visualisation
        )

    def _remove_seek_bar_update_idle(self) -> None:
        if self._timeout_id != -1:
            GLib.source_remove(self._timeout_id)
        self._timeout_id = -1

    def _get_constrained_position(self, pos: float) -> float:
        if pos >= self._state.duration:
            return self._state.duration
        if pos < 0:
            return 0.0
        return pos

    def _get_constrained_speed(self, speed: float) -> tuple[bool, float]:
        if self._speed_min <= speed <= self._speed_max:
            return True, speed
        return False, self._state.speed

    def _set_playback_speed(self, speed: float) -> bool:
        success, self._state.speed = self._get_constrained_speed(speed)
        if not success:
            return False

        self._ui.speed_label.set_text(f"{self._state.speed:.2f}x")

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

    def _get_paused(self) -> bool:
        assert self._playbin is not None
        _, state, _ = self._playbin.get_state(timeout=40)
        return state == Gst.State.PAUSED

    def _get_ready(self) -> bool:
        assert self._playbin is not None
        _, state, _ = self._playbin.get_state(timeout=40)
        return state == Gst.State.READY

    def _pause_on_eos(self) -> bool:
        assert self._playbin is not None
        self._ui.play_icon.set_from_icon_name("media-playback-start-symbolic")

        self._state.position = self._state.duration
        self._playbin.set_state(Gst.State.PAUSED)

        return False

    def _error_info(self, message: Gst.Message) -> tuple[str, int]:
        structure = message.get_structure()
        assert structure is not None
        gerror = structure.get_value("gerror")
        assert gerror is not None
        return gerror.domain, gerror.code

    def _handle_error_on_playback(self, message: Gst.Message):
        domain, code = self._error_info(message)
        if domain == "gst-resource-error-quark":
            if code == 10:
                # On Windows: AUDCLNT_E_DEVICE_INVALIDATED (10)
                # GST_RESOURCE_ERROR_WRITE (10)
                # used when the resource can't be written to.
                self._set_ready()

    def _set_ready(self) -> None:
        assert self._playbin is not None
        self._playbin.set_state(Gst.State.READY)
        self._is_ready = True

        # State order is READY -> PAUSE -> PLAYING
        # I.e. we need to pause first, but keep in mind, that we want to
        # go a state further
        self._next_state_is_playing = True

        self._ui.play_icon.set_from_icon_name("media-playback-start-symbolic")

    def _seek(self, position: float) -> None:
        """
        Used in:
        * _on_seek: When the slider is dragged
        * _on_seek_bar_button_released:
        * _on_play_clicked
        """
        assert self._playbin is not None

        self._state.position = self._get_constrained_position(position)
        self._state.is_eos = False

        if self._pause_seek:
            return

        self._playbin.seek(
            self._state.speed,
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,
            Gst.SeekType.SET,
            int(self._state.position),
            Gst.SeekType.NONE,
            0,
        )

        if self._state.position >= self._state.duration:
            self._state.is_eos = True
            self._playbin.send_event(Gst.Event.new_eos())

    def _seek_unconditionally(self, position: float) -> None:
        """
        Used in:
        * _on_seek_bar_button_pressed
        * _on_rewind_clicked
        * _on_forward_clicked
        """
        assert self._playbin is not None

        self._state.position = self._get_constrained_position(position)
        self._state.is_eos = self._state.position >= self._state.duration

        if not self._is_ready:
            self._playbin.seek(
                self._state.speed,
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH,
                Gst.SeekType.SET,
                int(self._state.position),
                Gst.SeekType.NONE,
                0,
            )

        self._ui.seek_bar.set_value(self._state.position)
        self._audio_visualizer.render_static_graph(
            self._state.position / self._state.duration
        )

    def _on_bus_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        assert self._playbin is not None

        if message.type == Gst.MessageType.EOS:
            self._state.is_eos = True
            GLib.timeout_add(self._pause_on_eos_delay, self._pause_on_eos)
        elif message.type == Gst.MessageType.STATE_CHANGED:
            is_paused = self._get_paused()

            if self._is_ready and is_paused:
                # State changed from READY --> PAUSED
                self._is_ready = False
                self._playbin.seek(
                    self._state.speed,
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH,
                    Gst.SeekType.SET,
                    int(self._state.position),
                    Gst.SeekType.NONE,
                    0,
                )
                self._ui.seek_bar.set_value(self._state.position)

                if not self._next_state_is_playing:
                    return

                # Continue from state PAUSED --> PLAYING
                self.set_pause(False)
                self._next_state_is_playing = False
        elif message.type == Gst.MessageType.ERROR:
            self._handle_error_on_playback(message)

    def _on_speed_change(
        self, _range: Gtk.Range, _scroll: Gtk.ScrollType, value: float
    ) -> None:

        self._set_playback_speed(value)

    def _on_speed_inc_clicked(self, _button: Gtk.Button) -> None:
        speed = self._state.speed + self._speed_inc_step
        if self._set_playback_speed(speed):
            self._ui.speed_bar.set_value(speed)

    def _on_speed_dec_clicked(self, _button: Gtk.Button) -> None:
        speed = self._state.speed - self._speed_inc_step
        if self._set_playback_speed(speed):
            self._ui.speed_bar.set_value(speed)
        else:
            log.error("Could not set speed.")

    def _on_seek_bar_moved(self, _scake: Gtk.Scale) -> None:
        self._update_timestamp_label()

    def _on_timestamp_label_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        self._state.is_timestamp_positive = not self._state.is_timestamp_positive
        self._update_timestamp_label()
        return Gdk.EVENT_STOP

    def _on_seek_bar_button_pressed(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        assert self._cursor_pos is not None
        # There are two cases when the user clicks on the seek bar:
        # 1) Press and immediately release: Jump to the new position and
        #   continue playing
        # 2) Start of dragging the slider
        # In case of 2) pause active seeking to prevent audio scrubbing and
        # instead continue playing
        self._pause_seek = True
        width = self._ui.seek_bar.get_width() - 2 * SEEK_BAR_PADDING
        new_pos = self._state.duration * self._cursor_pos / width
        self._seek_unconditionally(new_pos)
        return Gdk.EVENT_STOP

    def _on_visualizer_button_pressed(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        _y: float,
    ) -> int:
        assert self._cursor_pos is not None
        width = self._audio_visualizer.get_width() - SEEK_BAR_PADDING
        new_pos = self._state.duration * x / width
        self._seek_unconditionally(new_pos)
        return Gdk.EVENT_STOP

    def _on_seek_bar_button_released(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        self._pause_seek = False
        self._seek(self._state.position)

        # Set the seek position to -1 to indicate that the user isn't about
        # to change the position
        self._seek_pos = -1
        return Gdk.EVENT_STOP

    def _on_seek_bar_cursor_move(
        self,
        _event_controller: Gtk.EventControllerMotion,
        x: float,
        _y: float,
    ) -> None:
        # Used to determine the click position on the seekbar
        if self._is_LTR:
            self._cursor_pos = x - SEEK_BAR_PADDING
        else:
            width = self._ui.seek_bar.get_width()
            self._cursor_pos = width - (x + SEEK_BAR_PADDING)

    def _on_seek_bar_scrolled(
        self,
        _event_controller: Gtk.EventControllerScroll,
        _dx: float,
        dy: float,
    ) -> None:
        if dy > 0:
            new_pos = self._state.position + self._offset_backward
        else:
            new_pos = self._state.position + self._offset_forward
        self._seek_unconditionally(new_pos)

    def _on_seek(
        self, _scale: Gtk.Scale, _scroll: Gtk.ScrollType, value: float
    ) -> None:
        self._seek(value)

        if not (self._get_paused() or self._get_ready()):
            self._seek_pos = value
        else:
            self._audio_visualizer.render_static_graph(
                self._state.position / self._state.duration
            )

    def _on_play_clicked(self, _button: Gtk.Button) -> None:
        app.preview_manager.stop_audio_except(self._id)
        if self._get_ready():
            # The order is always READY -> PAUSE -> PLAYING
            self.set_pause(True)
            self._next_state_is_playing = True

            if self._state.is_eos:
                new_pos = 0.0
            else:
                new_pos = self._state.position

            self._seek(new_pos)
            self._query.set_position(Gst.Format.TIME, int(new_pos))
            self._ui.seek_bar.set_value(new_pos)
            return

        if self._state.is_eos and self._get_paused():
            self._seek(0.0)
            self._ui.seek_bar.set_value(0.0)

        self.set_pause(not self._get_paused())

    def _on_rewind_clicked(self, _button: Gtk.Button) -> None:
        new_pos = self._get_constrained_position(
            self._state.position + self._offset_backward
        )
        self._seek_unconditionally(new_pos)

    def _on_forward_clicked(self, _button: Gtk.Button) -> None:
        new_pos = self._get_constrained_position(
            self._state.position + self._offset_forward
        )
        self._seek_unconditionally(new_pos)
