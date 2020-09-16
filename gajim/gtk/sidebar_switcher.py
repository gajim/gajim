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


class SideBarSwitcher(Gtk.ListBox):
    def __init__(self):
        Gtk.ListBox.__init__(self)
        self._stack = None
        self.get_style_context().add_class('settings-menu')
        self.connect('row-activated', self._on_row_activated)

    def set_stack(self, stack):
        self._stack = stack
        for page in self._stack.get_children():
            attributes = ['name', 'title', 'icon-name']
            properties = self._stack.child_get(page, *attributes)
            self.add(Row(*properties))

        self._select_first_row()

    def _on_row_activated(self, _listbox, row):
        self._stack.set_visible_child_name(row.name)

    def _select_first_row(self):
        self.select_row(self.get_row_at_index(0))


class Row(Gtk.ListBoxRow):
    def __init__(self, name, title, icon_name):
        Gtk.ListBoxRow.__init__(self)

        self.name = name
        box = Gtk.Box()
        if icon_name:
            image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            image.get_style_context().add_class('dim-label')
            box.add(image)

        label = Gtk.Label(label=title)
        label.set_xalign(0)
        box.add(label)
        self.add(box)
