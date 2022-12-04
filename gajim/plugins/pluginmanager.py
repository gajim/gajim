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

from __future__ import annotations

from typing import Any
from typing import Optional

import os
import sys
import json
import zipfile
import logging
from shutil import rmtree, move
from dataclasses import dataclass
from pathlib import Path
from importlib.util import spec_from_file_location
from importlib.util import module_from_spec

from packaging.version import Version as V
from packaging.requirements import Requirement

import gajim
from gajim.common import app
from gajim.common import configpaths
from gajim.common import modules
from gajim.common.client import Client
from gajim.common.events import PluginAdded
from gajim.common.events import PluginRemoved
from gajim.common.i18n import _
from gajim.common.exceptions import PluginsystemError
from gajim.common.helpers import Singleton
from gajim.plugins.plugins_i18n import _ as p_

from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.helpers import is_shipped_plugin
from gajim.plugins.gajimplugin import GajimPlugin
from gajim.plugins.gajimplugin import GajimPluginException

log = logging.getLogger('gajim.p.manager')


BLOCKED_PLUGINS = [
    'appindicator_integration',
    'plugin_installer',
    'syntax_highlight',
    'url_image_preview'
]

FIELDS = ('name',
          'short_name',
          'version',
          'description',
          'authors',
          'homepage')

GAJIM_VERSION = V(gajim.__version__.split('+', 1)[0]).base_version


@dataclass(frozen=True, eq=True)
class PluginManifest:
    name: str
    short_name: str
    description: str
    authors: list[str]
    homepage: str
    config_dialog: bool
    version: V
    requirements: list[Requirement]
    platforms: list[str]
    path: Optional[Path] = None

    def __hash__(self):
        return hash(f'{self.short_name}_{self.version}')

    @property
    def is_usable(self) -> bool:
        if self.short_name in BLOCKED_PLUGINS:
            return False

        if not self._check_requirements():
            return False

        platform = sys.platform
        if platform not in ('win32', 'darwin', 'linux'):
            # sys.platform can return an unknown amount of unix/linux derivates
            platform = 'others'

        return platform in self.platforms

    @property
    def is_shipped(self) -> bool:
        if self.path is None:
            return False
        return is_shipped_plugin(self.path)

    def get_remote_url(self, repository_url: str) -> str:
        filename = f'{self.short_name}_{self.version}.zip'
        return f'{repository_url}/{self.short_name}/{filename}'

    @classmethod
    def from_path(cls, path: Path) -> PluginManifest:
        manifest_path = path / 'plugin-manifest.json'
        if not manifest_path.exists():
            raise ValueError(f'Not a plugin path: {path}')

        if manifest_path.is_dir():
            raise ValueError(f'Not a plugin path: {path}')

        with manifest_path.open(encoding='utf8') as f:
            try:
                manifest = json.load(f)
            except Exception as error:
                raise ValueError(f'Error while parsing manifest: '
                                 f'{path}, {error}')
        return cls.from_manifest_json(manifest, manifest_path)

    def _check_requirements(self) -> bool:
        for req in self.requirements:
            if GAJIM_VERSION in req.specifier:
                return True
        return False

    @classmethod
    def from_manifest_json(cls,
                           manifest: dict[str, Any],
                           path: Optional[Path] = None) -> PluginManifest:
        return cls(
            name=manifest['name'],
            short_name=manifest['short_name'],
            description=p_(manifest['description']),
            authors=manifest['authors'],
            homepage=manifest['homepage'],
            config_dialog=manifest['config_dialog'],
            version=V(manifest['version']),
            requirements=[Requirement(r) for r in manifest['requirements']],
            platforms=manifest['platforms'],
            path=path.parent if path is not None else path)


class PluginManager(metaclass=Singleton):
    '''
    Main plug-in management class.
    '''

    def __init__(self):
        self.plugins: list[GajimPlugin] = []
        '''
        Detected plugin classes.

        Each class object in list is `GajimPlugin` subclass.
        '''
        self.active_plugins: list[GajimPlugin] = []
        '''
        Instance objects of active plugins.

        These are object instances of classes held `plugins`, but only those
        that were activated.
        '''
        self.gui_extension_points: dict[str, Any] = {}
        '''
        Registered GUI extension points.
        '''

        self.gui_extension_points_handlers: dict[str, Any] = {}
        '''
        Registered handlers of GUI extension points.
        '''

        self.encryption_plugins: dict[str, GajimPlugin] = {}
        '''
        Registered names with instances of encryption Plugins.
        '''

        self.update_plugins()
        self._load_manifests()

    def update_plugins(self,
                       replace: bool = True,
                       activate: bool = False,
                       plugin_name: Optional[str] = None
                       ) -> list[str]:
        '''
        Move plugins from the downloaded folder to the user plugin folder

        :param replace: replace plugin files if they already exist.
        :param activate: load and activate the plugin
        :param plugin_name: if provided, update only this plugin
        :return: list of updated plugins (files have been installed)
        '''
        updated_plugins: list[str] = []
        user_dir = configpaths.get('PLUGINS_USER')
        dl_dir = configpaths.get('PLUGINS_DOWNLOAD')
        to_update = [plugin_name] if plugin_name else next(os.walk(dl_dir))[1]
        for directory in to_update:
            src_dir = dl_dir / directory
            dst_dir = user_dir / directory
            try:
                if dst_dir.exists():
                    if not replace:
                        continue
                    self.delete_plugin_files(dst_dir)
                move(src_dir, dst_dir)
            except Exception:
                log.exception('Upgrade of plugin %s failed. '
                              'Impossible to move files from "%s" to "%s"',
                              directory, src_dir, dst_dir)
                continue
            updated_plugins.append(directory)
            if activate:
                manifest = self._load_manifest(Path(dst_dir))
                if manifest is None or not manifest.is_usable:
                    log.warning('Error while updating plugin')
                    continue

                self.add_plugin(manifest, activate=True)
        return updated_plugins

    def init_plugins(self) -> None:
        for plugin in self.plugins:
            if not app.settings.get_plugin_setting(plugin.manifest.short_name,
                                                   'active'):
                continue
            if not plugin.activatable:
                continue

            try:
                self.activate_plugin(plugin)
            except GajimPluginActivateException as error:
                plugin.activatable = False
                plugin.available_text = str(error)

    def _load_plugin_module(self,
                            manifest: PluginManifest
                            ) -> Optional[type[GajimPlugin]]:

        assert manifest.path is not None
        module_path = manifest.path / '__init__.py'
        if not module_path.exists():
            # On Windows we only ship compiled files
            module_path = manifest.path / '__init__.pyc'

        module_name = manifest.path.stem

        try:
            spec = spec_from_file_location(module_name, module_path)
            if spec is None:
                return None
            module = module_from_spec(spec)
            sys.modules[spec.name] = module
            assert spec.loader is not None
            spec.loader.exec_module(module)
        except Exception as error:
            log.warning('Error while loading module: %s', error)
            return None

        for module_attr_name in dir(module):
            module_attr = getattr(module, module_attr_name)
            if issubclass(module_attr, GajimPlugin):
                module_attr.manifest = manifest
                module_attr.__path__ = str(manifest.path)
                return module_attr
        return None

    def add_plugin(self,
                   manifest: PluginManifest,
                   activate: bool = False
                   ) -> Optional[GajimPlugin]:

        plugin_class = self._load_plugin_module(manifest)
        if plugin_class is None:
            return None

        if manifest in [p.manifest for p in self.plugins]:
            log.info('Not loading plugin %s v %s. Plugin already loaded.',
                     manifest.short_name,
                     manifest.version)
            return None

        try:
            plugin_obj = plugin_class()
        except Exception:
            log.exception('Error while loading a plugin')
            return None

        if manifest.short_name not in app.settings.get_plugins():
            app.settings.set_plugin_setting(manifest.short_name,
                                            'active',
                                            manifest.is_shipped)

        self.plugins.append(plugin_obj)
        plugin_obj.active = False

        if activate:
            self.activate_plugin(plugin_obj)

        app.ged.raise_event(PluginAdded(manifest=manifest))

        return plugin_obj

    def remove_plugin(self, plugin: GajimPlugin) -> None:
        '''
        removes the plugin from the plugin list and deletes all loaded modules
        from sys. This way we will have a fresh start when the plugin gets added
        again.
        '''
        if plugin.active:
            self.deactivate_plugin(plugin)

        self.plugins.remove(plugin)

        # remove modules from cache
        base_package = plugin.__module__.split('.')[0]
        # get the subpackages/-modules of the base_package. Add a dot to the
        # name to avoid name problems (removing module_abc if base_package is
        # module_ab)
        modules_to_remove = [module for module in sys.modules
                             if module.startswith('{}.'.format(base_package))]
        # remove the base_package itself
        if base_package in sys.modules:
            modules_to_remove.append(base_package)

        for module_to_remove in modules_to_remove:
            del sys.modules[module_to_remove]

    def get_active_plugin(self, plugin_name: str) -> Optional[GajimPlugin]:
        for plugin in self.active_plugins:
            if plugin.manifest.short_name == plugin_name:
                return plugin
        return None

    def get_plugin(self, short_name: str) -> Optional[GajimPlugin]:
        for plugin in self.plugins:
            if plugin.manifest.short_name == short_name:
                return plugin
        return None

    def extension_point(self, gui_extpoint_name: str, *args: Any) -> None:
        '''
        Invokes all handlers (from plugins) for a particular extension point,
        but doesn't add it to collection for further processing.
        For example if you pass a message for encryption via extension point to
        a plugin, its undesired that the call is stored and replayed on
        activating the plugin. For example after an update.

        :param gui_extpoint_name: name of GUI extension point.
        :param args: parameters to be passed to extension point handlers
                (typically and object that invokes `gui_extension_point`;
                however, this can be practically anything)
        :type args: tuple
        '''

        self._execute_all_handlers_of_gui_extension_point(
            gui_extpoint_name, *args)

    def gui_extension_point(self, gui_extpoint_name: str, *args: Any) -> None:
        '''
        Invokes all handlers (from plugins) for particular GUI extension point
        and adds it to collection for further processing (eg. by plugins not
        active yet).

        :param gui_extpoint_name: name of GUI extension point.
        :param args: parameters to be passed to extension point handlers
                (typically and object that invokes `gui_extension_point`;
                however, this can be practically anything)
        :type args: tuple
        '''

        self._add_gui_extension_point_call_to_list(gui_extpoint_name, *args)
        self._execute_all_handlers_of_gui_extension_point(
            gui_extpoint_name,
            *args)

    def remove_gui_extension_point(self,
                                   gui_extpoint_name: str,
                                   *args: Any
                                   ) -> None:
        '''
        Removes GUI extension point from collection held by `PluginManager`.

        From this point this particular extension point won't be visible
        to plugins (eg. it won't invoke any handlers when plugin is activated).

        GUI extension point is removed completely (there is no way to recover it
        from inside `PluginManager`).

        Removal is needed when instance object that given extension point was
        connect with is destroyed (eg. ChatControl is closed or context menu
        is hidden).

        Each `PluginManager.gui_extension_point` call should have a call of
        `PluginManager.remove_gui_extension_point` related to it.

        :note: in current implementation different arguments mean different
                extension points. The same arguments and the same name mean
                the same extension point.

        :param gui_extpoint_name: name of GUI extension point.
        :param args: arguments that `PluginManager.gui_extension_point` was
                called with for this extension point. This is used (along with
                extension point name) to identify element to be removed.
        :type args: tuple
        '''
        if gui_extpoint_name in self.gui_extension_points:
            extension_points = list(self.gui_extension_points[
                gui_extpoint_name])
            for ext_point in extension_points:
                if args[0] in ext_point:
                    self.gui_extension_points[gui_extpoint_name].remove(
                        ext_point)

        if gui_extpoint_name not in self.gui_extension_points_handlers:
            return

        for handlers in self.gui_extension_points_handlers[gui_extpoint_name]:
            disconnect_handler = handlers[1]
            if disconnect_handler is not None:
                disconnect_handler(args[0])

    def _add_gui_extension_point_call_to_list(self,
                                              gui_extpoint_name: str,
                                              *args: Any
                                              ) -> None:
        '''
        Adds GUI extension point call to list of calls.

        This is done only if such call hasn't been added already
        (same extension point name and same arguments).

        :note: This is assumption that GUI extension points are different only
        if they have different name or different arguments.

        :param gui_extpoint_name: GUI extension point name used to identify it
                by plugins.
        :param args: parameters to be passed to extension point handlers
                (typically and object that invokes `gui_extension_point`;
                however, this can be practically anything)
        :type args: tuple

        '''
        if (gui_extpoint_name not in self.gui_extension_points or
                args not in self.gui_extension_points[gui_extpoint_name]):
            self.gui_extension_points.setdefault(gui_extpoint_name, []).append(
                args)

    def _execute_all_handlers_of_gui_extension_point(self,
                                                     gui_extpoint_name: str,
                                                     *args: Any
                                                     ) -> None:
        if gui_extpoint_name in self.gui_extension_points_handlers:
            for handlers in self.gui_extension_points_handlers[
                    gui_extpoint_name]:
                try:
                    handlers[0](*args)
                except Exception:
                    log.warning('Error executing %s',
                                handlers[0], exc_info=True)

    def _register_events_handlers_in_ged(self, plugin: GajimPlugin) -> None:
        for event_name, handler in plugin.events_handlers.items():
            priority = handler[0]
            handler_function = handler[1]
            app.ged.register_event_handler(
                event_name, priority, handler_function)

    def _remove_events_handler_from_ged(self, plugin: GajimPlugin) -> None:
        for event_name, handler in plugin.events_handlers.items():
            priority = handler[0]
            handler_function = handler[1]
            app.ged.remove_event_handler(
                event_name, priority, handler_function)

    def _remove_name_from_encryption_plugins(self,
                                             plugin: GajimPlugin
                                             ) -> None:
        if plugin.encryption_name:
            del self.encryption_plugins[plugin.encryption_name]

    def _register_modules_with_handlers(self, plugin: GajimPlugin) -> None:
        if not hasattr(plugin, 'modules'):
            return
        for client in app.get_clients():
            for module in plugin.modules:
                instance, name = module.get_instance(client)
                modules.register_single_module(client, instance, name)

                for handler in instance.handlers:
                    client.connection.register_handler(handler)

    def _unregister_modules_with_handlers(self, plugin: GajimPlugin) -> None:
        if not hasattr(plugin, 'modules'):
            return
        for client in app.get_clients():
            for module in plugin.modules:
                instance = client.get_module(module.name)
                modules.unregister_single_module(client, module.name)

                for handler in instance.handlers:
                    client.connection.unregister_handler(handler)

    def activate_plugin(self, plugin: GajimPlugin) -> None:
        '''
        :param plugin: plugin to be activated
        :type plugin: class object of `GajimPlugin` subclass
        '''
        if not plugin.active and plugin.activatable:

            self._add_gui_extension_points_handlers_from_plugin(plugin)
            self._add_encryption_name_from_plugin(plugin)
            self._handle_all_gui_extension_points_with_plugin(plugin)
            self._register_events_handlers_in_ged(plugin)
            self._register_modules_with_handlers(plugin)

            self.active_plugins.append(plugin)
            try:
                plugin.activate()
            except GajimPluginException as e:
                self.deactivate_plugin(plugin)
                raise GajimPluginActivateException(str(e))
            app.settings.set_plugin_setting(plugin.manifest.short_name,
                                            'active',
                                            True)
            plugin.active = True

    def deactivate_plugin(self, plugin: GajimPlugin) -> None:
        # remove GUI extension points handlers (provided by plug-in) from
        # handlers list
        for gui_extpoint_name, gui_extpoint_handlers in \
                plugin.gui_extension_points.items():
            self.gui_extension_points_handlers[gui_extpoint_name].remove(
                gui_extpoint_handlers)

        # detaching plug-in from handler GUI extension points (calling
        # cleaning up method that must be provided by plug-in developer
        # for each handled GUI extension point)
        for gui_extpoint_name, gui_extpoint_handlers in \
                plugin.gui_extension_points.items():
            if gui_extpoint_name in self.gui_extension_points:
                for gui_extension_point_args in self.gui_extension_points[
                        gui_extpoint_name]:
                    handler = gui_extpoint_handlers[1]
                    if handler:
                        try:
                            handler(*gui_extension_point_args)
                        except Exception:
                            log.warning('Error executing %s',
                                        handler, exc_info=True)

        self._remove_events_handler_from_ged(plugin)
        self._remove_name_from_encryption_plugins(plugin)

        # deactivate() must be before _unregister_modules_with_handlers(),
        # because plugin.deactivate() may want to use the module
        plugin.deactivate()

        self._unregister_modules_with_handlers(plugin)
        self.active_plugins.remove(plugin)
        app.settings.set_plugin_setting(plugin.manifest.short_name,
                                        'active',
                                        False)
        plugin.active = False

    def _add_gui_extension_points_handlers_from_plugin(self,
                                                       plugin: GajimPlugin
                                                       ) -> None:
        for gui_extpoint_name, gui_extpoint_handlers in \
                plugin.gui_extension_points.items():
            self.gui_extension_points_handlers.setdefault(
                gui_extpoint_name, []).append(gui_extpoint_handlers)

    def _add_encryption_name_from_plugin(self, plugin: GajimPlugin) -> None:
        if plugin.encryption_name:
            self.encryption_plugins[plugin.encryption_name] = plugin

    def _handle_all_gui_extension_points_with_plugin(self,
                                                     plugin: GajimPlugin
                                                     ) -> None:
        for gui_extpoint_name, gui_extpoint_handlers in \
                plugin.gui_extension_points.items():
            if gui_extpoint_name in self.gui_extension_points:
                for gui_extension_point_args in self.gui_extension_points[
                        gui_extpoint_name]:
                    handler = gui_extpoint_handlers[0]
                    if handler:
                        try:
                            handler(*gui_extension_point_args)
                        except Exception:
                            log.warning('Error executing %s',
                                        handler, exc_info=True)

    def register_modules_for_account(self, client: Client) -> None:
        '''
        A new account has been added, register modules
        of all active plugins
        '''
        for plugin in self.plugins:
            if not plugin.active:
                continue

            if not hasattr(plugin, 'modules'):
                continue

            for module in plugin.modules:
                instance, name = module.get_instance(client)
                modules.register_single_module(client, instance, name)

                for handler in instance.handlers:
                    client.connection.register_handler(handler)

    @staticmethod
    def _load_manifest(plugin_path: Path) -> Optional[PluginManifest]:
        try:
            return PluginManifest.from_path(plugin_path)
        except Exception as error:
            log.warning('Unable to load manifest: %s', error)
            return None

    def _load_manifests(self) -> None:
        manifests: dict[str, PluginManifest] = {}
        for plugin_dir in configpaths.get_plugin_dirs():
            if not plugin_dir.is_dir():
                continue

            for plugin_path in plugin_dir.iterdir():
                manifest = self._load_manifest(plugin_path)
                if manifest is None:
                    continue

                if not manifest.is_usable:
                    log.info('Skipped plugin with not suitable requirements')
                    continue

                same_plugin = manifests.get(manifest.short_name)
                if same_plugin is not None:
                    if same_plugin.version > manifest.version:
                        continue

                log.info('Found plugin %s %s',
                         manifest.short_name, manifest.version)
                manifests[manifest.short_name] = manifest

        for manifest in manifests.values():
            self.add_plugin(manifest)

    def install_from_zip(self,
                         zip_filename: str,
                         overwrite: bool = False
                         ) -> Optional[GajimPlugin]:
        '''
        Install plugin from zip and return plugin
        '''
        try:
            zip_file = zipfile.ZipFile(zip_filename)
        except zipfile.BadZipfile:
            # it is not zip file
            raise PluginsystemError(_('Archive corrupted'))
        except IOError:
            raise PluginsystemError(_('Archive empty'))

        if zip_file.testzip():
            # CRC error
            raise PluginsystemError(_('Archive corrupted'))

        dirs: list[str] = []
        manifest = None
        for filename in zip_file.namelist():
            if (filename.startswith('.') or filename.startswith('/') or
                    ('/' not in filename)):
                # members not safe
                raise PluginsystemError(_('Archive is malformed'))
            if filename.endswith('/') and filename.find('/', 0, -1) < 0:
                dirs.append(filename.strip('/'))
            if 'plugin-manifest.json' in filename.split('/')[1]:
                manifest = True
        if not manifest:
            return None
        if len(dirs) > 1:
            raise PluginsystemError(_('Archive is malformed'))

        plugin_name = dirs[0]
        user_dir = configpaths.get('PLUGINS_USER')
        plugin_path = user_dir / plugin_name

        if plugin_path.exists():
            # Plugin dir already exists
            if not overwrite:
                raise PluginsystemError(_('Plugin already exists'))
            plugin = self.get_plugin_by_path(str(plugin_path))
            assert isinstance(plugin, GajimPlugin)
            self.uninstall_plugin(plugin)

        zip_file.extractall(user_dir)
        zip_file.close()

        manifest = self._load_manifest(plugin_path)
        if manifest is None or not manifest.is_usable:
            log.warning('Error while installing from zip')
            rmtree(plugin_path)
            raise PluginsystemError(_('Installation failed'))

        return self.add_plugin(manifest)

    def delete_plugin_files(self, plugin_path: Path) -> None:
        def on_error(func, path, error):
            if func is os.path.islink:
                # if symlink
                os.unlink(path)
                return
            # access is denied or other
            raise PluginsystemError(str(error[1]))

        rmtree(plugin_path, False, on_error)

    def uninstall_plugin(self, plugin: GajimPlugin) -> None:
        '''
        Deactivate and remove plugin from `plugins` list
        '''
        if not plugin:
            return

        self.remove_plugin(plugin)
        self.delete_plugin_files(Path(plugin.__path__))
        if not is_shipped_plugin(Path(plugin.__path__)):
            path = configpaths.get('PLUGINS_BASE') / plugin.manifest.short_name
            if path.exists():
                self.delete_plugin_files(path)

        path = configpaths.get('PLUGINS_DOWNLOAD') / plugin.manifest.short_name
        if path.exists():
            self.delete_plugin_files(path)

        app.settings.remove_plugin(plugin.manifest.short_name)

        app.ged.raise_event(PluginRemoved(manifest=plugin.manifest))

    def get_plugin_by_path(self, plugin_dir: str) -> Optional[GajimPlugin]:
        for plugin in self.plugins:
            if plugin.__path__ in plugin_dir:
                return plugin
        return None
