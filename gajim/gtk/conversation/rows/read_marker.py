# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Adw
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common.i18n import _

_FADE_DURATION_MS = 150


class ReadMarkerOverlay(Gtk.Box):
    """Floating “New” marker — not part of list layout."""

    __gtype_name__ = "ConversationReadMarkerOverlay"

    def __init__(self) -> None:
        Gtk.Box.__init__(
            self,
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        self.set_can_target(False)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.START)
        self.set_hexpand(True)
        self.set_margin_start(14)
        self.set_margin_end(12)
        self.set_opacity(0.0)
        self.add_css_class("conversation-read-marker")
        self._animation: Adw.TimedAnimation | None = None
        self._finished: Callable[[], None] | None = None
        self.after_pk: int = 0

        separator = Gtk.Separator(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
        )
        separator.add_css_class("conversation-read-marker-separator")
        self.append(separator)

        label = Gtk.Label(
            label=_("New"),
            valign=Gtk.Align.CENTER,
        )
        label.add_css_class("conversation-read-marker-label")
        self.append(label)

    def fade_in(self) -> None:
        self._animate(1.0)

    def fade_out(self, finished: Callable[[], None] | None = None) -> None:
        self._animate(0.0, finished)

    def update_fade(self, active: bool) -> None:
        if not active:
            self._cancel_fade()
        elif self._fade_id is None:
            self._fade_id = GLib.timeout_add(self._fade_ms, self._fade)

    def _fade(self) -> bool:
        self._fade_id = None
        self._on_timeout()
        return GLib.SOURCE_REMOVE

    def _cancel_fade(self) -> None:
        if self._fade_id is not None:
            GLib.source_remove(self._fade_id)
            self._fade_id = None

    def stop_animation(self) -> None:
        """Cancel any in-flight fade without invoking its completion callback."""
        self._cancel_fade()
        self._finished = None
        if self._animation is None:
            return

        animation = self._animation
        self._animation = None
        animation.reset()

    def _animate(
        self,
        end: float,
        finished: Callable[[], None] | None = None,
    ) -> None:
        self.stop_animation()
        self._finished = finished

        target = Adw.PropertyAnimationTarget.new(self, "opacity")
        animation = Adw.TimedAnimation.new(
            self, self.get_opacity(), end, _FADE_DURATION_MS, target
        )
        animation.set_easing(Adw.Easing.EASE_IN_OUT_CUBIC)

        def _on_done(_animation: Adw.TimedAnimation) -> None:
            if self._animation is not animation:
                return
            self._animation = None
            callback = self._finished
            self._finished = None
            if callback is not None:
                callback()

        animation.connect("done", _on_done)
        self._animation = animation
        animation.play()

    def do_unroot(self) -> None:
        self.stop_animation()
        Gtk.Box.do_unroot(self)
