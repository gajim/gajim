
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .util import open_window


class WorkspaceSideBar(Gtk.ListBox):
    def __init__(self, chat_list_stack):
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.set_valign(Gtk.Align.START)
        self.get_style_context().add_class('workspace-sidebar')

        # Drag and Drop
        entries = [Gtk.TargetEntry.new(
            'WORKSPACE_SIDEBAR_ITEM',
            Gtk.TargetFlags.SAME_APP,
            0)]
        self.drag_dest_set(
            Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP,
            entries,
            Gdk.DragAction.MOVE)

        self.drag_row = None
        self.row_before = None
        self.row_after = None

        self.connect('drag-motion', self._on_drag_motion)
        self.connect('drag-data-received', self._on_drag_data_received)
        self.connect('drag-leave', self._on_drag_leave)

        self.connect('row-activated', self._on_row_activated)

        self.add(AddWorkspace('add'))

        chat_list_stack.connect('unread-count-changed',
                                self._on_unread_count_changed)
        chat_list_stack.connect('chat-selected',
                                self._on_chat_selected)
        self._workspaces = {}

    def _on_drag_motion(self, _widget, _drag_context, _x_coord, y_coord,
                        _time):
        row = self.get_row_at_y(y_coord)

        if self.row_before:
            self.row_before.get_style_context().remove_class(
                'drag-hover-bottom')
        if self.row_after:
            self.row_after.get_style_context().remove_class(
                'drag-hover-top')

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

        if self.row_before and self.row_before.workspace_id != 'add':
            self.row_before.get_style_context().add_class('drag-hover-bottom')
        if self.row_after:
            self.row_after.get_style_context().add_class('drag-hover-top')
        return True

    def _on_drag_data_received(self, _widget, _drag_context, _x_coord,
                               _y_coord, selection_data, _info, _time):
        if self.row_before:
            self.row_before.get_style_context().remove_class(
                'drag-hover-bottom')
        if self.row_after:
            self.row_after.get_style_context().remove_class(
                'drag-hover-top')

        data = selection_data.get_data()
        workspace_id = data.decode('utf-8')
        row = self.get_workspace_by_id(workspace_id)

        if row in (self.row_after, None):
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

    def _on_drag_leave(self, _widget, _drag_context, _time):
        if self.row_before:
            self.row_before.get_style_context().remove_class(
                'drag-hover-bottom')
        if self.row_after:
            self.row_after.get_style_context().remove_class(
                'drag-hover-top')

    def _get_row_before(self, row):
        return self.get_row_at_index(row.get_index() - 1)

    def _get_row_after(self, row):
        return self.get_row_at_index(row.get_index() + 1)

    def _get_last_workspace_row(self):
        # len(children) would include AddWorkspace
        return self.get_row_at_index(len(self.get_children()) - 1)

    def set_drag_row(self, row):
        self.drag_row = row

    def _on_unread_count_changed(self, _chat_list_stack, workspace_id, count):
        workspace = self._workspaces[workspace_id]
        workspace.set_unread_count(count)

    def _on_chat_selected(self, _chat_list_stack, workspace_id, *args):
        self.activate_workspace(workspace_id)

    @staticmethod
    def _on_row_activated(_listbox, row):
        if row.workspace_id == 'add':
            open_window('WorkspaceDialog')
        else:
            app.window.activate_workspace(row.workspace_id)

    def add_workspace(self, workspace_id):
        row = Workspace(workspace_id)
        self._workspaces[workspace_id] = row
        # Insert row before AddWorkspace row
        self.insert(row, len(self.get_children()) - 1)

    def store_workspace_order(self):
        order = [row.workspace_id for row in self.get_children()]
        order.remove('add')
        app.settings.set_app_setting('workspace_order', order)

    def remove_workspace(self, workspace_id):
        if len(self._workspaces) == 1:
            return False
        row = self._workspaces.pop(workspace_id)
        self.remove(row)
        return True

    def activate_workspace(self, workspace_id):
        row = self.get_selected_row()
        if row is not None and row.workspace_id == workspace_id:
            return

        row = self._workspaces[workspace_id]
        self.select_row(row)

    def get_active_workspace(self):
        row = self.get_selected_row()
        if row is None:
            return None
        return row.workspace_id

    def get_first_workspace(self):
        for row in self.get_children():
            return row.workspace_id

    def get_workspace_by_id(self, workspace_id):
        for row in self.get_children():
            if row.workspace_id == workspace_id:
                return row
        return None

    def update_avatar(self, workspace_id):
        row = self._workspaces[workspace_id]
        row.update_avatar()


class CommonWorkspace(Gtk.ListBoxRow):
    def __init__(self, workspace_id):
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class('workspace-sidebar-item')

        self.workspace_id = workspace_id


class Workspace(CommonWorkspace):
    def __init__(self, workspace_id):
        CommonWorkspace.__init__(self, workspace_id)

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
        eventbox.add(overlay)

        self.add(eventbox)
        self.show_all()

    def update_avatar(self):
        self._image.update()

    def set_unread_count(self, count):
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text('999+')
        self._unread_label.set_visible(bool(count))

    def _on_drag_begin(self, _widget, drag_context):
        scale = self.get_scale_factor()
        surface = app.interface.avatar_storage.get_workspace_surface(
            self.workspace_id, AvatarSize.WORKSPACE, scale)
        Gtk.drag_set_icon_surface(drag_context, surface)

        listbox = self.get_parent()
        listbox.set_drag_row(self)

    def _on_drag_data_get(self, _widget, _drag_context, selection_data,
                          _info, _time):
        drop_type = Gdk.Atom.intern_static_string('WORKSPACE_SIDEBAR_ITEM')
        data = self.workspace_id.encode('utf-8')
        selection_data.set(drop_type, 32, data)


class AddWorkspace(CommonWorkspace):
    def __init__(self, workspace_id):
        CommonWorkspace.__init__(self, workspace_id)
        self.set_selectable(False)
        self.set_tooltip_text(_('Add Workspace'))
        self.get_style_context().add_class('workspace-add')

        image = Gtk.Image.new_from_icon_name('list-add-symbolic',
                                             Gtk.IconSize.DND)
        self.add(image)
        self.show_all()


class WorkspaceAvatar(Gtk.Image):
    def __init__(self, workspace_id):
        Gtk.Image.__init__(self)
        self._workspace_id = workspace_id
        self.update()

    def update(self):
        scale = self.get_scale_factor()
        surface = app.interface.avatar_storage.get_workspace_surface(
            self._workspace_id, AvatarSize.WORKSPACE, scale)
        self.set_from_surface(surface)
        name = app.settings.get_workspace_setting(self._workspace_id, 'name')
        self.set_tooltip_text(name)
