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

from enum import IntEnum
from collections import OrderedDict

from gi.repository import GdkPixbuf
from gi.repository import Gtk

class Emoji(IntEnum):
    ...

def is_emoji(codepoints: str) -> bool: ...
def get_emoji_font() -> str: ...
def get_emoji_pixbuf(codepoints: str) -> GdkPixbuf.Pixbuf: ...

class EmojiData(OrderedDict):
    def get_regex(self) -> str: ...

class EmojiPixbufs(dict):
    @property
    def complete(self) -> bool: ...
    @complete.setter
    def complete(self, value: bool) -> None: ...
    def clear(self) -> None: ...
    def append_marks(self,
                     textview: Gtk.TextView,
                     start: Gtk.TextMark,
                     end: Gtk.TextMark,
                     codepoint: str) -> None: ...

emoji_pixbufs: EmojiPixbufs
emoji_ascii_data: dict[str, str]
emoji_data: EmojiData
