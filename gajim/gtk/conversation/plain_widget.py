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

import logging

from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common.helpers import open_uri
from gajim.common.helpers import parse_uri
from gajim.common.structs import URIType
from gajim.common.styling import BaseHyperlink
from gajim.common.styling import PlainBlock
from gajim.common.styling import process_uris

from ..menus import get_conv_action_context_menu
from ..menus import repopulate_conv_uri_context_menu
from ..util import make_pango_attributes

log = logging.getLogger('gajim.gui.conversaion.plain_widget')

URI_TAGS = ['uri', 'xmppadr', 'mailadr']
STYLE_TAGS = ['strong', 'emphasis', 'strike', 'pre']


class PlainWidget(Gtk.Box):
    def __init__(self, account: str, selectable: bool) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)

        self._account = account

        self._text_widget = MessageLabel(self._account, selectable)
        self.add(self._text_widget)

    def set_selectable(self, selectable: bool) -> None:
        self._text_widget.set_selectable(selectable)

    def add_content(self, block: PlainBlock) -> None:
        self._text_widget.print_text_with_styling(block)

    def add_action_phrase(self, text: str, nickname: str) -> None:
        self._text_widget.add_action_phrase(text, nickname)


class MessageLabel(Gtk.Label):
    def __init__(self, account: str, selectable: bool) -> None:
        Gtk.Label.__init__(self)
        self.set_hexpand(True)
        self.set_selectable(selectable)
        self.set_line_wrap(True)
        self.set_xalign(0)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_track_visited_links(False)

        self._account = account

        self.get_style_context().add_class('gajim-conversation-text')

        self.connect('populate-popup', self._on_populate_popup)
        self.connect('activate-link', self._on_activate_link)
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)

    def _on_populate_popup(self, label: Gtk.Label, menu: Gtk.Menu) -> None:
        uri = label.get_current_uri()
        selected, start, end = label.get_selection_bounds()
        if uri:
            puri = parse_uri(uri)
            assert puri.type != URIType.INVALID  # would be a common.styling bug
            repopulate_conv_uri_context_menu(menu, self._account, puri)
        elif selected:
            selected_text = label.get_text()[start:end]
            action_menu_item = get_conv_action_context_menu(
                self._account, selected_text)
            menu.prepend(action_menu_item)
        menu.show_all()

    def _build_link_markup(self, text: str, uris: list[BaseHyperlink]) -> str:
        markup_text = ''
        after = GLib.markup_escape_text(text.strip())
        for uri in uris:
            uri_escaped = GLib.markup_escape_text(uri.text)
            before, _, after = after.partition(uri_escaped)
            markup_text += before
            markup_text += uri.get_markup_string()
        markup_text += after
        return markup_text

    def print_text_with_styling(self, block: PlainBlock) -> None:
        text = self._build_link_markup(block.text, block.uris)
        self.set_markup(text)

        if len(self.get_text()) > 10000:
            # Limit message styling processing
            return

        self.set_attributes(make_pango_attributes(block))

    def add_action_phrase(self, text: str, nickname: str) -> None:
        text = text.replace('/me', f'* {nickname}', 1)
        uris = process_uris(text)
        text = self._build_link_markup(text, uris)
        self.set_markup(f'<i>{text}</i>')

    def _on_activate_link(self, _label: Gtk.Label, uri: str) -> int:
        open_uri(uri, self._account)
        return Gdk.EVENT_STOP

    @staticmethod
    def _on_focus_in(widget: MessageLabel,
                     _event: Gdk.EventFocus
                     ) -> None:
        widget.get_style_context().remove_class('transparent-selection')

    @staticmethod
    def _on_focus_out(widget: MessageLabel,
                      _event: Gdk.EventFocus
                      ) -> None:
        widget.get_style_context().add_class('transparent-selection')
