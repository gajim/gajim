# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.util.classes import SignalManager


class SideBarSwitcher(Gtk.ListBox, SignalManager):
    def __init__(self, width: int | None = None) -> None:
        Gtk.ListBox.__init__(self)
        SignalManager.__init__(self)

        self.set_vexpand(True)
        self.add_css_class("settings-menu")
        if width is not None:
            self.set_size_request(width, -1)

        self._connect(self, "row-activated", self._on_row_activated)
        self._stack = cast(Gtk.Stack, None)
        self._rows: dict[str, Row] = {}

    def do_unroot(self) -> None:
        self.set_header_func(None)
        Gtk.ListBox.do_unroot(self)
        self._disconnect_all()
        del self._stack
        self._rows.clear()
        app.check_finalize(self)

    def set_stack(self, stack: Gtk.Stack, rows_visible: bool = True) -> None:
        self._stack = stack
        for page in self._stack.get_pages():  # pyright: ignore
            page = cast(Gtk.StackPage, page)
            name = page.get_name()
            if name is None:
                raise ValueError("unnamed child")
            title = page.get_title()
            if title is None:
                raise ValueError("no title on child")
            icon_name = page.get_icon_name()

            row = Row(name, title, icon_name, rows_visible)

            self.append(row)
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


class Row(Gtk.ListBoxRow):
    def __init__(
        self, name: str, title: str, icon_name: str | None, visible: bool
    ) -> None:

        Gtk.ListBoxRow.__init__(self)

        self.name = name

        box = Gtk.Box()
        if icon_name is not None:
            image = Gtk.Image.new_from_icon_name(icon_name)
            image.add_css_class("dim-label")
            box.append(image)

        label = Gtk.Label(label=title)
        label.set_xalign(0)
        box.append(label)
        self.set_child(box)
        self.set_visible(visible)


class RowHeader(Gtk.Box):
    def __init__(self, label_text: str) -> None:
        Gtk.Box.__init__(self, hexpand=True)
        self.add_css_class("sidebar-row-header")
        label = Gtk.Label(label=label_text)
        self.append(label)
