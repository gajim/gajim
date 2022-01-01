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

from typing import Any

import logging
import os

from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject

from gajim.common import app
from gajim.common.const import StyleAttr
from gajim.common.helpers import open_uri
from gajim.common.helpers import parse_uri
from gajim.common.structs import URI
from gajim.common.styling import PlainBlock

from ..menus import get_conv_action_context_menu
from ..menus import get_conv_uri_context_menu
from ..emoji_data import emoji_pixbufs
from ..emoji_data import get_emoji_pixbuf
from ..util import get_cursor
from ..util import make_pango_attributes

log = logging.getLogger('gajim.gui.conversaion.plain_widget')

URI_TAGS = ['uri', 'address', 'xmppadr', 'mailadr']
STYLE_TAGS = ['strong', 'emphasis', 'strike', 'pre']


class PlainWidget(Gtk.Box):
    def __init__(self, account: str, selectable: bool) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)

        self._account = account

        # We use a Gtk.Textview on Windows, since there is no support for
        # rendering color fonts (Emojis) on Windows yet, see:
        # https://gitlab.freedesktop.org/cairo/cairo/-/merge_requests/244
        if os.name == 'nt':
            self._text_widget = MessageTextview(self._account)
        else:
            self._text_widget = MessageLabel(self._account, selectable)
        self.add(self._text_widget)

    def add_content(self, block: PlainBlock) -> None:
        self._text_widget.print_text_with_styling(block)

    def add_action_phrase(self, text: str, nickname: str) -> None:
        text = text.replace('/me', '* %s' % nickname, 1)
        text = GLib.markup_escape_text(text)
        self._text_widget.add_action_phrase(text)

    def update_text_tags(self) -> None:
        self._text_widget.update_text_tags()


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

    def _on_populate_popup(self, label: Gtk.Label, menu: Gtk.Menu) -> None:
        selected, start, end = label.get_selection_bounds()
        if not selected:
            menu.show_all()
            return

        selected_text = label.get_text()[start:end]
        action_menu_item = get_conv_action_context_menu(
            self._account, selected_text)
        menu.prepend(action_menu_item)
        menu.show_all()

    def print_text_with_styling(self, block: PlainBlock) -> None:
        text = ''
        after = GLib.markup_escape_text(block.text.strip())
        for uri in block.uris:
            uri_escaped = GLib.markup_escape_text(uri.text)
            before, _, after = after.partition(uri_escaped)
            text += before
            text += uri.get_markup_string()
        text += after

        self.set_markup(text)
        self.set_attributes(make_pango_attributes(block))

    def add_action_phrase(self, text: str) -> None:
        self.set_markup(f'<i>{text}</i>')

    def update_text_tags(self) -> None:
        pass


class MessageTextview(Gtk.TextView):
    def __init__(self, account: str) -> None:
        Gtk.TextView.__init__(self)
        self.set_hexpand(True)
        self.set_margin_start(0)
        self.set_margin_end(0)
        self.set_border_width(0)
        self.set_left_margin(0)
        self.set_right_margin(0)
        self.set_has_tooltip(True)
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        self._handlers: dict[int, MessageTextview] = {}

        id_ = self.connect('query-tooltip', self._query_tooltip)
        self._handlers[id_] = self
        id_ = self.connect('button-press-event', self._on_button_press)
        self._handlers[id_] = self
        id_ = self.connect('populate-popup', self._on_populate_popup)
        self._handlers[id_] = self

        self._account = account

        # Used for changing the mouse pointer when hovering clickable URIs
        self._cursor_changed: bool = False

        # Keeps text selections for quoting and search actions
        self._selected_text: str = ''

        self.get_style_context().add_class('gajim-conversation-text')

        # Create Tags
        self._create_url_tags()
        self.get_buffer().create_tag('strong', weight=Pango.Weight.BOLD)
        self.get_buffer().create_tag('emphasis', style=Pango.Style.ITALIC)
        self.get_buffer().create_tag('strike', strikethrough=True)
        self.get_buffer().create_tag('pre', family='monospace')

        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args: Any) -> None:
        for id_, widget in self._handlers.items():
            if widget.handler_is_connected(id_):
                widget.disconnect(id_)
        self._handlers.clear()

    def _create_url_tags(self) -> None:
        color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)
        for name in URI_TAGS:
            tag = self.get_buffer().create_tag(name,
                                               foreground=color,
                                               underline=Pango.Underline.SINGLE)
            tag.connect('event', self._on_uri_clicked, tag)

    def update_text_tags(self) -> None:
        tag_table = self.get_buffer().get_tag_table()
        url_color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)
        for tag_name in URI_TAGS:
            tag = tag_table.lookup(tag_name)
            assert tag is not None
            tag.set_property('foreground', url_color)

    def clear(self) -> None:
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)

    def get_text(self) -> str:
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        return buffer_.get_text(start, end, False)

    def print_text_with_styling(self, block: PlainBlock) -> None:
        buffer_ = self.get_buffer()
        buffer_.insert(buffer_.get_start_iter(), block.text.strip())

        for span in block.spans:
            start_iter = buffer_.get_iter_at_offset(span.start)
            end_iter = buffer_.get_iter_at_offset(span.end)
            buffer_.apply_tag_by_name(span.name, start_iter, end_iter)

        for uri in block.uris:
            start_iter = buffer_.get_iter_at_offset(uri.start)
            end_iter = buffer_.get_iter_at_offset(uri.end)
            buffer_.apply_tag_by_name(uri.name, start_iter, end_iter)

        for emoji in block.emojis:
            start_iter = buffer_.get_iter_at_offset(emoji.start)
            end_iter = buffer_.get_iter_at_offset(emoji.end)
            if emoji_pixbufs.complete:
                # Only search for pixbuf if loading is completed
                pixbuf = get_emoji_pixbuf(emoji.text)
                if pixbuf is None:
                    buffer_.insert(end_iter, emoji.text)
                else:
                    pixbuf = pixbuf.copy()
                    anchor = buffer_.create_child_anchor(end_iter)
                    anchor.plaintext = emoji.text  # type: ignore
                    img = Gtk.Image.new_from_pixbuf(pixbuf)
                    img.show()
                    self.add_child_at_anchor(img, anchor)
                    buffer_.delete(
                        buffer_.get_iter_at_offset(emoji.start),
                        buffer_.get_iter_at_offset(emoji.end))
            else:
                # Set marks and save them so we can replace emojis
                # once loading is complete
                start_mark = buffer_.create_mark(None, end_iter, True)
                buffer_.insert(end_iter, emoji.text)
                end_mark = buffer_.create_mark(None, end_iter, True)
                emoji_pixbufs.append_marks(
                    self, start_mark, end_mark, emoji.text)

    def add_action_phrase(self, text: str) -> None:
        buffer_ = self.get_buffer()
        buffer_.insert(buffer_.get_start_iter(), text.strip())

        start_iter = buffer_.get_start_iter()
        end_iter = buffer_.get_end_iter()
        buffer_.apply_tag_by_name('emphasis', start_iter, end_iter)

    def _query_tooltip(self,
                       widget: Gtk.TextView,
                       x_pos: int,
                       y_pos: int,
                       _keyboard_mode: bool,
                       tooltip: Gtk.Tooltip
                       ) -> bool:

        window = widget.get_window(Gtk.TextWindowType.TEXT)
        assert window is not None
        x_pos, y_pos = self.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, x_pos, y_pos)

        iter_ = self.get_iter_at_position(x_pos, y_pos)[1]
        for tag in iter_.get_tags():
            tag_name = tag.get_property('name')
            if tag_name in URI_TAGS:
                window.set_cursor(get_cursor('pointer'))
                self._cursor_changed = True
                return False

        if self._cursor_changed:
            window.set_cursor(get_cursor('text'))
            self._cursor_changed = False
        return False

    def _on_button_press(self, _widget: Any, event: Gdk.EventButton) -> bool:
        '''
        We don’t open the standard context menu when receiving
        a click on tagged text.
        If it’s untagged text, check if something is selected
        '''
        self._selected_text = ''

        if event.button != 3:
            # If it’s not a right click
            return False

        x_pos, y_pos = self.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT,
            int(event.x),
            int(event.y))
        _, iter_ = self.get_iter_at_location(x_pos, y_pos)
        tags = iter_.get_tags()

        if tags:
            # A tagged text fragment has been clicked
            for tag in tags:
                if tag.get_property('name') in URI_TAGS:
                    # Block regular context menu
                    return True

        # Check if there is a selection and make it available for
        # _on_populate_popup
        buffer_ = self.get_buffer()
        return_val = buffer_.get_selection_bounds()
        if return_val:
            # Something has been selected, get the text
            start_sel, finish_sel = return_val[0], return_val[1]
            self._selected_text = buffer_.get_text(
                start_sel, finish_sel, True)
        elif iter_.get_char() and ord(iter_.get_char()) > 31:
            # Clicked on a word, take whole word for selection
            start_sel = iter_.copy()
            if not start_sel.starts_word():
                start_sel.backward_word_start()
            finish_sel = iter_.copy()
            if not finish_sel.ends_word():
                finish_sel.forward_word_end()
            self._selected_text = buffer_.get_text(
                start_sel, finish_sel, True)
        return False

    def _on_populate_popup(self,
                           _textview: Gtk.TextView,
                           menu: Gtk.Menu
                           ) -> None:
        '''
        Overrides the default context menu.
        If text is selected, a submenu with actions on the selection is added.
        (see _on_button_press)
        '''
        if not self._selected_text:
            menu.show_all()
            return

        action_menu_item = get_conv_action_context_menu(
            self._account, self._selected_text)
        menu.prepend(action_menu_item)
        menu.show_all()

    def _on_uri_clicked(self,
                        texttag: Gtk.TextTag,
                        _widget: Any,
                        event: Gdk.Event,
                        iter_: Gtk.TextIter,
                        _kind: Gtk.TextTag
                        ) -> int:
        if event.type != Gdk.EventType.BUTTON_PRESS:
            return Gdk.EVENT_PROPAGATE

        begin_iter = iter_.copy()
        # we get the beginning of the tag
        while not begin_iter.starts_tag(texttag):
            begin_iter.backward_char()
        end_iter = iter_.copy()
        # we get the end of the tag
        while not end_iter.ends_tag(texttag):
            end_iter.forward_char()

        # Detect XHTML-IM link
        word = getattr(texttag, 'href', None)
        if not word:
            word = self.get_buffer().get_text(begin_iter, end_iter, True)

        uri = parse_uri(word)
        if event.button.button == 3:  # right click
            self._show_uri_context_menu(uri)
            return Gdk.EVENT_STOP

        # TODO:
        # self.plugin_modified = False
        # app.plugin_manager.extension_point(
        #     'hyperlink_handler', uri, self, self.get_toplevel())
        # if self.plugin_modified:
        #     return Gdk.EVENT_STOP

        open_uri(uri, account=self._account)
        return Gdk.EVENT_STOP

    def _show_uri_context_menu(self, uri: URI) -> None:
        menu = get_conv_uri_context_menu(self._account, uri)
        if menu is None:
            log.warning('No handler for URI type: %s', uri)
            return

        def _destroy(menu: Gtk.Menu, _pspec: GObject.ParamSpec) -> None:
            visible = menu.get_property('visible')
            if not visible:
                GLib.idle_add(menu.destroy)

        menu.attach_to_widget(self, None)
        menu.connect('notify::visible', _destroy)
        menu.popup_at_pointer()
