# Copyright (C) 2003-2017 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
#                    Norman Rasmussen <norman AT rasmussen.co.za>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    James Newton <redshodan AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2016-2017 Emmanuel Gil Peyrot <linkmauve AT linkmauve.fr>
#                         Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import os
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import UTC
from pathlib import Path

from gi.repository import Adw
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType

import gajim
from gajim.common import app
from gajim.common import configpaths
from gajim.common import events
from gajim.common import ged
from gajim.common import idle
from gajim.common.application import CoreApplication
from gajim.common.const import GAJIM_FAQ_URI
from gajim.common.const import GAJIM_PRIVACY_POLICY_URI
from gajim.common.const import GAJIM_SUPPORT_JID
from gajim.common.const import GAJIM_WIKI_URI
from gajim.common.helpers import dump_json
from gajim.common.helpers import load_json
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.uri import open_file
from gajim.common.util.uri import open_uri
from gajim.common.util.uri import show_in_folder

from gajim.gtk import structs
from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.avatar import AvatarStorage
from gajim.gtk.const import ACCOUNT_ACTIONS
from gajim.gtk.const import ALWAYS_ACCOUNT_ACTIONS
from gajim.gtk.const import APP_ACTIONS
from gajim.gtk.const import FEATURE_ACCOUNT_ACTIONS
from gajim.gtk.const import MuteState
from gajim.gtk.const import ONLINE_ACCOUNT_ACTIONS
from gajim.gtk.const import SHORTCUTS
from gajim.gtk.util.icons import get_icon_theme
from gajim.gtk.util.misc import add_alternative_accelerator
from gajim.gtk.util.window import get_app_window
from gajim.gtk.util.window import get_app_windows
from gajim.gtk.util.window import open_window

ActionListT = list[tuple[str, Callable[[Gio.SimpleAction, GLib.Variant], Any]]]


class GajimApplication(Adw.Application, CoreApplication):
    """Main class handling activation and command line."""

    def __init__(self):
        CoreApplication.__init__(self)
        flags = (
            Gio.ApplicationFlags.HANDLES_COMMAND_LINE
            | Gio.ApplicationFlags.CAN_OVERRIDE_APP_ID
        )
        Adw.Application.__init__(
            self, application_id=app.get_default_app_id(), flags=flags
        )

        # required to track screensaver state
        self.props.register_session = True

        self.add_main_option(
            "version",
            ord("V"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Show the application's version"),
        )

        self.add_main_option(
            "quiet",
            ord("q"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Show only critical errors"),
        )

        self.add_main_option(
            "separate",
            ord("s"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _(
                "Separate profile files completely "
                "(even history database and plugins)"
            ),
        )

        self.add_main_option(
            "verbose",
            ord("v"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Print XML stanzas and other debug information"),
        )

        self.add_main_option(
            "profile",
            ord("p"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Use defined profile in configuration directory"),
            "NAME",
        )

        self.add_main_option(
            "user-profile",
            ord("u"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Use a profile to run multiple Gajim instances"),
            "NAME",
        )

        self.add_main_option(
            "config-path",
            ord("c"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Set configuration directory"),
            "PATH",
        )

        self.add_main_option(
            "loglevel",
            ord("l"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Configure logging system"),
            "LEVEL",
        )

        self.add_main_option(
            "warnings",
            ord("w"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Show all warnings"),
        )

        self.add_main_option(
            "gdebug",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Sets an environment variable so GLib debug messages are printed"),
        )

        self.add_main_option(
            "cprofile",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Profile application with cprofile"),
        )

        self.add_main_option(
            "start-chat",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Start a new chat"),
        )

        self.add_main_option_entries(self._get_remaining_entry())

        self.connect("activate", self._on_activate)
        self.connect("handle-local-options", self._handle_local_options)
        self.connect("command-line", self._command_line)
        self.connect("shutdown", self._shutdown)

    @staticmethod
    def _get_remaining_entry():
        option = GLib.OptionEntry()
        # https://gitlab.gnome.org/GNOME/pygobject/-/issues/608
        option.arg = int(GLib.OptionArg.STRING_ARRAY)  # pyright: ignore
        option.arg_data = None
        option.arg_description = "[URI …]"
        option.flags = GLib.OptionFlags.NONE
        option.long_name = GLib.OPTION_REMAINING
        option.short_name = 0
        return [option]

    def _startup(self) -> None:
        if sys.platform in ("win32", "darwin"):
            # Changing the PANGOCAIRO_BACKEND is necessary on Windows/MacOS
            # to render colored emoji glyphs
            os.environ["PANGOCAIRO_BACKEND"] = "fontconfig"

        app.ged.register_event_handler("db-migration", 0, self._on_db_migration)

        if not self._init_core():
            return

        icon_theme = get_icon_theme()
        icon_theme.add_search_path(str(configpaths.get("ICONS")))

        self.avatar_storage = AvatarStorage()

        app.load_css_config()

        from gajim.gtk.main import MainWindow

        main_window = MainWindow()

        from gajim.gtk import notification

        notification.init()

        idle.Monitor.set_interval(
            app.settings.get("autoawaytime") * 60, app.settings.get("autoxatime") * 60
        )

        from gajim.gtk.status_icon import StatusIcon

        self.systray = StatusIcon()

        self._add_app_actions()
        accounts = app.settings.get_accounts()
        for account in accounts:
            self.add_account_actions(account)

        self._load_shortcuts()
        self.update_app_actions_state()

        self.register_event("feature-discovered", ged.CORE, self._on_feature_discovered)

        main_window.init()

        if self._deprecated_options_used:
            migration_url = (
                "https://dev.gajim.org/gajim/gajim/-/wikis/Profile-Migration"
            )
            InformationAlertDialog(
                "Deprecation Warning",
                (
                    "The options <b>--profile</b> and <b>--separate</b> are deprecated "
                    "and will be removed in a future version of Gajim. Visit our "
                    f"<a href='{migration_url}'>Wiki</a> "
                    "to find the instructions on how to migrate."
                ),
                body_use_markup=True,
            )

        GLib.timeout_add(100, self._auto_connect)

    def _shutdown(self, _application: GajimApplication) -> None:
        self._shutdown_core()

    def _quit_app(self) -> None:
        self.quit()

    def _command_line(
        self, _application: GajimApplication, command_line: Gio.ApplicationCommandLine
    ) -> int:
        """Handles command line options not related to the startup of Gajim."""

        options = command_line.get_options_dict()

        remote_commands = [
            ("start-chat", GLib.Variant("as", ["", ""])),
        ]

        for cmd, parameter in remote_commands:
            if options.contains(cmd):
                self.activate_action(cmd, parameter)
                return 0

        remaining = options.lookup_value(
            GLib.OPTION_REMAINING, GLib.VariantType.new("as")
        )

        if remaining is not None:
            self.activate_action("handle-uri", remaining)
            return 0

        if not options.contains("is-first-startup"):
            # If no commands have been handled and it's not the first
            # startup, raise the application.
            self.activate()

        return 0

    def _handle_local_options(
        self, _application: Gtk.Application, options: GLib.VariantDict
    ) -> int:

        if options.contains("version"):
            print(gajim.__version__)
            return 0

        application_name = "Gajim"

        # --profile is deprecated with Gajim 2.3.0
        profile = options.lookup_value("profile")
        user_profile = options.lookup_value("user-profile")
        if user_profile is not None:
            if options.contains("separate"):
                print("--separate cannot be used with --user-profile")
                return 0

            if options.contains("profile"):
                print("--profile cannot be used with --user-profile")
                return 0

            configpaths.set_user_profile(user_profile.get_string())

        elif profile is not None:
            user_profile = profile
            configpaths.set_profile(user_profile.get_string())

        if user_profile is not None:
            # Incorporate user_profile name into application id
            # to have a single app instance for each user_profile.
            user_profile_str = user_profile.get_string()
            application_name = f"Gajim ({user_profile_str})"
            app_id = f"{self.get_application_id()}.{user_profile_str}"
            self.set_application_id(app_id)
            configpaths.set_user_profile(user_profile_str)

        GLib.set_application_name(application_name)

        self.register()
        if self.get_is_remote():
            print(
                "Gajim is already running. "
                "The primary instance will handle remote commands"
            )
            return -1

        self._deprecated_options_used = options.contains("profile") or options.contains(
            "separate"
        )

        options.insert_value("is-first-startup", GLib.Variant("b", True))
        self._core_command_line(options)
        self._startup()
        return -1

    def _on_activate(self, _application: Gtk.Application) -> None:
        app.window.show_window()

    def _add_app_actions(self) -> None:
        for action in APP_ACTIONS:
            action_name, variant = action
            if variant is not None:
                variant = GLib.VariantType.new(variant)

            act = Gio.SimpleAction.new(action_name, variant)
            self.add_action(act)

        self._connect_app_actions()

    def _connect_app_actions(self) -> None:
        actions: ActionListT = [
            ("quit", self._on_quit_action),
            ("add-account", self._on_add_account_action),
            ("manage-proxies", self._on_manage_proxies_action),
            ("preferences", self._on_preferences_action),
            ("plugins", self._on_plugins_action),
            ("xml-console", self._on_xml_console_action),
            ("shortcuts", self._on_shortcuts_action),
            ("features", self._on_features_action),
            ("content", self._on_content_action),
            ("join-support-chat", self._on_join_support_chat),
            ("about", self._on_about_action),
            ("faq", self._on_faq_action),
            ("privacy-policy", self._on_privacy_policy_action),
            ("start-chat", self._on_new_chat_action),
            ("accounts", self._on_accounts_action),
            ("add-contact", self._on_add_contact_action),
            ("copy-text", self._on_copy_text_action),
            ("open-link", self._on_open_link_action),
            ("export-history", self._on_export_history_action),
            ("remove-history", self._on_remove_history_action),
            ("create-groupchat", self._on_create_groupchat_action),
            ("forget-groupchat", self._on_forget_groupchat_action),
            ("open-chat", self._on_open_chat_action),
            ("mute-chat", self._on_mute_chat_action),
            ("save-file-as", self._on_save_file_as),
            ("open-file", self._on_open_file),
            ("open-folder", self._on_open_folder),
        ]

        for action in actions:
            action_name, func = action
            act = self.lookup_action(action_name)
            assert act is not None
            act.connect("activate", func)
            self.add_action(act)

    def add_account_actions(self, account: str) -> None:
        for action_name, type_ in ACCOUNT_ACTIONS:
            account_action_name = f"{account}-{action_name}"
            if self.has_action(account_action_name):
                raise ValueError("Trying to add action more than once")

            variant_type = None
            if type_ is not None:
                variant_type = GLib.VariantType.new(type_)
            act = Gio.SimpleAction.new(account_action_name, variant_type)
            act.set_enabled(action_name in ALWAYS_ACCOUNT_ACTIONS)
            self.add_action(act)

        self._connect_account_actions(account)

    def _connect_account_actions(self, account: str) -> None:
        actions = [
            ("add-contact", self._on_add_contact_account_action),
            ("services", self._on_services_action),
            ("profile", self._on_profile_action),
            ("pep-config", self._on_pep_config_action),
            ("open-event", self._on_open_event_action),
            ("mark-as-read", self._on_mark_as_read_action),
            ("block-contact", self._on_block_contact),
            ("remove-contact", self._on_remove_contact),
            ("execute-command", self._on_execute_command),
            ("subscription-accept", self._on_subscription_accept),
            ("subscription-deny", self._on_subscription_deny),
        ]

        for action_name, func in actions:
            account_action_name = f"{account}-{action_name}"
            act = self.lookup_action(account_action_name)
            assert act is not None
            act.connect("activate", func)

    def remove_account_actions(self, account: str) -> None:
        for action_name in self.list_actions():
            if action_name.startswith(f"{account}-"):
                self.remove_action(action_name)

    def set_action_state(self, action_name: str, state: bool) -> None:
        action = self.lookup_action(action_name)
        assert isinstance(action, Gio.SimpleAction)
        action.set_enabled(state)

    def set_account_actions_state(self, account: str, new_state: bool = False) -> None:

        for action_name in ONLINE_ACCOUNT_ACTIONS:
            self.set_action_state(f"{account}-{action_name}", new_state)

        # Disable all feature actions on disconnect
        if not new_state:
            for action_name in FEATURE_ACCOUNT_ACTIONS:
                self.set_action_state(f"{account}-{action_name}", new_state)

    def update_feature_actions_state(self, account: str) -> None:
        client = app.get_client(account)
        blocking_available = client.get_module("Blocking").supported

        self.set_action_state(f"{account}-block-contact", blocking_available)

    def update_app_actions_state(self) -> None:
        active_accounts = bool(app.get_connected_accounts(exclude_local=True))
        self.set_action_state("create-groupchat", active_accounts)

        enabled_accounts = bool(app.settings.get_active_accounts())
        self.set_action_state("start-chat", enabled_accounts)

    @staticmethod
    def get_user_shortcuts() -> dict[str, list[str]]:
        user_path = configpaths.get("MY_SHORTCUTS")
        user_shortcuts: dict[str, list[str]] = {}
        if user_path.exists():
            app.log("app").info("Load user shortcuts")
            user_shortcuts = load_json(user_path, default={})

        return user_shortcuts

    def set_user_shortcuts(self, user_shortcuts: dict[str, list[str]]) -> None:
        user_path = configpaths.get("MY_SHORTCUTS")
        dump_json(user_path, user_shortcuts)
        self._load_shortcuts()

    def _load_shortcuts(self) -> None:
        shortcuts = {
            action_name: shortcut_data.accelerators
            for action_name, shortcut_data in SHORTCUTS.items()
        }
        user_shortcuts = self.get_user_shortcuts()
        shortcuts.update(user_shortcuts)

        for action, accelerators in shortcuts.items():
            self.set_accels_for_action(
                action, add_alternative_accelerator(accelerators)
            )

    def _on_feature_discovered(self, event: events.FeatureDiscovered) -> None:
        self.update_feature_actions_state(event.account)

    def create_account(
        self,
        account: str,
        address: JID,
        password: str,
        proxy_name: str | None,
        custom_host: tuple[str, ConnectionProtocol, ConnectionType] | None,
        anonymous: bool = False,
    ) -> None:

        CoreApplication.create_account(
            self, account, address, password, proxy_name, custom_host, anonymous
        )

        app.css_config.refresh()

        # Action must be added before account window is updated
        self.add_account_actions(account)

    def enable_account(self, account: str) -> None:
        CoreApplication.enable_account(self, account)
        self.update_app_actions_state()

    def disable_account(self, account: str) -> None:
        for win in get_app_windows(account):
            # Close all account specific windows, except the RemoveAccount
            # dialog. It shows if the removal was successful.
            if type(win).__name__ == "RemoveAccount":
                continue
            win.close()

        CoreApplication.disable_account(self, account)

        self.update_app_actions_state()

    def remove_account(self, account: str) -> None:
        CoreApplication.remove_account(self, account)

        self.remove_account_actions(account)

    def _on_db_migration(self, _event: events.DBMigration) -> None:
        open_window("DBMigration")

        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(may_block=False)

    # Action Callbacks

    @staticmethod
    def _on_add_contact_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        jid = param.get_string() or None
        if jid is not None:
            jid = JID.from_string(jid)
        open_window("AddContact", account=None, jid=jid)

    @staticmethod
    def _on_preferences_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_window("Preferences")

    @staticmethod
    def _on_plugins_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_window("Preferences").show_page("plugins")

    @staticmethod
    def _on_accounts_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        window = open_window("Preferences")

        account = param.get_string()
        if account:
            window.show_page(account)

    @staticmethod
    def _on_quit_action(_action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        app.window.quit()

    @staticmethod
    def _on_new_chat_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:

        jid, initial_message = param.get_strv()
        open_window(
            "StartChatDialog",
            initial_jid=jid or None,
            initial_message=initial_message or None,
        )

    @staticmethod
    def _on_profile_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        account = param.get_string()
        open_window("ProfileWindow", account=account)

    @staticmethod
    def _on_services_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        account = param.get_string()
        open_window("ServiceDiscoveryWindow", account=account, address_entry=True)

    @staticmethod
    def _on_create_groupchat_action(
        _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        account = param.get_string()
        open_window("CreateGroupchatWindow", account=account or None)

    @structs.actionmethod
    def _on_add_contact_account_action(
        self, _action: Gio.SimpleAction, params: structs.AccountJidParam
    ) -> None:
        open_window("AddContact", account=params.account, jid=params.jid)

    @staticmethod
    def _on_add_account_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_window("AccountWizard")

    @structs.actionmethod
    def _on_block_contact(
        self, _action: Gio.SimpleAction, params: structs.AccountJidParam
    ) -> None:
        app.window.block_contact(params.account, params.jid)

    def _on_remove_contact(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        account, jid = param.unpack()
        app.window.remove_contact(account, JID.from_string(jid))

    def _on_execute_command(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        account, jids = param.unpack()
        open_window("AdHocCommands", account=account, jids=jids)

    @staticmethod
    @structs.actionfunction
    def _on_subscription_accept(
        _action: Gio.SimpleAction, params: structs.SubscriptionAcceptParam
    ) -> None:
        client = app.get_client(params.account)
        client.get_module("Presence").subscribed(params.jid)
        contact = client.get_module("Contacts").get_contact(params.jid)
        assert isinstance(contact, BareContact)
        if not contact.is_in_roster:
            open_window(
                "AddContact",
                account=params.account,
                jid=params.jid,
                nick=params.nickname or contact.name,
            )

    @staticmethod
    @structs.actionfunction
    def _on_subscription_deny(
        _action: Gio.SimpleAction, params: structs.AccountJidParam
    ) -> None:
        client = app.get_client(params.account)
        client.get_module("Presence").unsubscribed(params.jid)

    @staticmethod
    def _on_pep_config_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        account = param.get_string()
        open_window("PEPConfig", account=account)

    @staticmethod
    def _on_xml_console_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_window("DebugConsoleWindow")

    @staticmethod
    def _on_manage_proxies_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_window("ManageProxies")

    @staticmethod
    def _on_content_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_uri(GAJIM_WIKI_URI)

    @staticmethod
    def _on_join_support_chat(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        accounts = app.settings.get_active_accounts()
        if len(accounts) == 1:
            app.window.show_add_join_groupchat(accounts[0], GAJIM_SUPPORT_JID)
            return
        open_window("StartChatDialog", initial_jid=GAJIM_SUPPORT_JID)

    @staticmethod
    def _on_faq_action(_action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        open_uri(GAJIM_FAQ_URI)

    @staticmethod
    def _on_privacy_policy_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_uri(GAJIM_PRIVACY_POLICY_URI)

    @staticmethod
    def _on_shortcuts_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_window("Preferences").show_page("shortcuts")

    @staticmethod
    def _on_features_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        open_window("Features")

    @staticmethod
    def _on_about_action(
        _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        app.window.about_dialog.present()

    # @staticmethod
    # TODO Jingle FT
    # def _on_file_transfer_action(_action: Gio.SimpleAction,
    #                              _param: GLib.Variant | None) -> None:

    #     ft = app.interface.instances['file_transfers']
    #     if ft.window.get_property('visible'):
    #         ft.window.present()
    #     else:
    #         ft.window.show_all()

    @staticmethod
    @structs.actionfunction
    def _on_open_event_action(
        _action: Gio.SimpleAction, params: structs.OpenEventActionParams
    ) -> None:
        if params.type in ("connection-failed", "server-shutdown"):

            app.window.show_account_page(params.account)

        elif params.type in (
            "subscription-request",
            "muc-invitation",
        ):

            app.window.show_activity_page(params.context_id)

        elif params.type in ("incoming-message", "incoming-call", "file-transfer"):

            assert params.jid
            jid = JID.from_string(params.jid)
            app.window.select_chat(params.account, jid)

        app.window.present()

    @structs.actionmethod
    def _on_mark_as_read_action(
        self, _action: Gio.SimpleAction, params: structs.AccountJidParam
    ) -> None:

        app.window.mark_as_read(params.account, params.jid)

    @staticmethod
    def _on_open_link_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        open_uri(param.get_string())

    @staticmethod
    def _on_copy_text_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        app.window.get_clipboard().set(param.get_string())

    @staticmethod
    def _on_open_chat_action(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        account, jid = param.get_strv()
        app.window.start_chat_from_jid(account, jid)

    @staticmethod
    @structs.actionfunction
    def _on_mute_chat_action(
        _action: Gio.SimpleAction, params: structs.MuteContactParam
    ) -> None:

        client = app.get_client(params.account)
        contact = client.get_module("Contacts").get_contact(params.jid)
        assert not isinstance(contact, ResourceContact)

        if params.state == MuteState.UNMUTE:
            contact.settings.set("mute_until", None)
            return

        until = datetime.now(UTC) + timedelta(minutes=params.state)
        contact.settings.set("mute_until", until.isoformat())

    @staticmethod
    @structs.actionfunction
    def _on_export_history_action(
        _action: Gio.SimpleAction, params: structs.ExportHistoryParam
    ) -> None:
        open_window("HistoryExport", account=params.account, jid=params.jid)

    @staticmethod
    @structs.actionfunction
    def _on_remove_history_action(
        _action: Gio.SimpleAction, params: structs.AccountJidParam
    ) -> None:
        def _on_response() -> None:
            app.storage.archive.remove_history_for_jid(params.account, params.jid)

            app.window.clear_chat_list_row(params.account, params.jid)
            control = app.window.get_control()
            if not control.is_chat_active(params.account, params.jid):
                return

            control.reset_view()

        ConfirmationAlertDialog(
            _("Remove Chat History?"),
            _("Do you want to remove all chat history for this chat?"),
            confirm_label=_("_Remove"),
            appearance="destructive",
            callback=_on_response,
        )

    @staticmethod
    @structs.actionfunction
    def _on_forget_groupchat_action(
        _action: Gio.SimpleAction, params: structs.AccountJidParam
    ) -> None:

        def _on_response() -> None:
            window = get_app_window("StartChatDialog")
            if window is not None:
                window.remove_row(params.account, params.jid)

            client = app.get_client(params.account)
            client.get_module("MUC").leave(params.jid)
            client.get_module("Bookmarks").remove(params.jid)

            app.storage.archive.remove_history_for_jid(params.account, params.jid)

        ConfirmationAlertDialog(
            _("Forget this Group Chat?"),
            _("Do you want to remove this chat including its chat history?"),
            confirm_label=_("_Remove"),
            appearance="destructive",
            callback=_on_response,
        )

    def _on_save_file_as(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        orig_path = Path(param.get_string())

        def _on_save_finished(
            file_dialog: Gtk.FileDialog, result: Gio.AsyncResult
        ) -> None:
            try:
                gfile = file_dialog.save_finish(result)
            except GLib.Error as e:
                if e.code == 2:
                    # User dismissed dialog, do nothing
                    return

                InformationAlertDialog(
                    _("Could Not Save File"),
                    _("Could not save file to selected directory."),
                )
                return

            path = gfile.get_path()
            assert path is not None
            target_path = Path(path)
            orig_ext = orig_path.suffix
            new_ext = target_path.suffix
            if orig_ext != new_ext:
                # Windows file chooser selects the full file name including
                # extension. Starting to type will overwrite the extension
                # as well. Restore the extension if it's lost.
                target_path = target_path.with_suffix(orig_ext)
            dirname = target_path.parent
            if not os.access(dirname, os.W_OK):
                InformationAlertDialog(
                    _("Directory Not Writable"),
                    _(
                        'Directory "%s" is not writable. '
                        "You do not have the proper permissions to "
                        "create files in this directory."
                    )
                    % dirname,
                )
                return

            try:
                shutil.copyfile(orig_path, target_path)
            except Exception as e:
                InformationAlertDialog(
                    _("Could Not Save File"),
                    _(
                        "There was an error while trying to save the file.\n"
                        "Error: %s."
                    )
                    % e,
                )
                return

            app.settings.set("last_save_dir", str(target_path.parent))

            app.window.show_toast(
                Adw.Toast(
                    title=_("File saved"),
                    timeout=5,
                    button_label=_("Open Folder"),
                    action_name="app.open-folder",
                    action_target=GLib.Variant("s", str(target_path)),
                )
            )

        gfile = None
        last_dir = app.settings.get("last_save_dir")
        if last_dir:
            gfile = Gio.File.new_for_path(last_dir)

        dialog = Gtk.FileDialog(
            initial_folder=gfile,
            initial_name=orig_path.name,
        )
        dialog.save(app.window, None, _on_save_finished)

    def _on_open_file(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        open_file(Path(param.get_string()))

    def _on_open_folder(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        show_in_folder(Path(param.get_string()))
