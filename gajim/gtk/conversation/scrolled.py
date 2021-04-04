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

from gi.repository import Gtk
from gi.repository import GObject


class ScrolledView(Gtk.ScrolledWindow):

    __gsignals__ = {
        'request-history': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            ()
        )
    }

    def __init__(self, *args, **kwargs):
        Gtk.ScrolledWindow.__init__(self, *args, **kwargs)

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

        self._current_upper = 0
        self._autoscroll = True
        self._request_history_at_upper = None
        self._complete = False

        vadjustment = self.get_vadjustment()
        vadjustment.connect('notify::upper', self._on_adj_upper_changed)
        vadjustment.connect('notify::value', self._on_adj_value_changed)

    def get_autoscroll(self):
        return self._autoscroll

    def get_view(self):
        return self.get_child().get_child()

    def set_history_complete(self, complete):
        self._complete = complete
        self.get_view().set_history_complete(complete)

    def _on_adj_upper_changed(self, adj, *args):
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
                adj.set_value(adj.get_value() + diff)

        if upper == adj.get_page_size():
            # There is no scrollbar, request history until there is
            self.emit('request-history')

    def _on_adj_value_changed(self, adj, *args):
        bottom = adj.get_upper() - adj.get_page_size()
        if (bottom - adj.get_value()) < 1:
            self._autoscroll = True
        else:
            self._autoscroll = False

        if self._complete:
            self._request_history_at_upper = None
            return

        if self._request_history_at_upper == adj.get_upper():
            # Abort here if we already did a history request and the upper
            # did not change. This can happen if we scroll very fast and the
            # value changes while the request has not been fullfilled.
            return

        self._request_history_at_upper = None

        # Load messages when we are near the top
        if adj.get_value() < adj.get_page_size() * 2:
            self._request_history_at_upper = adj.get_upper()
            # Workaround: https://gitlab.gnome.org/GNOME/gtk/merge_requests/395
            self.set_kinetic_scrolling(False)
            self.emit('request-history')
