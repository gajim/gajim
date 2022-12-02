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

from datetime import datetime

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import types
from gajim.common.const import KindConstant
from gajim.common.helpers import from_one_line
from gajim.common.i18n import _
from gajim.common.storage.archive import ReferredMessageRow


class ReferredMessageWidget(Gtk.Box):
    def __init__(self,
                 contact: types.ChatContactT,
                 referred_message: ReferredMessageRow
                 ) -> None:

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_halign(Gtk.Align.START)
        self.get_style_context().add_class('referred-message')

        self._referred_message = referred_message

        if contact.is_groupchat:
            ref_str = _('%s wrote') % referred_message.contact_name
        else:
            if referred_message.kind == KindConstant.CHAT_MSG_RECV:
                ref_str = _('%s wrote') % contact.name
            else:
                ref_str = _('You wrote')

        icon = Gtk.Image.new_from_icon_name(
            'mail-reply-sender-symbolic',
            Gtk.IconSize.BUTTON)
        icon.get_style_context().add_class('dim-label')

        name_label = Gtk.Label(label=ref_str)
        name_label.get_style_context().add_class('dim-label')

        date_time = datetime.fromtimestamp(referred_message.time)
        time_format = from_one_line(app.settings.get('date_time_format'))
        timestamp_label = Gtk.Label(
            label=f'({date_time.strftime(time_format)})')
        timestamp_label.get_style_context().add_class('dim-label')

        jump_to_button = Gtk.LinkButton(label=_('[view message]'))
        jump_to_button.connect('activate-link', self._on_jump_clicked)

        meta_box = Gtk.Box(spacing=6)
        meta_box.get_style_context().add_class('small-label')
        meta_box.add(icon)
        meta_box.add(name_label)
        meta_box.add(timestamp_label)
        meta_box.add(jump_to_button)

        message_text = referred_message.message.split('\n')[0]
        message_label = Gtk.Label(label=message_text)
        message_label.set_halign(Gtk.Align.START)
        message_label.set_max_width_chars(52)
        message_label.set_ellipsize(Pango.EllipsizeMode.END)
        message_label.get_style_context().add_class('dim-label')

        self.add(meta_box)
        self.add(message_label)

        self.show_all()

    def _on_jump_clicked(self, _button: Gtk.LinkButton) -> bool:
        app.window.activate_action(
            'jump-to-message', GLib.Variant(
                'au',
                [self._referred_message.log_line_id,
                 self._referred_message.time]))
        return True
