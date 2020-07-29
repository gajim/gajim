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

from enum import IntEnum, unique

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import Q_

from gajim.gtk.util import get_builder


@unique
class Column(IntEnum):
    NAME = 0
    VALUE = 1
    TYPE = 2


def rate_limit(rate):
    """
    Call func at most *rate* times per second
    """
    def decorator(func):
        timeout = [None]

        def func_wrapper(*args, **kwargs):
            if timeout[0] is not None:
                GLib.source_remove(timeout[0])
                timeout[0] = None

            def timeout_func():
                func(*args, **kwargs)
                timeout[0] = None
            timeout[0] = GLib.timeout_add(int(1000.0 / rate), timeout_func)
        return func_wrapper
    return decorator


def tree_model_iter_children(model, treeiter):
    it = model.iter_children(treeiter)
    while it:
        yield it
        it = model.iter_next(it)


def tree_model_pre_order(model, treeiter):
    yield treeiter
    for childiter in tree_model_iter_children(model, treeiter):
        for it in tree_model_pre_order(model, childiter):
            yield it


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

        # Format:
        # key = option name (root/subopt/opt separated by \n then)
        # value = array(oldval, newval)
        self.changed_opts = {}

        # For i18n
        self.right_true_dict = {True: _('Activated'), False: _('Deactivated')}
        self.types = {
            'boolean': Q_('?config type:Boolean'),
            'integer': Q_('?config type:Integer'),
            'string': Q_('?config type:Text'),
            'color': Q_('?config type:Color')}

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

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)
        self.show_all()

    def _on_key_press(self, _widget, event):
        editing = self.renderer_text.get_property('editing')
        if event.keyval == Gdk.KEY_Escape and not editing:
            self.destroy()

    def _value_column_data_callback(self, _col, cell, model, iter_, _data):
        """
        Check if it's boolean or holds password stuff and if yes, make the
        cellrenderertext not editable, else - it's editable
        """
        optname = model[iter_][Column.NAME]
        opttype = model[iter_][Column.TYPE]
        if opttype == self.types['boolean'] or optname == 'password':
            cell.set_property('editable', False)
        else:
            cell.set_property('editable', True)

    @staticmethod
    def _get_option_path(model, iter_):
        # It looks like path made from reversed array
        # path[0] is the true one optname
        # path[1] is the key name
        # path[2] is the root of tree
        # last two is optional
        path = [model[iter_][0]]
        parent = model.iter_parent(iter_)
        while parent:
            path.append(model[parent][0])
            parent = model.iter_parent(parent)
        return path

    def _on_treeview_selection_changed(self, treeselection):
        model, iter_ = treeselection.get_selected()
        # Check for GtkTreeIter
        if iter_:
            opt_path = self._get_option_path(model, iter_)
            # Get text from first column in this row
            desc = None
            if len(opt_path) == 3:
                desc = app.config.get_desc_per(opt_path[2], opt_path[0])
            elif len(opt_path) == 1:
                desc = app.config.get_desc(opt_path[0])
            if desc:
                self._ui.description.set_text(desc)
            else:
                self._ui.description.set_text(Q_('?config description:None'))
            if (len(opt_path) == 3 or
                    (len(opt_path) == 1 and not model.iter_has_child(iter_))):
                self._ui.reset_button.set_sensitive(True)
            else:
                self._ui.reset_button.set_sensitive(False)
        else:
            self._ui.reset_button.set_sensitive(False)

    def _remember_option(self, option, oldval, newval):
        if option in self.changed_opts:
            self.changed_opts[option] = (self.changed_opts[option][0], newval)
        else:
            self.changed_opts[option] = (oldval, newval)

    def _on_treeview_row_activated(self, _treeview, path, _column):
        modelpath = self.modelfilter.convert_path_to_child_path(path)
        modelrow = self.model[modelpath]
        option = modelrow[0]
        if modelrow[2] == self.types['boolean']:
            for key in self.right_true_dict:
                if self.right_true_dict[key] == modelrow[1]:
                    modelrow[1] = str(key)
            newval = {'False': True, 'True': False}[modelrow[1]]
            if len(modelpath.get_indices()) > 1:
                optnamerow = self.model[modelpath.get_indices()[0]]
                optname = optnamerow[0]
                modelpath.up()
                keyrow = self.model[modelpath]
                key = keyrow[0]
                self._remember_option(
                    option + '\n' + key + '\n' + optname,
                    modelrow[1],
                    newval)
                app.config.set_per(optname, key, option, newval)
            else:
                self._remember_option(option, modelrow[1], newval)
                app.settings.set(option, newval)
            modelrow[1] = self.right_true_dict[newval]
            self._check_for_restart()

    def _check_for_restart(self):
        self._ui.restart_warning.hide()
        for opt in self.changed_opts:
            opt_path = opt.split('\n')
            if len(opt_path) == 3:
                restart = app.config.get_restart_per(
                    opt_path[2],
                    opt_path[1],
                    opt_path[0])
            else:
                restart = app.config.get_restart(opt_path[0])
            if restart:
                if self.changed_opts[opt][0] != self.changed_opts[opt][1]:
                    self._ui.restart_warning.set_no_show_all(False)
                    self._ui.restart_warning.show()
                    break

    def _on_config_edited(self, _cell, path, text):
        # Convert modelfilter path to model path
        path = Gtk.TreePath.new_from_string(path)
        modelpath = self.modelfilter.convert_path_to_child_path(path)
        modelrow = self.model[modelpath]
        option = modelrow[0]
        if modelpath.get_depth() > 2:
            modelpath.up()  # Get parent
            keyrow = self.model[modelpath]
            key = keyrow[0]
            modelpath.up()  # Get parent
            optnamerow = self.model[modelpath]
            optname = optnamerow[0]
            self._remember_option(
                option + '\n' + key + '\n' + optname,
                modelrow[1],
                text)
            app.config.set_per(optname, key, option, text)
        else:
            self._remember_option(option, modelrow[1], text)
            app.settings.set(option, text)
        modelrow[1] = text
        self._check_for_restart()

    def _on_reset_button_clicked(self, _widget):
        model, iter_ = self.treeview.get_selection().get_selected()
        # Check for GtkTreeIter
        if iter_:
            path = model.get_path(iter_)
            opt_path = self._get_option_path(model, iter_)
            if len(opt_path) == 1:
                default = app.config.get_default(opt_path[0])
            elif len(opt_path) == 3:
                default = app.config.get_default_per(opt_path[2], opt_path[0])

            if model[iter_][Column.TYPE] == self.types['boolean']:
                if self.right_true_dict[default] == model[iter_][Column.VALUE]:
                    return
                modelpath = self.modelfilter.convert_path_to_child_path(path)
                modelrow = self.model[modelpath]
                option = modelrow[0]
                if len(modelpath) > 1:
                    optnamerow = self.model[modelpath[0]]
                    optname = optnamerow[0]
                    keyrow = self.model[modelpath[:2]]
                    key = keyrow[0]
                    self._remember_option(
                        option + '\n' + key + '\n' + optname,
                        modelrow[Column.VALUE],
                        default)
                    app.config.set_per(optname, key, option, default)
                else:
                    self._remember_option(
                        option,
                        modelrow[Column.VALUE],
                        default)
                    app.settings.set(option, default)
                modelrow[Column.VALUE] = self.right_true_dict[default]
                self._check_for_restart()
            else:
                if str(default) == model[iter_][Column.VALUE]:
                    return
                self._on_config_edited(None, path.to_string(), str(default))

    def _fill_model(self, node=None, parent=None):
        for item, option in app.config.get_children(node):
            name = item[-1]
            if option is None:  # Node
                newparent = self.model.append(parent, [name, '', ''])
                self._fill_model(item, newparent)
            else:
                if len(item) == 1:
                    type_ = self.types[app.config.get_type(name)]
                elif len(item) == 3:
                    type_ = self.types[app.config.get_type_per(
                        item[0], item[2])]
                if name == 'password':
                    value = Q_('?password:Hidden')
                else:
                    if type_ == self.types['boolean']:
                        value = self.right_true_dict[option]
                    else:
                        try:
                            value = str(option)
                        except Exception:
                            value = option
                self.model.append(parent, [name, value, type_])

    def _visible_func(self, model, treeiter, _data):
        search_string = self._ui.filter_entry.get_text().lower()
        for it in tree_model_pre_order(model, treeiter):
            if model[it][Column.TYPE] != '':
                opt_path = self._get_option_path(model, it)
                if len(opt_path) == 3:
                    desc = app.config.get_desc_per(opt_path[2], opt_path[0])
                elif len(opt_path) == 1:
                    desc = app.config.get_desc(opt_path[0])
                if (search_string in model[it][Column.NAME] or
                        (desc and search_string in desc.lower())):
                    return True
        return False

    @rate_limit(3)
    def _on_filter_entry_changed(self, widget):
        self.modelfilter.refilter()
        if not widget.get_text():
            # Maybe the expanded rows should be remembered here ...
            self.treeview.collapse_all()
        else:
            # ... and be restored correctly here
            self.treeview.expand_all()
