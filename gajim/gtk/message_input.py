# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2008-2009 Julien Pivotto <roidelapluie AT gmail.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing
from typing import Any

import logging

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import get_default_lang
from gajim.common.storage.archive import models as mod
from gajim.common.styling import PlainBlock
from gajim.common.styling import process
from gajim.common.types import ChatContactT

from gajim.gtk.chat_action_processor import ChatActionProcessor
from gajim.gtk.const import MAX_MESSAGE_LENGTH
from gajim.gtk.util import scroll_to_end

if app.is_installed('GSPELL') or typing.TYPE_CHECKING:
    from gi.repository import Gspell

FORMAT_CHARS: dict[str, str] = {
    'bold': '*',
    'italic': '_',
    'strike': '~',
    'pre': '`',
}

log = logging.getLogger('gajim.gtk.message_input')


class MessageInputTextView(GtkSource.View):
    '''
    A GtkSource.View for chat message input
    '''

    __gsignals__ = {
        'buffer-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            ()
        )
    }

    def __init__(self) -> None:
        GtkSource.View.__init__(
            self,
            accepts_tab=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            border_width=0,
            margin_left=3,
            margin_top=3,
            margin_right=3,
            margin_bottom=3
        )

        self.get_style_context().add_class('gajim-conversation-text')

        self._contact: ChatContactT | None = None

        self._text_buffer_manager = TextBufferManager(self)
        self._text_buffer_manager.connect(
            'buffer-changed', self._on_buffer_changed)

        self._chat_action_processor = ChatActionProcessor(self)

        self.connect_after('paste-clipboard', self._after_paste_clipboard)
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect('destroy', self._on_destroy)
        self.connect('populate-popup', self._on_populate_popup)

        app.plugin_manager.gui_extension_point('message_input', self)

    def start_correction(self, message: mod.Message | None = None) -> None:
        self.get_style_context().add_class('gajim-msg-correcting')
        if message is None:
            return

        self.clear()
        self.grab_focus()

        text = message.text
        assert text is not None

        self.insert_text(text)

    def end_correction(self) -> None:
        self.clear()
        self.get_style_context().remove_class('gajim-msg-correcting')

    def switch_contact(self, contact: ChatContactT) -> None:
        if self._contact is not None:
            app.storage.drafts.set(self._contact, self.get_text())

        self._text_buffer_manager.switch_contact(contact)

        self.clear()
        draft = app.storage.drafts.get(contact)
        if draft is not None:
            self.insert_text(draft)

        self._contact = contact

        self._chat_action_processor.switch_contact(contact)

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._chat_action_processor.destroy()
        app.check_finalize(self)

    def _on_buffer_changed(self,
                           _text_buffer_manager: TextBufferManager
                           ) -> None:
        self._on_text_changed()
        self.emit('buffer-changed')

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

    def _on_text_changed(self) -> None:
        text = self.get_text()
        if not text:
            return

        self._clear_tags()

        if len(text) > MAX_MESSAGE_LENGTH:
            # Limit message styling processing
            return

        buf = self.get_buffer()
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
        # Reset IMContext to clear preedit state
        self.reset_im_context()
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
        return self.get_buffer().get_text(start, end, True)

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

    def clear(self, *args: Any) -> None:
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        buf.delete(start, end)

    def undo(self, *args: Any) -> None:
        buf = self.get_buffer()
        if buf.can_undo():
            buf.undo()

    def redo(self, *args: Any) -> None:
        buf = self.get_buffer()
        if buf.can_redo():
            buf.redo()

    def _on_populate_popup(self,
                           _textview: MessageInputTextView,
                           menu: Gtk.Widget
                           ) -> None:
        assert isinstance(menu, Gtk.Menu)
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


class TextBufferManager(GObject.Object):

    __gsignals__ = {
        'buffer-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            ()
        )
    }

    def __init__(self, message_input: MessageInputTextView) -> None:
        '''A manager for GtkSource.Buffers. Having a Buffer per contact
        allows us to have a GtkSource.UndoManager per contact.
        '''
        super().__init__()

        self._message_input = message_input
        self._contact: ChatContactT | None = None

        self._text_buffers: dict[ChatContactT, GtkSource.Buffer] = {}
        self._text_buffer_handlers: dict[ChatContactT, int] = {}
        self._language_handler_ids: dict[ChatContactT, int] = {}

        app.settings.connect_signal('use_speller', self._on_toggle_spell_check)

    def switch_contact(self, contact: ChatContactT) -> None:
        buf = self._text_buffers.get(contact)
        if buf is None:
            buf = GtkSource.Buffer()
            buf.create_tag('strong', weight=Pango.Weight.BOLD)
            buf.create_tag('emphasis', style=Pango.Style.ITALIC)
            buf.create_tag('strike', strikethrough=True)
            buf.create_tag('pre', family='monospace')
            self._text_buffers[contact] = buf
        else:
            buffer_handler = self._text_buffer_handlers[contact]
            buf.disconnect(buffer_handler)
            if app.is_installed('GSPELL'):
                gspell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(buf)
                checker = gspell_buffer.get_spell_checker()
                assert checker is not None
                checker_handler_id = self._language_handler_ids[contact]
                checker.disconnect(checker_handler_id)

        self._init_spell_checker(contact)
        self._set_spell_checker_language(contact)
        # Since the buffer changes when switching contacts, MessageActionsBox
        # cannot connect to a buffer's 'changed' signal.
        # Instead, we (re)connect each buffer and relay its 'changed' signal
        # via a custom 'buffer-changed' signal.
        self._text_buffer_handlers[contact] = buf.connect(
            'changed', self._on_buffer_changed)
        self._message_input.set_buffer(buf)

        self._contact = contact

    def _on_buffer_changed(self, _text_buffer: GtkSource.Buffer) -> None:
        self.emit('buffer-changed')

    def _init_spell_checker(self, contact: ChatContactT) -> None:
        if not app.is_installed('GSPELL'):
            return

        checker = Gspell.Checker.new(Gspell.language_get_default())

        buf = self._text_buffers[contact]
        gspell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(buf)
        gspell_buffer.set_spell_checker(checker)

        view = Gspell.TextView.get_from_gtk_text_view(self._message_input)
        view.set_enable_language_menu(True)

        self._on_toggle_spell_check()

        self._language_handler_ids[contact] = checker.connect(
            'notify::language', self._on_language_changed)

    def _on_toggle_spell_check(self, *args: Any) -> None:
        if not app.is_installed('GSPELL'):
            return

        use_spell_check = app.settings.get('use_speller')
        spell_view = Gspell.TextView.get_from_gtk_text_view(self._message_input)
        spell_view.set_inline_spell_checking(use_spell_check)

    def _get_spell_checker_language(self,
                                    contact: ChatContactT
                                    ) -> Gspell.Language | None:

        lang = contact.settings.get('speller_language')
        if not lang:
            # use the default one
            lang = app.settings.get('speller_language')
            if not lang:
                lang = get_default_lang()

        assert isinstance(lang, str)
        lang = Gspell.language_lookup(lang)
        if lang is None:
            return Gspell.language_get_default()
        return lang

    def _set_spell_checker_language(self, contact: ChatContactT) -> None:
        if not app.is_installed('GSPELL'):
            return

        buf = self._text_buffers[contact]
        gspell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(buf)
        checker = gspell_buffer.get_spell_checker()
        assert checker is not None
        lang = self._get_spell_checker_language(contact)

        handler_id = self._language_handler_ids[contact]
        with checker.handler_block(handler_id):
            checker.set_language(lang)

    def _on_language_changed(self,
                             checker: Gspell.Checker,
                             _param: Any) -> None:

        gspell_lang = checker.get_language()
        if gspell_lang is not None:
            assert self._contact is not None
            self._contact.settings.set('speller_language',
                                       gspell_lang.get_code())
