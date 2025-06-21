# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.configpaths import get_ui_path
from gajim.common.const import AvatarSize

from gajim.gtk.util.classes import SignalManager


class SideBarListBox(Gtk.ListBox):
    __gtype_name__ = "SideBarListBox"

    def __init__(self) -> None:
        Gtk.ListBox.__init__(self)
        self.set_name("SideBarListBox")


@Gtk.Template(filename=get_ui_path("side_bar_listbox_row.ui"))
class SideBarListBoxRow(Gtk.ListBoxRow, SignalManager):
    __gtype_name__ = "SideBarListBoxRow"

    _overlay: Gtk.Overlay = Gtk.Template.Child()
    _image: Gtk.Image = Gtk.Template.Child()
    _label: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        self._icon_name: str = ""
        self._item_id: str = ""
        self._index = 0
        self._drag_hotspot_x: float = 0
        self._drag_hotspot_y: float = 0
        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def enable_as_drag_source(self) -> None:
        drag_source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        self._connect(drag_source, "prepare", self._on_prepare)
        self._connect(drag_source, "drag-begin", self._on_drag_begin)
        self._connect(drag_source, "drag-end", self._on_drag_end)
        self.add_controller(drag_source)

    def _on_prepare(
        self, _drag_source: Gtk.DragSource, x: float, y: float
    ) -> Gdk.ContentProvider:
        self._drag_hotspot_x = x
        self._drag_hotspot_y = y

        value = GObject.Value()
        value.init(SideBarListBoxRow)
        value.set_object(self)

        return Gdk.ContentProvider.new_for_value(value)

    def _on_drag_begin(self, _drag_source: Gtk.DragSource, drag: Gdk.Drag) -> None:
        texture = app.app.avatar_storage.get_workspace_texture(
            self._item_id, AvatarSize.WORKSPACE, 1
        )
        if texture is not None:
            Gtk.DragIcon.set_from_paintable(
                drag, texture, int(self._drag_hotspot_x), int(self._drag_hotspot_y)
            )

        app.window.highlight_dnd_targets(self, True)

    def _on_drag_end(
        self, _drag_source: Gtk.DragSource, _drag: Gdk.Drag, _delete_data: bool
    ) -> None:
        app.window.highlight_dnd_targets(self, False)

    @GObject.Property(type=int)
    def index(self) -> int:  # pyright: ignore
        return self._index

    @index.setter
    def index(self, index: int) -> None:
        self._index = index

    @GObject.Property(type=str)
    def item_id(self) -> str:  # pyright: ignore
        return self._item_id

    @item_id.setter
    def item_id(self, item_id: str) -> None:
        self._item_id = item_id

    @GObject.Property(type=str)
    def icon_name(self) -> str:  # pyright: ignore
        return self._icon_name

    @icon_name.setter
    def icon_name(self, icon_name: str) -> None:
        self._icon_name = icon_name
        self._image.set_from_icon_name(icon_name)

    def set_workspace_id(self, workspace_id: str) -> None:
        self.item_id = workspace_id
        self.add_css_class("workspace-listbox-row")
        self.enable_as_drag_source()

    def set_from_paintable(self, paintable: Gdk.Paintable | None) -> None:
        self._image.set_from_paintable(paintable)

    def set_unread_notify(self, obj: GObject.Object) -> None:
        def _on_notify(obj_: GObject.Object, _param: GObject.ParamSpec) -> None:
            self.set_unread_count(obj_.props.unread_count)

        self._connect(obj, "notify::unread-count", _on_notify)

    def set_unread_count(self, count: int) -> None:
        if count == 0:
            self._label.set_visible(False)
            return

        if count < 1000:
            self._label.set_text(str(count))
        else:
            self._label.set_text("999+")

    def set_secondary_callback(self, callback: Any) -> None:
        controller = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(controller, "pressed", callback, self)
        self.add_controller(controller)
