# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk

from gajim.common.const import AvatarSize
from gajim.common.const import EncryptionInfoMsg
from gajim.common.events import EncryptionInfo
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.util.datetime import utc_now

from ...util import open_window
from .base import BaseRow
from .widgets import DateTimeLabel
from .widgets import SimpleLabel


class EncryptionInfoRow(BaseRow):
    def __init__(self, event: EncryptionInfo) -> None:
        BaseRow.__init__(self, event.account)

        self.type = 'encryption_info'
        timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self._event = event

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)

        icon = Gtk.Image.new_from_icon_name('channel-secure-symbolic',
                                            Gtk.IconSize.LARGE_TOOLBAR)
        icon.get_style_context().add_class('dim-label')
        avatar_placeholder.add(icon)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        timestamp_widget.set_margin_start(0)
        self.grid.attach(timestamp_widget, 1, 0, 1, 1)

        self._label = SimpleLabel()
        self._label.set_text(event.message.value)
        self.grid.attach(self._label, 1, 1, 1, 1)

        if event.message in (EncryptionInfoMsg.NO_FINGERPRINTS,
                             EncryptionInfoMsg.UNDECIDED_FINGERPRINTS):
            button = Gtk.Button(label=_('Manage Trust'))
            button.set_halign(Gtk.Align.START)
            button.connect('clicked', self._on_manage_trust_clicked)
            self.grid.attach(button, 1, 2, 1, 1)

        self.show_all()

    def _on_manage_trust_clicked(self, _button: Gtk.Button) -> None:
        contact = self._client.get_module('Contacts').get_contact(
            self._event.jid)
        if contact.is_groupchat:
            open_window('GroupchatDetails',
                        contact=contact,
                        page='encryption-omemo')
            return

        if isinstance(contact, BareContact) and contact.is_self:
            window = open_window('AccountsWindow')
            window.select_account(contact.account, page='encryption-omemo')
            return

        open_window('ContactInfo',
                    account=contact.account,
                    contact=contact,
                    page='encryption-omemo')
