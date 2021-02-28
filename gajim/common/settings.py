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
from typing import Dict
from typing import List
from typing import Union

import sys
import json
import uuid
import logging
import sqlite3
import inspect
import weakref
from pathlib import Path
from collections import namedtuple
from collections import defaultdict

from gi.repository import GLib

from gajim import IS_PORTABLE
from gajim.common import app
from gajim.common import configpaths
from gajim.common import optparser
from gajim.common.helpers import get_muc_context
from gajim.common.storage.base import Encoder
from gajim.common.storage.base import json_decoder
from gajim.common.setting_values import APP_SETTINGS
from gajim.common.setting_values import ACCOUNT_SETTINGS
from gajim.common.setting_values import PROXY_SETTINGS
from gajim.common.setting_values import PROXY_EXAMPLES
from gajim.common.setting_values import INITAL_WORKSPACE
from gajim.common.setting_values import PLUGIN_SETTINGS
from gajim.common.setting_values import WORKSPACE_SETTINGS
from gajim.common.setting_values import DEFAULT_SOUNDEVENT_SETTINGS
from gajim.common.setting_values import STATUS_PRESET_SETTINGS
from gajim.common.setting_values import STATUS_PRESET_EXAMPLES
from gajim.common.setting_values import HAS_APP_DEFAULT
from gajim.common.setting_values import HAS_ACCOUNT_DEFAULT

SETTING_TYPE = Union[bool, int, str, object, list]

log = logging.getLogger('gajim.c.settings')

CREATE_SQL = '''
    CREATE TABLE settings (
            name TEXT UNIQUE,
            settings TEXT
    );

    CREATE TABLE account_settings (
            account TEXT UNIQUE,
            settings TEXT
    );

    INSERT INTO settings(name, settings) VALUES ('app', '{}');
    INSERT INTO settings(name, settings) VALUES ('soundevents', '{}');
    INSERT INTO settings(name, settings) VALUES ('status_presets', '%s');
    INSERT INTO settings(name, settings) VALUES ('proxies', '%s');
    INSERT INTO settings(name, settings) VALUES ('plugins', '{}');
    INSERT INTO settings(name, settings) VALUES ('workspaces', '%s');

    PRAGMA user_version=1;
    ''' % (json.dumps(STATUS_PRESET_EXAMPLES),
           json.dumps(PROXY_EXAMPLES),
           json.dumps(INITAL_WORKSPACE))


class Settings:
    def __init__(self):
        self._con = None
        self._commit_scheduled = None

        self._settings = {}
        self._account_settings = {}

        self._callbacks = defaultdict(list)

    def connect_signal(self, setting, func, account=None, jid=None):
        if not inspect.ismethod(func):
            # static methods are not bound to an object so we can’t easily
            # remove the func once it should not be called anymore
            raise ValueError('Only bound methods can be connected')


        func = weakref.WeakMethod(func)
        self._callbacks[(setting, account, jid)].append(func)

    def disconnect_signals(self, object_):
        for _, handlers in self._callbacks.items():
            for handler in list(handlers):
                if isinstance(handler, tuple):
                    continue
                func = handler()
                if func is None or func.__self__ is object_:
                    handlers.remove(handler)

    def bind_signal(self,
                    setting,
                    widget,
                    func_name,
                    account=None,
                    jid=None,
                    inverted=False,
                    default_text=None):

        callbacks = self._callbacks[(setting, account, jid)]
        func = getattr(widget, func_name)
        callbacks.append((func, inverted, default_text))

        def _on_destroy(*args):
            callbacks.remove((func, inverted, default_text))

        widget.connect('destroy', _on_destroy)

    def _notify(self, value, setting, account=None, jid=None):
        log.info('Signal: %s changed', setting)

        callbacks = self._callbacks[(setting, account, jid)]
        for func in list(callbacks):
            if isinstance(func, tuple):
                func, inverted, default_text = func
                if isinstance(value, bool) and inverted:
                    value = not value

                if value == '' and default_text is not None:
                    value = default_text

                try:
                    func(value)
                except Exception:
                    log.exception('Error while executing signal callback')
                continue

            if func() is None:
                callbacks.remove(func)
                continue

            func = func()
            if func is None:
                continue

            try:
                func(value, setting, account, jid)
            except Exception:
                log.exception('Error while executing signal callback')

    def init(self) -> None:
        self._setup_installation_defaults()
        self._connect_database()
        self._load_settings()
        self._load_account_settings()
        if not self._settings['app']:
            self._migrate_old_config()
            self._commit()
        self._migrate_database()

    @staticmethod
    def _setup_installation_defaults() -> None:
        if IS_PORTABLE:
            APP_SETTINGS['use_keyring'] = False

    @staticmethod
    def _namedtuple_factory(cursor: Any, row: Any) -> Any:
        fields = [col[0] for col in cursor.description]
        return namedtuple("Row", fields)(*row)

    def _connect_database(self) -> None:
        path = configpaths.get('SETTINGS')
        if path.is_dir():
            log.error('%s is a directory but should be a file', path)
            sys.exit()

        if not path.exists():
            self._create_database(CREATE_SQL, path)

        self._con = sqlite3.connect(path)
        self._con.row_factory = self._namedtuple_factory

    @staticmethod
    def _create_database(statement: str, path: Path) -> None:
        log.info('Creating %s', path)
        con = sqlite3.connect(path)

        try:
            con.executescript(statement)
        except Exception:
            log.exception('Error')
            con.close()
            path.unlink()
            sys.exit()

        con.commit()
        con.close()
        path.chmod(0o600)

    def _get_user_version(self) -> int:
        return self._con.execute('PRAGMA user_version').fetchone()[0]

    def _set_user_version(self, version: int) -> None:
        self._con.execute(f'PRAGMA user_version = {version}')
        self._commit()

    def _commit(self, schedule: bool = False) -> None:
        if not schedule:
            if self._commit_scheduled is not None:
                GLib.source_remove(self._commit_scheduled)
                self._commit_scheduled = None
            log.info('Commit')
            self._con.commit()

        elif self._commit_scheduled is None:
            self._commit_scheduled = GLib.timeout_add(
                200, self._scheduled_commit)

    def save(self) -> None:
        self._commit()

    def _scheduled_commit(self) -> None:
        self._commit_scheduled = None
        log.info('Commit')
        self._con.commit()

    def _migrate_database(self) -> None:
        try:
            self._migrate()
        except Exception:
            self._con.close()
            log.exception('Error')
            sys.exit()

    def _migrate(self) -> None:
        version = self._get_user_version()
        if version < 1:
            sql = '''INSERT INTO settings(name, settings)
                     VALUES ('workspaces', ?)'''
            self._con.execute(sql, (json.dumps(INITAL_WORKSPACE),))
            self._set_user_version(2)

    def _migrate_old_config(self) -> None:
        config_file = configpaths.get('CONFIG_FILE')
        if not config_file.exists():
            return

        # Read legacy config
        optparser.OptionsParser(str(configpaths.get('CONFIG_FILE'))).read()

        account_settings = app.config.get_all_per('accounts')
        self._cleanup_account_default_values('account', account_settings)

        contact_settings = app.config.get_all_per('contacts')
        self._cleanup_account_default_values('contact', contact_settings)

        group_chat_settings = app.config.get_all_per('rooms')
        self._cleanup_account_default_values('group_chat',
                                             group_chat_settings)

        for account, settings in account_settings.items():
            self.add_account(account)
            self._account_settings[account]['account'] = settings
            self._account_settings[account]['contact'] = contact_settings
            self._account_settings[account]['group_chat'] = group_chat_settings
            self._commit_account_settings(account)

        self._migrate_encryption_settings()

        # Migrate plugin settings
        self._settings['plugins'] = app.config.get_all_per('plugins')
        self._commit_settings('plugins')

        self._migrate_app_settings()
        self._migrate_soundevent_settings()
        self._migrate_status_preset_settings()
        self._migrate_proxy_settings()

        new_path = config_file.with_name(f'{config_file.name}.old')
        config_file.rename(new_path)
        log.info('Successfully migrated config')

    def _migrate_app_settings(self) -> None:
        app_settings = app.config.get_all()

        # Migrate deprecated settings
        value = app_settings.pop('send_chatstate_muc_default', None)
        if value is not None:
            for account, settings in self._account_settings.items():
                settings['account']['gc_send_chatstate_default'] = value

        value = app_settings.pop('send_chatstate_default', None)
        if value is not None:
            for account, settings in self._account_settings.items():
                settings['account']['send_chatstate_default'] = value

        value = app_settings.pop('print_join_left_default', None)
        if value is not None:
            app_settings['gc_print_join_left_default'] = value

        value = app_settings.pop('print_status_muc_default', None)
        if value is not None:
            app_settings['gc_print_status_default'] = value

        # Cleanup values which are equal to current defaults
        for setting, value in list(app_settings.items()):
            if (setting not in APP_SETTINGS or
                    value == APP_SETTINGS[setting]):
                del app_settings[setting]

        self._settings['app'] = app_settings
        self._commit_settings('app')

        for account in self._account_settings:
            self._commit_account_settings(account)

    def _migrate_encryption_settings(self) -> None:
        # Migrate encryption settings into contact/group chat settings
        encryption_settings = app.config.get_all_per('encryption')
        for key, settings in encryption_settings.items():
            account, jid = self._split_encryption_config_key(key)
            if account is None:
                continue

            encryption = settings.get('encryption')
            if not encryption:
                continue

            if '@' not in jid:
                continue

            # Sad try to determine if the jid is a group chat
            # At this point there is no better way
            domain = jid.split('@')[1]
            subdomain = domain.split('.')[0]
            if subdomain in ('muc', 'conference', 'conf',
                             'rooms', 'room', 'chat'):
                category = 'group_chat'
            else:
                category = 'contact'

            if not jid in self._account_settings[account][category]:
                self._account_settings[account][category][jid] = {
                    'encryption': encryption}
            else:
                self._account_settings[account][category][
                    jid]['encryption'] = encryption
            self._commit_account_settings(account)

    def _split_encryption_config_key(self, key: str) -> Any:
        for account in self._account_settings:
            if not key.startswith(account):
                continue
            jid = key.replace(f'{account}-', '', 1)
            return account, jid
        return None, None

    def _migrate_soundevent_settings(self) -> None:
        soundevent_settings = app.config.get_all_per('soundevents')
        for soundevent, settings in list(soundevent_settings.items()):
            if soundevent not in DEFAULT_SOUNDEVENT_SETTINGS:
                del soundevent_settings[soundevent]
                continue

            for setting, value in list(settings.items()):
                if DEFAULT_SOUNDEVENT_SETTINGS[soundevent][setting] == value:
                    del soundevent_settings[soundevent][setting]
                    if not soundevent_settings[soundevent]:
                        del soundevent_settings[soundevent]

        self._settings['soundevents'] = soundevent_settings
        self._commit_settings('soundevents')

    def _migrate_status_preset_settings(self) -> None:
        status_preset_settings = app.config.get_all_per('statusmsg')
        for preset, settings in list(status_preset_settings.items()):
            if '_last_' in preset:
                del status_preset_settings[preset]
                continue

            for setting, value in list(settings.items()):
                if setting not in STATUS_PRESET_SETTINGS:
                    continue
                if STATUS_PRESET_SETTINGS[setting] == value:
                    del status_preset_settings[preset][setting]
                    if not status_preset_settings[preset]:
                        del status_preset_settings[preset]

        self._settings['status_presets'] = status_preset_settings
        self._commit_settings('status_presets')

    def _migrate_proxy_settings(self) -> None:
        proxy_settings = app.config.get_all_per('proxies')
        for proxy_name, settings in proxy_settings.items():
            for setting, value in list(settings.items()):
                if (setting not in PROXY_SETTINGS or
                        PROXY_SETTINGS[setting] == value):
                    del proxy_settings[proxy_name][setting]

        self._settings['proxies'] = proxy_settings
        self._commit_settings('proxies')

    @staticmethod
    def _cleanup_account_default_values(category: str, settings: Any) -> None:
        for contact, settings_ in list(settings.items()):
            for setting, value in list(settings_.items()):
                if setting not in ACCOUNT_SETTINGS[category]:
                    del settings[contact][setting]
                    if not settings[contact]:
                        del settings[contact]
                    continue

                default = ACCOUNT_SETTINGS[category][setting]
                if default == value:
                    del settings[contact][setting]
                    if not settings[contact]:
                        del settings[contact]
                    continue

    def close(self) -> None:
        log.info('Close settings')
        self._con.commit()
        self._con.close()
        self._con = None

    def _load_settings(self) -> None:
        settings = self._con.execute('SELECT * FROM settings').fetchall()
        for row in settings:
            log.info('Load %s settings', row.name)
            self._settings[row.name] = json.loads(row.settings,
                                                  object_hook=json_decoder)

    def _load_account_settings(self) -> None:
        account_settings = self._con.execute(
            'SELECT * FROM account_settings').fetchall()
        for row in account_settings:
            log.info('Load account settings: %s', row.account)
            self._account_settings[row.account] = json.loads(
                row.settings,
                object_hook=json_decoder)

    def _commit_account_settings(self,
                                 account: str,
                                 schedule: bool = True) -> None:
        log.info('Set account settings: %s', account)
        self._con.execute(
            'UPDATE account_settings SET settings = ? WHERE account = ?',
            (json.dumps(self._account_settings[account], cls=Encoder), account))

        self._commit(schedule=schedule)

    def _commit_settings(self, name: str, schedule: bool = True) -> None:
        log.info('Set settings: %s', name)
        self._con.execute(
            'UPDATE settings SET settings = ? WHERE name = ?',
            (json.dumps(self._settings[name], cls=Encoder), name))

        self._commit(schedule=schedule)

    def get_app_setting(self, setting: str) -> SETTING_TYPE:
        if setting not in APP_SETTINGS:
            raise ValueError(f'Invalid app setting: {setting}')

        try:
            return self._settings['app'][setting]
        except KeyError:
            return APP_SETTINGS[setting]

    get = get_app_setting

    def set_app_setting(self, setting: str, value: SETTING_TYPE) -> None:
        if setting not in APP_SETTINGS:
            raise ValueError(f'Invalid app setting: {setting}')

        default = APP_SETTINGS[setting]
        if not isinstance(value, type(default)) and value is not None:
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        if value is None:
            try:
                del self._settings['app'][setting]
            except KeyError:
                pass

            self._commit_settings('app')
            self._notify(default, setting)
            return

        self._settings['app'][setting] = value

        self._commit_settings('app')
        self._notify(value, setting)

    set = set_app_setting

    def get_plugin_setting(self, plugin: str, setting: str) ->  SETTING_TYPE:
        if setting not in PLUGIN_SETTINGS:
            raise ValueError(f'Invalid plugin setting: {setting}')

        if plugin not in self._settings['plugins']:
            raise ValueError(f'Unknown plugin {plugin}')

        try:
            return self._settings['plugins'][plugin][setting]
        except KeyError:
            return PLUGIN_SETTINGS[setting]

    def get_plugins(self) -> List[str]:
        return list(self._settings['plugins'].keys())

    def set_plugin_setting(self,
                           plugin: str,
                           setting: str,
                           value: bool) -> None:

        if setting not in PLUGIN_SETTINGS:
            raise ValueError(f'Invalid plugin setting: {setting}')

        default = PLUGIN_SETTINGS[setting]
        if not isinstance(value, type(default)):
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        if plugin in self._settings['plugins']:
            self._settings['plugins'][plugin][setting] = value
        else:
            self._settings['plugins'][plugin] = {setting: value}

        self._commit_settings('plugins')

    def remove_plugin(self, plugin: str) -> None:
        try:
            del self._settings['plugins'][plugin]
        except KeyError:
            pass

    def add_account(self, account: str) -> None:
        log.info('Add account: %s', account)
        self._account_settings[account] = {'account': {},
                                           'contact': {},
                                           'group_chat': {}}
        self._con.execute(
            'INSERT INTO account_settings(account, settings) VALUES(?, ?)',
            (account, json.dumps(self._account_settings[account])))
        self._commit()

    def remove_account(self, account: str) -> None:
        if account not in self._account_settings:
            raise ValueError(f'Unknown account: {account}')

        del self._account_settings[account]
        self._con.execute(
            'DELETE FROM account_settings WHERE account = ?',
            (account,))
        self._commit()

    def get_accounts(self) -> List[str]:
        return list(self._account_settings.keys())

    def get_active_accounts(self) -> List[str]:
        active = []
        for account, settings in self._account_settings.items():
            if settings['account']['active'] is True:
                active.append(account)
        return active

    def get_account_setting(self,
                            account: str,
                            setting: str) -> SETTING_TYPE:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['account']:
            raise ValueError(f'Invalid account setting: {setting}')

        try:
            return self._account_settings[account]['account'][setting]
        except KeyError:
            return ACCOUNT_SETTINGS['account'][setting]

    def set_account_setting(self,
                            account: str,
                            setting: str,
                            value: SETTING_TYPE) -> None:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['account']:
            raise ValueError(f'Invalid account setting: {setting}')

        default = ACCOUNT_SETTINGS['account'][setting]
        if not isinstance(value, type(default)) and value is not None:
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        if value is None:
            try:
                del self._account_settings[account]['account'][setting]
            except KeyError:
                pass

            self._commit_account_settings(account)
            self._notify(default, setting, account)
            return

        self._account_settings[account]['account'][setting] = value

        self._commit_account_settings(account)
        self._notify(value, setting, account)

    def get_group_chat_setting(self,
                               account: str,
                               jid: Union[str, JID],
                               setting: str) -> SETTING_TYPE:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['group_chat']:
            raise ValueError(f'Invalid group chat setting: {setting}')

        try:
            return self._account_settings[account]['group_chat'][jid][setting]
        except KeyError:

            context = get_muc_context(jid)
            if context is None:
                # If there is no disco info available
                # to determine the context assume public
                log.warning('Unable to determine context for: %s', jid)
                context = 'public'

            default = ACCOUNT_SETTINGS['group_chat'][setting]
            if default is HAS_APP_DEFAULT:
                context_default_setting = f'gc_{setting}_{context}_default'
                if context_default_setting in APP_SETTINGS:
                    return self.get_app_setting(context_default_setting)
                return self.get_app_setting(f'gc_{setting}_default')

            if default is HAS_ACCOUNT_DEFAULT:
                context_default_setting = f'gc_{setting}_{context}_default'
                if context_default_setting in ACCOUNT_SETTINGS['account']:
                    return self.get_account_setting(account,
                                                    context_default_setting)
                return self.get_account_setting(account,
                                                f'gc_{setting}_default')

            return default

    def set_group_chat_setting(self,
                               account: str,
                               jid: str,
                               setting: str,
                               value: SETTING_TYPE) -> None:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['group_chat']:
            raise ValueError(f'Invalid group chat setting: {setting}')

        default = ACCOUNT_SETTINGS['group_chat'][setting]
        if default in (HAS_APP_DEFAULT, HAS_ACCOUNT_DEFAULT):

            context = get_muc_context(jid)
            if context is None:
                # If there is no disco info available
                # to determine the context assume public
                log.warning('Unable to determine context for: %s', jid)
                context = 'public'

            default_store = APP_SETTINGS
            if default is HAS_ACCOUNT_DEFAULT:
                default_store = ACCOUNT_SETTINGS['account']

            default = default_store.get(f'gc_{setting}_{context}_default',
                                        f'gc_{setting}_default')

        if not isinstance(value, type(default)) and value is not None:
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        if value is None:
            try:
                del self._account_settings[account]['group_chat'][jid][setting]
            except KeyError:
                pass

            self._commit_account_settings(account)
            self._notify(default, setting, account, jid)
            return

        group_chat_settings = self._account_settings[account]['group_chat']
        if jid not in group_chat_settings:
            group_chat_settings[jid] = {setting: value}
        else:
            group_chat_settings[jid][setting] = value

        self._commit_account_settings(account)
        self._notify(value, setting, account, jid)

    def set_group_chat_settings(self,
                                setting: str,
                                value: SETTING_TYPE,
                                context: str = None) -> None:

        for account, acc_settings in self._account_settings.items():
            for jid in acc_settings['group_chat']:
                if context is not None:
                    if get_muc_context(jid) != context:
                        continue
                self.set_group_chat_setting(account, jid, setting, value)

    def get_contact_setting(self,
                            account: str,
                            jid: str,
                            setting: str) -> SETTING_TYPE:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['contact']:
            raise ValueError(f'Invalid contact setting: {setting}')

        try:
            return self._account_settings[account]['contact'][jid][setting]
        except KeyError:
            default = ACCOUNT_SETTINGS['contact'][setting]
            if default is HAS_APP_DEFAULT:
                return self.get_app_setting(f'{setting}_default')

            if default is HAS_ACCOUNT_DEFAULT:
                return self.get_account_setting(account, f'{setting}_default')

            return default

    def set_contact_setting(self,
                            account: str,
                            jid: str,
                            setting: str,
                            value: SETTING_TYPE) -> None:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['contact']:
            raise ValueError(f'Invalid contact setting: {setting}')

        default = ACCOUNT_SETTINGS['contact'][setting]
        if default in (HAS_APP_DEFAULT, HAS_ACCOUNT_DEFAULT):

            default_store = APP_SETTINGS
            if default is HAS_ACCOUNT_DEFAULT:
                default_store = ACCOUNT_SETTINGS['account']

            default = default_store[f'{setting}_default']

        if not isinstance(value, type(default)) and value is not None:
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        if value is None:
            try:
                del self._account_settings[account]['contact'][jid][setting]
            except KeyError:
                pass

            self._commit_account_settings(account)
            self._notify(default, setting, account, jid)
            return

        contact_settings = self._account_settings[account]['contact']
        if jid not in contact_settings:
            contact_settings[jid] = {setting: value}
        else:
            contact_settings[jid][setting] = value

        self._commit_account_settings(account)
        self._notify(value, setting, account, jid)

    def set_contact_settings(self,
                             setting: str,
                             value: SETTING_TYPE) -> None:

        for account, acc_settings in self._account_settings.items():
            for jid in acc_settings['contact']:
                self.set_contact_setting(account, jid, setting, value)

    def set_soundevent_setting(self,
                               event_name: str,
                               setting: str,
                               value: SETTING_TYPE) -> None:

        if event_name not in DEFAULT_SOUNDEVENT_SETTINGS:
            raise ValueError(f'Invalid soundevent: {event_name}')

        if setting not in DEFAULT_SOUNDEVENT_SETTINGS[event_name]:
            raise ValueError(f'Invalid soundevent setting: {setting}')

        default = DEFAULT_SOUNDEVENT_SETTINGS[event_name][setting]
        if not isinstance(value, type(default)):
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        if event_name not in self._settings['soundevents']:
            self._settings['soundevents'][event_name] = {setting: value}
        else:
            self._settings['soundevents'][event_name][setting] = value

        self._commit_settings('soundevents')

    def get_soundevent_settings(self,
                                event_name: str) -> Dict[str, SETTING_TYPE]:
        if event_name not in DEFAULT_SOUNDEVENT_SETTINGS:
            raise ValueError(f'Invalid soundevent: {event_name}')

        settings = DEFAULT_SOUNDEVENT_SETTINGS[event_name].copy()
        user_settings = self._settings['soundevents'].get(event_name, {})
        settings.update(user_settings)
        return settings

    def set_status_preset_setting(self,
                                  status_preset: str,
                                  setting: str,
                                  value: str) -> None:

        if setting not in STATUS_PRESET_SETTINGS:
            raise ValueError(f'Invalid status preset setting: {setting}')

        if not isinstance(value, str):
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        presets = self._settings['status_presets']
        if status_preset not in presets:
            presets[status_preset] = {setting: value}
        else:
            presets[status_preset][setting] = value

        self._commit_settings('status_presets')

    def get_status_preset_settings(self, status_preset: str) -> Dict[str, str]:
        if status_preset not in self._settings['status_presets']:
            raise ValueError(f'Invalid status preset name: {status_preset}')

        settings = STATUS_PRESET_SETTINGS.copy()
        user_settings = self._settings['status_presets'][status_preset]
        settings.update(user_settings)
        return settings

    def get_status_presets(self) -> List[str]:
        return list(self._settings['status_presets'].keys())

    def remove_status_preset(self, status_preset: str) -> None:
        if status_preset not in self._settings['status_presets']:
            raise ValueError(f'Unknown status preset: {status_preset}')

        del self._settings['status_presets'][status_preset]
        self._commit_settings('status_presets')

    def set_proxy_setting(self,
                          proxy_name: str,
                          setting: str,
                          value: SETTING_TYPE) -> None:

        if setting not in PROXY_SETTINGS:
            raise ValueError(f'Invalid proxy setting: {setting}')

        default = PROXY_SETTINGS[setting]
        if not isinstance(value, type(default)):
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        if proxy_name in self._settings['proxies']:
            self._settings['proxies'][proxy_name][setting] = value
        else:
            self._settings['proxies'][proxy_name] = {setting: value}

        self._commit_settings('proxies')

    def get_proxy_settings(self, proxy_name: str) -> Dict[str, SETTING_TYPE]:
        if proxy_name not in self._settings['proxies']:
            raise ValueError(f'Unknown proxy: {proxy_name}')

        settings = PROXY_SETTINGS.copy()
        user_settings = self._settings['proxies'][proxy_name]
        settings.update(user_settings)
        return settings

    def get_proxies(self) -> List[str]:
        return list(self._settings['proxies'].keys())

    def add_proxy(self, proxy_name: str) -> None:
        if proxy_name in self._settings['proxies']:
            raise ValueError(f'Proxy already exists: {proxy_name}')

        self._settings['proxies'][proxy_name] = {}

    def rename_proxy(self, old_proxy_name: str, new_proxy_name: str) -> None:
        settings = self._settings['proxies'].pop(old_proxy_name)
        self._settings['proxies'][new_proxy_name] = settings

    def remove_proxy(self, proxy_name: str) -> None:
        if proxy_name not in self._settings['proxies']:
            raise ValueError(f'Unknown proxy: {proxy_name}')

        del self._settings['proxies'][proxy_name]
        self._commit_settings('proxies')

        if self.get_app_setting('global_proxy') == proxy_name:
            self.set_app_setting('global_proxy', None)

        for account in self._account_settings:
            if self.get_account_setting(account, 'proxy') == proxy_name:
                self.set_account_setting(account, 'proxy', None)

    def set_workspace_setting(self,
                              workspace_id: str,
                              setting: str,
                              value: SETTING_TYPE) -> None:

        if setting not in WORKSPACE_SETTINGS:
            raise ValueError(f'Invalid workspace setting: {setting}')

        if workspace_id not in self._settings['workspaces']:
            raise ValueError(f'Workspace does not exists: {workspace_id}')

        default = WORKSPACE_SETTINGS[setting]
        if not isinstance(value, type(default)):
            raise TypeError(f'Invalid type for {setting}: '
                            f'{value} {type(value)}')

        self._settings['workspaces'][workspace_id][setting] = value
        self._commit_settings('workspaces')

    def get_workspace_setting(self,
                              workspace_id: str,
                              setting: str) -> SETTING_TYPE:

        if setting not in WORKSPACE_SETTINGS:
            raise ValueError(f'Invalid workspace setting: {setting}')

        if workspace_id not in self._settings['workspaces']:
            raise ValueError(f'Workspace does not exists: {workspace_id}')

        try:
            return self._settings['workspaces'][workspace_id][setting]
        except KeyError:
            return WORKSPACE_SETTINGS[setting]

    def get_workspaces(self) -> None:
        workspace_order = app.settings.get_app_setting('workspace_order')

        def sort_workspaces(workspace_id):
            try:
                return workspace_order.index(workspace_id)
            except ValueError:
                # Handle the case that a workflow id is for some reason not
                # in the workspace order list
                return 10000

        workspaces = list(self._settings['workspaces'].keys())
        workspaces.sort(key=sort_workspaces)
        return workspaces

    def add_workspace(self, name: str) -> None:
        id_ = str(uuid.uuid4())
        self._settings['workspaces'][id_] = {
            'name': name,
        }
        self._commit_settings('workspaces')
        return id_

    def remove_workspace(self, id_: str) -> None:
        del self._settings['workspaces'][id_]
        self._commit_settings('workspaces')



class LegacyConfig:

    @staticmethod
    def get(setting: str) -> SETTING_TYPE:
        return app.settings.get_app_setting(setting)

    @staticmethod
    def set(setting: str, value: SETTING_TYPE) -> None:
        app.settings.set_app_setting(setting, value)

    @staticmethod
    def get_per(kind: str, key: str, setting: str) -> SETTING_TYPE:
        if kind == 'accounts':
            return app.settings.get_account_setting(key, setting)

        if kind == 'plugins':
            return app.settings.get_plugin_setting(key, setting)
        raise ValueError

    @staticmethod
    def set_per(kind: str, key: str, setting: str, value: SETTING_TYPE) -> None:
        if kind == 'accounts':
            app.settings.set_account_setting(key, setting, value)
        raise ValueError
