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

from typing import Optional
from typing import Union

from gi.repository import Gdk
from gi.repository import Gtk

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

ContentT = Union[ParsingResult, QuoteBlock]


class MessageWidget(Gtk.Box):
    def __init__(self, account: str, selectable: bool = True) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self._account = account
        self._selectable = selectable

        self._content: ContentT | None = None
        self._original_text = ''
        self._action_phrase_text = ''

    def get_content(self) -> ContentT | None:
        return self._content

    def get_text(self) -> str:
        if self._content is not None:
            return self._original_text
        return self._action_phrase_text

    def set_selectable(self, selectable: bool) -> None:
        for widget in self.get_children():
            if isinstance(widget, PlainWidget):
                widget.set_selectable(selectable)

    def add_with_styling(self,
                         text: str,
                         nickname: Optional[str] = None) -> None:

        self._original_text = text
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH]

        if text.startswith('/me') and nickname is not None:
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
        widget.show_all()
        self.add(widget)

        self._action_phrase_text = text.replace('/me', f'* {nickname}', 1)

    def add_content(self, content: ContentT) -> None:
        self.clear()
        self._content = content
        for block in content.blocks:
            if isinstance(block, PlainBlock):
                widget = PlainWidget(self._account, self._selectable)
                widget.add_content(block)
                self.add(widget)
                continue

            if isinstance(block, PreBlock):
                widget = CodeWidget(self._account)
                widget.add_content(block)
                self.add(widget)
                continue

            if isinstance(block, QuoteBlock):
                message_widget = MessageWidget(self._account, self._selectable)
                message_widget.add_content(block)
                widget = QuoteWidget(self._account)
                widget.add(message_widget)
                self.add(widget)
                continue

        self.show_all()

    def _add_read_more_button(self, text: str) -> None:
        link_button = Gtk.LinkButton(label=_('[read more]'))
        link_button.set_halign(Gtk.Align.START)
        link_button.connect('activate-link', self._on_read_more, text)
        self.add(link_button)

    def _on_read_more(self, _button: Gtk.LinkButton, text: str) -> bool:
        FullMessageWindow(text)
        return True

    def clear(self) -> None:
        self.foreach(self.remove)


class FullMessageWindow(Gtk.ApplicationWindow):
    def __init__(self, text: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_size_request(800, 800)
        self.set_title(_('Full Message View'))
        self.get_style_context().add_class('dialog-margin')

        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_left_margin(3)
        textview.set_top_margin(3)
        textview.get_buffer().set_text(text)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)
        scrolled.add(textview)

        box = Gtk.Box()
        box.add(scrolled)

        self.add(box)
        self.show_all()

        self.connect('key-press-event', self._on_key_press_event)

    def _on_key_press_event(self,
                            _widget: Gtk.Widget,
                            event: Gdk.EventKey
                            ) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
