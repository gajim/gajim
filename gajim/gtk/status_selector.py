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
from gi.repository import Pango

from gajim.common import app
from gajim.common.helpers import get_uf_show
from gajim.common.helpers import get_global_show
from gajim.common.helpers import statuses_unified
from gajim.common.i18n import _
from gajim.dialogs import ChangeStatusMessageDialog

from gajim.gtk.util import get_icon_name


class StatusSelector(Gtk.MenuButton):
    def __init__(self, compact=False):
        Gtk.MenuButton.__init__(self)
        self.set_direction(Gtk.ArrowType.UP)
        self._compact = compact
        self._create_popover()

        self._current_show_icon = Gtk.Image()
        self._current_show_icon.set_from_icon_name(
            get_icon_name('offline'), Gtk.IconSize.MENU)

        box = Gtk.Box(spacing=6)
        box.add(self._current_show_icon)
        if not self._compact:
            self._current_show_label = Gtk.Label(label=get_uf_show('offline'))
            self._current_show_label.set_ellipsize(Pango.EllipsizeMode.END)
            self._current_show_label.set_halign(Gtk.Align.START)
            self._current_show_label.set_xalign(0)
            box.add(self._current_show_label)
        self.add(box)

    def _create_popover(self):
        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popover_box.get_style_context().add_class('margin-3')
        popover_items = [
            'online',
            'away',
            'xa',
            'dnd',
            'separator',
            'change_status_message',
            'separator',
            'offline',
        ]

        for item in popover_items:
            if item == 'separator':
                popover_box.add(Gtk.Separator())
                continue

            show_icon = Gtk.Image()
            show_label = Gtk.Label()
            show_label.set_halign(Gtk.Align.START)

            if item == 'change_status_message':
                show_icon.set_from_icon_name('document-edit-symbolic',
                                             Gtk.IconSize.MENU)
                show_label.set_text_with_mnemonic(_('_Change Status Message'))
            else:
                show_icon.set_from_icon_name(get_icon_name(item),
                                             Gtk.IconSize.MENU)
                show_label.set_text_with_mnemonic(
                    get_uf_show(item, use_mnemonic=True))

            show_box = Gtk.Box(spacing=6)
            show_box.add(show_icon)
            show_box.add(show_label)

            button = Gtk.Button()
            button.set_name(item)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(show_box)
            button.connect('clicked', self._on_change_status)

            if item == 'change_status_message':
                self._change_status_message = button

            popover_box.add(button)

        popover_box.show_all()
        self._status_popover = Gtk.Popover()
        self._status_popover.add(popover_box)
        self.set_popover(self._status_popover)

    def _on_change_status(self, button):
        def _on_response(message, pep_dict):
            if message is None:  # None if user pressed Cancel
                return
            for account in app.contacts.get_accounts():
                sync_account = app.config.get_per(
                    'accounts', account, 'sync_with_global_status')
                if not sync_account:
                    continue
                app.interface.roster.send_status(account, new_show, message)
                app.interface.roster.send_pep(account, pep_dict)

        self._status_popover.popdown()
        new_show = button.get_name()
        if new_show == 'change_status_message':
            new_show = get_global_show()
            ChangeStatusMessageDialog(_on_response, new_show)
            return

        app.interface.roster.get_status_message(new_show, _on_response)

    def update(self):
        show = get_global_show()
        uf_show = get_uf_show(show)
        self._current_show_icon.set_from_icon_name(
            get_icon_name(show), Gtk.IconSize.MENU)
        if statuses_unified():
            self._current_show_icon.set_tooltip_text(_('Status: %s') % uf_show)
            if not self._compact:
                self._current_show_label.set_text(uf_show)
        else:
            show_label = _('%s (desynced)') % uf_show
            self._current_show_icon.set_tooltip_text(
                _('Status: %s') % show_label)
            if not self._compact:
                self._current_show_label.set_text(show_label)

        self._change_status_message.set_sensitive(show != 'offline')
