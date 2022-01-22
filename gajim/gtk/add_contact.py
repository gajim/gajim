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
from typing import Optional
from typing import Union

import logging

from gi.repository import Gtk

from nbxmpp import JID
from nbxmpp import Namespace
from nbxmpp.errors import is_error
from nbxmpp.errors import StanzaError
from nbxmpp.structs import DiscoInfo

from gajim.common import app
from gajim.common import types
from gajim.common.helpers import get_subscription_request_msg
from gajim.common.helpers import validate_jid
from gajim.common.i18n import _
from gajim.common.modules.util import as_task

from .assistant import Assistant
from .assistant import Page
from .assistant import ErrorPage
from .assistant import ProgressPage
from .groupchat_info import GroupChatInfoScrolled
from .builder import get_builder
from .util import open_window

log = logging.getLogger('gajim.gui.add_contact')


class AddContact(Assistant):
    def __init__(self,
                 account: Optional[str] = None,
                 jid: Optional[JID] = None,
                 nick: Optional[str] = None):
        Assistant.__init__(self)
        self.account = account
        self.jid = jid
        self._nick = nick

        self._result: Union[DiscoInfo, StanzaError, None] = None

        self.add_button('next', _('Next'), complete=True,
                        css_class='suggested-action')
        self.add_button('back', _('Back'))
        self.add_button('add', _('Add Contact'),
                        css_class='suggested-action')
        self.add_button('join', _('Join…'),
                        css_class='suggested-action')

        self.add_pages({
            'address': Address(account, jid),
            'error': Error(),
            'contact': Contact(),
            'groupchat': GroupChat(),
            'gateway': Gateway(),
        })

        progress = cast(ProgressPage, self.add_default_page('progress'))
        progress.set_title(_('Gathering information…'))
        progress.set_text(_('Trying to gather information on this address…'))

        self.connect('button-clicked', self._on_button_clicked)
        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _on_destroy(self, *args: Any) -> None:
        app.check_finalize(self)

    def _on_button_clicked(self,
                           _assistant: Assistant,
                           button_name: str
                           ) -> None:
        page = self.get_current_page()
        address_page = cast(Address, self.get_page('address'))
        account, _ = address_page.get_account_and_jid()

        if button_name == 'next':
            self._start_disco()
            return

        if button_name == 'back':
            self.show_page('address',
                           Gtk.StackTransitionType.SLIDE_RIGHT)
            address_page.focus()
            return

        if button_name == 'add':
            client = app.get_client(account)
            if page == 'contact':
                contact_page = cast(Contact, self.get_page('contact'))
                data = contact_page.get_subscription_data()
                client.get_module('Presence').subscribe(
                    self._result.jid,
                    msg=data['message'],
                    groups=data['groups'],
                    auto_auth=data['auto_auth'])
            else:
                client.get_module('Presence').subscribe(
                    self._result.jid,
                    name=self._result.gateway_name,
                    auto_auth=True)
            app.window.show_account_page(account)
            self.destroy()
            return

        if button_name == 'join':
            _, jid = address_page.get_account_and_jid()
            open_window('GroupchatJoin', account=account, jid=jid)
            self.destroy()

    def _start_disco(self) -> None:
        self._result = None
        self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)

        address_page = cast(Address, self.get_page('address'))
        account, jid = address_page.get_account_and_jid()
        assert account is not None
        self._disco_info(account, jid)

    @as_task
    def _disco_info(self, account: str, address: str) -> Any:
        _task = yield

        client = app.get_client(account)

        result = yield client.get_module('Discovery').disco_info(address)
        if is_error(result):
            assert isinstance(result, StanzaError)
            self._process_error(account, result)
            raise result

        log.info('Disco Info received: %s', address)
        assert isinstance(result, DiscoInfo)
        self._process_info(account, result)

    def _process_error(self, account: str, result: StanzaError) -> None:
        log.debug('Error received: %s', result)
        self._result = result

        contact_conditions = [
            'service-unavailable',  # Prosody
            'subscription-required'  # ejabberd
        ]
        if result.condition in contact_conditions:
            # It seems to be a contact
            address_page = cast(Contact, self.get_page('contact'))
            address_page.prepare(account, result)
            self.show_page('contact', Gtk.StackTransitionType.SLIDE_LEFT)
        else:
            error_page = cast(ErrorPage, self.get_page('error'))
            error_page.set_text(result.get_text())
            self.show_page('error', Gtk.StackTransitionType.SLIDE_LEFT)

    def _process_info(self, account: str, result: DiscoInfo) -> None:
        log.debug('Info received: %s', result)
        self._result = result

        if result.is_muc:
            for identity in result.identities:
                if identity.type == 'text' and result.jid.is_domain:
                    # It's a group chat component advertising
                    # category 'conference'
                    error_page = cast(ErrorPage, self.get_page('error'))
                    error_page.set_text(
                        _('This address does not seem to offer any gateway '
                          'service.'))
                    self.show_page('error')
                    return

                if identity.type == 'irc' and result.jid.is_domain:
                    # It's an IRC gateway advertising category 'conference'
                    gateway_page = cast(Gateway, self.get_page('gateway'))
                    gateway_page.prepare(account, result)
                    self.show_page(
                        'gateway', Gtk.StackTransitionType.SLIDE_LEFT)
                    return

            groupchat_page = cast(GroupChat, self.get_page('groupchat'))
            groupchat_page.prepare(account, result)
            self.show_page('groupchat', Gtk.StackTransitionType.SLIDE_LEFT)
            return

        if result.is_gateway:
            gateway_page = cast(Gateway, self.get_page('gateway'))
            gateway_page.prepare(account, result)
            self.show_page('gateway', Gtk.StackTransitionType.SLIDE_LEFT)
            return

        contact_page = cast(Contact, self.get_page('contact'))
        contact_page.prepare(account, result)
        self.show_page('contact', Gtk.StackTransitionType.SLIDE_LEFT)


class Address(Page):
    def __init__(self, account: Optional[str], jid: Optional[JID]) -> None:
        Page.__init__(self)
        self.title = _('Add Contact')

        self._account = account
        self._jid = jid

        self._ui = get_builder('add_contact.ui')
        self.add(self._ui.address_box)

        self._ui.account_combo.connect('changed', self._on_account_changed)
        self._ui.address_entry.connect('changed', self._set_complete)

        accounts = app.get_enabled_accounts_with_labels(connected_only=True)
        liststore = self._ui.account_combo.get_model()
        assert isinstance(liststore, Gtk.ListStore)
        for acc in accounts:
            liststore.append(acc)

        if len(accounts) > 1:
            self._ui.account_box.show()

            if account is not None:
                self._ui.account_combo.set_active_id(account)
            else:
                self._ui.account_combo.set_active(0)
        else:
            # Set to first (and only) item; sets self._account automatically
            self._ui.account_combo.set_active(0)

        if jid is not None:
            self._ui.address_entry.set_text(str(jid))

        self._set_complete()

        self.show_all()

    def get_visible_buttons(self) -> list[str]:
        return ['next']

    def get_default_button(self) -> str:
        return 'next'

    def get_account_and_jid(self) -> tuple[str, str]:
        assert self._account is not None
        return self._account, self._ui.address_entry.get_text()

    def focus(self) -> None:
        self._ui.address_entry.grab_focus()

    def _on_account_changed(self, combobox: Gtk.ComboBox) -> None:
        account = combobox.get_active_id()
        self._account = account
        self._set_complete()

    def _show_icon(self, show: bool) -> None:
        icon = 'dialog-warning-symbolic' if show else None
        self._ui.address_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon)

    def _set_complete(self, *args: Any) -> None:
        if self._account is None:
            self.complete = False
            self.update_page_complete()
            return

        address = self._ui.address_entry.get_text()
        is_self = bool(address == app.get_jid_from_account(self._account))
        if is_self:
            self._show_icon(True)
            self._ui.address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY,
                _('You cannot add yourself to your contact list.'))
            self.complete = False
            self.update_page_complete()
            return

        client = app.get_client(self._account)
        for contact in client.get_module('Roster').iter_contacts():
            if address == str(contact.jid):
                self._show_icon(True)
                self._ui.address_entry.set_icon_tooltip_text(
                    Gtk.EntryIconPosition.SECONDARY,
                    _('%s is already in your contact list') % address)
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
            self._ui.address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _('Invalid Address'))
            return False

        self._show_icon(False)
        return True


class Error(ErrorPage):
    def __init__(self) -> None:
        ErrorPage.__init__(self)
        self.set_title(_('Add Contact'))
        self.set_heading(_('An Error Occurred'))

    def get_visible_buttons(self) -> list[str]:
        return ['back']

    def get_default_button(self) -> str:
        return 'back'


class Contact(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _('Add Contact')

        self._result: Union[DiscoInfo, StanzaError, None] = None
        self._account: Optional[str] = None
        self._contact: Optional[types.BareContact] = None

        self._ui = get_builder('add_contact.ui')
        self.add(self._ui.contact_grid)

        self._ui.contact_info_button.connect('clicked', self._on_info_clicked)

        self.show_all()

    def get_visible_buttons(self) -> list[str]:
        return ['back', 'add']

    def get_default_button(self) -> str:
        return 'add'

    def prepare(self, account: str, result: Union[DiscoInfo, StanzaError]):
        self._result = result
        self._account = account

        client = app.get_client(account)
        self._contact = client.get_module('Contacts').get_contact(result.jid)

        self._update_groups(account)
        self._ui.message_entry.set_text(get_subscription_request_msg(account))
        self._ui.contact_grid.set_sensitive(True)

    def _update_groups(self, account: str) -> None:
        model = self._ui.group_combo.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.clear()
        client = app.get_client(account)
        for group in client.get_module('Roster').get_groups():
            self._ui.group_combo.append_text(group)

    def _on_info_clicked(self, _button: Gtk.Button) -> None:
        open_window(
            'ContactInfo', account=self._account, contact=self._contact)

    def get_subscription_data(self) -> dict[str, Union[str, list[str], bool]]:
        group = self._ui.group_combo.get_child().get_text()
        groups = [group] if group else []
        return {
            'message': self._ui.message_entry.get_text(),
            'groups': groups,
            'auto_auth': self._ui.status_switch.get_active(),
        }


class Gateway(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _('Service Gateway')

        self._account: Optional[str] = None
        self._result: Optional[DiscoInfo] = None

        self._ui = get_builder('add_contact.ui')
        self.add(self._ui.gateway_box)

        self._ui.register_button.connect('clicked', self._on_register_clicked)
        self._ui.commands_button.connect('clicked', self._on_command_clicked)

        self.show_all()

    def get_visible_buttons(self) -> list[str]:
        return ['back', 'add']

    def get_default_button(self) -> str:
        return 'add'

    def prepare(self, account: str, result: DiscoInfo) -> None:
        self._account = account
        self._result = result

        icon_name = None
        if result.is_gateway:
            if result.gateway_type == 'sms':
                icon_name = 'gajim-agent-sms'
            if result.gateway_type == 'irc':
                icon_name = 'gajim-agent-irc'
            self._ui.gateway_image.set_from_icon_name(
                icon_name, Gtk.IconSize.DIALOG)
            gateway_name = result.gateway_name or self._result.jid
            if not result.gateway_type:
                self._ui.gateway_label.set_text(gateway_name)
            else:
                self._ui.gateway_label.set_text(
                    f'{gateway_name} ({result.gateway_type.upper()})')
        else:
            identity_name = ''
            identity_type = ''
            for identity in result.identities:
                if identity.type == 'sms':
                    icon_name = 'gajim-agent-sms'
                    identity_name = identity.name or self._result.jid
                    identity_type = identity.type
                if identity.type == 'irc':
                    icon_name = 'gajim-agent-irc'
                    identity_name = identity.name or self._result.jid
                    identity_type = identity.type
            self._ui.gateway_image.set_from_icon_name(
                icon_name, Gtk.IconSize.DIALOG)
            if not identity_type:
                self._ui.gateway_label.set_text(identity_name)
            else:
                self._ui.gateway_label.set_text(
                    f'{identity_name} ({identity_type.upper()})')

        if result.supports(Namespace.REGISTER):
            self._ui.register_button.set_sensitive(True)
            self._ui.register_button.set_tooltip_text('')
        else:
            self._ui.register_button.set_sensitive(False)
            self._ui.register_button.set_tooltip_text(
                _('This gateway does not support direct registering.'))

        if result.supports(Namespace.COMMANDS):
            self._ui.commands_button.set_sensitive(True)
            self._ui.commands_button.set_tooltip_text('')
        else:
            self._ui.commands_button.set_sensitive(False)
            self._ui.commands_button.set_tooltip_text(
                _('This gateway does not support Ad-Hoc Commands.'))

    def _on_register_clicked(self, _button: Gtk.Button) -> None:
        open_window(
            'ServiceRegistration',
            account=self._account,
            address=self._result.jid)

    def _on_command_clicked(self, _button: Gtk.Button) -> None:
        assert self._result is not None
        open_window(
            'AdHocCommand', account=self._account, jid=str(self._result.jid))


class GroupChat(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _('Join Group Chat?')

        self._result: Optional[DiscoInfo] = None

        heading = Gtk.Label(label=_('Join Group Chat?'))
        heading.get_style_context().add_class('large-header')
        heading.set_max_width_chars(30)
        heading.set_line_wrap(True)
        heading.set_halign(Gtk.Align.CENTER)
        heading.set_justify(Gtk.Justification.CENTER)
        self.pack_start(heading, False, True, 0)

        self._info_box = GroupChatInfoScrolled(minimal=True)
        self.pack_start(self._info_box, True, True, 0)

        self.show_all()

    def get_visible_buttons(self) -> list[str]:
        return ['back', 'join']

    def get_default_button(self) -> str:
        return 'join'

    def prepare(self, account: str, result: DiscoInfo) -> None:
        self._result = result

        self._info_box.set_account(account)
        self._info_box.set_from_disco_info(result)
