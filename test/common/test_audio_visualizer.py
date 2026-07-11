# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import math
import unittest
from unittest.mock import MagicMock

from gajim.gtk.preview.audio_visualizer import AudioVisualizerWidget

AudioSampleT = list[tuple[float, float]]


def _make_self(
    width: int = 340,
    height: int = 50,
    bar_width: int = 2,
    live_mode: bool = False,
) -> MagicMock:
    mock = MagicMock()
    mock._width = width
    mock._height = height
    mock._bar_width = bar_width
    mock._live_mode = live_mode
    return mock


def _flat(n: int, v: float = 0.5) -> AudioSampleT:
    return [(v, v)] * n


class TestIsStatic(unittest.TestCase):
    def test_static_when_not_live(self) -> None:
        mock = _make_self(live_mode=False)
        self.assertTrue(AudioVisualizerWidget._is_static.fget(mock))  # type: ignore[attr-defined]

    def test_not_static_in_live_mode(self) -> None:
        mock = _make_self(live_mode=True)
        self.assertFalse(AudioVisualizerWidget._is_static.fget(mock))  # type: ignore[attr-defined]


class TestNormalize(unittest.TestCase):
    def _call(self, samples: AudioSampleT) -> AudioSampleT:
        return AudioVisualizerWidget._normalize(_make_self(), samples)  # pyright: ignore[reportPrivateUsage]

    def test_empty_returns_empty(self) -> None:
        result = self._call([])
        self.assertEqual(result, [])

    def test_all_same_returns_unchanged(self) -> None:
        samples = [(0.5, 0.5), (0.5, 0.5)]
        result = self._call(samples)
        self.assertEqual(result, samples)

    def test_min_maps_to_zero(self) -> None:
        samples = [(0.0, 0.0), (1.0, 1.0)]
        result = self._call(samples)
        self.assertAlmostEqual(result[0][0], 0.0)
        self.assertAlmostEqual(result[0][1], 0.0)

    def test_max_maps_to_one(self) -> None:
        samples = [(0.0, 0.0), (1.0, 1.0)]
        result = self._call(samples)
        self.assertAlmostEqual(result[1][0], 1.0)
        self.assertAlmostEqual(result[1][1], 1.0)

    def test_midpoint_maps_to_half(self) -> None:
        samples = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        result = self._call(samples)
        self.assertAlmostEqual(result[1][0], 0.5)

    def test_all_values_in_range(self) -> None:
        samples = [(0.1, 0.9), (0.3, 0.7), (0.5, 0.5)]
        result = self._call(samples)
        for s1, s2 in result:
            self.assertGreaterEqual(s1, 0.0)
            self.assertLessEqual(s1, 1.0)
            self.assertGreaterEqual(s2, 0.0)
            self.assertLessEqual(s2, 1.0)

    def test_output_length_matches_input(self) -> None:
        samples = [(float(i), float(i)) for i in range(10)]
        result = self._call(samples)
        self.assertEqual(len(result), len(samples))


class TestRescale(unittest.TestCase):
    def _call(self, samples: AudioSampleT) -> AudioSampleT:
        return AudioVisualizerWidget._rescale(_make_self(), samples)  # pyright: ignore[reportPrivateUsage]

    def test_zero_maps_to_zero(self) -> None:
        result = self._call([(0.0, 0.0)])
        self.assertAlmostEqual(result[0][0], 0.0)
        self.assertAlmostEqual(result[0][1], 0.0)

    def test_one_maps_to_one(self) -> None:
        result = self._call([(1.0, 1.0)])
        self.assertAlmostEqual(result[0][0], 1.0, places=5)
        self.assertAlmostEqual(result[0][1], 1.0, places=5)

    def test_all_outputs_in_range(self) -> None:
        samples = [(v / 10, v / 10) for v in range(11)]
        result = self._call(samples)
        for s1, s2 in result:
            self.assertGreaterEqual(s1, 0.0)
            self.assertLessEqual(s1, 1.0)
            self.assertGreaterEqual(s2, 0.0)
            self.assertLessEqual(s2, 1.0)

    def test_monotonically_increasing(self) -> None:
        samples = [(v / 10, v / 10) for v in range(11)]
        result = self._call(samples)
        values = [s1 for s1, _ in result]
        for i in range(len(values) - 1):
            self.assertLessEqual(values[i], values[i + 1])

    def test_applies_sin_sqrt_formula(self) -> None:
        inv_sin1 = 1.0 / math.sin(1)
        v = 0.25
        expected = math.sin(math.sqrt(v)) * inv_sin1
        result = self._call([(v, v)])
        self.assertAlmostEqual(result[0][0], expected, places=10)

    def test_output_length_matches_input(self) -> None:
        result = self._call(_flat(7))
        self.assertEqual(len(result), 7)


class TestDownsample(unittest.TestCase):
    def _call(
        self, samples: AudioSampleT, width: int = 340, bar_width: int = 2
    ) -> AudioSampleT:
        mock = _make_self(width=width, bar_width=bar_width)
        return AudioVisualizerWidget._downsample(mock, samples)  # pyright: ignore[reportPrivateUsage]

    def test_short_input_returned_unchanged(self) -> None:
        # num_bars = 340 / (2*2) = 85; stride < 2 so no downsampling
        samples = _flat(10)
        result = self._call(samples)
        self.assertEqual(result, samples)

    def test_output_shorter_than_input_for_large_input(self) -> None:
        samples = _flat(10000)
        result = self._call(samples)
        self.assertLess(len(result), len(samples))

    def test_output_not_empty_for_large_input(self) -> None:
        samples = _flat(10000)
        result = self._call(samples)
        self.assertGreater(len(result), 0)

    def test_output_fits_display_width(self) -> None:
        width, bar_width = 200, 2
        num_bars = width // (bar_width * 2)
        samples = _flat(10000)
        result = self._call(samples, width=width, bar_width=bar_width)
        # result should be at most num_bars entries
        self.assertLessEqual(len(result), num_bars + 1)

    def test_zero_width_returns_empty(self) -> None:
        result = self._call(_flat(100), width=0)
        self.assertEqual(result, [])

    def test_output_values_are_averages_of_input(self) -> None:
        # All samples identical → downsampled values identical
        v = 0.7
        samples = _flat(5000, v)
        result = self._call(samples)
        for s1, s2 in result:
            self.assertAlmostEqual(s1, v, places=5)
            self.assertAlmostEqual(s2, v, places=5)


class TestPipeline(unittest.TestCase):
    """Integration: normalize → rescale produces valid output from raw data."""

    def _run(self, samples: AudioSampleT) -> AudioSampleT:
        mock = _make_self()
        normalized = AudioVisualizerWidget._normalize(mock, samples)  # pyright: ignore[reportPrivateUsage]
        return AudioVisualizerWidget._rescale(mock, normalized)  # pyright: ignore[reportPrivateUsage]

    def test_uniform_input_stays_in_range(self) -> None:
        result = self._run(_flat(50, 0.3))
        for s1, _s2 in result:
            self.assertGreaterEqual(s1, 0.0)
            self.assertLessEqual(s1, 1.0)

    def test_zero_to_one_ramp_in_range(self) -> None:
        samples = [(i / 99, i / 99) for i in range(100)]
        result = self._run(samples)
        for s1, _s2 in result:
            self.assertGreaterEqual(s1, 0.0)
            self.assertLessEqual(s1, 1.0)


if __name__ == "__main__":
    unittest.main()
