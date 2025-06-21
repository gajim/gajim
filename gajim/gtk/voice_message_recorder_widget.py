# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging
from collections.abc import Callable
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.util.text import format_duration

from gajim.gtk.builder import get_builder
from gajim.gtk.preview_audio import AudioWidget
from gajim.gtk.preview_audio_visualizer import AudioVisualizerWidget
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.voice_message_recorder import GST_ERROR_ON_RECORDING
from gajim.gtk.voice_message_recorder import GST_ERROR_ON_START
from gajim.gtk.voice_message_recorder import VoiceMessageRecorder

log = logging.getLogger("gajim.gtk.voice_message_recorder_widget")

TIME_LABEL_UPDATE_DELAY = 200
ANIMATION_PERIOD = 4
VISUALIZATION_UPDATE_DELAY = int(100 / ANIMATION_PERIOD)


class VoiceMessageRecorderButton(Gtk.MenuButton, SignalManager):
    def __init__(self) -> None:
        Gtk.MenuButton.__init__(self, visible=False, valign=Gtk.Align.CENTER)
        SignalManager.__init__(self)

        self.set_visible(app.settings.get("show_voice_message_button"))

        app.settings.bind_signal("show_voice_message_button", self, "set_visible")

        self._ui = get_builder("voice_message_recorder.ui")

        if not app.is_installed("GST"):
            self.set_sensitive(False)
            self.set_tooltip_text(_("Voice Messages are not available"))
            self.set_child(
                Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
            )
            return

        app.settings.connect_signal(
            "audio_input_device", self._on_audio_input_device_changed
        )

        gesture_direct_record_pressed = Gtk.GestureLongPress(button=Gdk.BUTTON_PRIMARY)
        gesture_direct_record_pressed.set_propagation_phase(
            Gtk.PropagationPhase.CAPTURE
        )
        self._connect(
            gesture_direct_record_pressed, "pressed", self._on_direct_record_pressed
        )
        self.add_controller(gesture_direct_record_pressed)

        gesture_direct_record_released = Gtk.GestureLongPress(button=Gdk.BUTTON_PRIMARY)
        self._connect(
            gesture_direct_record_released, "end", self._on_direct_record_long_press_end
        )
        self.add_controller(gesture_direct_record_released)

        self._time_label_update_timeout_id = None
        self._visualization_timeout_id = None

        self._mic_button_long_pressed = False

        self._animation_index = 0
        self._new_recording = True

        self._voice_message_recorder = VoiceMessageRecorder(self._on_error_occurred)
        self._audio_player_widget = AudioWidget(Path(""))

        self._connect(self._ui.cancel_button, "clicked", self._on_cancel_clicked)
        self._connect(
            self._ui.record_toggle_button, "clicked", self._on_record_toggle_clicked
        )
        self._connect(self._ui.send_button, "clicked", self._on_send_clicked)

        self.set_popover(self._ui.popover)
        self._connect(self._ui.popover, "closed", self._on_popover_closed)

        self._audio_visualizer = AudioVisualizerWidget()
        self._audio_visualizer.set_parameters(1.0, ANIMATION_PERIOD)
        self._audio_visualizer.set_visible(True)

        self._ui.visualization_box.append(self._audio_visualizer)
        self._ui.progression_box.set_visible(True)

        self._ui.audio_player_box.append(self._audio_player_widget)
        self._ui.audio_player_box.set_visible(False)

        self._update_button_state()
        self._update_icons()
        self._update_visualization(self._voice_message_recorder.recording_samples)
        app.ged.register_event_handler(
            "register-actions", ged.GUI1, self._on_register_actions
        )

    def do_unroot(self) -> None:
        self._voice_message_recorder.cleanup()

        self._disconnect_all()
        app.settings.disconnect_signals(self)
        Gtk.MenuButton.do_unroot(self)

    def _on_register_actions(self, _event: events.RegisterActions) -> None:
        # action = app.window.get_action('send-file-jingle')
        # action.connect('notify::enabled', self._on_send_file_action_changed)

        action = app.window.get_action("send-file-httpupload")
        self._connect(action, "notify::enabled", self._on_send_file_action_changed)

    @property
    def audio_rec_file_path(self) -> str:
        return self._voice_message_recorder.audio_file_uri

    def _on_send_file_action_changed(self, *args: Any) -> None:
        self._update_button_state()
        self._update_icons()

    def _on_audio_input_device_changed(self, *args: Any) -> None:
        self._update_button_state()
        self._update_icons()

    def _update_button_state(self) -> None:
        if self._voice_messages_available():
            self.set_sensitive(True)
            tooltip_text = _("Record Voice Message… (hold button to record directly)")
        else:
            self.set_sensitive(False)
            tooltip_text = _("Voice Messages are not available")

        self.set_tooltip_text(tooltip_text)

    def _update_icons(self) -> None:
        if self._voice_message_recorder.recording_in_progress:
            button_image_name = "media-record-symbolic"
            toggle_image_name = "media-playback-pause-symbolic"
        else:
            button_image_name = "audio-input-microphone-symbolic"
            toggle_image_name = "media-record-symbolic"

        button_image = Gtk.Image.new_from_icon_name(button_image_name)
        self.set_child(button_image)

        self._ui.record_toggle_button_image.set_from_icon_name(toggle_image_name)

    def _is_audio_input_device_found(self) -> bool:
        audio_device = app.settings.get("audio_input_device")

        if not self._voice_message_recorder.audio_input_device_exists(audio_device):
            log.error('Audio device "%s" not found', audio_device)
            return False

        return True

    def _is_audio_input_device_blacklisted(self) -> bool:
        audio_device = app.settings.get("audio_input_device")
        negative_list = ["audiotestsrc"]

        for device in negative_list:
            if device in audio_device:
                log.error('Audio device "%s" not supported', audio_device)
                return True

        return False

    def _voice_messages_available(self) -> bool:
        if (
            self._is_audio_input_device_blacklisted()
            or not self._is_audio_input_device_found()
            or self._voice_message_recorder.pipeline_setup_failed
        ):
            return False

        httpupload = app.window.get_action_enabled("send-file-httpupload")
        # jingle = app.window.get_action_enabled('send-file-jingle')
        jingle = False
        return httpupload or jingle

    def _remove_timeout_ids(self) -> None:
        if self._time_label_update_timeout_id is not None:
            GLib.source_remove(self._time_label_update_timeout_id)
        self._time_label_update_timeout_id = None

        if self._visualization_timeout_id is not None:
            GLib.source_remove(self._visualization_timeout_id)
        self._visualization_timeout_id = None

    def _start_recording(self) -> None:
        log.debug("Start recording")
        self._time_label_update_timeout_id = GLib.timeout_add(
            TIME_LABEL_UPDATE_DELAY,
            self._update_time_label,
            self._voice_message_recorder.recording_time,
        )

        self._visualization_timeout_id = GLib.timeout_add(
            VISUALIZATION_UPDATE_DELAY,
            self._update_visualization,
            self._voice_message_recorder.recording_samples,
        )

        self._voice_message_recorder.start_recording()
        self._new_recording = False
        self._update_icons()

    def _stop_recording(self) -> None:
        log.debug("Stopping recording")
        self._voice_message_recorder.stop_recording()
        self._show_playback_box()
        self._remove_timeout_ids()
        self._update_icons()
        self._animation_index = 0

    def _stop_and_reset_recording(self) -> None:
        log.debug("Stopping and resetting recording")
        self._voice_message_recorder.stop_and_reset()

        self._ui.time_label.set_text(format_duration(0, 0))
        self._ui.send_button.set_sensitive(False)
        self._ui.cancel_button.set_sensitive(False)

        self._animation_index = 0
        self._new_recording = True
        self._update_visualization(self._voice_message_recorder.recording_samples)

        self._show_recording_box()
        self._remove_timeout_ids()
        self._update_icons()

    def _on_error_occurred(self, occasion: int, error_msg: str) -> None:
        self._show_error_message(error_msg)

        if occasion == GST_ERROR_ON_START:
            if not self._voice_message_recorder.audio_file_is_valid:
                self._stop_and_reset_recording()
            else:
                self._stop_recording()
        elif occasion == GST_ERROR_ON_RECORDING:
            self._stop_recording()

            if not self._voice_message_recorder.audio_file_is_valid:
                self._stop_and_reset_recording()
            else:
                self._audio_player_widget.load_audio_file(
                    Path(self._voice_message_recorder.audio_file_abspath)
                )
                self._show_playback_box()
        else:
            self._stop_and_reset_recording()

    def _update_time_label(self, recording_time: Callable[..., int]) -> bool:
        formatted = format_duration(recording_time(), recording_time())
        self._ui.time_label.set_text(formatted)
        return True

    def _update_visualization(
        self,
        samples: Callable[..., list[tuple[float, float]]],
    ) -> bool:
        if self._animation_index == 0:
            if not self._new_recording:
                self._voice_message_recorder.request_new_sample()
            self._audio_visualizer.set_samples(samples())
        self._audio_visualizer.render_animated_graph(self._animation_index)
        self._animation_index = (self._animation_index + 1) % ANIMATION_PERIOD
        return True

    def _show_playback_box(self) -> None:
        self._ui.audio_player_box.set_visible(True)
        self._ui.progression_box.set_visible(False)

    def _show_recording_box(self) -> None:
        self._ui.audio_player_box.set_visible(False)
        self._ui.progression_box.set_visible(True)
        self._audio_player_widget.set_pause(True)

    def _show_recording_controls(self) -> None:
        self._ui.record_control_box.set_visible(True)

    def _hide_recording_controls(self) -> None:
        self._ui.record_control_box.set_visible(False)

    def _show_error_message(self, error_msg: str) -> None:
        self._ui.error_label.set_text(error_msg)
        self._ui.error_label.set_visible(True)

    def _hide_error_message(self) -> None:
        self._ui.error_label.set_visible(False)

    def _on_record_toggle_clicked(self, _button: Gtk.Button) -> None:
        self._hide_error_message()

        if self._voice_message_recorder.recording_in_progress:
            self._stop_recording()

            if not self._voice_message_recorder.audio_file_is_valid:
                log.error("Audio file is corrupted")
                return

            self._audio_player_widget.load_audio_file(
                Path(self._voice_message_recorder.audio_file_abspath)
            )
        else:
            # Paused -> Recording
            self._hide_error_message()
            self._ui.send_button.set_sensitive(True)
            self._ui.cancel_button.set_sensitive(True)
            self._show_recording_box()
            self._start_recording()

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self._stop_and_reset_recording()
        self._ui.popover.popdown()

    def _on_direct_record_pressed(self, _x: float, _y: float, _user_data: Any) -> None:
        self._mic_button_long_pressed = True
        self._ui.popover.set_autohide(False)
        self._hide_recording_controls()
        self._show_recording_box()
        self._ui.popover.set_visible(True)
        self._start_recording()

    def _on_direct_record_long_press_end(self, _x: float, _y: float) -> None:
        if self._mic_button_long_pressed:
            self._mic_button_long_pressed = False
            self._ui.popover.set_autohide(True)
            self._mic_button_long_pressed = False
            self._update_icons()
            self._show_recording_controls()
            self._ui.popover.popdown()

    def _on_popover_closed(self, _popover: Gtk.Popover) -> None:
        if not self._voice_message_recorder.recording_time() > 0:
            return

        self._stop_and_reset_recording()
        app.window.activate_action(
            "win.send-file", GLib.Variant("as", [self.audio_rec_file_path])
        )

    def _on_send_clicked(self, _button: Gtk.Button) -> None:
        self._stop_recording()
        app.window.activate_action(
            "win.send-file", GLib.Variant("as", [self.audio_rec_file_path])
        )
