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

from gajim.common import app

from gajim.gui.util import load_icon


class AppSideBar(Gtk.ListBox):
    def __init__(self, app_page):
        Gtk.ListBox.__init__(self)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_valign(Gtk.Align.START)
        self.get_style_context().add_class('workspace-sidebar')

        self.connect('row-activated', self._on_app_row_activated)

        app_page.connect('unread-count-changed', self._on_unread_count_changed)

        self._app_row = AppRow()
        self.add(self._app_row)

        self.show_all()

    @staticmethod
    def _on_app_row_activated(_listbox, _row):
        app.window.show_app_page()

    def _on_unread_count_changed(self, _app_page, count):
        self._app_row.set_unread_count(count)


class AppRow(Gtk.ListBoxRow):
    def __init__(self):
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class('workspace-sidebar-item')

        self._unread_label = Gtk.Label()
        self._unread_label.get_style_context().add_class(
            'unread-counter')
        self._unread_label.set_no_show_all(True)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)

        surface = load_icon('org.gajim.Gajim', self, 32)
        image = Gtk.Image.new_from_surface(surface)
        image.get_style_context().add_class('app-sidebar-image')

        selection_bar = Gtk.Box()
        selection_bar.set_size_request(6, -1)
        selection_bar.get_style_context().add_class('selection-bar')

        item_box = Gtk.Box()
        item_box.add(selection_bar)
        item_box.add(image)

        overlay = Gtk.Overlay()
        overlay.add(item_box)
        overlay.add_overlay(self._unread_label)

        self.add(overlay)
        self.show_all()

    def set_unread_count(self, count):
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text('999+')
        self._unread_label.set_visible(bool(count))
