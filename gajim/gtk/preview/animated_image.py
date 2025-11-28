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

from gajim.gtk.preview.gif_backend import GifBackend
from gajim.gtk.preview.webp_backend import WebPBackend
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
        width: int,
        height: int,
        player_backend: typing.Any[GifBackend, WebPBackend],
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._orig_path = orig_path

        self._static_picture = Gtk.Picture()
        self._static_picture.set_filename(str(thumbnail_path))
        self._static_picture.add_css_class("preview-image")

        self._icon = Gtk.Image.new_from_icon_name("inter-play-gif")
        self._icon.set_pixel_size(40 * app.window.get_scale_factor())
        self._icon.set_halign(Gtk.Align.CENTER)
        self._icon.set_valign(Gtk.Align.CENTER)

        self._content_box = Gtk.Box(width_request=width, height_request=height)
        self._controller = Gtk.GestureClick()
        self._connect(self._controller, "pressed", self._on_click)
        self._content_box.add_controller(self._controller)

        self._overlay = Gtk.Overlay()
        self._overlay.set_child(self._content_box)
        self._overlay.add_overlay(self._static_picture)
        self._overlay.add_overlay(self._icon)
        self.append(self._overlay)

        self._static_picture.set_can_target(False)
        self._icon.set_can_target(False)

        self._animated_picture = None
        self._backend = player_backend(self._orig_path, max_loops=3)
        self._connect(self._backend, "pipeline-changed", self._on_pipeline_changed)
        self._connect(self._backend, "playback-changed", self._on_playback_changed)

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)

        self._backend.cleanup()
        self._static_picture = None
        self._animated_picture = None

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

        self._animated_picture = Gtk.Picture(
            paintable=paintable, visible=False, can_target=False
        )
        self._animated_picture.add_css_class("preview-image")
        self._overlay.add_overlay(self._animated_picture)
        log.debug("Start playback...")
        self._backend.play()

    def _on_playback_changed(self, _backend: typing.Any, is_playing: bool) -> None:
        assert self._animated_picture is not None
        assert self._static_picture is not None
        if is_playing:
            self._icon.set_visible(False)
            self._animated_picture.set_visible(True)
            self._static_picture.set_visible(False)
        else:
            self._icon.set_visible(True)
            self._static_picture.set_visible(True)
            self._animated_picture.set_visible(False)

    def _on_click(
        self, _gesture_click: Gtk.GestureClick, _n_press: int, _x: float, _y: float
    ) -> None:
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
