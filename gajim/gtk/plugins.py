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

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import Optional

import logging
from enum import IntEnum
from enum import unique
from pathlib import Path

from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import Gdk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.events import PluginAdded
from gajim.common.events import PluginRemoved
from gajim.common.exceptions import PluginsystemError
from gajim.common.helpers import open_uri
from gajim.common.types import PluginRepositoryT

from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.manifest import PluginManifest

from gajim.gui.dialogs import WarningDialog
from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.filechoosers import ArchiveChooserDialog
from gajim.gui.builder import get_builder
from gajim.gui.util import load_icon_pixbuf
from gajim.gui.util import EventHelper


log = logging.getLogger('gajim.gui.plugins')


@unique
class Column(IntEnum):
    ICON = 0
    NAME = 1
    VERSION = 2
    INSTALLED = 3
    DOWNLOAD = 4
    UPDATE_AVAILABLE = 5
    RESTART = 6
    HAS_ERROR = 7
    ERROR_TEXT = 8
    MANIFEST = 9


class PluginsWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)

        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(650, 500)
        self.set_show_menubar(False)
        self.set_title(_('Plugins'))

        self._ui = get_builder('plugins.ui')
        self.add(self._ui.plugins_box)

        if app.is_flatpak():
            self._ui.help_button.show()
            self._ui.download_button.set_no_show_all(True)
            self._ui.uninstall_plugin_button.set_no_show_all(True)
            self._ui.install_from_zip_button.set_no_show_all(True)

        self._ui.liststore.set_sort_column_id(Column.NAME,
                                              Gtk.SortType.ASCENDING)

        self._ui.plugins_treeview.set_has_tooltip(True)
        self._ui.enabled_column.set_cell_data_func(self._ui.enabled_renderer,
                                                   self._on_render_enabled_cell)

        self._manifests: dict[str, Gtk.TreeIter] = {}

        self._clear_plugin_info()
        self._load_installed_manifests()
        self._load_repository_manifests()

        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.register_events([
            ('plugin-removed', ged.GUI1, self._on_plugin_removed),
            ('plugin-added', ged.GUI1, self._on_plugin_added),
        ])

        app.plugin_repository.connect('download-started',
                                      self._on_download_started)
        app.plugin_repository.connect('download-finished',
                                      self._on_download_finished)
        app.plugin_repository.connect('download-failed',
                                      self._on_download_failed)

        self.show_all()

    def _on_render_enabled_cell(self,
                                _tree_column: Gtk.TreeViewColumn,
                                cell: Gtk.CellRendererToggle,
                                tree_model: Gtk.TreeModel,
                                iter_: Gtk.TreeIter,
                                _user_data: Literal[None]) -> None:

        row = tree_model[iter_]
        manifest = row[Column.MANIFEST]
        plugin = app.plugin_manager.get_plugin(manifest.short_name)

        if plugin is None:
            cell.set_visible(False)
        else:
            cell.set_active(plugin.active)
            cell.set_activatable(plugin.activatable)
            cell.set_visible(True)

    def _on_query_tooltip(self,
                          treeview: Gtk.TreeView,
                          x_coord: int,
                          y_coord: int,
                          keyboard_mode: bool,
                          tooltip: Gtk.Tooltip) -> bool:

        context = treeview.get_tooltip_context(x_coord, y_coord, keyboard_mode)
        has_row, _x, _y, model, _path, iter_ = context
        if not has_row or model is None:
            return False

        row = model[iter_]
        if row[Column.UPDATE_AVAILABLE]:
            tooltip.set_text(_('Update available'))
            return True

        if row[Column.RESTART]:
            tooltip.set_text(_('Restart Gajim for changes to take effect'))
            return True

        if row[Column.HAS_ERROR]:
            manifest = row[Column.MANIFEST]
            plugin = app.plugin_manager.get_plugin(manifest.short_name)
            if plugin is not None and not plugin.activatable:
                tooltip.set_text(plugin.available_text)
            else:
                tooltip.set_text(row[Column.ERROR_TEXT])
            return True

        return False

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_destroy(self, *args: Any) -> None:
        self._ui.enabled_renderer.run_dispose()
        self._ui.enabled_column.run_dispose()
        self._ui.treeview_selection.run_dispose()
        app.plugin_repository.disconnect(self)
        app.check_finalize(self)

    def _selection_changed(self,
                           treeview_selection: Gtk.TreeSelection
                           ) -> None:
        model, iter_ = treeview_selection.get_selected()
        if iter_:
            row = model[iter_]
            self._load_plugin_info(row)
            self._set_button_states(row)
        else:
            self._clear_plugin_info()

    def _update_selected_plugin(self):
        self._ui.treeview_selection.emit('changed')

    def _load_plugin_info(self, row: Gtk.TreeModelRow) -> None:
        manifest = row[Column.MANIFEST]
        installed = row[Column.INSTALLED]
        has_error = row[Column.HAS_ERROR]

        self._ui.plugin_name_label.set_text(manifest.name)
        self._ui.plugin_version_label.set_text(str(manifest.version))
        self._ui.plugin_authors_label.set_text('\n'.join(manifest.authors))
        markup = f'<a href="{manifest.homepage}">{manifest.homepage}</a>'
        self._ui.plugin_homepage_linkbutton.set_markup(markup)
        self._ui.description.set_text(manifest.description)
        self._ui.uninstall_plugin_button.set_sensitive(installed)

        plugin = app.plugin_manager.get_plugin(manifest.short_name)
        enabled = plugin.active if plugin is not None else False

        has_config_dialog = has_error or manifest.config_dialog
        self._ui.configure_plugin_button.set_sensitive(
            enabled and has_config_dialog)

    def _set_button_states(self, row: Gtk.TreeModelRow) -> None:
        installed = row[Column.INSTALLED]
        update_available = row[Column.UPDATE_AVAILABLE]
        download = not installed and app.plugin_repository.available

        self._ui.uninstall_plugin_button.set_sensitive(installed)
        self._ui.download_button.set_sensitive(download or update_available)
        if update_available:
            self._ui.download_button.set_tooltip_text(_('Download Update'))
        else:
            self._ui.download_button.set_tooltip_text(_('Download and Install'))

    def _clear_plugin_info(self) -> None:
        self._ui.plugin_name_label.set_text('')
        self._ui.plugin_version_label.set_text('')
        self._ui.plugin_authors_label.set_text('')
        self._ui.plugin_homepage_linkbutton.set_markup('')

        self._ui.description.set_text('')
        self._ui.uninstall_plugin_button.set_sensitive(False)
        self._ui.configure_plugin_button.set_sensitive(False)

    def _load_installed_manifests(self) -> None:
        for plugin in app.plugin_manager.plugins:
            icon = self._get_plugin_icon(plugin.manifest)
            self._add_manifest(plugin.manifest, True, icon=icon)

    def _load_repository_manifests(self) -> None:
        for manifest in app.plugin_repository.get_manifests():
            icon = self._get_plugin_icon(manifest)
            self._add_manifest(manifest, False, icon=icon)

    def _get_restart(self, manifest: PluginManifest) -> bool:
        path = configpaths.get('PLUGINS_DOWNLOAD') / manifest.short_name
        return path.exists()

    def _get_error(self,
                   manifest: PluginManifest,
                   installed: bool) -> tuple[bool, str]:

        if not installed:
            return False, ''

        plugin = app.plugin_manager.get_plugin(manifest.short_name)
        assert plugin is not None
        if not plugin.activatable:
            return True, plugin.available_text
        return False, ''

    def _get_plugin_row(self, short_name: str) -> Optional[Gtk.TreeModelRow]:
        iter_ = self._manifests.get(short_name)
        if iter_ is None:
            return None
        return self._ui.liststore[iter_]

    def _add_manifest(self,
                      manifest: PluginManifest,
                      installed: bool,
                      icon: Optional[GdkPixbuf.Pixbuf] = None) -> None:

        restart = self._get_restart(manifest)
        has_error, error = self._get_error(manifest, installed)

        row = self._get_plugin_row(manifest.short_name)
        if row is None:
            iter_ = self._ui.liststore.append([icon,
                                               manifest.name,
                                               str(manifest.version),
                                               installed,
                                               False,
                                               False,
                                               restart,
                                               has_error,
                                               error or None,
                                               manifest])

            self._manifests[manifest.short_name] = iter_

        elif restart:
            row[Column.RESTART] = True

        else:
            current_manifest = row[Column.MANIFEST]
            if manifest.version > current_manifest.version:
                row[Column.UPDATE_AVAILABLE] = True

    def _get_plugin_icon(self,
                         manifest: PluginManifest
                         ) -> Optional[GdkPixbuf.Pixbuf]:

        image_name = f'{manifest.short_name}.png'
        path = configpaths.get('PLUGINS_IMAGES') / image_name
        if path.exists():
            return GdkPixbuf.Pixbuf.new_from_file_at_size(str(path), 16, 16)

        plugin = app.plugin_manager.get_plugin(manifest.short_name)
        if plugin is None:
            return

        path = Path(plugin.__path__) / image_name
        if path.exists():
            return GdkPixbuf.Pixbuf.new_from_file_at_size(str(path), 16, 16)

        return load_icon_pixbuf('applications-utilities')

    def _on_enabled_toggled(self,
                            _cell: Gtk.CellRendererToggle,
                            path: str
                            ) -> None:

        manifest = self._ui.liststore[path][Column.MANIFEST]

        plugin = app.plugin_manager.get_plugin(manifest.short_name)
        assert plugin is not None

        if plugin.active:
            app.plugin_manager.deactivate_plugin(plugin)
        else:
            try:
                app.plugin_manager.activate_plugin(plugin)
            except GajimPluginActivateException as e:
                WarningDialog(_('Plugin failed'), str(e))
                return

        self._update_selected_plugin()

    def _on_configure_plugin(self, _button: Gtk.Button) -> None:
        selection = self._ui.plugins_treeview.get_selection()
        model, iter_ = selection.get_selected()
        if iter_:
            manifest = model.get_value(iter_, Column.MANIFEST)
            plugin = app.plugin_manager.get_plugin(manifest.short_name)
            assert plugin is not None
            plugin.config_dialog(self)  # pyright: ignore

    def _on_uninstall_plugin(self, _button: Gtk.ToolButton) -> None:
        selection = self._ui.plugins_treeview.get_selection()
        model, iter_ = selection.get_selected()
        if not iter_:
            return

        manifest = model.get_value(iter_, Column.MANIFEST)
        plugin = app.plugin_manager.get_plugin(manifest.short_name)
        assert plugin is not None
        try:
            app.plugin_manager.uninstall_plugin(plugin)
        except PluginsystemError as error:
            WarningDialog(_('Unable to properly remove the plugin'),
                          str(error))
            return

    def _on_plugin_removed(self, event: PluginRemoved) -> None:
        row = self._get_plugin_row(event.manifest.short_name)
        assert row is not None

        if not app.plugin_repository.contains(event.manifest.short_name):
            self._ui.liststore.remove(row.iter)
            return

        row[Column.INSTALLED] = False
        row[Column.UPDATE_AVAILABLE] = False
        row[Column.HAS_ERROR] = False
        row[Column.RESTART] = False

        self._update_selected_plugin()

    def _on_plugin_added(self, event: PluginAdded) -> None:
        icon = self._get_plugin_icon(event.manifest)
        self._add_manifest(event.manifest, True, icon=icon)

    def _on_help_clicked(self, _button: Gtk.Button) -> None:
        open_uri('https://dev.gajim.org/gajim/gajim/wikis/help/flathub')

    def _on_download_clicked(self, _button: Gtk.Button) -> None:
        self._ui.download_button.set_sensitive(False)
        selection = self._ui.plugins_treeview.get_selection()
        model, iter_ = selection.get_selected()
        if iter_:
            row = model[iter_]
            manifest = row[Column.MANIFEST]
            app.plugin_repository.download_plugins([manifest])

    def _on_install_plugin_from_zip(self, _button: Gtk.ToolButton) -> None:
        def _show_warn_dialog() -> None:
            text = _('Archive is malformed')
            WarningDialog(text, transient_for=self)

        def _on_plugin_exists(zip_filename: str) -> None:
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

        def _try_install(paths: list[str]) -> None:
            zip_filename = paths[0]
            try:
                plugin = app.plugin_manager.install_from_zip(zip_filename)
            except PluginsystemError as er_type:
                error_text = str(er_type)
                if error_text == _('Plugin already exists'):
                    _on_plugin_exists(zip_filename)
                    return

                WarningDialog(error_text, f'"{zip_filename}"')
                return
            if not plugin:
                _show_warn_dialog()
                return

        ArchiveChooserDialog(_try_install, transient_for=self)

    def _on_download_started(self,
                             _repository: PluginRepositoryT,
                             _signal_name: str,
                             manifests: set[PluginManifest]) -> None:

        for manifest in manifests:
            row = self._get_plugin_row(manifest.short_name)
            assert row is not None
            row[Column.UPDATE_AVAILABLE] = False
            row[Column.HAS_ERROR] = False
            row[Column.DOWNLOAD] = True

    def _on_download_finished(self,
                              _repository: PluginRepositoryT,
                              _signal_name: str,
                              manifest: PluginManifest) -> None:

        row = self._get_plugin_row(manifest.short_name)
        assert row is not None
        row[Column.DOWNLOAD] = False
        row[Column.UPDATE_AVAILABLE] = False
        row[Column.HAS_ERROR] = False

        activated = app.plugin_manager.update_plugins(
            replace=False, activate=True, plugin_name=manifest.short_name)
        if activated:
            row[Column.INSTALLED] = True

        else:
            row[Column.RESTART] = True
            log.info('Plugin %s needs restart', manifest.short_name)

        self._update_selected_plugin()

    def _on_download_failed(self,
                            _repository: PluginRepositoryT,
                            _signal_name: str,
                            manifest: PluginManifest,
                            error: str) -> None:

        row = self._get_plugin_row(manifest.short_name)
        assert row is not None
        row[Column.DOWNLOAD] = False
        row[Column.UPDATE_AVAILABLE] = False
        row[Column.HAS_ERROR] = True
        row[Column.ERROR_TEXT] = error

        self._update_selected_plugin()
