# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import math
from statistics import mean

import cairo
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common.preview import AudioSampleT

log = logging.getLogger('gajim.gtk.preview_audio_visualizer')


class AudioVisualizerWidget(Gtk.DrawingArea):
    def __init__(self,
                 width: int,
                 height: int,
                 x_offset: int,
                 ) -> None:

        Gtk.DrawingArea.__init__(self)

        self._x_offset = x_offset
        self._peak_width = 2  # in px
        self._width = width
        self._height = height
        self._is_LTR = bool(self.get_direction() == Gtk.TextDirection.LTR)

        self._num_samples = 0
        self._samples: AudioSampleT = []
        self._seek_position = -1.0
        self._position = 0.0

        # Add EventMask to receive button press events (for skipping)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        self.connect('draw', self._on_drawingarea_draw)
        self.connect('configure-event', self._on_drawingarea_changed)
        self.connect('style-updated', self._on_style_updated)

        self._style_context = self.get_style_context()
        self._style_context.add_class('audiovisualizer')

        self.set_size_request(self._width, self._height)
        self._surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32,
            self._width,
            self._height)
        self._ctx: cairo.Context[cairo.ImageSurface] = cairo.Context(
            self._surface)
        self._cairo_path = self._ctx.copy_path()

    def update_params(self,
                      samples: AudioSampleT,
                      position: float
                      ) -> None:

        self._samples = samples
        self._position = position
        self._process_samples()
        self._num_samples = len(self._samples)
        self._render_waveform()

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
        self._render_waveform()
        self.queue_draw()

    def _on_style_updated(self,
                          _event: Gdk.EventConfigure
                          ) -> None:
        self.queue_draw()

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
        max_elem = max(max(samples))  # noqa: PLW3301
        min_elem = min(min(samples))  # noqa: PLW3301
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

    def _pixel_pos(self, pos: float) -> float:
        return pos * self._width + self._x_offset

    def _render_waveform(self) -> None:
        if self._num_samples != 0:
            self._draw_rms_amplitudes(self._ctx)
            self._draw_surface(self._ctx)

    def _draw_surface(self, ctx: cairo.Context[cairo.ImageSurface]) -> None:
        if not self._is_LTR:
            # rotate 180° around the center
            ctx.translate(
                (self._width + self._x_offset * 2) / 2, self._height / 2)
            ctx.rotate(math.pi)
            ctx.translate(
                -(self._width + self._x_offset * 2) / 2, -self._height / 2)

        ctx.append_path(self._cairo_path)
        ctx.clip()

        play_pos = self._pixel_pos(self._position)
        start_pos = self._pixel_pos(0.0)
        width_pos = play_pos - start_pos

        # Default
        self._style_context.set_state(Gtk.StateFlags.NORMAL)
        Gtk.render_background(
            self._style_context, ctx,
            start_pos, 0, self._width, self._height)

        # Progress
        self._style_context.set_state(Gtk.StateFlags.CHECKED)
        Gtk.render_background(self._style_context, ctx,
                              start_pos, 0, width_pos, self._height)

        # Seek
        if self._seek_position >= 0:
            seek_pos = self._pixel_pos(self._seek_position)
            start_seek = min(play_pos, seek_pos)
            end_seek = max(play_pos, seek_pos)
            width_seek = end_seek - start_seek

            self._style_context.set_state(Gtk.StateFlags.SELECTED)
            Gtk.render_background(self._style_context, ctx,
                                  start_seek, 0, width_seek, self._height)

    def _draw_rms_amplitudes(self,
                             ctx: cairo.Context[cairo.ImageSurface]
                             ) -> None:
        ctx.new_path()

        peak_width = self._peak_width
        radius = 1  # radius of the arcs on top and bottom of the amplitudes
        gap = 0.25  # between upper and lower peak in pixels
        scaling = self._height / 2 - radius - gap / 2  # peak scaling factor

        # determines the spacing between the amplitudes
        x_shift = (self._width - 2 * peak_width) / self._num_samples
        x = self._x_offset + x_shift

        for i in range(self._num_samples):
            sample1 = self._samples[i][0]
            sample2 = self._samples[i][1]

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
            x += x_shift

        self._cairo_path = ctx.copy_path()

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
        # A --- B --- C
        # |           |
        # F --- E --- D

        # Up
        # A -- B -- C
        ctx.move_to(x, y + height1)
        ctx.curve_to(x, y + height1,
                     x + m, y + height1 + radius,
                     x + width, y + height1)
        # C -- D
        ctx.line_to(x + width, y + gap_size)
        # D -- F
        ctx.line_to(x, y + gap_size)
        # F -- A
        ctx.line_to(x, y + height1)
        ctx.close_path()

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
        ctx.close_path()
