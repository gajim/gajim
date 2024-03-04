# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common.i18n import _

from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.settings import SettingsBox


class ContactSettings(SettingsBox):
    def __init__(self, account: str, jid: JID) -> None:
        SettingsBox.__init__(self, account, str(jid))
        self.get_style_context().add_class('border')
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_size_request(700, -1)
        self.set_valign(Gtk.Align.START)
        self.set_halign(Gtk.Align.CENTER)

        chat_state = {
            'disabled': _('Disabled'),
            'composing_only': _('Composing Only'),
            'all': _('All Chat States')
        }

        settings: list[Setting] = [
            Setting(SettingKind.POPOVER,
                    _('Send Chat State'),
                    SettingType.CONTACT,
                    'send_chatstate',
                    props={'entries': chat_state}),

            Setting(SettingKind.SWITCH,
                    _('Send Chat Markers'),
                    SettingType.CONTACT,
                    'send_marker',
                    desc=_('Let others know if you read up to this point')),
        ]

        for setting in settings:
            self.add_setting(setting)
        self.update_states()
