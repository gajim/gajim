# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal
from typing import overload

import logging

import pysequoia as pys
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.modules.openpgp import format_fingerprint
from gajim.common.modules.openpgp import MultipleSecretKeysImportError
from gajim.common.modules.util import Task
from gajim.plugins.plugins_i18n import _

from gajim.gtk.activity_list import OpenPGPEvent
from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import AssistantErrorPage
from gajim.gtk.assistant import AssistantPage
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.openpgp.wizard")


class OpenPGPWizard(Assistant):
    def __init__(
        self, account: str, *, mode: Literal["test-password"] | None = None
    ) -> None:
        Assistant.__init__(
            self, name="OpenPGPWizard", height=500, transient_for=app.window, modal=True
        )
        self._destroyed: bool = False
        self._mode = mode

        self.account = account
        self._client = app.get_client(account)

        self.add_button("back", _("Back"))
        self.add_button("close", _("Close"))
        self.add_button("overwrite", _("Overwrite"), css_class="destructive-action")
        self.add_button("other-options", _("Other Options"))
        self.add_button(
            "import", _("Import Key"), complete=True, css_class="suggested-action"
        )
        self.add_button(
            "restore", _("Restore Key"), css_class="suggested-action", complete=True
        )
        self.add_button("choose", _("Confirm"), css_class="suggested-action")
        self.add_button(
            "test-password", _("Apply"), css_class="suggested-action", complete=True
        )

        self.add_pages(
            {
                "welcome": WelcomePage(),
                "import": ImportPage(),
                "password": BackupPasswordPage(mode=mode),
                "choose-secret-key": ChooseSecretKeyPage(),
                "error": ErrorPage(),
                "success": SuccessPage(),
            }
        )

        self.add_default_page("progress")

        welcome_page = self.get_page("welcome")
        self._connect(welcome_page, "clicked", self._on_welcome_page_button_clicked)

        self._connect(self, "button-clicked", self._on_assistant_button_clicked)
        self._connect(self, "page-changed", self._on_page_changed)

        self.show_page("progress")
        if (
            self._client.get_module("OpenPGP").secret_key_exists()
            and not mode == "test-password"
        ):
            self._show_success_page()
        else:
            self._client.get_module("OpenPGP").request_secret_key(
                callback=self._on_secret_key_received
            )

    @overload
    def get_page(self, name: Literal["welcome"]) -> WelcomePage: ...

    @overload
    def get_page(self, name: Literal["import"]) -> ImportPage: ...

    @overload
    def get_page(self, name: Literal["password"]) -> BackupPasswordPage: ...

    @overload
    def get_page(self, name: Literal["choose-secret-key"]) -> ChooseSecretKeyPage: ...

    @overload
    def get_page(self, name: Literal["error"]) -> ErrorPage: ...

    @overload
    def get_page(self, name: Literal["success"]) -> SuccessPage: ...

    def get_page(self, name: str) -> AssistantPage:
        return self._pages[name]

    def _on_assistant_button_clicked(
        self, _assistant: Assistant, button_name: str
    ) -> None:
        match button_name:
            case "import":
                key_str = self.get_page("import").get_key_string()
                try:
                    self._client.get_module("OpenPGP").import_key(key_str)
                except Exception as error:
                    self._show_error_page(
                        _("Import Error"), _("Import Error"), str(error)
                    )

            case "restore" | "choose":
                fingerprint = None
                if button_name == "choose":
                    fingerprint = self.get_page(
                        "choose-secret-key"
                    ).get_selected_fingerprint()

                password = self.get_page("password").get_password()

                try:
                    self._client.get_module("OpenPGP").import_key(
                        self._encrypted_backup_bytes, password, fingerprint
                    )
                except MultipleSecretKeysImportError as error:
                    self.get_page("choose-secret-key").set_certs(error.get_certs())
                    self.show_page("choose-secret-key")

                except Exception as error:
                    self._show_error_page(
                        _("Import Error"),
                        _("Import Error"),
                        _(
                            "An error occurred while trying to import your OpenPGP key: %s"
                        )
                        % str(error),
                    )

                else:
                    self._show_success_page()

            case "test-password":
                password = self.get_page("password").get_password()
                try:
                    self._client.get_module("OpenPGP").test_backup_password(
                        self._encrypted_backup_bytes, password
                    )
                except Exception as error:
                    self._show_error_page(
                        _("Decryption Error"),
                        _("Decryption Error"),
                        _("An error occurred while trying to decrypt your backup: %s")
                        % str(error),
                    )

                else:
                    self._show_success_page()

            case "overwrite":
                self._client.get_module("OpenPGP").backup_secret_key(
                    callback=self._on_overwrite_result
                )
                self.show_page("progress")

            case "other-options":
                self.show_page("welcome")

            case "back":
                self.show_last_page()

            case "close":
                self.close()

            case _:
                raise ValueError

    def _on_welcome_page_button_clicked(
        self, _page: Gtk.Widget, button_name: str
    ) -> None:
        if button_name == "import":
            self.show_page("import", Gtk.StackTransitionType.SLIDE_LEFT)

        elif button_name == "generate":
            try:
                self._client.get_module("OpenPGP").generate_key()
            except Exception as error:
                self._show_error_page(_("Error"), _("Error"), str(error))
            else:
                self._show_success_page(
                    self._client.get_module("OpenPGP").get_backup_password()
                )

    def _on_page_changed(self, _assistant: Assistant, page_name: str) -> None:
        if page_name == "import":
            self.get_page("import").clear()

    def _show_success_page(self, backup_password: str | None = None) -> None:
        success_page = self.get_page("success")
        if self._mode == "test-password":
            success_page.set_title(_("Backup Successful"))
            success_page.set_text(_("Your OpenPGP key backup was successful."))
        else:
            success_page.set_title(_("Setup Complete"))
            success_page.set_text(
                _("Your OpenPGP key has been created. Your chat is now encrypted.")
            )
        success_page.show_backup_password(backup_password)

        self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)
        app.window.get_activity_list().remove_by_type(OpenPGPEvent)

    def _show_error_page(self, title: str, heading: str, text: str) -> None:
        self.get_page("error").set_title(title)
        self.get_page("error").set_heading(heading)
        self.get_page("error").set_text(text or "")
        self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_secret_key_received(self, task: Task) -> None:
        try:
            encrypted_bytes = cast(bytes | None, task.finish())
        except Exception as error:
            log.error("Error on secret key request: %s", error)
            self.show_page("welcome", Gtk.StackTransitionType.SLIDE_LEFT)
            return

        if not encrypted_bytes:
            self.show_page("welcome", Gtk.StackTransitionType.SLIDE_LEFT)
            return

        self._encrypted_backup_bytes = encrypted_bytes
        self.show_page("password")

    def _on_overwrite_result(self, task: Task) -> None:
        try:
            task.finish()
        except Exception as error:
            log.error("Error when overwriting secret key : %s", error)
            self._show_error_page(
                _("Backup Error"),
                _("Backup Error"),
                _("An error occurred while trying to overwrite your backup: %s")
                % str(error),
            )

        else:
            self._show_success_page(
                self._client.get_module("OpenPGP").get_backup_password()
            )


@Gtk.Template(string=get_ui_string("openpgp/welcome.ui"))
class WelcomePage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardWelcome"
    __gsignals__ = {
        "clicked": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    _import_button: Gtk.Button = Gtk.Template.Child()
    _generate_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Setup OpenPGP Encryption")

        self._connect(self._import_button, "clicked", self._on_button_clicked, "import")
        self._connect(
            self._generate_button, "clicked", self._on_button_clicked, "generate"
        )

    def _on_button_clicked(self, _button: Gtk.Button, name: str) -> None:
        self.emit("clicked", name)


@Gtk.Template(string=get_ui_string("openpgp/import.ui"))
class ImportPage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardImport"

    _import_textview: Gtk.TextView = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.set_valign(Gtk.Align.FILL)

        self.title = _("Import OpenPGP Key")
        self.complete = False

        self._buffer = self._import_textview.get_buffer()
        self._connect(self._buffer, "changed", self._on_buffer_changed)

    def _on_buffer_changed(self, buffer: Gtk.TextBuffer) -> None:
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, False)
        self.complete = bool(text)
        self.update_page_complete()

    def get_key_string(self) -> str:
        start, end = self._buffer.get_bounds()
        return self._buffer.get_text(start, end, False)

    def clear(self) -> None:
        self._buffer.delete(*self._buffer.get_bounds())

    def get_visible_buttons(self) -> list[str]:
        return ["back", "import"]


@Gtk.Template(string=get_ui_string("openpgp/password.ui"))
class BackupPasswordPage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardBackupPassword"

    _password_entry: Gtk.PasswordEntry = Gtk.Template.Child()

    def __init__(self, mode: Literal["test-password"] | None) -> None:
        AssistantPage.__init__(self)
        self._mode = mode
        if mode == "test-password":
            self.title = _("Enter Password")
        else:
            self.title = _("Restore Backup")
        self.complete = False

        self._connect(self._password_entry, "changed", self._on_entry_changed)

    def get_visible_buttons(self) -> list[str]:
        if self._mode == "test-password":
            return ["overwrite", "test-password"]
        return ["other-options", "restore"]

    def _on_entry_changed(self, entry: Gtk.PasswordEntry) -> None:
        ## TODO validate input against regex
        self.complete = True
        self.update_page_complete()

    def get_password(self) -> str:
        password = self._password_entry.get_text()
        return password.upper().strip()


@Gtk.Template(string=get_ui_string("openpgp/choose_secret_key.ui"))
class ChooseSecretKeyPage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardChooseSecretKey"

    _listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Choose Secret Key")
        self.complete = False

        self._certs: list[pys.Cert] = []

        self._connect(self._listbox, "row-selected", self._on_row_selected)

    def _on_row_selected(
        self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        self.complete = row is not None
        self.update_page_complete()

    def get_visible_buttons(self) -> list[str]:
        return ["back", "choose"]

    def get_selected_fingerprint(self) -> str:
        row = self._listbox.get_selected_row()
        assert row is not None
        label = cast(FingerprintLabel, row.get_child())
        return label.get_fingerprint()

    def set_certs(self, certs: list[pys.Cert]) -> None:
        container_remove_all(self._listbox)
        self._certs = certs
        for cert in certs:
            self._listbox.append(FingerprintLabel(cert))


@Gtk.Template(string=get_ui_string("openpgp/success.ui"))
class SuccessPage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardSuccess"

    _heading: Gtk.Label = Gtk.Template.Child()
    _text: Gtk.Label = Gtk.Template.Child()
    _backup_password_box: Gtk.Box = Gtk.Template.Child()
    _password_entry: Gtk.PasswordEntry = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)

    def set_title(self, title: str) -> None:
        self.title = title

    def set_heading(self, heading: str) -> None:
        self._heading.set_text(heading)

    def set_text(self, text: str) -> None:
        self._text.set_text(text)

    def show_backup_password(self, backup_password: str | None) -> None:
        if backup_password is None:
            self._backup_password_box.set_visible(False)
            return

        self._backup_password_box.set_visible(True)
        self._password_entry.set_text(backup_password)

    def get_visible_buttons(self) -> list[str]:
        return ["close"]


class FingerprintLabel(Gtk.Label):
    def __init__(self, cert: pys.Cert) -> None:
        super().__init__()
        self._cert = cert
        self.set_label(format_fingerprint(cert.fingerprint).upper())
        self.add_css_class("p-6")
        self.add_css_class("monospace")

    def get_fingerprint(self) -> str:
        return self._cert.fingerprint


class ErrorPage(AssistantErrorPage):
    def get_visible_buttons(self) -> list[str]:
        return ["back", "close"]
