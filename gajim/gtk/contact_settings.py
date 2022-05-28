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

from gi.repository import Gtk

from nbxmpp.protocol import JID

from gajim.common.i18n import _

from .const import Setting
from .const import SettingKind
from .const import SettingType
from .settings import SettingsBox


class ContactSettings(SettingsBox):
    def __init__(self, account: str, jid: JID) -> None:
        SettingsBox.__init__(self, account, str(jid))
        self.get_style_context().add_class('settings-border')
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
