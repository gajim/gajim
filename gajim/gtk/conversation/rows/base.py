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

from datetime import datetime

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import from_one_line

from ...util import convert_rgba_to_hex
from ...util import text_to_color
from ...util import wrap_with_event_box


class BaseRow(Gtk.ListBoxRow):
    def __init__(self, account, widget=None):
        Gtk.ListBoxRow.__init__(self)
        self._account = account
        self._client = app.get_client(account)
        self.type = ''
        self.timestamp = None
        self.kind = None
        self.name = None
        self.message_id = None
        self.log_line_id = None
        self.text = ''
        self._merged = False

        self.get_style_context().add_class('conversation-row')

        self.grid = Gtk.Grid(row_spacing=3, column_spacing=12)
        self.add(self.grid)

        if widget == 'label':
            self.label = Gtk.Label()
            self.label.set_selectable(True)
            self.label.set_line_wrap(True)
            self.label.set_xalign(0)
            self.label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

    @property
    def is_merged(self):
        return self._merged

    def update_text_tags(self):
        if self.textview is not None:
            self.textview.update_text_tags()

    @staticmethod
    def create_timestamp_widget(timestamp: datetime) -> Gtk.Label:
        time_format = from_one_line(app.settings.get('chat_timestamp_format'))
        timestamp_formatted = timestamp.strftime(time_format)
        label = Gtk.Label(label=timestamp_formatted)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.END)
        label.get_style_context().add_class('conversation-meta')
        label.set_tooltip_text(timestamp.strftime('%a, %d %b %Y - %X'))
        return label

    @staticmethod
    def create_name_widget(name: str, is_self: bool) -> Gtk.Label:
        label = Gtk.Label()
        label.set_selectable(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.get_style_context().add_class('conversation-nickname')
        label.set_markup(GLib.markup_escape_text(name))

        if is_self:
            label.get_style_context().add_class('gajim-outgoing-nickname')
        else:
            label.get_style_context().add_class('gajim-incoming-nickname')
        return label


@wrap_with_event_box
class MoreMenuButton(Gtk.MenuButton):
    def __init__(self, row):
        Gtk.MenuButton.__init__(self)

        self.set_valign(Gtk.Align.START)
        self.set_halign(Gtk.Align.END)
        self.set_relief(Gtk.ReliefStyle.NONE)
        image = Gtk.Image.new_from_icon_name(
            'feather-more-horizontal-symbolic', Gtk.IconSize.BUTTON)
        self.add(image)

        self._create_popover(row)

        self.get_style_context().add_class('conversation-more-button')

    def _create_popover(self, row):
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.get_style_context().add_class('padding-6')

        quote_button = Gtk.ModelButton()
        quote_button.set_halign(Gtk.Align.START)
        quote_button.connect('clicked', row.on_quote_message)
        quote_button.set_label(_('Quote…'))
        quote_button.set_image(Gtk.Image.new_from_icon_name(
            'mail-reply-sender-symbolic', Gtk.IconSize.MENU))
        menu_box.add(quote_button)

        copy_button = Gtk.ModelButton()
        copy_button.set_halign(Gtk.Align.START)
        copy_button.connect('clicked', row.on_copy_message)
        copy_button.set_label(_('Copy'))
        copy_button.set_image(Gtk.Image.new_from_icon_name(
            'edit-copy-symbolic', Gtk.IconSize.MENU))
        menu_box.add(copy_button)

        menu_box.show_all()

        popover = Gtk.PopoverMenu()
        popover.add(menu_box)
        self.set_popover(popover)
