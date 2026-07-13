# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.audio_player import AudioPreviewState
from gajim.gtk.preview.audio_visualizer import AudioVisualizerWidget
from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.preview_audio_waveform_navigator")


class AudioWaveformNavigator(AudioVisualizerWidget, SignalManager):
    __gtype_name__ = "AudioWaveformNavigator"

    __gsignals__ = {
        "seeked": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (float,),
        ),
    }

    def __init__(
        self, preview_state: AudioPreviewState, width: int = 340, height: int = 50
    ) -> None:
        AudioVisualizerWidget.__init__(
            self,
            width=width,
            is_seekable=True,
        )
        SignalManager.__init__(self)

        self._seek_ts = -1.0
        self._cursor_pos = 0.0
        self._user_holds_position_slider = False
        self._preview_state = preview_state

        self._scroll_step = 1e9  # 1 second

        self._width = width
        self._height = height
        self._is_ltr = bool(self.get_direction() == Gtk.TextDirection.LTR)

        gesture_seek_click = Gtk.GestureClick(
            button=Gdk.BUTTON_PRIMARY, propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(gesture_seek_click, "pressed", self._on_button_pressed)
        self._connect(gesture_seek_click, "released", self._on_button_released)

        controller_motion = Gtk.EventControllerMotion(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(controller_motion, "motion", self._on_cursor_move)

        controller_scroll = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.HORIZONTAL,
            propagation_phase=Gtk.PropagationPhase.CAPTURE,
        )
        self._connect(controller_scroll, "scroll", self._on_scroll)

        self.add_controller(controller_scroll)
        self.add_controller(controller_motion)
        self.add_controller(gesture_seek_click)

    def run_destroy(self) -> None:
        self._disconnect_all()
        app.check_finalize(self)

    def update(self) -> None:
        if not self._preview_state.duration > 0:
            return

        self.render_static_graph(
            self._preview_state.position / self._preview_state.duration,
            self._seek_ts / self._preview_state.duration,
        )

    def _convert_position_to_timestamp(self, x: float, x_max: float) -> float:
        if x_max == 0.0:
            log.warning("Width is zero, when converting position to thimestamp")
            return 0.0

        if not self._preview_state.duration > 0:
            return 0.0

        if not self._is_ltr:
            x = x_max - x
        x = max(0.0, x)
        x = min(x, x_max)
        timestamp = x / x_max * self._preview_state.duration
        return timestamp

    def _on_button_pressed(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        _y: float,
    ) -> None:
        self._user_holds_position_slider = True
        gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)
        self._seek_ts = self._convert_position_to_timestamp(x, self.get_width())
        self.update()

    def _on_button_released(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        _y: float,
    ) -> None:
        if not self._preview_state.duration > 0:
            return

        timestamp = self._convert_position_to_timestamp(x, self.get_width())
        self._seek_ts = -1.0
        self.emit(
            "seeked",
            timestamp,
        )
        self._user_holds_position_slider = False
        self.render_static_graph(
            timestamp / self._preview_state.duration,
            self._seek_ts / self._preview_state.duration,
        )

    def _on_cursor_move(
        self,
        _event_controller: Gtk.EventControllerMotion,
        x: float,
        _y: float,
    ) -> None:
        if not self._user_holds_position_slider:
            return

        if abs(x - self._cursor_pos) < 1e-2:
            return

        self._cursor_pos = x
        self._seek_ts = self._convert_position_to_timestamp(x, self.get_width())
        self.update()

    def _on_scroll(
        self,
        _event_controller: Gtk.EventControllerScroll,
        dx: float,
        _dy: float,
    ) -> bool:
        if not self._preview_state.duration > 0:
            return False

        if dx > 0:
            timestamp = self._preview_state.position + self._scroll_step
        else:
            timestamp = self._preview_state.position - self._scroll_step
        self.emit("seeked", timestamp)
        self.render_static_graph(
            timestamp / self._preview_state.duration,
            self._seek_ts / self._preview_state.duration,
        )
        return True
