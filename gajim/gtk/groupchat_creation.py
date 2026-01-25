# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging

from gi.repository import Adw
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common.const import MUC_DISCO_ERRORS
from gajim.common.events import AccountConnected
from gajim.common.events import AccountDisconnected
from gajim.common.ged import EventHelper
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.util.jid import validate_jid
from gajim.common.util.muc import get_random_muc_localpart

from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.util.misc import ensure_not_destroyed
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.window import GajimAppWindow

log = logging.getLogger("gajim.gtk.groupchat_creation")


@Gtk.Template(string=get_ui_string("groupchat_creation.ui"))
class CreateGroupchatWindow(GajimAppWindow, EventHelper):
    __gtype_name__ = "CreateGroupchatWindow"

    _stack: Gtk.Stack = Gtk.Template.Child()

    _account_group: Adw.PreferencesGroup = Gtk.Template.Child()
    _account_dropdown: GajimDropDown[str] = Gtk.Template.Child()

    _settings_listbox: Gtk.ListBox = Gtk.Template.Child()
    _name_entry_row: Adw.EntryRow = Gtk.Template.Child()
    _description_entry_row: Adw.EntryRow = Gtk.Template.Child()
    _advanced_expander_row: Adw.ExpanderRow = Gtk.Template.Child()
    _public_radio: Gtk.CheckButton = Gtk.Template.Child()
    _private_radio: Gtk.CheckButton = Gtk.Template.Child()
    _address_entry_row: Adw.EntryRow = Gtk.Template.Child()

    _error_label: Gtk.Label = Gtk.Template.Child()
    _info_label: Gtk.Label = Gtk.Template.Child()

    _spinner: Adw.Spinner = Gtk.Template.Child()
    _create_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, account: str | None) -> None:
        GajimAppWindow.__init__(
            self,
            name="CreateGroupchat",
            title=_("Create Group Chat"),
            default_width=500,
            default_height=550,
        )
        EventHelper.__init__(self)

        self._connect(
            self._account_dropdown,
            "notify::selected",
            self._on_account_changed,
        )

        self._connect(
            self._address_entry_row, "changed", self._on_address_entry_changed
        )
        self._connect(self._create_button, "clicked", self._on_create_clicked)

        self._account = account
        self._destroyed: bool = False

        self.register_events(
            [
                ("account-connected", ged.GUI2, self._on_account_state),
                ("account-disconnected", ged.GUI2, self._on_account_state),
            ]
        )

        if app.get_number_of_connected_accounts() == 0:
            # This can happen under rare circumstances
            self._stack.set_visible_child_name("no-connection")
            self._create_button.set_sensitive(False)
            return

        self._update_accounts(account)
        self._create_button.grab_focus()

    def _cleanup(self) -> None:
        # https://gitlab.gnome.org/GNOME/gtk/-/issues/7992
        self._name_entry_row.props.enable_emoji_completion = False
        self._description_entry_row.props.enable_emoji_completion = False

        self.unregister_events()
        self._destroyed = True

    def _on_account_state(self, _event: AccountConnected | AccountDisconnected) -> None:
        any_account_connected = app.get_number_of_connected_accounts() > 0
        if any_account_connected:
            self._stack.set_visible_child_name("create")
            self._create_button.set_sensitive(True)
        else:
            self._stack.set_visible_child_name("no-connection")
            self._create_button.set_sensitive(False)

        selected_account = self._account_dropdown.get_selected_key()
        self._update_accounts(selected_account)

    def _update_accounts(self, account: str | None = None) -> None:
        accounts = app.get_enabled_accounts_with_labels(connected_only=True)

        account_data = dict(accounts)
        self._account_dropdown.set_data(account_data)

        self._account_group.set_visible(len(accounts) != 1)

        if account is not None and self._account_dropdown.has_key(account):
            self._account_dropdown.select_key(account)
        else:
            self._account_dropdown.select_first()

    def _has_muc_service(self, account: str) -> bool:
        client = app.get_client(account)
        return client.get_module("MUC").service_jid is not None

    def _get_muc_service_jid(self) -> str:
        assert self._account is not None
        client = app.get_client(self._account)
        service_jid = client.get_module("MUC").service_jid
        if service_jid is None:
            return "muc.example.org"
        return str(service_jid)

    def _on_account_changed(
        self, dropdown: GajimDropDown[str], _param: GObject.ParamSpec
    ) -> None:
        self._account = dropdown.get_selected_key()
        log.debug("Set current account to: %s", self._account)
        if self._account is None:
            # Happens when we update the dropdown entries after an account
            # changes its state.
            return

        self._unset_error()
        self._unset_info()

        has_muc_service = self._has_muc_service(self._account)
        if has_muc_service:
            server = self._get_muc_service_jid()
            room_jid = f"{get_random_muc_localpart()}@{server}"
            self._address_entry_row.set_text(room_jid)
        else:
            self._address_entry_row.set_text("")

        if not has_muc_service:
            self._set_info(
                _(
                    "Your server does not offer a group chat service. "
                    "Please specify the address of a different server."
                )
            )

    def _is_jid_valid(self, text: str) -> bool:
        if not text:
            return True

        try:
            jid = validate_jid(text)
            if jid.resource:
                raise ValueError

        except ValueError:
            return False

        return True

    def _set_processing_state(self, enabled: bool) -> None:
        self._spinner.set_visible(enabled)
        self._account_group.set_sensitive(not enabled)
        self._settings_listbox.set_sensitive(not enabled)
        self._create_button.set_sensitive(not enabled)

    def _unset_info(self) -> None:
        self._info_label.set_visible(False)

    def _set_info(self, text: str) -> None:
        self._info_label.set_text(text)
        self._info_label.set_visible(True)

    def _unset_error(self) -> None:
        self._error_label.set_visible(False)
        self._create_button.set_sensitive(True)

    def _set_error(self, text: str) -> None:
        self._error_label.set_text(text)
        self._error_label.set_visible(True)
        self._create_button.set_sensitive(False)

    def _set_error_from_error(self, error: StanzaError) -> None:
        condition = error.condition or ""
        if condition == "gone":
            condition = "already-exists"
        text = MUC_DISCO_ERRORS.get(condition, to_user_string(error))
        self._set_error(text)

    def _set_error_from_error_code(self, error_code: str) -> None:
        self._set_error(MUC_DISCO_ERRORS[error_code])

    def _on_address_entry_changed(self, entry: Gtk.Entry) -> None:
        self._unset_error()

    def _on_create_clicked(self, _button: Gtk.Button) -> None:
        if self._account is None or not app.account_is_available(self._account):
            InformationAlertDialog(
                _("You are offline"),
                _("You have to be connected to create a group chat."),
            )
            return

        room_jid = self._address_entry_row.get_text()
        if not room_jid:
            room_jid = f"{get_random_muc_localpart()}@{self._get_muc_service_jid()}"

        if not self._is_jid_valid(room_jid):
            self._set_error(_("Invalid Address"))
            return

        self._set_processing_state(True)
        client = app.get_client(self._account)
        client.get_module("Discovery").disco_info(
            room_jid, callback=self._disco_info_received
        )

    @ensure_not_destroyed
    def _disco_info_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            if error.condition == "item-not-found":
                assert error.jid is not None
                self._create_muc(error.jid)
                return
            self._set_error_from_error(error)

        else:
            self._set_error_from_error_code(
                "already-exists" if result.is_muc else "not-muc-service"
            )

        self._set_processing_state(False)

    def _create_muc(self, room_jid: str) -> None:
        name = self._name_entry_row.get_text()
        description = self._description_entry_row.get_text()
        is_public = self._public_radio.get_active()

        config = {
            # XEP-0045 options
            "muc#roomconfig_roomname": name,
            "muc#roomconfig_roomdesc": description,
            "muc#roomconfig_publicroom": is_public,
            "muc#roomconfig_membersonly": not is_public,
            "muc#roomconfig_whois": "moderators" if is_public else "anyone",
            "muc#roomconfig_changesubject": not is_public,
            # Ejabberd options
            "public_list": is_public,
        }

        # Create new group chat by joining
        assert self._account is not None

        jid = JID.from_string(room_jid)
        if app.window.chat_exists(self._account, jid):
            log.error("Trying to create groupchat which is already added as chat")
            self.close()
            return

        client = app.get_client(self._account)
        client.get_module("MUC").create(jid, config)

        self.close()
