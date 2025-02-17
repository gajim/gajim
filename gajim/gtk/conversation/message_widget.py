# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.styling import ParsingResult
from gajim.common.styling import PlainBlock
from gajim.common.styling import PreBlock
from gajim.common.styling import process
from gajim.common.styling import QuoteBlock

from gajim.gtk.const import MAX_MESSAGE_LENGTH
from gajim.gtk.conversation.code_widget import CodeWidget
from gajim.gtk.conversation.plain_widget import PlainWidget
from gajim.gtk.conversation.quote_widget import QuoteWidget
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import iterate_children
from gajim.gtk.widgets import GajimAppWindow

ContentT = ParsingResult | QuoteBlock


class MessageWidget(Gtk.Box, SignalManager):
    def __init__(self, account: str, selectable: bool = True) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        SignalManager.__init__(self)

        self._account = account
        self._selectable = selectable

        self._content: ContentT | None = None
        self._original_text = ""
        self._action_phrase_text = ""

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def get_content(self) -> ContentT | None:
        return self._content

    def get_text(self) -> str:
        if self._content is not None:
            return self._original_text
        return self._action_phrase_text

    def set_selectable(self, selectable: bool) -> None:
        for widget in iterate_children(self):
            if isinstance(widget, PlainWidget):
                widget.set_selectable(selectable)

    def add_with_styling(self, text: str, nickname: str | None = None) -> None:

        self._original_text = text
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH]

        if text.startswith("/me ") and nickname is not None:
            self._add_action_phrase(text, nickname)
            if len(self._original_text) > MAX_MESSAGE_LENGTH:
                self._add_read_more_button(self._original_text)
            return

        result = process(text)
        self.add_content(result)
        if len(self._original_text) > MAX_MESSAGE_LENGTH:
            self._add_read_more_button(self._original_text)

    def _add_action_phrase(self, text: str, nickname: str):
        self.clear()
        widget = PlainWidget(self._account, self._selectable)
        widget.add_action_phrase(text, nickname)
        self.append(widget)

        self._action_phrase_text = text.replace("/me", f"* {nickname}", 1)

    def add_content(self, content: ContentT) -> None:
        self.clear()
        self._content = content
        for block in content.blocks:
            if isinstance(block, PlainBlock):
                widget = PlainWidget(self._account, self._selectable)
                widget.add_content(block)
                self.append(widget)
                continue

            if isinstance(block, PreBlock):
                widget = CodeWidget(self._account)
                widget.add_content(block)
                self.append(widget)
                continue

            if isinstance(block, QuoteBlock):
                message_widget = MessageWidget(self._account, self._selectable)
                message_widget.add_content(block)
                widget = QuoteWidget(self._account)
                widget.append(message_widget)
                self.append(widget)
                continue

    def _add_read_more_button(self, text: str) -> None:
        link_button = Gtk.LinkButton(label=_("[read more]"))
        link_button.set_halign(Gtk.Align.START)
        self._connect(link_button, "activate-link", self._on_read_more, text)
        self.append(link_button)

    def _on_read_more(self, _button: Gtk.LinkButton, text: str) -> bool:
        FullMessageWindow(text)
        return True

    def clear(self) -> None:
        container_remove_all(self)


class FullMessageWindow(GajimAppWindow):
    def __init__(self, text: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="FullMessageWindow",
            title=_("Full Message View"),
            default_width=800,
            default_height=800,
        )

        textview = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
        )
        textview.get_buffer().set_text(text)

        scrolled = Gtk.ScrolledWindow(child=textview, hexpand=True)

        box = Gtk.Box()
        box.append(scrolled)

        self.set_child(box)
        self.show()

    def _cleanup(self) -> None:
        pass
