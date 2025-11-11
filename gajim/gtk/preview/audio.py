# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
from concurrent.futures import Future
from functools import partial
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.enum import AudioPlayerState
from gajim.common.multiprocess.audio_preview import extract_audio_properties
from gajim.common.util.text import format_duration

from gajim.gtk.audio_player import AudioPlayer
from gajim.gtk.preview.audio_visualizer import AudioVisualizerWidget
from gajim.gtk.preview.misc import LoadingBox  # noqa: F401 # pyright: ignore
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.preview.audio")


SEEK_BAR_PADDING = 12


@Gtk.Template.from_string(string=get_ui_string("preview/audio.ui"))
class AudioPreviewWidget(Gtk.Box, SignalManager):

    __gtype_name__ = "AudioPreviewWidget"

    __gsignals__ = {
        "display-error": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (),
        )
    }

    _open_folder_button: Gtk.Button = Gtk.Template.Child()
    _save_as_button: Gtk.Button = Gtk.Template.Child()
    _stack: Gtk.Stack = Gtk.Template.Child()
    _seek_bar_adj: Gtk.Adjustment = Gtk.Template.Child()
    _speed_bar_adj: Gtk.Adjustment = Gtk.Template.Child()
    _drawing_box: Gtk.Box = Gtk.Template.Child()
    _seek_bar_box: Gtk.Box = Gtk.Template.Child()
    _seek_bar: Gtk.Scale = Gtk.Template.Child()
    _progress_label: Gtk.Label = Gtk.Template.Child()
    _control_box: Gtk.Box = Gtk.Template.Child()
    _rewind_button: Gtk.Button = Gtk.Template.Child()
    _play_pause_button: Gtk.Button = Gtk.Template.Child()
    _play_icon: Gtk.Image = Gtk.Template.Child()
    _forward_button: Gtk.Button = Gtk.Template.Child()
    _speed_dec_button: Gtk.Button = Gtk.Template.Child()
    _speed_menubutton: Gtk.MenuButton = Gtk.Template.Child()
    _speed_label: Gtk.Label = Gtk.Template.Child()
    _speed_inc_button: Gtk.Button = Gtk.Template.Child()
    _speed_popover: Gtk.Popover = Gtk.Template.Child()
    _speed_bar: Gtk.Scale = Gtk.Template.Child()

    def __init__(
        self,
        filename: str,
        file_size: int,
        orig_path: Path,
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._orig_path = orig_path
        self._filename = filename
        self._file_size = file_size

        self._id = hash(self._orig_path) % 100_000

        assert app.audio_player is not None
        self._preview_state = app.audio_player.get_audio_state(self._id)

        # UI
        self._is_ltr = bool(self.get_direction() == Gtk.TextDirection.LTR)
        self._offset_backward = -10e9  # in ns
        self._offset_forward = 10e9
        self._cursor_pos = 0.0
        self._user_holds_position_slider = False
        self._seek_ts = -1  # in ns, -1 means invalid
        self._new_voice_message_track = False

        self._open_folder_button.set_action_target_value(
            GLib.Variant("s", str(self._orig_path))
        )
        self._save_as_button.set_action_target_value(
            GLib.Variant("s", str(self._orig_path))
        )

        self._speed_bar_adj.set_value(self._preview_state.speed)
        self._set_playback_speed(self._preview_state.speed)

        self._speed_bar.add_mark(0.25, Gtk.PositionType.BOTTOM, "0.25")
        self._speed_bar.add_mark(0.5, Gtk.PositionType.BOTTOM, "")
        self._speed_bar.add_mark(0.75, Gtk.PositionType.BOTTOM, "")
        self._speed_bar.add_mark(1, Gtk.PositionType.BOTTOM, "1.0")
        self._speed_bar.add_mark(1.25, Gtk.PositionType.BOTTOM, "")
        self._speed_bar.add_mark(1.5, Gtk.PositionType.BOTTOM, "1.5")
        self._speed_bar.add_mark(1.75, Gtk.PositionType.BOTTOM, "")
        self._speed_bar.add_mark(2, Gtk.PositionType.BOTTOM, "2")
        self._connect(self._speed_bar, "change-value", self._on_speed_change)

        self._connect(self._speed_dec_button, "clicked", self._on_speed_dec_clicked)
        self._connect(self._speed_inc_button, "clicked", self._on_speed_inc_clicked)

        self._connect(self._rewind_button, "clicked", self._on_rewind_clicked)
        self._connect(self._forward_button, "clicked", self._on_forward_clicked)

        self._gesture_visualizer_click = Gtk.GestureClick(
            button=Gdk.BUTTON_PRIMARY, propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(
            self._gesture_visualizer_click,
            "pressed",
            self._on_visualizer_button_clicked,
        )

        gesture_seek_click = Gtk.GestureClick(
            button=Gdk.BUTTON_PRIMARY, propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(gesture_seek_click, "pressed", self._on_seek_bar_button_pressed)
        self._connect(gesture_seek_click, "released", self._on_seek_bar_button_released)
        self._seek_bar_box.add_controller(gesture_seek_click)

        controller_motion = Gtk.EventControllerMotion(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(controller_motion, "motion", self._on_seek_bar_cursor_move)
        self._seek_bar.add_controller(controller_motion)

        controller_scroll = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL
        )
        self._connect(controller_scroll, "scroll", self._on_seek_bar_scrolled)
        self._seek_bar.add_controller(controller_scroll)

        gesture_timestamp_click = Gtk.GestureClick(
            button=Gdk.BUTTON_PRIMARY, propagation_phase=Gtk.PropagationPhase.TARGET
        )
        self._connect(
            gesture_timestamp_click, "pressed", self._on_timestamp_label_clicked
        )
        self._progress_label.add_controller(gesture_timestamp_click)

        self._visualizer = AudioVisualizerWidget(
            width=300 - 2 * SEEK_BAR_PADDING, x_offset=SEEK_BAR_PADDING
        )
        self._visualizer.add_controller(self._gesture_visualizer_click)
        self._drawing_box.append(self._visualizer)

        self._progress_id = None
        self._connect(self._play_pause_button, "clicked", self._on_play_clicked)

        if self._orig_path.is_file():
            # In case of the voice message recorder, start with no existing file
            if self._preview_state.duration == 0 or not self._preview_state.samples:
                self._get_audio_properties()
            else:
                self._display_audio_preview()

    @property
    def id(self) -> int:
        return self._id

    def do_unroot(self) -> None:
        self._cleanup()

    def sample_voice_message(self, audio_path: Path) -> None:
        assert app.audio_player is not None
        if app.audio_player.preview_id == self._id:
            app.audio_player.stop(self._id)
        self._play_icon.set_from_icon_name("lucide-play-symbolic")
        self._orig_path = audio_path
        self._preview_state.position = 0
        self._seek_bar.set_value(0)
        self._new_voice_message_track = True
        self._get_audio_properties()

    def _get_audio_properties(self) -> None:
        assert self._orig_path is not None

        try:
            future = app.process_pool.submit(extract_audio_properties, self._orig_path)
            future.add_done_callback(
                partial(GLib.idle_add, self._get_audio_properties_finished)
            )
        except Exception as error:
            log.warning("Creating thumbnail failed for: %s %s", self._orig_path, error)

    def _get_audio_properties_finished(
        self, future: Future[tuple[list[tuple[float, float]], int]]
    ) -> bool:
        try:
            samples, duration = future.result()
        except Exception as error:
            log.exception(
                "Creating thumbnail failed for: %s %s", self._orig_path, error
            )
        else:
            self._preview_state.samples = samples
            self._preview_state.duration = duration
            log.info("State: %s", self._preview_state)
            self._display_audio_preview()

        return GLib.SOURCE_REMOVE

    def _set_preview_state_position(self, position: float) -> None:
        position = max(0.0, position)
        position = min(position, self._preview_state.duration)
        self._preview_state.position = position

    def _convert_pos_to_text(self, current_position: float, duration: float):
        dur_str = format_duration(duration, duration)
        ltr_char = "\u200e"

        if self._preview_state.is_timestamp_positive:
            cur_str = f"{format_duration(current_position, duration)}"
            cur_str = f"{cur_str}/{dur_str}"
        else:
            cur_str = f"{format_duration(duration - current_position, duration)}"
            cur_str = f"{ltr_char}-{cur_str}/{dur_str}"

        return cur_str

    def _on_audio_playback_progressed(
        self, _obj: AudioPlayer, preview_id: int, _state: AudioPlayerState
    ) -> None:
        if preview_id != self.id:
            return
        self._update_ui_from_state()

    def _on_audio_playback_changed(
        self, _obj: AudioPlayer, preview_id: int, state: int
    ) -> None:
        assert app.audio_player is not None
        if preview_id != self.id:
            self._disconnect_object(app.audio_player)
            self._play_icon.set_from_icon_name("lucide-play-symbolic")
            return

        if state == AudioPlayerState.PLAYING.value:
            self._play_icon.set_from_icon_name("lucide-pause-symbolic")
        else:
            self._play_icon.set_from_icon_name("lucide-play-symbolic")

        self._update_ui_from_state()

    def _update_ui_from_state(self):
        if not self._user_holds_position_slider:
            self._seek_bar.set_value(self._preview_state.position)
        self._visualizer.render_static_graph(
            self._preview_state.position / self._preview_state.duration,
            self._seek_ts / self._preview_state.duration,
        )
        self._progress_label.set_text(
            self._convert_pos_to_text(
                self._preview_state.position, self._preview_state.duration
            )
        )

    def _on_play_clicked(self, _button: Gtk.Button) -> None:
        assert app.audio_player is not None
        if app.audio_player.preview_id != self._id or self._new_voice_message_track:
            self._new_voice_message_track = False
            self._connect(
                app.audio_player,
                "audio-playback-progressed",
                self._on_audio_playback_progressed,
            )
            self._connect(
                app.audio_player,
                "audio-playback-changed",
                self._on_audio_playback_changed,
            )
            app.audio_player.play_audio_file(self._orig_path, self._id)
        else:
            app.audio_player.toggle_playback()

    def _update_timestamp_label(self) -> None:
        cur = self._preview_state.position
        dur = self._preview_state.duration

        dur_str = format_duration(dur, dur)
        ltr_char = "\u200e"

        if self._preview_state.is_timestamp_positive:
            cur_str = f"{format_duration(cur, dur)}"
            self._progress_label.set_text(f"{cur_str}/{dur_str}")
        else:
            cur_str = f"{format_duration(dur - cur, dur)}"
            self._progress_label.set_text(f"{ltr_char}-{cur_str}/{dur_str}")

    def _on_timestamp_label_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        self._preview_state.is_timestamp_positive = (
            not self._preview_state.is_timestamp_positive
        )
        self._update_timestamp_label()
        return Gdk.EVENT_STOP

    def _convert_position_to_timestamp(self, x: float, x_max: float) -> float:
        if x_max == 0.0:
            log.warning("Width is zero, when converting position to timestamp")
            return 0.0

        if not self._is_ltr:
            x = x_max - x
        x = max(0.0, x)
        x = min(x, x_max)
        timestamp = x / x_max * self._preview_state.duration
        return timestamp

    def _on_seek_bar_button_pressed(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        self._user_holds_position_slider = True
        return Gdk.EVENT_STOP

    def _on_seek_bar_button_released(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        assert app.audio_player is not None

        seek_ts = self._convert_position_to_timestamp(
            self._cursor_pos, self._seek_bar.get_width()
        )
        if app.audio_player.preview_id != self.id:
            self._preview_state.position = seek_ts
        else:
            app.audio_player.set_playback_position(self._id, seek_ts)

        self._update_ui_from_state()

        self._seek_ts = -1
        self._user_holds_position_slider = False

        return Gdk.EVENT_STOP

    def _on_seek_bar_cursor_move(
        self,
        _event_controller: Gtk.EventControllerMotion,
        x: float,
        _y: float,
    ) -> None:
        assert app.audio_player is not None
        if not self._user_holds_position_slider:
            return

        if abs(x - self._cursor_pos) < 1e-2:
            return

        self._cursor_pos = x
        seek_ts = self._convert_position_to_timestamp(x, self._seek_bar.get_width())
        if (
            self._user_holds_position_slider
            and self._preview_state.pipeline_state != AudioPlayerState.PLAYING
        ):
            if app.audio_player.preview_id != self.id:
                self._preview_state.position = seek_ts
            else:
                app.audio_player.set_playback_position(self._id, seek_ts)
            self._update_ui_from_state()
        else:
            self._seek_ts = seek_ts

    def _on_seek_bar_scrolled(
        self,
        _event_controller: Gtk.EventControllerScroll,
        _dx: float,
        dy: float,
    ) -> None:
        assert app.audio_player is not None
        if dy > 0:
            timestamp = self._preview_state.position + self._offset_backward
        else:
            timestamp = self._preview_state.position + self._offset_forward

        self._set_preview_state_position(timestamp)
        app.audio_player.set_playback_position(self.id, self._preview_state.position)
        self._update_ui_from_state()

    def _on_visualizer_button_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        _y: float,
    ) -> int:
        assert app.audio_player is not None
        assert self._cursor_pos is not None

        timestamp = self._convert_position_to_timestamp(
            x, self._visualizer.get_effective_width()
        )

        self._set_preview_state_position(timestamp)
        self._update_ui_from_state()
        app.audio_player.set_playback_position(self._id, timestamp)

        return Gdk.EVENT_STOP

    def _display_audio_preview(self) -> None:
        self._visualizer.set_samples(self._preview_state.samples)
        self._seek_bar_adj.set_lower(0.0)
        self._seek_bar_adj.set_upper(self._preview_state.duration)
        self._update_ui_from_state()
        self._stack.set_visible_child_name("preview")

    def _set_playback_speed(self, speed: float) -> None:
        assert app.audio_player is not None
        speed = max(0.25, speed)
        speed = min(speed, 2.0)

        self._preview_state.speed = speed
        self._speed_label.set_text(f"{speed:.2f}x")
        self._speed_bar_adj.set_value(speed)

        if app.audio_player.preview_id != self.id:
            return

        app.audio_player.set_playback_speed(speed)

    def _on_speed_change(
        self, _range: Gtk.Range, _scroll: Gtk.ScrollType, value: float
    ) -> None:

        self._set_playback_speed(value)

    def _on_speed_dec_clicked(self, _button: Gtk.Button) -> None:
        speed = self._preview_state.speed - self._speed_bar_adj.get_step_increment()
        self._set_playback_speed(speed)

    def _on_speed_inc_clicked(self, _button: Gtk.Button) -> None:
        speed = self._preview_state.speed + self._speed_bar_adj.get_step_increment()
        self._set_playback_speed(speed)

    def _change_playback_position_by_step(self, step: float) -> None:
        assert app.audio_player is not None
        new_pos = self._preview_state.position + step
        new_pos = max(0.0, new_pos)
        new_pos = min(new_pos, self._preview_state.duration)

        if app.audio_player.preview_id != self.id:
            self._preview_state.position = new_pos
        else:
            app.audio_player.set_playback_position(self._id, new_pos)

        self._update_ui_from_state()

    def _on_rewind_clicked(self, _button: Gtk.Button) -> None:
        self._change_playback_position_by_step(self._offset_backward)

    def _on_forward_clicked(self, _button: Gtk.Button) -> None:
        self._change_playback_position_by_step(self._offset_forward)

    def _cleanup(self) -> None:
        assert app.audio_player is not None
        Gtk.Box.do_unroot(self)
        app.audio_player.stop(self._id)
        self._disconnect_all()
        app.check_finalize(self)
