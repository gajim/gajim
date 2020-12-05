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

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import get_group_chat_nick

from .groupchat_info import GroupChatInfoScrolled
from .groupchat_nick import NickChooser


class GroupChatInvitation(Gtk.ApplicationWindow):
    def __init__(self, account, event):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('GroupChatInvitation')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Group Chat Invitation'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self.account = account
        self._room_jid = str(event.muc)
        self._from = str(event.from_)
        self._password = event.password

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_valign(Gtk.Align.FILL)
        main_box.get_style_context().add_class('padding-18')

        muc_info_box = GroupChatInfoScrolled(account, {'minimal': True})
        muc_info_box.set_from_disco_info(event.info)

        main_box.add(muc_info_box)

        separator = Gtk.Separator()
        contact_label = Gtk.Label(label=event.get_inviter_name())
        contact_label.get_style_context().add_class('bold16')
        contact_label.set_halign(Gtk.Align.CENTER)
        contact_label.set_justify(Gtk.Justification.CENTER)
        contact_label.set_line_wrap(True)
        invitation_label = Gtk.Label(
            label=_('has invited you to a group chat.\nDo you want to join?'))
        invitation_label.set_halign(Gtk.Align.CENTER)
        invitation_label.set_justify(Gtk.Justification.CENTER)
        invitation_label.set_max_width_chars(50)
        invitation_label.set_line_wrap(True)

        main_box.add(separator)
        main_box.add(contact_label)
        main_box.add(invitation_label)

        decline_button = Gtk.Button.new_with_mnemonic(_('_Decline'))
        decline_button.set_halign(Gtk.Align.START)
        decline_button.connect('clicked', self._on_decline)

        self._nick_chooser = NickChooser()
        self._nick_chooser.set_text(
            get_group_chat_nick(self.account, event.info.jid))

        join_button = Gtk.Button.new_with_mnemonic(_('_Join'))
        join_button.set_halign(Gtk.Align.END)
        join_button.get_style_context().add_class('suggested-action')
        join_button.connect('clicked', self._on_join)

        join_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        join_box.get_style_context().add_class('linked')
        join_box.set_halign(Gtk.Align.END)
        join_box.add(self._nick_chooser)
        join_box.add(join_button)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_margin_top(6)
        button_box.pack_start(decline_button, False, False, 0)
        button_box.pack_end(join_box, False, False, 0)

        main_box.add(button_box)

        self.connect('key-press-event', self._on_key_press_event)

        self.add(main_box)

        join_button.set_can_default(True)
        join_button.grab_focus()

        self.show_all()

    def _on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_join(self, _widget):
        nickname = self._nick_chooser.get_text()
        app.interface.show_or_join_groupchat(self.account,
                                             self._room_jid,
                                             nick=nickname,
                                             password=self._password)
        self.destroy()

    def _on_decline(self, _widget):
        app.connections[self.account].get_module('MUC').decline(
            self._room_jid, self._from)
        self.destroy()
