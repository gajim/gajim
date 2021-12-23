# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2008-2009 Julien Pivotto <roidelapluie AT gmail.com>
#
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

from typing import Dict
from typing import List
from typing import Tuple

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango

from gajim.common import app
from gajim.common.styling import process

from .util import scroll_to_end

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

UNDO_LIMIT: int = 20

FORMAT_CHARS: Dict[str, str] = {
    'bold': '*',
    'italic': '_',
    'strike': '~',
    'pre': '`',
}


class MessageInputTextView(Gtk.TextView):
    """
    A Gtk.Textview for chat message input
    """
    def __init__(self) -> None:
        Gtk.TextView.__init__(self)
        self.set_border_width(3)
        self.set_accepts_tab(True)
        self.set_editable(True)
        self.set_cursor_visible(True)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_left_margin(2)
        self.set_right_margin(2)
        self.set_pixels_above_lines(2)
        self.set_pixels_below_lines(2)
        self.get_style_context().add_class('gajim-conversation-text')

        self.drag_dest_unset()

        self._undo_list: List[str] = []
        self.undo_pressed: bool = False

        self.get_buffer().create_tag('strong', weight=Pango.Weight.BOLD)
        self.get_buffer().create_tag('emphasis', style=Pango.Style.ITALIC)
        self.get_buffer().create_tag('strike', strikethrough=True)
        self.get_buffer().create_tag('pre', family='monospace')

        self.get_buffer().connect('changed', self._on_text_changed)
        self.connect_after('paste-clipboard', self._after_paste_clipboard)
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args):
        # We restore the TextView’s drag destination to avoid a GTK warning
        # when closing the control. BaseControl.shutdown() calls destroy()
        # on the control’s main box, causing GTK to recursively destroy the
        # child widgets. GTK then tries to set a target list on the TextView,
        # resulting in a warning because the Widget has no drag destination.
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            None,
            Gdk.DragAction.DEFAULT)

    def _on_focus_in(self, _widget, _event):
        self.toggle_speller(True)
        scrolled = self.get_parent()
        scrolled.get_style_context().add_class('message-input-focus')
        return False

    def _on_focus_out(self, _widget, _event):
        scrolled = self.get_parent()
        scrolled.get_style_context().remove_class('message-input-focus')
        if not self.has_text():
            self.toggle_speller(False)
        return False

    def _clear_tags(self) -> None:
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        buf.remove_all_tags(start, end)

    def _on_text_changed(self, buf: Gtk.TextBuffer) -> None:
        text = self.get_text()
        if not text:
            return

        self._clear_tags()
        result = process(text)
        for block in result.blocks:
            if block.name == 'plain':
                for span in block.spans:
                    start_iter = buf.get_iter_at_offset(span.start)
                    end_iter = buf.get_iter_at_offset(span.end)
                    buf.apply_tag_by_name(span.name, start_iter, end_iter)

    def insert_text(self, text: str) -> None:
        self.get_buffer().insert_at_cursor(text)

    def insert_newline(self) -> None:
        buf = self.get_buffer()
        buf.insert_at_cursor('\n')
        mark = buf.get_insert()
        iter_ = buf.get_iter_at_mark(mark)
        if buf.get_end_iter().equal(iter_):
            GLib.idle_add(scroll_to_end, self.get_parent())

    def has_text(self) -> bool:
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, True)
        return text != ''

    def get_text(self) -> str:
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        text = self.get_buffer().get_text(start, end, True)
        return text

    def toggle_speller(self, activate: bool) -> None:
        if app.is_installed('GSPELL') and app.settings.get('use_speller'):
            spell_view = Gspell.TextView.get_from_gtk_text_view(self)
            spell_view.set_inline_spell_checking(activate)

    @staticmethod
    def _after_paste_clipboard(textview: Gtk.TextView) -> None:
        buf = textview.get_buffer()
        mark = buf.get_insert()
        iter_ = buf.get_iter_at_mark(mark)
        if iter_.get_offset() == buf.get_end_iter().get_offset():
            GLib.idle_add(scroll_to_end, textview.get_parent())

    def _get_active_iters(self) -> Tuple[Gtk.TextIter, Gtk.TextIter]:
        buf = self.get_buffer()
        return_val = buf.get_selection_bounds()
        if return_val:  # if something is selected
            start, end = return_val[0], return_val[1]
        else:
            start, end = buf.get_bounds()
        return (start, end)

    def apply_formatting(self, formatting: str) -> None:
        format_char = FORMAT_CHARS[formatting]

        buf = self.get_buffer()
        start, end = self._get_active_iters()
        start_offset = start.get_offset()
        end_offset = end.get_offset()

        text = buf.get_text(start, end, True)
        if text.startswith(format_char) and text.endswith(format_char):
            # (Selected) text begins and ends with formatting chars
            # -> remove them
            buf.delete(
                start,
                buf.get_iter_at_offset(start_offset + 1))
            buf.delete(
                buf.get_iter_at_offset(end_offset - 2),
                buf.get_iter_at_offset(end_offset - 1))
            return

        ext_start = buf.get_iter_at_offset(start_offset - 1)
        ext_end = buf.get_iter_at_offset(end_offset + 1)
        ext_text = buf.get_text(ext_start, ext_end, True)
        if ext_text.startswith(format_char) and ext_text.endswith(format_char):
            # (Selected) text is surrounded by formatting chars -> remove them
            buf.delete(
                ext_start,
                buf.get_iter_at_offset(start_offset))
            buf.delete(
                buf.get_iter_at_offset(end_offset - 1),
                buf.get_iter_at_offset(end_offset))
            return

        # No formatting chars found at start/end or surrounding -> add them
        buf.insert(start, format_char, -1)
        buf.insert(
            buf.get_iter_at_offset(end_offset + 1),
            format_char,
            -1)
        buf.select_range(
            buf.get_iter_at_offset(start_offset),
            buf.get_iter_at_offset(end_offset + 2))

    def replace_emojis(self) -> None:
        theme = app.settings.get('emoticons_theme')
        if not theme or theme == 'font':
            return

        def _replace(anchor):
            if anchor is None:
                return
            image = anchor.get_widgets()[0]
            if hasattr(image, 'codepoint'):
                # found emoji
                self._replace_char_at_iter(iter_, image.codepoint)
                image.destroy()

        iter_ = self.get_buffer().get_start_iter()
        _replace(iter_.get_child_anchor())

        while iter_.forward_char():
            _replace(iter_.get_child_anchor())

    def _replace_char_at_iter(self, iter_, new_char):
        buf = self.get_buffer()
        iter_2 = iter_.copy()
        iter_2.forward_char()
        buf.delete(iter_, iter_2)
        buf.insert(iter_, new_char)

    def insert_emoji(self, codepoint, pixbuf):
        buf = self.get_buffer()
        if buf.get_char_count():
            # buffer contains text
            buf.insert_at_cursor(' ')

        insert_mark = buf.get_insert()
        insert_iter = buf.get_iter_at_mark(insert_mark)

        if pixbuf is None:
            buf.insert(insert_iter, codepoint)
        else:
            anchor = buf.create_child_anchor(insert_iter)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.codepoint = codepoint
            image.show()
            self.add_child_at_anchor(image, anchor)
        buf.insert_at_cursor(' ')

    def clear(self, *args):
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        buf.delete(start, end)

    def save_undo(self, text: str) -> None:
        self._undo_list.append(text)
        if len(self._undo_list) > UNDO_LIMIT:
            del self._undo_list[0]
        self.undo_pressed = False

    def undo(self, *args):
        buf = self.get_buffer()
        if self._undo_list:
            buf.set_text(self._undo_list.pop())
        self.undo_pressed = True
