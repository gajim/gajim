# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import cast

import logging

from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.task import Task

from gajim.common.client import Client
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.gtk.builder import get_builder

from .apply_button_box import ApplyButtonBox
from .dataform import DataFormWidget

log = logging.getLogger('gajim.gui.groupchat_config')


class GroupchatConfig(Gtk.Box):
    def __init__(self, client: Client, contact: GroupchatContact) -> None:
        Gtk.Box.__init__(self)

        self._contact = contact
        self._client = client
        self._data_form_widget = cast(DataFormWidget, None)
        self_contact = self._contact.get_self()
        assert self_contact is not None

        self._own_affiliation = self_contact.affiliation

        self._ui = get_builder('groupchat_config.ui')

        self._apply_button = ApplyButtonBox(_('Apply'), self._on_apply)
        self._apply_button.set_halign(Gtk.Align.END)
        self._apply_button.get_style_context().add_class('margin-18')

        self._ui.config_box.pack_end(self._apply_button, False, True, 0)

        self.add(self._ui.stack)

        self.show_all()

        if self._own_affiliation.is_owner:
            self._ui.stack.set_visible_child_name('loading')
            self._client.get_module('MUC').request_config(
                self._contact.jid, callback=self._on_config_received)
        else:
            self._ui.error_label.set_text(
                _('You need Owner permission to change the configuration'))
            self._ui.error_image.set_from_icon_name('dialog-error',
                                                    Gtk.IconSize.DIALOG)
            self._ui.stack.set_visible_child_name('error')

    def _set_form(self, form: Any) -> None:
        self._data_form_widget = DataFormWidget(form)
        self._data_form_widget.connect('is-valid', self._on_is_valid)
        self._data_form_widget.show_all()
        self._ui.config_box.add(self._data_form_widget)
        self._ui.stack.set_visible_child_name('config')

    def _on_is_valid(self, _widget: Any, is_valid: bool) -> None:
        if not self._data_form_widget.was_modified():
            self._apply_button.set_button_state(False)
        else:
            self._apply_button.set_button_state(is_valid)

    def _on_config_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._ui.error_label.set_text(str(error))
            self._ui.error_image.set_from_icon_name('dialog-error',
                                                    Gtk.IconSize.DIALOG)
            self._ui.stack.set_visible_child_name('error')
            return

        self._set_form(result.form)
        self._ui.stack.set_visible_child_name('config')

    def _on_apply(self, button: Gtk.Button) -> None:
        form = self._data_form_widget.get_submit_form()

        self._data_form_widget.set_sensitive(False)

        self._client.get_module('MUC').set_config(self._contact.jid,
                                                  form,
                                                  callback=self._on_finished)

    def _on_finished(self, task: Task) -> None:
        self._data_form_widget.set_sensitive(True)
        self._data_form_widget.reset_form_hash()

        try:
            task.finish()
        except StanzaError as error:
            self._apply_button.set_error(str(error))
            return

        self._apply_button.set_success()
