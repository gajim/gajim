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

class Emoji(IntEnum):
    ...

def is_emoji(codepoints: str) -> bool: ...
def get_emoji_pixbuf(codepoints: str) -> GdkPixbuf.Pixbuf: ...

class EmojiData(OrderedDict):
    ...

class EmojiPixbufs(dict):
    ...

class EmojiAsciiData(dict):
    ...

emoji_pixbufs = EmojiPixbufs()

emoji_ascii_data = EmojiAsciiData()

emoji_data = EmojiData()
