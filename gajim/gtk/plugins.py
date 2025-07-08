# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import locale
import logging
from pathlib import Path

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from packaging.version import Version

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common.exceptions import PluginsystemError
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.types import PluginRepositoryT
from gajim.plugins.events import PluginAdded
from gajim.plugins.events import PluginRemoved
from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.manifest import PluginManifest
from gajim.plugins.repository import PluginRepository

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.util.window import get_app_window

log = logging.getLogger("gajim.gtk.plugins")


class Plugins(Adw.PreferencesGroup, EventHelper, SignalManager):
    __gtype_name__ = "Plugins"

    def __init__(self) -> None:
        Adw.PreferencesGroup.__init__(self, title=_("Plugins"))
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._plugin_rows: dict[str, PluginRow] = {}

        self._file_chooser_button = FileChooserButton(
            filters=[
                Filter(name=_("All files"), patterns=["*"]),
                Filter(name=_("ZIP files"), patterns=["*.zip"], default=True),
            ],
            label=_("Install from Archive"),
            tooltip=_("Install Plugin from ZIP-File"),
            icon_name="lucide-package-plus-symbolic",
        )
        self._file_chooser_button.set_visible(not app.is_flatpak())
        self._file_chooser_button.set_valign(Gtk.Align.CENTER)
        self._connect(
            self._file_chooser_button, "path-picked", self._on_install_plugin_from_zip
        )

        description_text = _("Manage and configure Gajim plugins")
        if app.is_flatpak():
            flatpak_howto_text = _("How to install plugins with Flatpak")
            flatpak_howto_url = "https://dev.gajim.org/gajim/gajim/wikis/help/flathub"
            description_text += (
                f"\n<a href='{flatpak_howto_url}'>{flatpak_howto_text}</a>"
            )

        self.set_description(description_text)
        self.set_header_suffix(self._file_chooser_button)

        self.register_events(
            [
                ("plugin-removed", ged.GUI1, self._on_plugin_removed),
                ("plugin-added", ged.GUI1, self._on_plugin_added),
            ]
        )

        app.plugin_repository.connect("download-started", self._on_download_started)
        app.plugin_repository.connect("download-finished", self._on_download_finished)
        app.plugin_repository.connect("download-failed", self._on_download_failed)
        app.plugin_repository.connect(
            "plugin-updates-available", self._on_plugin_updates_available
        )

        # Load manifests in idle fashion, since it blocks the UI
        GLib.idle_add(self._load_installed_manifests)
        GLib.idle_add(self._load_repository_manifests)

    def do_unroot(self) -> None:
        self._disconnect_all()
        app.plugin_repository.disconnect(self)
        self.unregister_events()
        Adw.PreferencesGroup.do_unroot(self)

    @staticmethod
    def _sort_func(row1: PluginRow, row2: PluginRow) -> int:
        return locale.strcoll(row1.name, row2.name)

    def _load_installed_manifests(self) -> None:
        for plugin in sorted(app.plugin_manager.plugins, key=lambda p: p.manifest.name):
            self._add_manifest(plugin.manifest, True)

    def _load_repository_manifests(self) -> None:
        for manifest in app.plugin_repository.get_manifests():
            self._add_manifest(manifest, False)

    def _get_restart(self, manifest: PluginManifest) -> bool:
        path = configpaths.get("PLUGINS_DOWNLOAD") / manifest.short_name
        return path.exists()

    def _add_manifest(self, manifest: PluginManifest, installed: bool) -> None:
        restart = self._get_restart(manifest)

        plugin_row = self._plugin_rows.get(manifest.short_name)
        if plugin_row is None:
            plugin_row = PluginRow(manifest, installed)
            self._plugin_rows[manifest.short_name] = plugin_row
            self.add(plugin_row)

        elif restart:
            plugin_row.set_requires_restart(True)

        else:
            if manifest.version > plugin_row.version:
                plugin_row.set_update_available(True, manifest.version)

    def _on_plugin_added(self, event: PluginAdded) -> None:
        self._add_manifest(event.manifest, True)

    def _on_plugin_removed(self, event: PluginRemoved) -> None:
        row = self._plugin_rows[event.manifest.short_name]

        if not app.plugin_repository.contains(event.manifest.short_name):
            self.remove(row)
            return

        row.set_requires_restart(False)
        row.set_update_available(False)
        row.set_installed(False)

    def _on_install_plugin_from_zip(
        self, _button: FileChooserButton, paths: list[Path]
    ) -> None:
        if not paths:
            return

        zip_filename = str(paths[0])

        def _on_response() -> None:
            plugin = app.plugin_manager.install_from_zip(zip_filename, overwrite=True)
            if not plugin:
                InformationAlertDialog(_("Archive Malformed"), _("Archive is malformed"))
                return

        try:
            plugin = app.plugin_manager.install_from_zip(zip_filename)
        except PluginsystemError as er_type:
            error_text = str(er_type)
            if error_text == _("Plugin already exists"):
                ConfirmationAlertDialog(
                    _("Overwrite Plugin?"),
                    _("Do you want to overwrite the currently installed version?"),
                    confirm_label=_("_Overwrite"),
                    appearance="destructive",
                    callback=_on_response,
                )
                return

            InformationAlertDialog(error_text, f'"{zip_filename}"')
            return

        if not plugin:
            InformationAlertDialog(_("Archive Malformed"), _("Archive is malformed"))

    def _on_download_started(
        self,
        _repository: PluginRepositoryT,
        _signal_name: str,
        manifests: set[PluginManifest],
    ) -> None:
        for manifest in manifests:
            row = self._plugin_rows[manifest.short_name]
            row.set_update_available(False)
            row.set_error(False)
            row.set_downloading(True)

    def _on_download_failed(
        self,
        _repository: PluginRepositoryT,
        _signal_name: str,
        manifest: PluginManifest,
        error: str,
    ) -> None:
        row = self._plugin_rows[manifest.short_name]
        assert row is not None
        row.set_downloading(False)
        row.set_error(True, error)

    def _on_download_finished(
        self,
        _repository: PluginRepositoryT,
        _signal_name: str,
        manifest: PluginManifest,
    ) -> None:
        row = self._plugin_rows[manifest.short_name]
        assert row is not None
        row.set_downloading(False)
        row.update_manifest(manifest)

        activated = app.plugin_manager.update_plugins(
            replace=False, activate=True, plugin_name=manifest.short_name
        )
        if activated:
            row.set_installed(True)
        else:
            row.set_requires_restart(True)
            log.info("Plugin %s needs restart", manifest.short_name)

    def _on_plugin_updates_available(
        self,
        _repository: PluginRepository,
        _signal_name: str,
        manifests: list[PluginManifest],
    ) -> None:
        for manifest in manifests:
            row = self._plugin_rows[manifest.short_name]
            row.set_update_available(True, new_version=manifest.version)


@Gtk.Template(string=get_ui_string("plugin_row.ui"))
class PluginRow(Adw.ExpanderRow, SignalManager):
    __gtype_name__ = "PluginRow"

    _warning_icon: Gtk.Image = Gtk.Template.Child()
    _update_badge: Gtk.Label = Gtk.Template.Child()
    _requires_restart_badge: Gtk.Label = Gtk.Template.Child()
    _downloading_spinner: Adw.Spinner = Gtk.Template.Child()
    _config_button: Gtk.Button = Gtk.Template.Child()
    _enable_switch: Gtk.Switch = Gtk.Template.Child()
    _install_button: Gtk.Button = Gtk.Template.Child()
    _authors_row: Adw.ActionRow = Gtk.Template.Child()
    _url_row: Adw.ActionRow = Gtk.Template.Child()
    _version_row: Adw.ActionRow = Gtk.Template.Child()
    _warning_row: Adw.ActionRow = Gtk.Template.Child()
    _management_row: Adw.ActionRow = Gtk.Template.Child()
    _update_button: Gtk.Button = Gtk.Template.Child()
    _uninstall_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, manifest: PluginManifest, installed: bool) -> None:
        Adw.ExpanderRow.__init__(
            self, title=manifest.name, subtitle=manifest.description
        )
        SignalManager.__init__(self)

        self._manifest = manifest
        self._installed = installed

        self.add_prefix(self._get_plugin_icon())

        plugin = app.plugin_manager.get_plugin(manifest.short_name)
        plugin_active = plugin.active if plugin is not None else False

        self._connect(self._config_button, "clicked", self._on_config_clicked)
        self._enable_switch.set_active(plugin_active)
        self._connect(self._enable_switch, "state-set", self._on_enable_switch_toggled)
        self._connect(self._install_button, "clicked", self._on_install_clicked)
        self._connect(self._update_button, "clicked", self._on_install_clicked)
        self._connect(self._uninstall_button, "clicked", self._on_uninstall_clicked)

        self._update()

    def do_unroot(self) -> None:
        self._disconnect_all()
        Adw.ExpanderRow.do_unroot(self)

    @property
    def name(self) -> str:
        return self._manifest.name

    @property
    def version(self) -> Version:
        return self._manifest.version

    def set_installed(self, installed: bool) -> None:
        self._installed = installed
        self._update()

    def set_error(self, has_error: bool, error: str | None = None) -> None:
        self._warning_icon.set_visible(has_error)
        self._warning_icon.set_tooltip_text(error or "")

        self._warning_row.set_visible(has_error)
        self._warning_row.set_subtitle(error or "")

    def set_downloading(self, downloading: bool) -> None:
        self._downloading_spinner.set_visible(downloading)

    def set_requires_restart(self, requires_restart: bool) -> None:
        self._requires_restart_badge.set_visible(requires_restart)
        self._install_button.set_sensitive(not requires_restart)

    def set_update_available(
        self, update_available: bool, new_version: Version | None = None
    ) -> None:
        self._update_badge.set_visible(update_available)
        self._update_button.set_visible(update_available)
        self._update_button.set_sensitive(True)

        if update_available:
            self._management_row.set_subtitle(
                _("Update available: Version %s") % str(new_version)
            )
        else:
            self._management_row.set_subtitle("")

    def update_manifest(self, manifest: PluginManifest) -> None:
        self._manifest = manifest
        self._update()

    def _update(self) -> None:
        authors = [GLib.markup_escape_text(author) for author in self._manifest.authors]
        self._authors_row.set_subtitle("\n".join(authors))
        self._url_row.set_subtitle(
            f"<a href='{self._manifest.homepage}'>{self._manifest.homepage}</a>"
        )
        self._version_row.set_subtitle(str(self._manifest.version))

        has_error, error_text = self._get_error()
        self._warning_icon.set_visible(has_error)
        self._warning_icon.set_tooltip_text(error_text)

        self._warning_row.set_visible(has_error)
        self._warning_row.set_subtitle(error_text)

        plugin = app.plugin_manager.get_plugin(self._manifest.short_name)
        plugin_active = plugin.active if plugin is not None else False
        plugin_activatable = plugin.activatable if plugin is not None else False

        self._config_button.set_visible(
            self._installed and self._manifest.config_dialog and not has_error
        )
        self._config_button.set_sensitive(plugin_active)

        self._enable_switch.set_visible(self._installed and not has_error)
        self._enable_switch.set_sensitive(plugin_activatable)
        self._enable_switch.set_active(plugin_active)

        self._install_button.set_visible(not self._installed and not app.is_flatpak())
        self._install_button.set_sensitive(not self._installed)

        self._management_row.set_visible(self._installed and not app.is_flatpak())

    def _get_plugin_icon(self) -> Gtk.Image:
        image = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="lucide-package-symbolic"))

        image_name = f"{self._manifest.short_name}.png"
        path = configpaths.get("PLUGINS_IMAGES") / image_name
        if path.exists():
            texture = Gdk.Texture.new_from_filename(str(path))
            image.set_from_paintable(texture)
            return image

        plugin = app.plugin_manager.get_plugin(self._manifest.short_name)
        if plugin is None:
            return image

        path = Path(plugin.__path__) / image_name
        if path.exists():
            texture = Gdk.Texture.new_from_filename(str(path))
            image.set_from_paintable(texture)
            return image

        image.add_css_class("dimmed")
        return image

    def _get_error(self) -> tuple[bool, str]:
        if not self._installed:
            return False, ""

        plugin = app.plugin_manager.get_plugin(self._manifest.short_name)
        assert plugin is not None
        if not plugin.activatable:
            return True, plugin.available_text
        return False, ""

    def _on_enable_switch_toggled(self, _switch: Gtk.Switch, state: bool) -> None:
        self._config_button.set_sensitive(state)

        plugin = app.plugin_manager.get_plugin(self._manifest.short_name)
        assert plugin is not None

        if plugin.active:
            app.plugin_manager.deactivate_plugin(plugin)
        else:
            try:
                app.plugin_manager.activate_plugin(plugin)
            except GajimPluginActivateException as e:
                InformationAlertDialog(_("Plugin Failed"), str(e))
                return

    def _on_config_clicked(self, _button: Gtk.Button) -> None:
        plugin = app.plugin_manager.get_plugin(self._manifest.short_name)
        assert plugin is not None
        plugin.config_dialog(get_app_window("Preferences").window)  # pyright: ignore

    def _on_install_clicked(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.plugin_repository.download_plugins([self._manifest])

    def _on_uninstall_clicked(self, _button: Gtk.Button) -> None:
        plugin = app.plugin_manager.get_plugin(self._manifest.short_name)
        error_text = _("Unable to properly remove the plugin")
        if plugin is None:
            InformationAlertDialog(_("Warning"), error_text)
            return

        try:
            app.plugin_manager.uninstall_plugin(plugin)
        except PluginsystemError as error:
            InformationAlertDialog(_("Warning"), f"{error_text}\n{error}")
            return
