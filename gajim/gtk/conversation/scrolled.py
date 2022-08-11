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

from typing import Any
from typing import Optional

from gi.repository import Gtk
from gi.repository import GObject

from gajim.common.types import ChatContactT

from .view import ConversationView


class ScrolledView(Gtk.ScrolledWindow):

    __gsignals__ = {
        'request-history': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (bool, )
        ),
        'autoscroll-changed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            (bool,)
        )
    }

    def __init__(self) -> None:
        Gtk.ScrolledWindow.__init__(self)

        self.set_overlay_scrolling(False)
        self.get_style_context().add_class('scrolled-no-border')
        self.get_style_context().add_class('no-scroll-indicator')
        self.get_style_context().add_class('scrollbar-style')
        self.set_shadow_type(Gtk.ShadowType.IN)
        self.set_vexpand(True)

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # This is a workaround: as soon as a line break occurs in Gtk.TextView
        # with word-char wrapping enabled, a hyphen character is automatically
        # inserted before the line break. This triggers the hscrollbar to show,
        # see: https://gitlab.gnome.org/GNOME/gtk/-/issues/2384
        # Using set_hscroll_policy(Gtk.Scrollable.Policy.NEVER) would cause bad
        # performance during resize, and prevent the window from being shrunk
        # horizontally under certain conditions (applies to GroupchatControl)
        self.get_hscrollbar().hide()

        self._current_upper: float = 0
        self._autoscroll: bool = True
        self._request_history_at_upper: Optional[float] = None
        self._upper_complete: bool = False
        self._lower_complete: bool = False
        self._requesting: Optional[str] = None
        self._block_signals = False

        vadjustment = self.get_vadjustment()
        vadjustment.connect('notify::upper', self._on_adj_upper_changed)
        vadjustment.connect('notify::value', self._on_adj_value_changed)

        self._view = ConversationView()
        self.add(self._view)
        self.set_focus_vadjustment(Gtk.Adjustment())

    def clear(self) -> None:
        self._block_signals = True
        self._reset()
        self._view.clear()

    def switch_contact(self, contact: ChatContactT) -> None:
        self._block_signals = True
        self._reset()
        self._view.switch_contact(contact)
        self._block_signals = False
        self._emit('request-history', True)

    def get_autoscroll(self) -> bool:
        return self._autoscroll

    def get_view(self) -> ConversationView:
        return self._view

    def block_signals(self, value: bool) -> None:
        self._block_signals = value

    def _emit(self, signal_name: str, *args: Any) -> None:
        if not self._block_signals:
            self.emit(signal_name, *args)

    def _reset(self) -> None:
        self._current_upper = 0
        self._request_history_at_upper = None
        self._upper_complete = False
        self._lower_complete = False
        self._requesting = None
        self.set_history_complete(True, False)

    def reset(self) -> None:
        self._reset()
        self._view.reset()

    def set_history_complete(self, before: bool, complete: bool) -> None:
        if before:
            self._upper_complete = complete
            self._view.set_history_complete(complete)
        else:
            self._lower_complete = complete

    def get_lower_complete(self) -> bool:
        return self._lower_complete

    def _on_adj_upper_changed(self,
                              adj: Gtk.Adjustment,
                              _pspec: GObject.ParamSpec) -> None:

        upper = adj.get_upper()
        diff = upper - self._current_upper

        if diff != 0:
            self._current_upper = upper
            if self._autoscroll:
                adj.set_value(adj.get_upper() - adj.get_page_size())
            else:
                # Workaround
                # https://gitlab.gnome.org/GNOME/gtk/merge_requests/395
                self.set_kinetic_scrolling(True)
                if self._requesting == 'before':
                    adj.set_value(adj.get_value() + diff)

        if upper == adj.get_page_size():
            # There is no scrollbar
            if not self._block_signals:
                self._emit('request-history', True)
            self._lower_complete = True
            self._autoscroll = True
            self._emit('autoscroll-changed', self._autoscroll)

        self._requesting = None

    def _on_adj_value_changed(self,
                              adj: Gtk.Adjustment,
                              _pspec: GObject.ParamSpec) -> None:

        if self._requesting is not None:
            return

        bottom = adj.get_upper() - adj.get_page_size()
        if (bottom - adj.get_value()) < 1:
            self._autoscroll = True
            self._emit('autoscroll-changed', self._autoscroll)
        else:
            self._autoscroll = False
            self._emit('autoscroll-changed', self._autoscroll)

        if self._upper_complete:
            self._request_history_at_upper = None
            if self._lower_complete:
                return

        if self._request_history_at_upper == adj.get_upper():
            # Abort here if we already did a history request and the upper
            # did not change. This can happen if we scroll very fast and the
            # value changes while the request has not been fulfilled.
            return

        self._request_history_at_upper = None

        distance = adj.get_page_size() * 2
        if adj.get_value() < distance:
            # Load messages when we are near the top
            if self._upper_complete:
                return
            self._request_history_at_upper = adj.get_upper()
            # Workaround: https://gitlab.gnome.org/GNOME/gtk/merge_requests/395
            self.set_kinetic_scrolling(False)
            if not self._block_signals:
                self._emit('request-history', True)
            self._requesting = 'before'
        elif (adj.get_upper() - (adj.get_value() + adj.get_page_size()) <
                distance):
            # ..or near the bottom
            if self._lower_complete:
                return
            # Workaround: https://gitlab.gnome.org/GNOME/gtk/merge_requests/395
            self.set_kinetic_scrolling(False)
            if not self._block_signals:
                self._emit('request-history', False)
            self._requesting = 'after'
