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
from typing import Union
from typing import cast

from gi.repository import Gtk

from gajim.common.styling import process
from gajim.common.styling import ParsingResult
from gajim.common.styling import PlainBlock
from gajim.common.styling import PreBlock
from gajim.common.styling import QuoteBlock

from .code_widget import CodeWidget
from .quote_widget import QuoteWidget
from .plain_widget import PlainWidget


ContentT = Union[ParsingResult, QuoteBlock]


class MessageWidget(Gtk.Box):
    def __init__(self, account: str, selectable: bool = True) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self._account = account
        self._selectable = selectable

        self._content = cast(ContentT, None)

    def get_content(self) -> ContentT:
        return self._content

    def get_text(self) -> str:
        return self._content.text

    def add_with_styling(self,
                         text: str,
                         nickname: Optional[str] = None) -> None:

        if text.startswith('/me') and nickname is not None:
            self._add_action_phrase(text, nickname)
            return

        result = process(text)
        self.add_content(result)

    def _add_action_phrase(self, text: str, nickname: str):
        widget = PlainWidget(self._account, self._selectable)
        widget.add_action_phrase(text, nickname)
        self.add(widget)

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
                widget.attach_message_widget(message_widget)
                self.add(widget)
                continue

        self.show_all()

    def clear(self) -> None:
        self.foreach(self.remove)
