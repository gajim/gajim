# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal

import logging
from enum import IntEnum
from enum import unique
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common.exceptions import PluginsystemError
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.types import PluginRepositoryT
from gajim.common.util.uri import open_uri
from gajim.plugins.events import PluginAdded
from gajim.plugins.events import PluginRemoved
from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.manifest import PluginManifest

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import WarningDialog
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger('gajim.gtk.plugins')


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


class PluginsWindow(GajimAppWindow, EventHelper):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name='PluginsWindow',
            title=_('Plugins'),
            default_height=500
        )

        EventHelper.__init__(self)

        self._ui = get_builder('plugins.ui')
        self.set_child(self._ui.plugins_box)

        self._file_chooser_button = FileChooserButton(
            filters=[
                Filter(name=_('All files'), patterns=['*']),
                Filter(name=_('ZIP files'), patterns=['*.zip'], default=True)
            ],
            tooltip=_('Install Plugin from ZIP-File'),
            icon_name='system-software-install-symbolic',
        )
        self._connect(
            self._file_chooser_button, 'path-picked', self._on_install_plugin_from_zip
        )
        self._ui.toolbar.prepend(self._file_chooser_button)
        self._ui.toolbar.reorder_child_after(self._ui.download_button)

        if app.is_flatpak():
            self._ui.help_button.show()
            self._ui.download_button.set_visible(False)
            self._ui.uninstall_plugin_button.set_visible(False)
            self._file_chooser_button.set_visible(False)

        self._ui.liststore.set_sort_column_id(Column.NAME,
                                              Gtk.SortType.ASCENDING)

        self._ui.plugins_treeview.set_has_tooltip(True)
        self._ui.enabled_column.set_cell_data_func(self._ui.enabled_renderer,
                                                   self._on_render_enabled_cell)

        self._manifests: dict[str, Gtk.TreeIter] = {}

        self._clear_plugin_info()
        self._load_installed_manifests()
        self._load_repository_manifests()

        self._connect(
            self._ui.configure_plugin_button, 'clicked', self._on_configure_plugin
        )
        self._connect(
            self._ui.plugins_treeview, 'query-tooltip', self._on_query_tooltip
        )
        self._connect(self._ui.treeview_selection, 'changed', self._selection_changed)
        self._connect(self._ui.enabled_renderer, 'toggled', self._on_enabled_toggled)
        self._connect(self._ui.help_button, 'clicked', self._on_help_clicked)
        self._connect(
            self._ui.uninstall_plugin_button, 'clicked', self._on_uninstall_plugin
        )
        self._connect(self._ui.download_button, 'clicked', self._on_download_clicked)

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

    def _cleanup(self) -> None:
        app.plugin_repository.disconnect(self)
        self.unregister_events()

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
        has_row, model, _path, iter_ = context
        if not has_row:
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
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

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

    def _get_plugin_row(self, short_name: str) -> Gtk.TreeModelRow | None:
        iter_ = self._manifests.get(short_name)
        if iter_ is None:
            return None
        return self._ui.liststore[iter_]

    def _add_manifest(self,
                      manifest: PluginManifest,
                      installed: bool,
                      icon: Gio.Icon | None = None) -> None:

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
                         ) -> Gio.Icon | None:

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

        return Gio.ThemedIcon(name='applications-utilities')

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
                WarningDialog(_('Plugin Failed'), str(e))
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

    def _on_uninstall_plugin(self, _button: Gtk.Button) -> None:
        selection = self._ui.plugins_treeview.get_selection()
        model, iter_ = selection.get_selected()
        if not iter_:
            return

        manifest = model.get_value(iter_, Column.MANIFEST)
        plugin = app.plugin_manager.get_plugin(manifest.short_name)
        error_text = _('Unable to properly remove the plugin')
        if plugin is None:
            WarningDialog(_('Warning'), error_text)
            return

        try:
            app.plugin_manager.uninstall_plugin(plugin)
        except PluginsystemError as error:
            WarningDialog(_('Warning'), f"{error_text}\n{error}")
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

    def _on_install_plugin_from_zip(
        self, _button: FileChooserButton, paths: list[Path]
    ) -> None:
        if not paths:
            return

        zip_filename = str(paths[0])

        def _on_overwrite():
            plugin = app.plugin_manager.install_from_zip(zip_filename,
                                                         overwrite=True)
            if not plugin:
                WarningDialog(_('Archive Malformed'), _('Archive is malformed'))
                return

        try:
            plugin = app.plugin_manager.install_from_zip(zip_filename)
        except PluginsystemError as er_type:
            error_text = str(er_type)
            if error_text == _('Plugin already exists'):
                ConfirmationDialog(
                    _('Overwrite Plugin?'),
                    _('Do you want to overwrite the currently installed version?'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       text=_('_Overwrite'),
                                       callback=_on_overwrite)],
                ).show()
                return

            WarningDialog(error_text, f'"{zip_filename}"')
            return

        if not plugin:
            WarningDialog(_('Archive Malformed'), _('Archive is malformed'))

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
