# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast
from typing import Literal
from typing import NamedTuple
from typing import overload
from typing import TypedDict

import inspect
import json
import logging
import sqlite3
import sys
import uuid
import weakref
from collections import defaultdict
from collections import namedtuple
from collections.abc import Callable
from pathlib import Path

from gi.repository import GLib
from nbxmpp.protocol import JID

from gajim import IS_PORTABLE
from gajim.common import app
from gajim.common import configpaths
from gajim.common import optparser
from gajim.common.setting_values import ACCOUNT_SETTINGS
from gajim.common.setting_values import AllContactSettings
from gajim.common.setting_values import AllContactSettingsT
from gajim.common.setting_values import AllGroupChatSettings
from gajim.common.setting_values import AllGroupChatSettingsT
from gajim.common.setting_values import AllSettingsT
from gajim.common.setting_values import AllWorkspaceSettings
from gajim.common.setting_values import AllWorkspaceSettingsT
from gajim.common.setting_values import APP_SETTINGS
from gajim.common.setting_values import BoolAccountSettings
from gajim.common.setting_values import BoolContactSettings
from gajim.common.setting_values import BoolGroupChatSettings
from gajim.common.setting_values import BoolSettings
from gajim.common.setting_values import DEFAULT_SOUNDEVENT_SETTINGS
from gajim.common.setting_values import FloatSettings
from gajim.common.setting_values import HAS_ACCOUNT_DEFAULT
from gajim.common.setting_values import HAS_APP_DEFAULT
from gajim.common.setting_values import INITAL_WORKSPACE
from gajim.common.setting_values import IntAccountSettings
from gajim.common.setting_values import IntGroupChatSettings
from gajim.common.setting_values import IntSettings
from gajim.common.setting_values import OpenChatsSettingT
from gajim.common.setting_values import PLUGIN_SETTINGS
from gajim.common.setting_values import PROXY_EXAMPLES
from gajim.common.setting_values import PROXY_SETTINGS
from gajim.common.setting_values import STATUS_PRESET_EXAMPLES
from gajim.common.setting_values import STATUS_PRESET_SETTINGS
from gajim.common.setting_values import StringAccountSettings
from gajim.common.setting_values import StringContactSettings
from gajim.common.setting_values import StringGroupChatSettings
from gajim.common.setting_values import StringSettings
from gajim.common.setting_values import StringWorkspaceSettings
from gajim.common.setting_values import WORKSPACE_SETTINGS
from gajim.common.setting_values import WorkspaceSettings
from gajim.common.storage.base import Encoder
from gajim.common.storage.base import json_decoder

SETTING_TYPE = bool | int | str | object


log = logging.getLogger('gajim.c.settings')

CURRENT_USER_VERSION = 5

CREATE_SQL = '''
    CREATE TABLE settings (
            name TEXT UNIQUE,
            settings TEXT
    );

    CREATE TABLE account_settings (
            account TEXT UNIQUE,
            settings TEXT
    );

    INSERT INTO settings(name, settings) VALUES ('app', '{{}}');
    INSERT INTO settings(name, settings) VALUES ('soundevents', '{{}}');
    INSERT INTO settings(name, settings) VALUES ('status_presets', '{status}');
    INSERT INTO settings(name, settings) VALUES ('proxies', '{proxies}');
    INSERT INTO settings(name, settings) VALUES ('plugins', '{{}}');
    INSERT INTO settings(name, settings) VALUES ('workspaces', '{workspaces}');

    PRAGMA user_version={version};
    '''.format(status=json.dumps(STATUS_PRESET_EXAMPLES),  # noqa: UP032
               proxies=json.dumps(PROXY_EXAMPLES),
               workspaces=json.dumps(INITAL_WORKSPACE),
               version=CURRENT_USER_VERSION)


_SignalCallable = Callable[[Any, str, str | None, JID | None], Any]
_CallbackDict = dict[tuple[str, str | None, JID | None],
                     list[weakref.WeakMethod[_SignalCallable]]]

if app.is_flatpak():
    app_overrides = '/app/app-overrides.json'
else:
    app_overrides = '/etc/gajim/app-overrides.json'
OVERRIDES_PATH = Path(app_overrides)


class SettingsDictT(TypedDict):
    app: dict[str, Any]
    plugins: dict[str, dict[str, Any]]
    workspaces: dict[str, dict[str, WorkspaceSettings]]
    soundevents: dict[str, dict[str, Any]]
    status_presets: dict[str, dict[str, str]]
    proxies: dict[str, dict[str, Any]]


class Settings:
    def __init__(self, in_memory: bool = False):
        self._con = cast(sqlite3.Connection, None)
        self._commit_scheduled = None
        self._in_memory = in_memory

        self._settings: SettingsDictT = {}
        self._app_overrides: dict[str, AllSettingsT] = {}
        self._account_settings: dict[
            str, Any | dict[str, dict[JID | str, Any]]] = {}

        self._callbacks: _CallbackDict = defaultdict(list)

    def connect_signal(self,
                       setting: str,
                       func: _SignalCallable,
                       account: str | None = None,
                       jid: JID | None = None) -> None:
        if not inspect.ismethod(func):
            # static methods are not bound to an object so we can’t easily
            # remove the func once it should not be called anymore
            raise ValueError('Only bound methods can be connected')

        weak_func = weakref.WeakMethod(func)
        self._callbacks[(setting, account, jid)].append(weak_func)

    def disconnect_signals(self, object_: object) -> Any:
        for handlers in self._callbacks.values():
            for handler in list(handlers):
                if isinstance(handler, tuple):
                    continue
                func = handler()
                if func is None or func.__self__ is object_:
                    handlers.remove(handler)

    def bind_signal(self,
                    setting: str,
                    widget: Any,
                    func_name: str,
                    account: str | None = None,
                    jid: JID | None = None,
                    inverted: bool = False,
                    default_text: str | None = None
                    ) -> None:

        callbacks = self._callbacks[(setting, account, jid)]
        func = getattr(widget, func_name)
        callbacks.append((func, inverted, default_text))

        def _on_destroy(*args: Any) -> None:
            callbacks.remove((func, inverted, default_text))

        widget.connect('destroy', _on_destroy)

    def _notify(self,
                value: Any,
                setting: str,
                account: str | None = None,
                jid: JID | None = None) -> None:

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
        if self._in_memory:
            self._connect_in_memory_database()
        else:
            self._connect_database()
        self._load_settings()
        self._load_account_settings()
        if not self._settings['app']:
            # ['app'] is empty in a newly created database.
            # If there is an old config, it gets migrated at this point.
            self._migrate_old_config()
            self._commit()
        self._migrate_database()
        self._load_app_overrides()
        self._commit()

    @staticmethod
    def _setup_installation_defaults() -> None:
        if IS_PORTABLE:
            APP_SETTINGS['use_keyring'] = False

        if sys.platform == 'win32':
            APP_SETTINGS['app_font_size'] = 1.125

    def _load_app_overrides(self) -> None:
        if not OVERRIDES_PATH.exists():
            return

        with OVERRIDES_PATH.open(encoding='utf8') as f:
            try:
                self._app_overrides = json.load(f)
            except Exception:
                log.exception('Failed to load overrides')
                return

        self._settings['app'].update(self._app_overrides)

    @staticmethod
    def _namedtuple_factory(cursor: sqlite3.Cursor,
                            row: tuple[Any, ...]) -> NamedTuple:
        fields = [col[0] for col in cursor.description]
        return namedtuple('Row', fields)(*row)  # pyright: ignore

    def _connect_database(self) -> None:
        path = configpaths.get('SETTINGS')
        if path.is_dir():
            log.error('%s is a directory but should be a file', path)
            sys.exit()

        if not path.exists():
            self._create_database(CREATE_SQL, path)

        self._con = sqlite3.connect(path)
        self._con.row_factory = self._namedtuple_factory

    def _connect_in_memory_database(self) -> None:
        log.info('Creating in memory')
        self._con = sqlite3.connect(':memory:')
        self._con.row_factory = self._namedtuple_factory

        try:
            self._con.executescript(CREATE_SQL)
        except Exception:
            log.exception('Error')
            self._con.close()
            sys.exit()

        self._con.commit()

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
        if self._in_memory:
            return

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
            self._settings['workspaces'] = INITAL_WORKSPACE
            self._set_user_version(1)

        if version < 2:
            # Migrate open chats to new key and format
            for workspace in self._settings['workspaces'].values():
                open_chats: list[dict[str, Any]] = []
                for open_chat in workspace.get('open_chats', []):
                    account, jid, type_, pinned = open_chat
                    open_chats.append({'account': account,
                                       'jid': jid,
                                       'type': type_,
                                       'pinned': pinned,
                                       'position': -1})

                workspace['chats'] = open_chats
                workspace.pop('open_chats', None)

            self._set_user_version(2)

        if version < 3:
            # Migrate open chats to new key and format
            for account_settings in self._account_settings.values():
                if account_settings['account'].get('active') is None:
                    account_settings['account']['active'] = True

            self._set_user_version(3)

        if version < 4:
            value = self._settings['app'].get('chat_timestamp_format')
            if value is not None:
                self._settings['app']['time_format'] = value

            value = self._settings['app'].get('date_timestamp_format')
            if value is not None:
                self._settings['app']['date_format'] = value

            self._set_user_version(4)

        if version < 5:
            self._settings['app'].pop('muclumbus_api_http_uri', None)
            self._set_user_version(5)

    def _migrate_old_config(self) -> None:
        if self._in_memory:
            return

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
            if account == 'Local':
                # Zeroconf support was dropped so don’t migrate the account
                continue
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
            for settings in self._account_settings.values():
                settings['account']['gc_send_chatstate_default'] = value

        value = app_settings.pop('send_chatstate_default', None)
        if value is not None:
            for settings in self._account_settings.values():
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

            assert jid is not None
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

            if jid not in self._account_settings[account][category]:
                self._account_settings[account][category][jid] = {
                    'encryption': encryption}
            else:
                self._account_settings[account][category][
                    jid]['encryption'] = encryption
            self._commit_account_settings(account)

    def _split_encryption_config_key(self, key: str) -> tuple[str | None,
                                                              str | None]:
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
        self._con = cast(sqlite3.Connection, None)

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

    def has_app_override(self, setting: str) -> bool:
        return setting in self._app_overrides

    @overload
    def get_app_setting(self, setting: BoolSettings) -> bool:
        ...

    @overload
    def get_app_setting(self, setting: StringSettings) -> str:
        ...

    @overload
    def get_app_setting(self, setting: IntSettings) -> int:
        ...

    @overload
    def get_app_setting(self, setting: FloatSettings) -> float:
        ...

    def get_app_setting(self, setting: str) -> AllSettingsT:
        if setting not in APP_SETTINGS:
            raise ValueError(f'Invalid app setting: {setting}')

        try:
            return self._settings['app'][setting]
        except KeyError:
            return APP_SETTINGS[setting]

    get = get_app_setting

    @overload
    def set_app_setting(self,
                        setting: BoolSettings,
                        value: bool | None) -> None:
        ...

    @overload
    def set_app_setting(self,
                        setting: StringSettings,
                        value: str | None) -> None:
        ...

    @overload
    def set_app_setting(self,
                        setting: IntSettings,
                        value: int | None) -> None:
        ...

    @overload
    def set_app_setting(self,
                        setting: FloatSettings,
                        value: float | None) -> None:
        ...

    @overload
    def set_app_setting(self,
                        setting: Literal['workspace_order'],
                        value: list[str]) -> None:
        ...

    def set_app_setting(self,
                        setting: str,
                        value: AllSettingsT | None) -> None:

        if setting not in APP_SETTINGS:
            raise ValueError(f'Invalid app setting: {setting}')

        if setting in self._app_overrides:
            log.warning('Changing %s is not allowed because there exists an '
                        'override', setting)
            return

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

    def get_plugin_setting(self, plugin: str, setting: str) -> SETTING_TYPE:
        if setting not in PLUGIN_SETTINGS:
            raise ValueError(f'Invalid plugin setting: {setting}')

        if plugin not in self._settings['plugins']:
            raise ValueError(f'Unknown plugin {plugin}')

        try:
            return self._settings['plugins'][plugin][setting]
        except KeyError:
            return PLUGIN_SETTINGS[setting]

    def get_plugins(self) -> list[str]:
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
        if account in self._account_settings:
            raise ValueError('Account %s exists already' % account)

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

    def get_accounts(self) -> list[str]:
        return list(self._account_settings.keys())

    def account_exists(self, jid: str) -> bool:
        for account in self._account_settings:
            name = self.get_account_setting(account, 'name')
            hostname = self.get_account_setting(account, 'hostname')
            if jid == f'{name}@{hostname}':
                return True
        return False

    def get_active_accounts(self) -> list[str]:
        active: list[str] = []
        for account in self._account_settings:
            if self.get_account_setting(account, 'active'):
                active.append(account)
        return active

    def get_account_from_jid(self, jid: JID) -> str:
        for account in self._account_settings:
            name = self.get_account_setting(account, 'name')
            hostname = self.get_account_setting(account, 'hostname')
            if jid.localpart == name and jid.domain == hostname:
                return account
        raise ValueError(f'No account found for: {jid}')

    @overload
    def get_account_setting(self,
                            account: str,
                            setting: StringAccountSettings) -> str:
        ...

    @overload
    def get_account_setting(self,
                            account: str,
                            setting: IntAccountSettings) -> int:
        ...

    @overload
    def get_account_setting(self,
                            account: str,
                            setting: BoolAccountSettings) -> bool:
        ...

    def get_account_setting(self,
                            account: str,
                            setting: str) -> AllSettingsT:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['account']:
            raise ValueError(f'Invalid account setting: {setting}')

        try:
            return self._account_settings[account]['account'][setting]
        except KeyError:
            return ACCOUNT_SETTINGS['account'][setting]

    @overload
    def set_account_setting(self,
                            account: str,
                            setting: StringAccountSettings,
                            value: str | None) -> None:
        ...

    @overload
    def set_account_setting(self,
                            account: str,
                            setting: IntAccountSettings,
                            value: int | None) -> None:
        ...

    @overload
    def set_account_setting(self,
                            account: str,
                            setting: BoolAccountSettings,
                            value: bool | None) -> None:
        ...

    def set_account_setting(self,
                            account: str,
                            setting: str,
                            value: AllSettingsT | None) -> None:

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

    @overload
    def get_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: IntGroupChatSettings
                               ) -> int:
        ...

    @overload
    def get_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: BoolGroupChatSettings
                               ) -> bool:
        ...

    @overload
    def get_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: StringGroupChatSettings
                               ) -> str:
        ...

    def get_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: AllGroupChatSettings
                               ) -> AllGroupChatSettingsT:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['group_chat']:
            raise ValueError(f'Invalid group chat setting: {setting}')

        try:
            return self._account_settings[account]['group_chat'][jid][setting]
        except KeyError:

            client = app.get_client(account)
            contact = client.get_module('Contacts').get_contact(jid)
            context = contact.muc_context
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
                default_settings = [
                    f'gc_{setting}_{context}_default',
                    f'gc_{setting}_default',
                    f'{setting}_default',
                ]

                for default_setting in default_settings:
                    if default_setting in ACCOUNT_SETTINGS['account']:
                        return self.get_account_setting(
                            account, default_setting)

                raise ValueError(f'No default setting found for {setting}')

            return default

    @overload
    def set_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: StringGroupChatSettings,
                               value: str | None) -> None:
        ...

    @overload
    def set_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: IntGroupChatSettings,
                               value: int | None) -> None:
        ...

    @overload
    def set_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: BoolGroupChatSettings,
                               value: bool | None) -> None:
        ...

    def set_group_chat_setting(self,
                               account: str,
                               jid: JID,
                               setting: AllGroupChatSettings,
                               value: AllGroupChatSettingsT | None) -> None:

        if account not in self._account_settings:
            raise ValueError(f'Account missing: {account}')

        if setting not in ACCOUNT_SETTINGS['group_chat']:
            raise ValueError(f'Invalid group chat setting: {setting}')

        default = ACCOUNT_SETTINGS['group_chat'][setting]
        if default in (HAS_APP_DEFAULT, HAS_ACCOUNT_DEFAULT):
            context = 'public'
            if app.account_is_connected(account):
                client = app.get_client(account)
                contact = client.get_module('Contacts').get_contact(jid)
                context = contact.muc_context
                if context is None:
                    # If there is no disco info available
                    # to determine the context assume public
                    log.warning('Unable to determine context for: %s', jid)
                    context = 'public'

            default_store = APP_SETTINGS
            if default is HAS_ACCOUNT_DEFAULT:
                default_store = ACCOUNT_SETTINGS['account']

            default_settings = [
                f'gc_{setting}_{context}_default',
                f'gc_{setting}_default',
                f'{setting}_default',
            ]

            default = None
            for default_setting in default_settings:
                if default_setting in default_store:
                    default = default_store.get(default_setting)
                    break

            if default is None:
                raise ValueError(f'No default setting found for {setting}')

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
            group_chat_settings[str(jid)] = {setting: value}
        else:
            group_chat_settings[jid][setting] = value

        self._commit_account_settings(account)
        self._notify(value, setting, account, jid)

    def set_group_chat_settings(self,
                                setting: str,
                                value: SETTING_TYPE,
                                context: str | None = None
                                ) -> None:

        for account, acc_settings in self._account_settings.items():
            for jid in acc_settings['group_chat']:
                if context is not None:
                    client = app.get_client(account)
                    contact = client.get_module('Contacts').get_contact(jid)
                    if contact.muc_context != context:
                        continue
                self.set_group_chat_setting(account, jid, setting, value)

    @overload
    def get_contact_setting(self,
                            account: str,
                            jid: JID,
                            setting: BoolContactSettings
                            ) -> bool:
        ...

    @overload
    def get_contact_setting(self,
                            account: str,
                            jid: JID,
                            setting: StringContactSettings
                            ) -> str:
        ...

    def get_contact_setting(self,
                            account: str,
                            jid: JID,
                            setting: AllContactSettings
                            ) -> AllContactSettingsT:

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

    @overload
    def set_contact_setting(self,
                            account: str,
                            jid: JID,
                            setting: StringContactSettings,
                            value: str | None) -> None:
        ...

    @overload
    def set_contact_setting(self,
                            account: str,
                            jid: JID,
                            setting: BoolContactSettings,
                            value: bool | None) -> None:
        ...

    def set_contact_setting(self,
                            account: str,
                            jid: JID,
                            setting: AllContactSettings,
                            value: AllContactSettingsT | None) -> None:

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
            contact_settings[str(jid)] = {setting: value}
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
                                event_name: str
                                ) -> dict[str, SETTING_TYPE]:

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

    def get_status_preset_settings(self, status_preset: str) -> dict[str, str]:
        if status_preset not in self._settings['status_presets']:
            raise ValueError(f'Invalid status preset name: {status_preset}')

        settings = STATUS_PRESET_SETTINGS.copy()
        user_settings = self._settings['status_presets'][status_preset]
        settings.update(user_settings)
        return settings

    def get_status_presets(self) -> list[str]:
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

    def get_proxy_settings(self, proxy_name: str) -> dict[str, SETTING_TYPE]:
        if proxy_name not in self._settings['proxies']:
            raise ValueError(f'Unknown proxy: {proxy_name}')

        settings = PROXY_SETTINGS.copy()
        user_settings = self._settings['proxies'][proxy_name]
        settings.update(user_settings)
        return settings

    def get_proxies(self) -> list[str]:
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

    @overload
    def set_workspace_setting(self,
                              workspace_id: str,
                              setting: StringWorkspaceSettings,
                              value: str) -> None:
        ...

    @overload
    def set_workspace_setting(self,
                              workspace_id: str,
                              setting: Literal['chats'],
                              value: OpenChatsSettingT
                              ) -> None:
        ...

    def set_workspace_setting(self,
                              workspace_id: str,
                              setting: AllWorkspaceSettings,
                              value: AllWorkspaceSettingsT) -> None:

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

    @overload
    def get_workspace_setting(self,
                              workspace_id: str,
                              setting: Literal['chats']
                              ) -> OpenChatsSettingT:
        ...

    @overload
    def get_workspace_setting(self,
                              workspace_id: str,
                              setting: StringWorkspaceSettings) -> str:
        ...

    def get_workspace_setting(self,
                              workspace_id: str,
                              setting: AllWorkspaceSettings
                              ) -> AllWorkspaceSettingsT:

        if setting not in WORKSPACE_SETTINGS:
            raise ValueError(f'Invalid workspace setting: {setting}')

        if workspace_id not in self._settings['workspaces']:
            raise ValueError(f'Workspace does not exists: {workspace_id}')

        try:
            return self._settings['workspaces'][workspace_id][setting]
        except KeyError:
            return WORKSPACE_SETTINGS[setting]

    def get_workspace_count(self) -> int:
        return len(self._settings['workspaces'].keys())

    def get_workspaces(self) -> list[str]:
        workspace_order = app.settings.get_app_setting('workspace_order')

        def sort_workspaces(workspace_id: str) -> int:
            try:
                return workspace_order.index(workspace_id)
            except ValueError:
                # Handle the case that a workspace id is for some reason not
                # in the workspace order list
                return 10000

        workspaces = list(self._settings['workspaces'].keys())
        workspaces.sort(key=sort_workspaces)
        return workspaces

    def add_workspace(self, name: str) -> str:
        id_ = str(uuid.uuid4())
        self._settings['workspaces'][id_] = {
            'name': name,
        }
        self._commit_settings('workspaces')
        return id_

    def remove_workspace(self, id_: str) -> None:
        del self._settings['workspaces'][id_]
        self._commit_settings('workspaces')

    def shutdown(self) -> None:
        if self._commit_scheduled is not None:
            GLib.source_remove(self._commit_scheduled)
            self._commit_scheduled = None

        self._commit()
        self._con.close()
        del self._con


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
