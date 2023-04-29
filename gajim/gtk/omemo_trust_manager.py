# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# OMEMO Gajim Plugin is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# OMEMO Gajim Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OMEMO Gajim Plugin. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Optional
from typing import Union

import locale
import logging
import time

from gi.repository import GdkPixbuf
from gi.repository import Gtk
from nbxmpp.protocol import JID
from omemo_dr.identitykeypair import IdentityKeyPair

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.const import XmppUriQuery
from gajim.common.events import AccountConnected
from gajim.common.events import AccountDisconnected
from gajim.common.ged import EventHelper
from gajim.common.helpers import generate_qr_code
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.omemo.util import get_fingerprint
from gajim.common.omemo.util import IdentityKeyExtended
from gajim.common.omemo.util import Trust

from .builder import get_builder
from .dialogs import ConfirmationDialog
from .dialogs import DialogButton
from .util import open_window

log = logging.getLogger('gajim.gui.omemo_trust_dialog')


TRUST_DATA = {
    Trust.UNTRUSTED: ('dialog-error-symbolic',
                      _('Untrusted'),
                      'error-color'),
    Trust.UNDECIDED: ('security-low-symbolic',
                      _('Not Decided'),
                      'warning-color'),
    Trust.VERIFIED: ('security-high-symbolic',
                     _('Verified'),
                     'encrypted-color'),
    Trust.BLIND: ('security-medium-symbolic',
                  _('Blind Trust'),
                  'encrypted-color')
}


class OMEMOTrustManager(Gtk.Box, EventHelper):
    def __init__(self,
                 account: str,
                 contact: Optional[types.ChatContactT] = None
                 ) -> None:

        Gtk.Box.__init__(self)
        EventHelper.__init__(self)

        self._account = account
        self._contact = contact

        self._ui = get_builder('omemo_trust_manager.ui')
        self.add(self._ui.stack)

        self._ui.list.set_filter_func(self._filter_func, None)
        self._ui.list.set_sort_func(self._sort_func, None)

        self._ui.connect_signals(self)

        self.connect('destroy', self._on_destroy)
        self.show_all()

        self.register_events([
            ('account-connected', ged.GUI2, self._on_account_state),
            ('account-disconnected', ged.GUI2, self._on_account_state)
        ])

        if not app.account_is_connected(account):
            self._ui.stack.set_visible_child_name('no-connection')
            return

        self._update()

    def _update(self) -> None:
        client = app.get_client(self._account)
        if self._contact is None:
            self._contact = client.get_module('Contacts').get_contact(
                client.get_own_jid().bare)

        if isinstance(self._contact, BareContact) and self._contact.is_self:
            header_text = _('Other devices connected with your account')
            popover_qr_text = _('Compare this code with the one shown on your '
                                'contact’s screen to ensure the safety of '
                                'your end-to-end encrypted chat.')
        else:
            header_text = _('Devices connected with "%s"') % self._contact.name
            popover_qr_text = _('Compare this code with the one shown on your '
                                'contact’s screen to ensure the safety of '
                                'your end-to-end encrypted chat '
                                'with %s.') % self._contact.name

        self._ui.list_heading.set_text(header_text)
        self._ui.comparing_instructions.set_text(popover_qr_text)

        self._omemo = client.get_module('OMEMO')

        self._identity_key = cast(
            IdentityKeyPair, self._omemo.backend.storage.getIdentityKeyPair())
        our_fpr_formatted = get_fingerprint(self._identity_key, formatted=True)
        self._ui.our_fingerprint_1.set_text(our_fpr_formatted)
        self._ui.our_fingerprint_2.set_text(our_fpr_formatted)

        self.update()
        self._load_qrcode()

    def update(self) -> None:
        assert self._contact is not None
        self._ui.list.foreach(self._ui.list.remove)

        if isinstance(self._contact, BareContact) and self._contact.is_self:
            self._ui.clear_devices_button.show()
            self._ui.list_heading_box.set_halign(Gtk.Align.START)
        else:
            self._ui.manage_trust_button.show()
            if self._contact.is_groupchat:
                self._ui.search_button.show()
            else:
                self._ui.list_heading_box.set_halign(Gtk.Align.START)

        self._load_fingerprints(self._contact)

    def _on_destroy(self, *args: Any) -> None:
        self.unregister_events()
        self._ui.list.set_filter_func(None)
        self._ui.search.disconnect_by_func(  # pyright: ignore
            self._on_search_changed)
        app.check_finalize(self)

    def _on_account_state(self,
                          event: Union[AccountConnected, AccountDisconnected]
                          ) -> None:

        if not app.account_is_connected(self._account):
            return

        if isinstance(event, AccountConnected):
            self._update()
            self._ui.stack.set_visible_child_name('manage-keys')
        else:
            self._ui.stack.set_visible_child_name('no-connection')

    def _filter_func(self, row: KeyRow, _user_data: Any) -> bool:
        search_text = self._ui.search.get_text()
        if search_text and search_text.lower() not in str(row.jid):
            return False
        if self._ui.show_inactive_switch.get_active():
            return True
        return row.active

    @staticmethod
    def _sort_func(row1: KeyRow, row2: KeyRow, _user_data: Any) -> int:
        result = locale.strcoll(str(row1.jid), str(row2.jid))
        if result != 0:
            return result

        if row1.active != row2.active:
            return -1 if row1.active else 1

        if row1.trust != row2.trust:
            return -1 if row1.trust > row2.trust else 1
        return 0

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self._ui.list.invalidate_filter()

    def _load_fingerprints(self, contact: types.ChatContactT) -> None:
        if contact.is_groupchat:
            members = list(self._omemo.backend.get_muc_members(
                str(contact.jid)))
            sessions = self._omemo.backend.storage.getSessionsFromJids(members)
            results = self._omemo.backend.storage.getMucFingerprints(members)
        else:
            sessions = self._omemo.backend.storage.getSessionsFromJid(
                str(contact.jid))
            results = self._omemo.backend.storage.getFingerprints(
                str(contact.jid))

        rows: dict[IdentityKeyExtended, KeyRow] = {}
        for result in results:
            rows[result.public_key] = KeyRow(contact,
                                             result.recipient_id,
                                             result.public_key,
                                             result.trust,
                                             result.timestamp)

        for item in sessions:
            if item.record.isFresh():
                return
            identity_key = item.record.getSessionState().getRemoteIdentityKey()
            identity_key = IdentityKeyExtended(identity_key.getPublicKey())
            try:
                key_row = rows[identity_key]
            except KeyError:
                log.warning('Could not find session identitykey %s',
                            item.device_id)
                self._omemo.backend.storage.deleteSession(item.recipient_id,
                                                          item.device_id)
                continue

            key_row.active = item.active
            key_row.device_id = item.device_id

        for row in rows.values():
            self._ui.list.add(row)

    @staticmethod
    def _get_qrcode(jid: JID,
                    sid: int,
                    identity_key: IdentityKeyPair
                    ) -> GdkPixbuf.Pixbuf | None:

        fingerprint = get_fingerprint(identity_key)
        qry = (XmppUriQuery.MESSAGE.value, [(f'omemo-sid-{sid}', fingerprint)])
        ver_string = jid.new_as_bare().to_iri(qry)
        log.debug('Verification String: %s', ver_string)
        return generate_qr_code(ver_string)

    def _load_qrcode(self) -> None:
        client = app.get_client(self._account)
        pixbuf = self._get_qrcode(client.get_own_jid(),
                                  self._omemo.backend.own_device,
                                  self._identity_key)
        self._ui.qr_code_image.set_from_pixbuf(pixbuf)

    def _on_show_inactive(self, switch: Gtk.Switch, _param: Any) -> None:
        self._ui.list.invalidate_filter()

    def _on_clear_devices_clicked(self, _button: Gtk.Button) -> None:
        def _clear():
            self._omemo.clear_devicelist()

        ConfirmationDialog(
            _('Clear Devices'),
            _('Clear Devices Now?'),
            _('This will clear the devices store for your account.'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Clear Devices'),
                               callback=_clear)],
            transient_for=cast(Gtk.Window, self.get_toplevel())).show()

    def _on_manage_trust_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        window = open_window('AccountsWindow')
        window.select_account(self._contact.account, 'encryption-omemo')


class KeyRow(Gtk.ListBoxRow):
    def __init__(self,
                 contact: types.ChatContactT,
                 jid: JID,
                 identity_key: IdentityKeyExtended,
                 trust: Trust,
                 last_seen: Optional[float]
                 ) -> None:

        Gtk.ListBoxRow.__init__(self)
        self.set_activatable(False)

        self._active = False
        self._device_id: Optional[int] = None
        self._identity_key = identity_key
        self.trust = trust
        self.jid = jid

        client = app.get_client(contact.account)
        self._omemo = client.get_module('OMEMO')

        grid = Gtk.Grid()
        grid.set_column_spacing(12)

        self._trust_button = TrustButton(self)
        grid.attach(self._trust_button, 1, 1, 1, 3)

        if contact.is_groupchat:
            jid_label = Gtk.Label(label=str(jid))
            jid_label.set_selectable(False)
            jid_label.set_halign(Gtk.Align.START)
            jid_label.set_valign(Gtk.Align.START)
            jid_label.set_hexpand(True)
            grid.attach(jid_label, 2, 1, 1, 1)

        self.fingerprint = Gtk.Label(
            label=self._identity_key.get_fingerprint(formatted=True))
        self.fingerprint.get_style_context().add_class('monospace')
        self.fingerprint.get_style_context().add_class('small-label')
        self.fingerprint.get_style_context().add_class('dim-label')
        self.fingerprint.set_selectable(True)
        self.fingerprint.set_halign(Gtk.Align.START)
        self.fingerprint.set_valign(Gtk.Align.START)
        self.fingerprint.set_hexpand(True)
        grid.attach(self.fingerprint, 2, 2, 1, 1)

        if last_seen is not None:
            last_seen_str = time.strftime(app.settings.get('date_time_format'),
                                          time.localtime(last_seen))
        else:
            last_seen_str = _('Never')
        last_seen_label = Gtk.Label(label=_('Last seen: %s') % last_seen_str)
        last_seen_label.set_halign(Gtk.Align.START)
        last_seen_label.set_valign(Gtk.Align.START)
        last_seen_label.set_hexpand(True)
        last_seen_label.get_style_context().add_class('small-label')
        last_seen_label.get_style_context().add_class('dim-label')
        grid.attach(last_seen_label, 2, 3, 1, 1)

        self.add(grid)

        self.connect('destroy', self._on_destroy)
        self.show_all()

    def _on_destroy(self, *args: Any) -> None:
        app.check_finalize(self)

    def delete_fingerprint(self, *args: Any) -> None:

        def _remove():
            self._omemo.backend.remove_device(str(self.jid), self.device_id)
            self._omemo.backend.storage.deleteSession(
                str(self.jid), self.device_id)
            self._omemo.backend.storage.deleteIdentity(
                str(self.jid), self._identity_key)

            listbox = cast(Gtk.ListBox, self.get_parent())
            listbox.remove(self)
            self.destroy()

        ConfirmationDialog(
            _('Delete'),
            _('Delete Fingerprint'),
            _('Doing so will permanently delete this Fingerprint'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               text=_('Delete'),
                               callback=_remove)],
            transient_for=cast(Gtk.Window, self.get_toplevel())).show()

    def set_trust(self) -> None:
        icon_name, tooltip, css_class = TRUST_DATA[self.trust]
        image = cast(Gtk.Image, self._trust_button.get_child())
        image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        image.get_style_context().add_class(css_class)
        image.set_tooltip_text(tooltip)

        self._omemo.backend.storage.setTrust(
            str(self.jid), self._identity_key, self.trust)

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, active: bool) -> None:
        context = self.fingerprint.get_style_context()
        self._active = bool(active)
        if self._active:
            context.remove_class('omemo-inactive-color')
        else:
            context.add_class('omemo-inactive-color')
        self._trust_button.update()

    @property
    def device_id(self) -> Optional[int]:
        return self._device_id

    @device_id.setter
    def device_id(self, device_id: int) -> None:
        self._device_id = device_id


class TrustButton(Gtk.MenuButton):
    def __init__(self, row: KeyRow) -> None:
        Gtk.MenuButton.__init__(self)
        self._row = row
        self._css_class = ''
        self._trust_popover = TrustPopver(row)
        self.set_popover(self._trust_popover)
        self.set_valign(Gtk.Align.CENTER)
        self.update()
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args: Any) -> None:
        self._trust_popover.destroy()
        app.check_finalize(self)

    def update(self) -> None:
        icon_name, tooltip, css_class = TRUST_DATA[self._row.trust]
        image = cast(Gtk.Image, self.get_child())
        image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        image.get_style_context().remove_class(self._css_class)

        if not self._row.active:
            css_class = 'omemo-inactive-color'
            tooltip = '%s - %s' % (_('Inactive'), tooltip)

        image.get_style_context().add_class(css_class)
        self._css_class = css_class
        self.set_tooltip_text(tooltip)


class TrustPopver(Gtk.Popover):
    def __init__(self, row: KeyRow) -> None:
        Gtk.Popover.__init__(self)
        self._row = row
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.update()
        self.add(self._listbox)
        self._listbox.show_all()
        self._listbox.connect('row-activated', self._activated)
        self.get_style_context().add_class('omemo-trust-popover')

    def _activated(self, _listbox: Gtk.ListBox, row: MenuOption) -> None:
        self.popdown()
        if row.type_ is None:
            self._row.delete_fingerprint()
        else:
            self._row.trust = row.type_
            self._row.set_trust()
            trust_button = cast(TrustButton, self.get_relative_to())
            trust_button.update()
            self.update()

    def update(self) -> None:
        self._listbox.foreach(self._listbox.remove)
        if self._row.trust != Trust.VERIFIED:
            self._listbox.add(VerifiedOption())
        if self._row.trust != Trust.BLIND:
            self._listbox.add(BlindOption())
        if self._row.trust != Trust.UNTRUSTED:
            self._listbox.add(NotTrustedOption())
        self._listbox.add(DeleteOption())


class MenuOption(Gtk.ListBoxRow):
    def __init__(self,
                 icon: str,
                 label_text: str,
                 color: str,
                 type_: Optional[Trust] = None
                 ) -> None:

        Gtk.ListBoxRow.__init__(self)

        self.type_ = type_
        self.icon = icon
        self.label = label_text
        self.color = color

        box = Gtk.Box()
        box.set_spacing(6)

        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        label = Gtk.Label(label=label_text)
        image.get_style_context().add_class(color)

        box.add(image)
        box.add(label)
        self.add(box)
        self.show_all()


class BlindOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(self,
                            'security-medium-symbolic',
                            _('Blind Trust'),
                            'encrypted-color',
                            Trust.BLIND)


class VerifiedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(self,
                            'security-high-symbolic',
                            _('Verified'),
                            'encrypted-color',
                            Trust.VERIFIED)


class NotTrustedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(self,
                            'dialog-error-symbolic',
                            _('Untrusted'),
                            'error-color',
                            Trust.UNTRUSTED)


class DeleteOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(self,
                            'user-trash-symbolic',
                            _('Delete'),
                            '')
