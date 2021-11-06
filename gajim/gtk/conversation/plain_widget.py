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

import logging

from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common.const import StyleAttr
from gajim.common.helpers import open_uri
from gajim.common.helpers import reduce_chars_newlines
from gajim.common.helpers import parse_uri

from gajim.gui_menu_builder import get_conv_action_context_menu
from gajim.gui_menu_builder import get_conv_uri_context_menu

from ..util import get_cursor
from ..util import make_pango_attribute

log = logging.getLogger('gajim.gui.conversaion.plain_widget')

URI_TAGS = ['uri', 'address', 'xmppadr', 'mailadr']
STYLE_TAGS = ['strong', 'emphasis', 'strike', 'pre']


class PlainWidget(Gtk.Box):
    def __init__(self, account, selectable):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)

        self._account = account

        # TODO: Window/Linux handling
        # self._text_widget = MessageTextview(self._account)
        self._text_widget = MessageLabel(self._account, selectable)
        self.add(self._text_widget)

    def add_content(self, block):
        self._text_widget.print_text_with_styling(block)

    def update_text_tags(self):
        self._text_widget.update_text_tags()


class MessageLabel(Gtk.Label):
    def __init__(self, account, selectable):
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

    def _on_populate_popup(self, label, menu):
        selected, start, end = label.get_selection_bounds()
        if not selected:
            menu.show_all()
            return

        selected_text = label.get_text()[start:end]
        action_menu_item = get_conv_action_context_menu(
            self._account, selected_text)
        menu.prepend(action_menu_item)
        menu.show_all()

    def print_text_with_styling(self, block):
        text = GLib.markup_escape_text(block.text.strip())
        for uri in block.uris:
            text = text.replace(uri.text, uri.get_markup_string())

        attr_list = Pango.AttrList()
        for span in block.spans:
            attr = make_pango_attribute(span.name, span.start, span.end)
            attr_list.insert(attr)

        self.set_markup(text)
        self.set_attributes(attr_list)

    def update_text_tags(self):
        pass


class MessageTextview(Gtk.TextView):
    def __init__(self, account):
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

        self._handlers = {}

        id_ = self.connect('query-tooltip', self._query_tooltip)
        self._handlers[id_] = self
        id_ = self.connect('button-press-event', self._on_button_press)
        self._handlers[id_] = self
        id_ = self.connect('populate-popup', self._on_populate_popup)
        self._handlers[id_] = self

        self._account = account

        # Used for changing the mouse pointer when hovering clickable URIs
        self._cursor_changed = False

        # Keeps text selections for quoting and search actions
        self._selected_text = ''

        self.get_style_context().add_class('gajim-conversation-text')

        # Create Tags
        self._create_url_tags()
        self.get_buffer().create_tag('strong', weight=Pango.Weight.BOLD)
        self.get_buffer().create_tag('emphasis', style=Pango.Style.ITALIC)
        self.get_buffer().create_tag('strike', strikethrough=True)
        self.get_buffer().create_tag('pre', family='monospace')

        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args):
        for id_, widget in self._handlers.items():
            if widget.handler_is_connected(id_):
                widget.disconnect(id_)
        self._handlers.clear()

    def _create_url_tags(self):
        color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)
        for name in URI_TAGS:
            tag = self.get_buffer().create_tag(name,
                                               foreground=color,
                                               underline=Pango.Underline.SINGLE)
            tag.connect('event', self._on_uri_clicked, tag)

    def update_text_tags(self):
        tag_table = self.get_buffer().get_tag_table()
        url_color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)
        for tag in URI_TAGS:
            tag_table.lookup(tag).set_property('foreground', url_color)

    def clear(self):
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)

    def get_text(self):
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        return buffer_.get_text(start, end, False)

    def print_text_with_styling(self, block):
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

    def _query_tooltip(self, widget, x_pos, y_pos, _keyboard_mode, tooltip):
        window = widget.get_window(Gtk.TextWindowType.TEXT)
        x_pos, y_pos = self.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, x_pos, y_pos)

        iter_ = self.get_iter_at_position(x_pos, y_pos)[1]
        for tag in iter_.get_tags():
            tag_name = tag.get_property('name')
            if getattr(tag, 'is_anchor', False):
                text = getattr(tag, 'title', False)
                if text:
                    if len(text) > 50:
                        text = reduce_chars_newlines(text, 47, 1)
                    tooltip.set_text(text)
                    window.set_cursor(get_cursor('pointer'))
                    self._cursor_changed = True
                    return True
            if tag_name in URI_TAGS:
                window.set_cursor(get_cursor('pointer'))
                self._cursor_changed = True
                return False

        if self._cursor_changed:
            window.set_cursor(get_cursor('text'))
            self._cursor_changed = False
        return False

    def _on_button_press(self, _widget, event):
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
        iter_ = self.get_iter_at_location(x_pos, y_pos)
        if isinstance(iter_, tuple):
            iter_ = iter_[1]
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

    def _on_populate_popup(self, _textview, menu):
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

    def _on_uri_clicked(self, texttag, _widget, event, iter_, _kind):
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

    def _show_uri_context_menu(self, uri):
        menu = get_conv_uri_context_menu(self._account, uri)
        if menu is None:
            log.warning('No handler for URI type: %s', uri)
            return

        def destroy(menu, _pspec):
            visible = menu.get_property('visible')
            if not visible:
                GLib.idle_add(menu.destroy)

        menu.attach_to_widget(self, None)
        menu.connect('notify::visible', destroy)
        menu.popup_at_pointer()
