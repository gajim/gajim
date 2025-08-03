# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal
from typing import overload

import logging

from gi.repository import Gtk
from nbxmpp.errors import ChangePasswordStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import passwords
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.assistant import SuccessPage
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util.misc import ensure_not_destroyed

log = logging.getLogger("gajim.gtk.change_password")


class ChangePassword(Assistant):
    def __init__(self, account: str) -> None:
        Assistant.__init__(self)

        self.account = account
        self._client = app.get_client(account)
        self._destroyed = False

        self.add_button("apply", _("Change"), "suggested-action", complete=True)
        self.add_button("close", _("Close"))
        self.add_button("back", _("Back"))

        self.add_pages(
            {
                "password": EnterPassword(),
                "next_stage": NextStage(),
                "error": Error(),
                "success": Success(),
            }
        )

        progress = self.add_default_page("progress")
        progress.set_title(_("Changing Password..."))
        progress.set_text(_("Trying to change password..."))

        self._connect(self, "button-clicked", self._on_button_clicked)

    @overload
    def get_page(self, name: Literal["password"]) -> EnterPassword: ...

    @overload
    def get_page(self, name: Literal["next_stage"]) -> NextStage: ...

    @overload
    def get_page(self, name: Literal["error"]) -> Error: ...

    @overload
    def get_page(self, name: Literal["success"]) -> Success: ...

    def get_page(self, name: str) -> Page:
        return self._pages[name]

    def _on_button_clicked(self, _assistant: Assistant, button_name: str) -> None:
        page = self.get_current_page()
        if button_name == "apply":
            self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)
            self._on_apply(next_stage=page == "next_stage")

        elif button_name == "back":
            self.show_page("password", Gtk.StackTransitionType.SLIDE_RIGHT)

        elif button_name == "close":
            self.window.close()

    def _on_apply(self, next_stage: bool = False) -> None:
        if next_stage:
            # TODO: Does not apply sasl prep profile
            form = self.get_page("next_stage").get_submit_form()
            self._client.get_module("Register").change_password_with_form(
                form, callback=self._on_change_password
            )
        else:
            password = self.get_page("password").get_password()
            self._client.get_module("Register").change_password(
                password, callback=self._on_change_password
            )

    @ensure_not_destroyed
    def _on_change_password(self, task: Task) -> None:
        try:
            task.finish()
        except ChangePasswordStanzaError as error:
            form = cast(SimpleDataForm, error.get_form())
            self.get_page("next_stage").set_form(form)
            self.show_page("next_stage", Gtk.StackTransitionType.SLIDE_LEFT)

        except StanzaError as error:
            error_text = to_user_string(error)
            self.get_page("error").set_text(error_text)
            self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)

        else:
            password = self.get_page("password").get_password()
            passwords.save_password(self.account, password)
            self.show_page("success")

    def _cleanup(self) -> None:
        self._destroyed = True


class EnterPassword(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.complete = False
        self.title = _("Change Password")

        heading = Gtk.Label(
            label=_("Change Password"),
            wrap=True,
            max_width_chars=30,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
        )

        label = Gtk.Label(
            label=_("Please enter your new password."),
            wrap=True,
            max_width_chars=50,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
            margin_bottom=12,
        )

        self._password1_entry = Gtk.Entry()
        self._password1_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._password1_entry.set_visibility(False)
        self._password1_entry.set_invisible_char("•")
        self._password1_entry.set_valign(Gtk.Align.END)
        self._password1_entry.set_placeholder_text(_("Enter new password..."))
        self._connect(self._password1_entry, "changed", self._on_changed)
        self._password2_entry = Gtk.Entry()
        self._password2_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._password2_entry.set_visibility(False)
        self._password2_entry.set_invisible_char("•")
        self._password2_entry.set_activates_default(True)
        self._password2_entry.set_valign(Gtk.Align.START)
        self._password2_entry.set_placeholder_text(_("Confirm new password..."))
        self._connect(self._password2_entry, "changed", self._on_changed)

        self.append(heading)
        self.append(label)
        self.append(self._password1_entry)
        self.append(self._password2_entry)
        self._hide_warning()

    def _hide_warning(self) -> None:
        self._password1_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, None
        )

    def _show_warning(self, text: str) -> None:
        self._password1_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, "dialog-warning-symbolic"
        )
        self._password1_entry.set_icon_tooltip_text(
            Gtk.EntryIconPosition.SECONDARY, text
        )

    def _on_changed(self, _entry: Gtk.Entry) -> None:
        password1 = self._password1_entry.get_text()
        if not password1:
            self._show_warning(_("Passwords do not match"))
            self._set_complete(False)
            return

        password2 = self._password2_entry.get_text()
        if password1 != password2:
            self._show_warning(_("Passwords do not match"))
            self._set_complete(False)
            return

        self._hide_warning()
        self._set_complete(True)

    def _set_complete(self, state: bool) -> None:
        self.complete = state
        self.update_page_complete()

    def get_password(self) -> str:
        return self._password1_entry.get_text()

    def get_visible_buttons(self) -> list[str]:
        return ["apply"]


class NextStage(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.set_valign(Gtk.Align.FILL)
        self.complete = False
        self.title = _("Change Password")
        self._current_form = None

    def _on_is_valid(self, _widget: Gtk.Widget, is_valid: bool) -> None:
        self.complete = is_valid
        self.update_page_complete()

    def set_form(self, form: SimpleDataForm) -> None:
        if self._current_form is not None:
            self.remove(self._current_form)
        self._current_form = DataFormWidget(form)
        self._connect(self._current_form, "is-valid", self._on_is_valid)
        self._current_form.validate()
        self.append(self._current_form)

    def get_submit_form(self) -> SimpleDataForm:
        assert self._current_form is not None
        form = self._current_form.get_submit_form()
        assert isinstance(form, SimpleDataForm)
        return form

    def get_visible_buttons(self) -> list[str]:
        return ["apply"]


class Error(ErrorPage):
    def __init__(self) -> None:
        ErrorPage.__init__(self)
        self.set_title(_("Password Change Failed"))
        self.set_heading(_("Password Change Failed"))
        self.set_text(_("An error occurred while trying to change your password."))

    def get_visible_buttons(self) -> list[str]:
        return ["back"]


class Success(SuccessPage):
    def __init__(self) -> None:
        SuccessPage.__init__(self)
        self.set_title(_("Password Changed"))
        self.set_heading(_("Password Changed"))
        self.set_text(_("Your password has successfully been changed."))

    def get_visible_buttons(self) -> list[str]:
        return ["close"]
