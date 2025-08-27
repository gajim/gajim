# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging

from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.client import Client
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.apply_button_box import ApplyButtonBox
from gajim.gtk.builder import get_builder
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.groupchat_config")


class GroupchatConfig(Gtk.Box, SignalManager):
    def __init__(self, client: Client, contact: GroupchatContact) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._contact = contact
        self._client = client
        self._data_form_widget: DataFormWidget | None = None
        self_contact = self._contact.get_self()
        assert self_contact is not None

        self._own_affiliation = self_contact.affiliation

        self._ui = get_builder("groupchat_config.ui")

        self._apply_button = ApplyButtonBox(_("Apply"), self._on_apply)
        self._apply_button.set_halign(Gtk.Align.END)
        self._apply_button.add_css_class("m-18")

        self._ui.config_box.append(self._apply_button)

        self.append(self._ui.stack)

        if self._own_affiliation.is_owner:
            self._ui.stack.set_visible_child_name("loading")
            self._client.get_module("MUC").request_config(
                self._contact.jid, callback=self._on_config_received
            )
        else:
            self._ui.error_label.set_text(
                _("You need Owner permission to change the configuration")
            )
            self._ui.error_image.set_from_icon_name("lucide-circle-x-symbolic")
            self._ui.stack.set_visible_child_name("error")

    def do_unroot(self) -> None:
        self._disconnect_all()
        del self._apply_button
        if self._data_form_widget is not None:
            app.check_finalize(self._data_form_widget)
        del self._data_form_widget
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _set_form(self, form: Any) -> None:
        self._data_form_widget = DataFormWidget(form)
        self._connect(self._data_form_widget, "is-valid", self._on_is_valid)
        self._data_form_widget.add_css_class("p-12")
        self._ui.config_box.prepend(self._data_form_widget)
        self._ui.stack.set_visible_child_name("config")

    def _on_is_valid(self, _widget: Any, is_valid: bool) -> None:
        assert self._data_form_widget is not None
        if not self._data_form_widget.was_modified():
            self._apply_button.set_button_state(False)
        else:
            self._apply_button.set_button_state(is_valid)

    def _on_config_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._ui.error_label.set_text(str(error))
            self._ui.error_image.set_from_icon_name("lucide-circle-x-symbolic")
            self._ui.stack.set_visible_child_name("error")
            return

        self._set_form(result.form)
        self._ui.stack.set_visible_child_name("config")

    def _on_apply(self, button: Gtk.Button) -> None:
        assert self._data_form_widget is not None
        form = self._data_form_widget.get_submit_form()

        self._data_form_widget.set_sensitive(False)

        self._client.get_module("MUC").set_config(
            self._contact.jid, form, callback=self._on_finished
        )

    def _on_finished(self, task: Task) -> None:
        assert self._data_form_widget is not None
        self._data_form_widget.set_sensitive(True)
        self._data_form_widget.reset_form_hash()

        try:
            task.finish()
        except StanzaError as error:
            self._apply_button.set_error(str(error))
            return

        self._apply_button.set_success()
