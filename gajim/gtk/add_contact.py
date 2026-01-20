# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload
from typing import TypedDict

import logging

from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp import Namespace
from nbxmpp.errors import BaseError
from nbxmpp.errors import is_error
from nbxmpp.errors import StanzaError
from nbxmpp.structs import DiscoInfo

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.util import as_task
from gajim.common.util.jid import validate_jid
from gajim.common.util.user_strings import get_subscription_request_msg

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import AssistantErrorPage
from gajim.gtk.assistant import AssistantPage
from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.util.window import open_window

log = logging.getLogger("gajim.gtk.add_contact")


class SubscriptionData(TypedDict):
    message: str
    groups: list[str]
    auto_auth: bool


class AddContact(Assistant):
    def __init__(
        self,
        account: str | None = None,
        jid: JID | None = None,
        nick: str | None = None,
    ):
        Assistant.__init__(self)
        self.account = account
        self.jid = jid
        self._nick = nick

        self._result: DiscoInfo | BaseError | StanzaError | None = None

        self.add_button("next", _("Next"), complete=True, css_class="suggested-action")
        self.add_button("back", _("Back"))
        self.add_button("add", _("Add Contact"), css_class="suggested-action")
        self.add_button("join", _("Join…"), css_class="suggested-action")

        self.add_pages(
            {
                "address": AddContactAddressPage(account, jid),
                "error": AddContactErrorPage(),
                "contact": AddContactContactPage(),
                "groupchat": AddContactGroupChatPage(),
                "gateway": AddContactGatewayPage(),
            }
        )

        progress = self.add_default_page("progress")
        progress.set_title(_("Gathering information…"))
        progress.set_text(_("Trying to gather information on this address…"))

        self._connect(self, "button-clicked", self._on_button_clicked)
        self.show_first_page()

    @overload
    def get_page(self, name: Literal["address"]) -> AddContactAddressPage: ...

    @overload
    def get_page(self, name: Literal["error"]) -> AddContactErrorPage: ...

    @overload
    def get_page(self, name: Literal["contact"]) -> AddContactContactPage: ...

    @overload
    def get_page(self, name: Literal["groupchat"]) -> AddContactGroupChatPage: ...

    @overload
    def get_page(self, name: Literal["gateway"]) -> AddContactGatewayPage: ...

    def get_page(self, name: str) -> AssistantPage:
        return self._pages[name]

    def _on_button_clicked(self, _assistant: Assistant, button_name: str) -> None:
        page = self.get_current_page()
        address_page = self.get_page("address")
        account, _ = address_page.get_account_and_jid()

        if button_name == "next":
            self._start_disco()
            return

        if button_name == "back":
            self.show_page("address", Gtk.StackTransitionType.SLIDE_RIGHT)
            address_page.focus()
            return

        if button_name == "add":
            assert isinstance(self._result, DiscoInfo | StanzaError)
            assert isinstance(self._result.jid, JID)
            client = app.get_client(account)

            if page == "contact":
                contact_page = self.get_page("contact")
                data = contact_page.get_subscription_data()
                client.get_module("Presence").subscribe(
                    self._result.jid,
                    msg=data["message"],
                    groups=data["groups"],
                    auto_auth=data["auto_auth"],
                    name=self._nick,
                )

            elif page == "gateway":
                assert isinstance(self._result, DiscoInfo)
                client.get_module("Presence").subscribe(
                    self._result.jid, name=self._result.gateway_name, auto_auth=True
                )

            else:
                raise ValueError("No handler for page: %s" % page)

            app.window.add_chat(account, self._result.jid, "chat", select=True)
            self.close()
            return

        if button_name == "join":
            _, jid = address_page.get_account_and_jid()
            open_window("GroupchatJoin", account=account, jid=jid)
            self.close()

    def _start_disco(self) -> None:
        self._result = None
        self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)

        address_page = self.get_page("address")
        account, jid = address_page.get_account_and_jid()
        assert account is not None
        self._disco_info(account, jid)

    @as_task
    def _disco_info(self, account: str, address: str) -> Any:
        _task = yield  # noqa: F841, # pyright: ignore

        client = app.get_client(account)

        result = yield client.get_module("Discovery").disco_info(address, timeout=10)  # pyright: ignore
        if is_error(result):
            assert isinstance(result, BaseError)
            self._process_error(account, result)
            raise result

        log.info("Disco Info received: %s", address)
        assert isinstance(result, DiscoInfo)
        self._process_info(account, result)

    def _process_error(self, account: str, result: BaseError | StanzaError) -> None:
        log.debug("Error received: %s", result)
        self._result = result

        contact_conditions = [
            "service-unavailable",  # Prosody
            "subscription-required",  # ejabberd
        ]
        if isinstance(result, StanzaError) and result.condition in contact_conditions:
            # It seems to be a contact
            address_page = self.get_page("contact")
            address_page.prepare(account, result)
            self.show_page("contact", Gtk.StackTransitionType.SLIDE_LEFT)
        else:
            # TimeoutStanzaError is handled here
            error_page = self.get_page("error")
            error_page.set_text(result.get_text())
            self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)

    def _process_info(self, account: str, result: DiscoInfo) -> None:
        log.debug("Info received: %s", result)
        self._result = result

        if result.is_gateway:
            gateway_page = self.get_page("gateway")
            gateway_page.prepare(account, result)
            self.show_page("gateway", Gtk.StackTransitionType.SLIDE_LEFT)
            return

        if result.is_muc:
            for identity in result.identities:
                assert result.jid is not None
                if identity.type == "text" and result.jid.is_domain:
                    # It's a group chat component advertising
                    # category 'conference'
                    error_page = self.get_page("error")
                    error_page.set_text(
                        _("This address does not seem to offer any gateway service.")
                    )
                    self.show_page("error")
                    return

                if identity.type == "irc" and result.jid.is_domain:
                    # It's an IRC gateway advertising category 'conference'
                    gateway_page = self.get_page("gateway")
                    gateway_page.prepare(account, result)
                    self.show_page("gateway", Gtk.StackTransitionType.SLIDE_LEFT)
                    return

            groupchat_page = self.get_page("groupchat")
            groupchat_page.prepare(account, result)
            self.show_page("groupchat", Gtk.StackTransitionType.SLIDE_LEFT)
            return

        contact_page = self.get_page("contact")
        contact_page.prepare(account, result)
        self.show_page("contact", Gtk.StackTransitionType.SLIDE_LEFT)


@Gtk.Template(string=get_ui_string("add_contact/address_page.ui"))
class AddContactAddressPage(AssistantPage):
    __gtype_name__ = "AddContactAddressPage"

    _account_box: Gtk.Box = Gtk.Template.Child()
    _dropdown: GajimDropDown[str] = Gtk.Template.Child()
    _address_entry: Gtk.Entry = Gtk.Template.Child()

    def __init__(self, account: str | None, jid: JID | None) -> None:
        AssistantPage.__init__(self)
        self.title = _("Add Contact")

        self._account = account
        self._jid = jid

        self._connect(self._dropdown, "notify::selected", self._on_account_selected)
        self._connect(self._address_entry, "changed", self._set_complete)

        accounts = app.get_enabled_accounts_with_labels(connected_only=True)
        self._dropdown.set_data(dict(accounts))

        self._account_box.set_visible(len(accounts) > 1)

        if account is not None:
            self._dropdown.select_key(account)

        if jid is not None:
            self._address_entry.set_text(str(jid))

        self._set_complete()

    def get_visible_buttons(self) -> list[str]:
        return ["next"]

    def get_default_button(self) -> str:
        return "next"

    def get_account_and_jid(self) -> tuple[str, str]:
        assert self._account is not None
        return self._account, self._address_entry.get_text()

    def focus(self) -> None:
        self._address_entry.grab_focus()

    def _on_account_selected(
        self, dropdown: GajimDropDown[str], _param: GObject.ParamSpec
    ) -> None:
        account = dropdown.get_selected_key()
        self._account = account
        self._set_complete()

    def _show_icon(self, show: bool) -> None:
        icon = "lucide-circle-alert-symbolic" if show else None
        self._address_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon
        )

    def _set_complete(self, *args: Any) -> None:
        if self._account is None:
            self.complete = False
            self.update_page_complete()
            return

        address = self._address_entry.get_text()
        is_self = bool(address == app.get_jid_from_account(self._account))
        if is_self:
            self._show_icon(True)
            self._address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY,
                _("You cannot add yourself to your contact list."),
            )
            self.complete = False
            self.update_page_complete()
            return

        client = app.get_client(self._account)
        for contact in client.get_module("Roster").iter_contacts():
            if address == str(contact.jid):
                self._show_icon(True)
                self._address_entry.set_icon_tooltip_text(
                    Gtk.EntryIconPosition.SECONDARY,
                    _("%s is already in your contact list") % address,
                )
                self.complete = False
                self.update_page_complete()
                return

        self.complete = self._validate_address(address)
        self.update_page_complete()

    def _validate_address(self, address: str) -> bool:
        if not address:
            self._show_icon(False)
            return False

        try:
            jid = validate_jid(address)
            if jid.resource:
                raise ValueError
        except ValueError:
            self._show_icon(True)
            self._address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _("Invalid Address")
            )
            return False

        if jid.localpart is None:
            self._show_icon(True)
            self._address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY,
                _("'@' is missing in address. Are you sure this is correct?"),
            )
            return True

        self._show_icon(False)
        return True


class AddContactErrorPage(AssistantErrorPage):
    def __init__(self) -> None:
        AssistantErrorPage.__init__(self)
        self.set_title(_("Add Contact"))
        self.set_heading(_("An Error Occurred"))

    def get_visible_buttons(self) -> list[str]:
        return ["back"]

    def get_default_button(self) -> str:
        return "back"


@Gtk.Template(string=get_ui_string("add_contact/contact_page.ui"))
class AddContactContactPage(AssistantPage):
    __gtype_name__ = "AddContactContactPage"

    _contact_grid: Gtk.Grid = Gtk.Template.Child()
    _status_switch: Gtk.Switch = Gtk.Template.Child()
    _group_combo: Gtk.ComboBoxText = Gtk.Template.Child()
    _message_entry: Gtk.Entry = Gtk.Template.Child()
    _contact_info_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Add Contact")

        self._result: DiscoInfo | BaseError | None = None
        self._account: str | None = None
        self._contact: types.BareContact | None = None

        entry = self._group_combo.get_child()
        assert isinstance(entry, Gtk.Entry)
        entry.set_activates_default(True)
        entry.set_placeholder_text(_("Choose a group…"))

        self._connect(self._contact_info_button, "clicked", self._on_info_clicked)

    def get_visible_buttons(self) -> list[str]:
        return ["back", "add"]

    def get_default_button(self) -> str:
        return "add"

    def prepare(self, account: str, result: DiscoInfo | StanzaError):
        self._result = result
        self._account = account

        client = app.get_client(account)
        assert result.jid is not None
        contact = client.get_module("Contacts").get_contact(result.jid)
        assert isinstance(contact, BareContact)
        self._contact = contact

        self._update_groups(account)
        self._message_entry.set_text(get_subscription_request_msg(account))
        self._contact_grid.set_sensitive(True)

    def _update_groups(self, account: str) -> None:
        model = self._group_combo.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.clear()
        client = app.get_client(account)
        for group in client.get_module("Roster").get_groups():
            self._group_combo.append_text(group)

    def _on_info_clicked(self, _button: Gtk.Button) -> None:
        open_window("ContactInfo", account=self._account, contact=self._contact)

    def get_subscription_data(self) -> SubscriptionData:
        entry = self._group_combo.get_child()
        assert isinstance(entry, Gtk.Entry)
        group = entry.get_text()
        groups = [group] if group else []
        return {
            "message": self._message_entry.get_text(),
            "groups": groups,
            "auto_auth": self._status_switch.get_active(),
        }


@Gtk.Template(string=get_ui_string("add_contact/gateway_page.ui"))
class AddContactGatewayPage(AssistantPage):
    __gtype_name__ = "AddContactGatewayPage"

    _gateway_image: Gtk.Image = Gtk.Template.Child()
    _gateway_label: Gtk.Label = Gtk.Template.Child()
    _register_button: Gtk.Button = Gtk.Template.Child()
    _commands_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Service Gateway")

        self._account: str | None = None
        self._result: DiscoInfo | None = None

        self._connect(self._register_button, "clicked", self._on_register_clicked)
        self._connect(self._commands_button, "clicked", self._on_command_clicked)

    def get_visible_buttons(self) -> list[str]:
        return ["back", "add"]

    def get_default_button(self) -> str:
        return "add"

    def prepare(self, account: str, result: DiscoInfo) -> None:
        self._account = account
        self._result = result

        icon_name = None
        if result.is_gateway:
            if result.gateway_type == "sms":
                icon_name = "gajim-agent-sms"
            if result.gateway_type == "irc":
                icon_name = "gajim-agent-irc"
            self._gateway_image.set_from_icon_name(icon_name)
            gateway_name = result.gateway_name or str(self._result.jid)
            if not result.gateway_type:
                self._gateway_label.set_text(gateway_name)
            else:
                self._gateway_label.set_text(
                    f"{gateway_name} ({result.gateway_type.upper()})"
                )
        else:
            identity_name = ""
            identity_type = ""
            for identity in result.identities:
                if identity.type == "sms":
                    icon_name = "gajim-agent-sms"
                    identity_name = identity.name or str(self._result.jid)
                    identity_type = identity.type
                if identity.type == "irc":
                    icon_name = "gajim-agent-irc"
                    identity_name = identity.name or str(self._result.jid)
                    identity_type = identity.type
            self._gateway_image.set_from_icon_name(icon_name)
            if not identity_type:
                self._gateway_label.set_text(identity_name)
            else:
                self._gateway_label.set_text(
                    f"{identity_name} ({identity_type.upper()})"
                )

        if result.supports(Namespace.REGISTER):
            self._register_button.set_sensitive(True)
            self._register_button.set_tooltip_text("")
        else:
            self._register_button.set_sensitive(False)
            self._register_button.set_tooltip_text(
                _("This gateway does not support direct registering.")
            )

        if result.supports(Namespace.COMMANDS):
            self._commands_button.set_sensitive(True)
            self._commands_button.set_tooltip_text("")
        else:
            self._commands_button.set_sensitive(False)
            self._commands_button.set_tooltip_text(
                _("This gateway does not support Ad-Hoc Commands.")
            )

    def _on_register_clicked(self, _button: Gtk.Button) -> None:
        assert self._result is not None
        open_window(
            "ServiceRegistration", account=self._account, address=self._result.jid
        )

    def _on_command_clicked(self, _button: Gtk.Button) -> None:
        assert self._result is not None
        open_window(
            "AdHocCommands", account=self._account, jids=[str(self._result.jid)]
        )


class AddContactGroupChatPage(AssistantPage):
    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Join Group Chat?")

        self._result: DiscoInfo | None = None

        heading = Gtk.Label(
            label=_("Join Group Chat?"),
            wrap=True,
            max_width_chars=30,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
        )
        heading.add_css_class("title-1")
        self.append(heading)

        self._info_box = GroupChatInfoScrolled(minimal=True)
        self.append(self._info_box)

    def get_visible_buttons(self) -> list[str]:
        return ["back", "join"]

    def get_default_button(self) -> str:
        return "join"

    def prepare(self, account: str, result: DiscoInfo) -> None:
        self._result = result

        self._info_box.set_account(account)
        self._info_box.set_from_disco_info(result)
