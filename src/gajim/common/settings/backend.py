# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
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
from gajim.common.helpers import deep_update
from gajim.common.settings.schema import DEFAULT_SOUNDEVENT_SETTINGS
from gajim.common.settings.schema import INITIAL_WORKSPACE
from gajim.common.settings.schema import PROXY_EXAMPLES
from gajim.common.settings.schema import SettingSchema
from gajim.common.settings.schema import SettingT
from gajim.common.settings.schema import SettingType
from gajim.common.settings.schema import WorkspaceSettings
from gajim.common.settings.types import AccountBoolSettings
from gajim.common.settings.types import AccountIntSettings
from gajim.common.settings.types import AccountStringSettings
from gajim.common.settings.types import AppBoolSettings
from gajim.common.settings.types import AppFloatSettings
from gajim.common.settings.types import AppIntSettings
from gajim.common.settings.types import AppStringSettings
from gajim.common.settings.types import ContactBoolSettings
from gajim.common.settings.types import ContactStringSettings
from gajim.common.settings.types import GroupChatBoolSettings
from gajim.common.settings.types import GroupChatIntSettings
from gajim.common.settings.types import GroupChatStringSettings
from gajim.common.settings.types import OpenChatSettingDetails
from gajim.common.settings.types import WorkspaceStringSettings
from gajim.common.storage.base import Encoder
from gajim.common.storage.base import json_decoder
from gajim.common.util.classes import SettingsAction

SETTING_TYPE = bool | int | str | object


log = logging.getLogger("gajim.c.settings")

CURRENT_USER_VERSION = 7

CREATE_SQL = """
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
    INSERT INTO settings(name, settings) VALUES ('proxies', '{proxies}');
    INSERT INTO settings(name, settings) VALUES ('plugins', '{{}}');
    INSERT INTO settings(name, settings) VALUES ('workspaces', '{workspaces}');
    INSERT INTO settings(name, settings) VALUES ('window_sizes', '{{}}');

    PRAGMA user_version={version};
    """.format(  # noqa: UP032
    proxies=json.dumps(PROXY_EXAMPLES),
    workspaces=json.dumps(INITIAL_WORKSPACE),
    version=CURRENT_USER_VERSION,
)


_SignalCallable = Callable[[Any, str, str | None, JID | None], Any]
_CallbackDict = dict[
    tuple[str, str | None, JID | None], list[weakref.WeakMethod[_SignalCallable]]
]

if app.is_flatpak():
    app_overrides = "/app/app-overrides.json"
else:
    app_overrides = "/etc/gajim/app-overrides.json"
OVERRIDES_PATH = Path(app_overrides)


class SettingsDictT(TypedDict):
    app: dict[str, Any]
    plugins: dict[str, dict[str, Any]]
    workspaces: dict[str, dict[str, WorkspaceSettings]]
    soundevents: dict[str, dict[str, Any]]
    proxies: dict[str, dict[str, Any]]
    window_sizes: dict[str, tuple[int, int]]


class Settings:
    def __init__(self, *, in_memory: bool = False, schema: SettingSchema | None = None):
        self._con = cast(sqlite3.Connection, None)
        self._commit_scheduled = None
        self._in_memory = in_memory

        if schema is None:
            schema = SettingSchema.get_default()

        self._schema = schema
        self._settings: SettingsDictT = {}
        self._app_overrides: dict[str, Any] = {}
        self._account_settings: dict[str, Any | dict[str, dict[JID | str, Any]]] = {}

        self._callbacks: _CallbackDict = defaultdict(list)

    def connect_signal(
        self,
        setting: str,
        func: _SignalCallable,
        account: str | None = None,
        jid: JID | None = None,
    ) -> None:
        if not inspect.ismethod(func):
            # static methods are not bound to an object so we can’t easily
            # remove the func once it should not be called anymore
            raise ValueError("Only bound methods can be connected")

        weak_func = weakref.WeakMethod(func)
        self._callbacks[(setting, account, jid)].append(weak_func)

    def disconnect_signals(self, object_: object) -> Any:
        for handlers in self._callbacks.values():
            for handler in list(handlers):
                if isinstance(handler, tuple):
                    widget = handler[1]
                    if widget is object_:
                        handlers.remove(handler)
                else:
                    func = handler()
                    if func is None or func.__self__ is object_:
                        handlers.remove(handler)

    def create_action(self, setting: AppBoolSettings) -> SettingsAction:
        # Currently only boolean app settings are supported
        value = self.get_app_setting(setting)
        action = SettingsAction(
            name=setting.replace("_", "-"),
            parameter_type=GLib.VariantType("b"),
            state=GLib.Variant("b", value),
        )

        self.bind_signal(setting, action, "change_state")
        return action

    def bind_signal(
        self,
        setting: str,
        widget: Any,
        func_name: str,
        account: str | None = None,
        jid: JID | None = None,
        inverted: bool = False,
        default_text: str | None = None,
    ) -> None:

        callbacks = self._callbacks[(setting, account, jid)]
        func = getattr(widget, func_name)
        callbacks.append((func, widget, inverted, default_text))

    def _notify(
        self,
        value: Any,
        setting: str,
        account: str | None = None,
        jid: JID | None = None,
    ) -> None:

        log.info("Signal: %s changed", setting)

        callbacks = self._callbacks[(setting, account, jid)]
        for func in list(callbacks):
            if isinstance(func, tuple):
                func, _widget, inverted, default_text = func
                if isinstance(value, bool) and inverted:
                    value = not value

                if value == "" and default_text is not None:
                    value = default_text

                try:
                    func(value)
                except Exception:
                    log.exception("Error while executing signal callback")
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
                log.exception("Error while executing signal callback")

    def init(self, init_config_path: Path | None = None) -> None:
        self._setup_installation_defaults()
        if self._in_memory:
            self._connect_in_memory_database()
        else:
            self._connect_database()
        self._load_settings()
        self._load_account_settings()
        self._migrate_database()
        self._load_settings_from_path(init_config_path)
        self._load_app_overrides()
        self._commit()

    def _setup_installation_defaults(self) -> None:
        if IS_PORTABLE:
            setting = self._schema.get_setting(SettingType.APP, "use_keyring")
            assert setting is not None
            setting.default = False

        if sys.platform == "win32":
            setting = self._schema.get_setting(SettingType.APP, "app_font_size")
            assert setting is not None
            setting.default = 1.125

    def _load_settings_from_path(self, path: Path | None) -> None:
        if path is None:
            return

        log.info("Load settings from path: %s", path)

        try:
            settings = json.loads(path.read_bytes(), object_hook=json_decoder)
        except Exception as error:
            sys.exit(f"Unable to load settings from path: {error}")

        for cat in self._settings:
            self._settings[cat] = deep_update(
                self._settings[cat], settings.get(cat, {})
            )

        account_settings = settings.get("accounts", {})
        for account in account_settings:
            if account not in self._account_settings:
                self.add_account(account)

        self._account_settings = deep_update(
            self._account_settings, settings.get("accounts", {})
        )

        self._commit_all()

    def _load_app_overrides(self) -> None:
        if not OVERRIDES_PATH.exists():
            return

        with OVERRIDES_PATH.open(encoding="utf8") as f:
            try:
                self._app_overrides = json.load(f)
            except Exception:
                log.exception("Failed to load overrides")
                return

        self._settings["app"].update(self._app_overrides)

    def export_to_json(self, path: Path) -> None:
        config = self._settings.copy()
        config["accounts"] = self._account_settings
        json_string = json.dumps(config, cls=Encoder, indent=2)
        path.write_text(json_string)

    @staticmethod
    def _namedtuple_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> NamedTuple:
        fields = [col[0] for col in cursor.description]
        return namedtuple("Row", fields)(*row)  # type: ignore

    def _connect_database(self) -> None:
        path = configpaths.get("SETTINGS")
        if path.is_dir():
            log.error("%s is a directory but should be a file", path)
            sys.exit()

        if not path.exists():
            self._create_database(CREATE_SQL, path)

        self._con = sqlite3.connect(path)
        self._con.row_factory = self._namedtuple_factory

    def _connect_in_memory_database(self) -> None:
        log.info("Creating in memory")
        self._con = sqlite3.connect(":memory:")
        self._con.row_factory = self._namedtuple_factory

        try:
            self._con.executescript(CREATE_SQL)
        except Exception:
            log.exception("Error")
            self._con.close()
            sys.exit()

        self._con.commit()

    @staticmethod
    def _create_database(statement: str, path: Path) -> None:
        log.info("Creating %s", path)
        con = sqlite3.connect(path)

        try:
            con.executescript(statement)
        except Exception:
            log.exception("Error")
            con.close()
            path.unlink()
            sys.exit()

        con.commit()
        con.close()
        path.chmod(0o600)

    def _get_user_version(self) -> int:
        return self._con.execute("PRAGMA user_version").fetchone()[0]

    def _set_user_version(self, version: int) -> None:
        self._con.execute(f"PRAGMA user_version = {version}")
        self._commit()

    def _commit(self, schedule: bool = False) -> None:
        if not schedule:
            if self._commit_scheduled is not None:
                GLib.source_remove(self._commit_scheduled)
                self._commit_scheduled = None
            log.info("Commit")
            self._con.commit()

        elif self._commit_scheduled is None:
            self._commit_scheduled = GLib.timeout_add(200, self._scheduled_commit)

    def _commit_all(self) -> None:
        for account in self._account_settings:
            self._commit_account_settings(account)

        for key in self._settings:
            self._commit_settings(key)

    def save(self) -> None:
        self._commit()

    def _scheduled_commit(self) -> None:
        self._commit_scheduled = None
        log.info("Commit")
        self._con.commit()

    def _migrate_database(self) -> None:
        if self._in_memory:
            return

        try:
            self._migrate()
        except Exception:
            self._con.close()
            log.exception("Error")
            sys.exit()

    def _migrate(self) -> None:
        version = self._get_user_version()
        if version < 1:
            sql = """INSERT INTO settings(name, settings)
                     VALUES ('workspaces', ?)"""
            self._con.execute(sql, (json.dumps(INITIAL_WORKSPACE),))
            self._settings["workspaces"] = INITIAL_WORKSPACE
            self._commit_settings("workspaces")
            self._set_user_version(1)

        if version < 2:
            # Migrate open chats to new key and format
            for workspace in self._settings["workspaces"].values():
                open_chats: list[dict[str, Any]] = []
                for open_chat in workspace.get("open_chats", []):
                    account, jid, type_, pinned = open_chat
                    open_chats.append(
                        {
                            "account": account,
                            "jid": jid,
                            "type": type_,
                            "pinned": pinned,
                            "position": -1,
                        }
                    )

                workspace["chats"] = open_chats
                workspace.pop("open_chats", None)

            self._commit_settings("workspaces")
            self._set_user_version(2)

        if version < 3:
            # Migrate open chats to new key and format
            for account_settings in self._account_settings.values():
                if account_settings["account"].get("active") is None:
                    account_settings["account"]["active"] = True

            for account in self._account_settings:
                self._commit_account_settings(account)

            self._set_user_version(3)

        if version < 4:
            value = self._settings["app"].get("chat_timestamp_format")
            if value is not None:
                self._settings["app"]["time_format"] = value

            value = self._settings["app"].get("date_timestamp_format")
            if value is not None:
                self._settings["app"]["date_format"] = value

            self._commit_settings("app")
            self._set_user_version(4)

        if version < 5:
            self._settings["app"].pop("muclumbus_api_http_uri", None)
            self._commit_settings("app")
            self._set_user_version(5)

        if version < 6:
            for account_settings in self._account_settings.values():
                settings = account_settings["account"]
                localpart = settings.get("name", "")
                domain = settings.get("hostname", "")
                try:
                    address = JID.from_string(f"{localpart}@{domain}")
                except Exception as error:
                    log.warning("Unable to migrate address: %s", error)
                    address = JID.from_string("unknown@unknown.invalid")

                settings["address"] = str(address)

            for account in self._account_settings:
                self._commit_account_settings(account)

            self._set_user_version(6)

        if version < 7:
            sql = """INSERT INTO settings(name, settings)
                     VALUES ('window_sizes', '{}')"""
            self._con.execute(sql)
            self._settings["window_sizes"] = {}
            self._set_user_version(7)

    def close(self) -> None:
        log.info("Close settings")
        self._con.commit()
        self._con.close()
        self._con = cast(sqlite3.Connection, None)

    def _load_settings(self) -> None:
        settings = self._con.execute("SELECT * FROM settings").fetchall()
        for row in settings:
            log.info("Load %s settings", row.name)
            self._settings[row.name] = json.loads(
                row.settings, object_hook=json_decoder
            )

    def _load_account_settings(self) -> None:
        account_settings = self._con.execute(
            "SELECT * FROM account_settings"
        ).fetchall()
        for row in account_settings:
            log.info("Load account settings: %s", row.account)
            self._account_settings[row.account] = json.loads(
                row.settings, object_hook=json_decoder
            )

    def _commit_account_settings(self, account: str, schedule: bool = True) -> None:
        log.info("Set account settings: %s", account)
        self._con.execute(
            "UPDATE account_settings SET settings = ? WHERE account = ?",
            (json.dumps(self._account_settings[account], cls=Encoder), account),
        )

        self._commit(schedule=schedule)

    def _commit_settings(self, name: str, schedule: bool = True) -> None:
        log.info("Set settings: %s", name)
        self._con.execute(
            "UPDATE settings SET settings = ? WHERE name = ?",
            (json.dumps(self._settings[name], cls=Encoder), name),
        )

        self._commit(schedule=schedule)

    def has_app_override(self, setting: str) -> bool:
        return setting in self._app_overrides

    @overload
    def get_app_setting(self, key: AppBoolSettings) -> bool: ...

    @overload
    def get_app_setting(self, key: AppStringSettings) -> str: ...

    @overload
    def get_app_setting(self, key: AppIntSettings) -> int: ...

    @overload
    def get_app_setting(self, key: AppFloatSettings) -> float: ...

    def get_app_setting(self, key: str) -> Any:
        setting = self._schema.get_setting(SettingType.APP, key)
        if setting is None:
            raise ValueError(f"Invalid app setting: {key}")

        try:
            return self._settings["app"][key]
        except KeyError:
            return setting.default

    get = get_app_setting

    @overload
    def set_app_setting(self, key: AppBoolSettings, value: bool | None) -> None: ...

    @overload
    def set_app_setting(self, key: AppStringSettings, value: str | None) -> None: ...

    @overload
    def set_app_setting(self, key: AppIntSettings, value: int | None) -> None: ...

    @overload
    def set_app_setting(self, key: AppFloatSettings, value: float | None) -> None: ...

    @overload
    def set_app_setting(
        self, key: Literal["workspace_order"], value: list[str]
    ) -> None: ...

    def set_app_setting(self, key: str, value: Any | None) -> None:
        setting = self._schema.get_setting(SettingType.APP, key)
        if setting is None:
            raise ValueError(f"Invalid app setting: {key}")

        if key in self._app_overrides:
            log.warning(
                "Changing %s is not allowed because there exists an override", key
            )
            return

        if value is None:
            try:
                del self._settings["app"][key]
            except KeyError:
                pass

            self._commit_settings("app")
            self._notify(setting.default, key)
            return

        self._settings["app"][key] = setting.validate_value(value)

        self._commit_settings("app")
        self._notify(value, key)

    set = set_app_setting

    def set_window_size(self, window_name: str, width: int, height: int) -> None:
        self._settings["window_sizes"][window_name] = (width, height)
        self._commit_settings("window_sizes")

    def get_window_size(self, window_name: str) -> tuple[int, int] | None:
        return self._settings["window_sizes"].get(window_name)

    def get_plugin_setting(self, plugin: str, key: str) -> SETTING_TYPE:
        setting = self._schema.get_setting(SettingType.PLUGIN, key)
        if setting is None:
            raise ValueError(f"Invalid plugin setting: {key}")

        if plugin not in self._settings["plugins"]:
            raise ValueError(f"Unknown plugin {plugin}")

        try:
            return self._settings["plugins"][plugin][key]
        except KeyError:
            return setting.default

    def get_plugins(self) -> list[str]:
        return list(self._settings["plugins"].keys())

    def set_plugin_setting(self, plugin: str, key: str, value: bool) -> None:
        setting = self._schema.get_setting(SettingType.PLUGIN, key)
        if setting is None:
            raise ValueError(f"Invalid plugin setting: {key}")

        if plugin in self._settings["plugins"]:
            self._settings["plugins"][plugin][key] = setting.validate_value(value)
        else:
            self._settings["plugins"][plugin] = {key: value}

        self._commit_settings("plugins")

    def remove_plugin(self, plugin: str) -> None:
        try:
            del self._settings["plugins"][plugin]
        except KeyError:
            pass

    def add_account(self, account: str) -> None:
        log.info("Add account: %s", account)
        if account in self._account_settings:
            raise ValueError("Account %s exists already" % account)

        self._account_settings[account] = {
            "account": {},
            "contact": {},
            "group_chat": {},
        }
        self._con.execute(
            "INSERT INTO account_settings(account, settings) VALUES(?, ?)",
            (account, json.dumps(self._account_settings[account])),
        )
        self._commit()

    def remove_account(self, account: str) -> None:
        if account not in self._account_settings:
            raise ValueError(f"Unknown account: {account}")

        del self._account_settings[account]
        self._con.execute("DELETE FROM account_settings WHERE account = ?", (account,))
        self._commit()

    def get_accounts(self) -> list[str]:
        return list(self._account_settings.keys())

    def account_exists(self, jid: str) -> bool:
        for account in self._account_settings:
            address = self.get_account_setting(account, "address")
            if jid == JID.from_string(address):
                return True
        return False

    def get_active_accounts(self) -> list[str]:
        active: list[str] = []
        for account in self._account_settings:
            if self.get_account_setting(account, "active"):
                active.append(account)
        return active

    def get_account_from_jid(self, jid: JID) -> str:
        for account in self._account_settings:
            address = self.get_account_setting(account, "address")
            if jid == JID.from_string(address):
                return account

        raise ValueError(f"No account found for: {jid}")

    @overload
    def get_account_setting(self, account: str, key: AccountStringSettings) -> str: ...
    @overload
    def get_account_setting(self, account: str, key: AccountIntSettings) -> int: ...
    @overload
    def get_account_setting(self, account: str, key: AccountBoolSettings) -> bool: ...
    def get_account_setting(self, account: str, key: str) -> Any:
        setting = self._schema.get_setting(SettingType.ACCOUNT, key)
        if setting is None:
            raise ValueError(f"Invalid account setting: {key}")

        if account not in self._account_settings:
            raise ValueError(f"Account missing: {account}")

        try:
            return self._account_settings[account]["account"][key]
        except KeyError:
            return setting.default

    @overload
    def set_account_setting(
        self, account: str, key: AccountStringSettings, value: str | None
    ) -> None: ...

    @overload
    def set_account_setting(
        self, account: str, key: AccountIntSettings, value: int | None
    ) -> None: ...

    @overload
    def set_account_setting(
        self, account: str, key: AccountBoolSettings, value: bool | None
    ) -> None: ...

    def set_account_setting(self, account: str, key: str, value: Any | None) -> None:
        setting = self._schema.get_setting(SettingType.ACCOUNT, key)
        if setting is None:
            raise ValueError(f"Invalid account setting: {key}")

        if account not in self._account_settings:
            raise ValueError(f"Account missing: {account}")

        if value is None:
            try:
                del self._account_settings[account]["account"][key]
            except KeyError:
                pass

            self._commit_account_settings(account)
            self._notify(setting.default, key, account)
            return

        self._account_settings[account]["account"][key] = setting.validate_value(value)

        self._commit_account_settings(account)
        self._notify(value, key, account)

    def _get_default(self, setting: SettingT, account: str, context: str | None) -> Any:
        if not setting.context_default:
            return setting.default

        default_keys: list[tuple[SettingType, str]] = []

        if setting.type == SettingType.GROUPCHAT:
            if context is None:
                # If there is no disco info available
                # to determine the context assume public
                log.warning("Unable to determine context for: %s")
                context = "public"

            default_keys += [
                (SettingType.ACCOUNT, f"gc_{setting.key}_{context}_default"),
                (SettingType.APP, f"gc_{setting.key}_{context}_default"),
                (SettingType.ACCOUNT, f"gc_{setting.key}_default"),
                (SettingType.APP, f"gc_{setting.key}_default"),
            ]

        default_keys += [
            (SettingType.ACCOUNT, f"{setting.key}_default"),
            (SettingType.APP, f"{setting.key}_default"),
        ]

        for setting_type, default_key in default_keys:
            if self._schema.get_setting(setting_type, default_key) is None:
                continue

            if setting_type == SettingType.ACCOUNT:
                return self.get_account_setting(account, default_key)
            else:
                return self.get_app_setting(default_key)

        raise ValueError(f"No default setting found for {setting.key}")

    @overload
    def get_group_chat_setting(
        self, account: str, jid: JID, key: GroupChatIntSettings, context: str | None
    ) -> int: ...

    @overload
    def get_group_chat_setting(
        self, account: str, jid: JID, key: GroupChatBoolSettings, context: str | None
    ) -> bool: ...

    @overload
    def get_group_chat_setting(
        self, account: str, jid: JID, key: GroupChatStringSettings, context: str | None
    ) -> str: ...

    def get_group_chat_setting(
        self, account: str, jid: JID, key: str, context: str | None
    ) -> Any:
        setting = self._schema.get_setting(SettingType.GROUPCHAT, key)
        if setting is None:
            raise ValueError(f"Invalid group chat setting: {key}")

        if account not in self._account_settings:
            raise ValueError(f"Account missing: {account}")

        try:
            return self._account_settings[account]["group_chat"][jid][key]
        except KeyError:
            return self._get_default(setting, account, context)

    @overload
    def set_group_chat_setting(
        self,
        account: str,
        jid: JID,
        key: GroupChatStringSettings,
        context: str | None,
        value: str | None,
    ) -> None: ...

    @overload
    def set_group_chat_setting(
        self,
        account: str,
        jid: JID,
        key: GroupChatIntSettings,
        context: str | None,
        value: int | None,
    ) -> None: ...

    @overload
    def set_group_chat_setting(
        self,
        account: str,
        jid: JID,
        key: GroupChatBoolSettings,
        context: str | None,
        value: bool | None,
    ) -> None: ...

    def set_group_chat_setting(
        self, account: str, jid: JID, key: str, context: str | None, value: Any | None
    ) -> None:
        setting = self._schema.get_setting(SettingType.GROUPCHAT, key)
        if setting is None:
            raise ValueError(f"Invalid group chat setting: {key}")

        if account not in self._account_settings:
            raise ValueError(f"Account missing: {account}")

        if value is None:
            try:
                del self._account_settings[account]["group_chat"][jid][key]
            except KeyError:
                pass

            default = self._get_default(setting, account, context)

            self._commit_account_settings(account)
            self._notify(default, key, account, jid)
            return

        setting.validate_value(value)
        group_chat_settings = self._account_settings[account]["group_chat"]
        if jid not in group_chat_settings:
            group_chat_settings[str(jid)] = {key: value}
        else:
            group_chat_settings[jid][key] = value

        self._commit_account_settings(account)
        self._notify(value, key, account, jid)

    def set_group_chat_settings(
        self,
        account: str | None,
        key: str,
        value: SETTING_TYPE,
        context_match_func: Callable[[str, JID], Literal["public", "private"] | None],
    ) -> None:

        if account is None:
            settings = self._account_settings.items()
        else:
            settings = [(account, self._account_settings[account])]

        for acc, acc_settings in settings:
            for jid in acc_settings["group_chat"]:
                context = context_match_func(acc, jid)
                if context is None:
                    continue
                self.set_group_chat_setting(acc, jid, key, context, value)

    @overload
    def get_contact_setting(
        self, account: str, jid: JID, key: ContactBoolSettings
    ) -> bool: ...

    @overload
    def get_contact_setting(
        self, account: str, jid: JID, key: ContactStringSettings
    ) -> str: ...
    def get_contact_setting(self, account: str, jid: JID, key: str) -> Any:

        setting = self._schema.get_setting(SettingType.CONTACT, key)
        if setting is None:
            raise ValueError(f"Invalid contact setting: {key}")

        if account not in self._account_settings:
            raise ValueError(f"Account missing: {account}")

        try:
            return self._account_settings[account]["contact"][jid][key]
        except KeyError:
            return self._get_default(setting, account, None)

    @overload
    def set_contact_setting(
        self, account: str, jid: JID, key: ContactStringSettings, value: str | None
    ) -> None: ...

    @overload
    def set_contact_setting(
        self, account: str, jid: JID, key: ContactBoolSettings, value: bool | None
    ) -> None: ...

    def set_contact_setting(
        self, account: str, jid: JID, key: str, value: Any | None
    ) -> None:
        setting = self._schema.get_setting(SettingType.CONTACT, key)
        if setting is None:
            raise ValueError(f"Invalid contact setting: {key}")

        if account not in self._account_settings:
            raise ValueError(f"Account missing: {account}")

        if value is None:
            try:
                del self._account_settings[account]["contact"][jid][key]
            except KeyError:
                pass

            default = self._get_default(setting, account, None)
            self._commit_account_settings(account)
            self._notify(default, key, account, jid)
            return

        setting.validate_value(value)
        contact_settings = self._account_settings[account]["contact"]
        if jid not in contact_settings:
            contact_settings[str(jid)] = {key: value}
        else:
            contact_settings[jid][key] = value

        self._commit_account_settings(account)
        self._notify(value, key, account, jid)

    def set_contact_settings(
        self, account: str | None, setting: str, value: SETTING_TYPE
    ) -> None:

        if account is None:
            settings = self._account_settings.items()
        else:
            settings = [(account, self._account_settings[account])]

        for acc, acc_settings in settings:
            for jid in acc_settings["contact"]:
                self.set_contact_setting(acc, jid, setting, value)

    def set_soundevent_setting(
        self, event_name: str, setting: str, value: SETTING_TYPE
    ) -> None:

        if event_name not in DEFAULT_SOUNDEVENT_SETTINGS:
            raise ValueError(f"Invalid soundevent: {event_name}")

        if setting not in DEFAULT_SOUNDEVENT_SETTINGS[event_name]:
            raise ValueError(f"Invalid soundevent setting: {setting}")

        default = DEFAULT_SOUNDEVENT_SETTINGS[event_name][setting]
        if not isinstance(value, type(default)):
            raise TypeError(f"Invalid type for {setting}: {value} {type(value)}")

        if event_name not in self._settings["soundevents"]:
            self._settings["soundevents"][event_name] = {setting: value}
        else:
            self._settings["soundevents"][event_name][setting] = value

        self._commit_settings("soundevents")

    def get_soundevent_settings(self, event_name: str) -> dict[str, SETTING_TYPE]:
        if event_name not in DEFAULT_SOUNDEVENT_SETTINGS:
            raise ValueError(f"Invalid soundevent: {event_name}")

        settings = DEFAULT_SOUNDEVENT_SETTINGS[event_name].copy()
        user_settings = self._settings["soundevents"].get(event_name, {})
        settings.update(user_settings)
        return settings

    def set_proxy_setting(self, proxy_name: str, key: str, value: SETTING_TYPE) -> None:
        setting = self._schema.get_setting(SettingType.PROXY, key)
        if setting is None:
            raise ValueError(f"Invalid proxy setting: {key}")

        setting.validate_value(value)
        if proxy_name in self._settings["proxies"]:
            self._settings["proxies"][proxy_name][key] = value
        else:
            self._settings["proxies"][proxy_name] = {key: value}

        self._commit_settings("proxies")

    def get_proxy_settings(self, proxy_name: str) -> dict[str, SETTING_TYPE]:
        if proxy_name not in self._settings["proxies"]:
            raise ValueError(f"Unknown proxy: {proxy_name}")

        settings = self._schema.get_type_default_settings(SettingType.PROXY)
        user_settings = self._settings["proxies"][proxy_name]
        settings.update(user_settings)
        return settings

    def get_proxies(self) -> list[str]:
        return list(self._settings["proxies"].keys())

    def add_proxy(self, proxy_name: str) -> None:
        if proxy_name in self._settings["proxies"]:
            raise ValueError(f"Proxy already exists: {proxy_name}")

        self._settings["proxies"][proxy_name] = {}

    def rename_proxy(self, old_proxy_name: str, new_proxy_name: str) -> None:
        settings = self._settings["proxies"].pop(old_proxy_name)
        self._settings["proxies"][new_proxy_name] = settings

    def remove_proxy(self, proxy_name: str) -> None:
        if proxy_name not in self._settings["proxies"]:
            raise ValueError(f"Unknown proxy: {proxy_name}")

        del self._settings["proxies"][proxy_name]
        self._commit_settings("proxies")

        if self.get_app_setting("global_proxy") == proxy_name:
            self.set_app_setting("global_proxy", None)

        for account in self._account_settings:
            if self.get_account_setting(account, "proxy") == proxy_name:
                self.set_account_setting(account, "proxy", None)

    @overload
    def set_workspace_setting(
        self, workspace_id: str, key: WorkspaceStringSettings, value: str
    ) -> None: ...

    @overload
    def set_workspace_setting(
        self,
        workspace_id: str,
        key: Literal["chats"],
        value: list[OpenChatSettingDetails],
    ) -> None: ...

    def set_workspace_setting(
        self,
        workspace_id: str,
        key: str,
        value: Any,
    ) -> None:

        setting = self._schema.get_setting(SettingType.WORKSPACE, key)
        if setting is None:
            raise ValueError(f"Invalid workspace setting: {key}")

        if workspace_id not in self._settings["workspaces"]:
            raise ValueError(f"Workspace does not exists: {workspace_id}")

        self._settings["workspaces"][workspace_id][key] = setting.validate_value(value)
        self._commit_settings("workspaces")

    @overload
    def get_workspace_setting(
        self, workspace_id: str, key: Literal["chats"]
    ) -> list[OpenChatSettingDetails]: ...
    @overload
    def get_workspace_setting(
        self, workspace_id: str, key: WorkspaceStringSettings
    ) -> str: ...
    def get_workspace_setting(self, workspace_id: str, key: str) -> Any:
        setting = self._schema.get_setting(SettingType.WORKSPACE, key)
        if setting is None:
            raise ValueError(f"Invalid workspace setting: {key}")

        if workspace_id not in self._settings["workspaces"]:
            raise ValueError(f"Workspace does not exists: {workspace_id}")

        try:
            return self._settings["workspaces"][workspace_id][key]
        except KeyError:
            return setting.default

    def get_workspace_count(self) -> int:
        return len(self._settings["workspaces"].keys())

    def get_workspaces(self) -> list[str]:
        workspace_order = app.settings.get_app_setting("workspace_order")

        def sort_workspaces(workspace_id: str) -> int:
            try:
                return workspace_order.index(workspace_id)
            except ValueError:
                # Handle the case that a workspace id is for some reason not
                # in the workspace order list
                return 10000

        workspaces = list(self._settings["workspaces"].keys())
        workspaces.sort(key=sort_workspaces)
        return workspaces

    def workspace_exists(self, workspace_id: str) -> bool:
        return workspace_id in app.settings.get_workspaces()

    def add_workspace(self, name: str) -> str:
        id_ = str(uuid.uuid4())
        self._settings["workspaces"][id_] = {
            "name": name,
        }
        self._commit_settings("workspaces")
        return id_

    def remove_workspace(self, id_: str) -> None:
        del self._settings["workspaces"][id_]
        self._commit_settings("workspaces")

    def shutdown(self) -> None:
        if self._commit_scheduled is not None:
            GLib.source_remove(self._commit_scheduled)
            self._commit_scheduled = None

        self._commit()
        self._con.close()
        del self._con
