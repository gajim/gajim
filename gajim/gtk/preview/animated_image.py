# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging
from pathlib import Path

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.preview.animated_image_backend import AnimatedImageBackend
from gajim.gtk.preview.animated_image_fallback_backend import (
    AnimatedImageFallbackBackend,
)
from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.animated_image")


class AnimatedImage(Gtk.Box, SignalManager):
    __gtype_name__ = "AnimatedImage"
    __gsignals__ = {
        "error": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(
        self,
        thumbnail_path: Path,
        orig_path: Path,
        player_backend: typing.Any[AnimatedImageBackend, AnimatedImageFallbackBackend],
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._orig_path = orig_path

        self._picture = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN)
        self._picture.set_filename(str(thumbnail_path))
        self._picture.add_css_class("preview-image")
        self._picture.set_can_target(False)

        self._static_paintable = self._picture.get_paintable()
        self._animated_paintable = None

        self._icon = Gtk.Image.new_from_icon_name("inter-play-gif")
        self._icon.set_pixel_size(40 * app.window.get_scale_factor())
        self._icon.set_halign(Gtk.Align.CENTER)
        self._icon.set_valign(Gtk.Align.CENTER)
        self._icon.set_can_target(False)

        self._overlay = Gtk.Overlay()
        self._overlay.set_child(self._picture)
        self._overlay.add_overlay(self._icon)
        self.append(self._overlay)

        self._controller = Gtk.GestureClick()
        self._connect(self._controller, "pressed", self._on_click)
        self._overlay.add_controller(self._controller)

        self._backend = player_backend(self._orig_path, max_loops=3)
        self._connect(self._backend, "pipeline-changed", self._on_pipeline_changed)
        self._connect(self._backend, "playback-changed", self._on_playback_changed)

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)

        self._backend.cleanup()
        self._static_paintable = None
        self._animated_paintable = None

        self._disconnect_all()
        app.check_finalize(self)

    def _on_pipeline_changed(self, _backend: typing.Any, success: bool) -> None:
        if not success:
            self.emit("error")
            return

        paintable = self._backend.paintable
        if paintable is None:
            log.warning("We got no paintable")
            self.emit("error")
            return

        self._animated_paintable = paintable
        log.debug("Start playback...")
        self._backend.play()

    def _on_playback_changed(self, _backend: typing.Any, is_playing: bool) -> None:
        if is_playing:
            assert self._animated_paintable is not None
            self._picture.set_paintable(self._animated_paintable)
        else:
            self._picture.set_paintable(self._static_paintable)

        self._icon.set_visible(not is_playing)

    def _on_click(
        self, gesture_click: Gtk.GestureClick, _n_press: int, _x: float, _y: float
    ) -> None:
        gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)

        if self._backend.pipeline_setup_failed:
            self.emit("error")
            return

        if not self._backend.pipeline_is_setup:
            self._backend.setup_pipeline()
            return

        if self._backend.is_playing():
            self._backend.pause()
        else:
            self._backend.play()
