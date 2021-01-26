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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .avatar import generate_default_avatar
from .avatar_selector import AvatarSelector
from .util import get_builder
from .util import text_to_color


class WorkspaceDialog(Gtk.ApplicationWindow):
    def __init__(self, workspace_id=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('WorkspaceDialog')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Workspace'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_size_request(350, -1)

        self._workspace_id = workspace_id

        self._ui = get_builder('workspace_dialog.ui')
        self.add(self._ui.box)

        self._avatar_selector = AvatarSelector()
        self._avatar_selector.set_size_request(200, 200)
        self._ui.image_box.add(self._avatar_selector)

        if workspace_id is not None:
            name = app.settings.get_workspace_setting(
                workspace_id, 'name')
            rgba = Gdk.RGBA()  # TODO: Load setting
        else:
            name = _('My Workspace')
            rgba = Gdk.RGBA(*text_to_color(name))

        self._ui.entry.set_text(name)
        self._ui.color_chooser.set_rgba(rgba)
        self._generate_avatar()

        self._ui.connect_signals(self)

        self.connect('key-press-event', self._on_key_press_event)
        self.show_all()

    def _on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_cancel(self, _button):
        self.destroy()

    def _generate_avatar(self):
        name = self._ui.entry.get_text()
        if not name:
            return
        letter = name[:1].upper()
        scale = self.get_scale_factor()
        surface = generate_default_avatar(
            letter, name, AvatarSize.GROUP_INFO, scale, style='round-corners')
        self._ui.preview.set_from_surface(surface)

    def _get_avatar_data(self):
        if not self._avatar_selector.get_prepared():
            return None

        success, data, width, height = self._avatar_selector.get_avatar_bytes()
        if not success:
            return None

        return data

    def _on_save(self, _button):
        name = self._ui.entry.get_text()
        # rgba = self._ui.color_chooser.get_rgba()
        # color = rgba.to_string()
        # avatar = self._get_avatar_data()
        # use_image = self._ui.use_image.get_active()

        if self._workspace_id is not None:
            app.settings.set_workspace_setting(
                self._workspace_id, 'name', name)
            self.destroy()
            return

        app.window.activate_action(
            'add-workspace', GLib.Variant('s', name))
        self.destroy()
