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

from typing import Any
from typing import Optional
from typing import Union
from typing import Type
from typing import TextIO

import os
import sys

from gi.repository import Gio

from gajim.common import app
from gajim.common import ged
from gajim.common import configpaths
from gajim.common.events import AccountDisonnected
from gajim.common.client import Client
from gajim.common.task_manager import TaskManager
from gajim.common.settings import Settings
from gajim.common.settings import LegacyConfig
from gajim.common.cert_store import CertificateStore
from gajim.common.storage.cache import CacheStorage
from gajim.common.storage.archive import MessageArchiveStorage


class CoreApplication:
    def _init_core(self) -> None:
        # Create and initialize Application Paths & Databases
        app.app = self
        app.print_version()
        app.detect_dependencies()
        configpaths.create_paths()

        app.settings = Settings()
        app.settings.init()

        app.config = LegacyConfig()

        app.storage.cache = CacheStorage()
        app.storage.cache.init()

        app.storage.archive = MessageArchiveStorage()
        app.storage.archive.init()

        app.cert_store = CertificateStore()
        app.task_manager = TaskManager()

        self._network_monitor = Gio.NetworkMonitor.get_default()
        self._network_monitor.connect('notify::network-available',
                                      self._network_status_changed)
        self._network_state = self._network_monitor.get_network_available()

    def start_shutdown(self, *args: Any, **kwargs: Any) -> None:
        accounts_to_disconnect: dict[str, Client] = {}

        for account, client in app.connections.items():
            if app.account_is_available(account):
                accounts_to_disconnect[account] = client

        if not accounts_to_disconnect:
            self._quit_app()
            return

        def _on_disconnect(event: AccountDisonnected) -> None:
            accounts_to_disconnect.pop(event.account)
            if not accounts_to_disconnect:
                self._quit_app()
                return

        app.ged.register_event_handler('account-disconnected',
                                       ged.CORE,
                                       _on_disconnect)

        for client in accounts_to_disconnect.values():
            client.change_status('offline', kwargs.get('message', ''))

    def _shutdown_core(self) -> None:
        # Commit any outstanding SQL transactions
        app.storage.cache.shutdown()
        app.storage.archive.shutdown()

    def _quit_app(self) -> None:
        self._shutdown_core()

    @staticmethod
    def _show_warnings() -> None:
        import traceback
        import warnings
        os.environ['GAJIM_LEAK'] = 'true'

        def warn_with_traceback(message: Union[Warning, str],
                                category: Type[Warning],
                                filename: str,
                                lineno: int,
                                _file: Optional[TextIO] = None,
                                line: Optional[str] = None) -> None:

            traceback.print_stack(file=sys.stderr)
            sys.stderr.write(warnings.formatwarning(message, category,
                                                    filename, lineno, line))

        warnings.showwarning = warn_with_traceback
        warnings.filterwarnings(action="always")

    def _network_status_changed(self,
                                monitor: Gio.NetworkMonitor,
                                _network_available: bool
                                ) -> None:
        connected = monitor.get_network_available()
        if connected == self._network_state:
            return

        self._network_state = connected
        if connected:
            app.log('gajim.application').info('Network connection available')
        else:
            app.log('gajim.application').info('Network connection lost')
            for connection in app.connections.values():
                if (connection.state.is_connected or
                        connection.state.is_available):
                    connection.disconnect(gracefully=False, reconnect=True)
