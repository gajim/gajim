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
from gajim.common.configpaths import get_ui_path
from gajim.common.const import AvatarSize

from gajim.gtk.chat_list_row import ChatListRow
from gajim.gtk.menus import get_workspace_menu
from gajim.gtk.sidebar_listbox import SideBarListBoxRow
from gajim.gtk.structs import ChatListEntryParam
from gajim.gtk.util.misc import get_listbox_row_count
from gajim.gtk.util.misc import iterate_listbox_children
from gajim.gtk.util.window import open_window
from gajim.gtk.widgets import GajimPopover

if TYPE_CHECKING:
    # Simplifies testing
    from gajim.gtk.chat_list_stack import ChatListStack
    from gajim.gtk.chat_page import ChatPage

log = logging.getLogger("gajim.gtk.workspace_listbox")


@Gtk.Template(filename=get_ui_path("workspace_listbox.ui"))
class WorkspaceListBox(Gtk.ListBox):
    __gtype_name__ = "WorkspaceListBox"

    def __init__(self) -> None:
        Gtk.ListBox.__init__(self)

        formats_workspace = Gdk.ContentFormats.new_for_gtype(SideBarListBoxRow)
        formats_chat_list_row = Gdk.ContentFormats.new_for_gtype(ChatListRow)
        formats = formats_workspace.union(formats_chat_list_row)

        drop_target = Gtk.DropTarget(formats=formats, actions=Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

        self.set_sort_func(self._sort_func)

        self._popover_menu = GajimPopover(None)
        self._popover_menu.set_parent(self)

        self._workspaces: dict[str, SideBarListBoxRow] = {}

    def set_chat_page(self, chat_page: ChatPage) -> None:
        chat_list_stack = chat_page.get_chat_list_stack()
        chat_list_stack.connect("unread-count-changed", self._on_unread_count_changed)
        chat_list_stack.connect("chat-selected", self._on_chat_selected)

    def get_row_count(self) -> int:
        return get_listbox_row_count(self)

    def _iterate_rows(self) -> Iterator[SideBarListBoxRow]:
        for row in iterate_listbox_children(self):
            yield cast(SideBarListBoxRow, row)

    def _sort_func(self, row1: SideBarListBoxRow, row2: SideBarListBoxRow) -> int:
        return -1 if row1.index < row2.index else 1

    def _on_drop(
        self, _drop_target: Gtk.DropTarget, item: GObject.Value, _x: float, y: float
    ) -> bool:
        target_workspace = self.get_row_at_y(int(y))
        app.window.highlight_dnd_targets(self, False)

        if not item or not isinstance(target_workspace, SideBarListBoxRow):
            # Reject drop
            return False

        app.window.highlight_dnd_targets(item, False)

        if isinstance(item, SideBarListBoxRow):
            workspaces = list(self._iterate_rows())
            moved_workspace = workspaces.pop(item.index)
            workspaces.insert(target_workspace.get_index(), moved_workspace)

            for index, workspace in enumerate(workspaces):
                if workspace.item_id == "add-workspace":
                    continue
                workspace.index = index

            self.invalidate_sort()
            target_workspace.set_state_flags(Gtk.StateFlags.NORMAL, True)

            self.store_workspace_order()
            app.window.activate_workspace(item.item_id)
            return True

        if isinstance(item, ChatListRow):
            params = ChatListEntryParam(
                workspace_id=target_workspace.item_id,
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

    @Gtk.Template.Callback()
    def _on_row_activated(self, _listbox: Gtk.ListBox, row: SideBarListBoxRow) -> None:
        if row.item_id == "add-workspace":
            open_window("WorkspaceDialog")
        else:
            app.window.activate_workspace(row.item_id)

    def add_workspace(self, workspace_id: str) -> None:
        row = SideBarListBoxRow()
        row.set_workspace_id(workspace_id)
        row.set_secondary_callback(self._on_pressed)
        self._update_workspace_properties(row, workspace_id)

        row.index = self.get_row_count() - 1

        self._workspaces[workspace_id] = row

        self.insert(row, 0)

    def _update_workspace_properties(
        self, row: SideBarListBoxRow, workspace_id: str
    ) -> None:
        app.app.avatar_storage.invalidate_cache(workspace_id)
        scale = self.get_scale_factor()
        texture = app.app.avatar_storage.get_workspace_texture(
            workspace_id, AvatarSize.WORKSPACE, scale
        )
        row.set_from_paintable(texture)

        name = app.settings.get_workspace_setting(workspace_id, "name")
        row.set_tooltip_text(name)

    def store_workspace_order(self) -> None:
        workspaces = list(self._iterate_rows())
        order = [row.item_id for row in workspaces]
        order.remove("add-workspace")
        app.settings.set_app_setting("workspace_order", order)

    def remove_workspace(self, workspace_id: str) -> None:
        row = self._workspaces.pop(workspace_id)
        self.remove(row)

    def get_other_workspace(self, exclude_workspace_id: str) -> str | None:
        for workspace in self._workspaces.values():
            if workspace.item_id != exclude_workspace_id:
                return workspace.item_id
        return None

    def activate_workspace(self, workspace_id: str) -> None:
        row = cast(SideBarListBoxRow | None, self.get_selected_row())
        if row is not None and row.item_id == workspace_id:
            return

        row = self._workspaces[workspace_id]
        self.select_row(row)

    def activate_workspace_number(self, number: int) -> None:
        row = cast(SideBarListBoxRow | None, self.get_row_at_index(number))
        if row is not None and row.item_id != "add-workspace":
            app.window.activate_workspace(row.item_id)

    def get_active_workspace(self) -> str | None:
        row = cast(SideBarListBoxRow | None, self.get_selected_row())
        if row is None:
            return None
        return row.item_id

    def get_first_workspace(self) -> str:
        for row in self._iterate_rows():
            return row.item_id
        return ""

    def get_workspace_by_id(self, workspace_id: str) -> SideBarListBoxRow | None:
        for row in self._iterate_rows():
            if row.item_id == workspace_id:
                return row
        return None

    def update_avatar(self, workspace_id: str) -> None:
        row = self._workspaces[workspace_id]
        self._update_workspace_properties(row, workspace_id)

    def _on_pressed(
        self,
        _gesture_click: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
        row: SideBarListBoxRow,
    ) -> bool:

        res = row.translate_coordinates(self, x, y)
        if res is None:
            return Gdk.EVENT_PROPAGATE

        x, y = res
        menu = get_workspace_menu(row.item_id)
        self._popover_menu.set_menu_model(menu)
        self._popover_menu.set_pointing_to_coord(x=x, y=y)
        self._popover_menu.popup()
        return Gdk.EVENT_STOP
