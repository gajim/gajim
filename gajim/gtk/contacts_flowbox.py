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

from typing import List

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _


class ContactItem(Gtk.FlowBoxChild):
    def __init__(self, account: str, jid: str, is_new: bool = False) -> None:
        Gtk.FlowBoxChild.__init__(self)
        self.set_size_request(150, -1)

        self.account = account
        self.jid = jid
        self.is_new = is_new

        name_label = Gtk.Label()
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(12)
        name_label.get_style_context().add_class('bold')

        if is_new:
            avatar_image =  Gtk.Image.new_from_icon_name(
                'avatar-default', Gtk.IconSize.DND)
            name_label.set_text(jid)
            name_label.set_tooltip_text(jid)
        else:
            client = app.get_client(account)
            contact = client.get_module('Contacts').get_contact(jid)
            surface = contact.get_avatar(
                AvatarSize.ROSTER, self.get_scale_factor())
            avatar_image = Gtk.Image.new_from_surface(surface)
            name_label.set_text(contact.name)
            name_label.set_tooltip_text(contact.name)

        remove_button = Gtk.Button.new_from_icon_name(
            'window-close', Gtk.IconSize.BUTTON)
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.set_halign(Gtk.Align.END)
        remove_button.set_hexpand(True)
        remove_button.set_relief(Gtk.ReliefStyle.NONE)
        remove_button.set_tooltip_text(_('Remove'))
        remove_button.connect('clicked', self._on_remove)

        box = Gtk.Box(spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        box.add(avatar_image)
        box.add(name_label)
        box.add(remove_button)
        box.get_style_context().add_class('contact-flowbox-item')
        self.add(box)
        self.show_all()

    def _on_remove(self, _button: Gtk.Button) -> None:
        self.get_parent().on_contact_removed(self)


class ContactsFlowBox(Gtk.FlowBox):

    __gsignals__ = {
        'contact-removed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str, bool)
        )
    }

    def __init__(self) -> None:
        Gtk.FlowBox.__init__(self)
        self.set_column_spacing(6)
        self.set_row_spacing(3)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_valign(Gtk.Align.START)
        self.show_all()

    def clear(self) -> None:
        def _remove(item):
            self.remove(item)
            item.destroy()
        self.foreach(_remove)

    def add_contact(self,
                    account: str,
                    jid: str,
                    is_new: bool = False
                    ) -> None:
        contact_item = ContactItem(account, jid, is_new=is_new)
        self.add(contact_item)

    def has_contacts(self) -> bool:
        return bool(self.get_child_at_index(0) is not None)

    def get_contact_jids(self) -> List[str]:
        contacts = []
        for contact in self.get_children():
            contacts.append(contact.jid)
        return contacts

    def on_contact_removed(self, row: ContactItem) -> None:
        account = row.account
        jid = row.jid
        is_new = row.is_new
        row.destroy()
        self.emit('contact-removed', account, jid, is_new)
