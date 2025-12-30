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
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource
from gi.repository import Pango

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.i18n import get_default_lang
from gajim.common.storage.archive import models as mod
from gajim.common.styling import PlainBlock
from gajim.common.styling import process
from gajim.common.types import ChatContactT

from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.completion.commands import CommandsCompletionProvider
from gajim.gtk.completion.emoji import EmojiCompletionProvider
from gajim.gtk.completion.nickname import NicknameCompletionProvider
from gajim.gtk.completion.popover import CompletionPopover
from gajim.gtk.const import MAX_MESSAGE_LENGTH
from gajim.gtk.menus import get_message_input_extra_context_menu
from gajim.gtk.util.misc import scroll_to
from gajim.gtk.widgets import GdkRectangle

if app.is_installed("SPELLING") or typing.TYPE_CHECKING:
    from gi.repository import Spelling

FORMAT_CHARS: dict[str, str] = {
    "bold": "*",
    "italic": "_",
    "strike": "~",
    "pre": "`",
}

log = logging.getLogger("gajim.gtk.message_input")


class MessageInputTextView(GtkSource.View, EventHelper):
    """
    A GtkSource.View for chat message input
    """

    __gsignals__ = {
        "buffer-changed": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (),
        ),
    }

    def __init__(self, parent: Gtk.Widget) -> None:
        GtkSource.View.__init__(
            self,
            accepts_tab=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            margin_top=3,
            margin_bottom=3,
            valign=Gtk.Align.CENTER,
        )
        EventHelper.__init__(self)

        self._parent = parent
        self._completion_providers = [
            EmojiCompletionProvider(),
            CommandsCompletionProvider(),
            NicknameCompletionProvider(),
        ]

        self.add_css_class("gajim-conversation-text")
        self.add_css_class("message-input-textview")

        self._contact: ChatContactT | None = None

        self._text_buffer_manager = TextBufferManager(self)
        self._text_buffer_manager.connect("buffer-changed", self._on_buffer_changed)

        self._completion_popover = CompletionPopover(self)
        self._completion_popover.connect(
            "completion-picked", self._on_completion_picked
        )

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture_secondary_click.connect("pressed", self._on_secondary_click)
        self.add_controller(gesture_secondary_click)

        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("enter", self._on_focus_enter)
        focus_controller.connect("leave", self._on_focus_leave)
        self.add_controller(focus_controller)

        manager = app.app.get_shortcut_manager()
        manager.install_shortcuts(self, ["input", "input-global"])

        self.connect_after("paste-clipboard", self._after_paste_clipboard)

        self._speller_menu: Gio.MenuModel | None = None
        self._update_extra_menu()

        app.plugin_manager.gui_extension_point("message_input", self)

        self.register_events(
            [
                ("register-actions", ged.GUI2, self._on_register_actions),
            ]
        )

    def _on_register_actions(self, _event: events.RegisterActions) -> None:
        actions = [
            "input-focus",
            "input-bold",
            "input-italic",
            "input-strike",
            "input-emoji",
        ]

        for action in actions:
            action = app.window.get_action(action)
            action.connect("activate", self._on_action)

    def _on_action(
        self, action: Gio.SimpleAction, param: GLib.Variant | None
    ) -> int | None:
        if self._contact is None:
            return

        action_name = action.get_name()
        log.warning("Activate action: %s", action_name)

        match action_name:
            case "input-focus":
                self.grab_focus_delayed()

            case "input-bold" | "input-italic" | "input-strike":
                self._apply_formatting(action_name.removeprefix("input-"))

            case "input-emoji":
                self.emit("insert-emoji")

            case _:
                pass

    def get_completion_popover(self) -> CompletionPopover:
        return self._completion_popover

    def grab_focus_delayed(self) -> bool:
        # Use this function if calling via GLib.idle_add to avoid
        # creating a loop raising CPU load
        self.grab_focus()
        return False

    def start_correction(self, message: mod.Message | None = None) -> None:
        if message is None:
            return

        self.clear()
        self.grab_focus()

        text = message.text
        assert text is not None

        self.insert_text(text)

    def end_correction(self) -> None:
        self.clear()

    def switch_contact(self, contact: ChatContactT) -> None:
        self._text_buffer_manager.switch_contact(contact)
        self.clear()
        self._contact = contact

    def set_speller_menu(self, menu: Gio.MenuModel) -> None:
        self._speller_menu = menu
        self._update_extra_menu()

    def _update_extra_menu(self) -> None:
        menu = get_message_input_extra_context_menu()
        if self._speller_menu is not None:
            menu.append_section(_("Spell Checking"), self._speller_menu)
        self.set_extra_menu(menu)

    def _on_buffer_changed(self, _text_buffer_manager: TextBufferManager) -> None:
        buf = self.get_buffer()
        if self._populate_completion(buf):
            _success, rect = self.compute_bounds(self._parent)
            point = rect.get_top_left()
            rect = GdkRectangle(int(point.x), int(point.y) - 20, 1, 1)
            self._completion_popover.set_pointing_to(rect)
            self._completion_popover.popup()
        else:
            self._completion_popover.popdown()

        self._on_text_changed()

        self.emit("buffer-changed")

    @staticmethod
    def _get_completion_candidate_bounds(
        text_buffer: Gtk.TextBuffer,
    ) -> tuple[Gtk.TextIter, Gtk.TextIter]:
        end = text_buffer.get_iter_at_mark(text_buffer.get_insert())

        _success, start_line_iter = text_buffer.get_iter_at_line(end.get_line())

        search_res = end.backward_search(
            " ",
            Gtk.TextSearchFlags.TEXT_ONLY | Gtk.TextSearchFlags.CASE_INSENSITIVE,
            start_line_iter,
        )
        if search_res is None:
            start = start_line_iter
        else:
            start, _ = search_res
            start.forward_char()
        return start, end

    def _populate_completion(self, buf: Gtk.TextBuffer) -> bool:
        start, end = self._get_completion_candidate_bounds(buf)
        candidate = buf.get_text(start, end, False)

        for provider in self._completion_providers:
            if not provider.check(candidate, start):
                continue

            if provider.populate(candidate, self._contact):
                self._completion_popover.set_provider(provider)
                return True
        return False

    def _on_completion_picked(
        self, popover: CompletionPopover, complete_string: str
    ) -> None:
        buf = self.get_buffer()
        start, end = self._get_completion_candidate_bounds(buf)
        buf.delete(start, end)
        buf.insert(start, complete_string)
        self.grab_focus()

    def _on_secondary_click(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:
        # Place the cursor at click position to trigger an update
        # for spelling suggestions, see:
        # https://gitlab.gnome.org/GNOME/libspelling/-/issues/5
        buf = self.get_buffer()
        if buf.get_has_selection():
            # Don't place cursor if text is selected, otherwise the selection is changed
            return Gdk.EVENT_PROPAGATE

        _, iter_, _ = self.get_iter_at_position(int(x), int(y))
        buf.place_cursor(iter_)
        return Gdk.EVENT_PROPAGATE

    def _on_focus_enter(self, _focus_controller: Gtk.EventControllerFocus) -> None:
        scrolled = self.get_parent()
        assert scrolled
        scrolled.add_css_class("message-input-focus")

    def _on_focus_leave(self, _focus_controller: Gtk.EventControllerFocus) -> None:
        scrolled = self.get_parent()
        assert scrolled
        scrolled.remove_css_class("message-input-focus")
        if not self.has_focus():
            self._completion_popover.popdown()

    def _clear_tags(self) -> None:
        to_remove: list[Gtk.TextTag] = []

        def _check(tag: Gtk.TextTag) -> None:
            if tag.get_property("underline-rgba-set") is True:
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
                    start_iter = buf.get_iter_at_offset(span.start + block.start)
                    end_iter = buf.get_iter_at_offset(span.end + block.start)
                    buf.apply_tag_by_name(span.name, start_iter, end_iter)

    def insert_text(self, text: str) -> None:
        self.get_buffer().insert_at_cursor(text)

    def insert_newline(self) -> None:
        # Reset IMContext to clear preedit state
        self.reset_im_context()
        buf = self.get_buffer()
        buf.insert_at_cursor("\n")
        mark = buf.get_insert()
        iter_ = buf.get_iter_at_mark(mark)
        if buf.get_end_iter().equal(iter_):
            GLib.idle_add(scroll_to, self.get_parent(), "bottom")

    @property
    def has_text(self) -> bool:
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, True)
        return text != ""

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
            GLib.idle_add(scroll_to, textview.get_parent(), "bottom")

    def _get_active_iters(self) -> tuple[Gtk.TextIter, Gtk.TextIter]:
        buf = self.get_buffer()
        return_val = buf.get_selection_bounds()
        if return_val:  # if something is selected
            start, end = return_val[0], return_val[1]
        else:
            start, end = buf.get_bounds()
        return (start, end)

    def _apply_formatting(self, formatting: str) -> None:
        format_char = FORMAT_CHARS[formatting]

        buf = self.get_buffer()
        start, end = self._get_active_iters()
        start_offset = start.get_offset()
        end_offset = end.get_offset()

        text = buf.get_text(start, end, True)
        if text.startswith(format_char) and text.endswith(format_char):
            # (Selected) text begins and ends with formatting chars
            # -> remove them
            buf.delete(start, buf.get_iter_at_offset(start_offset + 1))
            buf.delete(
                buf.get_iter_at_offset(end_offset - 2),
                buf.get_iter_at_offset(end_offset - 1),
            )
            return

        ext_start = buf.get_iter_at_offset(start_offset - 1)
        ext_end = buf.get_iter_at_offset(end_offset + 1)
        ext_text = buf.get_text(ext_start, ext_end, True)
        if ext_text.startswith(format_char) and ext_text.endswith(format_char):
            # (Selected) text is surrounded by formatting chars -> remove them
            buf.delete(ext_start, buf.get_iter_at_offset(start_offset))
            buf.delete(
                buf.get_iter_at_offset(end_offset - 1),
                buf.get_iter_at_offset(end_offset),
            )
            return

        # No formatting chars found at start/end or surrounding -> add them
        buf.insert(start, format_char, -1)
        buf.insert(buf.get_iter_at_offset(end_offset + 1), format_char, -1)
        buf.select_range(
            buf.get_iter_at_offset(start_offset), buf.get_iter_at_offset(end_offset + 2)
        )

    def clear(self, *args: Any) -> None:
        self.activate_action("text.clear")

    def undo(self, *args: Any) -> None:
        buf = self.get_buffer()
        if buf.get_can_undo():
            buf.undo()

    def redo(self, *args: Any) -> None:
        buf = self.get_buffer()
        if buf.get_can_redo():
            buf.redo()

    def mention_participant(self, name: str) -> None:
        gc_refer_to_nick_char = app.settings.get("gc_refer_to_nick_char")
        text = f"{name}{gc_refer_to_nick_char} "
        self.insert_text(text)
        self.grab_focus()

    def insert_as_quote(self, text: str) -> None:
        text = "> " + text.replace("\n", "\n> ") + "\n"
        self.insert_text(text)
        self.grab_focus()

    def insert_as_code_block(self, text: str) -> None:
        self.insert_text(f"```\n{text}\n```")
        self.grab_focus()

    def paste_as_quote(self) -> None:
        clipboard = self.get_clipboard()
        clipboard.read_text_async(
            None, self._on_clipboard_read_text_finished, "paste-as-quote"
        )

    def paste_as_code_block(self) -> None:
        clipboard = self.get_clipboard()
        clipboard.read_text_async(
            None, self._on_clipboard_read_text_finished, "paste-as-code-block"
        )

    def _on_clipboard_read_text_finished(
        self, clipboard: Gdk.Clipboard, result: Gio.AsyncResult, action_name: str
    ) -> None:
        try:
            text = clipboard.read_text_finish(result)
        except Exception as e:
            InformationAlertDialog(_("Pasting Content Failed"), _("Error: %s") % e)
            return

        if text is None:
            log.info("No text pasted")
            return

        if action_name == "paste-as-quote":
            self.insert_as_quote(text)
        elif action_name == "paste-as-code-block":
            self.insert_as_code_block(text)


class TextBufferManager(GObject.Object):
    __gsignals__ = {
        "buffer-changed": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (),
        )
    }

    def __init__(self, message_input: MessageInputTextView) -> None:
        """A manager for GtkSource.Buffers. Having a Buffer per contact
        allows us to have a GtkSource.UndoManager per contact.
        """
        super().__init__()

        self._message_input = message_input
        self._contact: ChatContactT | None = None

        self._text_buffers: dict[ChatContactT, GtkSource.Buffer] = {}
        self._text_buffer_handlers: dict[ChatContactT, int] = {}

        self._spelling_adapters: dict[ChatContactT, Spelling.TextBufferAdapter] = {}
        self._spelling_language_handlers: dict[ChatContactT, int] = {}

        app.settings.connect_signal("use_speller", self._on_toggle_spell_check)

    def switch_contact(self, contact: ChatContactT) -> None:
        buf = self._text_buffers.get(contact)
        if buf is None:
            buf = GtkSource.Buffer()
            buf.create_tag("strong", weight=Pango.Weight.BOLD)
            buf.create_tag("emphasis", style=Pango.Style.ITALIC)
            buf.create_tag("strike", strikethrough=True)
            buf.create_tag("pre", family="monospace")

            style_scheme = self._get_style_scheme(buf)
            if style_scheme is not None:
                buf.set_style_scheme(style_scheme)

            self._text_buffers[contact] = buf

            self._init_spell_checker(contact)
        else:
            buffer_handler = self._text_buffer_handlers[contact]
            buf.disconnect(buffer_handler)

            self._disconnect_spell_checker(contact)

        # Since the buffer changes when switching contacts, MessageActionsBox
        # cannot connect to a buffer's 'changed' signal.
        # Instead, we (re)connect each buffer and relay its 'changed' signal
        # via a custom 'buffer-changed' signal.
        self._text_buffer_handlers[contact] = buf.connect(
            "changed", self._on_buffer_changed
        )
        self._message_input.set_buffer(buf)

        self._connect_spell_checker(contact)

        self._contact = contact

    def _on_buffer_changed(self, _text_buffer: GtkSource.Buffer) -> None:
        self.emit("buffer-changed")

    def _get_style_scheme(self, buf: GtkSource.Buffer) -> GtkSource.StyleScheme | None:
        style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
        if app.css_config.prefer_dark:
            return style_scheme_manager.get_scheme("Adwaita-dark")
        return style_scheme_manager.get_scheme("Adwaita")

    def _init_spell_checker(self, contact: ChatContactT) -> None:
        if not app.is_installed("SPELLING"):
            return

        provider = Spelling.Provider.get_default()
        checker = Spelling.Checker.new(
            provider, self._get_spell_checker_language(contact)
        )

        text_buffer = self._text_buffers[contact]
        self._spelling_adapters[contact] = Spelling.TextBufferAdapter.new(
            text_buffer,
            checker,
        )

    def _connect_spell_checker(self, contact: ChatContactT) -> None:
        if not app.is_installed("SPELLING"):
            return

        adapter = self._spelling_adapters[contact]
        speller_menu = adapter.get_menu_model()

        self._message_input.set_speller_menu(speller_menu)
        self._message_input.insert_action_group("spelling", adapter)

        adapter.set_enabled(app.settings.get("use_speller"))

        checker = adapter.get_checker()
        assert checker is not None
        self._spelling_language_handlers[contact] = checker.connect(
            "notify::language", self._on_language_changed
        )

    def _disconnect_spell_checker(self, contact: ChatContactT) -> None:
        if not app.is_installed("SPELLING"):
            return

        adapter = self._spelling_adapters[contact]
        checker = adapter.get_checker()
        assert checker is not None
        checker_handler_id = self._spelling_language_handlers[contact]
        checker.disconnect(checker_handler_id)

        self._message_input.insert_action_group("spelling", None)

    def _on_toggle_spell_check(self, *args: Any) -> None:
        if not app.is_installed("SPELLING"):
            return

        use_spell_check = app.settings.get("use_speller")
        for adapter in self._spelling_adapters.values():
            adapter.set_enabled(use_spell_check)

    def _get_spell_checker_language(self, contact: ChatContactT) -> str:
        lang = contact.settings.get("speller_language")
        if not lang:
            # use the default one
            lang = app.settings.get("speller_language")
            if not lang:
                lang = get_default_lang()

        return lang or "en"

    def _on_language_changed(self, checker: Spelling.Checker, _param: Any) -> None:
        language_code = checker.get_language()
        if language_code is not None:
            assert self._contact is not None
            handler_id = self._spelling_language_handlers[self._contact]
            with checker.handler_block(handler_id):
                self._contact.settings.set("speller_language", language_code)
