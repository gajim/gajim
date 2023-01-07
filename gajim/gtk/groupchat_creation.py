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

from typing import Optional
from typing import Union

import logging
import random

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common.const import MUC_CREATION_EXAMPLES
from gajim.common.const import MUC_DISCO_ERRORS
from gajim.common.events import AccountConnected
from gajim.common.events import AccountDisconnected
from gajim.common.ged import EventHelper
from gajim.common.helpers import get_random_muc_localpart
from gajim.common.helpers import to_user_string
from gajim.common.helpers import validate_jid
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.util import ensure_not_destroyed

log = logging.getLogger('gajim.gtk.groupchat_creation')


class CreateGroupchatWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account: Optional[str]) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_name('CreateGroupchat')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(500, -1)
        self.set_show_menubar(False)
        self.set_resizable(True)
        self.set_title(_('Create Group Chat'))

        self._ui = get_builder('groupchat_creation.ui')
        self.add(self._ui.stack)

        self._account = account
        self._destroyed: bool = False

        self._create_entry_completion()

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)

        self.register_events([
            ('account-connected', ged.GUI2, self._on_account_state),
            ('account-disconnected', ged.GUI2, self._on_account_state)
        ])

        self.show_all()

        if app.get_number_of_connected_accounts() == 0:
            # This can happen under rare circumstances
            self._ui.stack.set_visible_child_name('no-connection')
            return

        self._update_accounts(account)

        self.set_focus(self._ui.address_entry)

    def _on_account_state(self,
                          _event: Union[AccountConnected, AccountDisconnected]
                          ) -> None:
        any_account_connected = app.get_number_of_connected_accounts() > 0
        if any_account_connected:
            self._ui.stack.set_visible_child_name('create')
            self._update_accounts()
        else:
            self._ui.stack.set_visible_child_name('no-connection')

    def _update_accounts(self, account: Optional[str] = None) -> None:
        accounts = app.get_enabled_accounts_with_labels(connected_only=True)
        account_liststore = self._ui.account_combo.get_model()
        assert isinstance(account_liststore, Gtk.ListStore)
        account_liststore.clear()

        for acc in accounts:
            account_liststore.append(acc)

        self._ui.account_combo.set_visible(len(accounts) != 1)
        self._ui.account_label.set_visible(len(accounts) != 1)

        if account is None:
            account = accounts[0][0]

        self._ui.account_combo.set_active_id(account)
        self._account = account
        self._fill_placeholders()

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
            _('e.g. %s') % placeholder[0])
        self._ui.description_entry.set_placeholder_text(
            _('e.g. %s') % placeholder[1])
        self._ui.address_entry.set_placeholder_text(
            f'{placeholder[2]}@{server}')

    def _get_muc_service_jid(self) -> str:
        assert self._account is not None
        client = app.get_client(self._account)
        return str(client.get_module('MUC').service_jid or 'muc.example.com')

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_account_combo_changed(self, combo: Gtk.ComboBox) -> None:
        self._account = combo.get_active_id()
        if self._account is None:
            model = combo.get_model()
            iter_ = model.get_iter_first()
            if not iter_:
                return
            self._account = model[iter_][0]
        self._fill_placeholders()

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
        condition = error.condition or ''
        if condition == 'gone':
            condition = 'already-exists'
        text = MUC_DISCO_ERRORS.get(condition, to_user_string(error))
        self._set_warning(text)

    def _set_warning_from_error_code(self, error_code: str) -> None:
        self._set_warning(MUC_DISCO_ERRORS[error_code])

    def _on_name_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._ui.private_radio.get_active():
            return

        name = entry.get_text()
        name = name.replace(' ', '-')
        server = self._get_muc_service_jid()
        self._ui.address_entry.set_text(f'{name.lower()}@{server}')

    def _on_address_entry_changed(self, entry: Gtk.Entry) -> None:
        text = entry.get_text()
        self._update_entry_completion(entry, text)
        self._validate_jid(text)

    def _update_entry_completion(self, entry: Gtk.Entry, text: str) -> None:
        text = entry.get_text()
        if '@' in text:
            text = text.split('@', 1)[0]

        model = entry.get_completion().get_model()
        assert isinstance(model, Gtk.ListStore)
        model.clear()

        server = self._get_muc_service_jid()
        model.append([f'{text}@{server}'])

    def _on_public_private_toggled(self, _radiobutton: Gtk.RadioButton) -> None:
        is_public = self._ui.public_radio.get_active()
        if is_public:
            self._validate_jid(self._ui.address_entry.get_text())
        else:
            self._ui.create_button.set_sensitive(True)
        self._ui.address_label.set_visible(is_public)
        self._ui.address_entry.set_visible(is_public)

    def _on_create_clicked(self, _button: Gtk.Button) -> None:
        assert self._account is not None
        if not app.account_is_available(self._account):
            ErrorDialog(
                _('Not Connected'),
                _('You have to be connected to create a group chat.'))
            return

        if self._ui.public_radio.get_active():
            room_jid = self._ui.address_entry.get_text()
        else:
            server = self._get_muc_service_jid()
            room_jid = f'{get_random_muc_localpart()}@{server}'

        self._set_processing_state(True)
        client = app.get_client(self._account)
        client.get_module('Discovery').disco_info(
            room_jid, callback=self._disco_info_received)

    @ensure_not_destroyed
    def _disco_info_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            if error.condition == 'item-not-found':
                assert error.jid is not None
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
        is_public = self._ui.public_radio.get_active()

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
        assert self._account is not None

        if app.window.chat_exists(self._account, JID.from_string(room_jid)):
            log.error('Trying to create groupchat '
                      'which is already added as chat')
            self.destroy()
            return

        client = app.get_client(self._account)
        client.get_module('MUC').create(room_jid, config)

        self.destroy()

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._destroyed = True
        self.unregister_events()
        app.check_finalize(self)
