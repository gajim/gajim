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

from typing import Any
from typing import Optional

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .avatar import make_workspace_avatar
from .avatar_selector import AvatarSelector
from .dialogs import ConfirmationDialog
from .dialogs import DialogButton
from .builder import get_builder
from .util import rgba_to_float
from .util import make_rgba
from .const import DEFAULT_WORKSPACE_COLOR


class WorkspaceDialog(Gtk.ApplicationWindow):
    def __init__(self, workspace_id: Optional[str] = None) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('WorkspaceDialog')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Workspace Settings'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_size_request(500, 600)

        self._workspace_id = workspace_id

        self._ui = get_builder('workspace_dialog.ui')
        self.add(self._ui.box)

        self._avatar_selector = AvatarSelector()
        self._avatar_selector.set_size_request(200, 200)
        self._ui.image_box.add(self._avatar_selector)

        name: str = _('My Workspace')
        color: Optional[str] = None
        self._avatar_sha: Optional[str] = None

        if len(app.settings.get_workspaces()) == 1:
            # Don't allow to remove last workspace
            self._ui.remove_workspace_button.set_sensitive(False)

        if workspace_id is None:
            # This is a new workspace
            self._ui.remove_workspace_button.set_sensitive(False)
        else:
            name = app.settings.get_workspace_setting(
                workspace_id, 'name')
            color = app.settings.get_workspace_setting(
                workspace_id, 'color')
            self._avatar_sha = app.settings.get_workspace_setting(
                workspace_id, 'avatar_sha')
            if self._avatar_sha == '':
                self._avatar_sha = None

        rgba = make_rgba(color or DEFAULT_WORKSPACE_COLOR)
        if self._avatar_sha is not None:
            self._ui.image_switch.set_state(True)
            self._ui.style_stack.set_visible_child_name('image')

        self._ui.entry.set_text(name)
        self._ui.color_chooser.set_rgba(rgba)
        self._update_avatar()
        self._ui.save_button.grab_default()

        self._ui.connect_signals(self)

        self.connect('key-press-event', self._on_key_press)
        self.show_all()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_remove_workspace(self, _button: Gtk.Button) -> None:
        def _on_remove():
            assert self._workspace_id is not None
            app.window.remove_workspace(self._workspace_id)
            self.destroy()
        assert self._workspace_id is not None
        chat_list = app.window.get_chat_list(self._workspace_id)
        open_chats = chat_list.get_open_chats()
        if len(open_chats) > 0:
            ConfirmationDialog(
                _('Remove Workspace'),
                _('Remove Workspace'),
                _('This workspace contains chats. Remove anyway?'),
                [DialogButton.make('Cancel',
                                   text=_('_No')),
                 DialogButton.make('Remove',
                                   callback=_on_remove)]).show()
            return
        # No chats in chat list, it is save to remove workspace
        _on_remove()

    def _on_cancel(self, _button: Gtk.Button) -> None:
        self.destroy()

    def _on_color_set(self, _button: Gtk.ColorButton) -> None:
        self._update_avatar()

    def _on_text_changed(self, entry: Gtk.Entry, _param: Any) -> None:
        self._ui.save_button.set_sensitive(bool(entry.get_text()))
        self._update_avatar()

    def _on_image_switch_toggled(self, switch: Gtk.Switch, *args: Any) -> None:
        if switch.get_active():
            self._ui.style_stack.set_visible_child_name('image')
            if self._workspace_id is not None:
                self._avatar_sha = app.settings.get_workspace_setting(
                    self._workspace_id, 'avatar_sha')
                if self._avatar_sha == '':
                    self._avatar_sha = None
        else:
            self._ui.style_stack.set_visible_child_name('color')
            self._avatar_sha = None
        self._update_avatar()

    def _update_avatar(self) -> None:
        name = self._ui.entry.get_text()
        rgba = self._ui.color_chooser.get_rgba()
        scale = self.get_scale_factor()
        if self._avatar_sha is not None:
            assert self._workspace_id is not None
            surface = app.app.avatar_storage.get_workspace_surface(
                self._workspace_id,
                AvatarSize.WORKSPACE_EDIT,
                scale)
        else:
            surface = make_workspace_avatar(
                name[:1].upper(),
                rgba_to_float(rgba),
                AvatarSize.WORKSPACE_EDIT,
                scale)
        self._ui.preview.set_from_surface(surface)

    def _get_avatar_data(self) -> Optional[bytes]:
        if not self._avatar_selector.get_prepared():
            return None

        success, data, _wid, _hei = self._avatar_selector.get_avatar_bytes()
        if not success:
            return None

        return data

    def _on_save(self, _button: Gtk.Button) -> None:
        name = self._ui.entry.get_text()
        rgba = self._ui.color_chooser.get_rgba()
        use_image = self._ui.image_switch.get_active()
        if use_image:
            data = self._get_avatar_data()
            if data is not None:
                self._avatar_sha = app.interface.save_avatar(data)

        if self._workspace_id is not None:
            app.settings.set_workspace_setting(
                self._workspace_id, 'name', name)
            app.settings.set_workspace_setting(
                self._workspace_id, 'color', rgba.to_string())
            if self._avatar_sha is None:
                app.settings.set_workspace_setting(
                    self._workspace_id, 'avatar_sha', '')
            else:
                app.settings.set_workspace_setting(
                    self._workspace_id, 'avatar_sha', self._avatar_sha)

            app.window.update_workspace(self._workspace_id)
            self.destroy()
            return

        workspace_id = app.settings.add_workspace(name)
        app.settings.set_workspace_setting(
            workspace_id, 'color', rgba.to_string())
        if self._avatar_sha is not None:
            app.settings.set_workspace_setting(
                workspace_id, 'avatar_sha', self._avatar_sha)

        app.window.add_workspace(workspace_id)
        self.destroy()
