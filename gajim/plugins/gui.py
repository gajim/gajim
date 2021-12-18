# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

'''
GUI classes related to plug-in management.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 6th June 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import os
from enum import IntEnum
from enum import unique

from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import Gdk

from gajim.common import app
from gajim.common import ged
from gajim.common.exceptions import PluginsystemError
from gajim.common.helpers import open_uri
from gajim.common.nec import EventHelper

from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.plugins_i18n import _

from gajim.gui.dialogs import WarningDialog
from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.filechoosers import ArchiveChooserDialog
from gajim.gui.builder import get_builder
from gajim.gui.util import load_icon


@unique
class Column(IntEnum):
    PLUGIN = 0
    NAME = 1
    ACTIVE = 2
    ACTIVATABLE = 3
    ICON = 4


class PluginsWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)

        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(650, 500)
        self.set_show_menubar(False)
        self.set_title(_('Plugins'))

        self._ui = get_builder('plugins_window.ui')
        self.add(self._ui.plugins_notebook)

        # Disable 'Install from ZIP' for Flatpak installs
        if app.is_flatpak():
            self._ui.install_plugin_button.set_tooltip_text(
                _('Click to view Gajim\'s wiki page on how to install plugins '
                  'in Flatpak.'))

        self.installed_plugins_model = Gtk.ListStore(object, str, bool, bool,
                                                     GdkPixbuf.Pixbuf)
        self._ui.installed_plugins_treeview.set_model(
            self.installed_plugins_model)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_('Plugin'))  # , renderer, text=Column.NAME)
        cell = Gtk.CellRendererPixbuf()
        col.pack_start(cell, False)
        col.add_attribute(cell, 'pixbuf', Column.ICON)
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.NAME)
        col.set_property('expand', True)
        self._ui.installed_plugins_treeview.append_column(col)

        renderer = Gtk.CellRendererToggle()
        renderer.connect('toggled', self._installed_plugin_toggled)
        col = Gtk.TreeViewColumn(_('Active'), renderer, active=Column.ACTIVE,
                                 activatable=Column.ACTIVATABLE)
        self._ui.installed_plugins_treeview.append_column(col)

        self.def_icon = load_icon('preferences-desktop', self, pixbuf=True)

        # connect signal for selection change
        selection = self._ui.installed_plugins_treeview.get_selection()
        selection.connect(
            'changed', self._installed_plugins_treeview_selection_changed)
        selection.set_mode(Gtk.SelectionMode.SINGLE)

        self._clear_installed_plugin_info()

        self._fill_installed_plugins_model()
        root_iter = self.installed_plugins_model.get_iter_first()
        if root_iter:
            selection.select_iter(root_iter)

        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self._ui.plugins_notebook.set_current_page(0)

        # Adding GUI extension point for Plugins that want to hook
        # the Plugin Window
        app.plugin_manager.gui_extension_point('plugin_window', self)

        self.register_events([
            ('plugin-removed', ged.GUI1, self._on_plugin_removed),
            ('plugin-added', ged.GUI1, self._on_plugin_added),
        ])

        self.show_all()

    def get_notebook(self):
        # Used by plugins
        return self._ui.plugins_notebook

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_destroy(self, *args):
        self.unregister_events()
        app.plugin_manager.remove_gui_extension_point('plugin_window', self)

    def _installed_plugins_treeview_selection_changed(self, treeview_selection):
        model, iter_ = treeview_selection.get_selected()
        if iter_:
            plugin = model.get_value(iter_, Column.PLUGIN)
            self._display_installed_plugin_info(plugin)
        else:
            self._clear_installed_plugin_info()

    def _display_installed_plugin_info(self, plugin):
        self._ui.plugin_name_label.set_text(plugin.name)
        self._ui.plugin_version_label.set_text(plugin.version)
        self._ui.plugin_authors_label.set_text(plugin.authors)
        markup = '<a href="%s">%s</a>' % (plugin.homepage, plugin.homepage)
        self._ui.plugin_homepage_linkbutton.set_markup(markup)

        if plugin.available_text:
            text = _('Warning: %s') % plugin.available_text
            self._ui.available_text_label.set_text(text)
            self._ui.available_text.show()
            # Workaround for https://bugzilla.gnome.org/show_bug.cgi?id=710888
            self._ui.available_text.queue_resize()
        else:
            self._ui.available_text.hide()

        self._ui.description.set_text(plugin.description)

        self._ui.uninstall_plugin_button.set_sensitive(True)
        self._ui.configure_plugin_button.set_sensitive(
            plugin.config_dialog is not None and plugin.active)

    def _clear_installed_plugin_info(self):
        self._ui.plugin_name_label.set_text('')
        self._ui.plugin_version_label.set_text('')
        self._ui.plugin_authors_label.set_text('')
        self._ui.plugin_homepage_linkbutton.set_markup('')

        self._ui.description.set_text('')
        self._ui.uninstall_plugin_button.set_sensitive(False)
        self._ui.configure_plugin_button.set_sensitive(False)

    def _fill_installed_plugins_model(self):
        pm = app.plugin_manager
        self.installed_plugins_model.clear()
        self.installed_plugins_model.set_sort_column_id(1,
                                                        Gtk.SortType.ASCENDING)

        for plugin in pm.plugins:
            icon = self._get_plugin_icon(plugin)
            self.installed_plugins_model.append(
                [plugin,
                 plugin.name,
                 plugin.active and plugin.activatable,
                 plugin.activatable,
                 icon])

    def _get_plugin_icon(self, plugin):
        icon_file = os.path.join(plugin.__path__, os.path.split(
                                 plugin.__path__)[1]) + '.png'
        icon = self.def_icon
        if os.path.isfile(icon_file):
            icon = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_file, 16, 16)
        return icon

    def _installed_plugin_toggled(self, _cell, path):
        is_active = self.installed_plugins_model[path][Column.ACTIVE]
        plugin = self.installed_plugins_model[path][Column.PLUGIN]

        if is_active:
            app.plugin_manager.deactivate_plugin(plugin)
        else:
            try:
                app.plugin_manager.activate_plugin(plugin)
            except GajimPluginActivateException as e:
                WarningDialog(_('Plugin failed'), str(e),
                              transient_for=self)
                return

        self._ui.configure_plugin_button.set_sensitive(
            plugin.config_dialog is not None and not is_active)
        self.installed_plugins_model[path][Column.ACTIVE] = not is_active

    def _on_configure_plugin(self, _widget):
        selection = self._ui.installed_plugins_treeview.get_selection()
        model, iter_ = selection.get_selected()
        if iter_:
            plugin = model.get_value(iter_, Column.PLUGIN)

            if isinstance(plugin.config_dialog, GajimPluginConfigDialog):
                plugin.config_dialog.run(self)
            else:
                plugin.config_dialog(self)

        else:
            # No plugin selected. this should never be reached. As configure
            # plugin button should only be clickable when plugin is selected.
            # XXX: maybe throw exception here?
            pass

    def _on_uninstall_plugin(self, _widget):
        selection = self._ui.installed_plugins_treeview.get_selection()
        model, iter_ = selection.get_selected()
        if iter_:
            plugin = model.get_value(iter_, Column.PLUGIN)
            try:
                app.plugin_manager.uninstall_plugin(plugin)
            except PluginsystemError as e:
                WarningDialog(_('Unable to properly remove the plugin'),
                              str(e), self)
                return

    def _on_plugin_removed(self, event):
        for row in self.installed_plugins_model:
            if row[Column.PLUGIN] == event.plugin:
                self.installed_plugins_model.remove(row.iter)
                break

    def _on_plugin_added(self, event):
        icon = self._get_plugin_icon(event.plugin)
        self.installed_plugins_model.append([event.plugin,
                                             event.plugin.name,
                                             False,
                                             event.plugin.activatable,
                                             icon])

    def _on_install_plugin(self, _widget):
        if app.is_flatpak():
            open_uri('https://dev.gajim.org/gajim/gajim/wikis/help/flathub')
            return

        def _show_warn_dialog():
            text = _('Archive is malformed')
            dialog = WarningDialog(text, '', transient_for=self)
            dialog.set_modal(False)
            dialog.popup()

        def _on_plugin_exists(zip_filename):
            def _on_yes():
                plugin = app.plugin_manager.install_from_zip(zip_filename,
                                                             overwrite=True)
                if not plugin:
                    _show_warn_dialog()
                    return

            ConfirmationDialog(
                _('Overwrite Plugin?'),
                _('Plugin already exists'),
                _('Do you want to overwrite the currently installed version?'),
                [DialogButton.make('Cancel'),
                 DialogButton.make('Remove',
                                   text=_('_Overwrite'),
                                   callback=_on_yes)],
                transient_for=self).show()

        def _try_install(zip_filename):
            try:
                plugin = app.plugin_manager.install_from_zip(zip_filename)
            except PluginsystemError as er_type:
                error_text = str(er_type)
                if error_text == _('Plugin already exists'):
                    _on_plugin_exists(zip_filename)
                    return

                WarningDialog(error_text, '"%s"' % zip_filename, self)
                return
            if not plugin:
                _show_warn_dialog()
                return

        ArchiveChooserDialog(_try_install, transient_for=self)


class GajimPluginConfigDialog(Gtk.Dialog):
    def __init__(self, plugin, **kwargs):
        Gtk.Dialog.__init__(self, title='%s %s' % (plugin.name,
                            _('Configuration')), **kwargs)
        self.plugin = plugin
        button = self.add_button('gtk-close', Gtk.ResponseType.CLOSE)
        button.connect('clicked', self.on_close_button_clicked)

        self.get_child().set_spacing(3)

        self.init()

    def on_close_dialog(self, widget, data):
        self.hide()
        return True

    def on_close_button_clicked(self, widget):
        self.hide()

    def run(self, parent=None):
        self.set_transient_for(parent)
        self.on_run()
        self.show_all()
        self.connect('delete-event', self.on_close_dialog)
        result = super(GajimPluginConfigDialog, self)
        return result

    def init(self):
        pass

    def on_run(self):
        pass
