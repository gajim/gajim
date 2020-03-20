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
import fnmatch
import zipfile
from shutil import rmtree, move
import configparser
from pkg_resources import parse_version

import gajim
from gajim.common import app
from gajim.common import nec
from gajim.common import configpaths
from gajim.common import modules
from gajim.common.nec import NetworkEvent
from gajim.common.i18n import _
from gajim.common.exceptions import PluginsystemError
from gajim.common.helpers import Singleton
from gajim.plugins import plugins_i18n

from gajim.plugins.helpers import log
from gajim.plugins.helpers import GajimPluginActivateException
from gajim.plugins.gajimplugin import GajimPlugin, GajimPluginException

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

        for path in reversed(configpaths.get_plugin_dirs()):
            pc = self.scan_dir_for_plugins(path)
            self.add_plugins(pc)

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
                log.exception('Upgrade of plugin %s failed. Impossible to move '
                    'files from "%s" to "%s"', directory, src_dir, dst_dir)
                continue
            updated_plugins.append(directory)
            if activate:
                pc = self.scan_dir_for_plugins(dst_dir, scan_dirs=True,
                    package=True)
                if not pc:
                    continue
                self.add_plugin(pc[0])
                plugin = self.plugins[-1]
                self.activate_plugin(plugin)
        return updated_plugins


    def init_plugins(self):
        self._activate_all_plugins_from_global_config()

    def add_plugin(self, plugin_class):
        '''
        :todo: what about adding plug-ins that are already added? Module reload
        and adding class from reloaded module or ignoring adding plug-in?
        '''
        try:
            plugin = plugin_class()
        except Exception:
            log.exception('Error while loading a plugin')
            return

        if plugin not in self.plugins:
            if not self._plugin_has_entry_in_global_config(plugin):
                self._create_plugin_entry_in_global_config(plugin)

            self.plugins.append(plugin)
            plugin.active = False
            app.nec.push_incoming_event(
                NetworkEvent('plugin-added', plugin=plugin))
        else:
            log.info('Not loading plugin %s v%s from module %s '
                     '(identified by short name: %s). Plugin already loaded.',
                     plugin.name, plugin.version,
                     plugin.__module__, plugin.short_name)

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

    def add_plugins(self, plugin_classes):
        for plugin_class in plugin_classes:
            self.add_plugin(plugin_class)

    def get_active_plugin(self, plugin_name):
        for plugin in self.active_plugins:
            if plugin.short_name == plugin_name:
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

                # If handlers have been registered, register the
                # plugin handlers. Otherwise this will be done
                # automatically on connecting
                # in connection_handlers._register_handlers()
                if con.handlers_registered:
                    for handler in instance.handlers:
                        con.connection.register_handler(*handler)

    def _unregister_modules_with_handlers(self, plugin):
        if not hasattr(plugin, 'modules'):
            return
        for con in app.connections.values():
            for module in plugin.modules:
                instance = con.get_module(module.name)
                modules.unregister_single_module(con, module.name)

                # Account is still connected and handlers are registered
                # So just unregister the plugin handlers
                if con.handlers_registered:
                    for handler in instance.handlers:
                        if len(handler) > 4:
                            handler = handler[:4]
                        con.connection.unregister_handler(*handler)

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

    def _deactivate_all_plugins(self):
        for plugin_object in self.active_plugins:
            self.deactivate_plugin(plugin_object)

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


    def _activate_all_plugins(self):
        '''
        Activates all plugins in `plugins`.

        Activated plugins are appended to `active_plugins` list.
        '''
        for plugin in self.plugins:
            try:
                self.activate_plugin(plugin)
            except GajimPluginActivateException:
                pass

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

    def scan_dir_for_plugins(self, path, scan_dirs=True, package=False):
        r'''
        Scans given directory for plugin classes.

        :param path: directory to scan for plugins
        :type path: str

        :param scan_dirs: folders inside path are processed as modules
        :type scan_dirs: boolean

        :param package: if path points to a single package folder
        :type package: boolean

        :return: list of found plugin classes (subclasses of `GajimPlugin`
        :rtype: [] of class objects

        :note: currently it only searches for plugin classes in '\*.py' files
                present in given directory `path` (no recursion here)

        :todo: add scanning zipped modules
        '''
        plugins_found = []
        conf = configparser.ConfigParser()
        fields = ('name', 'short_name', 'version', 'description', 'authors',
            'homepage')
        if not os.path.isdir(path):
            return plugins_found

        if package:
            path, package_name = os.path.split(path)
            dir_list = [package_name]
        else:
            dir_list = os.listdir(path)

        sys.path.insert(0, path)

        for elem_name in dir_list:
            file_path = os.path.join(path, elem_name)

            if os.path.isfile(file_path) and fnmatch.fnmatch(file_path, '*.py'):
                module_name = os.path.splitext(elem_name)[0]
            elif os.path.isdir(file_path) and scan_dirs:
                module_name = elem_name
                file_path += os.path.sep
            else:
                continue

            manifest_path = os.path.join(os.path.dirname(file_path),
                'manifest.ini')
            if scan_dirs and (not os.path.isfile(manifest_path)):
                continue

            # read metadata from manifest.ini
            conf.remove_section('info')
            with open(manifest_path, encoding='utf-8') as conf_file:
                try:
                    conf.read_file(conf_file)
                except configparser.Error:
                    log.warning('Plugin %s not loaded, error loading manifest',
                                elem_name, exc_info=True)
                    continue

            short_name = conf.get('info', 'short_name', fallback=None)
            if short_name is None:
                log.error('No short_name defined for %s', elem_name)

            # Check if the plugin is already loaded
            try:
                for plugin in self.plugins:
                    if plugin.short_name == short_name:
                        raise PluginAlreadyLoaded(
                            'Skip Plugin %s because its '
                            'already loaded' % elem_name)
            except PluginAlreadyLoaded as error:
                log.warning(error)
                continue

            min_v = conf.get('info', 'min_gajim_version', fallback=None)
            max_v = conf.get('info', 'max_gajim_version', fallback=None)

            if min_v is None or max_v is None:
                log.warning('Plugin without min/max version: %s', elem_name)
                continue

            gajim_v = gajim.__version__.split('+', 1)[0]
            gajim_v_cmp = parse_version(gajim_v)

            if min_v and gajim_v_cmp < parse_version(min_v):
                log.warning('Plugin %s not loaded, newer version of'
                            'gajim required: %s < %s',
                            elem_name, gajim_v, min_v)
                continue
            if max_v and gajim_v_cmp > parse_version(max_v):
                log.warning('Plugin %s not loaded, plugin incompatible '
                            'with current version of gajim: '
                            '%s > %s', elem_name, gajim_v, max_v)
                continue

            module = None
            try:
                log.info('Loading %s', module_name)
                module = __import__(module_name)
            except Exception:
                log.warning(
                    'While trying to load %s, exception occurred',
                    elem_name, exc_info=True)
                continue

            if module is None:
                continue

            log.debug('Attributes processing started')
            for module_attr_name in [attr_name for attr_name in dir(module)
            if not (attr_name.startswith('__') or attr_name.endswith('__'))]:
                module_attr = getattr(module, module_attr_name)
                log.debug('%s: %s', module_attr_name, module_attr)

                try:
                    if not issubclass(module_attr, GajimPlugin) or \
                    module_attr is GajimPlugin:
                        continue
                    log.debug('is subclass of GajimPlugin')
                    module_attr.__path__ = os.path.abspath(
                        os.path.dirname(file_path))

                    for option in fields:
                        if conf.get('info', option) == '':
                            raise configparser.NoOptionError(option, 'info')
                        if option == 'description':
                            setattr(module_attr, option, plugins_i18n._(conf.get('info', option)))
                            continue
                        setattr(module_attr, option, conf.get('info', option))

                    plugins_found.append(module_attr)
                except TypeError:
                    pass
                except configparser.NoOptionError:
                    # all fields are required
                    log.debug(
                        '%s: wrong manifest file. all fields are required!',
                        module_attr_name)
                except configparser.NoSectionError:
                    # info section are required
                    log.debug(
                        '%s: wrong manifest file. info section are required!',
                        module_attr_name)
                except configparser.MissingSectionHeaderError:
                    # info section are required
                    log.debug('%s: wrong manifest file. section are required!',
                              module_attr_name)

        sys.path.remove(path)
        return plugins_found

    def install_from_zip(self, zip_filename, owerwrite=None):
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
            return
        if len(dirs) > 1:
            raise PluginsystemError(_('Archive is malformed'))

        user_dir = configpaths.get('PLUGINS_USER')
        plugin_dir = os.path.join(user_dir, dirs[0])

        if os.path.isdir(plugin_dir):
        # Plugin dir already exists
            if not owerwrite:
                raise PluginsystemError(_('Plugin already exists'))
            self.uninstall_plugin(self.get_plugin_by_path(plugin_dir))

        zip_file.extractall(user_dir)
        zip_file.close()

        plugins = self.scan_dir_for_plugins(plugin_dir, package=True)
        if not plugins:
            return
        self.add_plugin(plugins[0])
        plugin = self.plugins[-1]
        return plugin

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
        if self._plugin_has_entry_in_global_config(plugin):
            self._remove_plugin_entry_in_global_config(plugin)

        app.nec.push_incoming_event(
            NetworkEvent('plugin-removed', plugin=plugin))

    def get_plugin_by_path(self, plugin_dir):
        for plugin in self.plugins:
            if plugin.__path__ in plugin_dir:
                return plugin


class PluginAlreadyLoaded(Exception):
    pass
