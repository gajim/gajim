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
Plug-in management related classes.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 30th May 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

__all__ = ['PluginManager']

import os
import sys
import zipfile
from pathlib import Path
from importlib.util import spec_from_file_location
from importlib.util import module_from_spec
from shutil import rmtree, move
import configparser
from dataclasses import dataclass
from packaging.version import Version as V

import gajim
from gajim.common import app
from gajim.common import nec
from gajim.common import configpaths
from gajim.common import modules
from gajim.common.nec import NetworkEvent
from gajim.common.i18n import _
from gajim.common.exceptions import PluginsystemError
from gajim.common.helpers import Singleton
from gajim.plugins.plugins_i18n import _ as p_

from gajim.plugins.helpers import log
from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.helpers import is_shipped_plugin
from gajim.plugins.gajimplugin import GajimPlugin, GajimPluginException


FIELDS = ('name',
          'short_name',
          'version',
          'min_gajim_version',
          'max_gajim_version',
          'description',
          'authors',
          'homepage')


@dataclass
class Plugin:
    name: str
    short_name: str
    description: str
    authors: str
    homepage: str
    version: V
    min_gajim_version: V
    max_gajim_version: V
    shipped: bool
    path: Path

    @classmethod
    def from_manifest(cls, path):
        shipped = is_shipped_plugin(path)
        manifest = path / 'manifest.ini'
        if not manifest.exists() and not manifest.is_dir():
            raise ValueError(f'Not a plugin path: {path}')

        conf = configparser.ConfigParser()
        conf.remove_section('info')

        with manifest.open() as conf_file:
            try:
                conf.read_file(conf_file)
            except configparser.Error as error:
                raise ValueError(f'Error while parsing manifest: '
                                 f'{path.name}, {error}')

        for field in FIELDS:
            try:
                value = conf.get('info', field, fallback=None)
            except configparser.Error as error:
                raise ValueError(f'Error while parsing manifest: '
                                 f'{path.name}, {error}')

            if value is None:
                raise ValueError(f'No {field} found for {path.name}')

        name = conf.get('info', 'name')
        short_name = conf.get('info', 'short_name')
        description = p_(conf.get('info', 'description'))
        authors = conf.get('info', 'authors')
        homepage = conf.get('info', 'homepage')
        version = V(conf.get('info', 'version'))
        min_gajim_version = V(conf.get('info', 'min_gajim_version'))
        max_gajim_version = V(conf.get('info', 'max_gajim_version'))
        gajim_version = V(gajim.__version__.split('+', 1)[0])

        if not min_gajim_version <= gajim_version <= max_gajim_version:
            raise ValueError(
                f'Plugin {path.name} not loaded, '
                f'newer version of gajim required: '
                f'{min_gajim_version} <= {gajim_version} <= {max_gajim_version}'
            )

        return cls(name=name,
                   short_name=short_name,
                   description=description,
                   authors=authors,
                   homepage=homepage,
                   version=version,
                   min_gajim_version=min_gajim_version,
                   max_gajim_version=max_gajim_version,
                   shipped=shipped,
                   path=path)

    def load_module(self):
        moduel_path = self.path / '__init__.py'
        module_name = self.path.stem

        try:
            spec = spec_from_file_location(module_name, moduel_path)
            if spec is None:
                return None
            module = module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        except Exception as error:
            log.warning('Error while loading module: %s', error)
            return None

        for module_attr_name in dir(module):
            module_attr = getattr(module, module_attr_name)
            if issubclass(module_attr, GajimPlugin):
                for field in FIELDS:
                    setattr(module_attr, field, str(getattr(self, field)))
                setattr(module_attr, '__path__', str(self.path))
                return module_attr
        return None


class PluginManager(metaclass=Singleton):
    '''
    Main plug-in management class.

    Currently:
            - scans for plugins
            - activates them
            - handles GUI extension points, when called by GUI objects after
                plugin is activated (by dispatching info about call to handlers
                in plugins)

    :todo: add more info about how GUI extension points work
    :todo: add list of available GUI extension points
    :todo: implement mechanism to dynamically load plugins where GUI extension
               points have been already called (i.e. when plugin is activated
               after GUI object creation). [DONE?]
    :todo: implement mechanism to dynamically deactivate plugins (call plugin's
               deactivation handler) [DONE?]
    :todo: when plug-in is deactivated all GUI extension points are removed
               from `PluginManager.gui_extension_points_handlers`. But when
               object that invoked GUI extension point is abandoned by Gajim,
               eg. closed ChatControl object, the reference to called GUI
               extension points is still in `PluginManager.gui_extension_points`
               These should be removed, so that object can be destroyed by
               Python.
               Possible solution: add call to clean up method in classes
               'destructors' (classes that register GUI extension points)
    '''

    def __init__(self):
        self.plugins = []
        '''
        Detected plugin classes.

        Each class object in list is `GajimPlugin` subclass.

        :type: [] of class objects
        '''
        self.active_plugins = []
        '''
        Instance objects of active plugins.

        These are object instances of classes held `plugins`, but only those
        that were activated.

        :type: [] of `GajimPlugin` based objects
        '''
        self.gui_extension_points = {}
        '''
        Registered GUI extension points.
        '''

        self.gui_extension_points_handlers = {}
        '''
        Registered handlers of GUI extension points.
        '''

        self.encryption_plugins = {}
        '''
        Registered names with instances of encryption Plugins.
        '''

        self.update_plugins()
        self._load_plugins()

    def _plugin_has_entry_in_global_config(self, plugin):
        if app.config.get_per('plugins', plugin.short_name) is None:
            return False
        return True

    def _create_plugin_entry_in_global_config(self, plugin):
        app.config.add_per('plugins', plugin.short_name)

    def _remove_plugin_entry_in_global_config(self, plugin):
        app.config.del_per('plugins', plugin.short_name)

    def update_plugins(self, replace=True, activate=False, plugin_name=None):
        '''
        Move plugins from the downloaded folder to the user plugin folder

        :param replace: replace plugin files if they already exist.
        :type replace: boolean
        :param activate: load and activate the plugin
        :type activate: boolean
        :param plugin_name: if provided, update only this plugin
        :type plugin_name: str
        :return: list of updated plugins (files have been installed)
        :rtype: [] of str
        '''
        updated_plugins = []
        user_dir = configpaths.get('PLUGINS_USER')
        dl_dir = configpaths.get('PLUGINS_DOWNLOAD')
        to_update = [plugin_name] if plugin_name else next(os.walk(dl_dir))[1]
        for directory in to_update:
            src_dir = os.path.join(dl_dir, directory)
            dst_dir = os.path.join(user_dir, directory)
            try:
                if os.path.exists(dst_dir):
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
                plugin = self._load_plugin(Path(dst_dir))
                if plugin is None:
                    log.warning('Error while updating plugin')
                    continue

                self.add_plugin(plugin, activate=True)
        return updated_plugins


    def init_plugins(self):
        self._activate_all_plugins_from_global_config()

    def add_plugin(self, plugin, activate=False):
        plugin_class = plugin.load_module()
        if plugin_class is None:
            return None

        if plugin in self.plugins:
            log.info('Not loading plugin %s v %s. Plugin already loaded.',
                     plugin.short_name, plugin.version)
            return None

        try:
            plugin_obj = plugin_class()
        except Exception:
            log.exception('Error while loading a plugin')
            return None

        if not self._plugin_has_entry_in_global_config(plugin):
            self._create_plugin_entry_in_global_config(plugin)
            if plugin.shipped:
                self._set_plugin_active_in_global_config(plugin)

        self.plugins.append(plugin_obj)
        plugin_obj.active = False

        if activate:
            self.activate_plugin(plugin_obj)

        app.nec.push_incoming_event(
            NetworkEvent('plugin-added', plugin=plugin_obj))

        return plugin_obj

    def remove_plugin(self, plugin):
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

    def get_active_plugin(self, plugin_name):
        for plugin in self.active_plugins:
            if plugin.short_name == plugin_name:
                return plugin
        return None

    def get_plugin(self, short_name):
        for plugin in self.plugins:
            if plugin.short_name == short_name:
                return plugin
        return None

    def extension_point(self, gui_extpoint_name, *args):
        '''
        Invokes all handlers (from plugins) for a particular extension point, but
        doesn't add it to collection for further processing.
        For example if you pass a message for encryption via extension point to a
        plugin, its undesired that the call is stored and replayed on activating the
        plugin. For example after an update.

        :param gui_extpoint_name: name of GUI extension point.
        :type gui_extpoint_name: str
        :param args: parameters to be passed to extension point handlers
                (typically and object that invokes `gui_extension_point`;
                however, this can be practically anything)
        :type args: tuple
        '''

        self._execute_all_handlers_of_gui_extension_point(gui_extpoint_name,
            *args)

    def gui_extension_point(self, gui_extpoint_name, *args):
        '''
        Invokes all handlers (from plugins) for particular GUI extension point
        and adds it to collection for further processing (eg. by plugins not
        active yet).

        :param gui_extpoint_name: name of GUI extension point.
        :type gui_extpoint_name: str
        :param args: parameters to be passed to extension point handlers
                (typically and object that invokes `gui_extension_point`;
                however, this can be practically anything)
        :type args: tuple

        :todo: GUI extension points must be documented well - names with
                parameters that will be passed to handlers (in plugins). Such
                documentation must be obeyed both in core and in plugins. This
                is a loosely coupled approach and is pretty natural in Python.

        :bug: what if only some handlers are successfully connected? we should
                revert all those connections that where successfully made. Maybe
                call 'self._deactivate_plugin()' or sth similar.
                Looking closer - we only rewrite tuples here. Real check should
                be made in method that invokes gui_extpoints handlers.
        '''

        self._add_gui_extension_point_call_to_list(gui_extpoint_name, *args)
        self._execute_all_handlers_of_gui_extension_point(gui_extpoint_name,
            *args)

    def remove_gui_extension_point(self, gui_extpoint_name, *args):
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
        :todo: instead of using argument to identify which extpoint should be
                removed, maybe add additional 'id' argument - this would work
                similar hash in Python objects. 'id' would be calculated based
                on arguments passed or on anything else (even could be constant)
                This would give core developers (that add new extpoints) more
                freedom, but is this necessary?

        :param gui_extpoint_name: name of GUI extension point.
        :type gui_extpoint_name: str
        :param args: arguments that `PluginManager.gui_extension_point` was
                called with for this extension point. This is used (along with
                extension point name) to identify element to be removed.
        :type args: tuple
        '''
        if gui_extpoint_name in self.gui_extension_points:
            extension_points = list(self.gui_extension_points[gui_extpoint_name])
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

    def _add_gui_extension_point_call_to_list(self, gui_extpoint_name, *args):
        '''
        Adds GUI extension point call to list of calls.

        This is done only if such call hasn't been added already
        (same extension point name and same arguments).

        :note: This is assumption that GUI extension points are different only
        if they have different name or different arguments.

        :param gui_extpoint_name: GUI extension point name used to identify it
                by plugins.
        :type gui_extpoint_name: str

        :param args: parameters to be passed to extension point handlers
                (typically and object that invokes `gui_extension_point`;
                however, this can be practically anything)
        :type args: tuple

        '''
        if ((gui_extpoint_name not in self.gui_extension_points)
        or (args not in self.gui_extension_points[gui_extpoint_name])):
            self.gui_extension_points.setdefault(gui_extpoint_name, []).append(
                args)

    def _execute_all_handlers_of_gui_extension_point(self, gui_extpoint_name,
    *args):
        if gui_extpoint_name in self.gui_extension_points_handlers:
            for handlers in self.gui_extension_points_handlers[
            gui_extpoint_name]:
                try:
                    handlers[0](*args)
                except Exception:
                    log.warning('Error executing %s',
                                handlers[0], exc_info=True)

    def _register_events_handlers_in_ged(self, plugin):
        for event_name, handler in plugin.events_handlers.items():
            priority = handler[0]
            handler_function = handler[1]
            app.ged.register_event_handler(event_name, priority,
                handler_function)

    def _remove_events_handler_from_ged(self, plugin):
        for event_name, handler in plugin.events_handlers.items():
            priority = handler[0]
            handler_function = handler[1]
            app.ged.remove_event_handler(event_name, priority,
                handler_function)

    def _register_network_events_in_nec(self, plugin):
        for event_class in plugin.events:
            setattr(event_class, 'plugin', plugin)
            if issubclass(event_class, nec.NetworkIncomingEvent):
                app.nec.register_incoming_event(event_class)
            elif issubclass(event_class, nec.NetworkOutgoingEvent):
                app.nec.register_outgoing_event(event_class)

    def _remove_network_events_from_nec(self, plugin):
        for event_class in plugin.events:
            if issubclass(event_class, nec.NetworkIncomingEvent):
                app.nec.unregister_incoming_event(event_class)
            elif issubclass(event_class, nec.NetworkOutgoingEvent):
                app.nec.unregister_outgoing_event(event_class)

    def _remove_name_from_encryption_plugins(self, plugin):
        if plugin.encryption_name:
            del self.encryption_plugins[plugin.encryption_name]

    def _register_modules_with_handlers(self, plugin):
        if not hasattr(plugin, 'modules'):
            return
        for con in app.connections.values():
            for module in plugin.modules:
                if not module.zeroconf and con.name == 'Local':
                    continue
                instance, name = module.get_instance(con)
                modules.register_single_module(con, instance, name)

                for handler in instance.handlers:
                    con.connection.register_handler(handler)

    def _unregister_modules_with_handlers(self, plugin):
        if not hasattr(plugin, 'modules'):
            return
        for con in app.connections.values():
            for module in plugin.modules:
                instance = con.get_module(module.name)
                modules.unregister_single_module(con, module.name)

                for handler in instance.handlers:
                    con.connection.unregister_handler(handler)

    def activate_plugin(self, plugin):
        '''
        :param plugin: plugin to be activated
        :type plugin: class object of `GajimPlugin` subclass
        '''
        if not plugin.active and plugin.activatable:

            self._add_gui_extension_points_handlers_from_plugin(plugin)
            self._add_encryption_name_from_plugin(plugin)
            self._handle_all_gui_extension_points_with_plugin(plugin)
            self._register_events_handlers_in_ged(plugin)
            self._register_network_events_in_nec(plugin)
            self._register_modules_with_handlers(plugin)

            self.active_plugins.append(plugin)
            try:
                plugin.activate()
            except GajimPluginException as e:
                self.deactivate_plugin(plugin)
                raise GajimPluginActivateException(str(e))
            self._set_plugin_active_in_global_config(plugin)
            plugin.active = True

    def deactivate_plugin(self, plugin):
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
        self._remove_network_events_from_nec(plugin)
        self._remove_name_from_encryption_plugins(plugin)
        self._unregister_modules_with_handlers(plugin)

        # removing plug-in from active plug-ins list
        plugin.deactivate()
        self.active_plugins.remove(plugin)
        self._set_plugin_active_in_global_config(plugin, False)
        plugin.active = False

    def _add_gui_extension_points_handlers_from_plugin(self, plugin):
        for gui_extpoint_name, gui_extpoint_handlers in \
        plugin.gui_extension_points.items():
            self.gui_extension_points_handlers.setdefault(gui_extpoint_name,
                []).append(gui_extpoint_handlers)

    def _add_encryption_name_from_plugin(self, plugin):
        if plugin.encryption_name:
            self.encryption_plugins[plugin.encryption_name] = plugin

    def _handle_all_gui_extension_points_with_plugin(self, plugin):
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

    def _activate_all_plugins_from_global_config(self):
        for plugin in self.plugins:
            if self._plugin_is_active_in_global_config(plugin) and \
            plugin.activatable:
                try:
                    self.activate_plugin(plugin)
                except GajimPluginActivateException:
                    pass

    def register_modules_for_account(self, con):
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
                instance, name = module.get_instance(con)
                if not module.zeroconf and con.name == 'Local':
                    continue
                modules.register_single_module(con, instance, name)

    def _plugin_is_active_in_global_config(self, plugin):
        return app.config.get_per('plugins', plugin.short_name, 'active')

    def _set_plugin_active_in_global_config(self, plugin, active=True):
        app.config.set_per('plugins', plugin.short_name, 'active', active)

    @staticmethod
    def _load_plugin(plugin_path):
        try:
            return Plugin.from_manifest(plugin_path)
        except Exception as error:
            log.warning(error)

    def _load_plugins(self):
        plugins = {}
        for plugin_dir in configpaths.get_plugin_dirs():
            if not plugin_dir.is_dir():
                continue

            for plugin_path in plugin_dir.iterdir():
                plugin = self._load_plugin(plugin_path)
                if plugin is None:
                    continue

                same_plugin = plugins.get(plugin.short_name)
                if same_plugin is not None:
                    if same_plugin.version > plugin.version:
                        continue

                log.info('Found plugin %s %s',
                         plugin.short_name, plugin.version)
                plugins[plugin.short_name] = plugin

        for plugin in plugins.values():
            self.add_plugin(plugin)

    def install_from_zip(self, zip_filename, overwrite=None):
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

        dirs = []
        manifest = None
        for filename in zip_file.namelist():
            if filename.startswith('.') or filename.startswith('/') or \
            ('/' not in filename):
                # members not safe
                raise PluginsystemError(_('Archive is malformed'))
            if filename.endswith('/') and filename.find('/', 0, -1) < 0:
                dirs.append(filename.strip('/'))
            if 'manifest.ini' in filename.split('/')[1]:
                manifest = True
        if not manifest:
            return None
        if len(dirs) > 1:
            raise PluginsystemError(_('Archive is malformed'))

        plugin_name = dirs[0]
        user_dir = Path(configpaths.get('PLUGINS_USER'))
        plugin_path = user_dir / plugin_name

        if plugin_path.exists():
        # Plugin dir already exists
            if not overwrite:
                raise PluginsystemError(_('Plugin already exists'))
            self.uninstall_plugin(self.get_plugin_by_path(str(plugin_path)))

        zip_file.extractall(user_dir)
        zip_file.close()

        plugin = self._load_plugin(plugin_path)
        if plugin is None:
            log.warning('Error while installing from zip')
            rmtree(plugin_path)
            raise PluginsystemError(_('Installation failed'))

        return self.add_plugin(plugin)

    def delete_plugin_files(self, plugin_path):
        def on_error(func, path, error):
            if func == os.path.islink:
            # if symlink
                os.unlink(path)
                return
            # access is denied or other
            raise PluginsystemError(error[1][1])

        rmtree(plugin_path, False, on_error)

    def uninstall_plugin(self, plugin):
        '''
        Deactivate and remove plugin from `plugins` list
        '''
        if not plugin:
            return

        self.remove_plugin(plugin)
        self.delete_plugin_files(plugin.__path__)
        if not is_shipped_plugin(Path(plugin.__path__)):
            path = Path(configpaths.get('PLUGINS_BASE')) / plugin.short_name
            if path.exists():
                self.delete_plugin_files(str(path))
        if self._plugin_has_entry_in_global_config(plugin):
            self._remove_plugin_entry_in_global_config(plugin)

        app.nec.push_incoming_event(
            NetworkEvent('plugin-removed', plugin=plugin))

    def get_plugin_by_path(self, plugin_dir):
        for plugin in self.plugins:
            if plugin.__path__ in plugin_dir:
                return plugin
        return None
