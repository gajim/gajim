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

import logging
import os
import pickle

from gajim.common import configpaths
from gajim.common.events import ApplicationEvent
from gajim.common.ged import HandlerFuncT
from gajim.common.modules.base import BaseModule
from gajim.common.types import PluginExtensionPoints
from gajim.plugins.manifest import PluginManifest

log = logging.getLogger('gajim.p.plugin')


class GajimPlugin:
    '''
    Base class for implementing Gajim plugins.
    '''

    __path__: str = ''

    encryption_name: str = ''
    manifest: PluginManifest

    gui_extension_points: PluginExtensionPoints = {}
    '''
    Extension points that plugin wants to connect with and handlers to be used.

    Keys of this string should be strings with name of GUI extension point
    to handles. Values should be 2-element tuples with references to handling
    functions. First function will be used to connect plugin with extpoint,
    the second one to successfully disconnect from it. Connecting takes places
    when plugin is activated and extpoint already exists, or when plugin is
    already activated but extpoint is being created (eg. chat window opens).
    Disconnecting takes place when plugin is deactivated and extpoint exists
    or when extpoint is destroyed and plugin is activate (eg. chat window
    closed).
    '''
    config_default_values: dict[str, tuple[Any, str]] = {}
    '''
    Default values for keys that should be stored in plug-in config.

    This dict is used when when someone calls for config option but it has not
    been set yet.

    Values are tuples: (default_value, option_description). The first one can
    be anything (this is the advantage of using shelve/pickle instead of
    custom-made     config I/O handling); the second one should be str (gettext
    can be used if need and/or translation is planned).
    '''
    events_handlers: dict[str, tuple[int, HandlerFuncT]] = {}
    '''
    Dictionary with events handlers.

    Keys are event names. Values should be 2-element tuples with handler
    priority as first element and reference to handler function as second
    element. Priority is integer. See `ged` module for predefined priorities
    like `ged.PRECORE`, `ged.CORE` or `ged.POSTCORE`.
    '''
    events: list[ApplicationEvent] = []
    '''
    New network event classes to be registered in Network Events Controller.
    '''
    modules: list[BaseModule] = []

    def __init__(self) -> None:
        self.config = GajimPluginConfig(self)
        self.activatable = True
        self.active = False
        self.available_text = ''
        self.load_config()
        self.config_dialog = None
        self.init()

    def save_config(self) -> None:
        self.config.save()

    def load_config(self) -> None:
        self.config.load()

    def __eq__(self, plugin: Any) -> bool:
        if not isinstance(plugin, GajimPlugin):
            return False
        return self.manifest.short_name == plugin.manifest.short_name

    def __ne__(self, plugin: Any) -> bool:
        return self.manifest.short_name != plugin.manifest.short_name

    def local_file_path(self, file_name: str) -> str:
        return os.path.join(self.__path__, file_name)

    def init(self) -> None:
        pass

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass

    def activate_encryption(self, chat_control: Any) -> None:
        pass


class GajimPluginConfig:
    def __init__(self, plugin: GajimPlugin) -> None:
        self.plugin = plugin
        self.FILE_PATH = (configpaths.get('PLUGINS_CONFIG_DIR') /
                          self.plugin.manifest.short_name)
        self.data: dict[str, Any] = {}

    def __getitem__(self, key: str) -> None:
        if key not in self.data:
            self.data[key] = self.plugin.config_default_values[key][0]
            self.save()

        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def __delitem__(self, key: str) -> None:
        del self.data[key]
        self.save()

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def __iter__(self):
        yield from self.data

    def keys(self):
        return self.data.keys()

    def items(self):
        return self.data.items()

    def save(self) -> None:
        with open(self.FILE_PATH, 'wb') as fd:
            pickle.dump(self.data, fd)

    def load(self) -> None:
        if not self.FILE_PATH.is_file():
            self.data = {}
            self.save()
            return
        with open(self.FILE_PATH, 'rb') as fd:
            try:
                self.data = pickle.load(fd)
            except Exception:
                try:
                    import shelve
                    shelf = shelve.open(str(self.FILE_PATH))
                    for (key, value) in shelf.items():
                        self.data[key] = value
                    if not isinstance(self.data, dict):
                        raise GajimPluginException
                    shelf.close()
                    self.save()
                except Exception:
                    filepath_bak = self.FILE_PATH.with_suffix('bak')
                    log.warning(
                        '%s plugin config file not readable. Saving it as '
                        '%s and creating a new one',
                        self.plugin.manifest.short_name, filepath_bak)
                    if filepath_bak.exists():
                        filepath_bak.unlink()

                    self.FILE_PATH.rename(f'{self.FILE_PATH}.bak')
                    self.data = {}
                    self.save()


class GajimPluginException(Exception):
    pass


class GajimPluginInitError(GajimPluginException):
    pass
