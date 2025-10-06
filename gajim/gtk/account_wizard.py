# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import overload

import json
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.client import Client as NBXMPPClient
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.const import Mode
from nbxmpp.const import StreamError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import RegisterStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.http import HTTPRequest
from nbxmpp.protocol import JID
from nbxmpp.protocol import validate_domainpart
from nbxmpp.structs import ProxyData
from nbxmpp.structs import RegisterData
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import GIO_TLS_ERRORS
from gajim.common.const import SASL_ERRORS
from gajim.common.events import StanzaReceived
from gajim.common.events import StanzaSent
from gajim.common.file_transfer_manager import FileTransfer
from gajim.common.helpers import get_global_proxy
from gajim.common.helpers import get_proxy
from gajim.common.i18n import _
from gajim.common.multiprocess.http import DownloadResult
from gajim.common.util.http import create_http_session
from gajim.common.util.jid import validate_jid
from gajim.common.util.text import get_country_flag_from_code

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.assistant import ProgressPage
from gajim.gtk.assistant import SuccessPage
from gajim.gtk.builder import get_builder
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util.misc import clear_listbox
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import open_uri
from gajim.gtk.util.styling import get_color_for_account
from gajim.gtk.util.window import get_app_window
from gajim.gtk.util.window import open_window

CustomHostT = tuple[str, ConnectionProtocol, ConnectionType]

log = logging.getLogger("gajim.gtk.account_wizard")


class AccountWizard(Assistant):
    def __init__(self) -> None:
        Assistant.__init__(self, name="AccountWizard", height=500)
        self._client: NBXMPPClient | None = None
        self._method: Literal["login"] | Literal["signup"] = "login"
        self._destroyed: bool = False

        self.add_button("back", _("Back"))
        self.add_button(
            "signup", _("Sign Up"), complete=True, css_class="suggested-action"
        )
        self.add_button("connect", _("Connect"), css_class="suggested-action")
        self.add_button("next", _("Next"), css_class="suggested-action")
        self.add_button(
            "login", _("Log In"), complete=True, css_class="suggested-action"
        )

        self.add_pages(
            {
                "login": Login(),
                "signup": Signup(),
                "advanced": AdvancedSettings(),
                "security-warning": SecurityWarning(),
                "form": Form(),
                "redirect": Redirect(),
                "success": Success(),
                "error": Error(),
            }
        )

        self.add_default_page("progress")

        login_page = self.get_page("login")
        self._connect(login_page, "clicked", self._on_button_clicked)
        self._connect(self, "button-clicked", self._on_assistant_button_clicked)
        self._connect(self, "page-changed", self._on_page_changed)

        self.update_proxy_list()

    @overload
    def get_page(self, name: Literal["login"]) -> Login: ...

    @overload
    def get_page(self, name: Literal["signup"]) -> Signup: ...

    @overload
    def get_page(self, name: Literal["advanced"]) -> AdvancedSettings: ...

    @overload
    def get_page(self, name: Literal["security-warning"]) -> SecurityWarning: ...

    @overload
    def get_page(self, name: Literal["form"]) -> Form: ...

    @overload
    def get_page(self, name: Literal["redirect"]) -> Redirect: ...

    @overload
    def get_page(self, name: Literal["success"]) -> Success: ...

    @overload
    def get_page(self, name: Literal["error"]) -> Error: ...

    @overload
    def get_page(self, name: Literal["progress"]) -> ProgressPage: ...

    def get_page(self, name: str) -> Page:
        return self._pages[name]

    def get_current_method(self) -> Literal["login"] | Literal["signup"]:
        return self._method

    def _on_button_clicked(self, _page: Gtk.Widget, button_name: str) -> None:
        if button_name == "login":
            if self.get_page("login").is_advanced():
                self.show_page("advanced", Gtk.StackTransitionType.SLIDE_LEFT)
            else:
                self._test_credentials()

        elif button_name == "signup":
            self.get_page("signup").update_providers_list()
            self.show_page("signup", Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_assistant_button_clicked(
        self, _assistant: Assistant, button_name: str
    ) -> None:
        page = self.get_current_page()

        if button_name == "login":
            if page == "advanced":
                self._test_credentials()

            elif page == "security-warning":
                if self.get_page("security-warning").trust_certificate:
                    cert = self.get_page("security-warning").cert
                    assert cert is not None
                    app.cert_store.add_certificate(cert)
                self._test_credentials(ignore_all_errors=True)

        elif button_name == "signup":

            if self.get_page("signup").is_anonymous():
                domain = self.get_page("signup").get_server()

                if app.settings.account_exists(f"anon@{domain}"):
                    self._show_error_page(
                        _("Account exists already"),
                        _("Account exists already"),
                        _("This account has already been added"),
                    )
                    return

            if page == "signup":
                if self.get_page("signup").is_advanced():
                    self.show_page("advanced", Gtk.StackTransitionType.SLIDE_LEFT)

                elif self.get_page("signup").is_anonymous():
                    self._test_anonymous_server()

                else:
                    self._register_with_server()

            elif page == "advanced":
                if self.get_page("signup").is_anonymous():
                    self._test_anonymous_server()
                else:
                    self._register_with_server()

            elif page == "security-warning":
                if self.get_page("security-warning").trust_certificate:
                    cert = self.get_page("security-warning").cert
                    assert cert is not None
                    app.cert_store.add_certificate(cert)

                if self.get_page("signup").is_anonymous():
                    self._test_anonymous_server(ignore_all_errors=True)

                else:
                    self._register_with_server(ignore_all_errors=True)

            elif page == "form":
                self._show_progress_page(
                    _("Creating Account..."), _("Trying to create account...")
                )
                self._submit_form()

        elif button_name == "connect":
            if page == "success":
                account = self.get_page("success").account
                assert account is not None
                app.app.enable_account(account)
                self.close()

        elif button_name == "back":
            if page == "signup":
                self.show_page("login", Gtk.StackTransitionType.SLIDE_RIGHT)

            elif page in ("advanced", "error", "security-warning"):
                if (
                    page == "error"
                    and self._method == "signup"
                    and self.get_page("form").has_form
                ):
                    self.show_page("form", Gtk.StackTransitionType.SLIDE_RIGHT)
                else:
                    self.show_page(self._method, Gtk.StackTransitionType.SLIDE_RIGHT)

            elif page == "form":
                self.show_page("signup", Gtk.StackTransitionType.SLIDE_RIGHT)
                self.get_page("form").remove_form()
                self._disconnect()

            elif page == "redirect":
                self.show_page("login", Gtk.StackTransitionType.SLIDE_RIGHT)

    def _on_page_changed(self, _assistant: Assistant, page_name: str) -> None:
        if page_name == "signup":
            self._method = page_name
            self.get_page("signup").focus()

        elif page_name == "login":
            self._method = page_name
            self.get_page("login").focus()

        elif page_name == "form":
            self.get_page("form").focus()

    def update_proxy_list(self) -> None:
        self.get_page("advanced").update_proxy_list()

    def _get_proxy_data(self, advanced: bool) -> ProxyData | None:
        if advanced:
            proxy_name = self.get_page("advanced").get_proxy()
            proxy_data = get_proxy(proxy_name)
            if proxy_data is not None:
                return proxy_data

        return get_global_proxy()

    def _get_base_client(
        self, address: JID, mode: Mode, advanced: bool, ignore_all_errors: bool
    ) -> NBXMPPClient:

        client = NBXMPPClient(log_context="Account Wizard")
        client.set_domain(address.domain)
        client.set_username(address.localpart)
        client.set_mode(mode)
        client.set_ignore_tls_errors(ignore_all_errors)
        client.set_accepted_certificates(app.cert_store.get_certificates())

        if advanced:
            custom_host = self.get_page("advanced").get_custom_host()
            if custom_host is not None:
                client.set_custom_host(*custom_host)

        proxy_data = self._get_proxy_data(advanced)
        client.set_proxy(proxy_data)
        client.set_http_session(create_http_session(proxy=proxy_data))
        client.subscribe("disconnected", self._on_disconnected)
        client.subscribe("connection-failed", self._on_connection_failed)
        client.subscribe("stanza-sent", self._on_stanza_sent)
        client.subscribe("stanza-received", self._on_stanza_received)
        return client

    def _disconnect(self) -> None:
        if self._client is None:
            return
        self._client.remove_subscriptions()
        self._client.disconnect()
        self._client = None

    @staticmethod
    def _on_stanza_sent(_client: NBXMPPClient, _signal_name: str, stanza: Any) -> None:
        app.ged.raise_event(StanzaSent(account="AccountWizard", stanza=stanza))

    @staticmethod
    def _on_stanza_received(
        _client: NBXMPPClient, _signal_name: str, stanza: Any
    ) -> None:
        app.ged.raise_event(StanzaReceived(account="AccountWizard", stanza=stanza))

    def _test_credentials(self, ignore_all_errors: bool = False) -> None:
        self._show_progress_page(_("Connecting..."), _("Connecting to server..."))
        jid, password = self.get_page("login").get_credentials()
        address = JID.from_string(jid)
        advanced = self.get_page("login").is_advanced()

        self._client = self._get_base_client(
            address, Mode.LOGIN_TEST, advanced, ignore_all_errors
        )

        self._client.set_password(password)
        self._client.subscribe("login-successful", self._on_login_successful)

        self._client.connect()

    def _test_anonymous_server(self, ignore_all_errors: bool = False) -> None:
        self._show_progress_page(_("Connecting..."), _("Connecting to server..."))
        domain = self.get_page("signup").get_server()
        advanced = self.get_page("signup").is_advanced()

        address = JID(localpart=None, domain=domain, resource=None)

        self._client = self._get_base_client(
            address, Mode.ANONYMOUS_TEST, advanced, ignore_all_errors
        )

        self._client.subscribe("anonymous-supported", self._on_anonymous_supported)
        self._client.connect()

    def _register_with_server(self, ignore_all_errors: bool = False) -> None:
        self._show_progress_page(_("Connecting..."), _("Connecting to server..."))
        domain = self.get_page("signup").get_server()
        advanced = self.get_page("signup").is_advanced()

        address = JID(localpart=None, domain=domain, resource=None)

        self._client = self._get_base_client(
            address, Mode.REGISTER, advanced, ignore_all_errors
        )

        self._client.subscribe("connected", self._on_connected)

        self._client.connect()

    def _on_login_successful(self, client: NBXMPPClient, _signal_name: str) -> None:
        account = self._generate_account_name(client.domain)
        proxy_name = None
        if client.proxy is not None:
            proxy_name = self.get_page("advanced").get_proxy()

        address = JID(localpart=client.username, domain=client.domain, resource=None)

        app.app.create_account(
            account, address, client.password, proxy_name, client.custom_host
        )
        self.get_page("success").set_account(account)
        self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)
        self._disconnect()

    def _on_connected(self, client: NBXMPPClient, _signal_name: str) -> None:
        client.get_module("Register").request_register_form(
            callback=self._on_register_form
        )

    def _on_anonymous_supported(self, client: NBXMPPClient, _signal_name: str) -> None:
        account = self._generate_account_name(client.domain)
        proxy_name = None
        if client.proxy is not None:
            proxy_name = self.get_page("advanced").get_proxy()

        address = JID(localpart=None, domain=client.domain, resource=None)

        app.app.create_account(
            account,
            address,
            client.password,
            proxy_name,
            client.custom_host,
            anonymous=True,
        )

        self.get_page("success").set_account(account)
        self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)
        self._disconnect()

    def _on_disconnected(self, client: NBXMPPClient, _signal_name: str) -> None:
        domain, error, text = client.get_error()
        if domain == StreamError.SASL:
            if error == "anonymous-not-supported":
                self._show_error_page(
                    _("Anonymous login not supported"),
                    _("Anonymous login not supported"),
                    _("This server does not support anonymous login."),
                )
            else:
                self._show_error_page(
                    _("Authentication failed"), SASL_ERRORS.get(error), text or ""
                )

        elif domain == StreamError.BAD_CERTIFICATE:
            self.get_page("security-warning").set_warning(
                self._client.domain, *self._client.peer_certificate
            )
            self.show_page("security-warning", Gtk.StackTransitionType.SLIDE_LEFT)

        elif domain == StreamError.REGISTER:
            if error == "register-not-supported":
                self._show_error_page(
                    _("Signup not allowed"),
                    _("Signup not allowed"),
                    _("This server does not allow signup."),
                )

        else:
            self._show_error_page(_("Error"), _("Error"), text or error)

        self.get_page("form").remove_form()
        assert self._client is not None
        self._client.destroy()
        self._client = None

    def _on_connection_failed(self, _client: NBXMPPClient, _signal_name: str) -> None:
        self._show_error_page(
            _("Connection failed"),
            _("Connection failed"),
            _(
                "Gajim was not able to reach the server. "
                "Make sure your XMPP address is correct."
            ),
        )
        self._client.destroy()
        self._client = None

    def _show_error_page(self, title: str, heading: str, text: str) -> None:
        self.get_page("error").set_title(title)
        self.get_page("error").set_heading(heading)
        self.get_page("error").set_text(text or "")
        self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)

    def _show_progress_page(self, title: str, text: str) -> None:
        self.get_page("progress").set_title(title)
        self.get_page("progress").set_text(text)
        self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)

    @staticmethod
    def _generate_account_name(domain: str) -> str:
        i = 1
        while domain in app.settings.get_accounts():
            domain = domain + str(i)
            i += 1
        return domain

    def _on_register_form(self, task: Task) -> None:
        try:
            result = cast(RegisterData, task.finish())
        except (StanzaError, MalformedStanzaError) as error:
            self._show_error_page(_("Error"), _("Error"), error.get_text())
            self._disconnect()
            return

        if result.bob_data is not None:
            algo_hash = result.bob_data.cid.split("@")[0]
            app.bob_cache[algo_hash] = result.bob_data.data

        form = result.form
        if result.form is None:
            form = result.fields_form

        if form is not None:
            self.get_page("form").add_form(form)

        elif result.oob_url is not None:
            self.get_page("redirect").set_redirect(result.oob_url, result.instructions)
            self.show_page("redirect", Gtk.StackTransitionType.SLIDE_LEFT)
            self._disconnect()
            return

        self.show_page("form", Gtk.StackTransitionType.SLIDE_LEFT)

    def _submit_form(self) -> None:
        self.get_page("progress").set_text(_("Account is being created"))
        self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)

        form = self.get_page("form").get_submit_form()
        self._client.get_module("Register").submit_register_form(
            form, callback=self._on_register_result
        )

    def _on_register_result(self, task: Task) -> None:
        try:
            task.finish()
        except RegisterStanzaError as error:
            self._set_error_text(error)
            if error.type != "modify":
                self.get_page("form").remove_form()
                self._disconnect()
                return

            register_data = error.get_data()
            form = register_data.form
            if register_data.form is None:
                form = register_data.fields_form

            if form is not None:
                self.get_page("form").add_form(form)

            else:
                self.get_page("form").remove_form()
                self._disconnect()
            return

        except (StanzaError, MalformedStanzaError) as error:
            self._set_error_text(error)
            self.get_page("form").remove_form()
            self._disconnect()
            return

        username, password = self.get_page("form").get_credentials()
        account = self._generate_account_name(self._client.domain)

        proxy_name = None
        if self._client.proxy is not None:
            proxy_name = self.get_page("advanced").get_proxy()

        address = JID(localpart=username, domain=self._client.domain, resource=None)

        app.app.create_account(
            account, address, password, proxy_name, self._client.custom_host
        )

        self.get_page("success").set_account(account)
        self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)
        self.get_page("form").remove_form()
        self._disconnect()

    def _set_error_text(
        self, error: StanzaError | RegisterStanzaError | MalformedStanzaError
    ) -> None:

        error_text = error.get_text()
        if not error_text:
            error_text = _(
                "The server rejected the registration without an error message"
            )
        self._show_error_page(_("Error"), _("Error"), error_text)

    def _cleanup(self, *args: Any) -> None:
        self._disconnect()
        self._destroyed = True


class Login(Page):

    __gsignals__ = {
        "clicked": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _("Add Account")

        self._ui = get_builder("account_wizard.ui")
        self._connect(
            self._ui.log_in_address_entry, "activate", self._on_address_entry_activate
        )
        self._connect(
            self._ui.log_in_address_entry, "changed", self._on_address_changed
        )
        self._connect(self._ui.log_in_password_entry, "changed", self._set_complete)
        self._connect(
            self._ui.log_in_password_entry, "activate", self._on_password_entry_activate
        )
        self._connect(self._ui.log_in_button, "clicked", self._on_login)
        self._connect(self._ui.sign_up_button, "clicked", self._on_signup)

        self.append(self._ui.login_box)

    def focus(self) -> None:
        self._ui.log_in_address_entry.grab_focus()

    def _on_login(self, *args: Any) -> None:
        self.emit("clicked", "login")

    def _on_signup(self, *args: Any) -> None:
        self.emit("clicked", "signup")

    def _on_address_changed(self, entry: Gtk.Entry) -> None:
        self._set_complete()

    def _show_icon(self, show: bool) -> None:
        icon = "lucide-circle-alert-symbolic" if show else None
        self._ui.log_in_address_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon
        )

    def _on_address_entry_activate(self, _entry: Gtk.Entry) -> None:
        GLib.idle_add(self._grab_password_entry_focus)

    def _grab_password_entry_focus(self) -> bool:
        self._ui.log_in_password_entry.grab_focus()
        return False

    def _on_password_entry_activate(self, _entry: Gtk.Entry) -> None:
        if self._ui.log_in_button.get_sensitive():
            self._ui.log_in_button.activate()

    def _validate_jid(self, address: str) -> bool:
        if not address:
            self._show_icon(False)
            return False

        try:
            jid = validate_jid(address, type_="bare")
            if jid.resource:
                raise ValueError
        except ValueError:
            self._show_icon(True)
            self._ui.log_in_address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _("Invalid Address")
            )
            return False

        if app.settings.account_exists(address):
            self._show_icon(True)
            self._ui.log_in_address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY,
                _("This account has already been added"),
            )
            return False

        self._show_icon(False)
        return True

    def _set_complete(self, *args: Any) -> None:
        address = self._validate_jid(self._ui.log_in_address_entry.get_text())
        password = self._ui.log_in_password_entry.get_text()
        self._ui.log_in_button.set_sensitive(bool(address and password))

    def is_advanced(self) -> bool:
        return self._ui.login_advanced_checkbutton.get_active()

    def get_credentials(self) -> tuple[str, str]:
        return (
            self._ui.log_in_address_entry.get_text(),
            self._ui.log_in_password_entry.get_text(),
        )


class Signup(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.complete: bool = False
        self.title: str = _("Create New Account")

        self._servers: list[dict[str, Any]] = []
        self._provider_list_request: HTTPRequest | None = None

        self._ui = get_builder("account_wizard.ui")
        entry = self._ui.server_comboboxtext_sign_up.get_child()
        assert isinstance(entry, Gtk.Entry)
        self._entry = entry
        self._entry.set_activates_default(True)
        self._entry.set_placeholder_text("example.org")
        self._entry.set_input_purpose(Gtk.InputPurpose.URL)

        self._entry_completion = Gtk.EntryCompletion(
            text_column=0,
            inline_completion=True,
            popup_completion=False,
            popup_single_match=False,
        )
        self._entry.set_completion(self._entry_completion)

        self._connect(
            self._ui.recommendation_link1, "activate-link", self._on_activate_link
        )
        self._connect(
            self._ui.recommendation_link2, "activate-link", self._on_activate_link
        )
        self._connect(self._ui.visit_server_button, "clicked", self._on_visit_server)
        self._connect(self._entry, "changed", self._set_complete)

        self.append(self._ui.signup_grid)

    def do_unroot(self) -> None:
        Page.do_unroot(self)
        if self._provider_list_request is None:
            return

        if not self._provider_list_request.is_finished():
            self._provider_list_request.cancel()

    def focus(self) -> None:
        self._entry.grab_focus()

    def update_providers_list(self) -> None:
        if len(self._servers) > 0 or self._provider_list_request is not None:
            # A request has already been started
            return

        self._ui.server_comboboxtext_sign_up.set_sensitive(False)
        self._ui.update_provider_list_icon.add_css_class("spin")

        app.ftm.http_download(
            app.settings.get_app_setting("providers_list_url"),
            callback=self._on_download_provider_list_finished,
        )

    def _on_download_provider_list_finished(
        self, obj: FileTransfer[DownloadResult]
    ) -> None:
        self._ui.server_comboboxtext_sign_up.set_sensitive(True)
        self._ui.update_provider_list_icon.remove_css_class("spin")

        try:
            result = obj.get_result()
        except Exception as error:
            log.warning("Error while downloading provider list: %s", error)
            self._ui.update_provider_list_icon.set_from_icon_name(
                "lucide-circle-x-symbolic"
            )
            self._ui.update_provider_list_icon.set_tooltip_text(
                _("Could not update providers list")
            )
            return

        self._ui.update_provider_list_icon.set_from_icon_name("lucide-check-symbolic")
        self._ui.update_provider_list_icon.set_tooltip_text(
            _("Providers list is up to date")
        )

        self._servers = json.loads(result.content)
        self._create_server_completion()

    def _create_server_completion(self) -> None:
        servers_model = Gtk.ListStore(str, str)

        for server in self._servers:
            server_locations = " ".join(
                get_country_flag_from_code(location)
                for location in server["serverLocations"]
            )
            servers_model.append((server["jid"], server_locations))

        self._entry_completion.set_model(servers_model)

        # Sign up combobox and entry
        self._ui.server_comboboxtext_sign_up.set_model(servers_model)
        cell_area = self._ui.server_comboboxtext_sign_up.get_area()
        assert cell_area is not None

        language_renderer = Gtk.CellRendererText(xalign=1)
        cell_area.add(language_renderer)
        cell_area.attribute_connect(language_renderer, "text", 1)

        self._connect(
            self._ui.server_comboboxtext_sign_up,
            "changed",
            self._on_sign_up_server_changed,
        )

    def _on_sign_up_server_changed(self, combo: Gtk.ComboBox) -> None:
        if len(self._servers) == 0:
            return

        selection = combo.get_active()
        server_data = self._servers[selection]
        if server_data["jid"] != self._entry.get_text():
            # Entry was changed manually
            self._clear_server_info_box()
            return

        self._show_server_infos(server_data)

    def _show_server_infos(self, server_data: dict[str, Any]) -> None:
        self._clear_server_info_box()

        heading = Gtk.Label(label=_("Provider Infos"), halign=Gtk.Align.START)
        heading.add_css_class("bold")
        self._ui.sign_up_info_grid.attach(heading, 0, 0, 2, 1)

        provider_category = server_data["category"]
        image = Gtk.Image.new_from_icon_name("lucide-check-symbolic")
        label = Gtk.Label(
            label=_("Provider Category: %s") % provider_category,
            halign=Gtk.Align.START,
            hexpand=True,
        )
        self._ui.sign_up_info_grid.attach(image, 0, 1, 1, 1)
        self._ui.sign_up_info_grid.attach(label, 1, 1, 1, 1)

        providers_link = Gtk.LinkButton(
            label=_("More infos at providers.xmpp.net"),
            uri=f'https://providers.xmpp.net/provider/{server_data["jid"]}/',
            halign=Gtk.Align.START,
        )
        self._ui.sign_up_info_grid.attach(providers_link, 0, 2, 2, 1)

        self._ui.sign_up_info_grid.attach(Gtk.Separator(), 0, 3, 2, 1)

    def _clear_server_info_box(self) -> None:
        container_remove_all(self._ui.sign_up_info_grid)

    def _on_visit_server(self, _button: Gtk.Button) -> int:
        server = self._entry.get_text().strip()
        server = f"https://{server}"
        open_uri(server)
        return Gdk.EVENT_STOP

    def _set_complete(self, *args: Any) -> None:
        try:
            self.get_server()
        except Exception:
            self.complete = False
            self._ui.visit_server_button.set_visible(False)
        else:
            self.complete = True
            self._ui.visit_server_button.set_visible(True)

        self.update_page_complete()

    def is_anonymous(self) -> bool:
        return self._ui.sign_up_anonymously.get_active()

    def is_advanced(self) -> bool:
        return self._ui.sign_up_advanced_checkbutton.get_active()

    def get_server(self) -> str:
        return validate_domainpart(self._entry.get_text())

    @staticmethod
    def _on_activate_link(_label: Gtk.Label, uri: str) -> int:
        # We have to use this, because the default GTK handler
        # is not cross-platform compatible
        open_uri(uri)
        return Gdk.EVENT_STOP

    def get_visible_buttons(self) -> list[str]:
        return ["back", "signup"]

    def get_default_button(self) -> str:
        return "signup"


class AdvancedSettings(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title: str = _("Advanced settings")
        self.complete: bool = False

        self._ui = get_builder("account_wizard.ui")
        self._connect(self._ui.manage_proxies_button, "clicked", self._on_proxy_manager)
        self._connect(self._ui.proxies_combobox, "changed", self._set_complete)
        self._connect(self._ui.custom_host_entry, "changed", self._set_complete)
        self._connect(self._ui.custom_port_entry, "changed", self._set_complete)
        self.append(self._ui.advanced_grid)

    @staticmethod
    def _on_proxy_manager(_button: Gtk.Button) -> None:
        app.app.activate_action("manage-proxies", None)

    def update_proxy_list(self) -> None:
        model = Gtk.ListStore(str, str)
        self._ui.proxies_combobox.set_model(model)
        model.append(["", _("System")])
        model.append(["no-proxy", _("No Proxy")])
        proxies = app.settings.get_proxies()
        for proxy in proxies:
            model.append([proxy, proxy])
        self._ui.proxies_combobox.set_active(0)

    def get_proxy(self) -> str:
        active = self._ui.proxies_combobox.get_active()
        return self._ui.proxies_combobox.get_model()[active][0]

    def get_custom_host(self) -> CustomHostT | None:
        host = self._ui.custom_host_entry.get_text()
        port = self._ui.custom_port_entry.get_text()
        if not host or not port:
            return None

        con_type = self._ui.con_type_combo.get_active_text()

        protocol = ConnectionProtocol.TCP
        if host.startswith(("ws://", "wss://")):
            protocol = ConnectionProtocol.WEBSOCKET

        return (f"{host}:{port}", protocol, ConnectionType(con_type))

    def _show_host_icon(self, show: bool) -> None:
        icon = "lucide-circle-alert-symbolic" if show else None
        self._ui.custom_host_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon
        )

    def _show_port_icon(self, show: bool) -> None:
        icon = "lucide-circle-alert-symbolic" if show else None
        self._ui.custom_port_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon
        )

    def _validate_host(self) -> bool:
        host = self._ui.custom_host_entry.get_text()
        if host.startswith(("ws://", "wss://")):
            # We have no method for validating websocket URIs
            self._show_host_icon(False)
            return True

        try:
            validate_domainpart(host)
        except Exception:
            self._show_host_icon(True)
            self._ui.custom_host_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _("Invalid domain name")
            )
            return False

        self._show_host_icon(False)
        return True

    def _validate_port(self) -> bool:
        port = self._ui.custom_port_entry.get_text()
        if not port:
            self._show_port_icon(False)
            return False

        try:
            port = int(port)
        except Exception:
            self._show_port_icon(True)
            self._ui.custom_port_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _("Must be a port number")
            )
            return False

        if port not in range(65535):
            self._show_port_icon(True)
            self._ui.custom_port_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY,
                _("Port must be a number between 0 and 65535"),
            )
            return False

        self._show_port_icon(False)
        return True

    def _is_custom_host_set(self) -> bool:
        host = bool(self._ui.custom_host_entry.get_text())
        port = bool(self._ui.custom_port_entry.get_text())
        return host or port

    def _is_proxy_set(self) -> bool:
        return self._ui.proxies_combobox.get_active() != 0

    def _set_complete(self, *args: Any) -> None:
        self.complete = False
        if self._is_proxy_set():
            self.complete = True

        if self._is_custom_host_set():
            port_valid = self._validate_port()
            host_valid = self._validate_host()
            self.complete = port_valid and host_valid

        self.update_page_complete()

    def get_visible_buttons(self) -> list[str]:
        window = get_app_window("AccountWizard")
        assert window is not None
        return ["back", window.get_current_method()]

    def get_default_button(self) -> str:
        window = get_app_window("AccountWizard")
        assert window is not None
        return window.get_current_method()


class SecurityWarning(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title: str = _("Security Warning")
        self._cert: Gio.TlsCertificate | None = None
        self._domain: str | None = None

        self._ui = get_builder("account_wizard.ui")
        self.append(self._ui.security_warning_box)
        self._connect(self._ui.view_cert_button, "clicked", self._on_view_cert)

    @property
    def cert(self) -> Gio.TlsCertificate | None:
        return self._cert

    def set_warning(
        self,
        domain: str,
        cert: Gio.TlsCertificate,
        errors: list[Gio.TlsCertificateFlags],
    ) -> None:
        # Clear list
        self._cert = cert
        self._domain = domain
        clear_listbox(self._ui.error_list)

        unknown_error = _('Unknown TLS error "%s"')
        for error in errors:
            error_text = GIO_TLS_ERRORS.get(error, unknown_error % error)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            image = Gtk.Image.new_from_icon_name("lucide-circle-alert-symbolic")
            image.add_css_class("warning")
            label = Gtk.Label(
                label=error_text,
                wrap=True,
                xalign=0,
                selectable=True,
            )
            box.append(image)
            box.append(label)
            self._ui.error_list.append(box)

        self._ui.trust_cert_checkbutton.set_visible(
            Gio.TlsCertificateFlags.UNKNOWN_CA in errors
        )

    def _on_view_cert(self, _button: Gtk.Button) -> None:
        open_window(
            "CertificateDialog",
            account=None,
            transient_for=self.get_root(),
            cert=self._cert,
        )

    @property
    def trust_certificate(self) -> bool:
        return self._ui.trust_cert_checkbutton.get_active()

    def get_visible_buttons(self) -> list[str]:
        window = get_app_window("AccountWizard")
        assert window is not None
        return ["back", window.get_current_method()]

    def get_default_button(self) -> str:
        return "back"


class Form(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.set_valign(Gtk.Align.FILL)
        self.complete: bool = False
        self.title: str = _("Create Account")
        self._current_form: DataFormWidget | None = None

        heading = Gtk.Label(
            label=_("Create Account"),
            wrap=True,
            max_width_chars=30,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
        )
        heading.add_css_class("title-1")
        self.append(heading)

    @property
    def has_form(self) -> bool:
        return self._current_form is not None

    def _on_is_valid(self, _widget: DataFormWidget, is_valid: bool) -> None:
        try:
            self.get_credentials()
        except Exception:
            is_valid = False

        self.complete = is_valid
        self.update_page_complete()

    def add_form(self, form: Any) -> None:
        self.remove_form()

        options = {"hide-fallback-fields": True, "entry-activates-default": True}
        self._current_form = DataFormWidget(form, options)
        self._connect(self._current_form, "is-valid", self._on_is_valid)
        self._current_form.validate()
        self.append(self._current_form)

    def get_credentials(self) -> tuple[str, str]:
        assert self._current_form is not None
        return (
            self._current_form.get_form()["username"].value,
            self._current_form.get_form()["password"].value,
        )

    def get_submit_form(self) -> Any:
        assert self._current_form is not None
        return self._current_form.get_submit_form()

    def remove_form(self) -> None:
        if self._current_form is None:
            return

        self.remove(self._current_form)
        self._current_form = None

    def focus(self) -> None:
        assert self._current_form is not None
        self._current_form.focus_first_entry()

    def get_visible_buttons(self) -> list[str]:
        return ["back", "signup"]

    def get_default_button(self) -> str:
        return "signup"


class Redirect(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title: str = _("Redirect")
        self._link: str | None = None

        self._ui = get_builder("account_wizard.ui")
        self.append(self._ui.redirect_box)
        self._connect(self._ui.link_button, "clicked", self._on_link_button)

    def set_redirect(self, link: str, instructions: str | None) -> None:
        if instructions is None:
            instructions = _("Register on the Website")
        self._ui.instructions.set_text(instructions)
        self._link = link

    def _on_link_button(self, _button: Gtk.Button) -> None:
        assert self._link is not None
        open_uri(self._link)

    def get_visible_buttons(self) -> list[str]:
        return ["back"]


class Success(SuccessPage):
    def __init__(self) -> None:
        SuccessPage.__init__(self)
        self.set_title(_("Account Added"))
        self.set_heading(_("Account has been added successfully"))

        self._account: str | None = None
        self._our_jid: str | None = None
        self._label: str | None = None
        self._color: str | None = None

        self._ui = get_builder("account_wizard.ui")
        self.append(self._ui.account_label_box)

        self._provider = self._add_css_provider()

        self._connect(self._ui.account_name_entry, "changed", self._on_name_changed)

        color_dialog = Gtk.ColorDialog()
        self._ui.account_color_button.set_dialog(color_dialog)
        self._connect(self._ui.account_color_button, "notify::rgba", self._on_color_set)

    def set_account(self, account: str) -> None:
        self._account = account
        self._our_jid = app.get_jid_from_account(account)
        self._ui.badge_preview.set_text(self._our_jid)
        rgba = Gdk.RGBA()
        rgba.parse(get_color_for_account(self._our_jid))
        self._ui.account_color_button.set_rgba(rgba)
        self._color = rgba.to_string()
        self._set_badge_color(self._color)
        self._save_config()

    @property
    def account(self) -> str | None:
        return self._account

    def _add_css_provider(self) -> Gtk.CssProvider:
        context = self._ui.badge_preview.get_style_context()
        provider = Gtk.CssProvider()
        context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        return provider

    def _on_name_changed(self, entry: Gtk.Entry):
        assert self._our_jid is not None
        self._label = entry.get_text()
        self._ui.badge_preview.set_text(self._label or self._our_jid)
        self._save_config()

    def _on_color_set(self, color_button: Gtk.ColorDialogButton, *args: Any):
        rgba = color_button.get_rgba()
        self._color = rgba.to_string()
        self._set_badge_color(self._color)
        self._save_config()

    def _set_badge_color(self, color: str) -> None:
        css = ".badge { background-color: %s; font-size: 100%%; }" % color
        self._provider.load_from_bytes(GLib.Bytes.new(css.encode("utf-8")))

    def _save_config(self) -> None:
        assert self._account is not None
        app.settings.set_account_setting(self._account, "account_color", self._color)
        if self._label:
            app.settings.set_account_setting(
                self._account, "account_label", self._label
            )
        app.css_config.refresh()

    def get_visible_buttons(self) -> list[str]:
        return ["connect"]


class Error(ErrorPage):
    def __init__(self) -> None:
        ErrorPage.__init__(self)
        self.set_heading(_("An error occurred during account creation"))

    def get_visible_buttons(self) -> list[str]:
        return ["back"]
