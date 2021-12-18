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

import logging
import random

from gi.repository import Gtk
from gi.repository import Gdk

from nbxmpp.errors import StanzaError

from gajim.common import app
from gajim.common.const import MUC_CREATION_EXAMPLES
from gajim.common.const import MUC_DISCO_ERRORS
from gajim.common.i18n import _
from gajim.common.helpers import validate_jid
from gajim.common.helpers import to_user_string

from .dialogs import ErrorDialog
from .builder import get_builder
from .util import ensure_not_destroyed

log = logging.getLogger('gajim.gui.groupchat_creation')


class CreateGroupchatWindow(Gtk.ApplicationWindow):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('CreateGroupchat')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(500, -1)
        self.set_show_menubar(False)
        self.set_resizable(True)
        self.set_title(_('Create Group Chat'))

        self._ui = get_builder('groupchat_creation.ui')
        self.add(self._ui.create_group_chat)

        self._destroyed: bool = False

        self._account = self._fill_account_combo(account)

        self._create_entry_completion()
        self._fill_placeholders()

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press_event)
        self.connect('destroy', self._on_destroy)

        self.show_all()
        self.set_focus(self._ui.address_entry)

    def _get_muc_service_jid(self) -> str:
        con = app.connections[self._account]
        return str(con.get_module('MUC').service_jid or 'muc.example.com')

    def _fill_account_combo(self, account: str) -> str:
        accounts = app.get_enabled_accounts_with_labels(connected_only=True)
        account_liststore = self._ui.account_combo.get_model()
        for acc in accounts:
            account_liststore.append(acc)

        # Hide account combobox if there is only one account
        if len(accounts) == 1:
            self._ui.account_combo.hide()
            self._ui.account_label.hide()

        if account is None:
            account = accounts[0][0]

        self._ui.account_combo.set_active_id(account)
        return account

    def _create_entry_completion(self) -> None:
        entry_completion = Gtk.EntryCompletion()
        model = Gtk.ListStore(str)
        entry_completion.set_model(model)
        entry_completion.set_text_column(0)

        entry_completion.set_inline_completion(True)
        entry_completion.set_popup_single_match(False)

        self._ui.address_entry.set_completion(entry_completion)

    def _fill_placeholders(self) -> None:
        placeholder = random.choice(MUC_CREATION_EXAMPLES)
        server = self._get_muc_service_jid()

        self._ui.name_entry.set_placeholder_text(
            placeholder[0] + _(' (optional)...'))
        self._ui.description_entry.set_placeholder_text(
            placeholder[1] + _(' (optional)...'))
        self._ui.address_entry.set_placeholder_text(
            f'{placeholder[2]}@{server}')

    def _on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_account_combo_changed(self, combo):
        self._account = combo.get_active_id()
        self._fill_placeholders()

    def _update_entry_completion(self, entry, text):
        text = entry.get_text()
        if '@' in text:
            text = text.split('@', 1)[0]

        model = entry.get_completion().get_model()
        model.clear()

        server = self._get_muc_service_jid()
        model.append([f'{text}@{server}'])

    def _validate_jid(self, text: str) -> None:
        if not text:
            self._set_warning_icon(False)
            self._ui.create_button.set_sensitive(False)
            return

        try:
            jid = validate_jid(text)
            if jid.resource:
                raise ValueError

        except ValueError:
            self._set_warning(_('Invalid Address'))
        else:
            self._set_warning_icon(False)
            self._ui.create_button.set_sensitive(True)

    def _set_processing_state(self, enabled: bool) -> None:
        if enabled:
            self._ui.spinner.start()
            self._ui.create_button.set_sensitive(False)
        else:
            self._ui.spinner.stop()
        self._ui.grid.set_sensitive(not enabled)

    def _set_warning_icon(self, enabled: bool) -> None:
        icon = 'dialog-warning-symbolic' if enabled else None
        self._ui.address_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon)

    def _set_warning_tooltip(self, text: str) -> None:
        self._ui.address_entry.set_icon_tooltip_text(
            Gtk.EntryIconPosition.SECONDARY, text)

    def _set_warning(self, text: str) -> None:
        self._set_warning_icon(True)
        self._set_warning_tooltip(text)
        self._ui.create_button.set_sensitive(False)

    def _set_warning_from_error(self, error: StanzaError) -> None:
        condition = error.condition
        if condition == 'gone':
            condition = 'already-exists'
        text = MUC_DISCO_ERRORS.get(condition, to_user_string(error))
        self._set_warning(text)

    def _set_warning_from_error_code(self, error_code: str) -> None:
        self._set_warning(MUC_DISCO_ERRORS[error_code])

    def _on_address_entry_changed(self, entry):
        text = entry.get_text()
        self._update_entry_completion(entry, text)
        self._validate_jid(text)

    def _on_address_entry_activate(self, _widget):
        self._on_create_clicked()

    def _on_create_clicked(self, *args):
        if not app.account_is_available(self._account):
            ErrorDialog(
                _('Not Connected'),
                _('You have to be connected to create a group chat.'))
            return

        room_jid = self._ui.address_entry.get_text()

        self._set_processing_state(True)
        con = app.connections[self._account]
        con.get_module('Discovery').disco_info(
            room_jid, callback=self._disco_info_received)

    @ensure_not_destroyed
    def _disco_info_received(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            if error.condition == 'item-not-found':
                self._create_muc(error.jid)
                return
            self._set_warning_from_error(error)

        else:
            self._set_warning_from_error_code(
                'already-exists' if result.is_muc else 'not-muc-service')

        self._set_processing_state(False)

    def _create_muc(self, room_jid: str) -> None:
        name = self._ui.name_entry.get_text()
        description = self._ui.description_entry.get_text()
        is_public = self._ui.public_switch.get_active()

        config = {
            # XEP-0045 options
            'muc#roomconfig_roomname': name,
            'muc#roomconfig_roomdesc': description,
            'muc#roomconfig_publicroom': is_public,
            'muc#roomconfig_membersonly': not is_public,
            'muc#roomconfig_whois': 'moderators' if is_public else 'anyone',
            'muc#roomconfig_changesubject': not is_public,

            # Ejabberd options
            'public_list': is_public,
        }

        # Create new group chat by joining
        app.interface.create_groupchat(
            self._account,
            str(room_jid),
            config)

        self.destroy()

    def _on_destroy(self, *args):
        self._destroyed = True
