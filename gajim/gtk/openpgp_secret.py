# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal
from typing import overload

import logging
from pathlib import Path

from gi.repository import Adw
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import passwords
from gajim.common.helpers import generate_qr_code
from gajim.plugins.plugins_i18n import _

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import AssistantPage
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.preference.widgets import CopyButton
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.openpgp.secret")


class OpenPGPSecret(Assistant):
    def __init__(self, account: str) -> None:
        Assistant.__init__(
            self,
            name="OpenPGPSecret",
            height=500,
            transient_for=app.app.get_active_window(),
            modal=True,
        )
        self._destroyed: bool = False

        self.account = account

        self.add_button("close", _("Close"))
        self.add_button(
            "unlock", _("Unlock"), complete=True, css_class="suggested-action"
        )

        self.add_pages(
            {
                "unlock": UnlockPage(account),
                "share": SharePage(account),
            }
        )

        self._connect(self, "button-clicked", self._on_assistant_button_clicked)

    @overload
    def get_page(self, name: Literal["unlock"]) -> UnlockPage: ...

    @overload
    def get_page(self, name: Literal["share"]) -> SharePage: ...

    def get_page(self, name: str) -> AssistantPage:
        return self._pages[name]

    def _on_assistant_button_clicked(
        self, _assistant: Assistant, button_name: str
    ) -> None:
        match button_name:
            case "unlock":
                self.get_page("share").generate()
                self.show_page("share")

            case "close":
                self.close()

            case _:
                raise ValueError(f"Unknown button: {button_name}")


@Gtk.Template(string=get_ui_string("openpgp/unlock.ui"))
class UnlockPage(AssistantPage):
    __gtype_name__ = "OpenPGPUnlock"

    _password_entry: Gtk.PasswordEntry = Gtk.Template.Child()
    _warning_box: Gtk.Box = Gtk.Template.Child()
    _warning_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, account: str) -> None:
        AssistantPage.__init__(self)
        self.title = _("Enter Password to Unlock")
        self.complete = False

        self._password_check_timeout_id = None

        self._cur_password = passwords.get_password(account)

        self._connect(self._password_entry, "changed", self._on_changed)

    def _on_changed(self, _password_entry: Gtk.PasswordEntry) -> None:
        if self._password_check_timeout_id is not None:
            GLib.source_remove(self._password_check_timeout_id)
            self._password_check_timeout_id = None

        if self._cur_password is None:
            self.set_warning(_("No account password found, unlocking not possible"))
            self.set_complete(False)
            return

        if not self._password_entry.get_text():
            self.set_complete(False)
            self.set_warning(None)
            return

        self._password_check_timeout_id = GLib.timeout_add(
            800, self.delayed_password_check
        )

    def delayed_password_check(self) -> None:
        assert self._password_check_timeout_id is not None
        GLib.source_remove(self._password_check_timeout_id)
        self._password_check_timeout_id = None

        cur_password = self._password_entry.get_text()
        if cur_password != self._cur_password:
            self.set_warning(_("Password incorrect"))
            self.set_complete(False)
            return

        self.set_warning(None)
        self.set_complete(True)

    def set_warning(self, text: str | None) -> None:
        self._warning_label.set_text(text or "")
        self._warning_box.set_visible(bool(text))

    def get_visible_buttons(self) -> list[str]:
        return ["close", "unlock"]

    def get_default_button(self) -> str:
        return "unlock"


@Gtk.Template(string=get_ui_string("openpgp/secret_share.ui"))
class SharePage(AssistantPage):
    __gtype_name__ = "OpenPGPSecretShare"

    _toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    _box: Gtk.Box = Gtk.Template.Child()
    _key_label: Gtk.Label = Gtk.Template.Child()
    _copy_button: CopyButton = Gtk.Template.Child()
    _hint_label: Gtk.Label = Gtk.Template.Child()
    _qr_code_image: Gtk.Image = Gtk.Template.Child()

    def __init__(self, account: str) -> None:
        AssistantPage.__init__(self)
        self.set_valign(Gtk.Align.FILL)

        self.title = _("Share Secret Key")
        self.complete = True

        self._client = app.get_client(account)

        file_chooser_button = FileChooserButton(
            path=Path.home() / f"{self._client.account}-private.key",
            mode="save",
            label=_("Export…"),
            icon_name="lucide-file-down-symbolic",
        )
        self._box.append(file_chooser_button)
        self._connect(file_chooser_button, "path-picked", self._on_path_picked)
        self._connect(self._copy_button, "clicked", self._on_copy_clicked)

    def generate(self) -> None:
        share_uri = self._client.get_module("OpenPGP").get_secret_share_uri()
        backup_password = self._client.get_module("OpenPGP").get_backup_password()

        if share_uri is None or backup_password is None:
            self._key_label.set_text(_("No key found"))
            self._copy_button.set_sensitive(False)
            self._hint_label.set_visible(False)

            self._qr_code_image.set_visible(False)
            self._qr_code_image.set_from_paintable(None)

        else:
            self._key_label.set_text(backup_password)
            self._copy_button.set_sensitive(True)
            self._hint_label.set_visible(True)

            texture = generate_qr_code(share_uri)
            self._qr_code_image.set_visible(True)
            self._qr_code_image.set_from_paintable(texture)

    def _on_copy_clicked(self, _button: CopyButton) -> None:
        app.window.get_clipboard().set(self._key_label.get_text())
        self._toast_overlay.add_toast(Adw.Toast.new(_("Key copied to clipboard")))

    def _on_path_picked(self, button: Gtk.Button, paths: list[Path]) -> None:
        exported_key = self._client.get_module("OpenPGP").export_secret_key()
        if exported_key is None or not paths:
            return

        paths[0].write_text(exported_key)

        toast = Adw.Toast(
            title=_("Key has been saved"),
            timeout=5,
            button_label=_("Open Folder"),
            action_name="app.open-folder",
            action_target=GLib.Variant("s", str(paths[0])),
        )
        self._toast_overlay.add_toast(toast)

    def get_visible_buttons(self) -> list[str]:
        return ["close"]

    def get_default_button(self) -> str:
        return "close"
