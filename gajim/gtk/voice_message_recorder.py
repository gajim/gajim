# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

import datetime
import logging
import math
import sys
import wave
from collections import deque
from collections.abc import Callable
from pathlib import Path

from gi.repository import GObject

from gajim.common import app
from gajim.common import configpaths
from gajim.common.i18n import _

try:
    from gi.repository import Gst
except Exception:
    if TYPE_CHECKING:
        from gi.repository import Gst

log = logging.getLogger("gajim.gtk.voice_message_recorder")

WAV_SILENCE_START_ENABLED = True

GST_ERROR_ON_START = 0
GST_ERROR_ON_RECORDING = 1
GST_ERROR_ON_STOP = 2
GST_ERROR_ON_MERGING = 3


class VoiceMessageRecorder(GObject.GObject):
    __gtype_name__ = "VoiceMessageRecorder"

    def __init__(self, error_callback: Callable[[int, str], None]) -> None:
        GObject.GObject.__init__(self)
        self._available = True
        self._error_callback = error_callback

        # Recording state
        self._new_recording = True
        self._output_file_counter = 0
        self._output_file_valid = False
        self._output_files_invalid: list[int] = []
        self._num_samples = 80
        self._samples: deque[float] = deque(
            [0.0] * self._num_samples, maxlen=self._num_samples
        )
        self._current_peak: float = 0.0
        self._noise_floor_db: float = -45.0
        self._floor_samples: list[float] = []
        self._floor_established: bool = False
        self._recent_db: deque[float] = deque(maxlen=500)
        self._rec_time = {"start": 0, "total": 0}

        app.settings.connect_signal(
            "audio_input_device", self._on_audio_input_device_changed
        )

        # Voice message storage location
        self._filetype = "m4a"
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self._file_name = f"voice-message-{timestamp}.{self._filetype}"
        self._file_path = configpaths.get_temp_dir() / self._file_name

        self._init_pipeline()

    def _init_pipeline(self) -> None:
        log.debug("Setting up pipeline")

        self._pipeline = Gst.Pipeline.new("pipeline")
        self._queue = Gst.ElementFactory.make("queue")
        audioconvert = Gst.ElementFactory.make("audioconvert")
        audioresample = Gst.ElementFactory.make("audioresample")
        audiolevel = Gst.ElementFactory.make("level")
        capsfilt = Gst.ElementFactory.make("capsfilter")
        wavenc = Gst.ElementFactory.make("wavenc")
        self._filesink = Gst.ElementFactory.make("filesink")

        pipeline_elements = [
            self._pipeline,
            self._queue,
            audioconvert,
            audioresample,
            audiolevel,
            capsfilt,
            wavenc,
            self._filesink,
        ]

        if any(element is None for element in pipeline_elements):
            raise Exception("Error while setting up pipeline")

        assert self._pipeline is not None
        assert self._queue is not None
        assert audioconvert is not None
        assert audioresample is not None
        assert audiolevel is not None
        assert capsfilt is not None
        assert wavenc is not None
        assert self._filesink is not None

        audiolevel.set_property("message", True)
        audiolevel.set_property("interval", 10 * 1_000_000)  # 10 ms in nanoseconds
        # Force S16LE so wavenc writes standard integer PCM (format 1)
        capsfilt.set_property("caps", Gst.Caps.from_string("audio/x-raw,format=S16LE"))
        self._filesink.set_property("location", str(self._file_path))
        self._filesink.set_property("async", False)

        self._pipeline.add(self._queue)
        self._pipeline.add(audioconvert)
        self._pipeline.add(audioresample)
        self._pipeline.add(audiolevel)
        self._pipeline.add(capsfilt)
        self._pipeline.add(wavenc)
        self._pipeline.add(self._filesink)

        self._queue.link(audioconvert)
        audioconvert.link(audioresample)
        audioresample.link(audiolevel)
        audiolevel.link(capsfilt)
        capsfilt.link(wavenc)
        wavenc.link(self._filesink)

        self._clock: Gst.Clock | None = None

        self._bus = self._pipeline.get_bus()
        self._bus.add_signal_watch()
        self._id = self._bus.connect("message", self._on_gst_message)

        self._audiosrc = self._create_new_audio_src()
        if self._audiosrc is not None:
            self._pipeline.add(self._audiosrc)
            self._audiosrc.link(self._queue)

        self._available = self._audiosrc is not None
        self.notify("available")

    @GObject.Property(type=bool, default=True, flags=GObject.ParamFlags.READABLE)
    def available(self) -> bool:
        return self._available

    def _set_property_available(self, value: bool) -> None:
        if value == self._available:
            return
        self._available = value
        self.notify("available")

    @property
    def recording_in_progress(self) -> bool:
        _, pipeline_state, _ = self._pipeline.get_state(timeout=100)
        return pipeline_state != Gst.State.NULL

    @property
    def audio_file_is_valid(self) -> bool:
        return self._output_file_valid

    @property
    def audio_file_abspath(self) -> Path:
        return self._file_path

    @property
    def audio_file_uri(self) -> str:
        uri = self._file_path.as_uri()
        assert uri is not None
        return uri

    def cleanup(self) -> None:
        del self._error_callback
        self._file_path.unlink(missing_ok=True)
        self._pipeline.get_bus().disconnect(self._id)

    def start_recording(self) -> None:
        assert self._filesink is not None

        if self._new_recording:
            self._new_recording = False
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            self._file_name = f"voice-message-{timestamp}.{self._filetype}"
            self._file_path = configpaths.get_temp_dir() / self._file_name

        if not self._file_path.parent.exists():
            self._handle_error_output_dir_inaccessible()
            return

        self._output_file_counter += 1
        self._filesink.set_property(
            "location", f"{self._file_path}.part{self._output_file_counter}"
        )
        log.debug(
            "Creating new recording file: %s", self._filesink.get_property("location")
        )
        self._pipeline.set_state(Gst.State.PLAYING)
        message = self._pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
        if message is not None:
            self._handle_error_on_start(message)
        self._clock = self._pipeline.get_pipeline_clock()
        self._rec_time["start"] = self._clock.get_time()

    def stop_recording(self) -> None:
        if not self.recording_in_progress:
            return

        assert self._clock is not None

        self._rec_time["total"] += self._clock.get_time() - self._rec_time["start"]

        self._pipeline.send_event(Gst.Event.new_eos())
        message = self._pipeline.get_bus().timed_pop_filtered(
            Gst.CLOCK_TIME_NONE, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        self._pipeline.set_state(Gst.State.NULL)
        assert message is not None
        self._handle_error_on_stop(message)

        self._merge_output_files()

    def stop_and_reset(self) -> None:
        if self.recording_in_progress:
            self.stop_recording()

        self._new_recording = True
        self._output_file_valid = False
        self._output_file_counter = 0
        self._output_files_invalid = []
        self._samples = deque([0] * self._num_samples, maxlen=self._num_samples)
        self._current_peak = 0.0
        self._noise_floor_db = -45.0
        self._floor_samples = []
        self._floor_established = False
        self._recent_db.clear()
        self._rec_time = {"start": 0, "total": 0}

    def cancel_recording(self) -> None:
        # Immediately abort without draining EOS or merging files, so short taps
        # that triggered an early pipeline start don't block the main thread.
        self._pipeline.set_state(Gst.State.NULL)
        self._new_recording = True
        self._output_file_valid = False
        self._output_file_counter = 0
        self._output_files_invalid = []
        self._samples = deque([0] * self._num_samples, maxlen=self._num_samples)
        self._current_peak = 0.0
        self._noise_floor_db = -45.0
        self._floor_samples = []
        self._floor_established = False
        self._recent_db.clear()
        self._rec_time = {"start": 0, "total": 0}

    def recording_time(self) -> int:
        delta = 0
        if self.recording_in_progress and self._clock is not None:
            delta = self._clock.get_time() - self._rec_time["start"]
        return self._rec_time["total"] + delta

    def request_new_sample(self) -> None:
        peak = self._current_peak
        self._current_peak = 0.0
        prev = self._samples[0] if self._samples else 0.0
        # Release envelope: decay rather than hard-cut to zero on silence
        released = prev * 0.5
        self._samples.appendleft(max(peak, released))

    def _normalize_peak_db(self, peak_db: float) -> float:
        self._recent_db.append(peak_db)

        if not self._floor_established:
            self._floor_samples.append(peak_db)
            if len(self._floor_samples) >= 5:  # 5 × 10 ms = 50 ms
                self._noise_floor_db = sum(self._floor_samples) / len(
                    self._floor_samples
                )
                self._floor_established = True
            return 0.0
        elif len(self._recent_db) >= 50:
            sorted_levels = sorted(self._recent_db)
            idx = int(len(sorted_levels) * 0.10)
            floor_estimate = sorted_levels[idx]
            # Very slow EMA so the floor never visibly shifts during recording
            self._noise_floor_db = self._noise_floor_db * 0.999 + floor_estimate * 0.001

        adjusted = peak_db - self._noise_floor_db - 3.0
        if adjusted <= 0.0:
            return 0.0

        value = min(1.0, adjusted / 50.0)
        return math.sqrt(value)

    def recording_samples(self) -> list[tuple[float, float]]:
        sample_list = reversed(list(self._samples))
        result: list[tuple[float, float]] = []
        for sample in sample_list:
            result.append((sample, sample))
        return result

    def _is_error(self, message: Gst.Message | None) -> bool:
        if message is not None and message.type == Gst.MessageType.ERROR:
            self._log_error(message)
            return True
        return False

    def _log_error(self, message: Gst.Message | None) -> None:
        if message is None:
            return

        structure = message.get_structure()
        if structure is not None:
            gerror = structure.get_value("gerror")
            debug = structure.get_value("debug")

            assert gerror is not None
            log.error("gerror code: %s", gerror.code)
            log.error("gerror domain: %s", gerror.domain)
            log.error("debug: %s", debug)

    def _error_info(self, message: Gst.Message | None) -> tuple[str | None, int | None]:
        if message is None:
            return None, None
        structure = message.get_structure()
        assert structure is not None
        gerror = structure.get_value("gerror")
        assert gerror is not None
        return gerror.domain, gerror.code

    def _handle_error_on_start(self, message: Gst.Message) -> None:
        assert message is not None
        if not self._is_error(message):
            return

        log.error("Error on starting the recording.")
        self._output_files_invalid.append(self._output_file_counter)

        domain, code = self._error_info(message)
        if domain == "gst-resource-error-quark":
            if code == 5:
                # GST_RESOURCE_ERROR_OPEN_READ (5)
                # used when resource fails to open for reading.
                self._error_callback(
                    GST_ERROR_ON_START, _("Is a microphone plugged in and accessible?")
                )

    def _handle_error_on_recording(self, message: Gst.Message | None):
        if message is not None and not self._is_error(message):
            return

        log.error("Error during the recording.")
        self._output_files_invalid.append(self._output_file_counter)

        domain, code = self._error_info(message)
        if domain == "gst-resource-error-quark":
            if code == 9:
                # GST_RESOURCE_ERROR_READ (9)
                # used when the resource can't be read from.
                self._error_callback(
                    GST_ERROR_ON_RECORDING,
                    _("Is a microphone plugged in and accessible?"),
                )

        if domain == "gst-stream-error-quark":
            if code == 1:
                # GST_STREAM_ERROR_FAILED (1)
                # a general error which doesn't fit in any other category.
                # Make sure you add a custom message to the error call.
                self._error_callback(
                    GST_ERROR_ON_RECORDING, _("Error in audio data stream.")
                )

    def _handle_error_on_stop(self, message: Gst.Message | None) -> None:
        if message is not None and not self._is_error(message):
            return
        # TODO
        log.error("Error when stopping the recording.")

    def _handle_error_on_merging(self, message: Gst.Message | None) -> None:
        if message is not None and not self._is_error(message):
            return

        # TODO
        log.error("Error when merging the recordings.")

    def _handle_error_output_dir_inaccessible(self) -> None:
        log.error(
            "Voice message lost. Temporary output folder %s not accessible",
            self._file_path.parent,
        )
        error_message = _("Voice message could not be saved. Please try again.")
        self._error_callback(GST_ERROR_ON_MERGING, error_message)
        self.stop_and_reset()

    def _on_gst_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        structure = message.get_structure()
        if structure is None:
            return
        message_string = structure.to_string()

        if message.type == Gst.MessageType.ELEMENT:
            name = structure.get_name()
            if name == "level":
                if not structure.has_field("peak"):
                    return

                peak_values = structure.get_value("peak")
                assert peak_values is not None
                if len(peak_values) > 0:
                    peak_db = float(peak_values[0])
                    if not math.isinf(peak_db) and peak_db > -90.0:
                        normalized = self._normalize_peak_db(peak_db)
                        self._current_peak = max(self._current_peak, normalized)
            log.debug("gst element message: %s", message_string)

        elif message.type == Gst.MessageType.ERROR:
            self._handle_error_on_recording(message)

        elif message.type == Gst.MessageType.EOS:
            pass

    def _switch_sources(self) -> None:
        assert self._queue is not None
        assert not self.recording_in_progress

        if self._audiosrc is not None:
            self._audiosrc.unlink(self._queue)
            self._pipeline.remove(self._audiosrc)

        self._audiosrc = self._create_new_audio_src()
        if self._audiosrc is not None:
            self._pipeline.add(self._audiosrc)
            self._audiosrc.link(self._queue)

        self._available = self._audiosrc is not None
        self.notify("available")

    def _create_new_audio_src(self) -> Gst.Element | None:
        device = self._extract_first_word(app.settings.get("audio_input_device"))

        if sys.platform == "win32" and device == "autoaudiosrc":
            device = "wasapisrc"

        if device == "audiotestsrc":
            log.error('Audio device "audiotestsrc" not supported')
            return None

        audiosrc = Gst.ElementFactory.make(device)
        if audiosrc is None:
            log.debug("Unable to create audio source for: %s", device)
        else:
            log.debug("Created audio source for: %s", device)
            if device == "wasapisrc":
                audiosrc.set_property("role", "comms")

        return audiosrc

    def _on_audio_input_device_changed(self, device: str, *args: Any) -> None:
        log.debug("Switching to input device: %s", device)
        self._switch_sources()

    def _file_merge_required(self) -> bool:
        return self._output_file_counter > 1

    def _smooth_wav_boundaries(
        self, file_path: Path, silence_ms: int = 20, fade_ms: int = 30
    ) -> None:
        try:
            with wave.open(str(file_path), "rb") as wav_in:
                params = wav_in.getparams()
                frames = wav_in.readframes(params.nframes)
        except Exception as e:
            log.warning("Skipping boundary smoothing for %s: %s", file_path, e)
            return

        n_channels = params.nchannels
        sampwidth = params.sampwidth
        n_frames = params.nframes
        framerate = params.framerate

        silence_frames = min(int(framerate * silence_ms / 1000), n_frames)
        fade_frames = min(int(framerate * fade_ms / 1000), n_frames - silence_frames)

        buf = bytearray(frames)

        # Zero the initial silence region
        silence_bytes = silence_frames * n_channels * sampwidth
        buf[:silence_bytes] = b"\x00" * silence_bytes

        if sampwidth == 2:
            # Fade-in after the silence to avoid a step discontinuity at the start
            for i in range(fade_frames):
                factor = i / fade_frames
                frame_start = (silence_frames + i) * n_channels * sampwidth
                for ch in range(n_channels):
                    offset = frame_start + ch * sampwidth
                    value = int.from_bytes(
                        buf[offset : offset + 2], "little", signed=True
                    )
                    buf[offset : offset + 2] = int(value * factor).to_bytes(
                        2, "little", signed=True
                    )

            # Fade-out at the end to avoid a step discontinuity at the merge point
            fade_out_frames = min(int(framerate * fade_ms / 1000), n_frames)
            for i in range(fade_out_frames):
                factor = i / fade_out_frames
                frame_start = (n_frames - 1 - i) * n_channels * sampwidth
                for ch in range(n_channels):
                    offset = frame_start + ch * sampwidth
                    value = int.from_bytes(
                        buf[offset : offset + 2], "little", signed=True
                    )
                    buf[offset : offset + 2] = int(value * factor).to_bytes(
                        2, "little", signed=True
                    )

        with wave.open(str(file_path), "wb") as wav_out:
            wav_out.setparams(params)
            wav_out.writeframes(bytes(buf))

    def _build_merge_command(self) -> str:
        log.info("Merging WAV files started")

        # Use as_posix() on file path to convert "\" to "/" on Windows
        sources = ""
        for i in range(1, self._output_file_counter + 1):
            if i in self._output_files_invalid:
                continue
            source = " ! ".join(
                [
                    f"filesrc location={self._file_path.as_posix()}.part{i}",
                    "wavparse",
                    "audioconvert",
                    "audioresample",
                    "c. ",
                ]
            )
            sources += source

        command = " ! ".join(
            [
                "concat name=c",
                "queue",
                "audioconvert",
                "audioresample",
                "opusenc audio-type=voice bitrate=32000",
                "mp4mux ",
                f"filesink location={self._file_path.as_posix()} {sources}",
            ]
        )
        return command

    def _merge_output_files(self) -> None:
        if not self._file_path.parent.exists():
            self._handle_error_output_dir_inaccessible()
            return

        for i in range(1, self._output_file_counter + 1):
            if i in self._output_files_invalid:
                continue
            part_path = Path(f"{self._file_path}.part{i}")
            if WAV_SILENCE_START_ENABLED:
                self._smooth_wav_boundaries(part_path)

        command = self._build_merge_command()
        pipeline = Gst.parse_launch(command)

        # Remove the original output file first before writing into it
        if self._file_path.exists():
            self._file_path.unlink()

        pipeline.set_state(Gst.State.PLAYING)

        bus = pipeline.get_bus()
        if bus is None:
            return

        message = bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        pipeline.set_state(Gst.State.NULL)

        self._handle_error_on_merging(message)
        self._output_file_valid = True
        log.debug("Merging files finished")

    @staticmethod
    def _extract_first_word(gst_cmd: str) -> str:
        """
        Gajim gives us a string with an audio src plus additional parameters
        such as volume. This method takes only the first word == audio src.
        """
        if " " in gst_cmd:
            idx = gst_cmd.index(" ")
            gst_cmd = gst_cmd[:idx]
        return gst_cmd
