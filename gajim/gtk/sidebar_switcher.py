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

from typing import cast

from gi.repository import Gtk

from gajim.common import app


class SideBarSwitcher(Gtk.ListBox):
    def __init__(self, width: int | None = None) -> None:
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.get_style_context().add_class('settings-menu')
        if width is not None:
            self.set_size_request(width, -1)
        self.connect('row-activated', self._on_row_activated)
        self._stack = cast(Gtk.Stack, None)
        self._rows: dict[str, Row] = {}

        self.connect('destroy', self._destroy)

    def set_stack(self, stack: Gtk.Stack, rows_visible: bool = True) -> None:
        self._stack = stack
        for page in self._stack.get_children():
            name = self._stack.child_get_property(page, 'name')
            if name is None:
                raise ValueError('unnamed child')
            title = self._stack.child_get_property(page, 'title')
            if title is None:
                raise ValueError('no title on child')
            icon_name = self._stack.child_get_property(page, 'icon-name')

            row = Row(name, title, icon_name, rows_visible)

            self.add(row)
            self._rows[name] = row

        self._select_first_row()

    def set_row_visible(self, name: str, state: bool) -> None:
        row = self._rows.get(name)
        if row is None:
            raise ValueError
        row.set_visible(state)

    def set_row(self, name: str) -> None:
        row = self._rows.get(name)
        if row is None:
            raise ValueError
        self.select_row(row)
        self._stack.set_visible_child_name(name)

    def _on_row_activated(self, _listbox: SideBarSwitcher, row: Row):
        self._stack.set_visible_child_name(row.name)

    def _select_first_row(self):
        self.select_row(self.get_row_at_index(0))

    def _destroy(self, _widget: SideBarSwitcher) -> None:
        for row in self._rows.values():
            row.destroy()
        self._rows.clear()
        del self._stack
        app.check_finalize(self)


class Row(Gtk.ListBoxRow):
    def __init__(self,
                 name: str,
                 title: str,
                 icon_name: str | None,
                 visible: bool) -> None:

        Gtk.ListBoxRow.__init__(self)

        self.name = name

        box = Gtk.Box()
        if icon_name is not None:
            image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            image.get_style_context().add_class('dim-label')
            box.add(image)

        label = Gtk.Label(label=title)
        label.set_xalign(0)
        box.add(label)
        self.add(box)

        self.show_all()
        self.set_no_show_all(True)
        self.set_visible(visible)
