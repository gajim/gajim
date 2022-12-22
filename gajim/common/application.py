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
from typing import TextIO

import os
import sys
import json
import logging
import cProfile
import pstats
from pstats import SortKey
from datetime import datetime
from packaging.version import Version as V

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Soup
from nbxmpp.const import ConnectionType
from nbxmpp.const import ConnectionProtocol

from gajim.common import app
from gajim.common import ged
from gajim.common import configpaths
from gajim.common import logging_helpers
from gajim.common import passwords
from gajim.common.commands import ChatCommands
from gajim.common.dbus import logind
from gajim.common.dbus import file_manager
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountDisconnected
from gajim.common.events import AccountEnabled
from gajim.common.events import AllowGajimUpdateCheck
from gajim.common.events import GajimUpdateAvailable
from gajim.common.events import SignedIn
from gajim.common.client import Client
from gajim.common.helpers import make_http_request
from gajim.common.helpers import get_random_string
from gajim.common.helpers import get_global_show
from gajim.common.helpers import from_one_line
from gajim.common.storage.events import EventStorage
from gajim.common.task_manager import TaskManager
from gajim.common.settings import Settings
from gajim.common.settings import LegacyConfig
from gajim.common.cert_store import CertificateStore
from gajim.common.storage.cache import CacheStorage
from gajim.common.storage.draft import DraftStorage
from gajim.common.storage.archive import MessageArchiveStorage

from gajim.plugins.pluginmanager import PluginManager
from gajim.plugins.repository import PluginRepository


class CoreApplication(ged.EventHelper):
    def __init__(self) -> None:
        ged.EventHelper.__init__(self)
        self._profiling_session = None

    def _init_core(self) -> None:
        # Create and initialize Application Paths & Databases
        app.app = self
        app.print_version()
        app.detect_dependencies()
        configpaths.create_paths()

        passwords.init()

        app.settings = Settings()
        app.settings.init()

        app.config = LegacyConfig()
        app.commands = ChatCommands()

        app.storage.cache = CacheStorage()
        app.storage.cache.init()

        app.storage.events = EventStorage()
        app.storage.events.init()

        app.storage.archive = MessageArchiveStorage()
        app.storage.archive.init()

        app.storage.drafts = DraftStorage()

        app.cert_store = CertificateStore()
        app.task_manager = TaskManager()

        from gajim.common.call_manager import CallManager
        app.call_manager = CallManager()

        from gajim.common.preview import PreviewManager
        app.preview_manager = PreviewManager()

        self._network_monitor = Gio.NetworkMonitor.get_default()
        self._network_monitor.connect('notify::network-available',
                                      self._network_status_changed)
        self._network_state = self._network_monitor.get_network_available()

        if sys.platform in ('win32', 'darwin'):
            GLib.timeout_add_seconds(20, self._check_for_updates)
        else:
            logind.enable()

        file_manager.init()

        for account in app.settings.get_active_accounts():
            app.connections[account] = Client(account)
            app.to_be_removed[account] = []
            app.nicks[account] = app.settings.get_account_setting(account,
                                                                  'name')

        app.plugin_manager = PluginManager()
        app.plugin_manager.init_plugins()
        app.plugin_repository = PluginRepository()

        for client in app.get_clients():
            client.get_module('Roster').load_roster()

        GLib.timeout_add_seconds(5, self._remote_init)

        self.register_events([
            ('signed-in', ged.CORE, self._on_signed_in),
        ])

    @property
    def _log(self) -> logging.Logger:
        return app.log('gajim.application')

    def _core_command_line(self, options: GLib.VariantDict) -> None:
        if options.contains('cprofile'):
            self.start_profiling()

        if options.contains('gdebug'):
            os.environ['G_MESSAGES_DEBUG'] = 'all'

        if options.contains('separate'):
            configpaths.set_separation(True)

        config_path = options.lookup_value('config-path')
        if config_path is not None:
            config_path = config_path.get_string()
            configpaths.set_config_root(config_path)

        configpaths.init()
        logging_helpers.init()

        if options.contains('quiet'):
            logging_helpers.set_quiet()

        if options.contains('verbose'):
            logging_helpers.set_verbose()

        loglevel = options.lookup_value('loglevel')
        if loglevel is not None:
            loglevel = loglevel.get_string()
            logging_helpers.set_loglevels(loglevel)

        if options.contains('warnings'):
            self._show_warnings()

    def _auto_connect(self) -> None:
        for client in app.get_clients():
            account = client.account
            if not app.settings.get_account_setting(account,
                                                    'autoconnect'):
                continue

            status = 'online'
            status_message = ''

            if app.settings.get_account_setting(account, 'restore_last_status'):
                status = app.settings.get_account_setting(
                    account, 'last_status')
                status_message = app.settings.get_account_setting(
                    account, 'last_status_msg')
                status_message = from_one_line(status_message)

            client.change_status(status, status_message)

    def _remote_init(self) -> None:
        if not app.settings.get('remote_control'):
            return

        try:
            from gajim.common.dbus import remote_control
            remote_control.GajimRemote()
        except Exception:
            self._log.exception('Failed to init remote control')

    def start_profiling(self) -> None:
        self._log.info('Start profiling')
        self._profiling_session = cProfile.Profile()
        self._profiling_session.enable()

    def end_profiling(self) -> None:
        if self._profiling_session is None:
            return

        self._profiling_session.disable()
        self._log.info('End profiling')
        ps = pstats.Stats(self._profiling_session)
        ps = ps.sort_stats(SortKey.CUMULATIVE)
        ps.print_stats()

    def start_shutdown(self, *args: Any, **kwargs: Any) -> None:
        app.app.systray.shutdown()

        accounts_to_disconnect: dict[str, Client] = {}

        for client in app.get_clients():
            if client.state.is_available:
                accounts_to_disconnect[client.account] = client

        if not accounts_to_disconnect:
            self._quit_app()
            return

        def _on_disconnect(event: AccountDisconnected) -> None:
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
        app.storage.archive.cleanup_chat_history()
        app.storage.cache.shutdown()
        app.storage.archive.shutdown()
        app.settings.shutdown()
        self.end_profiling()
        logind.shutdown()

    def _quit_app(self) -> None:
        self._shutdown_core()

    @staticmethod
    def _show_warnings() -> None:
        import traceback
        import warnings
        os.environ['GAJIM_LEAK'] = 'true'

        def warn_with_traceback(message: Union[Warning, str],
                                category: type[Warning],
                                filename: str,
                                lineno: int,
                                _file: Optional[TextIO] = None,
                                line: Optional[str] = None) -> None:

            traceback.print_stack(file=sys.stderr)
            sys.stderr.write(warnings.formatwarning(message, category,
                                                    filename, lineno, line))

        warnings.showwarning = warn_with_traceback
        warnings.filterwarnings(action='always')

    def _network_status_changed(self,
                                monitor: Gio.NetworkMonitor,
                                _network_available: bool
                                ) -> None:
        connected = monitor.get_network_available()
        if connected == self._network_state:
            return

        self._network_state = connected
        if connected:
            self._log.info('Network connection available')
        else:
            self._log.info('Network connection lost')
            for client in app.get_clients():
                if (client.state.is_connected or
                        client.state.is_available):
                    client.disconnect(gracefully=False, reconnect=True)

    def _check_for_updates(self) -> None:
        if not app.settings.get('check_for_update'):
            return

        now = datetime.now()
        last_check = app.settings.get('last_update_check')
        if not last_check:
            app.ged.raise_event(AllowGajimUpdateCheck())
            return

        last_check_time = datetime.strptime(last_check, '%Y-%m-%d %H:%M')
        if (now - last_check_time).days < 7:
            return

        self.check_for_gajim_updates()

    def check_for_gajim_updates(self) -> None:
        self._log.info('Checking for Gajim updates')
        make_http_request('https://gajim.org/current-version.json',
                          self._on_update_response)

    def _on_update_response(self,
                            _session: Soup.Session,
                            message: Soup.Message) -> None:

        now = datetime.now()
        app.settings.set('last_update_check', now.strftime('%Y-%m-%d %H:%M'))

        response_body = message.props.response_body
        if response_body is None or not response_body.data:
            self._log.warning('Could not reach gajim.org for update check')
            return

        data = json.loads(response_body.data)
        latest_version = data['current_version']

        if V(latest_version) > V(app.version):
            app.ged.raise_event(GajimUpdateAvailable(version=latest_version))
            return

        self._log.info('Gajim is up to date')

    def create_account(self,
                       account: str,
                       username: str,
                       domain: str,
                       password: str,
                       proxy_name: str,
                       custom_host: tuple[str,
                                          ConnectionProtocol,
                                          ConnectionType],
                       anonymous: bool = False
                       ) -> None:

        account_label = f'{username}@{domain}'
        if anonymous:
            username = 'anon'
            account_label = f'anon@{domain}'

        config: dict[str, Union[str, int, bool]] = {
            'name': username,
            'resource': f'gajim.{get_random_string(8)}',
            'account_label': account_label,
            'hostname': domain,
            'anonymous_auth': anonymous,
        }

        if proxy_name is not None:
            config['proxy'] = proxy_name

        use_custom_host = custom_host is not None
        config['use_custom_host'] = use_custom_host
        if custom_host:
            host, _protocol, type_ = custom_host
            host, port = host.rsplit(':', maxsplit=1)
            config['custom_port'] = int(port)
            config['custom_host'] = host
            config['custom_type'] = type_.value

        app.settings.add_account(account)
        for opt, value in config.items():
            app.settings.set_account_setting(account, opt, value)  # pyright: ignore  # noqa

        # Password module depends on existing config
        passwords.save_password(account, password)

    def enable_account(self, account: str) -> None:
        app.connections[account] = Client(account)

        app.plugin_manager.register_modules_for_account(
            app.connections[account])

        app.to_be_removed[account] = []
        app.nicks[account] = app.settings.get_account_setting(account, 'name')
        app.settings.set_account_setting(account, 'active', True)

        app.ged.raise_event(AccountEnabled(account=account))

        app.get_client(account).change_status('online', '')

    def disable_account(self, account: str) -> None:
        app.settings.set_account_setting(account, 'roster_version', '')
        app.settings.set_account_setting(account, 'active', False)

        # Code in account-disabled handlers may use app.get_client()
        app.ged.raise_event(AccountDisabled(account=account))

        app.get_client(account).cleanup()
        del app.connections[account]
        if account in app.interface.instances:
            del app.interface.instances[account]
        del app.nicks[account]
        del app.to_be_removed[account]

    def remove_account(self, account: str) -> None:
        if app.settings.get_account_setting(account, 'active'):
            self.disable_account(account)

        app.storage.cache.remove_roster(account)
        # Delete password must be before del_per() because it calls set_per()
        # which would recreate the account with defaults values if not found
        passwords.delete_password(account)
        app.settings.remove_account(account)
        app.app.remove_account_actions(account)

    def _on_signed_in(self, event: SignedIn) -> None:
        client = app.get_client(event.account)
        app.storage.archive.insert_jid(client.get_own_jid().bare)

        if client.get_module('MAM').available:
            client.get_module('MAM').request_archive_on_signin()

    def change_status(self,
                      status: str,
                      account: Optional[str] = None
                      ) -> None:

        if status is None:
            status = get_global_show()

        if account is not None:
            self._change_status(account, status)
            return

        for client in app.get_clients():
            if not app.settings.get_account_setting(client.account,
                                                    'sync_with_global_status'):
                continue

            self._change_status(client.account, status)

    @staticmethod
    def _change_status(account: str, status: str) -> None:
        client = app.get_client(account)
        message = client.status_message

        if status == 'offline':
            # TODO delete pep
            # self.delete_pep(app.get_jid_from_account(account), account)
            pass

        client.change_status(status, message)
