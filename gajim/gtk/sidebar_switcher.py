# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

from gi.repository import Adw
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.util.classes import SignalManager


class SideBarSwitcher(Gtk.Stack, SignalManager):
    __gtype_name__ = "SideBarSwitcher"

    width = GObject.Property(type=int, default=-1)

    def __init__(self, width: int = -1) -> None:
        Gtk.Stack.__init__(self)
        SignalManager.__init__(self)

        self.set_property("width", width)

        self._stack: Gtk.Stack | None = None
        self._menu: list[SideBarMenuItem] = []
        self._last_visible_child_name = ""
        self._current_visible_child_name = ""

        self._connect(self, "notify::visible-child-name", self._on_child_name_changed)

    def do_unroot(self) -> None:
        Gtk.Stack.do_unroot(self)
        self._disconnect_all()
        del self._stack
        self._menu.clear()
        app.check_finalize(self)

    def set_with_menu(
        self, stack: Gtk.Stack, menu: list[SideBarMenuItem], *, visible: bool = True
    ) -> None:
        self._menu = menu
        self._stack = stack

        def _append_menus(menu: list[SideBarMenuItem], key: str) -> None:
            listbox = self._append_page(key)
            if key != "__main":
                menu_item = SideBarMenuItem(
                    "__back", _("Back"), icon_name="lucide-chevron-left-symbolic"
                )
                listbox.append(menu_item)

            for m in menu:
                if not visible:
                    m.set_visible(False)
                listbox.append(m)
                if m.children:
                    _append_menus(m.children, m.key)

        _append_menus(menu, "__main")
        self._current_visible_child_name = "__main"

        self._select_first_menu_item()

    def set_with_stack(self, stack: Gtk.Stack, visible: bool = True) -> None:
        if self._menu:
            raise ValueError("Menu already was set for SideBarSwitcher")

        menu = self._build_from_stack(stack)
        self.set_with_menu(stack, menu, visible=visible)

    def _append_page(self, name: str) -> Gtk.ListBox:
        listbox = Gtk.ListBox(vexpand=True)
        listbox.add_css_class("sidebar-switcher")
        listbox.add_css_class("navigation-sidebar")
        listbox.set_size_request(self.width, -1)
        listbox.set_header_func(self._sidebar_header_func)
        self._connect(listbox, "row-activated", self._on_item_activated)
        self.add_named(listbox, name)
        return listbox

    def _select_first_menu_item(self) -> None:
        self.set_visible_child_name("__main")
        listbox = cast(Gtk.ListBox, self.get_child_by_name("__main"))

        index = 0
        while row := listbox.get_row_at_index(index):
            index += 1
            if not row.get_visible():
                continue

            assert isinstance(row, SideBarMenuItem)
            GLib.idle_add(self._activate_item, row)
            break

    @staticmethod
    def _build_from_stack(stack: Gtk.Stack) -> list[SideBarMenuItem]:
        menu: list[SideBarMenuItem] = []
        for page in stack.get_pages():  # pyright: ignore
            page = cast(Gtk.StackPage, page)
            name = page.get_name()
            if name is None:
                raise ValueError("unnamed child")
            title = page.get_title()
            if title is None:
                raise ValueError("no title on child")
            icon_name = page.get_icon_name()

            menu.append(SideBarMenuItem(name, title, icon_name=icon_name))
        return menu

    def _find_menu_item_by_key(self, key: str) -> SideBarMenuItem | None:
        def _find(menu: list[SideBarMenuItem]) -> SideBarMenuItem | None:
            for m in menu:
                if m.key == key:
                    return m
                if m.children:
                    return _find(m.children)

        return _find(self._menu)

    def set_item_visible(self, key: str, state: bool) -> None:
        menu_item = self._find_menu_item_by_key(key)
        if menu_item is None:
            raise ValueError
        menu_item.set_visible(state)

    def activate_item(self, key: str) -> None:
        menu_item = self._find_menu_item_by_key(key)
        if menu_item is None:
            raise ValueError

        GLib.idle_add(self._activate_item, menu_item)

    def _activate_item(self, item: SideBarMenuItem) -> int:
        item.emit("activate")
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _sidebar_header_func(
        item: SideBarMenuItem, before: SideBarMenuItem | None
    ) -> None:
        if before is None:
            if item.group:
                item.set_header(ItemHeader(label_text=item.group))
            else:
                item.set_header(None)

        else:
            if before.group == item.group:
                item.set_header(None)
            else:
                item.set_header(ItemHeader(label_text=item.group or "Unknown"))

    def _on_child_name_changed(
        self, stack: Gtk.Stack, _param: GObject.ParamSpec
    ) -> None:
        self._last_visible_child_name = self._current_visible_child_name
        name = stack.get_visible_child_name()
        assert name is not None
        self._current_visible_child_name = name

    def _on_item_activated(
        self, _listbox: SideBarSwitcher, item: SideBarMenuItem
    ) -> None:
        if item.children:
            self.set_visible_child_full(item.key, Gtk.StackTransitionType.SLIDE_LEFT)
            return

        if item.key == "__back":
            self.set_visible_child_full(
                self._last_visible_child_name, Gtk.StackTransitionType.SLIDE_RIGHT
            )
            return

        assert self._stack is not None
        self._stack.set_visible_child_name(item.key)

        toolbar_view = self._stack.get_parent()
        if not isinstance(toolbar_view, Adw.ToolbarView):
            return

        navigation_page = toolbar_view.get_parent()
        if not isinstance(navigation_page, Adw.NavigationPage):
            return

        navigation_page.set_title(item.title)


class SideBarMenuItem(Gtk.ListBoxRow):
    def __init__(
        self,
        key: str,
        title: str,
        group: str | None = None,
        icon_name: str | None = None,
        children: list[SideBarMenuItem] | None = None,
        visible: bool = True,
    ) -> None:
        Gtk.ListBoxRow.__init__(self)

        self.key = key
        self.title = title
        self.children = children
        self.group = group

        box = Gtk.Box(spacing=12)
        if icon_name is not None:
            image = Gtk.Image.new_from_icon_name(icon_name)
            box.append(image)

        label = Gtk.Label(label=title, xalign=0, hexpand=True)
        box.append(label)

        if self.children:
            image = Gtk.Image.new_from_icon_name("lucide-chevron-right-symbolic")
            box.append(image)

        self.set_child(box)
        self.set_visible(visible)

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        if self.children is not None:
            self.children.clear()
        app.check_finalize(self)


class ItemHeader(Gtk.Box):
    def __init__(self, label_text: str) -> None:
        Gtk.Box.__init__(self, hexpand=True)
        self.add_css_class("sidebar-row-header")
        label = Gtk.Label(label=label_text)
        self.append(label)
