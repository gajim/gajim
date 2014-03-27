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
from shutil import rmtree
import configparser

from common import gajim
from common import nec
from common.exceptions import PluginsystemError

from plugins.helpers import log, log_calls, Singleton
from plugins.helpers import GajimPluginActivateException
from plugins.plugin import GajimPlugin, GajimPluginException

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
    :todo: implement mechanism to dynamically deactive plugins (call plugin's
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

    __metaclass__ = Singleton

    #@log_calls('PluginManager')
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
        for path in [gajim.PLUGINS_DIRS[1], gajim.PLUGINS_DIRS[0]]:
            pc = PluginManager.scan_dir_for_plugins(path)
            self.add_plugins(pc)
        self._activate_all_plugins_from_global_config()

    @log_calls('PluginManager')
    def _plugin_has_entry_in_global_config(self, plugin):
        if gajim.config.get_per('plugins', plugin.short_name) is None:
            return False
        else:
            return True

    @log_calls('PluginManager')
    def _create_plugin_entry_in_global_config(self, plugin):
        gajim.config.add_per('plugins', plugin.short_name)

    def _remove_plugin_entry_in_global_config(self, plugin):
        gajim.config.del_per('plugins', plugin.short_name)

    @log_calls('PluginManager')
    def add_plugin(self, plugin_class):
        '''
        :todo: what about adding plug-ins that are already added? Module reload
        and adding class from reloaded module or ignoring adding plug-in?
        '''
        plugin = plugin_class()

        if plugin not in self.plugins:
            if not self._plugin_has_entry_in_global_config(plugin):
                self._create_plugin_entry_in_global_config(plugin)

            self.plugins.append(plugin)
            plugin.active = False
        else:
            log.info('Not loading plugin %s v%s from module %s (identified by'
                ' short name: %s). Plugin already loaded.' % (plugin.name,
                plugin.version, plugin.__module__, plugin.short_name))

    @log_calls('PluginManager')
    def add_plugins(self, plugin_classes):
        for plugin_class in plugin_classes:
            self.add_plugin(plugin_class)

    @log_calls('PluginManager')
    def get_active_plugin(self, plugin_name):
        for plugin in self.active_plugins:
            if plugin.short_name == plugin_name:
                return plugin
        return None

    @log_calls('PluginManager')
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

    @log_calls('PluginManager')
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


    @log_calls('PluginManager')
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
            self.gui_extension_points.setdefault(gui_extpoint_name,[]).append(
                args)

    @log_calls('PluginManager')
    def _execute_all_handlers_of_gui_extension_point(self, gui_extpoint_name,
    *args):
        if gui_extpoint_name in self.gui_extension_points_handlers:
            for handlers in self.gui_extension_points_handlers[
            gui_extpoint_name]:
                try:
                    handlers[0](*args)
                except Exception as e:
                    log.warning('Error executing %s', handlers[0],
                        exc_info=True)

    def _register_events_handlers_in_ged(self, plugin):
        for event_name, handler in plugin.events_handlers.items():
            priority = handler[0]
            handler_function = handler[1]
            gajim.ged.register_event_handler(event_name, priority,
                handler_function)

    def _remove_events_handler_from_ged(self, plugin):
        for event_name, handler in plugin.events_handlers.items():
            priority = handler[0]
            handler_function = handler[1]
            gajim.ged.remove_event_handler(event_name, priority,
                handler_function)

    def _register_network_events_in_nec(self, plugin):
        for event_class in plugin.events:
            setattr(event_class, 'plugin', plugin)
            if issubclass(event_class, nec.NetworkIncomingEvent):
                gajim.nec.register_incoming_event(event_class)
            elif issubclass(event_class, nec.NetworkOutgoingEvent):
                gajim.nec.register_outgoing_event(event_class)

    def _remove_network_events_from_nec(self, plugin):
        for event_class in plugin.events:
            if issubclass(event_class, nec.NetworkIncomingEvent):
                gajim.nec.unregister_incoming_event(event_class)
            elif issubclass(event_class, nec.NetworkOutgoingEvent):
                gajim.nec.unregister_outgoing_event(event_class)

    @log_calls('PluginManager')
    def activate_plugin(self, plugin):
        '''
        :param plugin: plugin to be activated
        :type plugin: class object of `GajimPlugin` subclass
        '''
        if not plugin.active and plugin.activatable:

            self._add_gui_extension_points_handlers_from_plugin(plugin)
            self._handle_all_gui_extension_points_with_plugin(plugin)
            self._register_events_handlers_in_ged(plugin)
            self._register_network_events_in_nec(plugin)

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
                        except Exception as e:
                            log.warning('Error executing %s', handler,
                                exc_info=True)

        self._remove_events_handler_from_ged(plugin)
        self._remove_network_events_from_nec(plugin)

        # removing plug-in from active plug-ins list
        plugin.deactivate()
        self.active_plugins.remove(plugin)
        self._set_plugin_active_in_global_config(plugin, False)
        plugin.active = False

    def _deactivate_all_plugins(self):
        for plugin_object in self.active_plugins:
            self.deactivate_plugin(plugin_object)

    @log_calls('PluginManager')
    def _add_gui_extension_points_handlers_from_plugin(self, plugin):
        for gui_extpoint_name, gui_extpoint_handlers in \
        plugin.gui_extension_points.items():
            self.gui_extension_points_handlers.setdefault(gui_extpoint_name,
                []).append(gui_extpoint_handlers)

    @log_calls('PluginManager')
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
                        except Exception as e:
                            log.warning('Error executing %s', handler,
                                exc_info=True)


    @log_calls('PluginManager')
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

    def _plugin_is_active_in_global_config(self, plugin):
        return gajim.config.get_per('plugins', plugin.short_name, 'active')

    def _set_plugin_active_in_global_config(self, plugin, active=True):
        gajim.config.set_per('plugins', plugin.short_name, 'active', active)

    @staticmethod
    @log_calls('PluginManager')
    def scan_dir_for_plugins(path, scan_dirs=True):
        '''
        Scans given directory for plugin classes.

        :param path: directory to scan for plugins
        :type path: str

        :return: list of found plugin classes (subclasses of `GajimPlugin`
        :rtype: [] of class objects

        :note: currently it only searches for plugin classes in '\*.py' files
                present in given direcotory `path` (no recursion here)

        :todo: add scanning packages
        :todo: add scanning zipped modules
        '''
        from plugins.plugins_i18n import _
        plugins_found = []
        conf = configparser.ConfigParser()
        fields = ('name', 'short_name', 'version', 'description', 'authors',
            'homepage')
        if not os.path.isdir(path):
            return plugins_found

        dir_list = os.listdir(path)

        sys.path.insert(0, path)

        for elem_name in dir_list:
            file_path = os.path.join(path, elem_name)

            if os.path.isfile(file_path) and fnmatch.fnmatch(file_path, '*.py'):
                module_name = os.path.splitext(elem_name)[0]
            elif os.path.isdir(file_path) and scan_dirs:
                module_name = elem_name
                file_path += os.path.sep

            manifest_path = os.path.join(os.path.dirname(file_path),
                'manifest.ini')
            if scan_dirs and (not os.path.isfile(manifest_path)):
                continue

            # read metadata from manifest.ini
            conf.remove_section('info')
            conf_file = open(manifest_path)
            conf.read_file(conf_file)
            conf_file.close()

            try:
                min_v = conf.get('info', 'min_gajim_version')
            except Exception:
                min_v = None
            try:
                max_v = conf.get('info', 'max_gajim_version')
            except Exception:
                max_v = None

            gajim_v = gajim.config.get('version')
            gajim_v = gajim_v.split('-', 1)[0]
            gajim_v = gajim_v.split('.')

            if min_v:
                min_v = min_v.split('.')
                if gajim_v < min_v:
                    continue
            if max_v:
                max_v = max_v.split('.')
                if gajim_v > max_v:
                    continue


            module = None

            if module_name in sys.modules:
            # do not load the module twice
                continue
            try:
                module = __import__(module_name)
            except ValueError as value_error:
                log.debug(str(value_error))
            except ImportError as import_error:
                log.debug(str(import_error))

            if module is None:
                continue

            log.debug('Attributes processing started')
            for module_attr_name in [attr_name for attr_name in dir(module)
            if not (attr_name.startswith('__') or attr_name.endswith('__'))]:
                module_attr = getattr(module, module_attr_name)
                log.debug('%s : %s' % (module_attr_name, module_attr))

                try:
                    if not issubclass(module_attr, GajimPlugin) or \
                    module_attr is GajimPlugin:
                        continue
                    log.debug('is subclass of GajimPlugin')
                    module_attr.__path__ = os.path.abspath(
                        os.path.dirname(file_path))

                    for option in fields:
                        if conf.get('info', option) is '':
                            raise configparser.NoOptionError('field empty')
                        if option == 'description':
                            setattr(module_attr, option, _(conf.get('info', option)))
                            continue
                        setattr(module_attr, option, conf.get('info', option))

                    plugins_found.append(module_attr)
                except TypeError:
                    # set plugin localization
                    try:
                        module_attr._ = _
                    except AttributeError:
                        pass
                except configparser.NoOptionError:
                    # all fields are required
                    log.debug('%s : %s' % (module_attr_name,
                        'wrong manifest file. all fields are required!'))
                except configparser.NoSectionError:
                    # info section are required
                    log.debug('%s : %s' % (module_attr_name,
                        'wrong manifest file. info section are required!'))
                except configparser.MissingSectionHeaderError:
                    # info section are required
                    log.debug('%s : %s' % (module_attr_name,
                        'wrong manifest file. section are required!'))

        return plugins_found

    def install_from_zip(self, zip_filename, owerwrite=None):
        '''
        Install plagin from zip and return plugin
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
                dirs.append(filename)
            if 'manifest.ini' in filename.split('/')[1]:
                manifest = True
        if not manifest:
            return
        if len(dirs) > 1:
            raise PluginsystemError(_('Archive is malformed'))

        base_dir, user_dir = gajim.PLUGINS_DIRS
        plugin_dir = os.path.join(user_dir, dirs[0])

        if os.path.isdir(plugin_dir):
        # Plugin dir already exists
            if not owerwrite:
                raise PluginsystemError(_('Plugin already exists'))
            self.remove_plugin(self.get_plugin_by_path(plugin_dir))

        zip_file.extractall(user_dir)
        zip_file.close()
        path = os.path.join(user_dir, dirs[0])
        plugins = self.scan_dir_for_plugins(plugin_dir, False)
        if not plugins:
            return
        self.add_plugin(plugins[0])
        plugin = self.plugins[-1]
        return plugin

    def remove_plugin(self, plugin):
        '''
        Deactivate and remove plugin from `plugins` list
        '''
        def on_error(func, path, error):
            if func == os.path.islink:
            # if symlink
                os.unlink(path)
                return
            # access is denied or other
            raise PluginsystemError(error[1][1])

        if plugin:
            if plugin.active:
                self.deactivate_plugin(plugin)
            rmtree(plugin.__path__, False, on_error)
            self.plugins.remove(plugin)
            if self._plugin_has_entry_in_global_config(plugin):
                self._remove_plugin_entry_in_global_config(plugin)
            del sys.modules[plugin.__module__.split('.')[0]]
            del plugin.__module__.split('.')[-1]
            del plugin

    def get_plugin_by_path(self, plugin_dir):
        for plugin in self.plugins:
            if plugin.__path__ in plugin_dir:
                return plugin
