# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Optional

import logging
import math
from statistics import mean

import cairo
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common.preview import AudioSampleT

from .util import rgba_to_float

log = logging.getLogger('gajim.gui.preview_audio_visualizer')


class AudioVisualizerWidget(Gtk.DrawingArea):
    def __init__(self,
                 width: int,
                 height: int,
                 x_offset: int,
                 ) -> None:

        Gtk.DrawingArea.__init__(self)

        self.set_name('AudioVisualizer')
        self._update_colors()
        self._x_offset = x_offset
        self._peak_width = 2  # in px
        self._width = width
        self._height = height
        self._is_LTR = bool(self.get_direction() == Gtk.TextDirection.LTR)

        self._num_samples = 0
        self._samples: AudioSampleT = []
        self._seek_position = -1.0
        self._position = 0.0

        self.connect('draw', self._on_drawingarea_draw)
        self.connect('configure-event', self._on_drawingarea_changed)
        self.connect('style-updated', self._on_style_updated)

        self.set_size_request(self._width, self._height)
        self._surface: Optional[cairo.ImageSurface] = None
        self._setup_surface()

    def update_params(self,
                      samples: AudioSampleT,
                      position: float
                      ) -> None:

        self._samples = samples
        self._position = position
        self._process_samples()
        self._num_samples = len(self._samples)

    def draw_graph(self, position: float, seek_position: float = -1.0) -> None:
        if self._num_samples == 0:
            return

        self._position = position
        self._seek_position = seek_position

        self.queue_draw()

    def _on_drawingarea_draw(self,
                             _drawing_area: Gtk.DrawingArea,
                             ctx: cairo.Context[cairo.ImageSurface]
                             ) -> None:

        if self._num_samples != 0:
            self._draw_surface(ctx)

    def _on_drawingarea_changed(self,
                                _drawing_area: Gtk.DrawingArea,
                                _event: Gdk.EventConfigure
                                ) -> None:

        self._is_LTR = bool(self.get_direction() == Gtk.TextDirection.LTR)
        self._setup_surface()
        self.queue_draw()

    def _on_style_updated(self,
                          _event: Gdk.EventConfigure
                          ) -> None:

        self._update_colors()
        self.queue_draw()

    def _update_colors(self) -> None:
        sc = self.get_style_context()
        self._progress_color = rgba_to_float(
            sc.get_color(Gtk.StateFlags.NORMAL)
        )
        self._default_color = rgba_to_float(
            sc.get_background_color(Gtk.StateFlags.NORMAL)
        )
        self._outline_color = rgba_to_float(
            sc.get_border_color(Gtk.StateFlags.NORMAL)
        )
        self._seek_color = rgba_to_float(
            sc.get_color(Gtk.StateFlags.SELECTED)
        )

    def _setup_surface(self) -> None:
        if self._surface:
            self._surface.finish()

        self._surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32,
            self._width,
            self._height)
        ctx: cairo.Context[cairo.ImageSurface] = cairo.Context(self._surface)

        if self._num_samples != 0:
            self._draw_surface(ctx)

    def _process_samples(self) -> None:
        # Create a subset by taking the average of three samples
        # around every nth sample
        num_divisions = int(self._width / (self._peak_width * 2))
        n = math.floor(len(self._samples) / num_divisions) + 1

        if n >= 2:
            samples: AudioSampleT = []
            samples1, samples2 = zip(*self._samples, strict=True)
            for i in range(2, int(len(self._samples) - n / 2), n):
                index = int(i + n / 2)
                avg1 = mean(samples1[index - 1:index + 1])
                avg2 = mean(samples2[index - 1:index + 1])
                samples.append((avg1, avg2))
        else:
            samples = self._samples

        # Normalize both channels using the same scale
        max_elem = max(max(samples))
        min_elem = min(min(samples))
        delta = max_elem - min_elem
        if delta > 0:
            self._samples = [
                (
                    (val1 - min_elem) / delta,
                    (val2 - min_elem) / delta
                )
                for val1, val2 in samples
            ]
        else:
            self._samples = samples

    def _draw_surface(self, ctx: cairo.Context[cairo.ImageSurface]) -> None:
        # First draw the progress part from left
        end = min(round(self._position * self._num_samples), self._num_samples)
        self._draw_rms_amplitudes(ctx,
                                  start=0,
                                  end=end,
                                  color=self._progress_color
                                  )

        if self._seek_position >= 0:
            # If state is PLAYING and the user seeks, determine whether the
            # seek position lies in the past, i.e. on the left side of current
            # position or in the future, i.e. on the right side.
            # Highlight the skipped area from seek
            # to the current position on the determined site.
            play_pos = min(round(
                self._position * self._num_samples), self._num_samples)
            seek_pos = min(round(
                self._seek_position * self._num_samples), self._num_samples)
            if play_pos > seek_pos:
                start = seek_pos
                end = play_pos
            else:
                start = play_pos
                end = seek_pos

            self._draw_rms_amplitudes(ctx,
                                      start=start,
                                      end=end,
                                      color=self._seek_color
                                      )

        # Draw the default amplitudes for the rest of the timeline
        play_pos = min(round(
            self._position * self._num_samples), self._num_samples)
        seek_pos = min(round(
            self._seek_position * self._num_samples), self._num_samples)
        start_default = max(play_pos, seek_pos)

        self._draw_rms_amplitudes(ctx,
                                  start=start_default,
                                  end=self._num_samples,
                                  color=self._default_color
                                  )

    def _draw_rms_amplitudes(self,
                             ctx: cairo.Context[cairo.ImageSurface],
                             start: int,
                             end: int,
                             color: tuple[float, float, float]
                             ) -> None:
        peak_width = self._peak_width
        radius = 1  # radius of the arcs on top and bottom of the amplitudes
        gap = 0.25  # between upper and lower peak in pixels
        scaling = self._height / 2 - radius - gap / 2  # peak scaling factor
        ctx.set_line_width(1.0)

        if self._is_LTR:
            # determines the spacing between the amplitudes
            x_shift = (self._width - 2 * peak_width) / self._num_samples
            x = self._x_offset + x_shift * (start + 1)
        else:
            x_shift = -(self._width - 2 * peak_width) / self._num_samples
            x = -x_shift * (self._num_samples - start) + self._x_offset

        for i in range(start, end):
            if self._is_LTR:
                sample1 = self._samples[i][0]
                sample2 = self._samples[i][1]
            else:
                sample1 = self._samples[i][1]
                sample2 = self._samples[i][0]

            self._draw_rounded_rec(
                ctx,
                x,
                self._height / 2,
                peak_width,
                sample1 * scaling,
                sample2 * scaling,
                radius,
                gap,
            )

            ctx.set_source_rgb(*self._outline_color)
            ctx.stroke_preserve()

            ctx.set_source_rgb(*color)
            ctx.fill()

            x += x_shift

    def _draw_rounded_rec(self,
                          ctx: cairo.Context[cairo.ImageSurface],
                          x: float,
                          y: float,
                          width: float,
                          height1: float,
                          height2: float,
                          radius: float,
                          gap_size: float,
                          ) -> None:

        # Don't insert a gap if bars are too small
        if height1 + height2 < 3:
            gap_size = 0.0

        # Set a minimum height to improve visibility for quasi silence
        height1 = max(0.5, height1)
        height2 = max(0.5, height2)

        # Draws a rectangle of width w and total height of h1+h2
        # The top and bottom edges are curved to the outside
        m = width / 2
        if not self._is_LTR:
            m = -m
            width = -width

        # A --- B --- C
        # |           |
        # F --- E --- D

        # Up
        # A -- B -- C
        ctx.curve_to(x, y + height1,
                     x + m, y + height1 + radius,
                     x + width, y + height1)
        # C -- D
        ctx.line_to(x + width, y + gap_size)
        # D -- F
        ctx.line_to(x, y + gap_size)
        # F -- A
        ctx.line_to(x, y + height1)

        # Down
        # C -- D
        ctx.move_to(x + width, y - gap_size)
        ctx.line_to(x + width, y - height2)
        # D -- E -- F
        ctx.curve_to(x + width, y - height2,
                     x + m, y - height2 - radius,
                     x, y - height2)
        # F -- A
        ctx.line_to(x, y - gap_size)
        # A -- C
        ctx.line_to(x + width, y - gap_size)
