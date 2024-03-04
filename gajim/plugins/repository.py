# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast

import json
import logging
from collections.abc import Iterable
from io import BytesIO
from zipfile import ZipFile

from gi.repository import GLib
from nbxmpp.http import HTTPRequest

from gajim.common import app
from gajim.common import configpaths
from gajim.common.helpers import Observable
from gajim.common.util.http import create_http_request

from .manifest import PluginManifest

log = logging.getLogger('gajim.p.repository')


REPO_INDEX_FILENAME = 'package_index.json'
UPDATE_CHECK_INTERVAL = 68400


class PluginRepository(Observable):
    '''Signals

        - donwload-started
        - download-finished
        - download-failed
        - plugin-updates-available
        - auto-update-finished
    '''
    def __init__(self) -> None:
        Observable.__init__(self)
        self._manifests: dict[str, PluginManifest] = {}

        self._repository_url = ''
        self._repository_index_url = ''
        self._download_path = configpaths.get('PLUGINS_DOWNLOAD')

        self._auto_update_in_progress = False

        self._download_queue: set[PluginManifest] = set()

        if app.settings.get('plugins_repository_enabled'):
            request = create_http_request()
            request.send('GET', 'https://gajim.org/updates.json',
                         callback=self._on_repository_received)

    @property
    def available(self):
        return bool(self._repository_url)

    def _on_repository_received(self, request: HTTPRequest) -> None:

        if not request.is_complete():
            log.warning('Repository retrieval failed: %s',
                        request.get_error_string())
            return

        try:
            updates = json.loads(request.get_data())
        except Exception as error:
            log.warning('Unable to parse repository information: %s', error)
            return

        repository_url = updates.get('plugin_repository')
        if repository_url is None:
            log.warning('No plugin repository url found')
            return

        self.set_repository(repository_url)

    def get_manifests(self) -> list[PluginManifest]:
        return list(self._manifests.values())

    def contains(self, short_name: str) -> bool:
        return self._manifests.get(short_name) is not None

    def set_repository(self, repository_url: str) -> None:
        self._repository_url = repository_url
        self._repository_index_url = f'{repository_url}/{REPO_INDEX_FILENAME}'
        self._refresh_plugin_index()
        if app.settings.get('plugins_update_check'):
            GLib.timeout_add_seconds(30, self._check_if_updates_are_needed)

    def _refresh_update_check_timer(self, seconds: int) -> None:
        GLib.timeout_add_seconds(seconds,
                                 self._refresh_plugin_index,
                                 self._check_if_updates_are_needed)

    def _plugin_needs_update(self, manifest: PluginManifest) -> bool:
        installed_plugin = app.plugin_manager.get_plugin(manifest.short_name)
        if installed_plugin is None:
            return False

        path = configpaths.get('PLUGINS_DOWNLOAD') / manifest.short_name
        if path.exists():
            return False

        return installed_plugin.manifest.version < manifest.version

    def _parse_package_json(self,
                            package_index: dict[str, Any]
                            ) -> dict[str, PluginManifest]:

        suitable_plugins: dict[str, PluginManifest] = {}
        plugins = package_index['plugins']
        for name, versions in plugins.items():
            for version, manifest in versions.items():
                manifest['short_name'] = name
                manifest['version'] = version
                try:
                    manifest = PluginManifest.from_manifest_json(manifest)
                except Exception as error:
                    log.info('Invalid manifest: %s', error)
                    continue

                if not manifest.is_usable:
                    log.info('Ignore not suitable plugin: %s %s',
                             manifest.short_name, manifest.version)
                    continue

                last_plugin = suitable_plugins.get(manifest.short_name)
                if (last_plugin is None or
                        last_plugin.version < manifest.version):
                    suitable_plugins[manifest.short_name] = manifest

        return suitable_plugins

    def _refresh_plugin_index(self, callback: Any | None = None) -> None:
        log.info('Refresh index')
        request = create_http_request()
        request.set_user_data(callback)
        request.send('GET', self._repository_index_url,
                     callback=self._on_index_received)

    def _on_index_received(self, request: HTTPRequest) -> None:

        if not request.is_complete():
            log.warning('Refresh failed: %s %s',
                        self._repository_index_url,
                        request.get_error_string())
            return

        try:
            package_index = json.loads(request.get_data())
        except Exception as error:
            log.warning('Unable to parse repository index: %s', error)
            return

        self._manifests = self._parse_package_json(package_index)

        image_path = package_index['metadata']['image_path']
        callback = request.get_user_data()

        request = create_http_request()
        request.send('GET', f'{self._repository_url}/{image_path}',
                     callback=self._on_images_received)

        log.info('Refresh successful')

        if callback is not None:
            callback()

    def _on_images_received(self, request: HTTPRequest) -> None:

        if not request.is_complete():
            log.warning('Image download failed: %s', request.get_error_string())
            return

        path = configpaths.get('PLUGINS_IMAGES')

        try:
            zipfile = ZipFile(BytesIO(request.get_data()))
            zipfile.extractall(path)
        except Exception as error:
            log.warning('Failed to extract images: %s', error)

    def _check_if_updates_are_needed(self) -> None:
        plugins_to_update: list[PluginManifest] = []
        for manifest in self._manifests.values():
            if not self._plugin_needs_update(manifest):
                continue

            log.info('Update available for: %s - %s',
                     manifest.short_name, manifest.version)
            plugins_to_update.append(manifest)

        if not plugins_to_update:
            log.info('No updates available')
            return

        if app.settings.get('plugins_auto_update'):
            self._auto_update_in_progress = True
            self.download_plugins(plugins_to_update)
        else:
            self.notify('plugin-updates-available', plugins_to_update)

        self._refresh_update_check_timer(UPDATE_CHECK_INTERVAL)

    def download_plugins(self, manifests: Iterable[PluginManifest]) -> None:
        if not self._repository_url:
            log.warning('Unable to download plugins because repository not set')
            return

        manifests = [self._manifests[manifest.short_name] for manifest
                     in manifests]

        manifests = set(manifests) - self._download_queue
        if not manifests:
            return

        self._download_queue |= manifests
        self.notify('download-started', manifests)

        for manifest in manifests:
            self._download_plugin(manifest)

    def _download_plugin(self, manifest: PluginManifest) -> None:
        log.info('Download plugin %s', manifest.short_name)
        url = manifest.get_remote_url(self._repository_url)
        request = create_http_request()
        request.set_user_data(manifest)
        request.send('GET', url,
                     callback=self._on_download_plugin_finished)

    def _on_download_plugin_finished(self, request: HTTPRequest) -> None:

        manifest = cast(PluginManifest, request.get_user_data())
        self._download_queue.remove(manifest)

        if not request.is_complete():
            error = request.get_error_string()
            log.error('Download failed: %s %s',
                      manifest.get_remote_url(self._repository_url),
                      error)
            self.notify('download-failed', manifest, error)
            return

        with ZipFile(BytesIO(request.get_data())) as zip_file:
            zip_file.extractall(self._download_path / manifest.short_name)

        log.info('Finished downloading %s', manifest.short_name)
        self.notify('download-finished', manifest)

        if len(self._download_queue) == 0:
            if self._auto_update_in_progress:
                self._auto_update_in_progress = False
                if app.settings.get('plugins_notify_after_update'):
                    self.notify('auto-update-finished')
