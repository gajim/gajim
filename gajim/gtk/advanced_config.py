# Copyright (C) 2005 Travis Shirk <travis AT pobox.com>
#                    Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
#
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

from enum import IntEnum
from enum import unique

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import Q_

from gajim.common.setting_values import ADVANCED_SETTINGS
from gajim.common.setting_values import APP_SETTINGS
from gajim.gtk.util import get_builder


@unique
class Column(IntEnum):
    NAME = 0
    VALUE = 1
    TYPE = 2


BOOL_DICT = {
    True: _('Activated'),
    False: _('Deactivated')
}


SETTING_TYPES = {
    bool: Q_('?config type:Boolean'),
    int: Q_('?config type:Integer'),
    str: Q_('?config type:Text'),
}


class AdvancedConfig(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('AdvancedConfig')
        self.set_title(_('Advanced Configuration Editor (ACE)'))

        self._ui = get_builder('advanced_configuration.ui')
        self.add(self._ui.box)

        treeview = self._ui.advanced_treeview
        self.treeview = treeview
        self.model = Gtk.TreeStore(str, str, str)
        self._fill_model()
        self.model.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self.modelfilter = self.model.filter_new()
        self.modelfilter.set_visible_func(self._visible_func)

        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property('ellipsize', Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(Q_('?config:Preference Name'),
                                 renderer_text, text=0)
        treeview.insert_column(col, -1)
        col.props.expand = True
        col.props.sizing = Gtk.TreeViewColumnSizing.FIXED
        col.set_resizable(True)

        self.renderer_text = Gtk.CellRendererText()
        self.renderer_text.connect('edited', self._on_config_edited)
        self.renderer_text.set_property('ellipsize', Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(
            Q_('?config:Value'), self.renderer_text, text=1)
        treeview.insert_column(col, -1)
        col.set_cell_data_func(self.renderer_text,
                               self._value_column_data_callback)
        col.props.expand = True
        col.props.sizing = Gtk.TreeViewColumnSizing.FIXED
        col.set_resizable(True)

        renderer_text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(Q_('?config:Type'), renderer_text, text=2)
        treeview.insert_column(col, -1)
        col.props.sizing = Gtk.TreeViewColumnSizing.FIXED

        treeview.set_model(self.modelfilter)

        self.connect_after('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)
        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval != Gdk.KEY_Escape:
            return

        if self._ui.search_entry.get_text():
            self._ui.search_entry.set_text('')
            return

        self.destroy()

    def _value_column_data_callback(self, _col, cell, model, iter_, _data):
        opttype = model[iter_][Column.TYPE]
        cell.set_property('editable', opttype != SETTING_TYPES[bool])

    def _on_treeview_selection_changed(self, treeselection):
        model, iter_ = treeselection.get_selected()
        if not iter_:
            self._ui.reset_button.set_sensitive(False)
            return

        setting = model[iter_][Column.NAME]
        desc = ADVANCED_SETTINGS['app'][setting]

        self._ui.description.set_text(desc or Q_('?config description:None'))
        self._ui.reset_button.set_sensitive(True)

    def _on_treeview_row_activated(self, _treeview, path, _column):
        modelpath = self.modelfilter.convert_path_to_child_path(path)
        modelrow = self.model[modelpath]
        setting = modelrow[Column.NAME]

        if modelrow[Column.TYPE] != SETTING_TYPES[bool]:
            return

        setting_value = modelrow[Column.VALUE] != _('Activated')
        column_value = BOOL_DICT[setting_value]

        app.settings.set(setting, setting_value)
        modelrow[Column.VALUE] = column_value

    def _on_config_edited(self, _cell, path, text):
        path = Gtk.TreePath.new_from_string(path)
        modelpath = self.modelfilter.convert_path_to_child_path(path)
        modelrow = self.model[modelpath]
        setting = modelrow[Column.NAME]

        app.settings.set(setting, text)
        modelrow[Column.VALUE] = text

    def _on_reset_button_clicked(self, button):
        model, iter_ = self.treeview.get_selection().get_selected()
        if not iter_:
            return

        setting = model[iter_][Column.NAME]
        default = APP_SETTINGS[setting]

        if isinstance(default, bool):
            model[iter_][Column.VALUE] = BOOL_DICT[default]
        else:
            model[iter_][Column.VALUE] = default

        app.settings.set(setting, default)
        button.set_sensitive(False)

    def _fill_model(self, node=None, parent=None):
        for category, settings in ADVANCED_SETTINGS.items():
            if category != 'app':
                continue

            for setting, description in settings.items():
                value = app.settings.get(setting)
                if isinstance(value, bool):
                    value = BOOL_DICT[value]
                    type_ = SETTING_TYPES[bool]

                elif isinstance(value, int):
                    value = str(value)
                    type_ = SETTING_TYPES[int]

                elif isinstance(value, str):
                    type_ = SETTING_TYPES[str]

                else:
                    raise ValueError

                self.model.append(parent, [setting, value, type_])

    def _visible_func(self, model, treeiter, _data):
        search_string = self._ui.search_entry.get_text().lower()
        if not search_string:
            return True

        setting = model[treeiter][Column.NAME]
        desc = ADVANCED_SETTINGS['app'][setting]

        if search_string in setting or search_string in desc.lower():
            return True
        return False

    def _on_search_entry_changed(self, _widget):
        self.modelfilter.refilter()
