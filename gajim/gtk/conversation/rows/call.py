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

import time
from datetime import datetime

from gi.repository import Gtk

from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .widgets import SimpleLabel
from .base import BaseRow


class CallRow(BaseRow):
    def __init__(self, account, contact, timestamp, text, event=None):
        BaseRow.__init__(self, account)

        self.type = 'call'
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        self._contact = contact
        self._event = event

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        if event is None:
            icon = Gtk.Image.new_from_icon_name('call-start-symbolic',
                                                Gtk.IconSize.MENU)
            self.grid.attach(icon, 1, 0, 1, 1)

            self._label = SimpleLabel()
            self._label.set_text(text)
            self.grid.attach(self._label, 2, 0, 1, 1)
        else:
            self._prepare_incoming_call()

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_hexpand(True)
        timestamp_widget.set_halign(Gtk.Align.END)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 3, 0, 1, 1)

        self.show_all()

    def _on_accept(self, button):
        button.set_sensitive(False)
        self._reject_button.set_sensitive(False)
        self.get_parent().on_call_answered('accept', self._event)

    def _on_reject(self, button):
        button.set_sensitive(False)
        self._accept_button.set_sensitive(False)
        self.get_parent().on_call_answered('reject', self._event)

    def _prepare_incoming_call(self):
        call_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        call_box.set_size_request(350, -1)
        call_box.get_style_context().add_class('conversation-call-box')
        call_box.get_style_context().add_class('gajim-call-message')

        scale = self.get_scale_factor()
        avatar = self._contact.get_avatar(
            AvatarSize.CALL,
            scale,
            add_show=False)
        avatar_image = Gtk.Image.new_from_surface(avatar)
        call_box.add(avatar_image)

        content_types = []
        for item in self._event.contents:
            content_types.append(item.media)
        text = _('%s is calling') % self._contact.name
        if 'video' in content_types:
            text += _(' (Video Call)')
        else:
            text += _(' (Voice Call)')
        label = Gtk.Label(label=text)
        label.get_style_context().add_class('bold')
        label.set_max_width_chars(40)
        label.set_line_wrap(True)
        call_box.add(label)

        self._accept_button = Gtk.Button.new_with_label(_('Accept Call'))
        self._accept_button.connect('clicked', self._on_accept)

        self._reject_button = Gtk.Button.new_with_label(_('Reject'))
        self._reject_button.connect('clicked', self._on_reject)

        button_box = Gtk.Box(spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.add(self._accept_button)
        button_box.add(self._reject_button)
        call_box.add(button_box)

        self.grid.attach(call_box, 1, 0, 1, 1)
