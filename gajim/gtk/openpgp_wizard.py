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
from gajim.gtk.assistant import AssistantSuccessPage
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.openpgp.wizard")


class OpenPGPWizard(Assistant):
    def __init__(self, account: str, *, backup_mode: bool = False) -> None:
        Assistant.__init__(
            self, name="OpenPGPWizard", height=500, transient_for=app.window, modal=True
        )
        self._destroyed: bool = False
        self._backup_mode = backup_mode

        self.account = account
        self._client = app.get_client(account)

        self.add_button("back", _("Back"))
        self.add_button("close", _("Close"))

        if backup_mode:
            self.add_button("backup", _("Backup"), css_class="suggested-action")
            self.add_pages(
                {
                    "backup": BackupPage("dummy"),
                }
            )

        else:
            self.add_pages(
                {
                    "welcome": WelcomePage(),
                    "import": ImportPage(),
                    "restore": RestoreBackupPage(),
                    "choose-secret-key": ChooseSecretKeyPage(),
                }
            )

            self.add_button(
                "import", _("Import Key"), complete=True, css_class="suggested-action"
            )
            self.add_button(
                "restore", _("Restore"), css_class="suggested-action", complete=True
            )
            self.add_button("choose", _("Confirm"), css_class="suggested-action")

            welcome_page = self.get_page("welcome")
            self._connect(welcome_page, "clicked", self._on_welcome_page_button_clicked)

        self.add_pages(
            {
                "error": ErrorPage(),
                "success": SuccessPage(),
            }
        )

        self.add_default_page("progress")

        self._connect(self, "button-clicked", self._on_assistant_button_clicked)
        self._connect(self, "page-changed", self._on_page_changed)

        self.show_page("progress")
        if self._client.get_module("OpenPGP").secret_key_exists():
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
    def get_page(self, name: Literal["restore"]) -> RestoreBackupPage: ...

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

                password = self.get_page("restore").get_password()

                try:
                    self._client.get_module("OpenPGP").import_key(
                        self._encrypted_backup_bytes, password, fingerprint
                    )
                except MultipleSecretKeysImportError as error:
                    self.get_page("choose-secret-key").set_certs(error.get_certs())
                    self.show_page("choose-secret-key")

                except Exception as error:
                    self._show_error_page(_("Error"), _("Error on import"), str(error))

                else:
                    self._show_success_page()

            case "backup":
                self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)
                self._client.get_module("OpenPGP").backup_secret_key(
                    callback=self._on_backup_result,
                )

            case "back":
                self.show_page("welcome", Gtk.StackTransitionType.SLIDE_RIGHT)

            case "close":
                self.close()

            case _:
                raise ValueError

    def _on_welcome_page_button_clicked(
        self, _page: Gtk.Widget, button_name: str
    ) -> None:
        if button_name == "import":
            self.show_page("import", Gtk.StackTransitionType.SLIDE_LEFT)

        elif button_name == "restore_backup":
            self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)
            self._client.get_module("OpenPGP").request_secret_key(
                callback=self._on_secret_key_received,
            )

        elif button_name == "generate":
            try:
                self._client.get_module("OpenPGP").generate_key()
            except Exception as error:
                self._show_error_page(_("Error"), _("Error"), str(error))
            else:
                self._show_success_page()

    def _on_page_changed(self, _assistant: Assistant, page_name: str) -> None:
        if page_name == "import":
            self.get_page("import").clear()

    def _show_success_page(self) -> None:
        if self._backup_mode:
            self.get_page("success").set_title(_("Backup Successful"))
            self.get_page("success").set_text(
                _("Your OpenPGP key backup was successful.")
            )
        else:
            self.get_page("success").set_title(_("Setup Complete"))
            self.get_page("success").set_text(
                _("Your OpenPGP key has been created. Your chat is now encrypted.")
            )
        self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)
        app.window.get_activity_list().remove_by_type(OpenPGPEvent)

    def _show_error_page(self, title: str, heading: str, text: str) -> None:
        self.get_page("error").set_title(title)
        self.get_page("error").set_heading(heading)
        self.get_page("error").set_text(text or "")
        self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_backup_result(self, task: Task) -> None:
        try:
            task.finish()
        except Exception as error:
            self._show_error_page(
                _("Error on backup"), _("Error on backup"), str(error)
            )
            return

        self._show_success_page()

    def _on_secret_key_received(self, task: Task) -> None:
        try:
            encrypted_bytes = cast(bytes | None, task.finish())
        except Exception as error:
            log.error("Error on secret key request: %s", error)
            self._show_error_page(_("Error"), _("Error"), str(error))
            return

        if not encrypted_bytes:
            self._show_error_page(
                _("No backup found"),
                _("No backup found"),
                _("There is no backup on the server"),
            )
            return

        self._encrypted_backup_bytes = encrypted_bytes
        self.show_page("restore")


@Gtk.Template(string=get_ui_string("openpgp/welcome.ui"))
class WelcomePage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardWelcome"
    __gsignals__ = {
        "clicked": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    _import_button: Gtk.Button = Gtk.Template.Child()
    _restore_backup_button: Gtk.Button = Gtk.Template.Child()
    _generate_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Setup OpenPGP Encryption")

        self._connect(self._import_button, "clicked", self._on_button_clicked, "import")
        self._connect(
            self._restore_backup_button,
            "clicked",
            self._on_button_clicked,
            "restore_backup",
        )
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


@Gtk.Template(string=get_ui_string("openpgp/restore.ui"))
class RestoreBackupPage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardRestore"

    _password_entry: Gtk.PasswordEntry = Gtk.Template.Child()

    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Restore Backup")
        self.complete = False

        self._connect(self._password_entry, "changed", self._on_entry_changed)

    def get_visible_buttons(self) -> list[str]:
        return ["back", "restore"]

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


class FingerprintLabel(Gtk.Label):
    def __init__(self, cert: pys.Cert) -> None:
        super().__init__()
        self._cert = cert
        self.set_label(format_fingerprint(cert.fingerprint))

    def get_fingerprint(self) -> str:
        return self._cert.fingerprint


@Gtk.Template(string=get_ui_string("openpgp/backup.ui"))
class BackupPage(AssistantPage):
    __gtype_name__ = "OpenPGPWizardBackup"

    _password_label: Gtk.Label = Gtk.Template.Child()
    _copy_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, password: str) -> None:
        AssistantPage.__init__(self)
        self.title = _("Backup")
        self.complete = False

        self._password_label.set_text(password)

        self._connect(self._copy_button, "clicked", self._on_copy_clicked)

    def _on_copy_clicked(self, _button: Gtk.Button) -> None:
        app.window.get_clipboard().set(self._password_label.get_text())

    def get_visible_buttons(self) -> list[str]:
        return ["close", "backup"]


class ErrorPage(AssistantErrorPage):
    def get_visible_buttons(self) -> list[str]:
        return ["back"]


class SuccessPage(AssistantSuccessPage):
    def get_visible_buttons(self) -> list[str]:
        return ["close"]
