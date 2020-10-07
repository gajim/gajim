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

from gajim.common.const import THRESHOLD_OPTIONS
from gajim.common.i18n import _

from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.settings import SettingsBox


class GroupChatSettings(SettingsBox):
    def __init__(self, account, jid, context):
        SettingsBox.__init__(self, account, jid)

        self.get_style_context().add_class('settings-border')
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_valign(Gtk.Align.START)
        self.set_halign(Gtk.Align.CENTER)

        chat_state = {
            'disabled': _('Disabled'),
            'composing_only': _('Composing Only'),
            'all': _('All Chat States')
        }

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Show Join/Leave'),
                    SettingType.GROUP_CHAT,
                    'print_join_left'),

            Setting(SettingKind.SWITCH,
                    _('Show Status Changes'),
                    SettingType.GROUP_CHAT,
                    'print_status'),

            Setting(SettingKind.SWITCH,
                    _('Notify on all Messages'),
                    SettingType.GROUP_CHAT,
                    'notify_on_all_messages',
                    context=context),

            Setting(SettingKind.SWITCH,
                    _('Minimize on Close'),
                    SettingType.GROUP_CHAT,
                    'minimize_on_close'),

            Setting(SettingKind.SWITCH,
                    _('Minimize When Joining Automatically'),
                    SettingType.GROUP_CHAT,
                    'minimize_on_autojoin'),

            Setting(SettingKind.POPOVER,
                    _('Send Chat State'),
                    SettingType.GROUP_CHAT,
                    'send_chatstate',
                    props={'entries': chat_state}),

            Setting(SettingKind.SWITCH,
                    _('Send Chat Markers'),
                    SettingType.GROUP_CHAT,
                    'send_marker',
                    context=context,
                    desc=_('Let others know if you read up to this point')),

            Setting(SettingKind.POPOVER,
                    _('Sync Threshold'),
                    SettingType.GROUP_CHAT,
                    'sync_threshold',
                    context=context,
                    props={'entries': THRESHOLD_OPTIONS}),

        ]

        for setting in settings:
            self.add_setting(setting)
        self.update_states()
