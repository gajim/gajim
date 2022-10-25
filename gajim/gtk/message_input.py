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

from __future__ import annotations

from typing import Any
from typing import Optional

from collections import defaultdict

import logging
import sys

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Pango

from gajim.common import app
from gajim.common import ged
from gajim.common.events import MessageSent
from gajim.common.ged import EventHelper
from gajim.common.i18n import LANG
from gajim.common.i18n import _
from gajim.common.styling import process
from gajim.common.styling import PlainBlock
from gajim.common.types import ChatContactT

from .chat_action_processor import ChatActionProcessor
from .util import scroll_to_end

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

UNDO_LIMIT: int = 20

FORMAT_CHARS: dict[str, str] = {
    'bold': '*',
    'italic': '_',
    'strike': '~',
    'pre': '`',
}

log = logging.getLogger('gajim.gui.message_input')


class MessageInputTextView(Gtk.TextView, EventHelper):
    '''
    A Gtk.Textview for chat message input
    '''
    def __init__(self) -> None:
        Gtk.TextView.__init__(self)
        EventHelper.__init__(self)

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

        self._undo_list: list[str] = []
        self.undo_pressed: bool = False

        self._contact: Optional[ChatContactT] = None

        # XEP-0308 Message Correction
        self._correcting: dict[ChatContactT, bool] = defaultdict(lambda: False)
        self._last_message_id: dict[ChatContactT, Optional[str]] = {}

        self._chat_action_processor = ChatActionProcessor(self)

        self.get_buffer().create_tag('strong', weight=Pango.Weight.BOLD)
        self.get_buffer().create_tag('emphasis', style=Pango.Style.ITALIC)
        self.get_buffer().create_tag('strike', strikethrough=True)
        self.get_buffer().create_tag('pre', family='monospace')

        self.get_buffer().connect('changed', self._on_text_changed)
        self.connect_after('paste-clipboard', self._after_paste_clipboard)
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect('destroy', self._on_destroy)
        self.connect('populate-popup', self._on_populate_popup)

        self.register_events([
            ('message-sent', ged.GUI2, self._on_message_sent)
        ])

        self._language_handler_id = self._init_spell_checker()
        app.settings.connect_signal('use_speller', self._on_toggle_spell_check)

        app.plugin_manager.gui_extension_point('message_input', self)

    @property
    def correcting(self) -> bool:
        assert self._contact is not None
        return self._correcting[self._contact]

    @correcting.setter
    def correcting(self, state: bool) -> None:
        assert self._contact is not None
        self._correcting[self._contact] = state

    def get_last_message_id(self, contact: ChatContactT) -> Optional[str]:
        return self._last_message_id.get(contact)

    def toggle_message_correction(self) -> None:
        self.clear()
        self.grab_focus()

        if self.correcting:
            self.correcting = False
            self.get_style_context().remove_class('gajim-msg-correcting')
            return

        assert self._contact is not None
        last_message_id = self._last_message_id.get(self._contact)
        if last_message_id is None:
            return

        message_row = app.storage.archive.get_last_correctable_message(
            self._contact.account, self._contact.jid, last_message_id)
        if message_row is None:
            return

        self.correcting = True
        self.get_style_context().add_class('gajim-msg-correcting')
        self.insert_text(message_row.message)

    def try_message_correction(self, message: str) -> Optional[str]:
        assert self._contact is not None
        if not self.correcting:
            return None

        self.toggle_message_correction()

        correct_id = self._last_message_id.get(self._contact)
        message_row = app.storage.archive.get_last_correctable_message(
            self._contact.account, self._contact.jid, correct_id)
        if message_row is None:
            log.info('Trying to correct message older than threshold')
            return None

        if message_row.message == message:
            log.info('Trying to correct message with original text')
            return None

        return correct_id

    def _on_message_sent(self, event: MessageSent) -> None:
        if not event.message:
            return

        if event.correct_id is None:
            # This wasn't a corrected message
            assert self._contact is not None
            oob_url = event.additional_data.get_value('gajim', 'oob_url')
            if oob_url == event.message:
                # Don't allow to correct HTTP Upload file transfer URLs
                self._last_message_id.pop(self._contact)
            else:
                self._last_message_id[self._contact] = event.message_id

    def _init_spell_checker(self) -> int:
        if not app.is_installed('GSPELL'):
            return 0

        checker = Gspell.Checker.new(Gspell.language_get_default())

        buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(self.get_buffer())
        buffer.set_spell_checker(checker)

        view = Gspell.TextView.get_from_gtk_text_view(self)
        view.set_enable_language_menu(True)

        self._on_toggle_spell_check()

        return checker.connect('notify::language', self._on_language_changed)

    def _set_spell_checker_language(self, contact: ChatContactT) -> None:
        if not app.is_installed('GSPELL'):
            return

        buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(self.get_buffer())
        checker = buffer.get_spell_checker()
        assert checker is not None
        lang = self._get_spell_checker_language(contact)

        with checker.handler_block(self._language_handler_id):
            checker.set_language(lang)

    def _get_spell_checker_language(self,
                                    contact: ChatContactT
                                    ) -> Optional[Gspell.Language]:

        lang = contact.settings.get('speller_language')
        if not lang:
            # use the default one
            lang = app.settings.get('speller_language')
            if not lang:
                lang = LANG

        assert isinstance(lang, str)
        lang = Gspell.language_lookup(lang)
        if lang is None:
            lang = Gspell.language_get_default()
        return lang

    def _on_language_changed(self,
                             checker: Gspell.Checker,
                             _param: Any) -> None:

        gspell_lang = checker.get_language()
        if gspell_lang is not None:
            assert self._contact is not None
            self._contact.settings.set('speller_language',
                                       gspell_lang.get_code())

    def switch_contact(self, contact: ChatContactT) -> None:
        if self._contact is not None:
            app.storage.drafts.set(self._contact, self.get_text())

        self.clear()
        draft = app.storage.drafts.get(contact)
        if draft is not None:
            self.insert_text(draft)

        self._contact = contact
        self._chat_action_processor.switch_contact(contact)
        self._set_spell_checker_language(contact)

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        # We restore the TextView’s drag destination to avoid a GTK warning
        # when closing the control. BaseControl.shutdown() calls destroy()
        # on the control’s main box, causing GTK to recursively destroy the
        # child widgets. GTK then tries to set a target list on the TextView,
        # resulting in a warning because the Widget has no drag destination.
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            None,
            Gdk.DragAction.DEFAULT)
        self._chat_action_processor.destroy()
        app.check_finalize(self)

    def _on_focus_in(self,
                     _widget: Gtk.Widget,
                     _event: Gdk.EventFocus
                     ) -> bool:

        scrolled = self.get_parent()
        assert scrolled
        scrolled.get_style_context().add_class('message-input-focus')
        return False

    def _on_focus_out(self,
                      _widget: Gtk.Widget,
                      _event: Gdk.EventFocus
                      ) -> bool:

        scrolled = self.get_parent()
        assert scrolled
        scrolled.get_style_context().remove_class('message-input-focus')
        return False

    def _clear_tags(self) -> None:
        to_remove: list[Gtk.TextTag] = []

        def _check(tag: Gtk.TextTag) -> None:
            if tag.get_property('underline-rgba-set') is True:
                # Don’t remove spell checking underlines
                return
            to_remove.append(tag)

        buf = self.get_buffer()
        start, end = buf.get_bounds()
        tag_table = buf.get_tag_table()
        tag_table.foreach(_check)
        for tag in to_remove:
            buf.remove_tag(tag, start, end)

    def _on_text_changed(self, buf: Gtk.TextBuffer) -> None:
        text = self.get_text()
        if not text:
            return

        self._clear_tags()

        if len(text) > 10000:
            # Limit message styling processing
            return

        result = process(text)
        for block in result.blocks:
            if isinstance(block, PlainBlock):
                for span in block.spans:
                    start_iter = buf.get_iter_at_offset(
                        span.start + block.start)
                    end_iter = buf.get_iter_at_offset(
                        span.end + block.start)
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

    @property
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

    def _on_toggle_spell_check(self, *args: Any) -> None:
        if not app.is_installed('GSPELL'):
            return

        use_spell_check = app.settings.get('use_speller')
        spell_view = Gspell.TextView.get_from_gtk_text_view(self)
        spell_view.set_inline_spell_checking(use_spell_check)

    @staticmethod
    def _after_paste_clipboard(textview: Gtk.TextView) -> None:
        buf = textview.get_buffer()
        mark = buf.get_insert()
        iter_ = buf.get_iter_at_mark(mark)
        if iter_.get_offset() == buf.get_end_iter().get_offset():
            GLib.idle_add(scroll_to_end, textview.get_parent())

    def _get_active_iters(self) -> tuple[Gtk.TextIter, Gtk.TextIter]:
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
        if sys.platform != 'darwin':
            # TODO: Remove if colored emoji rendering works well on MacOS
            return

        theme = app.settings.get('emoticons_theme')
        if not theme or theme == 'font':
            return

        def _replace(anchor: Gtk.TextChildAnchor) -> None:
            if anchor is None:
                return
            image = anchor.get_widgets()[0]
            if hasattr(image, 'codepoint'):
                # found emoji
                codepoint = getattr(image, 'codepoint')
                self._replace_char_at_iter(iter_, codepoint)
                image.destroy()

        iter_ = self.get_buffer().get_start_iter()
        _replace(iter_.get_child_anchor())

        while iter_.forward_char():
            _replace(iter_.get_child_anchor())

    def _replace_char_at_iter(self,
                              iter_: Gtk.TextIter,
                              new_char: str
                              ) -> None:
        buf = self.get_buffer()
        iter_2 = iter_.copy()
        iter_2.forward_char()
        buf.delete(iter_, iter_2)
        buf.insert(iter_, new_char)

    def insert_emoji(self, codepoint: str, pixbuf: GdkPixbuf.Pixbuf) -> None:
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
            setattr(image, 'codepoint', codepoint)
            image.show()
            self.add_child_at_anchor(image, anchor)
        buf.insert_at_cursor(' ')

    def clear(self, *args: Any) -> None:
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        buf.delete(start, end)
        self._undo_list.clear()

    def save_undo(self, text: str) -> None:
        self._undo_list.append(text)
        if len(self._undo_list) > UNDO_LIMIT:
            del self._undo_list[0]
        self.undo_pressed = False

    def undo(self, *args: Any) -> None:
        buf = self.get_buffer()
        if self._undo_list:
            buf.set_text(self._undo_list.pop())
        self.undo_pressed = True

    def _on_populate_popup(self,
                           _textview: MessageInputTextView,
                           menu: Gtk.Widget
                           ) -> None:
        assert isinstance(menu, Gtk.Menu)
        item = Gtk.MenuItem.new_with_mnemonic(_('_Undo'))
        menu.prepend(item)
        item.connect('activate', self.undo)

        item = Gtk.SeparatorMenuItem()
        menu.prepend(item)

        item = Gtk.MenuItem.new_with_mnemonic(_('_Clear'))
        menu.prepend(item)
        item.connect('activate', self.clear)

        paste_code_block_item = Gtk.MenuItem.new_with_label(
            _('Paste as Code Block'))
        paste_code_block_item.connect(
            'activate', self._paste_clipboard_as_code_block)
        menu.append(paste_code_block_item)

        paste_item = Gtk.MenuItem.new_with_label(_('Paste as Quote'))
        paste_item.connect('activate', self._paste_clipboard_as_quote)
        menu.append(paste_item)

        menu.show_all()

    def mention_participant(self, name: str) -> None:
        gc_refer_to_nick_char = app.settings.get('gc_refer_to_nick_char')
        text = f'{name}{gc_refer_to_nick_char} '
        self.insert_text(text)
        self.grab_focus()

    def insert_as_quote(self, text: str) -> None:
        text = '> ' + text.replace('\n', '\n> ') + '\n'
        self.insert_text(text)
        self.grab_focus()

    def insert_as_code_block(self, text: str) -> None:
        self.insert_text(f'```\n{text}\n```')
        self.grab_focus()

    def _paste_clipboard_as_quote(self, _item: Gtk.MenuItem) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()
        if text is None:
            return
        self.insert_as_quote(text)

    def _paste_clipboard_as_code_block(self, _item: Gtk.MenuItem) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()
        if text is None:
            return
        self.insert_as_code_block(text)
