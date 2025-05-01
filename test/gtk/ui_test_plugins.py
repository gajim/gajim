# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import cast

from pathlib import Path
from unittest.mock import MagicMock

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common.helpers import Observable
from gajim.plugins.events import PluginRemoved
from gajim.plugins.manifest import PluginManifest

from gajim.gtk.plugins import PluginsWindow

from . import util

plugin_a_data = {
    "name": "Plugin A",
    "short_name": "plugin_a",
    "description": "Plugin A description",
    "authors": ["Author 1"],
    "homepage": "example.org",
    "config_dialog": False,
    "version": "1.0.0",
    "requirements": [],
    "platforms": [],
}
plugin_a_data_update = {
    "name": "Plugin A",
    "short_name": "plugin_a",
    "description": "Plugin A description",
    "authors": ["Author 1", "Author 2"],
    "homepage": "example.org/plugin",
    "config_dialog": False,
    "version": "1.0.1",
    "requirements": [],
    "platforms": [],
}
plugin_b_data = {
    "name": "Plugin B",
    "short_name": "plugin_b",
    "description": "Plugin B description",
    "authors": ["author"],
    "homepage": "example.org",
    "config_dialog": False,
    "version": "1.0.0",
    "requirements": [],
    "platforms": [],
}
plugin_c_data = {
    "name": "Plugin C",
    "short_name": "plugin_c",
    "description": "Plugin C description",
    "authors": ["author"],
    "homepage": "example.org",
    "config_dialog": False,
    "version": "1.0.0",
    "requirements": [],
    "platforms": [],
}


class GajimPluginTest:
    def __init__(self, manifest: PluginManifest) -> None:
        self._manifest = manifest

    @property
    def active(self) -> bool:
        return True

    @property
    def activatable(self) -> bool:
        return True

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    @property
    def __path__(self) -> Path:
        return Path("")


class PluginManagerTest:
    def __init__(self) -> None:
        self._plugins: list[GajimPluginTest] = [
            GajimPluginTest(PluginManifest.from_manifest_json(plugin_a_data))
        ]

    @property
    def plugins(self) -> list[GajimPluginTest]:
        return self._plugins

    def get_plugin(self, short_name: str) -> GajimPluginTest | None:
        for plugin in self.plugins:
            if plugin.manifest.short_name == short_name:
                return plugin
        return None

    def deactivate_plugin(self, plugin: GajimPluginTest) -> None:
        pass

    def update_plugins(
        self,
        replace: bool = True,
        activate: bool = False,
        plugin_name: str | None = None,
    ) -> list[str]:
        return ["asd"]

    def mock_update_plugins(self, manifests: list[PluginManifest]) -> None:
        for manifest in manifests:
            for plugin in self._plugins:
                if plugin.manifest.short_name == manifest.short_name:
                    self._plugins.remove(plugin)

            self._plugins.append(GajimPluginTest(manifest=manifest))

    def uninstall_plugin(self, plugin: GajimPluginTest) -> None:
        self.plugins.remove(plugin)
        app.ged.raise_event(PluginRemoved(manifest=plugin.manifest))


class PluginRepositoryTest(Observable):
    def __init__(self) -> None:
        Observable.__init__(self)

        self._manifests: list[PluginManifest] = [
            PluginManifest.from_manifest_json(plugin_a_data),
            PluginManifest.from_manifest_json(plugin_b_data),
            PluginManifest.from_manifest_json(plugin_c_data),
        ]

    def get_manifests(self) -> list[PluginManifest]:
        return self._manifests

    def contains(self, short_name: str) -> bool:
        return True

    def download_plugins(self, manifests: list[PluginManifest]) -> None:
        self.notify("download-started", manifests)
        # Notify with repository manifests
        finished_updates: list[PluginManifest] = []
        for manifest in manifests:
            for repo_manifest in self._manifests:
                if repo_manifest.short_name == manifest.short_name:
                    finished_updates.append(repo_manifest)

        app.plugin_manager.mock_update_plugins(finished_updates)  # type: ignore

        GLib.timeout_add_seconds(1, self._notify_finished, finished_updates)

    def _notify_finished(self, manifests: list[PluginManifest]) -> None:
        for manifest in manifests:
            self.notify("download-finished", manifest)

    def trigger_updates_available(self) -> None:
        self._manifests = [
            PluginManifest.from_manifest_json(plugin_a_data_update),
            PluginManifest.from_manifest_json(plugin_b_data),
            PluginManifest.from_manifest_json(plugin_c_data),
        ]
        self.notify("plugin-updates-available", [self._manifests[0]])


util.init_settings()

app.plugin_manager = PluginManagerTest()
app.plugin_repository = PluginRepositoryTest()


def _on_trigger_update_clicked(_button: Gtk.Button) -> None:
    app.plugin_repository.trigger_updates_available()  # type: ignore


configpaths.get = MagicMock(return_value=Path())

window = PluginsWindow()
window.window.set_default_size(600, 800)

box = cast(Gtk.Box, util.get_content_widget(window))

controls_box = Gtk.Box(spacing=12)
box.prepend(controls_box)

update_button = Gtk.Button(label="Trigger Update")
update_button.connect("clicked", _on_trigger_update_clicked)
controls_box.append(update_button)

window.show()

util.run_app()
