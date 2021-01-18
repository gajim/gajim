
from gi.repository import Gtk
from gajim.common.const import AvatarSize
from gajim.common import app

from gajim.gui.avatar import generate_default_avatar


class WorkspaceSideBar(Gtk.ListBox):
    def __init__(self):
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.set_valign(Gtk.Align.START)

    def add_workspace(self, workspace_id):
        self.add(Workspace(workspace_id))

    def remove_workspace(self, workspace_id):
        pass


class Workspace(Gtk.ListBoxRow):
    def __init__(self, workspace_id):
        Gtk.ListBoxRow.__init__(self)

        self._workspace_id = workspace_id
        name = app.settings.get_workspace_setting(workspace_id, 'name')
        letter = name[:2]

        scale = self.get_scale_factor()
        surface = generate_default_avatar(
            letter, name, AvatarSize.WORKSPACE, scale)
        self._image = Gtk.Image.new_from_surface(surface)
        self.add(self._image)
        self.show_all()
