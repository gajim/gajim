# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging
import pickle

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.chat_list_stack import ChatListStack
from gajim.gtk.chat_page import ChatPage
from gajim.gtk.menus import get_workspace_menu
from gajim.gtk.structs import ChatListEntryParam
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import open_window

log = logging.getLogger('gajim.gtk.workspace_sidebar')


class WorkspaceSideBar(Gtk.ListBox):
    def __init__(self, chat_page: ChatPage) -> None:
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.set_valign(Gtk.Align.START)
        self.get_style_context().add_class('workspace-sidebar')

        # Drag and Drop
        entries = [
            Gtk.TargetEntry.new(
                'WORKSPACE_SIDEBAR_ITEM',
                Gtk.TargetFlags.SAME_APP,
                0),
            Gtk.TargetEntry.new(
                'CHAT_LIST_ITEM',
                Gtk.TargetFlags.SAME_APP,
                0)
        ]
        self.drag_dest_set(
            Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP,
            entries,
            Gdk.DragAction.MOVE)

        self.drag_row: Workspace | None = None
        self.row_before: CommonWorkspace | None = None
        self.row_after: CommonWorkspace | None = None

        self.connect('drag-motion', self._on_drag_motion)
        self.connect('drag-data-received', self._on_drag_data_received)
        self.connect('row-activated', self._on_row_activated)

        self.add(AddWorkspace('add'))

        chat_list_stack = chat_page.get_chat_list_stack()
        chat_list_stack.connect('unread-count-changed',
                                self._on_unread_count_changed)
        chat_list_stack.connect('chat-selected',
                                self._on_chat_selected)
        self._workspaces: dict[str, Workspace] = {}

    def _on_drag_motion(self,
                        _widget: Gtk.Widget,
                        _drag_context: Gdk.DragContext,
                        _x_coord: int,
                        y_coord: int,
                        _time: int
                        ) -> bool:
        row = cast(CommonWorkspace, self.get_row_at_y(y_coord))

        if row:
            alloc = row.get_allocation()
            hover_row_y = alloc.y
            hover_row_height = alloc.height
            if y_coord < hover_row_y + hover_row_height / 2:
                self.row_after = row
                self.row_before = self._get_row_before(row)
            else:
                self.row_before = row
                self.row_after = self._get_row_after(row)
        else:
            self.row_before = self._get_last_workspace_row()
            self.row_after = None

        return self.drag_row not in (self.row_before, self.row_after)

    def _on_drag_data_received(self,
                               _widget: Gtk.Widget,
                               _drag_context: Gdk.DragContext,
                               _x_coord: int,
                               y_coord: int,
                               selection_data: Gtk.SelectionData,
                               _info: int,
                               _time: int
                               ) -> None:
        data = selection_data.get_data()
        item_type = selection_data.get_data_type().name()
        if item_type == 'WORKSPACE_SIDEBAR_ITEM':
            self._process_workspace_drop(data.decode('utf-8'))
        elif item_type == 'CHAT_LIST_ITEM':
            account, jid, source_workspace = pickle.loads(data)
            self._process_chat_list_drop(
                account, jid, source_workspace, y_coord)
        else:
            log.debug('Unknown item type dropped')

    def _process_workspace_drop(self, workspace_id: str) -> None:
        row = self.get_workspace_by_id(workspace_id)

        if row == self.row_after:
            return
        if row is None:
            return

        self.remove(row)

        if self.row_after:
            pos = self.row_after.get_index()
        elif self.row_before and self.row_before.workspace_id != 'add':
            pos = self.row_before.get_index() + 1
        else:
            pos = len(self.get_children()) - 1

        self.insert(row, pos)
        self.store_workspace_order()
        app.window.activate_workspace(workspace_id)

    def _process_chat_list_drop(self,
                                account: str,
                                jid: JID,
                                source_workspace: str,
                                y_coord: int) -> None:

        workspace_row = cast(Workspace, self.get_row_at_y(y_coord))

        workspace_id = workspace_row.workspace_id
        if workspace_row.workspace_id == 'add':
            workspace_id = ''

        params = ChatListEntryParam(workspace_id=workspace_id,
                                    source_workspace_id=source_workspace,
                                    account=account,
                                    jid=jid)
        app.window.activate_action('move-chat-to-workspace',
                                   params.to_variant())

    def _get_row_before(self,
                        row: CommonWorkspace
                        ) -> CommonWorkspace | None:
        workspace = cast(
            CommonWorkspace, self.get_row_at_index(row.get_index() - 1))
        return workspace

    def _get_row_after(self,
                       row: CommonWorkspace
                       ) -> CommonWorkspace | None:
        workspace = cast(
            CommonWorkspace, self.get_row_at_index(row.get_index() + 1))
        return workspace

    def _get_last_workspace_row(self) -> Workspace:
        # Calling len(children) would include AddWorkspace
        last_workspace = cast(
            Workspace, self.get_row_at_index(len(self.get_children()) - 1))
        return last_workspace

    def set_drag_row(self, row: Workspace) -> None:
        self.drag_row = row

    def _on_unread_count_changed(self,
                                 _chat_list_stack: ChatListStack,
                                 workspace_id: str,
                                 count: int
                                 ) -> None:
        workspace = self._workspaces[workspace_id]
        workspace.set_unread_count(count)

    def _on_chat_selected(self,
                          _chat_list_stack: ChatListStack,
                          workspace_id: str,
                          *args: Any) -> None:
        self.activate_workspace(workspace_id)

    @staticmethod
    def _on_row_activated(_listbox: Gtk.ListBox,
                          row: CommonWorkspace
                          ) -> None:
        if row.workspace_id == 'add':
            open_window('WorkspaceDialog')
        else:
            app.window.activate_workspace(row.workspace_id)

    def add_workspace(self, workspace_id: str) -> None:
        row = Workspace(workspace_id)
        self._workspaces[workspace_id] = row
        # Insert row before AddWorkspace row
        self.insert(row, len(self.get_children()) - 1)

    def store_workspace_order(self) -> None:
        workspaces = cast(list[CommonWorkspace], self.get_children())
        order = [row.workspace_id for row in workspaces]
        order.remove('add')
        app.settings.set_app_setting('workspace_order', order)

    def remove_workspace(self, workspace_id: str) -> None:
        row = self._workspaces.pop(workspace_id)
        self.remove(row)

    def get_other_workspace(self,
                            exclude_workspace_id: str
                            ) -> str | None:

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
        if row is not None and row.workspace_id != 'add':
            app.window.activate_workspace(row.workspace_id)

    def get_active_workspace(self) -> str | None:
        row = cast(CommonWorkspace | None, self.get_selected_row())
        if row is None:
            return None
        return row.workspace_id

    def get_first_workspace(self) -> str:
        workspaces = cast(list[CommonWorkspace], self.get_children())
        for row in workspaces:
            return row.workspace_id
        return ''

    def get_workspace_by_id(self,
                            workspace_id: str
                            ) -> CommonWorkspace | None:
        workspaces = cast(list[CommonWorkspace], self.get_children())
        for row in workspaces:
            if row.workspace_id == workspace_id:
                return row
        return None

    def update_avatar(self, workspace_id: str) -> None:
        row = self._workspaces[workspace_id]
        row.update_avatar()


class CommonWorkspace(Gtk.ListBoxRow):
    def __init__(self, workspace_id: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.workspace_id = workspace_id


class Workspace(CommonWorkspace):
    def __init__(self, workspace_id: str) -> None:
        CommonWorkspace.__init__(self, workspace_id)
        self.get_style_context().add_class('workspace-sidebar-item')

        self._unread_label = Gtk.Label()
        self._unread_label.get_style_context().add_class(
            'unread-counter')
        self._unread_label.set_no_show_all(True)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)

        self._image = WorkspaceAvatar(workspace_id)
        self._image.set_halign(Gtk.Align.CENTER)

        selection_bar = Gtk.Box()
        selection_bar.set_size_request(6, -1)
        selection_bar.get_style_context().add_class('selection-bar')

        item_box = Gtk.Box()
        item_box.add(selection_bar)
        item_box.add(self._image)

        overlay = Gtk.Overlay()
        overlay.add(item_box)
        overlay.add_overlay(self._unread_label)

        # Drag and Drop
        entries = [Gtk.TargetEntry.new(
            'WORKSPACE_SIDEBAR_ITEM',
            Gtk.TargetFlags.SAME_APP,
            0)]
        eventbox = Gtk.EventBox()
        eventbox.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            entries,
            Gdk.DragAction.MOVE)
        eventbox.connect('drag-begin', self._on_drag_begin)
        eventbox.connect('drag-end', self._on_drag_end)
        eventbox.connect('drag-data-get', self._on_drag_data_get)
        eventbox.connect('button-press-event', self._popup_menu)
        eventbox.add(overlay)
        self.add(eventbox)
        self.show_all()

    def _popup_menu(self, _widget: Gtk.Widget, event: Gdk.EventButton) -> None:
        if event.button != Gdk.BUTTON_SECONDARY:
            return

        menu = get_workspace_menu(self.workspace_id)

        popover = GajimPopover(menu, relative_to=self, event=event)
        popover.popup()

    def update_avatar(self) -> None:
        self._image.update()

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text('999+')
        self._unread_label.set_visible(bool(count))

    def _on_drag_begin(self,
                       row: Workspace,
                       drag_context: Gdk.DragContext
                       ) -> None:

        scale = self.get_scale_factor()
        surface = app.app.avatar_storage.get_workspace_surface(
            self.workspace_id, AvatarSize.WORKSPACE, scale)
        if surface is not None:
            Gtk.drag_set_icon_surface(drag_context, surface)

        listbox = cast(WorkspaceSideBar, self.get_parent())
        listbox.set_drag_row(self)

        app.window.highlight_dnd_targets(row, True)

    def _on_drag_end(self,
                     row: Workspace,
                     drag_context: Gdk.DragContext
                     ) -> None:

        app.window.highlight_dnd_targets(row, False)

    def _on_drag_data_get(self,
                          _widget: Gtk.Widget,
                          _drag_context: Gdk.DragContext,
                          selection_data: Gtk.SelectionData,
                          _info: int,
                          _time: int
                          ) -> None:
        drop_type = Gdk.Atom.intern_static_string('WORKSPACE_SIDEBAR_ITEM')
        data = self.workspace_id.encode('utf-8')
        selection_data.set(drop_type, 8, data)


class AddWorkspace(CommonWorkspace):
    def __init__(self, workspace_id: str) -> None:
        CommonWorkspace.__init__(self, workspace_id)
        self.set_selectable(False)
        self.set_tooltip_text(_('Add Workspace'))
        self.get_style_context().add_class('workspace-add')
        button = Gtk.Button.new_from_icon_name('list-add-symbolic',
                                               Gtk.IconSize.BUTTON)
        button.connect('clicked', self._on_add_clicked)
        self.add(button)
        self.show_all()

    @staticmethod
    def _on_add_clicked(_button: Gtk.Button) -> None:
        open_window('WorkspaceDialog')


class WorkspaceAvatar(Gtk.Image):
    def __init__(self, workspace_id: str) -> None:
        Gtk.Image.__init__(self)
        self._workspace_id = workspace_id
        self.get_style_context().add_class('workspace-avatar')
        self.update()

    def update(self) -> None:
        app.app.avatar_storage.invalidate_cache(self._workspace_id)
        scale = self.get_scale_factor()
        surface = app.app.avatar_storage.get_workspace_surface(
            self._workspace_id, AvatarSize.WORKSPACE, scale)
        self.set_from_surface(surface)
        name = app.settings.get_workspace_setting(self._workspace_id, 'name')
        self.set_tooltip_text(name)
