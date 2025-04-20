# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import TYPE_CHECKING

import logging
import os
import shutil
from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.types import BlockingReportValues

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common import types
from gajim.common.client import Client
from gajim.common.const import Direction
from gajim.common.const import Display
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.helpers import play_sound
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.storage.archive.const import MessageType
from gajim.common.util.uri import open_file
from gajim.common.util.uri import open_uri
from gajim.common.util.uri import show_in_folder

from gajim.gtk.account_side_bar import AccountSideBar
from gajim.gtk.activity_side_bar import ActivitySideBar
from gajim.gtk.builder import get_builder
from gajim.gtk.chat_list import ChatList
from gajim.gtk.chat_list_row import ChatListRow
from gajim.gtk.chat_stack import ChatStack
from gajim.gtk.const import MAIN_WIN_ACTIONS
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.dialogs import SimpleDialog
from gajim.gtk.emoji_chooser import EmojiChooser
from gajim.gtk.main_menu_button import MainMenuButton
from gajim.gtk.main_stack import MainStack
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.structs import actionmethod
from gajim.gtk.structs import AddChatActionParams
from gajim.gtk.structs import ChatListEntryParam
from gajim.gtk.structs import DeleteMessageParam
from gajim.gtk.structs import ModerateAllMessagesParam
from gajim.gtk.structs import ModerateMessageParam
from gajim.gtk.structs import RetractMessageParam
from gajim.gtk.util.window import get_app_window
from gajim.gtk.util.window import open_window
from gajim.gtk.util.window import resize_window
from gajim.gtk.workspace_side_bar import WorkspaceSideBar

if TYPE_CHECKING:
    from gajim.gtk.control import ChatControl

if app.is_display(Display.X11):
    from gi.repository import GdkX11

log = logging.getLogger("gajim.gtk.main")


class MainWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_title(GLib.get_application_name())
        self.set_default_icon_name("gajim")

        app.window = self

        self._add_actions()
        self._add_stateful_actions()
        self._connect_actions()

        self._startup_finished: bool = False

        self._ui = get_builder("main.ui")

        self.set_child(self._ui.main_grid)

        self._emoji_chooser: EmojiChooser | None = None

        self._main_stack = MainStack()
        self._ui.main_grid.attach(self._main_stack, 1, 0, 1, 1)

        self._chat_page = self._main_stack.get_chat_page()

        self._ui.left_grid.attach(MainMenuButton(), 0, 0, 1, 1)

        self._activity_side_bar = ActivitySideBar(self._chat_page)
        self._ui.activity_box.prepend(self._activity_side_bar)

        self._workspace_side_bar = WorkspaceSideBar(self._chat_page)
        self._ui.workspace_scrolled.set_child(self._workspace_side_bar)

        self._account_side_bar = AccountSideBar()
        self._ui.account_box.append(self._account_side_bar)

        self.connect("notify::is-active", self._on_window_active)
        self.connect("close-request", self._on_close_request)

        controller = Gtk.EventControllerMotion(
            propagation_phase=Gtk.PropagationPhase.BUBBLE
        )
        controller.connect("motion", self._on_window_motion_notify)
        self.add_controller(controller)

        controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.BUBBLE
        )
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

        self.register_events(
            [
                ("message-received", ged.GUI1, self._on_message_received),
                ("read-state-sync", ged.GUI1, self._on_read_state_sync),
                ("call-started", ged.GUI1, self._on_call_started),
                ("jingle-request-received", ged.GUI1, self._on_jingle_request),
                ("file-request-received", ged.GUI1, self._on_file_request),
                ("account-enabled", ged.GUI1, self._on_account_enabled),
                ("account-disabled", ged.GUI1, self._on_account_disabled),
                ("roster-item-exchange", ged.GUI1, self._on_roster_item_exchange),
                ("plain-connection", ged.GUI1, self._on_plain_connection),
                ("password-required", ged.GUI1, self._on_password_required),
                ("http-auth", ged.GUI1, self._on_http_auth),
                ("muc-added", ged.GUI1, self._on_muc_added),
                ("message-sent", ged.GUI1, self._on_message_sent),
                ("signed-in", ged.GUI1, self._on_signed_in),
            ]
        )

        self._check_for_account()
        self._load_chats()
        self._load_unread_counts()

        self._prepare_window()

        chat_list_stack = self._chat_page.get_chat_list_stack()
        app.app.systray.connect_unread_widget(chat_list_stack, "unread-count-changed")

        self.set_show_menubar(app.settings.get_app_setting("show_main_menu"))

        for client in app.get_clients():
            client.connect_signal("state-changed", self._on_client_state_changed)
            client.connect_signal(
                "resume-successful", self._on_client_resume_successful
            )

    def get_action(self, name: str) -> Gio.SimpleAction:
        action = self.lookup_action(name)
        assert isinstance(action, Gio.SimpleAction)
        return action

    def get_chat_stack(self) -> ChatStack:
        return self._chat_page.get_chat_stack()

    def get_emoji_chooser(self) -> EmojiChooser:
        if self._emoji_chooser is None:
            self._emoji_chooser = EmojiChooser()

        parent = cast(Gtk.MenuButton | None, self._emoji_chooser.get_parent())
        if parent is not None:
            parent.set_popover(None)

        return self._emoji_chooser

    def show(self) -> None:
        self.present()

    def set_skip_taskbar_hint(self, value: bool) -> None:
        if not app.is_display(Display.X11):
            return
        toplevel = cast(GdkX11.X11Surface, self.get_surface())
        toplevel.set_skip_taskbar_hint(value)

    def set_urgency_hint(self, value: bool) -> None:
        if not app.is_display(Display.X11):
            return

        if not app.settings.get("use_urgency_hint"):
            return

        toplevel = cast(GdkX11.X11Surface, self.get_surface())
        toplevel.set_urgency_hint(value)

    def mark_workspace_as_read(self, workspace: str) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_chatlist(workspace)
        open_chats = chat_list.get_open_chats()
        for chat in open_chats:
            self.mark_as_read(chat["account"], chat["jid"])

    def _mark_workspace_as_read(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:

        workspace_id = param.get_string() or None
        if workspace_id is not None:
            self.mark_workspace_as_read(workspace_id)

    def _prepare_window(self) -> None:
        window_width = app.settings.get("mainwin_width")
        window_height = app.settings.get("mainwin_height")
        resize_window(self, window_width, window_height)

        self.set_visible(True)

        if app.is_display(Display.X11):
            self.set_skip_taskbar_hint(not app.settings.get("show_in_taskbar"))

        show_main_window = app.settings.get("show_main_window_on_startup")
        if show_main_window == "never":
            self.hide_window()

        elif show_main_window == "last_state" and not app.settings.get(
            "is_window_visible"
        ):
            self.hide_window()

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        client = app.get_client(event.account)
        client.connect_signal("state-changed", self._on_client_state_changed)
        client.connect_signal("resume-successful", self._on_client_resume_successful)

    def _on_account_disabled(self, event: events.AccountDisabled) -> None:
        workspace_id = self._workspace_side_bar.get_first_workspace()
        self.activate_workspace(workspace_id)
        self._main_stack.remove_account_page(event.account)
        self._main_stack.remove_chats_for_account(event.account)

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:

        if keyval == Gdk.KEY_space:
            self.get_chat_stack().get_message_input().grab_focus()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_client_state_changed(
        self, client: Client, _signal_name: str, state: SimpleClientState
    ) -> None:

        app.app.set_account_actions_state(client.account, state.is_connected)
        app.app.update_app_actions_state()

    def _on_client_resume_successful(self, client: Client, _signal_name: str) -> None:

        app.app.update_feature_actions_state(client.account)

    @staticmethod
    def _on_roster_item_exchange(event: events.RosterItemExchangeEvent) -> None:
        open_window(
            "RosterItemExchange",
            account=event.client.account,
            action=event.action,
            exchange_list=event.exchange_items_list,
            jid_from=event.jid,
        )

    @staticmethod
    def _on_plain_connection(event: events.PlainConnection) -> None:
        ConfirmationDialog(
            _("Insecure Connection"),
            _(
                "You are about to connect to the account %(account)s "
                "(%(server)s) using an insecure connection method. This means "
                "conversations will not be encrypted. Connecting PLAIN is "
                "strongly discouraged."
            )
            % {
                "account": event.account,
                "server": app.get_hostname_from_account(
                    event.account, prefer_custom=True
                ),
            },
            [
                DialogButton.make("Cancel", text=_("_Abort"), callback=event.abort),
                DialogButton.make(
                    "Remove", text=_("_Connect Anyway"), callback=event.connect
                ),
            ],
        )

    @staticmethod
    def _on_password_required(event: events.PasswordRequired) -> None:
        open_window("PasswordDialog", account=event.client.account, event=event)

    @staticmethod
    def _on_http_auth(event: events.HttpAuth) -> None:
        def _response(answer: str) -> None:
            event.client.get_module("HTTPAuth").build_http_auth_answer(
                event.stanza, answer
            )

        account = event.client.account
        message = _("HTTP (%(method)s) Authorization for %(url)s (ID: %(id)s)") % {
            "method": event.data.method,
            "url": event.data.url,
            "id": event.data.id,
        }
        sec_msg = _("Do you accept this request?")
        if app.get_number_of_connected_accounts() > 1:
            sec_msg = _("Do you accept this request (account: %s)?") % account
        if event.data.body:
            sec_msg = event.data.body + "\n" + sec_msg
        message = message + "\n" + sec_msg

        ConfirmationDialog(
            _("HTTP Authorization Request"),
            message,
            [
                DialogButton.make(
                    "Cancel", text=_("_No"), callback=_response, args=["no"]
                ),
                DialogButton.make("Accept", callback=_response, args=["yes"]),
            ],
        )

    def _on_muc_added(self, event: events.MucAdded) -> None:
        if self.chat_exists(event.account, event.jid):
            return

        self.add_group_chat(event.account, event.jid, select=event.select_chat)

    def _on_message_sent(self, event: events.MessageSent) -> None:
        if not event.play_sound:
            return

        enabled = app.settings.get_soundevent_settings("message_sent")["enabled"]
        if enabled:
            if isinstance(event.jid, list) and len(event.jid) > 1:
                return
            play_sound("message_sent", event.account)

    def _on_signed_in(self, event: events.SignedIn) -> None:
        if app.settings.get("ask_online_status"):
            self.show_account_page(event.account)

    def _add_actions(self) -> None:
        for action, variant_type, enabled in MAIN_WIN_ACTIONS:
            if variant_type is not None:
                variant_type = GLib.VariantType(variant_type)
            act = Gio.SimpleAction.new(action, variant_type)
            act.set_enabled(enabled)
            self.add_action(act)

    def _add_stateful_actions(self) -> None:
        action = Gio.SimpleAction.new_stateful(
            "set-encryption", GLib.VariantType("s"), GLib.Variant("s", "disabled")
        )

        self.add_action(action)

    def _connect_actions(self) -> None:
        actions = [
            ("change-nickname", self._on_action),
            ("change-subject", self._on_action),
            ("escape", self._on_action),
            ("close-chat", self._on_action),
            ("restore-chat", self._on_action),
            ("switch-next-chat", self._on_action),
            ("switch-prev-chat", self._on_action),
            ("switch-next-unread-chat", self._on_action),
            ("switch-prev-unread-chat", self._on_action),
            ("switch-chat-1", self._on_action),
            ("switch-chat-2", self._on_action),
            ("switch-chat-3", self._on_action),
            ("switch-chat-4", self._on_action),
            ("switch-chat-5", self._on_action),
            ("switch-chat-6", self._on_action),
            ("switch-chat-7", self._on_action),
            ("switch-chat-8", self._on_action),
            ("switch-chat-9", self._on_action),
            ("switch-workspace-1", self._on_action),
            ("switch-workspace-2", self._on_action),
            ("switch-workspace-3", self._on_action),
            ("switch-workspace-4", self._on_action),
            ("switch-workspace-5", self._on_action),
            ("switch-workspace-6", self._on_action),
            ("switch-workspace-7", self._on_action),
            ("switch-workspace-8", self._on_action),
            ("switch-workspace-9", self._on_action),
            ("increase-app-font-size", self._on_app_font_size_action),
            ("decrease-app-font-size", self._on_app_font_size_action),
            ("reset-app-font-size", self._on_app_font_size_action),
            ("toggle-chat-list", self._on_action),
            ("toggle-menu-bar", self._on_action),
            ("preview-download", self._on_preview_action),
            ("preview-open", self._on_preview_action),
            ("preview-save-as", self._on_preview_action),
            ("preview-open-folder", self._on_preview_action),
            ("preview-copy-link", self._on_preview_action),
            ("preview-open-link", self._on_preview_action),
            ("copy-message", self._on_copy_message),
            ("retract-message", self._on_retract_message),
            ("moderate-message", self._on_moderate_message),
            ("moderate-all-messages", self._on_moderate_all_messages),
            ("delete-message-locally", self._on_delete_message_locally),
            ("add-workspace", self._add_workspace),
            ("edit-workspace", self._edit_workspace),
            ("remove-workspace", self._remove_workspace),
            ("activate-workspace", self._activate_workspace),
            ("mark-workspace-as-read", self._mark_workspace_as_read),
            ("add-chat", self._add_chat),
            ("add-group-chat", self._add_group_chat),
            ("chat-contact-info", self._on_chat_contact_info),
        ]

        for action, func in actions:
            act = self.get_action(action)
            act.connect("activate", func)

    def _on_action(
        self, action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> int | None:

        action_name = action.get_name()
        log.info("Activate action: %s", action_name)

        if action_name == "escape" and self._chat_page.hide_search():
            return None

        chat_stack = self._chat_page.get_chat_stack()
        if action_name == "escape" and chat_stack.process_escape():
            return None

        control = self.get_control()
        if control.has_active_chat():
            if action_name == "change-nickname":
                app.window.activate_action("win.muc-change-nickname", None)
                return None

            if action_name == "change-subject":
                open_window("GroupchatDetails", contact=control.contact, page="manage")
                return None

            if action_name == "escape":
                if app.settings.get("escape_key_closes"):
                    self._chat_page.remove_chat(
                        control.contact.account, control.contact.jid
                    )
                    return None

            elif action_name == "close-chat":
                self._chat_page.remove_chat(
                    control.contact.account, control.contact.jid
                )
                return None

        if action_name == "escape" and app.settings.get("escape_key_closes"):
            self.close()

        elif action_name == "restore-chat":
            self._chat_page.restore_chat()

        elif action_name == "switch-next-chat":
            self.select_next_chat(Direction.NEXT)

        elif action_name == "switch-prev-chat":
            self.select_next_chat(Direction.PREV)

        elif action_name == "switch-next-unread-chat":
            self.select_next_chat(Direction.NEXT, unread_first=True)

        elif action_name == "switch-prev-unread-chat":
            self.select_next_chat(Direction.PREV, unread_first=True)

        elif action_name.startswith("switch-chat-"):
            number = int(action_name[-1]) - 1
            self.select_chat_number(number)

        elif action_name.startswith("switch-workspace-"):
            number = int(action_name[-1]) - 1
            self._workspace_side_bar.activate_workspace_number(number)

        elif action_name == "toggle-chat-list":
            self._toggle_chat_list()

        elif action_name == "toggle-menu-bar":
            show_menu_bar = not self.get_show_menubar()
            app.settings.set_app_setting("show_main_menu", show_menu_bar)
            self.set_show_menubar(show_menu_bar)

        return None

    def _on_app_font_size_action(
        self, action: Gio.SimpleAction, _param: GLib.Variant
    ) -> None:

        action_name = action.get_name()
        if action_name == "reset-app-font-size":
            app.settings.set_app_setting("app_font_size", None)
            app.css_config.apply_app_font_size()
            return

        app_font_size = app.settings.get("app_font_size")
        new_app_font_size = app_font_size
        if action_name == "increase-app-font-size":
            new_app_font_size = app_font_size + 0.125
        elif action_name == "decrease-app-font-size":
            new_app_font_size = app_font_size - 0.125

        # Clamp font size
        new_app_font_size = max(min(1.5, new_app_font_size), 1.0)

        if new_app_font_size == app_font_size:
            return

        app.settings.set_app_setting("app_font_size", new_app_font_size)
        app.css_config.apply_app_font_size()

    def _on_preview_action(self, action: Gio.SimpleAction, param: GLib.Variant) -> None:

        action_name = action.get_name()
        preview = app.preview_manager.get_preview(param.get_string())
        if preview is None:
            return

        if action_name == "preview-download":
            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)

        elif action_name == "preview-open":
            if preview.is_geo_uri:
                open_uri(preview.uri)
                return

            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)
                return

            assert preview.orig_path is not None
            open_file(preview.orig_path)

        elif action_name == "preview-save-as":

            def _on_save_finished(
                file_dialog: Gtk.FileDialog, result: Gio.AsyncResult
            ) -> None:
                try:
                    gfile = file_dialog.save_finish(result)
                except GLib.Error as e:
                    if e.code == 2:
                        # User dismissed dialog, do nothing
                        return

                    log.exception(e)
                    SimpleDialog(
                        _("Could Not Save File"),
                        _("Could not save file to selected directory."),
                        transient_for=self,
                    )
                    return

                assert preview is not None
                assert preview.orig_path is not None

                path = gfile.get_path()
                assert path is not None
                target_path = Path(path)
                orig_ext = preview.orig_path.suffix
                new_ext = target_path.suffix
                if orig_ext != new_ext:
                    # Windows file chooser selects the full file name including
                    # extension. Starting to type will overwrite the extension
                    # as well. Restore the extension if it's lost.
                    target_path = target_path.with_suffix(orig_ext)
                dirname = target_path.parent
                if not os.access(dirname, os.W_OK):
                    SimpleDialog(
                        _("Directory Not Writable") % dirname,
                        _(
                            'Directory "%s" is not writable. '
                            "You do not have the proper permissions to "
                            "create files in this directory."
                        )
                        % dirname,
                        transient_for=self,
                    )
                    return

                try:
                    shutil.copyfile(preview.orig_path, target_path)
                except PermissionError as e:
                    SimpleDialog(
                        _("Could Not Save File"),
                        _(
                            "You do not have permissions for this directory.\n"
                            "Error: %s."
                        )
                        % e,
                        transient_for=self,
                    )
                    return

                app.settings.set("last_save_dir", str(target_path.parent))

            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)
                return

            gfile = None
            last_dir = app.settings.get("last_save_dir")
            if last_dir:
                gfile = Gio.File.new_for_path(last_dir)

            dialog = Gtk.FileDialog(
                initial_folder=gfile,
                initial_name=preview.filename,
            )
            dialog.save(self, None, _on_save_finished)

        elif action_name == "preview-open-folder":
            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)
                return

            assert preview.orig_path is not None
            show_in_folder(preview.orig_path)

        elif action_name == "preview-copy-link":
            self.get_clipboard().set(preview.uri)

        elif action_name == "preview-open-link":
            if preview.is_aes_encrypted:
                if preview.is_geo_uri:
                    open_uri(preview.uri)
                    return

                assert preview.orig_path
                open_file(preview.orig_path)
            else:
                open_uri(preview.uri)

    def _toggle_chat_list(self) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            if chat_list.is_visible():
                self._ui.toggle_chat_list_button.set_tooltip_text(_("Show chat list"))
                self._ui.toggle_chat_list_icon.set_from_icon_name("go-next-symbolic")
            else:
                self._ui.toggle_chat_list_button.set_tooltip_text(_("Hide chat list"))
                self._ui.toggle_chat_list_icon.set_from_icon_name(
                    "go-previous-symbolic"
                )
        self._chat_page.toggle_chat_list()

    def _on_copy_message(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:

        self.get_clipboard().set(param.get_string())

    @actionmethod
    def _on_chat_contact_info(
        self, _action: Gio.SimpleAction, params: AccountJidParam
    ) -> None:
        client = app.get_client(params.account)
        contact = client.get_module("Contacts").get_contact(params.jid)
        if isinstance(contact, GroupchatContact):
            open_window("GroupchatDetails", contact=contact)
        else:
            open_window("ContactInfo", account=contact.account, contact=contact)

    @actionmethod
    def _on_retract_message(
        self, _action: Gio.SimpleAction, params: RetractMessageParam
    ) -> None:

        def _on_retract() -> None:
            client = app.get_client(params.account)
            contact = client.get_module("Contacts").get_contact(params.jid)
            assert not isinstance(contact, ResourceContact)
            client.get_module("Retraction").send_retraction(
                contact, params.retraction_id
            )

        ConfirmationDialog(
            _("Retract Message?"),
            _(
                "Do you want to retract this message?\n"
                "Please note that retracting a message does not guarantee that your "
                "provider or your contact’s device will remove it."
            ),
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Remove", text=_("_Retract"), callback=_on_retract),
            ],
            transient_for=app.window,
        )

    @actionmethod
    def _on_moderate_message(
        self, _action: Gio.SimpleAction, params: ModerateMessageParam
    ) -> None:

        def _on_moderate(reason: str) -> None:
            client = app.get_client(params.account)
            client.get_module("MUC").moderate_message(
                params.namespace, params.jid, params.stanza_id, reason or None
            )

        InputDialog(
            _("Moderate Message?"),
            _("Why do you want to moderate this message?"),
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Remove", text=_("_Moderate"), callback=_on_moderate),
            ],
            input_str=_("Spam"),
            transient_for=app.window,
        )

    @actionmethod
    def _on_moderate_all_messages(
        self, _action: Gio.SimpleAction, params: ModerateAllMessagesParam
    ) -> None:
        messages = app.storage.archive.get_message_stanza_ids_from_occupant(
            params.account, params.jid, params.occupant_id
        )
        if messages is None:
            SimpleDialog(
                _("No Messages Found"),
                _("Could not find any messages for this participant."),
            )
            return

        def _on_moderate(reason: str) -> None:
            client = app.get_client(params.account)
            groupchat_contact = client.get_module("Contacts").get_contact(params.jid)
            assert isinstance(groupchat_contact, GroupchatContact)
            if not groupchat_contact.is_joined:
                SimpleDialog(
                    _("Not Joined"), _("You are currently not joined this group chat")
                )
                return

            muc_module = client.get_module("MUC")
            for stanza_id in messages:
                muc_module.moderate_message(
                    params.namespace, params.jid, stanza_id, reason or None
                )

        InputDialog(
            _("Moderate Messages?"),
            _(
                "%(count)s messages from %(participant)s will be moderated.\n"
                "Why do you want to moderate these messages?"
            )
            % {"count": len(messages), "participant": params.nickname},
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Remove", text=_("_Moderate"), callback=_on_moderate),
            ],
            input_str=_("Spam"),
            transient_for=app.window,
        )

    @actionmethod
    def _on_delete_message_locally(
        self, _action: Gio.SimpleAction, params: DeleteMessageParam
    ) -> None:

        def _on_delete() -> None:
            app.storage.archive.delete_message(params.pk)
            app.ged.raise_event(
                events.MessageDeleted(
                    account=params.account, jid=params.jid, pk=params.pk
                )
            )

        ConfirmationDialog(
            _("Delete Message Locally?"),
            _("This message will be deleted from your local chat history"),
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Delete", callback=_on_delete),
            ],
            transient_for=app.window,
        )

    def _on_window_motion_notify(
        self,
        _widget: Gtk.EventControllerMotion,
        _x: float,
        _y: float,
    ) -> None:
        control = self.get_control()
        if not control.has_active_chat():
            return

        if self.is_active():
            client = app.get_client(control.contact.account)
            chat_stack = self._chat_page.get_chat_stack()
            msg_action_box = chat_stack.get_message_action_box()
            client.get_module("Chatstate").set_mouse_activity(
                control.contact, msg_action_box.msg_textview.has_text
            )

    def _on_close_request(self, _widget: Gtk.ApplicationWindow) -> int:
        if app.settings.get("confirm_on_window_delete"):
            open_window("QuitDialog")
            return Gdk.EVENT_STOP

        action = app.settings.get("action_on_close")
        if action == "hide":
            self.hide_window()
        elif action == "minimize":
            self.minimize()
        else:
            self.quit()

        return Gdk.EVENT_STOP

    def show_window(self) -> None:
        app.settings.set("is_window_visible", True)
        self.set_visible(True)

    def hide_window(self) -> None:
        app.settings.set("is_window_visible", False)
        self.set_visible(False)

    def _set_startup_finished(self) -> None:
        self._startup_finished = True
        self._chat_page.set_startup_finished()

    def _load_unread_counts(self) -> None:
        chats = app.storage.cache.get_unread()
        chat_list_stack = self._chat_page.get_chat_list_stack()

        for chat in chats:
            chat_list_stack.set_chat_unread_count(chat.account, chat.jid, chat.count)

    def show_account_page(self, account: str) -> None:
        self._activity_side_bar.unselect()
        self._workspace_side_bar.unselect_all()
        self._account_side_bar.select()
        self._main_stack.show_account(account)

    def get_active_workspace(self) -> str | None:
        return self._workspace_side_bar.get_active_workspace()

    def is_chat_active(self, account: str, jid: JID) -> bool:
        if not self.is_active():
            return False
        if self._main_stack.get_visible_page_name() != "chats":
            return False
        return self._chat_page.is_chat_selected(account, jid)

    def highlight_dnd_targets(self, drag_row: Any, highlight: bool) -> None:
        if isinstance(drag_row, ChatListRow):
            chat_list_stack = self._chat_page.get_chat_list_stack()
            workspace = self.get_active_workspace()
            if workspace is None:
                return

            if drag_row.is_pinned:
                chat_list = chat_list_stack.get_chatlist(workspace)
                for row in chat_list.get_chat_list_rows():
                    if not row.is_pinned:
                        continue

                    if highlight:
                        row.add_css_class("dnd-target-chatlist")
                    else:
                        row.remove_css_class("dnd-target-chatlist")

        if highlight:
            self._workspace_side_bar.add_css_class("dnd-target")
        else:
            self._workspace_side_bar.remove_css_class("dnd-target")

    def _add_workspace(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:

        workspace_id = param.get_string()
        if workspace_id:
            self.add_workspace(workspace_id)

    def add_workspace(
        self, workspace_id: str | None = None, switch: bool = True
    ) -> str:

        if workspace_id is None:
            workspace_id = app.settings.add_workspace(_("My Workspace"))

        self._workspace_side_bar.add_workspace(workspace_id)
        self._chat_page.add_chat_list(workspace_id)

        if self._startup_finished and switch:
            self.activate_workspace(workspace_id)
            self._workspace_side_bar.store_workspace_order()

        return workspace_id

    def _edit_workspace(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        workspace_id = param.get_string() or None
        if workspace_id is None:
            workspace_id = self.get_active_workspace()
        open_window("WorkspaceDialog", workspace_id=workspace_id)

    def _remove_workspace(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:

        workspace_id = param.get_string() or None
        if workspace_id is None:
            workspace_id = self.get_active_workspace()

        if workspace_id is not None:
            self.remove_workspace(workspace_id)

    def remove_workspace(self, workspace_id: str) -> None:
        if app.settings.get_workspace_count() == 1:
            log.warning("Tried to remove the only workspace")
            return

        was_active = self.get_active_workspace() == workspace_id
        chat_list = self.get_chat_list(workspace_id)
        open_chats = chat_list.get_open_chats()

        def _continue_removing_workspace():
            new_workspace_id = self._workspace_side_bar.get_other_workspace(
                workspace_id
            )
            if new_workspace_id is None:
                log.warning("No other workspaces found")
                return

            for open_chat in open_chats:
                params = ChatListEntryParam(
                    workspace_id=new_workspace_id,
                    source_workspace_id=workspace_id,
                    account=open_chat["account"],
                    jid=open_chat["jid"],
                )
                self.activate_action("move-chat-to-workspace", params.to_variant())

            if was_active:
                self.activate_workspace(new_workspace_id)

            self._workspace_side_bar.remove_workspace(workspace_id)
            self._chat_page.remove_chat_list(workspace_id)
            app.settings.remove_workspace(workspace_id)

        if open_chats:
            ConfirmationDialog(
                _("Remove Workspace?"),
                _(
                    "This workspace contains chats. All chats will be moved to "
                    "the next workspace. Remove anyway?"
                ),
                [
                    DialogButton.make("Cancel", text=_("_No")),
                    DialogButton.make("Remove", callback=_continue_removing_workspace),
                ],
            )
            return

        # No chats in chat list, it is save to remove this workspace
        _continue_removing_workspace()

    def _activate_workspace(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:

        workspace_id = param.get_string()
        if workspace_id:
            self.activate_workspace(workspace_id)

    def activate_workspace(self, workspace_id: str) -> None:
        self._activity_side_bar.unselect()
        self._account_side_bar.unselect()
        self._main_stack.show_chats(workspace_id)
        self._workspace_side_bar.activate_workspace(workspace_id)

        # Show chatlist if it is hidden
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            if not chat_list.is_visible():
                self._toggle_chat_list()

    def update_workspace(self, workspace_id: str) -> None:
        self._chat_page.update_workspace(workspace_id)
        self._workspace_side_bar.update_avatar(workspace_id)

    def get_chat_list(self, workspace_id: str) -> ChatList:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        return chat_list_stack.get_chatlist(workspace_id)

    def _get_suitable_workspace(
        self, account: str, jid: JID, private_chat: bool = False
    ) -> str:

        if private_chat:
            # Try to add private chat to the same workspace the MUC resides in
            chat_list_stack = self._chat_page.get_chat_list_stack()
            chat_list = chat_list_stack.find_chat(account, jid.new_as_bare())
            if chat_list is not None:
                return chat_list.workspace_id

        default = app.settings.get_account_setting(account, "default_workspace")
        workspaces = app.settings.get_workspaces()
        if default in workspaces:
            return default

        workspace_id = self.get_active_workspace()
        if workspace_id is not None:
            return workspace_id
        return self._workspace_side_bar.get_first_workspace()

    def _add_group_chat(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:

        account, jid, select = param.unpack()
        self.add_group_chat(account, JID.from_string(jid), select)

    def add_group_chat(self, account: str, jid: JID, select: bool = False) -> None:

        workspace_id = self._get_suitable_workspace(account, jid)
        self._chat_page.add_chat_for_workspace(
            workspace_id, account, jid, "groupchat", select=select
        )

    def _add_chat(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:

        params = AddChatActionParams.from_variant(param)
        self.add_chat(params.account, params.jid, params.type, params.select)

    def add_chat(
        self,
        account: str,
        jid: JID,
        type_: Literal["chat", "groupchat", "pm"],
        select: bool = False,
        message: str | None = None,
    ) -> None:

        workspace_id = self._get_suitable_workspace(account, jid)
        self._chat_page.add_chat_for_workspace(
            workspace_id, account, jid, type_, select=select, message=message
        )

    def add_private_chat(self, account: str, jid: JID, select: bool = False) -> None:

        workspace_id = self._get_suitable_workspace(account, jid, private_chat=True)
        self._chat_page.add_chat_for_workspace(
            workspace_id, account, jid, "pm", select=select
        )

    def clear_chat_list_row(self, account: str, jid: JID) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.find_chat(account, jid)
        if chat_list is not None:
            chat_list.clear_chat_list_row(account, jid)

    def select_chat(self, account: str, jid: JID) -> None:
        self._activity_side_bar.unselect()
        self._account_side_bar.unselect()
        self._main_stack.show_chat_page()
        self._chat_page.select_chat(account, jid)

    def select_next_chat(
        self, direction: Direction, unread_first: bool = False
    ) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            chat_list.select_next_chat(direction, unread_first)

    def select_chat_number(self, number: int) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            chat_list.select_chat_number(number)

    def show_activity_page(self, context_id: str | None = None) -> None:
        self._account_side_bar.unselect()
        self._workspace_side_bar.unselect_all()
        self._activity_side_bar.select()
        self._main_stack.show_activity_page(context_id)

    def get_control(self) -> ChatControl:
        return self._chat_page.get_control()

    def chat_exists(self, account: str, jid: JID) -> bool:
        return self._chat_page.chat_exists(account, jid)

    def is_message_correctable(
        self, contact: types.ChatContactT, message_id: str
    ) -> bool:

        chat_stack = self._chat_page.get_chat_stack()
        last_message_id = chat_stack.get_last_message_id(contact)
        if last_message_id is None or last_message_id != message_id:
            return False

        message_row = app.storage.archive.get_last_correctable_message(
            contact.account, contact.jid, last_message_id
        )
        return message_row is not None

    def get_total_unread_count(self) -> int:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        return chat_list_stack.get_total_unread_count()

    def get_chat_unread_count(
        self, account: str, jid: JID, include_silent: bool = False
    ) -> int:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        count = chat_list_stack.get_chat_unread_count(account, jid, include_silent)
        return count or 0

    def mark_as_read(
        self,
        account: str,
        jid: JID,
        *,
        is_sync: bool = False,
    ) -> None:

        unread_count = self.get_chat_unread_count(account, jid, include_silent=True)

        self.set_urgency_hint(False)
        control = self.get_control()
        if control.has_active_chat():
            # Reset jump to bottom button unread counter
            control.mark_as_read()

        # Reset chat list unread counter (emits unread-count-changed)
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list_stack.mark_as_read(account, jid)

        if not unread_count or is_sync:
            # Read marker must be sent only once
            return

        if not app.account_is_connected(account):
            return

        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact(jid)
        assert not isinstance(contact, ResourceContact)

        if not client.get_module("MAM").is_catch_up_finished(contact):
            # Dont set read state before we have all messages
            return

        last_message = app.storage.archive.get_last_conversation_row(account, jid)
        if last_message is None or last_message.id is None:
            return

        mds_assist_sent = client.get_module("ChatMarkers").send_displayed_marker(
            contact, last_message.id, last_message.stanza_id
        )

        if not mds_assist_sent and last_message.stanza_id is not None:
            by = contact.jid if isinstance(contact, GroupchatContact) else None
            client.get_module("MDS").set_mds(contact.jid, last_message.stanza_id, by)

    def _on_window_active(self, window: Gtk.ApplicationWindow, _param: Any) -> None:
        if not window.is_active():
            return

        self.set_urgency_hint(False)
        control = self.get_control()
        if not control.has_active_chat():
            return

        if control.view_is_at_bottom():
            self.mark_as_read(control.contact.account, control.contact.jid)

    def get_preferred_ft_method(self, contact: types.ChatContactT) -> str | None:

        httpupload_enabled = app.window.get_action_enabled("send-file-httpupload")
        return "httpupload" if httpupload_enabled else None
        # TODO Jingle FT
        # ft_pref = app.settings.get_account_setting(
        #     contact.account,
        #     'filetransfer_preference')

        # jingle_enabled = app.window.get_action_enabled('send-file-jingle')

        # if isinstance(contact, GroupchatContact):
        #     if httpupload_enabled:
        #         return 'httpupload'
        #     return None

        # if httpupload_enabled and jingle_enabled:
        #     return ft_pref

        # if httpupload_enabled:
        #     return 'httpupload'

        # if jingle_enabled:
        #     return 'jingle'

        # return None

    def show_add_join_groupchat(
        self,
        account: str,
        jid: str,
        nickname: str | None = None,
        password: str | None = None,
    ) -> None:

        jid_ = JID.from_string(jid)
        if not self.chat_exists(account, jid_):
            client = app.get_client(account)
            client.get_module("MUC").join(jid_, nick=nickname, password=password)

        self.add_group_chat(account, jid_, select=True)

    def start_chat_from_jid(
        self, account: str, jid: str, message: str | None = None
    ) -> None:

        jid_ = JID.from_string(jid)
        if self.chat_exists(account, jid_):
            self.select_chat(account, jid_)
            if message is not None:
                message_input = self.get_chat_stack().get_message_input()
                message_input.insert_text(message)
            return

        app.app.activate_action(
            "start-chat", GLib.Variant("as", [str(jid), message or ""])
        )

    def block_contact(self, account: str, jid: JID) -> None:
        client = app.get_client(account)

        contact = client.get_module("Contacts").get_contact(jid)
        assert isinstance(contact, BareContact)
        if contact.is_blocked:
            client.get_module("Blocking").unblock([contact.jid])
            return

        # TODO: Keep "confirm_block" setting?
        def _block_contact(report: BlockingReportValues | None = None) -> None:
            client.get_module("Blocking").block([contact.jid], report)
            self._chat_page.remove_chat(account, contact.jid)

        ConfirmationDialog(
            _("Block Contact?"),
            _(
                "You will appear offline for this contact and you "
                "will not receive further messages."
            ),
            [
                DialogButton.make("Cancel"),
                DialogButton.make(
                    "OK",
                    text=_("_Report Spam"),
                    callback=_block_contact,
                    kwargs={"report": "spam"},
                ),
                DialogButton.make("Remove", text=_("_Block"), callback=_block_contact),
            ],
        )

    def remove_contact(self, account: str, jid: JID) -> None:
        client = app.get_client(account)

        def _remove_contact():
            client.get_module("Roster").delete_item(jid)

        contact = client.get_module("Contacts").get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        sec_text = _(
            "You are about to remove %(name)s (%(jid)s) from your contact list."
        ) % {"name": contact.name, "jid": jid}

        ConfirmationDialog(
            _("Remove From Contact List?"),
            sec_text,
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Remove", callback=_remove_contact),
            ],
        )

    @staticmethod
    def _check_for_account() -> None:
        accounts = app.settings.get_accounts()
        if not accounts:

            def _open_wizard():
                open_window("AccountWizard")

            GLib.idle_add(_open_wizard)

    def _load_chats(self) -> None:
        for workspace_id in app.settings.get_workspaces():
            self.add_workspace(workspace_id)
            self._chat_page.load_workspace_chats(workspace_id)

        workspace_id = self._workspace_side_bar.get_first_workspace()
        self.activate_workspace(workspace_id)

        self._set_startup_finished()

    def _on_message_received(self, event: events.MessageReceived) -> None:
        if self.chat_exists(event.account, event.jid):
            return

        if event.m_type == MessageType.PM:
            self.add_private_chat(event.account, event.jid)

        else:
            self.add_chat(event.account, event.jid, "chat")

    def _on_read_state_sync(self, event: events.ReadStateSync) -> None:
        last_message = app.storage.archive.get_last_conversation_row(
            event.account, event.jid
        )

        if last_message is None:
            return

        if event.marker_id not in (last_message.id, last_message.stanza_id):
            return

        self.mark_as_read(event.account, event.jid, is_sync=True)

    def _on_call_started(self, event: events.CallStarted) -> None:
        # Make sure there is only one window
        win = get_app_window("CallWindow")
        if win is not None:
            win.close()
        open_window(
            "CallWindow", account=event.account, resource_jid=event.resource_jid
        )

    def _on_jingle_request(self, event: events.JingleRequestReceived) -> None:
        if not self.chat_exists(event.account, event.jid):
            for item in event.contents:
                if item.media not in ("audio", "video"):
                    return
                self.add_chat(event.account, event.jid, "chat")
                break

    def _on_file_request(self, event: events.FileRequestReceivedEvent) -> None:
        if not self.chat_exists(event.account, event.jid):
            self.add_chat(event.account, event.jid, "chat")

    def quit(self) -> None:
        if self.is_visible():
            window_width, window_height = self.get_width(), self.get_height()
            app.settings.set("mainwin_width", window_width)
            app.settings.set("mainwin_height", window_height)

        app.settings.save()
        app.app.start_shutdown()
