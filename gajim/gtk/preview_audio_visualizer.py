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
import cairo
import math
from statistics import mean

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
                 seek_bar_color: Gdk.RGBA
                 ) -> None:

        Gtk.DrawingArea.__init__(self)

        self._x_offset = x_offset
        self._width = width
        self._height = height
        self._is_LTR = (self.get_direction() == Gtk.TextDirection.LTR)
        self._amplitude_width = 2

        self._num_samples = 0
        self._samples: AudioSampleT = []
        self._seek_position = -1.0
        self._position = 0.0

        self._default_color = (0.6, 0.6, 0.6)  # gray
        self._progress_color = rgba_to_float(seek_bar_color)

        # Use a 50% lighter color to the seeking indicator
        self._seek_color = tuple(
            min(1.0, color * 1.5) for color in self._progress_color
        )

        self._surface: Optional[cairo.ImageSurface] = None

        self.set_size_request(self._width, self._height)

        self.connect('draw', self._on_drawingarea_draw)
        self.connect('configure-event', self._on_drawingarea_changed)

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
        # Pick a subset of all samples and average over three samples
        w = int(self._width / (self._amplitude_width * 2))
        n = math.floor(len(self._samples) / w) + 1

        if n >= 2:
            samples: AudioSampleT = []
            samples1, samples2 = zip(*self._samples)
            for i in range(2, int(len(self._samples) - n / 2), n):
                index = int(i + n / 2)
                avg1 = mean(samples1[index - 1:index + 1])
                avg2 = mean(samples2[index - 1:index + 1])
                samples.append((avg1, avg2))
        else:
            samples = self._samples

        # Normalize both channels using the same scale
        max_elem = max(max(samples))
        self._samples = [
            (val1 / max_elem, val2 / max_elem) for val1, val2 in samples
        ]

    def _draw_surface(self, ctx: cairo.Context[cairo.ImageSurface]) -> None:
        # First draw the progress part from left
        end = min(round(self._position * self._num_samples), self._num_samples)
        self._draw_rms_amplitudes(ctx,
                                  start=0,
                                  end=end,
                                  color=self._progress_color)

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
                                      color=self._seek_color)

        # Draw the default amplitudes for the rest of the timeline
        play_pos = min(round(
            self._position * self._num_samples), self._num_samples)
        seek_pos = min(round(
            self._seek_position * self._num_samples), self._num_samples)
        start_default = max(play_pos, seek_pos)

        self._draw_rms_amplitudes(ctx,
                                  start=start_default,
                                  end=self._num_samples,
                                  color=self._default_color)

    def _draw_rms_amplitudes(self,
                             ctx: cairo.Context[cairo.ImageSurface],
                             start: int,
                             end: int,
                             color: tuple[float, float, float]
                             ) -> None:

        ctx.set_source_rgb(*color)

        w = self._amplitude_width

        # determines the spacing between the amplitudes
        o = (self._width - 2 * w) / self._num_samples
        y = self._height / 2
        r = 1  # radius of the arcs on top and bottom of the amplitudes
        s = self._height / 2 - r  # amplitude scaling factor

        if self._is_LTR:
            o = (self._width - 2 * w) / self._num_samples
            x = self._x_offset + o * (start + 1)
        else:
            o = -(self._width - 2 * w) / self._num_samples
            x = -o * (self._num_samples - start) + self._x_offset

        for i in range(start, end):
            # Ensure that no empty area is drawn,
            # thus use a minimum sample value

            if self._is_LTR:
                sample1 = max(0.05, self._samples[i][0])
                sample2 = max(0.05, self._samples[i][1])
            else:
                sample1 = max(0.05, self._samples[i][1])
                sample2 = max(0.05, self._samples[i][0])

            self._draw_rounded_rec2(ctx, x, y, w, sample1 * s, sample2 * s, r)
            ctx.fill()
            x += o

    def _on_drawingarea_draw(self,
                             _drawing_area: Gtk.DrawingArea,
                             ctx: cairo.Context[cairo.ImageSurface],
                             ) -> None:

        if self._num_samples != 0:
            self._draw_surface(ctx)

    def _on_drawingarea_changed(self,
                                _drawing_area: Gtk.DrawingArea,
                                _event: Gdk.EventConfigure,
                                ) -> None:

        self._is_LTR = (self.get_direction() == Gtk.TextDirection.LTR)
        self._setup_surface()
        self.queue_draw()

    def _draw_rounded_rec2(self,
                           context: cairo.Context[cairo.ImageSurface],
                           x: float,
                           y: float,
                           w: float,
                           h1: float,
                           h2: float,
                           r: float
                           ) -> None:

        '''
        Draws a rectangle of width w and total height of h1+h2
        The top and bottom edges are curved to the outside
        '''
        m = w / 2

        if not self._is_LTR:
            m = -m
            w = -w

        context.curve_to(x, y + h1,
                         x + m, y + h1 + r,
                         x + w, y + h1)

        context.line_to(x + w, y - h2)

        context.curve_to(x + w, y - h2,
                         x + m, y - h2 - r,
                         x, y - h2)

        context.line_to(x, y + h1)
