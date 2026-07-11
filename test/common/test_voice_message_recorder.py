# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock

from gajim.gtk.voice_message_recorder import GST_ERROR_ON_RECORDING
from gajim.gtk.voice_message_recorder import GST_ERROR_ON_START
from gajim.gtk.voice_message_recorder import VoiceMessageRecorder


def _make_wav(
    path: Path,
    n_frames: int = 4800,
    framerate: int = 48000,
    n_channels: int = 1,
    value: int = 16384,
) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(struct.pack(f"<{n_frames * n_channels}h", *([value] * n_frames * n_channels)))


def _read_samples(path: Path) -> list[int]:
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return list(struct.unpack(f"<{len(raw) // 2}h", raw))


class TestExtractFirstWord(unittest.TestCase):
    def test_single_word(self) -> None:
        self.assertEqual(
            VoiceMessageRecorder._extract_first_word("autoaudiosrc"), "autoaudiosrc"
        )

    def test_word_with_parameters(self) -> None:
        self.assertEqual(
            VoiceMessageRecorder._extract_first_word("pulsesrc volume=0.8 device=default"),
            "pulsesrc",
        )

    def test_empty_string(self) -> None:
        self.assertEqual(VoiceMessageRecorder._extract_first_word(""), "")


class TestBuildMergeCommand(unittest.TestCase):
    def _make(self, counter: int, invalids: list[int], path: Path) -> MagicMock:
        mock = MagicMock()
        mock._output_file_counter = counter
        mock._output_files_invalid = invalids
        mock._file_path = path
        return mock

    def test_single_part_contains_required_elements(self) -> None:
        path = Path("/tmp/voice-test.m4a")
        cmd = VoiceMessageRecorder._build_merge_command(self._make(1, [], path))
        self.assertIn(f"location={path.as_posix()}.part1", cmd)
        self.assertIn("wavparse", cmd)
        self.assertIn("opusenc", cmd)
        self.assertIn("mp4mux", cmd)
        self.assertIn(f"location={path.as_posix()} ", cmd)

    def test_multiple_parts_all_included(self) -> None:
        path = Path("/tmp/voice-test.m4a")
        cmd = VoiceMessageRecorder._build_merge_command(self._make(3, [], path))
        for i in (1, 2, 3):
            self.assertIn(f"location={path.as_posix()}.part{i}", cmd)

    def test_invalid_parts_excluded(self) -> None:
        path = Path("/tmp/voice-test.m4a")
        cmd = VoiceMessageRecorder._build_merge_command(self._make(3, [2], path))
        self.assertIn(f"location={path.as_posix()}.part1", cmd)
        self.assertNotIn(f"location={path.as_posix()}.part2", cmd)
        self.assertIn(f"location={path.as_posix()}.part3", cmd)


class TestSmoothWavBoundaries(unittest.TestCase):
    FRAMERATE = 48000
    VALUE = 16384

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._mock_self = MagicMock()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _call(self, path: Path, silence_ms: int = 20, fade_ms: int = 30) -> None:
        VoiceMessageRecorder._smooth_wav_boundaries(self._mock_self, path, silence_ms, fade_ms)

    def _wav_path(self, name: str = "test.wav", n_frames: int = FRAMERATE) -> Path:
        path = self._tmp / name
        _make_wav(path, n_frames=n_frames, framerate=self.FRAMERATE, value=self.VALUE)
        return path

    def test_silence_region_is_zero(self) -> None:
        silence_ms = 20
        path = self._wav_path()
        self._call(path, silence_ms=silence_ms, fade_ms=5)
        samples = _read_samples(path)
        silence_frames = int(self.FRAMERATE * silence_ms / 1000)
        for i in range(silence_frames):
            self.assertEqual(samples[i], 0, f"sample {i} should be zero")

    def test_fade_in_ramps_up_after_silence(self) -> None:
        silence_ms, fade_ms = 20, 30
        path = self._wav_path()
        self._call(path, silence_ms=silence_ms, fade_ms=fade_ms)
        samples = _read_samples(path)
        silence_frames = int(self.FRAMERATE * silence_ms / 1000)
        fade_frames = int(self.FRAMERATE * fade_ms / 1000)
        # First fade sample ≈ 0, last fade sample ≈ full value
        self.assertAlmostEqual(samples[silence_frames], 0, delta=100)
        self.assertAlmostEqual(
            samples[silence_frames + fade_frames - 1], self.VALUE, delta=200
        )
        # Each sample must be >= the previous one (monotonically increasing)
        for i in range(silence_frames, silence_frames + fade_frames - 1):
            self.assertLessEqual(samples[i], samples[i + 1])

    def test_fade_out_ramps_down_at_end(self) -> None:
        silence_ms, fade_ms = 20, 30
        path = self._wav_path()
        self._call(path, silence_ms=silence_ms, fade_ms=fade_ms)
        samples = _read_samples(path)
        fade_frames = int(self.FRAMERATE * fade_ms / 1000)
        n = len(samples)
        # Last sample ≈ 0, first sample of fade-out ≈ full value
        self.assertAlmostEqual(samples[-1], 0, delta=100)
        self.assertAlmostEqual(samples[n - fade_frames], self.VALUE, delta=200)
        # Each sample must be <= the previous one (monotonically decreasing)
        for i in range(n - fade_frames, n - 1):
            self.assertGreaterEqual(samples[i], samples[i + 1])

    def test_middle_section_unchanged(self) -> None:
        silence_ms, fade_ms = 20, 30
        n_frames = self.FRAMERATE
        path = self._wav_path(n_frames=n_frames)
        self._call(path, silence_ms=silence_ms, fade_ms=fade_ms)
        samples = _read_samples(path)
        silence_frames = int(self.FRAMERATE * silence_ms / 1000)
        fade_frames = int(self.FRAMERATE * fade_ms / 1000)
        mid_start = silence_frames + fade_frames
        mid_end = n_frames - fade_frames
        for i in range(mid_start, mid_end):
            self.assertEqual(samples[i], self.VALUE, f"sample {i} should be unchanged")

    def test_stereo_both_channels_processed(self) -> None:
        silence_ms, fade_ms = 20, 10
        path = self._tmp / "stereo.wav"
        _make_wav(path, framerate=self.FRAMERATE, n_channels=2, value=self.VALUE)
        self._call(path, silence_ms=silence_ms, fade_ms=fade_ms)
        samples = _read_samples(path)
        silence_frames = int(self.FRAMERATE * silence_ms / 1000)
        # Both channels (interleaved) should be zero in silence region
        for i in range(silence_frames * 2):
            self.assertEqual(samples[i], 0, f"stereo sample {i} should be zero")

    def test_missing_file_does_not_raise(self) -> None:
        self._call(self._tmp / "nonexistent.wav")

    def test_output_is_valid_wav(self) -> None:
        path = self._wav_path()
        self._call(path)
        with wave.open(str(path), "rb") as w:
            self.assertEqual(w.getsampwidth(), 2)
            self.assertEqual(w.getnframes(), self.FRAMERATE)


def _make_error_self(counter: int = 1) -> MagicMock:
    mock = MagicMock()
    mock._output_file_counter = counter
    mock._output_files_invalid = []
    return mock


class TestHandleErrorOnStart(unittest.TestCase):
    def test_microphone_inaccessible_fires_callback(self) -> None:
        mock_self = _make_error_self()
        mock_self._is_error.return_value = True
        mock_self._error_info.return_value = ("gst-resource-error-quark", 5)
        error_cb = MagicMock()
        mock_self._error_callback = error_cb

        VoiceMessageRecorder._handle_error_on_start(mock_self, MagicMock())

        error_cb.assert_called_once()
        kind, msg = error_cb.call_args[0]
        self.assertEqual(kind, GST_ERROR_ON_START)
        self.assertIn("microphone", msg.lower())

    def test_marks_current_file_invalid(self) -> None:
        mock_self = _make_error_self(counter=3)
        mock_self._is_error.return_value = True
        mock_self._error_info.return_value = ("gst-resource-error-quark", 5)

        VoiceMessageRecorder._handle_error_on_start(mock_self, MagicMock())

        self.assertIn(3, mock_self._output_files_invalid)

    def test_non_error_message_is_ignored(self) -> None:
        mock_self = _make_error_self()
        mock_self._is_error.return_value = False
        error_cb = MagicMock()
        mock_self._error_callback = error_cb

        VoiceMessageRecorder._handle_error_on_start(mock_self, MagicMock())

        error_cb.assert_not_called()
        self.assertEqual(mock_self._output_files_invalid, [])

    def test_unknown_error_code_marks_invalid_but_no_callback(self) -> None:
        mock_self = _make_error_self()
        mock_self._is_error.return_value = True
        mock_self._error_info.return_value = ("gst-resource-error-quark", 99)
        error_cb = MagicMock()
        mock_self._error_callback = error_cb

        VoiceMessageRecorder._handle_error_on_start(mock_self, MagicMock())

        self.assertIn(1, mock_self._output_files_invalid)
        error_cb.assert_not_called()


class TestHandleErrorOnRecording(unittest.TestCase):
    def test_microphone_disconnected_fires_callback(self) -> None:
        mock_self = _make_error_self()
        mock_self._is_error.return_value = True
        mock_self._error_info.return_value = ("gst-resource-error-quark", 9)
        error_cb = MagicMock()
        mock_self._error_callback = error_cb

        VoiceMessageRecorder._handle_error_on_recording(mock_self, MagicMock())

        error_cb.assert_called_once()
        kind, msg = error_cb.call_args[0]
        self.assertEqual(kind, GST_ERROR_ON_RECORDING)
        self.assertIn("microphone", msg.lower())

    def test_stream_error_fires_callback(self) -> None:
        mock_self = _make_error_self()
        mock_self._is_error.return_value = True
        mock_self._error_info.return_value = ("gst-stream-error-quark", 1)
        error_cb = MagicMock()
        mock_self._error_callback = error_cb

        VoiceMessageRecorder._handle_error_on_recording(mock_self, MagicMock())

        error_cb.assert_called_once()
        kind, _ = error_cb.call_args[0]
        self.assertEqual(kind, GST_ERROR_ON_RECORDING)

    def test_marks_current_file_invalid(self) -> None:
        mock_self = _make_error_self(counter=2)
        mock_self._is_error.return_value = True
        mock_self._error_info.return_value = ("gst-resource-error-quark", 9)

        VoiceMessageRecorder._handle_error_on_recording(mock_self, MagicMock())

        self.assertIn(2, mock_self._output_files_invalid)

    def test_none_message_still_marks_invalid(self) -> None:
        # message=None means the pipeline itself reported an error without a message object
        mock_self = _make_error_self()
        mock_self._error_info.return_value = (None, None)

        VoiceMessageRecorder._handle_error_on_recording(mock_self, None)

        self.assertIn(1, mock_self._output_files_invalid)

    def test_non_error_message_is_ignored(self) -> None:
        mock_self = _make_error_self()
        mock_self._is_error.return_value = False
        error_cb = MagicMock()
        mock_self._error_callback = error_cb

        VoiceMessageRecorder._handle_error_on_recording(mock_self, MagicMock())

        error_cb.assert_not_called()
        self.assertEqual(mock_self._output_files_invalid, [])


if __name__ == "__main__":
    unittest.main()
