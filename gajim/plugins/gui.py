# -*- coding: utf-8 -*-

## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

'''
GUI classes related to plug-in management.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 6th June 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

__all__ = ['PluginsWindow']

from gi.repository import Pango
from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import GLib, Gdk
import os

from enum import IntEnum, unique

from gajim import gtkgui_helpers
from gajim.dialogs import WarningDialog, YesNoDialog, ArchiveChooserDialog
from gajim.htmltextview import HtmlTextView
from gajim.common import app
from gajim.common import configpaths
from gajim.plugins.helpers import log_calls
from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.plugins_i18n import _
from gajim.common.exceptions import PluginsystemError

@unique
class Column(IntEnum):
    PLUGIN = 0
    NAME = 1
    ACTIVE = 2
    ACTIVATABLE = 3
    ICON = 4


class PluginsWindow(object):
    '''Class for Plugins window'''

    @log_calls('PluginsWindow')
    def __init__(self):
        '''Initialize Plugins window'''
        builder = gtkgui_helpers.get_gtk_builder('plugins_window.ui')
        self.window = builder.get_object('plugins_window')
        self.window.set_transient_for(app.interface.roster.window)

        widgets_to_extract = ('plugins_notebook', 'plugin_name_label',
            'plugin_version_label', 'plugin_authors_label',
            'plugin_homepage_linkbutton', 'uninstall_plugin_button',
            'configure_plugin_button', 'installed_plugins_treeview',
            'close_button')

        for widget_name in widgets_to_extract:
            setattr(self, widget_name, builder.get_object(widget_name))

        self.plugin_description_textview = HtmlTextView()
        self.plugin_description_textview.connect_tooltip()
        self.plugin_description_textview.set_wrap_mode(Gtk.WrapMode.WORD)
        sw = builder.get_object('scrolledwindow2')
        sw.add(self.plugin_description_textview)
        self.installed_plugins_model = Gtk.ListStore(object, str, bool, bool,
            GdkPixbuf.Pixbuf)
        self.installed_plugins_treeview.set_model(self.installed_plugins_model)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_('Plugin'))#, renderer, text=Column.NAME)
        cell = Gtk.CellRendererPixbuf()
        col.pack_start(cell, False)
        col.add_attribute(cell, 'pixbuf', Column.ICON)
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.NAME)
        col.set_property('expand', True)
        self.installed_plugins_treeview.append_column(col)

        renderer = Gtk.CellRendererToggle()
        renderer.connect('toggled', self.installed_plugins_toggled_cb)
        col = Gtk.TreeViewColumn(_('Active'), renderer, active=Column.ACTIVE,
            activatable=Column.ACTIVATABLE)
        self.installed_plugins_treeview.append_column(col)

        self.def_icon = gtkgui_helpers.get_icon_pixmap('preferences-desktop')

        # connect signal for selection change
        selection = self.installed_plugins_treeview.get_selection()
        selection.connect('changed',
            self.installed_plugins_treeview_selection_changed)
        selection.set_mode(Gtk.SelectionMode.SINGLE)

        self._clear_installed_plugin_info()

        self.fill_installed_plugins_model()
        root_iter = self.installed_plugins_model.get_iter_first()
        if root_iter:
            selection.select_iter(root_iter)

        builder.connect_signals(self)

        self.plugins_notebook.set_current_page(0)
        self.close_button.grab_focus()

        # Adding GUI extension point for Plugins that want to hook the Plugin Window
        app.plugin_manager.gui_extension_point('plugin_window', self)

        self.window.show_all()
        gtkgui_helpers.possibly_move_window_in_current_desktop(self.window)

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def on_plugins_notebook_switch_page(self, widget, page, page_num):
        GLib.idle_add(self.close_button.grab_focus)

    @log_calls('PluginsWindow')
    def installed_plugins_treeview_selection_changed(self, treeview_selection):
        model, iter = treeview_selection.get_selected()
        if iter:
            plugin = model.get_value(iter, Column.PLUGIN)
            self._display_installed_plugin_info(plugin)
        else:
            self._clear_installed_plugin_info()

    def _display_installed_plugin_info(self, plugin):
        self.plugin_name_label.set_text(plugin.name)
        self.plugin_version_label.set_text(plugin.version)
        self.plugin_authors_label.set_text(plugin.authors)
        self.plugin_homepage_linkbutton.set_uri(plugin.homepage)
        self.plugin_homepage_linkbutton.set_label(plugin.homepage)
        label = self.plugin_homepage_linkbutton.get_children()[0]
        label.set_ellipsize(Pango.EllipsizeMode.END)
        self.plugin_homepage_linkbutton.set_property('sensitive', True)

        desc_textbuffer = self.plugin_description_textview.get_buffer()
        desc_textbuffer.set_text('')
        txt = plugin.description
        txt.replace('</body>', '')
        if plugin.available_text:
            txt += '<br/><br/>' + _('Warning: %s') % plugin.available_text
        if not txt.startswith('<body '):
            txt = '<body  xmlns=\'http://www.w3.org/1999/xhtml\'>' + txt
        txt += ' </body>'
        self.plugin_description_textview.display_html(txt,
            self.plugin_description_textview, None)

        self.plugin_description_textview.set_property('sensitive', True)
        self.uninstall_plugin_button.set_property(
            'sensitive', configpaths.get('PLUGINS_USER') in plugin.__path__)
        self.configure_plugin_button.set_property(
            'sensitive', plugin.config_dialog is not None)

    def _clear_installed_plugin_info(self):
        self.plugin_name_label.set_text('')
        self.plugin_version_label.set_text('')
        self.plugin_authors_label.set_text('')
        self.plugin_homepage_linkbutton.set_uri('')
        self.plugin_homepage_linkbutton.set_label('')
        self.plugin_homepage_linkbutton.set_property('sensitive', False)

        desc_textbuffer = self.plugin_description_textview.get_buffer()
        desc_textbuffer.set_text('')
        self.plugin_description_textview.set_property('sensitive', False)
        self.uninstall_plugin_button.set_property('sensitive', False)
        self.configure_plugin_button.set_property('sensitive', False)

    @log_calls('PluginsWindow')
    def fill_installed_plugins_model(self):
        pm = app.plugin_manager
        self.installed_plugins_model.clear()
        self.installed_plugins_model.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        for plugin in pm.plugins:
            icon = self.get_plugin_icon(plugin)
            self.installed_plugins_model.append([plugin, plugin.name,
                plugin.active and plugin.activatable, plugin.activatable, icon])

    def get_plugin_icon(self, plugin):
        icon_file = os.path.join(plugin.__path__, os.path.split(
                plugin.__path__)[1]) + '.png'
        icon = self.def_icon
        if os.path.isfile(icon_file):
            icon = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_file, 16, 16)
        return icon

    @log_calls('PluginsWindow')
    def installed_plugins_toggled_cb(self, cell, path):
        is_active = self.installed_plugins_model[path][Column.ACTIVE]
        plugin = self.installed_plugins_model[path][Column.PLUGIN]

        if is_active:
            app.plugin_manager.deactivate_plugin(plugin)
        else:
            try:
                app.plugin_manager.activate_plugin(plugin)
            except GajimPluginActivateException as e:
                WarningDialog(_('Plugin failed'), str(e),
                    transient_for=self.window)
                return

        self.installed_plugins_model[path][Column.ACTIVE] = not is_active

    @log_calls('PluginsWindow')
    def on_plugins_window_destroy(self, widget):
        '''Close window'''
        app.plugin_manager.remove_gui_extension_point('plugin_window', self)
        del app.interface.instances['plugins']

    @log_calls('PluginsWindow')
    def on_close_button_clicked(self, widget):
        self.window.destroy()

    @log_calls('PluginsWindow')
    def on_configure_plugin_button_clicked(self, widget):
        selection = self.installed_plugins_treeview.get_selection()
        model, iter = selection.get_selected()
        if iter:
            plugin = model.get_value(iter, Column.PLUGIN)

            if isinstance(plugin.config_dialog, GajimPluginConfigDialog):
                plugin.config_dialog.run(self.window)
            else:
                plugin.config_dialog(self.window)

        else:
            # No plugin selected. this should never be reached. As configure
            # plugin button should only be clickable when plugin is selected.
            # XXX: maybe throw exception here?
            pass

    @log_calls('PluginsWindow')
    def on_uninstall_plugin_button_clicked(self, widget):
        selection = self.installed_plugins_treeview.get_selection()
        model, iter = selection.get_selected()
        if iter:
            plugin = model.get_value(iter, Column.PLUGIN)
            try:
                app.plugin_manager.uninstall_plugin(plugin)
            except PluginsystemError as e:
                WarningDialog(_('Unable to properly remove the plugin'),
                    str(e), self.window)
                return
            model.remove(iter)

    @log_calls('PluginsWindow')
    def on_install_plugin_button_clicked(self, widget):
        def show_warn_dialog():
            text = _('Archive is malformed')
            dialog = WarningDialog(text, '', transient_for=self.window)
            dialog.set_modal(False)
            dialog.popup()

        def _on_plugin_exists(zip_filename):
            def on_yes(is_checked):
                plugin = app.plugin_manager.install_from_zip(zip_filename,
                    True)
                if not plugin:
                    show_warn_dialog()
                    return
                model = self.installed_plugins_model

                for i, row in enumerate(model):
                    if plugin == row[Column.PLUGIN]:
                        model.remove(row.iter)
                        break

                iter_ = model.append([plugin, plugin.name, False,
                    plugin.activatable, self.get_plugin_icon(plugin)])
                sel = self.installed_plugins_treeview.get_selection()
                sel.select_iter(iter_)

            YesNoDialog(_('Plugin already exists'), sectext=_('Overwrite?'),
                on_response_yes=on_yes, transient_for=self.window)

        def _try_install(zip_filename):
            try:
                plugin = app.plugin_manager.install_from_zip(zip_filename)
            except PluginsystemError as er_type:
                error_text = str(er_type)
                if error_text == _('Plugin already exists'):
                    _on_plugin_exists(zip_filename)
                    return

                WarningDialog(error_text, '"%s"' % zip_filename, self.window)
                return
            if not plugin:
                show_warn_dialog()
                return
            model = self.installed_plugins_model
            iter_ = model.append([plugin, plugin.name, False,
                plugin.activatable, self.get_plugin_icon(plugin)])
            sel = self.installed_plugins_treeview.get_selection()
            sel.select_iter(iter_)

        self.dialog = ArchiveChooserDialog(
            on_response_ok=_try_install, transient_for=self.window)


class GajimPluginConfigDialog(Gtk.Dialog):

    @log_calls('GajimPluginConfigDialog')
    def __init__(self, plugin, **kwargs):
        Gtk.Dialog.__init__(self, title='%s %s'%(plugin.name,
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

    @log_calls('GajimPluginConfigDialog')
    def run(self, parent=None):
        self.set_transient_for(parent)
        self.on_run()
        self.show_all()
        self.connect('delete-event', self.on_close_dialog)
        result =  super(GajimPluginConfigDialog, self)
        return result

    def init(self):
        pass

    def on_run(self):
        pass
