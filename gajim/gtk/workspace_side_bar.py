# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import TYPE_CHECKING

import logging
from collections.abc import Iterator

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.chat_list_row import ChatListRow
from gajim.gtk.menus import get_workspace_menu
from gajim.gtk.structs import ChatListEntryParam
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_listbox_row_count
from gajim.gtk.util.misc import iterate_listbox_children
from gajim.gtk.util.window import open_window
from gajim.gtk.widgets import GajimPopover

if TYPE_CHECKING:
    # Simplifies testing
    from gajim.gtk.chat_list_stack import ChatListStack
    from gajim.gtk.chat_page import ChatPage

log = logging.getLogger("gajim.gtk.workspace_sidebar")


class WorkspaceSideBar(Gtk.ListBox, SignalManager):
    def __init__(self, chat_page: ChatPage) -> None:
        Gtk.ListBox.__init__(self, vexpand=True, valign=Gtk.Align.START)
        SignalManager.__init__(self)

        self.add_css_class("workspace-sidebar")

        formats_workspace = Gdk.ContentFormats.new_for_gtype(Workspace)
        formats_chat_list_row = Gdk.ContentFormats.new_for_gtype(ChatListRow)
        formats = formats_workspace.union(formats_chat_list_row)

        drop_target = Gtk.DropTarget(formats=formats, actions=Gdk.DragAction.MOVE)
        self._connect(drop_target, "drop", self._on_drop)
        self.add_controller(drop_target)

        self._connect(self, "row-activated", self._on_row_activated)

        self.append(AddWorkspace())

        self.set_sort_func(self._sort_func)

        chat_list_stack = chat_page.get_chat_list_stack()
        self._connect(
            chat_list_stack, "unread-count-changed", self._on_unread_count_changed
        )
        self._connect(chat_list_stack, "chat-selected", self._on_chat_selected)
        self._workspaces: dict[str, Workspace] = {}

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBox.do_unroot(self)
        app.check_finalize(self)

    def get_row_count(self) -> int:
        return get_listbox_row_count(self)

    def _iterate_rows(self) -> Iterator[CommonWorkspace]:
        for row in iterate_listbox_children(self):
            yield cast(CommonWorkspace, row)

    def _sort_func(self, row1: CommonWorkspace, row2: CommonWorkspace) -> int:
        return -1 if row1.index < row2.index else 1

    def _on_drop(
        self, _drop_target: Gtk.DropTarget, item: GObject.Value, _x: float, y: float
    ) -> bool:
        target_workspace = self.get_row_at_y(int(y))
        app.window.highlight_dnd_targets(self, False)

        if not item or not isinstance(target_workspace, Workspace):
            # Reject drop
            return False

        app.window.highlight_dnd_targets(item, False)

        if isinstance(item, Workspace):
            workspaces = list(self._iterate_rows())
            moved_workspace = workspaces.pop(item.index)
            workspaces.insert(target_workspace.get_index(), moved_workspace)

            for index, workspace in enumerate(workspaces):
                if workspace.workspace_id == "add":
                    continue
                workspace.index = index

            self.invalidate_sort()
            target_workspace.set_state_flags(Gtk.StateFlags.NORMAL, True)

            self.store_workspace_order()
            app.window.activate_workspace(item.workspace_id)
            return True

        if isinstance(item, ChatListRow):
            params = ChatListEntryParam(
                workspace_id=target_workspace.workspace_id,
                source_workspace_id=item.workspace_id,
                account=item.account,
                jid=item.jid,
            )
            app.window.activate_action(
                "win.move-chat-to-workspace", params.to_variant()
            )
            return True

        # Reject drop
        log.debug("Unknown item type dropped")
        return False

    def _on_unread_count_changed(
        self, _chat_list_stack: ChatListStack, workspace_id: str, count: int
    ) -> None:
        workspace = self._workspaces[workspace_id]
        workspace.set_unread_count(count)

    def _on_chat_selected(
        self, _chat_list_stack: ChatListStack, workspace_id: str, *args: Any
    ) -> None:
        self.activate_workspace(workspace_id)

    @staticmethod
    def _on_row_activated(_listbox: Gtk.ListBox, row: CommonWorkspace) -> None:
        if row.workspace_id == "add":
            open_window("WorkspaceDialog")
        else:
            app.window.activate_workspace(row.workspace_id)

    def add_workspace(self, workspace_id: str) -> None:
        row = Workspace(workspace_id, self.get_row_count() - 1)
        self._workspaces[workspace_id] = row

        self.insert(row, 0)

    def store_workspace_order(self) -> None:
        workspaces = list(self._iterate_rows())
        order = [row.workspace_id for row in workspaces]
        order.remove("add")
        app.settings.set_app_setting("workspace_order", order)

    def remove_workspace(self, workspace_id: str) -> None:
        row = self._workspaces.pop(workspace_id)
        self.remove(row)

    def get_other_workspace(self, exclude_workspace_id: str) -> str | None:
        for workspace in self._workspaces.values():
            if workspace.workspace_id != exclude_workspace_id:
                return workspace.workspace_id
        return None

    def activate_workspace(self, workspace_id: str) -> None:
        row = cast(CommonWorkspace | None, self.get_selected_row())
        if row is not None and row.workspace_id == workspace_id:
            return

        row = self._workspaces[workspace_id]
        self.select_row(row)

    def activate_workspace_number(self, number: int) -> None:
        row = cast(CommonWorkspace | None, self.get_row_at_index(number))
        if row is not None and row.workspace_id != "add":
            app.window.activate_workspace(row.workspace_id)

    def get_active_workspace(self) -> str | None:
        row = cast(CommonWorkspace | None, self.get_selected_row())
        if row is None:
            return None
        return row.workspace_id

    def get_first_workspace(self) -> str:
        for row in self._iterate_rows():
            return row.workspace_id
        return ""

    def get_workspace_by_id(self, workspace_id: str) -> CommonWorkspace | None:
        for row in self._iterate_rows():
            if row.workspace_id == workspace_id:
                return row
        return None

    def update_avatar(self, workspace_id: str) -> None:
        row = self._workspaces[workspace_id]
        row.update_avatar()


class CommonWorkspace(Gtk.ListBoxRow, SignalManager):
    def __init__(self, workspace_id: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)
        self.workspace_id = workspace_id
        self.index = 0

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)


class Workspace(CommonWorkspace):
    def __init__(self, workspace_id: str, index: int) -> None:
        CommonWorkspace.__init__(self, workspace_id)
        self.add_css_class("workspace-sidebar-item")

        self.index = index

        self._unread_label = Gtk.Label()
        self._unread_label.add_css_class("unread-counter")
        self._unread_label.set_visible(False)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)

        self._image = WorkspaceAvatar(workspace_id)
        self._image.set_halign(Gtk.Align.CENTER)

        selection_bar = Gtk.Box()
        selection_bar.set_size_request(6, -1)
        selection_bar.add_css_class("selection-bar")

        self._popover_menu = GajimPopover(None)

        item_box = Gtk.Box()
        item_box.append(selection_bar)
        item_box.append(self._image)
        item_box.append(self._popover_menu)

        overlay = Gtk.Overlay()
        overlay.set_child(item_box)
        overlay.add_overlay(self._unread_label)

        self._drag_hotspot_x: float = 0
        self._drag_hotspot_y: float = 0

        drag_source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        self._connect(drag_source, "prepare", self._on_prepare)
        self._connect(drag_source, "drag-begin", self._on_drag_begin)
        self._connect(drag_source, "drag-end", self._on_drag_end)
        self.add_controller(drag_source)

        controller = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(controller, "pressed", self._on_pressed)
        self.add_controller(controller)

        self.set_child(overlay)

    def _on_pressed(
        self,
        _gesture_click: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> bool:
        menu = get_workspace_menu(self.workspace_id)
        self._popover_menu.set_menu_model(menu)
        self._popover_menu.set_pointing_to_coord(x=x, y=y)
        self._popover_menu.popup()
        return Gdk.EVENT_STOP

    def update_avatar(self) -> None:
        self._image.update()

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text("999+")
        self._unread_label.set_visible(bool(count))

    def _on_prepare(
        self, _drag_source: Gtk.DragSource, x: float, y: float
    ) -> Gdk.ContentProvider:
        self._drag_hotspot_x = x
        self._drag_hotspot_y = y

        value = GObject.Value()
        value.init(Workspace)
        value.set_object(self)

        return Gdk.ContentProvider.new_for_value(value)

    def _on_drag_begin(self, _drag_source: Gtk.DragSource, drag: Gdk.Drag) -> None:
        texture = app.app.avatar_storage.get_workspace_texture(
            self.workspace_id, AvatarSize.WORKSPACE, 1
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


class AddWorkspace(CommonWorkspace):
    def __init__(self) -> None:
        CommonWorkspace.__init__(self, "add")

        self.index = 999

        self.set_selectable(False)
        self.set_tooltip_text(_("Add Workspace"))
        self.add_css_class("workspace-add")

        button = Gtk.Button(icon_name="feather-plus-symbolic")
        self._connect(button, "clicked", self._on_add_clicked)
        self.set_child(button)

    @staticmethod
    def _on_add_clicked(_button: Gtk.Button) -> None:
        open_window("WorkspaceDialog")


class WorkspaceAvatar(Gtk.Image):
    def __init__(self, workspace_id: str) -> None:
        Gtk.Image.__init__(self, pixel_size=AvatarSize.WORKSPACE)
        self._workspace_id = workspace_id
        self.add_css_class("workspace-avatar")
        self.update()

    def update(self) -> None:
        app.app.avatar_storage.invalidate_cache(self._workspace_id)
        scale = self.get_scale_factor()
        texture = app.app.avatar_storage.get_workspace_texture(
            self._workspace_id, AvatarSize.WORKSPACE, scale
        )
        self.set_from_paintable(texture)
        name = app.settings.get_workspace_setting(self._workspace_id, "name")
        self.set_tooltip_text(name)
