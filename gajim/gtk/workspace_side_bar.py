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
from typing import List
from typing import Optional
from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .chat_list_stack import ChatListStack
from .chat_page import ChatPage
from .structs import ChatListEntryParam
from .util import open_window

log = logging.getLogger('gajim.gui.workspace_sidebar')


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

        self.drag_row: Optional[Workspace] = None
        self.row_before: Optional[CommonWorkspace] = None
        self.row_after: Optional[CommonWorkspace] = None

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

        if self.drag_row in (self.row_before, self.row_after):
            return False

        return True

    def _on_drag_data_received(self,
                               _widget: Gtk.Widget,
                               _drag_context: Gdk.DragContext,
                               _x_coord: int,
                               y_coord: int,
                               selection_data: Gtk.SelectionData,
                               _info: int,
                               _time: int
                               ) -> None:
        data = selection_data.get_data().decode('utf-8')
        item_type = selection_data.get_data_type().name()
        if item_type == 'WORKSPACE_SIDEBAR_ITEM':
            self._process_workspace_drop(data)
        elif item_type == 'CHAT_LIST_ITEM':
            self._process_chat_list_drop(data, y_coord)
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

    def _process_chat_list_drop(self, identifier: str, y_coord: int) -> None:
        account, jid = identifier.split()
        jid = JID.from_string(jid)
        workspace_row = cast(Workspace, self.get_row_at_y(y_coord))
        if workspace_row.workspace_id == 'add':
            app.window.move_chat_to_new_workspace(
                account, jid)
            return

        params = ChatListEntryParam(workspace_id=workspace_row.workspace_id,
                                    account=account,
                                    jid=jid)
        app.window.activate_action('move-chat-to-workspace',
                                   params.to_variant())

    def _get_row_before(self,
                        row: CommonWorkspace
                        ) -> Optional[CommonWorkspace]:
        workspace = cast(
            CommonWorkspace, self.get_row_at_index(row.get_index() - 1))
        return workspace

    def _get_row_after(self,
                       row: CommonWorkspace
                       ) -> Optional[CommonWorkspace]:
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
        workspaces: list[CommonWorkspace] = cast(
            list[CommonWorkspace], self.get_children())
        order: list[str] = [row.workspace_id for row in workspaces]
        order.remove('add')
        app.settings.set_app_setting('workspace_order', order)

    def remove_workspace(self, workspace_id: str) -> bool:
        if len(self._workspaces) == 1:
            return False
        row = self._workspaces.pop(workspace_id)
        self.remove(row)
        return True

    def activate_workspace(self, workspace_id: str) -> None:
        row = cast(CommonWorkspace, self.get_selected_row())
        if row is not None and row.workspace_id == workspace_id:
            return

        row = self._workspaces[workspace_id]
        self.select_row(row)

    def get_active_workspace(self) -> Optional[str]:
        row = cast(CommonWorkspace, self.get_selected_row())
        if row is None:
            return None
        return row.workspace_id

    def get_first_workspace(self) -> str:
        workspaces: list[CommonWorkspace] = cast(
            list[CommonWorkspace], self.get_children())
        for row in workspaces:
            return row.workspace_id
        return ''

    def get_workspace_by_id(self,
                            workspace_id: str
                            ) -> Optional[CommonWorkspace]:
        workspaces: list[CommonWorkspace] = cast(
            list[CommonWorkspace], self.get_children())
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
        eventbox.connect('drag-data-get', self._on_drag_data_get)
        eventbox.connect('button-press-event', self._popup_menu)
        eventbox.add(overlay)
        self.add(eventbox)
        self.show_all()

    def _popup_menu(self, _widget: Gtk.Widget, event: Gdk.EventButton) -> None:
        if event.button != 3:  # right click
            return

        menu = self._get_workspace_menu()

        rectangle = Gdk.Rectangle()
        rectangle.x = int(event.x)
        rectangle.y = int(event.y)
        rectangle.width = rectangle.height = 1

        popover = Gtk.Popover.new_from_model(self, menu)
        popover.set_relative_to(self)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.set_pointing_to(rectangle)
        popover.popup()

    def _get_workspace_menu(self) -> Gio.Menu:
        menu_items: List[Any] = [
            ('edit-workspace', _('Edit…')),
        ]
        menu = Gio.Menu()
        for item in menu_items:
            action, label = item
            action = f'win.{action}'
            menuitem = Gio.MenuItem.new(label, action)
            variant = GLib.Variant('s', self.workspace_id)
            menuitem.set_action_and_target_value(action, variant)
            menu.append_item(menuitem)
        return menu

    def update_avatar(self) -> None:
        self._image.update()

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text('999+')
        self._unread_label.set_visible(bool(count))

    def _on_drag_begin(self,
                       _widget: Gtk.Widget,
                       drag_context: Gdk.DragContext
                       ) -> None:
        scale = self.get_scale_factor()
        surface = app.app.avatar_storage.get_workspace_surface(
            self.workspace_id, AvatarSize.WORKSPACE, scale)
        if surface is not None:
            Gtk.drag_set_icon_surface(drag_context, surface)

        listbox = cast(WorkspaceSideBar, self.get_parent())
        listbox.set_drag_row(self)

    def _on_drag_data_get(self,
                          _widget: Gtk.Widget,
                          _drag_context: Gdk.DragContext,
                          selection_data: Gtk.SelectionData,
                          _info: int,
                          _time: int
                          ) -> None:
        drop_type = Gdk.Atom.intern_static_string('WORKSPACE_SIDEBAR_ITEM')
        data = self.workspace_id.encode('utf-8')
        selection_data.set(drop_type, 32, data)


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
        self.update()

    def update(self) -> None:
        app.app.avatar_storage.invalidate_cache(self._workspace_id)
        scale = self.get_scale_factor()
        surface = app.app.avatar_storage.get_workspace_surface(
            self._workspace_id, AvatarSize.WORKSPACE, scale)
        self.set_from_surface(surface)
        name = app.settings.get_workspace_setting(self._workspace_id, 'name')
        self.set_tooltip_text(name)
