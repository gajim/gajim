# Copyright (C) 2005 Travis Shirk <travis AT pobox.com>
#                    Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from enum import IntEnum
from enum import unique

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.setting_values import ADVANCED_SETTINGS
from gajim.common.setting_values import APP_SETTINGS

from gajim.gtk.builder import get_builder
from gajim.gtk.window import GajimAppWindow


@unique
class Column(IntEnum):
    NAME = 0
    VALUE = 1
    TYPE = 2
    IS_DEFAULT = 3


BOOL_DICT = {True: _("Activated"), False: _("Deactivated")}


SETTING_TYPES = {
    bool: p_("Configuration type", "Boolean"),
    int: p_("Configuration type", "Integer"),
    str: p_("Configuration type", "Text"),
}


class AdvancedConfig(GajimAppWindow):
    def __init__(self, transient_for: Gtk.Window | None) -> None:
        GajimAppWindow.__init__(
            self,
            name="AdvancedConfig",
            title=_("Advanced Configuration Editor (ACE)"),
            modal=True,
            transient_for=transient_for,
            add_window_padding=True,
            header_bar=True,
        )

        self._ui = get_builder("advanced_configuration.ui")

        self.set_child(self._ui.box)

        self._connect(self._ui.reset_button, "clicked", self._on_reset_button_clicked)
        self._connect(
            self._ui.search_entry, "search-changed", self._on_search_entry_changed
        )
        self._connect(
            self._ui.advanced_treeview, "row-activated", self._on_treeview_row_activated
        )
        self._connect(
            self._ui.treeview_selection, "changed", self._on_treeview_selection_changed
        )

        treeview = self._ui.advanced_treeview
        self.treeview = treeview
        self.model = Gtk.TreeStore(str, str, str, bool)

        self._fill_model()
        self.model.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self.modelfilter = self.model.filter_new()
        self.modelfilter.set_visible_func(self._visible_func, self._ui.search_entry)

        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(
            p_("Configuration", "Preference Name"), renderer_text, text=0
        )
        treeview.insert_column(col, -1)
        col.set_cell_data_func(renderer_text, self._value_column_name_callback)
        col.set_expand(True)
        col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        col.set_resizable(True)

        self.renderer_text = Gtk.CellRendererText()
        self.renderer_text.set_property("ellipsize", Pango.EllipsizeMode.END)
        self._connect(self.renderer_text, "edited", self._on_config_edited)

        col = Gtk.TreeViewColumn(
            p_("Configuration", "Value"), self.renderer_text, text=1
        )
        treeview.insert_column(col, -1)
        col.set_cell_data_func(self.renderer_text, self._value_column_data_callback)
        col.set_expand(True)
        col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        col.set_resizable(True)

        renderer_text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(p_("Configuration", "Type"), renderer_text, text=2)
        treeview.insert_column(col, -1)
        col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)

        treeview.set_model(self.modelfilter)

        self._connect(
            self.get_default_controller(), "key-pressed", self._on_key_pressed
        )

    def _cleanup(self) -> None:
        del self.renderer_text
        del self.modelfilter
        del self.model
        del self.treeview

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval != Gdk.KEY_Escape:
            return Gdk.EVENT_PROPAGATE

        if self._ui.search_entry.get_text():
            self._ui.search_entry.set_text("")
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    @staticmethod
    def _value_column_name_callback(
        _col: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        iter_: Gtk.TreeIter,
        _data: object | None,
    ) -> None:
        opt_is_default = model[iter_][Column.IS_DEFAULT]
        cell.set_property("weight", 400 if opt_is_default else 700)

    @staticmethod
    def _value_column_data_callback(
        _col: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        iter_: Gtk.TreeIter,
        _data: object | None,
    ) -> None:
        opt_type = model[iter_][Column.TYPE]
        cell.set_property("editable", opt_type != SETTING_TYPES[bool])

        opt_is_default = model[iter_][Column.IS_DEFAULT]
        cell.set_property("weight", 400 if opt_is_default else 700)

    def _on_treeview_selection_changed(self, treeselection: Gtk.TreeSelection) -> None:
        model, iter_ = treeselection.get_selected()
        if not iter_:
            self._ui.reset_button.set_sensitive(False)
            return

        setting = model[iter_][Column.NAME]
        desc = ADVANCED_SETTINGS["app"][setting]

        self._ui.description.set_text(desc or p_("Configuration description", "None"))
        self._ui.reset_button.set_sensitive(not model[iter_][Column.IS_DEFAULT])

    def _on_treeview_row_activated(
        self, _treeview: Gtk.TreeView, path: Gtk.TreePath, _column: Gtk.TreeViewColumn
    ) -> None:
        modelpath = self.modelfilter.convert_path_to_child_path(path)
        assert modelpath
        modelrow = self.model[modelpath]
        setting = modelrow[Column.NAME]

        if modelrow[Column.TYPE] != SETTING_TYPES[bool]:
            return

        setting_value = modelrow[Column.VALUE] != _("Activated")
        column_value = BOOL_DICT[setting_value]
        default = APP_SETTINGS[setting]

        app.settings.set(setting, setting_value)
        modelrow[Column.VALUE] = column_value
        modelrow[Column.IS_DEFAULT] = bool(setting_value == default)

        self._ui.reset_button.set_sensitive(setting_value != default)

    def _on_config_edited(
        self, _cell: Gtk.CellRendererText, path: str, text: str
    ) -> None:
        treepath = Gtk.TreePath.new_from_string(path)
        assert treepath is not None
        modelpath = self.modelfilter.convert_path_to_child_path(treepath)
        assert modelpath
        modelrow = self.model[modelpath]
        setting = modelrow[Column.NAME]
        default = APP_SETTINGS[setting]

        value = text
        if modelrow[Column.TYPE] == SETTING_TYPES[int]:
            try:
                value = int(text)
            except ValueError:
                return

        app.settings.set(setting, value)
        modelrow[Column.VALUE] = text
        modelrow[Column.IS_DEFAULT] = bool(value == default)

        self._ui.reset_button.set_sensitive(value != default)

    def _on_reset_button_clicked(self, button: Gtk.Button) -> None:
        model, iter_ = self.treeview.get_selection().get_selected()
        if not iter_:
            return

        setting = model[iter_][Column.NAME]
        default = APP_SETTINGS[setting]

        if isinstance(default, bool):
            model[iter_][Column.VALUE] = BOOL_DICT[default]
        else:
            model[iter_][Column.VALUE] = str(default)

        model[iter_][Column.IS_DEFAULT] = True

        app.settings.set(setting, default)
        button.set_sensitive(False)

    def _fill_model(self) -> None:
        for category, settings in ADVANCED_SETTINGS.items():
            if category != "app":
                continue

            for setting in settings:
                value = app.settings.get(setting)  # pyright: ignore
                default = APP_SETTINGS[setting]
                is_default = bool(value == default)  # pyright: ignore

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

                self.model.append(None, [setting, value, type_, is_default])

    @staticmethod
    def _visible_func(
        model: Gtk.TreeModel, treeiter: Gtk.TreeIter, search_entry: Gtk.SearchEntry
    ) -> bool:
        search_string = search_entry.get_text().lower()
        if not search_string:
            return True

        setting = model[treeiter][Column.NAME]
        desc = ADVANCED_SETTINGS["app"][setting]

        return search_string in setting or search_string in desc.lower()

    def _on_search_entry_changed(self, _entry: Gtk.SearchEntry) -> None:
        self.modelfilter.refilter()
