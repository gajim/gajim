# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import math

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Graphene
from gi.repository import Gsk
from gi.repository import Gtk

from gajim.gtk.audio_player import AudioSampleT

log = logging.getLogger("gajim.gtk.preview_audio_visualizer")


class AudioVisualizerWidget(Gtk.Widget):
    def __init__(
        self,
        width: int = 340,
        height: int = 50,
        x_offset: int = 0,
        is_seekable: bool = False,
    ) -> None:
        Gtk.Widget.__init__(
            self,
            margin_start=x_offset,
            width_request=width,
            height_request=height,
            halign=Gtk.Align.START,
        )

        self._bar_width = 2  # px
        self._width = width
        self._height = height
        self._is_LTR = bool(self.get_direction() == Gtk.TextDirection.LTR)

        self._samples: AudioSampleT = []
        self._is_seekable = is_seekable
        self._seek_position = -1.0
        self._position = 0.0
        self._live_mode = False
        self._scroll_fraction = 0.0

        self._waveform_path: Gsk.Path | None = None

        accent = Adw.StyleManager.get_default().get_accent_color_rgba()

        style_context = self.get_style_context()
        self._slider_color = style_context.lookup_color("window_bg_color")[1]
        self._slider_border_color = style_context.lookup_color("window_fg_color")[1]

        self._color_progress = accent
        self._color_seek = Gdk.RGBA(
            red=min(1.0, accent.red * 1.3),
            green=min(1.0, accent.green * 1.3),
            blue=min(1.0, accent.blue * 1.3),
            alpha=accent.alpha,
        )
        color_default = accent.copy()
        color_default.alpha = max(0.0, accent.alpha - 0.4)
        self._color_default = color_default

    def get_effective_width(self) -> int:
        return self._width

    def set_parameters(self, position: float, live_mode: bool = False) -> None:
        self._position = position
        self._live_mode = live_mode

    def set_samples(self, samples: AudioSampleT) -> None:
        if self._is_static:
            samples = self._downsample(samples)
            samples = self._normalize(samples)
            samples = self._rescale(samples)
            self._waveform_path = self._build_static_path(samples)
        self._samples = samples

    def render_animated_graph(self, scroll_fraction: float = 0.0) -> None:
        if not self._samples:
            log.debug("Render animated graph: No samples")
            return
        self._scroll_fraction = scroll_fraction
        self.queue_draw()

    def render_static_graph(self, position: float, seek_position: float = -1.0) -> None:
        if not self._samples:
            return
        self._position = position
        self._seek_position = seek_position
        self.queue_draw()

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        if self._is_static:
            if self._waveform_path is None:
                log.debug("Waveform path is None")
                return
            self._draw_static(snapshot)
        else:
            if not self._samples:
                return
            self._draw_animated(snapshot)

    def _draw_static(self, snapshot: Gtk.Snapshot) -> None:
        assert self._waveform_path is not None
        if not self._is_LTR:
            self._apply_rtl_transform(snapshot)

        play_x = self._position * self._width

        snapshot.push_clip(Graphene.Rect().init(0, 0, self._width, self._height))
        snapshot.append_fill(
            self._waveform_path, Gsk.FillRule.WINDING, self._color_default
        )
        snapshot.pop()

        snapshot.push_clip(Graphene.Rect().init(0, 0, play_x, self._height))
        snapshot.append_fill(
            self._waveform_path, Gsk.FillRule.WINDING, self._color_progress
        )
        snapshot.pop()

        if self._seek_position >= 0:
            seek_x = self._seek_position * self._width
            x0 = min(play_x, seek_x)
            x1 = max(play_x, seek_x)
            snapshot.push_clip(Graphene.Rect().init(x0, 0, x1 - x0, self._height))
            snapshot.append_fill(
                self._waveform_path, Gsk.FillRule.WINDING, self._color_seek
            )
            snapshot.pop()
            slider_pos = seek_x
        else:
            slider_pos = play_x

        slider_pos = max(slider_pos, self._bar_width)
        slider_pos = min(slider_pos, self._width - self._bar_width)
        slider_radius = self._height // 5
        self._draw_slider(
            snapshot,
            x=slider_pos,
            y=self._height // 2,
            radius=slider_radius,
            fill_color=self._slider_color,
            border_color=self._slider_border_color,
            border_width=1,
        )

    def _draw_animated(self, snapshot: Gtk.Snapshot) -> None:
        if not self._is_LTR:
            self._apply_rtl_transform(snapshot)

        n = len(self._samples)
        x_step = (self._width - 2 * self._bar_width) / n
        x0 = x_step * (1.0 - self._scroll_fraction)
        cy = self._height / 2
        fade_n = max(1, n // 8)

        # Batch all fully opaque bars into a single path and draw call
        pb = Gsk.PathBuilder.new()
        for i in range(fade_n, n):
            self._add_bar(pb, x0 + i * x_step, cy, *self._samples[i])
        snapshot.append_fill(pb.to_path(), Gsk.FillRule.WINDING, self._color_progress)

        # Draw faded bars individually — only ~10 of them
        r = self._color_progress.red
        g = self._color_progress.green
        b = self._color_progress.blue
        a = self._color_progress.alpha
        for i in range(fade_n):
            t = i / fade_n
            alpha = t * t * (3.0 - 2.0 * t)  # smoothstep fade-in
            color = Gdk.RGBA(red=r, green=g, blue=b, alpha=a * alpha)
            pb = Gsk.PathBuilder.new()
            self._add_bar(pb, x0 + i * x_step, cy, *self._samples[i])
            snapshot.append_fill(pb.to_path(), Gsk.FillRule.WINDING, color)

    def _apply_rtl_transform(self, snapshot: Gtk.Snapshot) -> None:
        cx, cy = self._width / 2, self._height / 2
        snapshot.translate(Graphene.Point().init(cx, cy))
        snapshot.rotate(180)
        snapshot.translate(Graphene.Point().init(-cx, -cy))

    def _draw_slider(
        self,
        snapshot: Gtk.Snapshot,
        x: float,
        y: float,
        radius: float,
        fill_color: Gdk.RGBA,
        border_color: Gdk.RGBA,
        border_width: float,
    ) -> None:
        rect = Graphene.Rect()
        rect.init(
            x - radius,
            y - radius,
            radius * 2,
            radius * 2,
        )
        rounded = Gsk.RoundedRect()
        rounded.init_from_rect(rect, radius)
        snapshot.push_rounded_clip(rounded)
        snapshot.append_color(fill_color, rect)
        snapshot.pop()
        snapshot.append_border(
            rounded,
            [border_width] * 4,
            [border_color] * 4,
        )

    def _build_static_path(self, samples: AudioSampleT) -> Gsk.Path | None:
        if not samples:
            return None
        n = len(samples)
        x_step = (self._width - 2 * self._bar_width) / n
        cy = self._height / 2
        pb = Gsk.PathBuilder.new()
        for i, (s1, s2) in enumerate(samples):
            self._add_bar(pb, x_step * (i + 1), cy, s1, s2)
        return pb.to_path()

    def _add_bar(
        self,
        pb: Gsk.PathBuilder,
        x: float,
        cy: float,
        h1: float,
        h2: float,
    ) -> None:
        # Upper half grows downward from cy, lower half grows upward.
        # Outer (top/bottom) edges are rounded with a conic arc.
        scaling = self._height / 2 - 1
        h1 = max(0.5, h1 * scaling)
        h2 = max(0.5, h2 * scaling)
        hw = self._bar_width / 2
        r = self._bar_width  # right edge x

        pb.move_to(x, cy + h1)
        pb.conic_to(x + hw, cy + h1 + hw, x + r, cy + h1, 30)
        pb.line_to(x + r, cy)
        pb.line_to(x, cy)
        pb.close()

        pb.move_to(x + r, cy)
        pb.line_to(x + r, cy - h2)
        pb.conic_to(x + hw, cy - h2 - hw, x, cy - h2, 30)
        pb.line_to(x, cy)
        pb.line_to(x + r, cy)
        pb.close()

    def _downsample(self, samples: AudioSampleT) -> AudioSampleT:
        num_bars = int(self._width / (self._bar_width * 2))
        if num_bars == 0:
            log.error("Number of bars is zero")
            return []

        stride = math.floor(len(samples) / num_bars) + 1
        if stride < 2:
            return samples

        s1_vals, s2_vals = zip(*samples, strict=True)
        result: AudioSampleT = []
        for i in range(2, int(len(samples) - stride / 2), stride):
            c = int(i + stride / 2)
            result.append(
                (
                    (s1_vals[c - 1] + s1_vals[c]) / 2,
                    (s2_vals[c - 1] + s2_vals[c]) / 2,
                )
            )
        return result

    def _normalize(self, samples: AudioSampleT) -> AudioSampleT:
        if not samples:
            log.error("No samples to normalize")
            return []
        all_vals = [v for pair in samples for v in pair]
        lo = min(all_vals)
        hi = max(all_vals)
        span = hi - lo
        if span <= 0:
            return samples
        return [((v1 - lo) / span, (v2 - lo) / span) for v1, v2 in samples]

    def _rescale(self, samples: AudioSampleT) -> AudioSampleT:
        # sin(sqrt) expands quieter peaks to match perceptual loudness
        inv_sin1 = 1.0 / math.sin(1)
        return [
            (
                math.sin(math.sqrt(abs(v1))) * inv_sin1,
                math.sin(math.sqrt(abs(v2))) * inv_sin1,
            )
            for v1, v2 in samples
        ]

    @property
    def _is_static(self) -> bool:
        return not self._live_mode
