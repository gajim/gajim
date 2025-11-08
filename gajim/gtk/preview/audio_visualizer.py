# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import math
from statistics import mean

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Graphene
from gi.repository import Gsk
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.audio_player import AudioSampleT

log = logging.getLogger("gajim.gtk.preview_audio_visualizer")


class AudioVisualizerWidget(Gtk.Widget):
    def __init__(
        self,
        width: int = 340,
        height: int = 50,
        x_offset: int = 0,
    ) -> None:
        Gtk.Widget.__init__(
            self, margin_start=x_offset, width_request=width, height_request=height
        )

        self._peak_width = 2  # in px
        self._gap_height = 0.25
        self._width = width
        self._height = height
        self._is_LTR = bool(self.get_direction() == Gtk.TextDirection.LTR)

        self._samples: AudioSampleT = []
        self._seek_position = -1.0
        self._position = 0.0
        self._animation_index = 0
        self._animation_period = 1

        self._waveform_path = None

        style_manager = Adw.StyleManager.get_default()
        accent_color = style_manager.get_accent_color_rgba()

        self._color_progress = accent_color

        color_seek = Gdk.RGBA(
            red=accent_color.red * 1.3,
            green=accent_color.green * 1.3,
            blue=accent_color.blue * 1.3,
            alpha=accent_color.alpha,
        )
        self._color_seek = color_seek

        color_default = accent_color.copy()
        color_default.alpha = color_default.alpha - 0.4
        self._color_default = color_default

    def do_unroot(self) -> None:
        Gtk.Widget.do_unroot(self)
        app.check_finalize(self)

    def get_effective_width(self):
        return self._width

    def set_parameters(self, position: float, animation_period: int = 1) -> None:
        self._position = position
        self._animation_period = animation_period

    def set_samples(self, samples: AudioSampleT) -> None:
        if self._is_static():
            samples = self._average_samples(samples)
            samples = self._normalize_samples(samples)
        self._samples = self._rescale_samples(samples)
        self._waveform_path = self._create_waveform_path()

    def render_animated_graph(self, animation_index: int = 0) -> None:
        if not self._samples:
            log.debug("Render animated graph: No samples")
            return

        self._animation_index = animation_index
        self._waveform_path = self._create_waveform_path()
        self.queue_draw()

    def render_static_graph(self, position: float, seek_position: float = -1.0) -> None:
        if not self._samples:
            return

        self._position = position
        self._seek_position = seek_position
        self.queue_draw()

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        if self._waveform_path is None:
            log.debug("Waveform Path is None")
            return

        if not self._is_LTR:
            # rotate 180° around the center
            snapshot.translate(Graphene.Point().init(self._width / 2, self._height / 2))
            snapshot.rotate(180)
            snapshot.translate(
                Graphene.Point().init(-self._width / 2, -self._height / 2)
            )

        play_pos = self._pixel_pos(self._position)

        # Default
        snapshot.push_clip(Graphene.Rect().init(0, 0, self._width, self._height))
        snapshot.append_fill(
            self._waveform_path, Gsk.FillRule.WINDING, self._color_default
        )
        snapshot.pop()

        # Progress
        snapshot.push_clip(Graphene.Rect().init(0, 0, play_pos, self._height))
        snapshot.append_fill(
            self._waveform_path, Gsk.FillRule.WINDING, self._color_progress
        )
        snapshot.pop()

        # Seek
        if self._seek_position >= 0:
            seek_pos = self._pixel_pos(self._seek_position)
            start_seek = min(play_pos, seek_pos)
            end_seek = max(play_pos, seek_pos)
            width_seek = end_seek - start_seek

            snapshot.push_clip(
                Graphene.Rect().init(start_seek, 0, width_seek, self._height)
            )
            snapshot.append_fill(
                self._waveform_path, Gsk.FillRule.WINDING, self._color_seek
            )
            snapshot.pop()

    def _is_static(self):
        return self._animation_period == 1

    def _average_samples(self, samples: AudioSampleT) -> AudioSampleT:
        # Create a subset by taking the average of three samples
        # around every nth sample
        num_divisions = int(self._width / (self._peak_width * 2))

        if num_divisions == 0:
            log.error("Number of divisions is zero")
            return []

        n = math.floor(len(samples) / num_divisions) + 1

        if n < 2:
            return samples

        samples_averaged: AudioSampleT = []
        samples1, samples2 = zip(*samples, strict=True)
        for i in range(2, int(len(samples) - n / 2), n):
            index = int(i + n / 2)
            avg1 = mean(samples1[index - 1 : index + 1])
            avg2 = mean(samples2[index - 1 : index + 1])
            samples_averaged.append((avg1, avg2))
        return samples_averaged

    def _normalize_samples(self, samples: AudioSampleT) -> AudioSampleT:
        if not samples:
            log.error("No samples")
            return []

        # Normalize both channels using the same scale
        max_elem = max(max(samples))  # noqa: PLW3301
        min_elem = min(min(samples))  # noqa: PLW3301
        delta = max_elem - min_elem
        if delta > 0:
            samples_normalized = [
                ((val1 - min_elem) / delta, (val2 - min_elem) / delta)
                for val1, val2 in samples
            ]
            return samples_normalized
        else:
            return samples

    def _rescale_samples(self, samples: AudioSampleT):
        """
        Recorded volume is perceived louder than the visual pretends.
        Therefore, rescale lower peaks bit. The sin(sqrt) function is
        a bit steeper than a shifted and normalized log function.
        """
        samples_rescaled = [
            (
                math.sin(math.sqrt(math.fabs(val1))) / math.sin(1),
                math.sin(math.sqrt(math.fabs(val2))) / math.sin(1),
            )
            for val1, val2 in samples
        ]
        return samples_rescaled

    def _pixel_pos(self, pos: float) -> float:
        return pos * self._width

    def _create_waveform_path(self) -> Gsk.Path | None:
        if not self._samples:
            return None

        peak_width = self._peak_width

        # determines the spacing between the amplitudes
        x_shift = (self._width - 2 * peak_width) / len(self._samples)
        x_shift_anime = x_shift * self._animation_index / self._animation_period
        x = x_shift - x_shift_anime

        path_builder = Gsk.PathBuilder.new()
        for i in range(len(self._samples)):
            sample1 = self._samples[i][0]
            sample2 = self._samples[i][1]

            rounded_rec = self._rounded_rec(
                x,
                self._height / 2,
                peak_width,
                sample1,
                sample2,
            )
            path_builder.add_path(rounded_rec)
            x += x_shift

        return path_builder.to_path()

    def _rounded_rec(
        self,
        x: float,
        y: float,
        width: float,
        height1: float,
        height2: float,
    ) -> Gsk.Path:

        # Don't insert a gap if bars are too small
        if height1 + height2 < 3 or not self._is_static():
            gap = 0.0
        else:
            gap = self._gap_height  # between upper and lower peak in pixels

        radius = 1  # radius of the arcs on top and bottom of the amplitudes
        scaling = self._height / 2 - radius - gap / 2  # peak scaling factor

        # Set a minimum height to improve visibility for quasi silence
        height1 = max(0.5, height1 * scaling)
        height2 = max(0.5, height2 * scaling)

        # Draws a rectangle of width w and total height of h1+h2
        # The top and bottom edges are curved to the outside
        # A --- B --- C
        # |           |
        # F --- E --- D

        # Up
        # A -- B -- C
        pb = Gsk.PathBuilder.new()

        pb.move_to(x, y + height1)
        pb.conic_to(x + width / 2, y + height1 + width / 2, x + width, y + height1, 30)
        # C -- D
        pb.line_to(x + width, y + gap)
        # D -- F
        pb.line_to(x, y + gap)
        # F -- A
        pb.line_to(x, y + height1)
        pb.close()

        # Down
        # C -- D
        pb.move_to(x + width, y - gap)
        pb.line_to(x + width, y - height2)
        # D -- E -- F
        pb.conic_to(x + width / 2, y - height2 - width / 2, x, y - height2, 30)
        # F -- A
        pb.line_to(x, y - gap)
        # A -- C
        pb.line_to(x + width, y - gap)
        pb.close()

        return pb.to_path()
