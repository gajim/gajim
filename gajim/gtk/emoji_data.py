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

# pylint: disable=too-many-lines

from typing import Optional

import re
import weakref
from enum import IntEnum
from collections import OrderedDict

from gi.repository import GdkPixbuf
from gi.repository import Gtk

_MODIFIERS = ['\U0001F3FB',
              '\U0001F3FC',
              '\U0001F3FD',
              '\U0001F3FE',
              '\U0001F3FF']


class Emoji(IntEnum):
    TEXT_SIZE = 18
    INPUT_SIZE = 14
    PARSE_HEIGHT = 24
    PARSE_WIDTH = 24
    PARSE_COLUMNS = 20


def is_emoji(codepoints: str) -> bool:
    if codepoints in emoji_data:
        return True
    if codepoints in emoji_ascii_data:
        return True
    return False


def get_emoji_pixbuf(codepoints: str) -> Optional[GdkPixbuf.Pixbuf]:
    ascii_codepoint = emoji_ascii_data.get(codepoints, None)
    if ascii_codepoint is not None:
        codepoints = ascii_codepoint

    pixbuf = emoji_pixbufs.get(codepoints, None)
    if pixbuf is None:
        return None
    pixbuf = pixbuf.scale_simple(Emoji.TEXT_SIZE,
                                 Emoji.TEXT_SIZE,
                                 GdkPixbuf.InterpType.HYPER)
    return pixbuf


class EmojiData(OrderedDict):
    def __getitem__(self, key):
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            for mod in _MODIFIERS:
                if mod in key:
                    key = key.replace(mod, '')
                    return OrderedDict.__getitem__(self, key)
            raise KeyError

    def __contains__(self, item):
        try:
            return bool(self[item])
        except KeyError:
            return False

    def get_regex(self) -> str:
        emojis = []
        for codepoint, attrs in self.items():
            if attrs.get('variations', False):
                for variation in attrs['variations'].keys():
                    emojis.append(variation)
            emojis.append(codepoint)

        emojis = sorted(emojis, key=len, reverse=True)
        return '(' + '|'.join(re.escape(u) for u in emojis) + ')'


class EmojiPixbufs(dict):
    _complete = False

    def __init__(self):
        dict.__init__(self)
        self._marks: weakref.WeakKeyDictionary[
            Gtk.TextView,
            list[tuple[
                weakref.ReferenceType[Gtk.TextMark],
                weakref.ReferenceType[Gtk.TextMark],
                str]]
            ] = weakref.WeakKeyDictionary()

    @property
    def complete(self) -> bool:
        return self._complete

    @complete.setter
    def complete(self, value: bool) -> None:
        if value:
            self._replace_emojis()
            self._marks.clear()
        self._complete = value

    def clear(self) -> None:
        self.complete = False
        self._marks.clear()
        dict.clear(self)

    def append_marks(self,
                     textview: Gtk.TextView,
                     start: Gtk.TextMark,
                     end: Gtk.TextMark,
                     codepoint: str
                     ) -> None:
        # We have to assign some dummy data to the mark, or else
        # pygobject will not keep the python wrapper alive, which in turn
        # makes the weakref invalid as soon as the method ends
        start.dummy = 'x'  # type: ignore
        start_ref = weakref.ref(start)
        end.dummy = 'x'  # type: ignore
        end_ref = weakref.ref(end)
        if textview in self._marks:
            self._marks[textview].append((start_ref, end_ref, codepoint))
        else:
            self._marks[textview] = [(start_ref, end_ref, codepoint)]

    def _replace_emojis(self) -> None:
        for textview, emojis in self._marks.items():
            for emoji in emojis:
                start, end, codepoint = emoji
                if start() is None or end() is None:
                    # Marks are gone
                    continue
                ascii_codepoint = emoji_ascii_data.get(codepoint, None)
                if ascii_codepoint is not None:
                    codepoint = ascii_codepoint
                pixbuf = self.get(codepoint, None)
                if pixbuf is None:
                    # theme does not support this codepoint
                    continue
                pixbuf = pixbuf.scale_simple(Emoji.TEXT_SIZE,
                                             Emoji.TEXT_SIZE,
                                             GdkPixbuf.InterpType.HYPER)
                textview.replace_emojis(
                    start(), end(), pixbuf.copy(), codepoint)


emoji_pixbufs = EmojiPixbufs()

# pylint: disable=line-too-long

emoji_ascii_data: dict[str, str] = dict([
    ("':-D", '\U0001F605'),
    (':)', '\U0001F642'),
    (':-O', '\U0001F62e'),
    ('>:/', '\U0001F615'),
    ('*\\O/*', '\U0001F646'),
    ('#)', '\U0001F635'),
    (":'-)", '\U0001F602'),
    ('B-)', '\U0001F60e'),
    ('=#', '\U0001F636'),
    (':@', '\U0001F620'),
    ('=*', '\U0001F618'),
    (':-*', '\U0001F618'),
    ('>:\\', '\U0001F615'),
    ('\\O/', '\U0001F646'),
    ('D:', '\U0001F628'),
    ('*\\0/*', '\U0001F646'),
    (':-Þ', '\U0001F61b'),
    ('8)', '\U0001F60e'),
    (';D', '\U0001F609'),
    ('%)', '\U0001F635'),
    ('=X', '\U0001F636'),
    ('>:(', '\U0001F620'),
    (':-X', '\U0001F636'),
    ('>:O', '\U0001F62e'),
    (":')", '\U0001F602'),
    ('=)', '\U0001F642'),
    ('=(', '\U0001F61e'),
    ('>:-)', '\U0001F606'),
    ('=]', '\U0001F642'),
    ('O:-3', '\U0001F607'),
    ('-__-', '\U0001F611'),
    ('>:P', '\U0001F61c'),
    ("'=D", '\U0001F605'),
    ("'=(", '\U0001F613'),
    (':-(', '\U0001F61e'),
    (':-P', '\U0001F61b'),
    ('0;^)', '\U0001F607'),
    (':P', '\U0001F61b'),
    ("'=)", '\U0001F605'),
    (':-D', '\U0001F603'),
    (':\\', '\U0001F615'),
    ('0:)', '\U0001F607'),
    ('>:[', '\U0001F61e'),
    (';]', '\U0001F609'),
    (':Þ', '\U0001F61b'),
    (':-.', '\U0001F615'),
    (':b', '\U0001F61b'),
    (':-#', '\U0001F636'),
    ('\\0/', '\U0001F646'),
    ('O_O', '\U0001F62e'),
    ('>:-(', '\U0001F620'),
    (":'-(", '\U0001F622'),
    (':#', '\U0001F636'),
    ('>.<', '\U0001F623'),
    ('0:3', '\U0001F607'),
    ('O;-)', '\U0001F607'),
    ('=/', '\U0001F615'),
    (':D', '\U0001F603'),
    (':[', '\U0001F61e'),
    (':-[', '\U0001F61e'),
    ('=\\', '\U0001F615'),
    ('8-)', '\U0001F60e'),
    (':*', '\U0001F618'),
    ("':(", '\U0001F613'),
    ("':D", '\U0001F605'),
    ('*)', '\U0001F609'),
    ('<3', '\U00002764'),
    ('X)', '\U0001F635'),
    (';)', '\U0001F609'),
    ('8-D', '\U0001F60e'),
    ('O:)', '\U0001F607'),
    (':L', '\U0001F615'),
    ('B)', '\U0001F60e'),
    ('>;)', '\U0001F606'),
    ('</3', '\U0001F494'),
    (';(', '\U0001F622'),
    (':O', '\U0001F62e'),
    ('>=)', '\U0001F606'),
    (';^)', '\U0001F609'),
    (':-/', '\U0001F615'),
    ('O=)', '\U0001F607'),
    (':$', '\U0001F633'),
    (':-b', '\U0001F61b'),
    (';-(', '\U0001F622'),
    ('%-)', '\U0001F635'),
    (':/', '\U0001F615'),
    (':-)', '\U0001F642'),
    ('0:-3', '\U0001F607'),
    (":'(", '\U0001F622'),
    ('0;-)', '\U0001F607'),
    ('#-)', '\U0001F635'),
    (':(', '\U0001F61e'),
    ('B-D', '\U0001F60e'),
    (';-]', '\U0001F609'),
    ("':-)", '\U0001F605'),
    ('X-)', '\U0001F635'),
    (':]', '\U0001F642'),
    ('(y)', '\U0001F44d'),
    ('>:)', '\U0001F606'),
    ('0:-)', '\U0001F607'),
    ('O:-)', '\U0001F607'),
    ('O:3', '\U0001F607'),
    ('=L', '\U0001F615'),
    (':X', '\U0001F636'),
    ('=$', '\U0001F633'),
    (';-)', '\U0001F609'),
    ("':)", '\U0001F605'),
    ('X-P', '\U0001F61c'),
    ('-___-', '\U0001F611'),
    ('=P', '\U0001F61b'),
    (':^*', '\U0001F618'),
    ('=D', '\U0001F603'),
    ('*-)', '\U0001F609'),
    ("':-(", '\U0001F613'),
    ('-_-', '\U0001F611')
])

emoji_data = EmojiData([
    ('\U0001F600', {
        'desc': 'grinning face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F601', {
        'desc': 'beaming face with smiling eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F602', {
        'desc': 'face with tears of joy',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F923', {
        'desc': 'rolling on the floor laughing',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F603', {
        'desc': 'grinning face with big eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F604', {
        'desc': 'grinning face with smiling eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F605', {
        'desc': 'grinning face with sweat',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F606', {
        'desc': 'grinning squinting face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F609', {
        'desc': 'winking face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F60A', {
        'desc': 'smiling face with smiling eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F60B', {
        'desc': 'face savoring food',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F60E', {
        'desc': 'smiling face with sunglasses',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F60D', {
        'desc': 'smiling face with heart-eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F618', {
        'desc': 'face blowing a kiss',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F970', {
        'desc': 'smiling face with 3 hearts',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F617', {
        'desc': 'kissing face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F619', {
        'desc': 'kissing face with smiling eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F61A', {
        'desc': 'kissing face with closed eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000263A\U0000FE0F', {
        'desc': 'smiling face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True
    }),
    ('\U0000263A', {
        'desc': 'smiling face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F642', {
        'desc': 'slightly smiling face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F917', {
        'desc': 'hugging face',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F929', {
        'desc': 'star-struck',
        'group': 'Smileys & People',
        'subgroup': 'face-positive',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F914', {
        'desc': 'thinking face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F928', {
        'desc': 'face with raised eyebrow',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F610', {
        'desc': 'neutral face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F611', {
        'desc': 'expressionless face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F636', {
        'desc': 'face without mouth',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F644', {
        'desc': 'face with rolling eyes',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F60F', {
        'desc': 'smirking face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F623', {
        'desc': 'persevering face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F625', {
        'desc': 'sad but relieved face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F62E', {
        'desc': 'face with open mouth',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F910', {
        'desc': 'zipper-mouth face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F62F', {
        'desc': 'hushed face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F62A', {
        'desc': 'sleepy face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F62B', {
        'desc': 'tired face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F634', {
        'desc': 'sleeping face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F60C', {
        'desc': 'relieved face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F61B', {
        'desc': 'face with tongue',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F61C', {
        'desc': 'winking face with tongue',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F61D', {
        'desc': 'squinting face with tongue',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F924', {
        'desc': 'drooling face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F612', {
        'desc': 'unamused face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F613', {
        'desc': 'downcast face with sweat',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F614', {
        'desc': 'pensive face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F615', {
        'desc': 'confused face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F643', {
        'desc': 'upside-down face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F911', {
        'desc': 'money-mouth face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F632', {
        'desc': 'astonished face',
        'group': 'Smileys & People',
        'subgroup': 'face-neutral',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002639\U0000FE0F', {
        'desc': 'frowning face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True
    }),
    ('\U00002639', {
        'desc': 'frowning face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F641', {
        'desc': 'slightly frowning face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F616', {
        'desc': 'confounded face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F61E', {
        'desc': 'disappointed face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F61F', {
        'desc': 'worried face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F624', {
        'desc': 'face with steam from nose',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F622', {
        'desc': 'crying face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F62D', {
        'desc': 'loudly crying face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F626', {
        'desc': 'frowning face with open mouth',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F627', {
        'desc': 'anguished face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F628', {
        'desc': 'fearful face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F629', {
        'desc': 'weary face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F92F', {
        'desc': 'exploding head',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F62C', {
        'desc': 'grimacing face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F630', {
        'desc': 'anxious face with sweat',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F631', {
        'desc': 'face screaming in fear',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F975', {
        'desc': 'hot face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F976', {
        'desc': 'cold face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F633', {
        'desc': 'flushed face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F92A', {
        'desc': 'zany face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F635', {
        'desc': 'dizzy face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F621', {
        'desc': 'pouting face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F620', {
        'desc': 'angry face',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F92C', {
        'desc': 'face with symbols on mouth',
        'group': 'Smileys & People',
        'subgroup': 'face-negative',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F637', {
        'desc': 'face with medical mask',
        'group': 'Smileys & People',
        'subgroup': 'face-sick',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F912', {
        'desc': 'face with thermometer',
        'group': 'Smileys & People',
        'subgroup': 'face-sick',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F915', {
        'desc': 'face with head-bandage',
        'group': 'Smileys & People',
        'subgroup': 'face-sick',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F922', {
        'desc': 'nauseated face',
        'group': 'Smileys & People',
        'subgroup': 'face-sick',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F92E', {
        'desc': 'face vomiting',
        'group': 'Smileys & People',
        'subgroup': 'face-sick',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F927', {
        'desc': 'sneezing face',
        'group': 'Smileys & People',
        'subgroup': 'face-sick',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F607', {
        'desc': 'smiling face with halo',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F920', {
        'desc': 'cowboy hat face',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F973', {
        'desc': 'partying face',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F974', {
        'desc': 'woozy face',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F97A', {
        'desc': 'pleading face',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F925', {
        'desc': 'lying face',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F92B', {
        'desc': 'shushing face',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F92D', {
        'desc': 'face with hand over mouth',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D0', {
        'desc': 'face with monocle',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F913', {
        'desc': 'nerd face',
        'group': 'Smileys & People',
        'subgroup': 'face-role',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F608', {
        'desc': 'smiling face with horns',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F47F', {
        'desc': 'angry face with horns',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F921', {
        'desc': 'clown face',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F479', {
        'desc': 'ogre',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F47A', {
        'desc': 'goblin',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F480', {
        'desc': 'skull',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002620\U0000FE0F', {
        'desc': 'skull and crossbones',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True
    }),
    ('\U00002620', {
        'desc': 'skull and crossbones',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F47B', {
        'desc': 'ghost',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F47D', {
        'desc': 'alien',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F47E', {
        'desc': 'alien monster',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F916', {
        'desc': 'robot face',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A9', {
        'desc': 'pile of poo',
        'group': 'Smileys & People',
        'subgroup': 'face-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F63A', {
        'desc': 'grinning cat face',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F638', {
        'desc': 'grinning cat face with smiling eyes',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F639', {
        'desc': 'cat face with tears of joy',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F63B', {
        'desc': 'smiling cat face with heart-eyes',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F63C', {
        'desc': 'cat face with wry smile',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F63D', {
        'desc': 'kissing cat face',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F640', {
        'desc': 'weary cat face',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F63F', {
        'desc': 'crying cat face',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F63E', {
        'desc': 'pouting cat face',
        'group': 'Smileys & People',
        'subgroup': 'cat-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F648', {
        'desc': 'see-no-evil monkey',
        'group': 'Smileys & People',
        'subgroup': 'monkey-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F649', {
        'desc': 'hear-no-evil monkey',
        'group': 'Smileys & People',
        'subgroup': 'monkey-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F64A', {
        'desc': 'speak-no-evil monkey',
        'group': 'Smileys & People',
        'subgroup': 'monkey-face',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F476', {
        'desc': 'baby',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F476\U0001F3FB', {
                'desc': 'baby: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F476\U0001F3FC', {
                'desc': 'baby: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F476\U0001F3FD', {
                'desc': 'baby: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F476\U0001F3FE', {
                'desc': 'baby: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F476\U0001F3FF', {
                'desc': 'baby: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D2', {
        'desc': 'child',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D2\U0001F3FB', {
                'desc': 'child: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D2\U0001F3FC', {
                'desc': 'child: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D2\U0001F3FD', {
                'desc': 'child: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D2\U0001F3FE', {
                'desc': 'child: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D2\U0001F3FF', {
                'desc': 'child: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F466', {
        'desc': 'boy',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F466\U0001F3FB', {
                'desc': 'boy: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F466\U0001F3FC', {
                'desc': 'boy: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F466\U0001F3FD', {
                'desc': 'boy: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F466\U0001F3FE', {
                'desc': 'boy: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F466\U0001F3FF', {
                'desc': 'boy: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F467', {
        'desc': 'girl',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F467\U0001F3FB', {
                'desc': 'girl: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F467\U0001F3FC', {
                'desc': 'girl: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F467\U0001F3FD', {
                'desc': 'girl: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F467\U0001F3FE', {
                'desc': 'girl: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F467\U0001F3FF', {
                'desc': 'girl: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D1', {
        'desc': 'adult',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D1\U0001F3FB', {
                'desc': 'adult: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D1\U0001F3FC', {
                'desc': 'adult: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D1\U0001F3FD', {
                'desc': 'adult: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D1\U0001F3FE', {
                'desc': 'adult: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D1\U0001F3FF', {
                'desc': 'adult: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F468', {
        'desc': 'man',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB', {
                'desc': 'man: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F468\U0001F3FC', {
                'desc': 'man: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F468\U0001F3FD', {
                'desc': 'man: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F468\U0001F3FE', {
                'desc': 'man: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F468\U0001F3FF', {
                'desc': 'man: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F469', {
        'desc': 'woman',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB', {
                'desc': 'woman: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F469\U0001F3FC', {
                'desc': 'woman: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F469\U0001F3FD', {
                'desc': 'woman: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F469\U0001F3FE', {
                'desc': 'woman: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F469\U0001F3FF', {
                'desc': 'woman: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D3', {
        'desc': 'older adult',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D3\U0001F3FB', {
                'desc': 'older adult: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D3\U0001F3FC', {
                'desc': 'older adult: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D3\U0001F3FD', {
                'desc': 'older adult: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D3\U0001F3FE', {
                'desc': 'older adult: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D3\U0001F3FF', {
                'desc': 'older adult: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F474', {
        'desc': 'old man',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F474\U0001F3FB', {
                'desc': 'old man: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F474\U0001F3FC', {
                'desc': 'old man: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F474\U0001F3FD', {
                'desc': 'old man: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F474\U0001F3FE', {
                'desc': 'old man: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F474\U0001F3FF', {
                'desc': 'old man: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F475', {
        'desc': 'old woman',
        'group': 'Smileys & People',
        'subgroup': 'person',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F475\U0001F3FB', {
                'desc': 'old woman: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F475\U0001F3FC', {
                'desc': 'old woman: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F475\U0001F3FD', {
                'desc': 'old woman: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F475\U0001F3FE', {
                'desc': 'old woman: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F475\U0001F3FF', {
                'desc': 'old woman: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F468\U0000200D\U00002695\U0000FE0F', {
        'desc': 'man health worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U00002695\U0000FE0F', {
                'desc': 'man health worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U00002695\U0000FE0F', {
                'desc': 'man health worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U00002695\U0000FE0F', {
                'desc': 'man health worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U00002695\U0000FE0F', {
                'desc': 'man health worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U00002695\U0000FE0F', {
                'desc': 'man health worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U00002695', {
        'desc': 'man health worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U00002695', {
                'desc': 'man health worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U00002695', {
                'desc': 'man health worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U00002695', {
                'desc': 'man health worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U00002695', {
                'desc': 'man health worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U00002695', {
                'desc': 'man health worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F469\U0000200D\U00002695\U0000FE0F', {
        'desc': 'woman health worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U00002695\U0000FE0F', {
                'desc': 'woman health worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U00002695\U0000FE0F', {
                'desc': 'woman health worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U00002695\U0000FE0F', {
                'desc': 'woman health worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U00002695\U0000FE0F', {
                'desc': 'woman health worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U00002695\U0000FE0F', {
                'desc': 'woman health worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U00002695', {
        'desc': 'woman health worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U00002695', {
                'desc': 'woman health worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U00002695', {
                'desc': 'woman health worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U00002695', {
                'desc': 'woman health worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U00002695', {
                'desc': 'woman health worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U00002695', {
                'desc': 'woman health worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F468\U0000200D\U0001F393', {
        'desc': 'man student',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F393', {
                'desc': 'man student: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F393', {
                'desc': 'man student: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F393', {
                'desc': 'man student: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F393', {
                'desc': 'man student: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F393', {
                'desc': 'man student: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F393', {
        'desc': 'woman student',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F393', {
                'desc': 'woman student: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F393', {
                'desc': 'woman student: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F393', {
                'desc': 'woman student: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F393', {
                'desc': 'woman student: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F393', {
                'desc': 'woman student: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F3EB', {
        'desc': 'man teacher',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F3EB', {
                'desc': 'man teacher: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F3EB', {
                'desc': 'man teacher: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F3EB', {
                'desc': 'man teacher: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F3EB', {
                'desc': 'man teacher: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F3EB', {
                'desc': 'man teacher: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F3EB', {
        'desc': 'woman teacher',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F3EB', {
                'desc': 'woman teacher: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F3EB', {
                'desc': 'woman teacher: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F3EB', {
                'desc': 'woman teacher: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F3EB', {
                'desc': 'woman teacher: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F3EB', {
                'desc': 'woman teacher: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U00002696\U0000FE0F', {
        'desc': 'man judge',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U00002696\U0000FE0F', {
                'desc': 'man judge: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U00002696\U0000FE0F', {
                'desc': 'man judge: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U00002696\U0000FE0F', {
                'desc': 'man judge: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U00002696\U0000FE0F', {
                'desc': 'man judge: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U00002696\U0000FE0F', {
                'desc': 'man judge: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U00002696', {
        'desc': 'man judge',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U00002696', {
                'desc': 'man judge: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U00002696', {
                'desc': 'man judge: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U00002696', {
                'desc': 'man judge: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U00002696', {
                'desc': 'man judge: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U00002696', {
                'desc': 'man judge: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F469\U0000200D\U00002696\U0000FE0F', {
        'desc': 'woman judge',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U00002696\U0000FE0F', {
                'desc': 'woman judge: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U00002696\U0000FE0F', {
                'desc': 'woman judge: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U00002696\U0000FE0F', {
                'desc': 'woman judge: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U00002696\U0000FE0F', {
                'desc': 'woman judge: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U00002696\U0000FE0F', {
                'desc': 'woman judge: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U00002696', {
        'desc': 'woman judge',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U00002696', {
                'desc': 'woman judge: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U00002696', {
                'desc': 'woman judge: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U00002696', {
                'desc': 'woman judge: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U00002696', {
                'desc': 'woman judge: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U00002696', {
                'desc': 'woman judge: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F468\U0000200D\U0001F33E', {
        'desc': 'man farmer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F33E', {
                'desc': 'man farmer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F33E', {
                'desc': 'man farmer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F33E', {
                'desc': 'man farmer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F33E', {
                'desc': 'man farmer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F33E', {
                'desc': 'man farmer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F33E', {
        'desc': 'woman farmer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F33E', {
                'desc': 'woman farmer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F33E', {
                'desc': 'woman farmer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F33E', {
                'desc': 'woman farmer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F33E', {
                'desc': 'woman farmer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F33E', {
                'desc': 'woman farmer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F373', {
        'desc': 'man cook',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F373', {
                'desc': 'man cook: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F373', {
                'desc': 'man cook: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F373', {
                'desc': 'man cook: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F373', {
                'desc': 'man cook: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F373', {
                'desc': 'man cook: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F373', {
        'desc': 'woman cook',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F373', {
                'desc': 'woman cook: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F373', {
                'desc': 'woman cook: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F373', {
                'desc': 'woman cook: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F373', {
                'desc': 'woman cook: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F373', {
                'desc': 'woman cook: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F527', {
        'desc': 'man mechanic',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F527', {
                'desc': 'man mechanic: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F527', {
                'desc': 'man mechanic: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F527', {
                'desc': 'man mechanic: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F527', {
                'desc': 'man mechanic: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F527', {
                'desc': 'man mechanic: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F527', {
        'desc': 'woman mechanic',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F527', {
                'desc': 'woman mechanic: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F527', {
                'desc': 'woman mechanic: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F527', {
                'desc': 'woman mechanic: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F527', {
                'desc': 'woman mechanic: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F527', {
                'desc': 'woman mechanic: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F3ED', {
        'desc': 'man factory worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F3ED', {
                'desc': 'man factory worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F3ED', {
                'desc': 'man factory worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F3ED', {
                'desc': 'man factory worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F3ED', {
                'desc': 'man factory worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F3ED', {
                'desc': 'man factory worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F3ED', {
        'desc': 'woman factory worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F3ED', {
                'desc': 'woman factory worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F3ED', {
                'desc': 'woman factory worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F3ED', {
                'desc': 'woman factory worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F3ED', {
                'desc': 'woman factory worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F3ED', {
                'desc': 'woman factory worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F4BC', {
        'desc': 'man office worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F4BC', {
                'desc': 'man office worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F4BC', {
                'desc': 'man office worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F4BC', {
                'desc': 'man office worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F4BC', {
                'desc': 'man office worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F4BC', {
                'desc': 'man office worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F4BC', {
        'desc': 'woman office worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F4BC', {
                'desc': 'woman office worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F4BC', {
                'desc': 'woman office worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F4BC', {
                'desc': 'woman office worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F4BC', {
                'desc': 'woman office worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F4BC', {
                'desc': 'woman office worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F52C', {
        'desc': 'man scientist',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F52C', {
                'desc': 'man scientist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F52C', {
                'desc': 'man scientist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F52C', {
                'desc': 'man scientist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F52C', {
                'desc': 'man scientist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F52C', {
                'desc': 'man scientist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F52C', {
        'desc': 'woman scientist',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F52C', {
                'desc': 'woman scientist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F52C', {
                'desc': 'woman scientist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F52C', {
                'desc': 'woman scientist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F52C', {
                'desc': 'woman scientist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F52C', {
                'desc': 'woman scientist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F4BB', {
        'desc': 'man technologist',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F4BB', {
                'desc': 'man technologist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F4BB', {
                'desc': 'man technologist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F4BB', {
                'desc': 'man technologist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F4BB', {
                'desc': 'man technologist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F4BB', {
                'desc': 'man technologist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F4BB', {
        'desc': 'woman technologist',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F4BB', {
                'desc': 'woman technologist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F4BB', {
                'desc': 'woman technologist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F4BB', {
                'desc': 'woman technologist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F4BB', {
                'desc': 'woman technologist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F4BB', {
                'desc': 'woman technologist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F3A4', {
        'desc': 'man singer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F3A4', {
                'desc': 'man singer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F3A4', {
                'desc': 'man singer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F3A4', {
                'desc': 'man singer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F3A4', {
                'desc': 'man singer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F3A4', {
                'desc': 'man singer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F3A4', {
        'desc': 'woman singer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F3A4', {
                'desc': 'woman singer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F3A4', {
                'desc': 'woman singer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F3A4', {
                'desc': 'woman singer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F3A4', {
                'desc': 'woman singer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F3A4', {
                'desc': 'woman singer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F3A8', {
        'desc': 'man artist',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F3A8', {
                'desc': 'man artist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F3A8', {
                'desc': 'man artist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F3A8', {
                'desc': 'man artist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F3A8', {
                'desc': 'man artist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F3A8', {
                'desc': 'man artist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F3A8', {
        'desc': 'woman artist',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F3A8', {
                'desc': 'woman artist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F3A8', {
                'desc': 'woman artist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F3A8', {
                'desc': 'woman artist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F3A8', {
                'desc': 'woman artist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F3A8', {
                'desc': 'woman artist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U00002708\U0000FE0F', {
        'desc': 'man pilot',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U00002708\U0000FE0F', {
                'desc': 'man pilot: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U00002708\U0000FE0F', {
                'desc': 'man pilot: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U00002708\U0000FE0F', {
                'desc': 'man pilot: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U00002708\U0000FE0F', {
                'desc': 'man pilot: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U00002708\U0000FE0F', {
                'desc': 'man pilot: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U00002708', {
        'desc': 'man pilot',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U00002708', {
                'desc': 'man pilot: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U00002708', {
                'desc': 'man pilot: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U00002708', {
                'desc': 'man pilot: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U00002708', {
                'desc': 'man pilot: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U00002708', {
                'desc': 'man pilot: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F469\U0000200D\U00002708\U0000FE0F', {
        'desc': 'woman pilot',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U00002708\U0000FE0F', {
                'desc': 'woman pilot: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U00002708\U0000FE0F', {
                'desc': 'woman pilot: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U00002708\U0000FE0F', {
                'desc': 'woman pilot: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U00002708\U0000FE0F', {
                'desc': 'woman pilot: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U00002708\U0000FE0F', {
                'desc': 'woman pilot: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U00002708', {
        'desc': 'woman pilot',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U00002708', {
                'desc': 'woman pilot: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U00002708', {
                'desc': 'woman pilot: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U00002708', {
                'desc': 'woman pilot: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U00002708', {
                'desc': 'woman pilot: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U00002708', {
                'desc': 'woman pilot: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F468\U0000200D\U0001F680', {
        'desc': 'man astronaut',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F680', {
                'desc': 'man astronaut: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F680', {
                'desc': 'man astronaut: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F680', {
                'desc': 'man astronaut: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F680', {
                'desc': 'man astronaut: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F680', {
                'desc': 'man astronaut: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F680', {
        'desc': 'woman astronaut',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F680', {
                'desc': 'woman astronaut: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F680', {
                'desc': 'woman astronaut: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F680', {
                'desc': 'woman astronaut: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F680', {
                'desc': 'woman astronaut: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F680', {
                'desc': 'woman astronaut: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F692', {
        'desc': 'man firefighter',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F692', {
                'desc': 'man firefighter: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F692', {
                'desc': 'man firefighter: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F692', {
                'desc': 'man firefighter: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F692', {
                'desc': 'man firefighter: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F692', {
                'desc': 'man firefighter: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F692', {
        'desc': 'woman firefighter',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F692', {
                'desc': 'woman firefighter: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F692', {
                'desc': 'woman firefighter: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F692', {
                'desc': 'woman firefighter: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F692', {
                'desc': 'woman firefighter: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F692', {
                'desc': 'woman firefighter: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F46E', {
        'desc': 'police officer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F46E\U0001F3FB', {
                'desc': 'police officer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F46E\U0001F3FC', {
                'desc': 'police officer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F46E\U0001F3FD', {
                'desc': 'police officer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F46E\U0001F3FE', {
                'desc': 'police officer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F46E\U0001F3FF', {
                'desc': 'police officer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F46E\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man police officer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F46E\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man police officer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man police officer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man police officer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man police officer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man police officer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F46E\U0000200D\U00002642', {
        'desc': 'man police officer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F46E\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man police officer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man police officer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man police officer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man police officer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man police officer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F46E\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman police officer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F46E\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman police officer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman police officer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman police officer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman police officer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F46E\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman police officer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F46E\U0000200D\U00002640', {
        'desc': 'woman police officer',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F46E\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman police officer: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman police officer: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman police officer: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman police officer: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F46E\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman police officer: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F575\U0000FE0F', {
        'desc': 'detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F575\U0001F3FB', {
                'desc': 'detective: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F575\U0001F3FC', {
                'desc': 'detective: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F575\U0001F3FD', {
                'desc': 'detective: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F575\U0001F3FE', {
                'desc': 'detective: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F575\U0001F3FF', {
                'desc': 'detective: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0001F575', {
        'desc': 'detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F575\U0000FE0F\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F575\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man detective: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man detective: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man detective: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man detective: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man detective: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F575\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False
    }),
    ('\U0001F575\U0000FE0F\U0000200D\U00002642', {
        'desc': 'man detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F575\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man detective: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man detective: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man detective: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man detective: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man detective: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F575\U0000200D\U00002642', {
        'desc': 'man detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False
    }),
    ('\U0001F575\U0000FE0F\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F575\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman detective: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman detective: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman detective: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman detective: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F575\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman detective: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F575\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False
    }),
    ('\U0001F575\U0000FE0F\U0000200D\U00002640', {
        'desc': 'woman detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F575\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman detective: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman detective: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman detective: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman detective: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F575\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman detective: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F575\U0000200D\U00002640', {
        'desc': 'woman detective',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False
    }),
    ('\U0001F482', {
        'desc': 'guard',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F482\U0001F3FB', {
                'desc': 'guard: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F482\U0001F3FC', {
                'desc': 'guard: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F482\U0001F3FD', {
                'desc': 'guard: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F482\U0001F3FE', {
                'desc': 'guard: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F482\U0001F3FF', {
                'desc': 'guard: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F482\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man guard',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F482\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man guard: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man guard: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man guard: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man guard: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man guard: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F482\U0000200D\U00002642', {
        'desc': 'man guard',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F482\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man guard: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man guard: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man guard: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man guard: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man guard: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F482\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman guard',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F482\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman guard: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman guard: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman guard: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman guard: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F482\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman guard: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F482\U0000200D\U00002640', {
        'desc': 'woman guard',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F482\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman guard: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman guard: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman guard: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman guard: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F482\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman guard: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F477', {
        'desc': 'construction worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F477\U0001F3FB', {
                'desc': 'construction worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F477\U0001F3FC', {
                'desc': 'construction worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F477\U0001F3FD', {
                'desc': 'construction worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F477\U0001F3FE', {
                'desc': 'construction worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F477\U0001F3FF', {
                'desc': 'construction worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F477\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man construction worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F477\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man construction worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man construction worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man construction worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man construction worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man construction worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F477\U0000200D\U00002642', {
        'desc': 'man construction worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F477\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man construction worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man construction worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man construction worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man construction worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man construction worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F477\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman construction worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F477\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman construction worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman construction worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman construction worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman construction worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F477\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman construction worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F477\U0000200D\U00002640', {
        'desc': 'woman construction worker',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F477\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman construction worker: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman construction worker: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman construction worker: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman construction worker: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F477\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman construction worker: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F934', {
        'desc': 'prince',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F934\U0001F3FB', {
                'desc': 'prince: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F934\U0001F3FC', {
                'desc': 'prince: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F934\U0001F3FD', {
                'desc': 'prince: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F934\U0001F3FE', {
                'desc': 'prince: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F934\U0001F3FF', {
                'desc': 'prince: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F478', {
        'desc': 'princess',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F478\U0001F3FB', {
                'desc': 'princess: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F478\U0001F3FC', {
                'desc': 'princess: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F478\U0001F3FD', {
                'desc': 'princess: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F478\U0001F3FE', {
                'desc': 'princess: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F478\U0001F3FF', {
                'desc': 'princess: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F473', {
        'desc': 'person wearing turban',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F473\U0001F3FB', {
                'desc': 'person wearing turban: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F473\U0001F3FC', {
                'desc': 'person wearing turban: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F473\U0001F3FD', {
                'desc': 'person wearing turban: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F473\U0001F3FE', {
                'desc': 'person wearing turban: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F473\U0001F3FF', {
                'desc': 'person wearing turban: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F473\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man wearing turban',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F473\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man wearing turban: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man wearing turban: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man wearing turban: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man wearing turban: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man wearing turban: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F473\U0000200D\U00002642', {
        'desc': 'man wearing turban',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F473\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man wearing turban: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man wearing turban: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man wearing turban: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man wearing turban: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man wearing turban: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F473\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman wearing turban',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F473\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman wearing turban: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman wearing turban: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman wearing turban: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman wearing turban: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F473\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman wearing turban: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F473\U0000200D\U00002640', {
        'desc': 'woman wearing turban',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F473\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman wearing turban: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman wearing turban: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman wearing turban: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman wearing turban: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F473\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman wearing turban: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F472', {
        'desc': 'man with Chinese cap',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F472\U0001F3FB', {
                'desc': 'man with Chinese cap: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F472\U0001F3FC', {
                'desc': 'man with Chinese cap: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F472\U0001F3FD', {
                'desc': 'man with Chinese cap: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F472\U0001F3FE', {
                'desc': 'man with Chinese cap: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F472\U0001F3FF', {
                'desc': 'man with Chinese cap: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D5', {
        'desc': 'woman with headscarf',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D5\U0001F3FB', {
                'desc': 'woman with headscarf: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D5\U0001F3FC', {
                'desc': 'woman with headscarf: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D5\U0001F3FD', {
                'desc': 'woman with headscarf: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D5\U0001F3FE', {
                'desc': 'woman with headscarf: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D5\U0001F3FF', {
                'desc': 'woman with headscarf: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D4', {
        'desc': 'bearded person',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D4\U0001F3FB', {
                'desc': 'bearded person: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D4\U0001F3FC', {
                'desc': 'bearded person: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D4\U0001F3FD', {
                'desc': 'bearded person: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D4\U0001F3FE', {
                'desc': 'bearded person: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D4\U0001F3FF', {
                'desc': 'bearded person: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F471', {
        'desc': 'blond-haired person',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F471\U0001F3FB', {
                'desc': 'blond-haired person: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F471\U0001F3FC', {
                'desc': 'blond-haired person: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F471\U0001F3FD', {
                'desc': 'blond-haired person: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F471\U0001F3FE', {
                'desc': 'blond-haired person: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F471\U0001F3FF', {
                'desc': 'blond-haired person: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F471\U0000200D\U00002642\U0000FE0F', {
        'desc': 'blond-haired man',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F471\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'blond-haired man: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'blond-haired man: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'blond-haired man: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'blond-haired man: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'blond-haired man: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F471\U0000200D\U00002642', {
        'desc': 'blond-haired man',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F471\U0001F3FB\U0000200D\U00002642', {
                'desc': 'blond-haired man: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FC\U0000200D\U00002642', {
                'desc': 'blond-haired man: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FD\U0000200D\U00002642', {
                'desc': 'blond-haired man: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FE\U0000200D\U00002642', {
                'desc': 'blond-haired man: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FF\U0000200D\U00002642', {
                'desc': 'blond-haired man: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F471\U0000200D\U00002640\U0000FE0F', {
        'desc': 'blond-haired woman',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F471\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'blond-haired woman: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'blond-haired woman: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'blond-haired woman: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'blond-haired woman: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F471\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'blond-haired woman: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F471\U0000200D\U00002640', {
        'desc': 'blond-haired woman',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F471\U0001F3FB\U0000200D\U00002640', {
                'desc': 'blond-haired woman: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FC\U0000200D\U00002640', {
                'desc': 'blond-haired woman: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FD\U0000200D\U00002640', {
                'desc': 'blond-haired woman: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FE\U0000200D\U00002640', {
                'desc': 'blond-haired woman: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            }),
            ('\U0001F471\U0001F3FF\U0000200D\U00002640', {
                'desc': 'blond-haired woman: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F468\U0000200D\U0001F9B0', {
        'desc': 'man, red haired',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F9B0', {
                'desc': 'man, red haired: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F9B0', {
                'desc': 'man, red haired: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F9B0', {
                'desc': 'man, red haired: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F9B0', {
                'desc': 'man, red haired: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F9B0', {
                'desc': 'man, red haired: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F9B0', {
        'desc': 'woman, red haired',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F9B0', {
                'desc': 'woman, red haired: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F9B0', {
                'desc': 'woman, red haired: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F9B0', {
                'desc': 'woman, red haired: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F9B0', {
                'desc': 'woman, red haired: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F9B0', {
                'desc': 'woman, red haired: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F9B1', {
        'desc': 'man, curly haired',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F9B1', {
                'desc': 'man, curly haired: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F9B1', {
                'desc': 'man, curly haired: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F9B1', {
                'desc': 'man, curly haired: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F9B1', {
                'desc': 'man, curly haired: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F9B1', {
                'desc': 'man, curly haired: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F9B1', {
        'desc': 'woman, curly haired',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F9B1', {
                'desc': 'woman, curly haired: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F9B1', {
                'desc': 'woman, curly haired: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F9B1', {
                'desc': 'woman, curly haired: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F9B1', {
                'desc': 'woman, curly haired: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F9B1', {
                'desc': 'woman, curly haired: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F9B2', {
        'desc': 'man, bald',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F9B2', {
                'desc': 'man, bald: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F9B2', {
                'desc': 'man, bald: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F9B2', {
                'desc': 'man, bald: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F9B2', {
                'desc': 'man, bald: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F9B2', {
                'desc': 'man, bald: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F9B2', {
        'desc': 'woman, bald',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F9B2', {
                'desc': 'woman, bald: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F9B2', {
                'desc': 'woman, bald: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F9B2', {
                'desc': 'woman, bald: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F9B2', {
                'desc': 'woman, bald: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F9B2', {
                'desc': 'woman, bald: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F9B3', {
        'desc': 'man, white haired',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F468\U0001F3FB\U0000200D\U0001F9B3', {
                'desc': 'man, white haired: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FC\U0000200D\U0001F9B3', {
                'desc': 'man, white haired: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FD\U0000200D\U0001F9B3', {
                'desc': 'man, white haired: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FE\U0000200D\U0001F9B3', {
                'desc': 'man, white haired: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F468\U0001F3FF\U0000200D\U0001F9B3', {
                'desc': 'man, white haired: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F9B3', {
        'desc': 'woman, white haired',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F469\U0001F3FB\U0000200D\U0001F9B3', {
                'desc': 'woman, white haired: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FC\U0000200D\U0001F9B3', {
                'desc': 'woman, white haired: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FD\U0000200D\U0001F9B3', {
                'desc': 'woman, white haired: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FE\U0000200D\U0001F9B3', {
                'desc': 'woman, white haired: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            }),
            ('\U0001F469\U0001F3FF\U0000200D\U0001F9B3', {
                'desc': 'woman, white haired: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F935', {
        'desc': 'man in tuxedo',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F935\U0001F3FB', {
                'desc': 'man in tuxedo: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F935\U0001F3FC', {
                'desc': 'man in tuxedo: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F935\U0001F3FD', {
                'desc': 'man in tuxedo: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F935\U0001F3FE', {
                'desc': 'man in tuxedo: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F935\U0001F3FF', {
                'desc': 'man in tuxedo: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F470', {
        'desc': 'bride with veil',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F470\U0001F3FB', {
                'desc': 'bride with veil: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F470\U0001F3FC', {
                'desc': 'bride with veil: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F470\U0001F3FD', {
                'desc': 'bride with veil: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F470\U0001F3FE', {
                'desc': 'bride with veil: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F470\U0001F3FF', {
                'desc': 'bride with veil: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F930', {
        'desc': 'pregnant woman',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F930\U0001F3FB', {
                'desc': 'pregnant woman: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F930\U0001F3FC', {
                'desc': 'pregnant woman: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F930\U0001F3FD', {
                'desc': 'pregnant woman: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F930\U0001F3FE', {
                'desc': 'pregnant woman: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F930\U0001F3FF', {
                'desc': 'pregnant woman: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F931', {
        'desc': 'breast-feeding',
        'group': 'Smileys & People',
        'subgroup': 'person-role',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F931\U0001F3FB', {
                'desc': 'breast-feeding: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F931\U0001F3FC', {
                'desc': 'breast-feeding: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F931\U0001F3FD', {
                'desc': 'breast-feeding: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F931\U0001F3FE', {
                'desc': 'breast-feeding: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F931\U0001F3FF', {
                'desc': 'breast-feeding: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-role',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F47C', {
        'desc': 'baby angel',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F47C\U0001F3FB', {
                'desc': 'baby angel: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F47C\U0001F3FC', {
                'desc': 'baby angel: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F47C\U0001F3FD', {
                'desc': 'baby angel: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F47C\U0001F3FE', {
                'desc': 'baby angel: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F47C\U0001F3FF', {
                'desc': 'baby angel: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F385', {
        'desc': 'Santa Claus',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F385\U0001F3FB', {
                'desc': 'Santa Claus: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F385\U0001F3FC', {
                'desc': 'Santa Claus: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F385\U0001F3FD', {
                'desc': 'Santa Claus: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F385\U0001F3FE', {
                'desc': 'Santa Claus: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F385\U0001F3FF', {
                'desc': 'Santa Claus: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F936', {
        'desc': 'Mrs. Claus',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F936\U0001F3FB', {
                'desc': 'Mrs. Claus: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F936\U0001F3FC', {
                'desc': 'Mrs. Claus: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F936\U0001F3FD', {
                'desc': 'Mrs. Claus: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F936\U0001F3FE', {
                'desc': 'Mrs. Claus: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F936\U0001F3FF', {
                'desc': 'Mrs. Claus: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B8', {
        'desc': 'superhero',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B8\U0001F3FB', {
                'desc': 'superhero: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B8\U0001F3FC', {
                'desc': 'superhero: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B8\U0001F3FD', {
                'desc': 'superhero: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B8\U0001F3FE', {
                'desc': 'superhero: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B8\U0001F3FF', {
                'desc': 'superhero: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B8\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman superhero',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B8\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman superhero: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman superhero: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman superhero: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman superhero: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman superhero: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9B8\U0000200D\U00002640', {
        'desc': 'woman superhero',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9B8\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman superhero: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman superhero: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman superhero: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman superhero: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman superhero: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9B8\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man superhero',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B8\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man superhero: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man superhero: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man superhero: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man superhero: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B8\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man superhero: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9B8\U0000200D\U00002642', {
        'desc': 'man superhero',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9B8\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man superhero: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man superhero: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man superhero: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man superhero: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B8\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man superhero: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9B9', {
        'desc': 'supervillain',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B9\U0001F3FB', {
                'desc': 'supervillain: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B9\U0001F3FC', {
                'desc': 'supervillain: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B9\U0001F3FD', {
                'desc': 'supervillain: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B9\U0001F3FE', {
                'desc': 'supervillain: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B9\U0001F3FF', {
                'desc': 'supervillain: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B9\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman supervillain',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B9\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman supervillain: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman supervillain: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman supervillain: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman supervillain: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman supervillain: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9B9\U0000200D\U00002640', {
        'desc': 'woman supervillain',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9B9\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman supervillain: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman supervillain: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman supervillain: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman supervillain: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman supervillain: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9B9\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man supervillain',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B9\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man supervillain: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man supervillain: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man supervillain: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man supervillain: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9B9\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man supervillain: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9B9\U0000200D\U00002642', {
        'desc': 'man supervillain',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9B9\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man supervillain: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man supervillain: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man supervillain: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man supervillain: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9B9\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man supervillain: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9D9', {
        'desc': 'mage',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D9\U0001F3FB', {
                'desc': 'mage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D9\U0001F3FC', {
                'desc': 'mage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D9\U0001F3FD', {
                'desc': 'mage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D9\U0001F3FE', {
                'desc': 'mage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D9\U0001F3FF', {
                'desc': 'mage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D9\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman mage',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D9\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D9\U0000200D\U00002640', {
        'desc': 'woman mage',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D9\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman mage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman mage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman mage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman mage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman mage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9D9\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man mage',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D9\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9D9\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D9\U0000200D\U00002642', {
        'desc': 'man mage',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D9\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man mage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man mage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man mage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man mage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9D9\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man mage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DA', {
        'desc': 'fairy',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DA\U0001F3FB', {
                'desc': 'fairy: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DA\U0001F3FC', {
                'desc': 'fairy: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DA\U0001F3FD', {
                'desc': 'fairy: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DA\U0001F3FE', {
                'desc': 'fairy: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DA\U0001F3FF', {
                'desc': 'fairy: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9DA\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman fairy',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DA\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman fairy: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman fairy: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman fairy: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman fairy: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman fairy: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DA\U0000200D\U00002640', {
        'desc': 'woman fairy',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DA\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman fairy: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman fairy: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman fairy: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman fairy: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman fairy: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DA\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man fairy',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DA\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man fairy: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man fairy: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man fairy: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man fairy: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DA\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man fairy: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DA\U0000200D\U00002642', {
        'desc': 'man fairy',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DA\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man fairy: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man fairy: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man fairy: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man fairy: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DA\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man fairy: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DB', {
        'desc': 'vampire',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DB\U0001F3FB', {
                'desc': 'vampire: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DB\U0001F3FC', {
                'desc': 'vampire: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DB\U0001F3FD', {
                'desc': 'vampire: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DB\U0001F3FE', {
                'desc': 'vampire: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DB\U0001F3FF', {
                'desc': 'vampire: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9DB\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman vampire',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DB\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman vampire: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman vampire: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman vampire: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman vampire: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman vampire: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DB\U0000200D\U00002640', {
        'desc': 'woman vampire',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DB\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman vampire: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman vampire: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman vampire: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman vampire: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman vampire: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DB\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man vampire',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DB\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man vampire: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man vampire: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man vampire: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man vampire: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DB\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man vampire: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DB\U0000200D\U00002642', {
        'desc': 'man vampire',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DB\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man vampire: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man vampire: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man vampire: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man vampire: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DB\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man vampire: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DC', {
        'desc': 'merperson',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DC\U0001F3FB', {
                'desc': 'merperson: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DC\U0001F3FC', {
                'desc': 'merperson: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DC\U0001F3FD', {
                'desc': 'merperson: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DC\U0001F3FE', {
                'desc': 'merperson: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DC\U0001F3FF', {
                'desc': 'merperson: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9DC\U0000200D\U00002640\U0000FE0F', {
        'desc': 'mermaid',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DC\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'mermaid: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'mermaid: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'mermaid: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'mermaid: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'mermaid: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DC\U0000200D\U00002640', {
        'desc': 'mermaid',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DC\U0001F3FB\U0000200D\U00002640', {
                'desc': 'mermaid: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FC\U0000200D\U00002640', {
                'desc': 'mermaid: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FD\U0000200D\U00002640', {
                'desc': 'mermaid: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FE\U0000200D\U00002640', {
                'desc': 'mermaid: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FF\U0000200D\U00002640', {
                'desc': 'mermaid: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DC\U0000200D\U00002642\U0000FE0F', {
        'desc': 'merman',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DC\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'merman: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'merman: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'merman: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'merman: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DC\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'merman: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DC\U0000200D\U00002642', {
        'desc': 'merman',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DC\U0001F3FB\U0000200D\U00002642', {
                'desc': 'merman: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FC\U0000200D\U00002642', {
                'desc': 'merman: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FD\U0000200D\U00002642', {
                'desc': 'merman: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FE\U0000200D\U00002642', {
                'desc': 'merman: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DC\U0001F3FF\U0000200D\U00002642', {
                'desc': 'merman: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DD', {
        'desc': 'elf',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DD\U0001F3FB', {
                'desc': 'elf: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DD\U0001F3FC', {
                'desc': 'elf: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DD\U0001F3FD', {
                'desc': 'elf: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DD\U0001F3FE', {
                'desc': 'elf: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9DD\U0001F3FF', {
                'desc': 'elf: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9DD\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman elf',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DD\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman elf: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman elf: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman elf: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman elf: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman elf: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DD\U0000200D\U00002640', {
        'desc': 'woman elf',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DD\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman elf: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman elf: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman elf: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman elf: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman elf: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DD\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man elf',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9DD\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man elf: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man elf: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man elf: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man elf: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            }),
            ('\U0001F9DD\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man elf: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DD\U0000200D\U00002642', {
        'desc': 'man elf',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9DD\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man elf: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man elf: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man elf: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man elf: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            }),
            ('\U0001F9DD\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man elf: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-fantasy',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9DE', {
        'desc': 'genie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9DE\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman genie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DE\U0000200D\U00002640', {
        'desc': 'woman genie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False
    }),
    ('\U0001F9DE\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man genie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DE\U0000200D\U00002642', {
        'desc': 'man genie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False
    }),
    ('\U0001F9DF', {
        'desc': 'zombie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9DF\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman zombie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DF\U0000200D\U00002640', {
        'desc': 'woman zombie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False
    }),
    ('\U0001F9DF\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man zombie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9DF\U0000200D\U00002642', {
        'desc': 'man zombie',
        'group': 'Smileys & People',
        'subgroup': 'person-fantasy',
        'fully-qualified': False
    }),
    ('\U0001F64D', {
        'desc': 'person frowning',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64D\U0001F3FB', {
                'desc': 'person frowning: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64D\U0001F3FC', {
                'desc': 'person frowning: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64D\U0001F3FD', {
                'desc': 'person frowning: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64D\U0001F3FE', {
                'desc': 'person frowning: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64D\U0001F3FF', {
                'desc': 'person frowning: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F64D\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man frowning',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64D\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man frowning: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man frowning: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man frowning: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man frowning: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man frowning: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F64D\U0000200D\U00002642', {
        'desc': 'man frowning',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F64D\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man frowning: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man frowning: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man frowning: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man frowning: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man frowning: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F64D\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman frowning',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64D\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman frowning: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman frowning: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman frowning: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman frowning: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64D\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman frowning: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F64D\U0000200D\U00002640', {
        'desc': 'woman frowning',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F64D\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman frowning: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman frowning: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman frowning: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman frowning: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64D\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman frowning: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F64E', {
        'desc': 'person pouting',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64E\U0001F3FB', {
                'desc': 'person pouting: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64E\U0001F3FC', {
                'desc': 'person pouting: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64E\U0001F3FD', {
                'desc': 'person pouting: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64E\U0001F3FE', {
                'desc': 'person pouting: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64E\U0001F3FF', {
                'desc': 'person pouting: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F64E\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man pouting',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64E\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man pouting: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man pouting: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man pouting: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man pouting: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man pouting: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F64E\U0000200D\U00002642', {
        'desc': 'man pouting',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F64E\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man pouting: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man pouting: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man pouting: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man pouting: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man pouting: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F64E\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman pouting',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64E\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman pouting: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman pouting: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman pouting: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman pouting: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64E\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman pouting: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F64E\U0000200D\U00002640', {
        'desc': 'woman pouting',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F64E\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman pouting: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman pouting: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman pouting: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman pouting: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64E\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman pouting: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F645', {
        'desc': 'person gesturing NO',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F645\U0001F3FB', {
                'desc': 'person gesturing NO: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F645\U0001F3FC', {
                'desc': 'person gesturing NO: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F645\U0001F3FD', {
                'desc': 'person gesturing NO: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F645\U0001F3FE', {
                'desc': 'person gesturing NO: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F645\U0001F3FF', {
                'desc': 'person gesturing NO: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F645\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man gesturing NO',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F645\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing NO: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing NO: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing NO: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing NO: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing NO: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F645\U0000200D\U00002642', {
        'desc': 'man gesturing NO',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F645\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man gesturing NO: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man gesturing NO: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man gesturing NO: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man gesturing NO: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man gesturing NO: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F645\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman gesturing NO',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F645\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing NO: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing NO: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing NO: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing NO: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F645\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing NO: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F645\U0000200D\U00002640', {
        'desc': 'woman gesturing NO',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F645\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman gesturing NO: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman gesturing NO: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman gesturing NO: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman gesturing NO: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F645\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman gesturing NO: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F646', {
        'desc': 'person gesturing OK',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F646\U0001F3FB', {
                'desc': 'person gesturing OK: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F646\U0001F3FC', {
                'desc': 'person gesturing OK: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F646\U0001F3FD', {
                'desc': 'person gesturing OK: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F646\U0001F3FE', {
                'desc': 'person gesturing OK: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F646\U0001F3FF', {
                'desc': 'person gesturing OK: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F646\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man gesturing OK',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F646\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing OK: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing OK: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing OK: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing OK: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man gesturing OK: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F646\U0000200D\U00002642', {
        'desc': 'man gesturing OK',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F646\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man gesturing OK: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man gesturing OK: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man gesturing OK: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man gesturing OK: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man gesturing OK: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F646\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman gesturing OK',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F646\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing OK: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing OK: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing OK: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing OK: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F646\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman gesturing OK: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F646\U0000200D\U00002640', {
        'desc': 'woman gesturing OK',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F646\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman gesturing OK: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman gesturing OK: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman gesturing OK: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman gesturing OK: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F646\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman gesturing OK: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F481', {
        'desc': 'person tipping hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F481\U0001F3FB', {
                'desc': 'person tipping hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F481\U0001F3FC', {
                'desc': 'person tipping hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F481\U0001F3FD', {
                'desc': 'person tipping hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F481\U0001F3FE', {
                'desc': 'person tipping hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F481\U0001F3FF', {
                'desc': 'person tipping hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F481\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man tipping hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F481\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man tipping hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man tipping hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man tipping hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man tipping hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man tipping hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F481\U0000200D\U00002642', {
        'desc': 'man tipping hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F481\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man tipping hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man tipping hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man tipping hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man tipping hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man tipping hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F481\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman tipping hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F481\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman tipping hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman tipping hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman tipping hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman tipping hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F481\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman tipping hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F481\U0000200D\U00002640', {
        'desc': 'woman tipping hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F481\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman tipping hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman tipping hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman tipping hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman tipping hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F481\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman tipping hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F64B', {
        'desc': 'person raising hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64B\U0001F3FB', {
                'desc': 'person raising hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64B\U0001F3FC', {
                'desc': 'person raising hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64B\U0001F3FD', {
                'desc': 'person raising hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64B\U0001F3FE', {
                'desc': 'person raising hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64B\U0001F3FF', {
                'desc': 'person raising hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F64B\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man raising hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64B\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man raising hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man raising hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man raising hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man raising hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man raising hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F64B\U0000200D\U00002642', {
        'desc': 'man raising hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F64B\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man raising hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man raising hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man raising hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man raising hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man raising hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F64B\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman raising hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64B\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman raising hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman raising hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman raising hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman raising hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F64B\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman raising hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F64B\U0000200D\U00002640', {
        'desc': 'woman raising hand',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F64B\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman raising hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman raising hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman raising hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman raising hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F64B\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman raising hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F647', {
        'desc': 'person bowing',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F647\U0001F3FB', {
                'desc': 'person bowing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F647\U0001F3FC', {
                'desc': 'person bowing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F647\U0001F3FD', {
                'desc': 'person bowing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F647\U0001F3FE', {
                'desc': 'person bowing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F647\U0001F3FF', {
                'desc': 'person bowing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F647\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man bowing',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F647\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bowing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bowing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bowing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bowing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bowing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F647\U0000200D\U00002642', {
        'desc': 'man bowing',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F647\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man bowing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man bowing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man bowing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man bowing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man bowing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F647\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman bowing',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F647\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bowing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bowing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bowing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bowing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F647\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bowing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F647\U0000200D\U00002640', {
        'desc': 'woman bowing',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F647\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman bowing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman bowing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman bowing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman bowing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F647\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman bowing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F926', {
        'desc': 'person facepalming',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F926\U0001F3FB', {
                'desc': 'person facepalming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F926\U0001F3FC', {
                'desc': 'person facepalming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F926\U0001F3FD', {
                'desc': 'person facepalming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F926\U0001F3FE', {
                'desc': 'person facepalming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F926\U0001F3FF', {
                'desc': 'person facepalming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F926\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man facepalming',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F926\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man facepalming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man facepalming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man facepalming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man facepalming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man facepalming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F926\U0000200D\U00002642', {
        'desc': 'man facepalming',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F926\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man facepalming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man facepalming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man facepalming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man facepalming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man facepalming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F926\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman facepalming',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F926\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman facepalming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman facepalming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman facepalming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman facepalming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F926\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman facepalming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F926\U0000200D\U00002640', {
        'desc': 'woman facepalming',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F926\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman facepalming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman facepalming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman facepalming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman facepalming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F926\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman facepalming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F937', {
        'desc': 'person shrugging',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F937\U0001F3FB', {
                'desc': 'person shrugging: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F937\U0001F3FC', {
                'desc': 'person shrugging: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F937\U0001F3FD', {
                'desc': 'person shrugging: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F937\U0001F3FE', {
                'desc': 'person shrugging: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F937\U0001F3FF', {
                'desc': 'person shrugging: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F937\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man shrugging',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F937\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man shrugging: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man shrugging: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man shrugging: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man shrugging: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man shrugging: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F937\U0000200D\U00002642', {
        'desc': 'man shrugging',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F937\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man shrugging: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man shrugging: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man shrugging: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man shrugging: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man shrugging: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F937\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman shrugging',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F937\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman shrugging: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman shrugging: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman shrugging: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman shrugging: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            }),
            ('\U0001F937\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman shrugging: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F937\U0000200D\U00002640', {
        'desc': 'woman shrugging',
        'group': 'Smileys & People',
        'subgroup': 'person-gesture',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F937\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman shrugging: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman shrugging: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman shrugging: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman shrugging: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            }),
            ('\U0001F937\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman shrugging: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-gesture',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F486', {
        'desc': 'person getting massage',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F486\U0001F3FB', {
                'desc': 'person getting massage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F486\U0001F3FC', {
                'desc': 'person getting massage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F486\U0001F3FD', {
                'desc': 'person getting massage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F486\U0001F3FE', {
                'desc': 'person getting massage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F486\U0001F3FF', {
                'desc': 'person getting massage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F486\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man getting massage',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F486\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting massage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting massage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting massage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting massage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting massage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F486\U0000200D\U00002642', {
        'desc': 'man getting massage',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F486\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man getting massage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man getting massage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man getting massage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man getting massage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man getting massage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F486\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman getting massage',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F486\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting massage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting massage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting massage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting massage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F486\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting massage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F486\U0000200D\U00002640', {
        'desc': 'woman getting massage',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F486\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman getting massage: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman getting massage: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman getting massage: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman getting massage: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F486\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman getting massage: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F487', {
        'desc': 'person getting haircut',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F487\U0001F3FB', {
                'desc': 'person getting haircut: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F487\U0001F3FC', {
                'desc': 'person getting haircut: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F487\U0001F3FD', {
                'desc': 'person getting haircut: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F487\U0001F3FE', {
                'desc': 'person getting haircut: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F487\U0001F3FF', {
                'desc': 'person getting haircut: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F487\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man getting haircut',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F487\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting haircut: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting haircut: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting haircut: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting haircut: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man getting haircut: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F487\U0000200D\U00002642', {
        'desc': 'man getting haircut',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F487\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man getting haircut: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man getting haircut: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man getting haircut: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man getting haircut: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man getting haircut: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F487\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman getting haircut',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F487\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting haircut: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting haircut: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting haircut: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting haircut: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F487\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman getting haircut: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F487\U0000200D\U00002640', {
        'desc': 'woman getting haircut',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F487\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman getting haircut: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman getting haircut: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman getting haircut: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman getting haircut: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F487\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman getting haircut: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6B6', {
        'desc': 'person walking',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B6\U0001F3FB', {
                'desc': 'person walking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B6\U0001F3FC', {
                'desc': 'person walking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B6\U0001F3FD', {
                'desc': 'person walking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B6\U0001F3FE', {
                'desc': 'person walking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B6\U0001F3FF', {
                'desc': 'person walking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B6\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man walking',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B6\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man walking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man walking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man walking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man walking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man walking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6B6\U0000200D\U00002642', {
        'desc': 'man walking',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6B6\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man walking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man walking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man walking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man walking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man walking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6B6\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman walking',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B6\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman walking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman walking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman walking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman walking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F6B6\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman walking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6B6\U0000200D\U00002640', {
        'desc': 'woman walking',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6B6\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman walking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman walking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman walking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman walking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F6B6\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman walking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3C3', {
        'desc': 'person running',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C3\U0001F3FB', {
                'desc': 'person running: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C3\U0001F3FC', {
                'desc': 'person running: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C3\U0001F3FD', {
                'desc': 'person running: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C3\U0001F3FE', {
                'desc': 'person running: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C3\U0001F3FF', {
                'desc': 'person running: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C3\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man running',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C3\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man running: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man running: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man running: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man running: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man running: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3C3\U0000200D\U00002642', {
        'desc': 'man running',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3C3\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man running: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man running: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man running: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man running: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man running: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3C3\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman running',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C3\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman running: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman running: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman running: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman running: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F3C3\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman running: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3C3\U0000200D\U00002640', {
        'desc': 'woman running',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3C3\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman running: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman running: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman running: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman running: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F3C3\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman running: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F483', {
        'desc': 'woman dancing',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F483\U0001F3FB', {
                'desc': 'woman dancing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F483\U0001F3FC', {
                'desc': 'woman dancing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F483\U0001F3FD', {
                'desc': 'woman dancing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F483\U0001F3FE', {
                'desc': 'woman dancing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F483\U0001F3FF', {
                'desc': 'woman dancing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F57A', {
        'desc': 'man dancing',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F57A\U0001F3FB', {
                'desc': 'man dancing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F57A\U0001F3FC', {
                'desc': 'man dancing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F57A\U0001F3FD', {
                'desc': 'man dancing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F57A\U0001F3FE', {
                'desc': 'man dancing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F57A\U0001F3FF', {
                'desc': 'man dancing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F46F', {
        'desc': 'people with bunny ears',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F46F\U0000200D\U00002642\U0000FE0F', {
        'desc': 'men with bunny ears',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F46F\U0000200D\U00002642', {
        'desc': 'men with bunny ears',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False
    }),
    ('\U0001F46F\U0000200D\U00002640\U0000FE0F', {
        'desc': 'women with bunny ears',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F46F\U0000200D\U00002640', {
        'desc': 'women with bunny ears',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False
    }),
    ('\U0001F9D6', {
        'desc': 'person in steamy room',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D6\U0001F3FB', {
                'desc': 'person in steamy room: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D6\U0001F3FC', {
                'desc': 'person in steamy room: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D6\U0001F3FD', {
                'desc': 'person in steamy room: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D6\U0001F3FE', {
                'desc': 'person in steamy room: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D6\U0001F3FF', {
                'desc': 'person in steamy room: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D6\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman in steamy room',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D6\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in steamy room: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in steamy room: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in steamy room: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in steamy room: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in steamy room: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D6\U0000200D\U00002640', {
        'desc': 'woman in steamy room',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D6\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman in steamy room: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman in steamy room: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman in steamy room: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman in steamy room: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman in steamy room: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9D6\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man in steamy room',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D6\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in steamy room: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in steamy room: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in steamy room: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in steamy room: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D6\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in steamy room: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D6\U0000200D\U00002642', {
        'desc': 'man in steamy room',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D6\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man in steamy room: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man in steamy room: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man in steamy room: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man in steamy room: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D6\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man in steamy room: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9D7', {
        'desc': 'person climbing',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D7\U0001F3FB', {
                'desc': 'person climbing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D7\U0001F3FC', {
                'desc': 'person climbing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D7\U0001F3FD', {
                'desc': 'person climbing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D7\U0001F3FE', {
                'desc': 'person climbing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D7\U0001F3FF', {
                'desc': 'person climbing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D7\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman climbing',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D7\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman climbing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman climbing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman climbing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman climbing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman climbing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D7\U0000200D\U00002640', {
        'desc': 'woman climbing',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D7\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman climbing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman climbing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman climbing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman climbing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman climbing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9D7\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man climbing',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D7\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man climbing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man climbing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man climbing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man climbing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D7\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man climbing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D7\U0000200D\U00002642', {
        'desc': 'man climbing',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D7\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man climbing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man climbing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man climbing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man climbing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D7\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man climbing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9D8', {
        'desc': 'person in lotus position',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D8\U0001F3FB', {
                'desc': 'person in lotus position: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D8\U0001F3FC', {
                'desc': 'person in lotus position: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D8\U0001F3FD', {
                'desc': 'person in lotus position: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D8\U0001F3FE', {
                'desc': 'person in lotus position: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9D8\U0001F3FF', {
                'desc': 'person in lotus position: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9D8\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman in lotus position',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D8\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in lotus position: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in lotus position: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in lotus position: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in lotus position: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman in lotus position: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D8\U0000200D\U00002640', {
        'desc': 'woman in lotus position',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D8\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman in lotus position: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman in lotus position: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman in lotus position: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman in lotus position: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman in lotus position: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F9D8\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man in lotus position',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9D8\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in lotus position: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in lotus position: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in lotus position: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in lotus position: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            }),
            ('\U0001F9D8\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man in lotus position: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F9D8\U0000200D\U00002642', {
        'desc': 'man in lotus position',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F9D8\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man in lotus position: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man in lotus position: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man in lotus position: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man in lotus position: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            }),
            ('\U0001F9D8\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man in lotus position: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6C0', {
        'desc': 'person taking bath',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6C0\U0001F3FB', {
                'desc': 'person taking bath: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6C0\U0001F3FC', {
                'desc': 'person taking bath: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6C0\U0001F3FD', {
                'desc': 'person taking bath: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6C0\U0001F3FE', {
                'desc': 'person taking bath: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6C0\U0001F3FF', {
                'desc': 'person taking bath: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6CC', {
        'desc': 'person in bed',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6CC\U0001F3FB', {
                'desc': 'person in bed: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6CC\U0001F3FC', {
                'desc': 'person in bed: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6CC\U0001F3FD', {
                'desc': 'person in bed: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6CC\U0001F3FE', {
                'desc': 'person in bed: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6CC\U0001F3FF', {
                'desc': 'person in bed: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F574\U0000FE0F', {
        'desc': 'man in suit levitating',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F574\U0001F3FB', {
                'desc': 'man in suit levitating: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F574\U0001F3FC', {
                'desc': 'man in suit levitating: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F574\U0001F3FD', {
                'desc': 'man in suit levitating: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F574\U0001F3FE', {
                'desc': 'man in suit levitating: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F574\U0001F3FF', {
                'desc': 'man in suit levitating: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-activity',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0001F574', {
        'desc': 'man in suit levitating',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5E3\U0000FE0F', {
        'desc': 'speaking head',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True
    }),
    ('\U0001F5E3', {
        'desc': 'speaking head',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F464', {
        'desc': 'bust in silhouette',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F465', {
        'desc': 'busts in silhouette',
        'group': 'Smileys & People',
        'subgroup': 'person-activity',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F93A', {
        'desc': 'person fencing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C7', {
        'desc': 'horse racing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C7\U0001F3FB', {
                'desc': 'horse racing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C7\U0001F3FC', {
                'desc': 'horse racing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C7\U0001F3FD', {
                'desc': 'horse racing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C7\U0001F3FE', {
                'desc': 'horse racing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C7\U0001F3FF', {
                'desc': 'horse racing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F7\U0000FE0F', {
        'desc': 'skier',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True
    }),
    ('\U000026F7', {
        'desc': 'skier',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C2', {
        'desc': 'snowboarder',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C2\U0001F3FB', {
                'desc': 'snowboarder: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C2\U0001F3FC', {
                'desc': 'snowboarder: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C2\U0001F3FD', {
                'desc': 'snowboarder: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C2\U0001F3FE', {
                'desc': 'snowboarder: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C2\U0001F3FF', {
                'desc': 'snowboarder: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3CC\U0000FE0F', {
        'desc': 'person golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CC\U0001F3FB', {
                'desc': 'person golfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CC\U0001F3FC', {
                'desc': 'person golfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CC\U0001F3FD', {
                'desc': 'person golfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CC\U0001F3FE', {
                'desc': 'person golfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CC\U0001F3FF', {
                'desc': 'person golfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0001F3CC', {
        'desc': 'person golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3CC\U0000FE0F\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CC\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man golfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man golfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man golfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man golfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man golfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3CC\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3CC\U0000FE0F\U0000200D\U00002642', {
        'desc': 'man golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3CC\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man golfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man golfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man golfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man golfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man golfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3CC\U0000200D\U00002642', {
        'desc': 'man golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3CC\U0000FE0F\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CC\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman golfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman golfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman golfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman golfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CC\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman golfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3CC\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3CC\U0000FE0F\U0000200D\U00002640', {
        'desc': 'woman golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3CC\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman golfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman golfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman golfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman golfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CC\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman golfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3CC\U0000200D\U00002640', {
        'desc': 'woman golfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3C4', {
        'desc': 'person surfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C4\U0001F3FB', {
                'desc': 'person surfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C4\U0001F3FC', {
                'desc': 'person surfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C4\U0001F3FD', {
                'desc': 'person surfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C4\U0001F3FE', {
                'desc': 'person surfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3C4\U0001F3FF', {
                'desc': 'person surfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C4\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man surfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C4\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man surfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man surfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man surfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man surfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man surfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3C4\U0000200D\U00002642', {
        'desc': 'man surfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3C4\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man surfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man surfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man surfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man surfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man surfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3C4\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman surfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3C4\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman surfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman surfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman surfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman surfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3C4\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman surfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3C4\U0000200D\U00002640', {
        'desc': 'woman surfing',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3C4\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman surfing: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman surfing: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman surfing: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman surfing: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3C4\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman surfing: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6A3', {
        'desc': 'person rowing boat',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6A3\U0001F3FB', {
                'desc': 'person rowing boat: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6A3\U0001F3FC', {
                'desc': 'person rowing boat: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6A3\U0001F3FD', {
                'desc': 'person rowing boat: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6A3\U0001F3FE', {
                'desc': 'person rowing boat: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6A3\U0001F3FF', {
                'desc': 'person rowing boat: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A3\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man rowing boat',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6A3\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man rowing boat: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man rowing boat: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man rowing boat: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man rowing boat: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man rowing boat: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6A3\U0000200D\U00002642', {
        'desc': 'man rowing boat',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6A3\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man rowing boat: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man rowing boat: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man rowing boat: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man rowing boat: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man rowing boat: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6A3\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman rowing boat',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6A3\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman rowing boat: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman rowing boat: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman rowing boat: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman rowing boat: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6A3\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman rowing boat: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6A3\U0000200D\U00002640', {
        'desc': 'woman rowing boat',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6A3\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman rowing boat: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman rowing boat: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman rowing boat: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman rowing boat: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6A3\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman rowing boat: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3CA', {
        'desc': 'person swimming',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CA\U0001F3FB', {
                'desc': 'person swimming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CA\U0001F3FC', {
                'desc': 'person swimming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CA\U0001F3FD', {
                'desc': 'person swimming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CA\U0001F3FE', {
                'desc': 'person swimming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CA\U0001F3FF', {
                'desc': 'person swimming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3CA\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man swimming',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CA\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man swimming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man swimming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man swimming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man swimming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man swimming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3CA\U0000200D\U00002642', {
        'desc': 'man swimming',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3CA\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man swimming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man swimming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man swimming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man swimming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man swimming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3CA\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman swimming',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CA\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman swimming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman swimming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman swimming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman swimming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CA\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman swimming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3CA\U0000200D\U00002640', {
        'desc': 'woman swimming',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3CA\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman swimming: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman swimming: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman swimming: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman swimming: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CA\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman swimming: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U000026F9\U0000FE0F', {
        'desc': 'person bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U000026F9\U0001F3FB', {
                'desc': 'person bouncing ball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U000026F9\U0001F3FC', {
                'desc': 'person bouncing ball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U000026F9\U0001F3FD', {
                'desc': 'person bouncing ball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U000026F9\U0001F3FE', {
                'desc': 'person bouncing ball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U000026F9\U0001F3FF', {
                'desc': 'person bouncing ball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U000026F9', {
        'desc': 'person bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F9\U0000FE0F\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U000026F9\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bouncing ball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bouncing ball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bouncing ball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bouncing ball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man bouncing ball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U000026F9\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U000026F9\U0000FE0F\U0000200D\U00002642', {
        'desc': 'man bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U000026F9\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man bouncing ball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man bouncing ball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man bouncing ball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man bouncing ball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man bouncing ball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U000026F9\U0000200D\U00002642', {
        'desc': 'man bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U000026F9\U0000FE0F\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U000026F9\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bouncing ball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bouncing ball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bouncing ball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bouncing ball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U000026F9\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman bouncing ball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U000026F9\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U000026F9\U0000FE0F\U0000200D\U00002640', {
        'desc': 'woman bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U000026F9\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman bouncing ball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman bouncing ball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman bouncing ball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman bouncing ball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U000026F9\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman bouncing ball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U000026F9\U0000200D\U00002640', {
        'desc': 'woman bouncing ball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3CB\U0000FE0F', {
        'desc': 'person lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CB\U0001F3FB', {
                'desc': 'person lifting weights: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CB\U0001F3FC', {
                'desc': 'person lifting weights: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CB\U0001F3FD', {
                'desc': 'person lifting weights: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CB\U0001F3FE', {
                'desc': 'person lifting weights: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F3CB\U0001F3FF', {
                'desc': 'person lifting weights: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0001F3CB', {
        'desc': 'person lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3CB\U0000FE0F\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CB\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man lifting weights: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man lifting weights: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man lifting weights: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man lifting weights: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man lifting weights: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3CB\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3CB\U0000FE0F\U0000200D\U00002642', {
        'desc': 'man lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3CB\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man lifting weights: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man lifting weights: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man lifting weights: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man lifting weights: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man lifting weights: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3CB\U0000200D\U00002642', {
        'desc': 'man lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3CB\U0000FE0F\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F3CB\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman lifting weights: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman lifting weights: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman lifting weights: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman lifting weights: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F3CB\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman lifting weights: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3CB\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F3CB\U0000FE0F\U0000200D\U00002640', {
        'desc': 'woman lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F3CB\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman lifting weights: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman lifting weights: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman lifting weights: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman lifting weights: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F3CB\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman lifting weights: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3CB\U0000200D\U00002640', {
        'desc': 'woman lifting weights',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F6B4', {
        'desc': 'person biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B4\U0001F3FB', {
                'desc': 'person biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B4\U0001F3FC', {
                'desc': 'person biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B4\U0001F3FD', {
                'desc': 'person biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B4\U0001F3FE', {
                'desc': 'person biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B4\U0001F3FF', {
                'desc': 'person biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B4\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B4\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6B4\U0000200D\U00002642', {
        'desc': 'man biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6B4\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6B4\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B4\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B4\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6B4\U0000200D\U00002640', {
        'desc': 'woman biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6B4\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B4\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6B5', {
        'desc': 'person mountain biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B5\U0001F3FB', {
                'desc': 'person mountain biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B5\U0001F3FC', {
                'desc': 'person mountain biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B5\U0001F3FD', {
                'desc': 'person mountain biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B5\U0001F3FE', {
                'desc': 'person mountain biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F6B5\U0001F3FF', {
                'desc': 'person mountain biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B5\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man mountain biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B5\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mountain biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mountain biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mountain biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mountain biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man mountain biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6B5\U0000200D\U00002642', {
        'desc': 'man mountain biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6B5\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man mountain biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man mountain biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man mountain biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man mountain biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man mountain biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F6B5\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman mountain biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F6B5\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mountain biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mountain biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mountain biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mountain biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F6B5\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman mountain biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F6B5\U0000200D\U00002640', {
        'desc': 'woman mountain biking',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F6B5\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman mountain biking: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman mountain biking: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman mountain biking: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman mountain biking: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F6B5\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman mountain biking: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F3CE\U0000FE0F', {
        'desc': 'racing car',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True
    }),
    ('\U0001F3CE', {
        'desc': 'racing car',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3CD\U0000FE0F', {
        'desc': 'motorcycle',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True
    }),
    ('\U0001F3CD', {
        'desc': 'motorcycle',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F938', {
        'desc': 'person cartwheeling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F938\U0001F3FB', {
                'desc': 'person cartwheeling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F938\U0001F3FC', {
                'desc': 'person cartwheeling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F938\U0001F3FD', {
                'desc': 'person cartwheeling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F938\U0001F3FE', {
                'desc': 'person cartwheeling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F938\U0001F3FF', {
                'desc': 'person cartwheeling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F938\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man cartwheeling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F938\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man cartwheeling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man cartwheeling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man cartwheeling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man cartwheeling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man cartwheeling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F938\U0000200D\U00002642', {
        'desc': 'man cartwheeling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F938\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man cartwheeling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man cartwheeling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man cartwheeling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man cartwheeling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man cartwheeling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F938\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman cartwheeling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F938\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman cartwheeling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman cartwheeling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman cartwheeling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman cartwheeling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F938\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman cartwheeling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F938\U0000200D\U00002640', {
        'desc': 'woman cartwheeling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F938\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman cartwheeling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman cartwheeling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman cartwheeling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman cartwheeling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F938\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman cartwheeling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F93C', {
        'desc': 'people wrestling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F93C\U0000200D\U00002642\U0000FE0F', {
        'desc': 'men wrestling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F93C\U0000200D\U00002642', {
        'desc': 'men wrestling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F93C\U0000200D\U00002640\U0000FE0F', {
        'desc': 'women wrestling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F93C\U0000200D\U00002640', {
        'desc': 'women wrestling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False
    }),
    ('\U0001F93D', {
        'desc': 'person playing water polo',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F93D\U0001F3FB', {
                'desc': 'person playing water polo: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93D\U0001F3FC', {
                'desc': 'person playing water polo: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93D\U0001F3FD', {
                'desc': 'person playing water polo: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93D\U0001F3FE', {
                'desc': 'person playing water polo: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93D\U0001F3FF', {
                'desc': 'person playing water polo: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F93D\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man playing water polo',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F93D\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing water polo: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing water polo: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing water polo: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing water polo: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing water polo: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F93D\U0000200D\U00002642', {
        'desc': 'man playing water polo',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F93D\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man playing water polo: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man playing water polo: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man playing water polo: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man playing water polo: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man playing water polo: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F93D\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman playing water polo',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F93D\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing water polo: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing water polo: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing water polo: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing water polo: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93D\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing water polo: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F93D\U0000200D\U00002640', {
        'desc': 'woman playing water polo',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F93D\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman playing water polo: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman playing water polo: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman playing water polo: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman playing water polo: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93D\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman playing water polo: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F93E', {
        'desc': 'person playing handball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F93E\U0001F3FB', {
                'desc': 'person playing handball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93E\U0001F3FC', {
                'desc': 'person playing handball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93E\U0001F3FD', {
                'desc': 'person playing handball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93E\U0001F3FE', {
                'desc': 'person playing handball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F93E\U0001F3FF', {
                'desc': 'person playing handball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F93E\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man playing handball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F93E\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing handball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing handball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing handball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing handball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man playing handball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F93E\U0000200D\U00002642', {
        'desc': 'man playing handball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F93E\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man playing handball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man playing handball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man playing handball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man playing handball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man playing handball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F93E\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman playing handball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F93E\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing handball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing handball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing handball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing handball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F93E\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman playing handball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F93E\U0000200D\U00002640', {
        'desc': 'woman playing handball',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F93E\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman playing handball: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman playing handball: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman playing handball: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman playing handball: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F93E\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman playing handball: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F939', {
        'desc': 'person juggling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F939\U0001F3FB', {
                'desc': 'person juggling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F939\U0001F3FC', {
                'desc': 'person juggling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F939\U0001F3FD', {
                'desc': 'person juggling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F939\U0001F3FE', {
                'desc': 'person juggling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F939\U0001F3FF', {
                'desc': 'person juggling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F939\U0000200D\U00002642\U0000FE0F', {
        'desc': 'man juggling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F939\U0001F3FB\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man juggling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FC\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man juggling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FD\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man juggling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FE\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man juggling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FF\U0000200D\U00002642\U0000FE0F', {
                'desc': 'man juggling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F939\U0000200D\U00002642', {
        'desc': 'man juggling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F939\U0001F3FB\U0000200D\U00002642', {
                'desc': 'man juggling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FC\U0000200D\U00002642', {
                'desc': 'man juggling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FD\U0000200D\U00002642', {
                'desc': 'man juggling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FE\U0000200D\U00002642', {
                'desc': 'man juggling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FF\U0000200D\U00002642', {
                'desc': 'man juggling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F939\U0000200D\U00002640\U0000FE0F', {
        'desc': 'woman juggling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F939\U0001F3FB\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman juggling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FC\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman juggling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FD\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman juggling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FE\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman juggling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            }),
            ('\U0001F939\U0001F3FF\U0000200D\U00002640\U0000FE0F', {
                'desc': 'woman juggling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': True
            })
        ]),
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F939\U0000200D\U00002640', {
        'desc': 'woman juggling',
        'group': 'Smileys & People',
        'subgroup': 'person-sport',
        'fully-qualified': False,
        'variations': OrderedDict([
            ('\U0001F939\U0001F3FB\U0000200D\U00002640', {
                'desc': 'woman juggling: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FC\U0000200D\U00002640', {
                'desc': 'woman juggling: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FD\U0000200D\U00002640', {
                'desc': 'woman juggling: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FE\U0000200D\U00002640', {
                'desc': 'woman juggling: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            }),
            ('\U0001F939\U0001F3FF\U0000200D\U00002640', {
                'desc': 'woman juggling: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'person-sport',
                'fully-qualified': False
            })
        ])
    }),
    ('\U0001F46B', {
        'desc': 'man and woman holding hands',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F46C', {
        'desc': 'two men holding hands',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F46D', {
        'desc': 'two women holding hands',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F48F', {
        'desc': 'kiss',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F469\U0000200D\U00002764\U0000FE0F\U0000200D\U0001F48B\U0000200D\U0001F468', {
        'desc': 'kiss: woman, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U00002764\U0000200D\U0001F48B\U0000200D\U0001F468', {
        'desc': 'kiss: woman, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': False
    }),
    ('\U0001F468\U0000200D\U00002764\U0000FE0F\U0000200D\U0001F48B\U0000200D\U0001F468', {
        'desc': 'kiss: man, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U00002764\U0000200D\U0001F48B\U0000200D\U0001F468', {
        'desc': 'kiss: man, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': False
    }),
    ('\U0001F469\U0000200D\U00002764\U0000FE0F\U0000200D\U0001F48B\U0000200D\U0001F469', {
        'desc': 'kiss: woman, woman',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U00002764\U0000200D\U0001F48B\U0000200D\U0001F469', {
        'desc': 'kiss: woman, woman',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': False
    }),
    ('\U0001F491', {
        'desc': 'couple with heart',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F469\U0000200D\U00002764\U0000FE0F\U0000200D\U0001F468', {
        'desc': 'couple with heart: woman, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U00002764\U0000200D\U0001F468', {
        'desc': 'couple with heart: woman, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': False
    }),
    ('\U0001F468\U0000200D\U00002764\U0000FE0F\U0000200D\U0001F468', {
        'desc': 'couple with heart: man, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U00002764\U0000200D\U0001F468', {
        'desc': 'couple with heart: man, man',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': False
    }),
    ('\U0001F469\U0000200D\U00002764\U0000FE0F\U0000200D\U0001F469', {
        'desc': 'couple with heart: woman, woman',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U00002764\U0000200D\U0001F469', {
        'desc': 'couple with heart: woman, woman',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': False
    }),
    ('\U0001F46A', {
        'desc': 'family',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F468\U0000200D\U0001F469\U0000200D\U0001F466', {
        'desc': 'family: man, woman, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F469\U0000200D\U0001F467', {
        'desc': 'family: man, woman, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F469\U0000200D\U0001F467\U0000200D\U0001F466', {
        'desc': 'family: man, woman, girl, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F469\U0000200D\U0001F466\U0000200D\U0001F466', {
        'desc': 'family: man, woman, boy, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F469\U0000200D\U0001F467\U0000200D\U0001F467', {
        'desc': 'family: man, woman, girl, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F468\U0000200D\U0001F466', {
        'desc': 'family: man, man, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F468\U0000200D\U0001F467', {
        'desc': 'family: man, man, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F468\U0000200D\U0001F467\U0000200D\U0001F466', {
        'desc': 'family: man, man, girl, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F468\U0000200D\U0001F466\U0000200D\U0001F466', {
        'desc': 'family: man, man, boy, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F468\U0000200D\U0001F467\U0000200D\U0001F467', {
        'desc': 'family: man, man, girl, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F469\U0000200D\U0001F466', {
        'desc': 'family: woman, woman, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F469\U0000200D\U0001F467', {
        'desc': 'family: woman, woman, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F469\U0000200D\U0001F467\U0000200D\U0001F466', {
        'desc': 'family: woman, woman, girl, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F469\U0000200D\U0001F466\U0000200D\U0001F466', {
        'desc': 'family: woman, woman, boy, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F469\U0000200D\U0001F467\U0000200D\U0001F467', {
        'desc': 'family: woman, woman, girl, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F466', {
        'desc': 'family: man, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F466\U0000200D\U0001F466', {
        'desc': 'family: man, boy, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F467', {
        'desc': 'family: man, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F467\U0000200D\U0001F466', {
        'desc': 'family: man, girl, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F468\U0000200D\U0001F467\U0000200D\U0001F467', {
        'desc': 'family: man, girl, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F466', {
        'desc': 'family: woman, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F466\U0000200D\U0001F466', {
        'desc': 'family: woman, boy, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F467', {
        'desc': 'family: woman, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F467\U0000200D\U0001F466', {
        'desc': 'family: woman, girl, boy',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F469\U0000200D\U0001F467\U0000200D\U0001F467', {
        'desc': 'family: woman, girl, girl',
        'group': 'Smileys & People',
        'subgroup': 'family',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F933', {
        'desc': 'selfie',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F933\U0001F3FB', {
                'desc': 'selfie: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F933\U0001F3FC', {
                'desc': 'selfie: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F933\U0001F3FD', {
                'desc': 'selfie: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F933\U0001F3FE', {
                'desc': 'selfie: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F933\U0001F3FF', {
                'desc': 'selfie: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4AA', {
        'desc': 'flexed biceps',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F4AA\U0001F3FB', {
                'desc': 'flexed biceps: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F4AA\U0001F3FC', {
                'desc': 'flexed biceps: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F4AA\U0001F3FD', {
                'desc': 'flexed biceps: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F4AA\U0001F3FE', {
                'desc': 'flexed biceps: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F4AA\U0001F3FF', {
                'desc': 'flexed biceps: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B5', {
        'desc': 'leg',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B5\U0001F3FB', {
                'desc': 'leg: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B5\U0001F3FC', {
                'desc': 'leg: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B5\U0001F3FD', {
                'desc': 'leg: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B5\U0001F3FE', {
                'desc': 'leg: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B5\U0001F3FF', {
                'desc': 'leg: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B6', {
        'desc': 'foot',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F9B6\U0001F3FB', {
                'desc': 'foot: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B6\U0001F3FC', {
                'desc': 'foot: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B6\U0001F3FD', {
                'desc': 'foot: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B6\U0001F3FE', {
                'desc': 'foot: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F9B6\U0001F3FF', {
                'desc': 'foot: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F448', {
        'desc': 'backhand index pointing left',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F448\U0001F3FB', {
                'desc': 'backhand index pointing left: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F448\U0001F3FC', {
                'desc': 'backhand index pointing left: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F448\U0001F3FD', {
                'desc': 'backhand index pointing left: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F448\U0001F3FE', {
                'desc': 'backhand index pointing left: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F448\U0001F3FF', {
                'desc': 'backhand index pointing left: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F449', {
        'desc': 'backhand index pointing right',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F449\U0001F3FB', {
                'desc': 'backhand index pointing right: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F449\U0001F3FC', {
                'desc': 'backhand index pointing right: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F449\U0001F3FD', {
                'desc': 'backhand index pointing right: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F449\U0001F3FE', {
                'desc': 'backhand index pointing right: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F449\U0001F3FF', {
                'desc': 'backhand index pointing right: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0000261D\U0000FE0F', {
        'desc': 'index pointing up',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0000261D\U0001F3FB', {
                'desc': 'index pointing up: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000261D\U0001F3FC', {
                'desc': 'index pointing up: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000261D\U0001F3FD', {
                'desc': 'index pointing up: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000261D\U0001F3FE', {
                'desc': 'index pointing up: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000261D\U0001F3FF', {
                'desc': 'index pointing up: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0000261D', {
        'desc': 'index pointing up',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F446', {
        'desc': 'backhand index pointing up',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F446\U0001F3FB', {
                'desc': 'backhand index pointing up: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F446\U0001F3FC', {
                'desc': 'backhand index pointing up: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F446\U0001F3FD', {
                'desc': 'backhand index pointing up: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F446\U0001F3FE', {
                'desc': 'backhand index pointing up: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F446\U0001F3FF', {
                'desc': 'backhand index pointing up: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F595', {
        'desc': 'middle finger',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F595\U0001F3FB', {
                'desc': 'middle finger: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F595\U0001F3FC', {
                'desc': 'middle finger: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F595\U0001F3FD', {
                'desc': 'middle finger: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F595\U0001F3FE', {
                'desc': 'middle finger: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F595\U0001F3FF', {
                'desc': 'middle finger: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F447', {
        'desc': 'backhand index pointing down',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F447\U0001F3FB', {
                'desc': 'backhand index pointing down: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F447\U0001F3FC', {
                'desc': 'backhand index pointing down: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F447\U0001F3FD', {
                'desc': 'backhand index pointing down: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F447\U0001F3FE', {
                'desc': 'backhand index pointing down: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F447\U0001F3FF', {
                'desc': 'backhand index pointing down: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0000270C\U0000FE0F', {
        'desc': 'victory hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0000270C\U0001F3FB', {
                'desc': 'victory hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270C\U0001F3FC', {
                'desc': 'victory hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270C\U0001F3FD', {
                'desc': 'victory hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270C\U0001F3FE', {
                'desc': 'victory hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270C\U0001F3FF', {
                'desc': 'victory hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0000270C', {
        'desc': 'victory hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F91E', {
        'desc': 'crossed fingers',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F91E\U0001F3FB', {
                'desc': 'crossed fingers: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91E\U0001F3FC', {
                'desc': 'crossed fingers: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91E\U0001F3FD', {
                'desc': 'crossed fingers: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91E\U0001F3FE', {
                'desc': 'crossed fingers: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91E\U0001F3FF', {
                'desc': 'crossed fingers: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F596', {
        'desc': 'vulcan salute',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F596\U0001F3FB', {
                'desc': 'vulcan salute: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F596\U0001F3FC', {
                'desc': 'vulcan salute: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F596\U0001F3FD', {
                'desc': 'vulcan salute: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F596\U0001F3FE', {
                'desc': 'vulcan salute: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F596\U0001F3FF', {
                'desc': 'vulcan salute: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F918', {
        'desc': 'sign of the horns',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F918\U0001F3FB', {
                'desc': 'sign of the horns: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F918\U0001F3FC', {
                'desc': 'sign of the horns: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F918\U0001F3FD', {
                'desc': 'sign of the horns: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F918\U0001F3FE', {
                'desc': 'sign of the horns: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F918\U0001F3FF', {
                'desc': 'sign of the horns: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F919', {
        'desc': 'call me hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F919\U0001F3FB', {
                'desc': 'call me hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F919\U0001F3FC', {
                'desc': 'call me hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F919\U0001F3FD', {
                'desc': 'call me hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F919\U0001F3FE', {
                'desc': 'call me hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F919\U0001F3FF', {
                'desc': 'call me hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F590\U0000FE0F', {
        'desc': 'hand with fingers splayed',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F590\U0001F3FB', {
                'desc': 'hand with fingers splayed: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F590\U0001F3FC', {
                'desc': 'hand with fingers splayed: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F590\U0001F3FD', {
                'desc': 'hand with fingers splayed: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F590\U0001F3FE', {
                'desc': 'hand with fingers splayed: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F590\U0001F3FF', {
                'desc': 'hand with fingers splayed: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0001F590', {
        'desc': 'hand with fingers splayed',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0000270B', {
        'desc': 'raised hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0000270B\U0001F3FB', {
                'desc': 'raised hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270B\U0001F3FC', {
                'desc': 'raised hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270B\U0001F3FD', {
                'desc': 'raised hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270B\U0001F3FE', {
                'desc': 'raised hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270B\U0001F3FF', {
                'desc': 'raised hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F44C', {
        'desc': 'OK hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F44C\U0001F3FB', {
                'desc': 'OK hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44C\U0001F3FC', {
                'desc': 'OK hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44C\U0001F3FD', {
                'desc': 'OK hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44C\U0001F3FE', {
                'desc': 'OK hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44C\U0001F3FF', {
                'desc': 'OK hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F44D', {
        'desc': 'thumbs up',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F44D\U0001F3FB', {
                'desc': 'thumbs up: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44D\U0001F3FC', {
                'desc': 'thumbs up: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44D\U0001F3FD', {
                'desc': 'thumbs up: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44D\U0001F3FE', {
                'desc': 'thumbs up: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44D\U0001F3FF', {
                'desc': 'thumbs up: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F44E', {
        'desc': 'thumbs down',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F44E\U0001F3FB', {
                'desc': 'thumbs down: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44E\U0001F3FC', {
                'desc': 'thumbs down: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44E\U0001F3FD', {
                'desc': 'thumbs down: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44E\U0001F3FE', {
                'desc': 'thumbs down: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44E\U0001F3FF', {
                'desc': 'thumbs down: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0000270A', {
        'desc': 'raised fist',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0000270A\U0001F3FB', {
                'desc': 'raised fist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270A\U0001F3FC', {
                'desc': 'raised fist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270A\U0001F3FD', {
                'desc': 'raised fist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270A\U0001F3FE', {
                'desc': 'raised fist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270A\U0001F3FF', {
                'desc': 'raised fist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F44A', {
        'desc': 'oncoming fist',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F44A\U0001F3FB', {
                'desc': 'oncoming fist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44A\U0001F3FC', {
                'desc': 'oncoming fist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44A\U0001F3FD', {
                'desc': 'oncoming fist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44A\U0001F3FE', {
                'desc': 'oncoming fist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44A\U0001F3FF', {
                'desc': 'oncoming fist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F91B', {
        'desc': 'left-facing fist',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F91B\U0001F3FB', {
                'desc': 'left-facing fist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91B\U0001F3FC', {
                'desc': 'left-facing fist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91B\U0001F3FD', {
                'desc': 'left-facing fist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91B\U0001F3FE', {
                'desc': 'left-facing fist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91B\U0001F3FF', {
                'desc': 'left-facing fist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F91C', {
        'desc': 'right-facing fist',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F91C\U0001F3FB', {
                'desc': 'right-facing fist: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91C\U0001F3FC', {
                'desc': 'right-facing fist: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91C\U0001F3FD', {
                'desc': 'right-facing fist: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91C\U0001F3FE', {
                'desc': 'right-facing fist: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91C\U0001F3FF', {
                'desc': 'right-facing fist: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F91A', {
        'desc': 'raised back of hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F91A\U0001F3FB', {
                'desc': 'raised back of hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91A\U0001F3FC', {
                'desc': 'raised back of hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91A\U0001F3FD', {
                'desc': 'raised back of hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91A\U0001F3FE', {
                'desc': 'raised back of hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91A\U0001F3FF', {
                'desc': 'raised back of hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F44B', {
        'desc': 'waving hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F44B\U0001F3FB', {
                'desc': 'waving hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44B\U0001F3FC', {
                'desc': 'waving hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44B\U0001F3FD', {
                'desc': 'waving hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44B\U0001F3FE', {
                'desc': 'waving hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44B\U0001F3FF', {
                'desc': 'waving hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F91F', {
        'desc': 'love-you gesture',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F91F\U0001F3FB', {
                'desc': 'love-you gesture: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91F\U0001F3FC', {
                'desc': 'love-you gesture: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91F\U0001F3FD', {
                'desc': 'love-you gesture: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91F\U0001F3FE', {
                'desc': 'love-you gesture: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F91F\U0001F3FF', {
                'desc': 'love-you gesture: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0000270D\U0000FE0F', {
        'desc': 'writing hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0000270D\U0001F3FB', {
                'desc': 'writing hand: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270D\U0001F3FC', {
                'desc': 'writing hand: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270D\U0001F3FD', {
                'desc': 'writing hand: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270D\U0001F3FE', {
                'desc': 'writing hand: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0000270D\U0001F3FF', {
                'desc': 'writing hand: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ])
    }),
    ('\U0000270D', {
        'desc': 'writing hand',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False,
        'Emoji': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F44F', {
        'desc': 'clapping hands',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F44F\U0001F3FB', {
                'desc': 'clapping hands: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44F\U0001F3FC', {
                'desc': 'clapping hands: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44F\U0001F3FD', {
                'desc': 'clapping hands: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44F\U0001F3FE', {
                'desc': 'clapping hands: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F44F\U0001F3FF', {
                'desc': 'clapping hands: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F450', {
        'desc': 'open hands',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F450\U0001F3FB', {
                'desc': 'open hands: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F450\U0001F3FC', {
                'desc': 'open hands: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F450\U0001F3FD', {
                'desc': 'open hands: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F450\U0001F3FE', {
                'desc': 'open hands: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F450\U0001F3FF', {
                'desc': 'open hands: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F64C', {
        'desc': 'raising hands',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64C\U0001F3FB', {
                'desc': 'raising hands: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64C\U0001F3FC', {
                'desc': 'raising hands: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64C\U0001F3FD', {
                'desc': 'raising hands: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64C\U0001F3FE', {
                'desc': 'raising hands: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64C\U0001F3FF', {
                'desc': 'raising hands: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F932', {
        'desc': 'palms up together',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F932\U0001F3FB', {
                'desc': 'palms up together: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F932\U0001F3FC', {
                'desc': 'palms up together: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F932\U0001F3FD', {
                'desc': 'palms up together: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F932\U0001F3FE', {
                'desc': 'palms up together: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F932\U0001F3FF', {
                'desc': 'palms up together: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F64F', {
        'desc': 'folded hands',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F64F\U0001F3FB', {
                'desc': 'folded hands: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64F\U0001F3FC', {
                'desc': 'folded hands: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64F\U0001F3FD', {
                'desc': 'folded hands: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64F\U0001F3FE', {
                'desc': 'folded hands: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F64F\U0001F3FF', {
                'desc': 'folded hands: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F91D', {
        'desc': 'handshake',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F485', {
        'desc': 'nail polish',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F485\U0001F3FB', {
                'desc': 'nail polish: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F485\U0001F3FC', {
                'desc': 'nail polish: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F485\U0001F3FD', {
                'desc': 'nail polish: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F485\U0001F3FE', {
                'desc': 'nail polish: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F485\U0001F3FF', {
                'desc': 'nail polish: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F442', {
        'desc': 'ear',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F442\U0001F3FB', {
                'desc': 'ear: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F442\U0001F3FC', {
                'desc': 'ear: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F442\U0001F3FD', {
                'desc': 'ear: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F442\U0001F3FE', {
                'desc': 'ear: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F442\U0001F3FF', {
                'desc': 'ear: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F443', {
        'desc': 'nose',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'variations': OrderedDict([
            ('\U0001F443\U0001F3FB', {
                'desc': 'nose: light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F443\U0001F3FC', {
                'desc': 'nose: medium-light skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F443\U0001F3FD', {
                'desc': 'nose: medium skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F443\U0001F3FE', {
                'desc': 'nose: medium-dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            }),
            ('\U0001F443\U0001F3FF', {
                'desc': 'nose: dark skin tone',
                'group': 'Smileys & People',
                'subgroup': 'body',
                'fully-qualified': True,
                'Emoji_Modifier_Sequence': True
            })
        ]),
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Modifier_Base': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B0', {
        'desc': 'red-haired',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Component': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B1', {
        'desc': 'curly-haired',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Component': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B2', {
        'desc': 'bald',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Component': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B3', {
        'desc': 'white-haired',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Emoji_Component': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F463', {
        'desc': 'footprints',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F440', {
        'desc': 'eyes',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F441\U0000FE0F', {
        'desc': 'eye',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True
    }),
    ('\U0001F441', {
        'desc': 'eye',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F441\U0000FE0F\U0000200D\U0001F5E8\U0000FE0F', {
        'desc': 'eye in speech bubble',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F441\U0000200D\U0001F5E8\U0000FE0F', {
        'desc': 'eye in speech bubble',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False
    }),
    ('\U0001F441\U0000FE0F\U0000200D\U0001F5E8', {
        'desc': 'eye in speech bubble',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False
    }),
    ('\U0001F441\U0000200D\U0001F5E8', {
        'desc': 'eye in speech bubble',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': False
    }),
    ('\U0001F9E0', {
        'desc': 'brain',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B4', {
        'desc': 'bone',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9B7', {
        'desc': 'tooth',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F445', {
        'desc': 'tongue',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F444', {
        'desc': 'mouth',
        'group': 'Smileys & People',
        'subgroup': 'body',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F48B', {
        'desc': 'kiss mark',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F498', {
        'desc': 'heart with arrow',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002764\U0000FE0F', {
        'desc': 'red heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True
    }),
    ('\U00002764', {
        'desc': 'red heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F493', {
        'desc': 'beating heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F494', {
        'desc': 'broken heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F495', {
        'desc': 'two hearts',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F496', {
        'desc': 'sparkling heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F497', {
        'desc': 'growing heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F499', {
        'desc': 'blue heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F49A', {
        'desc': 'green heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F49B', {
        'desc': 'yellow heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E1', {
        'desc': 'orange heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F49C', {
        'desc': 'purple heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5A4', {
        'desc': 'black heart',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F49D', {
        'desc': 'heart with ribbon',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F49E', {
        'desc': 'revolving hearts',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F49F', {
        'desc': 'heart decoration',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002763\U0000FE0F', {
        'desc': 'heavy heart exclamation',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True
    }),
    ('\U00002763', {
        'desc': 'heavy heart exclamation',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F48C', {
        'desc': 'love letter',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A4', {
        'desc': 'zzz',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A2', {
        'desc': 'anger symbol',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A3', {
        'desc': 'bomb',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A5', {
        'desc': 'collision',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A6', {
        'desc': 'sweat droplets',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A8', {
        'desc': 'dashing away',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4AB', {
        'desc': 'dizzy',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4AC', {
        'desc': 'speech balloon',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5E8\U0000FE0F', {
        'desc': 'left speech bubble',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True
    }),
    ('\U0001F5E8', {
        'desc': 'left speech bubble',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5EF\U0000FE0F', {
        'desc': 'right anger bubble',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True
    }),
    ('\U0001F5EF', {
        'desc': 'right anger bubble',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4AD', {
        'desc': 'thought balloon',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F573\U0000FE0F', {
        'desc': 'hole',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': True
    }),
    ('\U0001F573', {
        'desc': 'hole',
        'group': 'Smileys & People',
        'subgroup': 'emotion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F453', {
        'desc': 'glasses',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F576\U0000FE0F', {
        'desc': 'sunglasses',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True
    }),
    ('\U0001F576', {
        'desc': 'sunglasses',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F97D', {
        'desc': 'goggles',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F97C', {
        'desc': 'lab coat',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F454', {
        'desc': 'necktie',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F455', {
        'desc': 't-shirt',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F456', {
        'desc': 'jeans',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E3', {
        'desc': 'scarf',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E4', {
        'desc': 'gloves',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E5', {
        'desc': 'coat',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E6', {
        'desc': 'socks',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F457', {
        'desc': 'dress',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F458', {
        'desc': 'kimono',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F459', {
        'desc': 'bikini',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F45A', {
        'desc': 'woman’s clothes',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F45B', {
        'desc': 'purse',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F45C', {
        'desc': 'handbag',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F45D', {
        'desc': 'clutch bag',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6CD\U0000FE0F', {
        'desc': 'shopping bags',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True
    }),
    ('\U0001F6CD', {
        'desc': 'shopping bags',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F392', {
        'desc': 'school backpack',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F45E', {
        'desc': 'man’s shoe',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F45F', {
        'desc': 'running shoe',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F97E', {
        'desc': 'hiking boot',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F97F', {
        'desc': 'woman’s flat shoe',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F460', {
        'desc': 'high-heeled shoe',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F461', {
        'desc': 'woman’s sandal',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F462', {
        'desc': 'woman’s boot',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F451', {
        'desc': 'crown',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F452', {
        'desc': 'woman’s hat',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A9', {
        'desc': 'top hat',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F393', {
        'desc': 'graduation cap',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E2', {
        'desc': 'billed cap',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026D1\U0000FE0F', {
        'desc': 'rescue worker’s helmet',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True
    }),
    ('\U000026D1', {
        'desc': 'rescue worker’s helmet',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4FF', {
        'desc': 'prayer beads',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F484', {
        'desc': 'lipstick',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F48D', {
        'desc': 'ring',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F48E', {
        'desc': 'gem stone',
        'group': 'Smileys & People',
        'subgroup': 'clothing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F435', {
        'desc': 'monkey face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F412', {
        'desc': 'monkey',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F98D', {
        'desc': 'gorilla',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F436', {
        'desc': 'dog face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F415', {
        'desc': 'dog',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F429', {
        'desc': 'poodle',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F43A', {
        'desc': 'wolf face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F98A', {
        'desc': 'fox face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F99D', {
        'desc': 'raccoon',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F431', {
        'desc': 'cat face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F408', {
        'desc': 'cat',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F981', {
        'desc': 'lion face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F42F', {
        'desc': 'tiger face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F405', {
        'desc': 'tiger',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F406', {
        'desc': 'leopard',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F434', {
        'desc': 'horse face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F40E', {
        'desc': 'horse',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F984', {
        'desc': 'unicorn face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F993', {
        'desc': 'zebra',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F98C', {
        'desc': 'deer',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F42E', {
        'desc': 'cow face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F402', {
        'desc': 'ox',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F403', {
        'desc': 'water buffalo',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F404', {
        'desc': 'cow',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F437', {
        'desc': 'pig face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F416', {
        'desc': 'pig',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F417', {
        'desc': 'boar',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F43D', {
        'desc': 'pig nose',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F40F', {
        'desc': 'ram',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F411', {
        'desc': 'ewe',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F410', {
        'desc': 'goat',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F42A', {
        'desc': 'camel',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F42B', {
        'desc': 'two-hump camel',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F999', {
        'desc': 'llama',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F992', {
        'desc': 'giraffe',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F418', {
        'desc': 'elephant',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F98F', {
        'desc': 'rhinoceros',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F99B', {
        'desc': 'hippopotamus',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F42D', {
        'desc': 'mouse face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F401', {
        'desc': 'mouse',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F400', {
        'desc': 'rat',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F439', {
        'desc': 'hamster face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F430', {
        'desc': 'rabbit face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F407', {
        'desc': 'rabbit',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F43F\U0000FE0F', {
        'desc': 'chipmunk',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True
    }),
    ('\U0001F43F', {
        'desc': 'chipmunk',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F994', {
        'desc': 'hedgehog',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F987', {
        'desc': 'bat',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F43B', {
        'desc': 'bear face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F428', {
        'desc': 'koala',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F43C', {
        'desc': 'panda face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F998', {
        'desc': 'kangaroo',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9A1', {
        'desc': 'badger',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F43E', {
        'desc': 'paw prints',
        'group': 'Animals & Nature',
        'subgroup': 'animal-mammal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F983', {
        'desc': 'turkey',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F414', {
        'desc': 'chicken',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F413', {
        'desc': 'rooster',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F423', {
        'desc': 'hatching chick',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F424', {
        'desc': 'baby chick',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F425', {
        'desc': 'front-facing baby chick',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F426', {
        'desc': 'bird',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F427', {
        'desc': 'penguin',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F54A\U0000FE0F', {
        'desc': 'dove',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True
    }),
    ('\U0001F54A', {
        'desc': 'dove',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F985', {
        'desc': 'eagle',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F986', {
        'desc': 'duck',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9A2', {
        'desc': 'swan',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F989', {
        'desc': 'owl',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F99A', {
        'desc': 'peacock',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F99C', {
        'desc': 'parrot',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bird',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F438', {
        'desc': 'frog face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-amphibian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F40A', {
        'desc': 'crocodile',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F422', {
        'desc': 'turtle',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F98E', {
        'desc': 'lizard',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F40D', {
        'desc': 'snake',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F432', {
        'desc': 'dragon face',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F409', {
        'desc': 'dragon',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F995', {
        'desc': 'sauropod',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F996', {
        'desc': 'T-Rex',
        'group': 'Animals & Nature',
        'subgroup': 'animal-reptile',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F433', {
        'desc': 'spouting whale',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F40B', {
        'desc': 'whale',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F42C', {
        'desc': 'dolphin',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F41F', {
        'desc': 'fish',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F420', {
        'desc': 'tropical fish',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F421', {
        'desc': 'blowfish',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F988', {
        'desc': 'shark',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F419', {
        'desc': 'octopus',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F41A', {
        'desc': 'spiral shell',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F980', {
        'desc': 'crab',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F99E', {
        'desc': 'lobster',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F990', {
        'desc': 'shrimp',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F991', {
        'desc': 'squid',
        'group': 'Animals & Nature',
        'subgroup': 'animal-marine',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F40C', {
        'desc': 'snail',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F98B', {
        'desc': 'butterfly',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F41B', {
        'desc': 'bug',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F41C', {
        'desc': 'ant',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F41D', {
        'desc': 'honeybee',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F41E', {
        'desc': 'lady beetle',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F997', {
        'desc': 'cricket',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F577\U0000FE0F', {
        'desc': 'spider',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True
    }),
    ('\U0001F577', {
        'desc': 'spider',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F578\U0000FE0F', {
        'desc': 'spider web',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True
    }),
    ('\U0001F578', {
        'desc': 'spider web',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F982', {
        'desc': 'scorpion',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F99F', {
        'desc': 'mosquito',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9A0', {
        'desc': 'microbe',
        'group': 'Animals & Nature',
        'subgroup': 'animal-bug',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F490', {
        'desc': 'bouquet',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F338', {
        'desc': 'cherry blossom',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4AE', {
        'desc': 'white flower',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F5\U0000FE0F', {
        'desc': 'rosette',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True
    }),
    ('\U0001F3F5', {
        'desc': 'rosette',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F339', {
        'desc': 'rose',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F940', {
        'desc': 'wilted flower',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F33A', {
        'desc': 'hibiscus',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F33B', {
        'desc': 'sunflower',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F33C', {
        'desc': 'blossom',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F337', {
        'desc': 'tulip',
        'group': 'Animals & Nature',
        'subgroup': 'plant-flower',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F331', {
        'desc': 'seedling',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F332', {
        'desc': 'evergreen tree',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F333', {
        'desc': 'deciduous tree',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F334', {
        'desc': 'palm tree',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F335', {
        'desc': 'cactus',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F33E', {
        'desc': 'sheaf of rice',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F33F', {
        'desc': 'herb',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002618\U0000FE0F', {
        'desc': 'shamrock',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True
    }),
    ('\U00002618', {
        'desc': 'shamrock',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F340', {
        'desc': 'four leaf clover',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F341', {
        'desc': 'maple leaf',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F342', {
        'desc': 'fallen leaf',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F343', {
        'desc': 'leaf fluttering in wind',
        'group': 'Animals & Nature',
        'subgroup': 'plant-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F347', {
        'desc': 'grapes',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F348', {
        'desc': 'melon',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F349', {
        'desc': 'watermelon',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F34A', {
        'desc': 'tangerine',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F34B', {
        'desc': 'lemon',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F34C', {
        'desc': 'banana',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F34D', {
        'desc': 'pineapple',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F96D', {
        'desc': 'mango',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F34E', {
        'desc': 'red apple',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F34F', {
        'desc': 'green apple',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F350', {
        'desc': 'pear',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F351', {
        'desc': 'peach',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F352', {
        'desc': 'cherries',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F353', {
        'desc': 'strawberry',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F95D', {
        'desc': 'kiwi fruit',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F345', {
        'desc': 'tomato',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F965', {
        'desc': 'coconut',
        'group': 'Food & Drink',
        'subgroup': 'food-fruit',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F951', {
        'desc': 'avocado',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F346', {
        'desc': 'eggplant',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F954', {
        'desc': 'potato',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F955', {
        'desc': 'carrot',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F33D', {
        'desc': 'ear of corn',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F336\U0000FE0F', {
        'desc': 'hot pepper',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True
    }),
    ('\U0001F336', {
        'desc': 'hot pepper',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F952', {
        'desc': 'cucumber',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F96C', {
        'desc': 'leafy green',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F966', {
        'desc': 'broccoli',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F344', {
        'desc': 'mushroom',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F95C', {
        'desc': 'peanuts',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F330', {
        'desc': 'chestnut',
        'group': 'Food & Drink',
        'subgroup': 'food-vegetable',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F35E', {
        'desc': 'bread',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F950', {
        'desc': 'croissant',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F956', {
        'desc': 'baguette bread',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F968', {
        'desc': 'pretzel',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F96F', {
        'desc': 'bagel',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F95E', {
        'desc': 'pancakes',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9C0', {
        'desc': 'cheese wedge',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F356', {
        'desc': 'meat on bone',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F357', {
        'desc': 'poultry leg',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F969', {
        'desc': 'cut of meat',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F953', {
        'desc': 'bacon',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F354', {
        'desc': 'hamburger',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F35F', {
        'desc': 'french fries',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F355', {
        'desc': 'pizza',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F32D', {
        'desc': 'hot dog',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F96A', {
        'desc': 'sandwich',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F32E', {
        'desc': 'taco',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F32F', {
        'desc': 'burrito',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F959', {
        'desc': 'stuffed flatbread',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F95A', {
        'desc': 'egg',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F373', {
        'desc': 'cooking',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F958', {
        'desc': 'shallow pan of food',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F372', {
        'desc': 'pot of food',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F963', {
        'desc': 'bowl with spoon',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F957', {
        'desc': 'green salad',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F37F', {
        'desc': 'popcorn',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9C2', {
        'desc': 'salt',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F96B', {
        'desc': 'canned food',
        'group': 'Food & Drink',
        'subgroup': 'food-prepared',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F371', {
        'desc': 'bento box',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F358', {
        'desc': 'rice cracker',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F359', {
        'desc': 'rice ball',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F35A', {
        'desc': 'cooked rice',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F35B', {
        'desc': 'curry rice',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F35C', {
        'desc': 'steaming bowl',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F35D', {
        'desc': 'spaghetti',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F360', {
        'desc': 'roasted sweet potato',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F362', {
        'desc': 'oden',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F363', {
        'desc': 'sushi',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F364', {
        'desc': 'fried shrimp',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F365', {
        'desc': 'fish cake with swirl',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F96E', {
        'desc': 'moon cake',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F361', {
        'desc': 'dango',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F95F', {
        'desc': 'dumpling',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F960', {
        'desc': 'fortune cookie',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F961', {
        'desc': 'takeout box',
        'group': 'Food & Drink',
        'subgroup': 'food-asian',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F366', {
        'desc': 'soft ice cream',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F367', {
        'desc': 'shaved ice',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F368', {
        'desc': 'ice cream',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F369', {
        'desc': 'doughnut',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F36A', {
        'desc': 'cookie',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F382', {
        'desc': 'birthday cake',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F370', {
        'desc': 'shortcake',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9C1', {
        'desc': 'cupcake',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F967', {
        'desc': 'pie',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F36B', {
        'desc': 'chocolate bar',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F36C', {
        'desc': 'candy',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F36D', {
        'desc': 'lollipop',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F36E', {
        'desc': 'custard',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F36F', {
        'desc': 'honey pot',
        'group': 'Food & Drink',
        'subgroup': 'food-sweet',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F37C', {
        'desc': 'baby bottle',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F95B', {
        'desc': 'glass of milk',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002615', {
        'desc': 'hot beverage',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F375', {
        'desc': 'teacup without handle',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F376', {
        'desc': 'sake',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F37E', {
        'desc': 'bottle with popping cork',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F377', {
        'desc': 'wine glass',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F378', {
        'desc': 'cocktail glass',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F379', {
        'desc': 'tropical drink',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F37A', {
        'desc': 'beer mug',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F37B', {
        'desc': 'clinking beer mugs',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F942', {
        'desc': 'clinking glasses',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F943', {
        'desc': 'tumbler glass',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F964', {
        'desc': 'cup with straw',
        'group': 'Food & Drink',
        'subgroup': 'drink',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F962', {
        'desc': 'chopsticks',
        'group': 'Food & Drink',
        'subgroup': 'dishware',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F37D\U0000FE0F', {
        'desc': 'fork and knife with plate',
        'group': 'Food & Drink',
        'subgroup': 'dishware',
        'fully-qualified': True
    }),
    ('\U0001F37D', {
        'desc': 'fork and knife with plate',
        'group': 'Food & Drink',
        'subgroup': 'dishware',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F374', {
        'desc': 'fork and knife',
        'group': 'Food & Drink',
        'subgroup': 'dishware',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F944', {
        'desc': 'spoon',
        'group': 'Food & Drink',
        'subgroup': 'dishware',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F52A', {
        'desc': 'kitchen knife',
        'group': 'Food & Drink',
        'subgroup': 'dishware',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3FA', {
        'desc': 'amphora',
        'group': 'Food & Drink',
        'subgroup': 'dishware',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F30D', {
        'desc': 'globe showing Europe-Africa',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F30E', {
        'desc': 'globe showing Americas',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F30F', {
        'desc': 'globe showing Asia-Australia',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F310', {
        'desc': 'globe with meridians',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5FA\U0000FE0F', {
        'desc': 'world map',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': True
    }),
    ('\U0001F5FA', {
        'desc': 'world map',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5FE', {
        'desc': 'map of Japan',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9ED', {
        'desc': 'compass',
        'group': 'Travel & Places',
        'subgroup': 'place-map',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D4\U0000FE0F', {
        'desc': 'snow-capped mountain',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True
    }),
    ('\U0001F3D4', {
        'desc': 'snow-capped mountain',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F0\U0000FE0F', {
        'desc': 'mountain',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True
    }),
    ('\U000026F0', {
        'desc': 'mountain',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F30B', {
        'desc': 'volcano',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5FB', {
        'desc': 'mount fuji',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D5\U0000FE0F', {
        'desc': 'camping',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True
    }),
    ('\U0001F3D5', {
        'desc': 'camping',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D6\U0000FE0F', {
        'desc': 'beach with umbrella',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True
    }),
    ('\U0001F3D6', {
        'desc': 'beach with umbrella',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3DC\U0000FE0F', {
        'desc': 'desert',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True
    }),
    ('\U0001F3DC', {
        'desc': 'desert',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3DD\U0000FE0F', {
        'desc': 'desert island',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True
    }),
    ('\U0001F3DD', {
        'desc': 'desert island',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3DE\U0000FE0F', {
        'desc': 'national park',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': True
    }),
    ('\U0001F3DE', {
        'desc': 'national park',
        'group': 'Travel & Places',
        'subgroup': 'place-geographic',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3DF\U0000FE0F', {
        'desc': 'stadium',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True
    }),
    ('\U0001F3DF', {
        'desc': 'stadium',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3DB\U0000FE0F', {
        'desc': 'classical building',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True
    }),
    ('\U0001F3DB', {
        'desc': 'classical building',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D7\U0000FE0F', {
        'desc': 'building construction',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True
    }),
    ('\U0001F3D7', {
        'desc': 'building construction',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F1', {
        'desc': 'bricks',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D8\U0000FE0F', {
        'desc': 'houses',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True
    }),
    ('\U0001F3D8', {
        'desc': 'houses',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3DA\U0000FE0F', {
        'desc': 'derelict house',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True
    }),
    ('\U0001F3DA', {
        'desc': 'derelict house',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E0', {
        'desc': 'house',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E1', {
        'desc': 'house with garden',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E2', {
        'desc': 'office building',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E3', {
        'desc': 'Japanese post office',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E4', {
        'desc': 'post office',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E5', {
        'desc': 'hospital',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E6', {
        'desc': 'bank',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E8', {
        'desc': 'hotel',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E9', {
        'desc': 'love hotel',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3EA', {
        'desc': 'convenience store',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3EB', {
        'desc': 'school',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3EC', {
        'desc': 'department store',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3ED', {
        'desc': 'factory',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3EF', {
        'desc': 'Japanese castle',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F0', {
        'desc': 'castle',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F492', {
        'desc': 'wedding',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5FC', {
        'desc': 'Tokyo tower',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5FD', {
        'desc': 'Statue of Liberty',
        'group': 'Travel & Places',
        'subgroup': 'place-building',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026EA', {
        'desc': 'church',
        'group': 'Travel & Places',
        'subgroup': 'place-religious',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F54C', {
        'desc': 'mosque',
        'group': 'Travel & Places',
        'subgroup': 'place-religious',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F54D', {
        'desc': 'synagogue',
        'group': 'Travel & Places',
        'subgroup': 'place-religious',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026E9\U0000FE0F', {
        'desc': 'shinto shrine',
        'group': 'Travel & Places',
        'subgroup': 'place-religious',
        'fully-qualified': True
    }),
    ('\U000026E9', {
        'desc': 'shinto shrine',
        'group': 'Travel & Places',
        'subgroup': 'place-religious',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F54B', {
        'desc': 'kaaba',
        'group': 'Travel & Places',
        'subgroup': 'place-religious',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F2', {
        'desc': 'fountain',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026FA', {
        'desc': 'tent',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F301', {
        'desc': 'foggy',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F303', {
        'desc': 'night with stars',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D9\U0000FE0F', {
        'desc': 'cityscape',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True
    }),
    ('\U0001F3D9', {
        'desc': 'cityscape',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F304', {
        'desc': 'sunrise over mountains',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F305', {
        'desc': 'sunrise',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F306', {
        'desc': 'cityscape at dusk',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F307', {
        'desc': 'sunset',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F309', {
        'desc': 'bridge at night',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002668\U0000FE0F', {
        'desc': 'hot springs',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True
    }),
    ('\U00002668', {
        'desc': 'hot springs',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F30C', {
        'desc': 'milky way',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A0', {
        'desc': 'carousel horse',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A1', {
        'desc': 'ferris wheel',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A2', {
        'desc': 'roller coaster',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F488', {
        'desc': 'barber pole',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3AA', {
        'desc': 'circus tent',
        'group': 'Travel & Places',
        'subgroup': 'place-other',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F682', {
        'desc': 'locomotive',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F683', {
        'desc': 'railway car',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F684', {
        'desc': 'high-speed train',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F685', {
        'desc': 'bullet train',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F686', {
        'desc': 'train',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F687', {
        'desc': 'metro',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F688', {
        'desc': 'light rail',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F689', {
        'desc': 'station',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F68A', {
        'desc': 'tram',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F69D', {
        'desc': 'monorail',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F69E', {
        'desc': 'mountain railway',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F68B', {
        'desc': 'tram car',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F68C', {
        'desc': 'bus',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F68D', {
        'desc': 'oncoming bus',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F68E', {
        'desc': 'trolleybus',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F690', {
        'desc': 'minibus',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F691', {
        'desc': 'ambulance',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F692', {
        'desc': 'fire engine',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F693', {
        'desc': 'police car',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F694', {
        'desc': 'oncoming police car',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F695', {
        'desc': 'taxi',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F696', {
        'desc': 'oncoming taxi',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F697', {
        'desc': 'automobile',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F698', {
        'desc': 'oncoming automobile',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F699', {
        'desc': 'sport utility vehicle',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F69A', {
        'desc': 'delivery truck',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F69B', {
        'desc': 'articulated lorry',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F69C', {
        'desc': 'tractor',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B2', {
        'desc': 'bicycle',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F4', {
        'desc': 'kick scooter',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F9', {
        'desc': 'skateboard',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F5', {
        'desc': 'motor scooter',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F68F', {
        'desc': 'bus stop',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6E3\U0000FE0F', {
        'desc': 'motorway',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True
    }),
    ('\U0001F6E3', {
        'desc': 'motorway',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6E4\U0000FE0F', {
        'desc': 'railway track',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True
    }),
    ('\U0001F6E4', {
        'desc': 'railway track',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6E2\U0000FE0F', {
        'desc': 'oil drum',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True
    }),
    ('\U0001F6E2', {
        'desc': 'oil drum',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000026FD', {
        'desc': 'fuel pump',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A8', {
        'desc': 'police car light',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A5', {
        'desc': 'horizontal traffic light',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A6', {
        'desc': 'vertical traffic light',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6D1', {
        'desc': 'stop sign',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A7', {
        'desc': 'construction',
        'group': 'Travel & Places',
        'subgroup': 'transport-ground',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002693', {
        'desc': 'anchor',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F5', {
        'desc': 'sailboat',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F6', {
        'desc': 'canoe',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A4', {
        'desc': 'speedboat',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F3\U0000FE0F', {
        'desc': 'passenger ship',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True
    }),
    ('\U0001F6F3', {
        'desc': 'passenger ship',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F4\U0000FE0F', {
        'desc': 'ferry',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True
    }),
    ('\U000026F4', {
        'desc': 'ferry',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6E5\U0000FE0F', {
        'desc': 'motor boat',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True
    }),
    ('\U0001F6E5', {
        'desc': 'motor boat',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A2', {
        'desc': 'ship',
        'group': 'Travel & Places',
        'subgroup': 'transport-water',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002708\U0000FE0F', {
        'desc': 'airplane',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True
    }),
    ('\U00002708', {
        'desc': 'airplane',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6E9\U0000FE0F', {
        'desc': 'small airplane',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True
    }),
    ('\U0001F6E9', {
        'desc': 'small airplane',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6EB', {
        'desc': 'airplane departure',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6EC', {
        'desc': 'airplane arrival',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4BA', {
        'desc': 'seat',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F681', {
        'desc': 'helicopter',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F69F', {
        'desc': 'suspension railway',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A0', {
        'desc': 'mountain cableway',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A1', {
        'desc': 'aerial tramway',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F0\U0000FE0F', {
        'desc': 'satellite',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True
    }),
    ('\U0001F6F0', {
        'desc': 'satellite',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F680', {
        'desc': 'rocket',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F8', {
        'desc': 'flying saucer',
        'group': 'Travel & Places',
        'subgroup': 'transport-air',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6CE\U0000FE0F', {
        'desc': 'bellhop bell',
        'group': 'Travel & Places',
        'subgroup': 'hotel',
        'fully-qualified': True
    }),
    ('\U0001F6CE', {
        'desc': 'bellhop bell',
        'group': 'Travel & Places',
        'subgroup': 'hotel',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F3', {
        'desc': 'luggage',
        'group': 'Travel & Places',
        'subgroup': 'hotel',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000231B', {
        'desc': 'hourglass done',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023F3', {
        'desc': 'hourglass not done',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000231A', {
        'desc': 'watch',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023F0', {
        'desc': 'alarm clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023F1\U0000FE0F', {
        'desc': 'stopwatch',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True
    }),
    ('\U000023F1', {
        'desc': 'stopwatch',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000023F2\U0000FE0F', {
        'desc': 'timer clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True
    }),
    ('\U000023F2', {
        'desc': 'timer clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F570\U0000FE0F', {
        'desc': 'mantelpiece clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True
    }),
    ('\U0001F570', {
        'desc': 'mantelpiece clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F55B', {
        'desc': 'twelve o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F567', {
        'desc': 'twelve-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F550', {
        'desc': 'one o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F55C', {
        'desc': 'one-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F551', {
        'desc': 'two o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F55D', {
        'desc': 'two-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F552', {
        'desc': 'three o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F55E', {
        'desc': 'three-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F553', {
        'desc': 'four o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F55F', {
        'desc': 'four-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F554', {
        'desc': 'five o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F560', {
        'desc': 'five-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F555', {
        'desc': 'six o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F561', {
        'desc': 'six-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F556', {
        'desc': 'seven o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F562', {
        'desc': 'seven-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F557', {
        'desc': 'eight o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F563', {
        'desc': 'eight-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F558', {
        'desc': 'nine o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F564', {
        'desc': 'nine-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F559', {
        'desc': 'ten o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F565', {
        'desc': 'ten-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F55A', {
        'desc': 'eleven o’clock',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F566', {
        'desc': 'eleven-thirty',
        'group': 'Travel & Places',
        'subgroup': 'time',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F311', {
        'desc': 'new moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F312', {
        'desc': 'waxing crescent moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F313', {
        'desc': 'first quarter moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F314', {
        'desc': 'waxing gibbous moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F315', {
        'desc': 'full moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F316', {
        'desc': 'waning gibbous moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F317', {
        'desc': 'last quarter moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F318', {
        'desc': 'waning crescent moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F319', {
        'desc': 'crescent moon',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F31A', {
        'desc': 'new moon face',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F31B', {
        'desc': 'first quarter moon face',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F31C', {
        'desc': 'last quarter moon face',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F321\U0000FE0F', {
        'desc': 'thermometer',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F321', {
        'desc': 'thermometer',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002600\U0000FE0F', {
        'desc': 'sun',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U00002600', {
        'desc': 'sun',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F31D', {
        'desc': 'full moon face',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F31E', {
        'desc': 'sun with face',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002B50', {
        'desc': 'star',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F31F', {
        'desc': 'glowing star',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F320', {
        'desc': 'shooting star',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002601\U0000FE0F', {
        'desc': 'cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U00002601', {
        'desc': 'cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000026C5', {
        'desc': 'sun behind cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026C8\U0000FE0F', {
        'desc': 'cloud with lightning and rain',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U000026C8', {
        'desc': 'cloud with lightning and rain',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F324\U0000FE0F', {
        'desc': 'sun behind small cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F324', {
        'desc': 'sun behind small cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F325\U0000FE0F', {
        'desc': 'sun behind large cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F325', {
        'desc': 'sun behind large cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F326\U0000FE0F', {
        'desc': 'sun behind rain cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F326', {
        'desc': 'sun behind rain cloud',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F327\U0000FE0F', {
        'desc': 'cloud with rain',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F327', {
        'desc': 'cloud with rain',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F328\U0000FE0F', {
        'desc': 'cloud with snow',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F328', {
        'desc': 'cloud with snow',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F329\U0000FE0F', {
        'desc': 'cloud with lightning',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F329', {
        'desc': 'cloud with lightning',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F32A\U0000FE0F', {
        'desc': 'tornado',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F32A', {
        'desc': 'tornado',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F32B\U0000FE0F', {
        'desc': 'fog',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F32B', {
        'desc': 'fog',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F32C\U0000FE0F', {
        'desc': 'wind face',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U0001F32C', {
        'desc': 'wind face',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F300', {
        'desc': 'cyclone',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F308', {
        'desc': 'rainbow',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F302', {
        'desc': 'closed umbrella',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002602\U0000FE0F', {
        'desc': 'umbrella',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U00002602', {
        'desc': 'umbrella',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002614', {
        'desc': 'umbrella with rain drops',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F1\U0000FE0F', {
        'desc': 'umbrella on ground',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U000026F1', {
        'desc': 'umbrella on ground',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000026A1', {
        'desc': 'high voltage',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002744\U0000FE0F', {
        'desc': 'snowflake',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U00002744', {
        'desc': 'snowflake',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002603\U0000FE0F', {
        'desc': 'snowman',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U00002603', {
        'desc': 'snowman',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000026C4', {
        'desc': 'snowman without snow',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002604\U0000FE0F', {
        'desc': 'comet',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True
    }),
    ('\U00002604', {
        'desc': 'comet',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F525', {
        'desc': 'fire',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A7', {
        'desc': 'droplet',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F30A', {
        'desc': 'water wave',
        'group': 'Travel & Places',
        'subgroup': 'sky & weather',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F383', {
        'desc': 'jack-o-lantern',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F384', {
        'desc': 'Christmas tree',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F386', {
        'desc': 'fireworks',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F387', {
        'desc': 'sparkler',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E8', {
        'desc': 'firecracker',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002728', {
        'desc': 'sparkles',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F388', {
        'desc': 'balloon',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F389', {
        'desc': 'party popper',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F38A', {
        'desc': 'confetti ball',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F38B', {
        'desc': 'tanabata tree',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F38D', {
        'desc': 'pine decoration',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F38E', {
        'desc': 'Japanese dolls',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F38F', {
        'desc': 'carp streamer',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F390', {
        'desc': 'wind chime',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F391', {
        'desc': 'moon viewing ceremony',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E7', {
        'desc': 'red envelope',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F380', {
        'desc': 'ribbon',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F381', {
        'desc': 'wrapped gift',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F397\U0000FE0F', {
        'desc': 'reminder ribbon',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True
    }),
    ('\U0001F397', {
        'desc': 'reminder ribbon',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F39F\U0000FE0F', {
        'desc': 'admission tickets',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True
    }),
    ('\U0001F39F', {
        'desc': 'admission tickets',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3AB', {
        'desc': 'ticket',
        'group': 'Activities',
        'subgroup': 'event',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F396\U0000FE0F', {
        'desc': 'military medal',
        'group': 'Activities',
        'subgroup': 'award-medal',
        'fully-qualified': True
    }),
    ('\U0001F396', {
        'desc': 'military medal',
        'group': 'Activities',
        'subgroup': 'award-medal',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C6', {
        'desc': 'trophy',
        'group': 'Activities',
        'subgroup': 'award-medal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C5', {
        'desc': 'sports medal',
        'group': 'Activities',
        'subgroup': 'award-medal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F947', {
        'desc': '1st place medal',
        'group': 'Activities',
        'subgroup': 'award-medal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F948', {
        'desc': '2nd place medal',
        'group': 'Activities',
        'subgroup': 'award-medal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F949', {
        'desc': '3rd place medal',
        'group': 'Activities',
        'subgroup': 'award-medal',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026BD', {
        'desc': 'soccer ball',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026BE', {
        'desc': 'baseball',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F94E', {
        'desc': 'softball',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C0', {
        'desc': 'basketball',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D0', {
        'desc': 'volleyball',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C8', {
        'desc': 'american football',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C9', {
        'desc': 'rugby football',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3BE', {
        'desc': 'tennis',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F94F', {
        'desc': 'flying disc',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B3', {
        'desc': 'bowling',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3CF', {
        'desc': 'cricket game',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D1', {
        'desc': 'field hockey',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D2', {
        'desc': 'ice hockey',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F94D', {
        'desc': 'lacrosse',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3D3', {
        'desc': 'ping pong',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F8', {
        'desc': 'badminton',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F94A', {
        'desc': 'boxing glove',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F94B', {
        'desc': 'martial arts uniform',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F945', {
        'desc': 'goal net',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F3', {
        'desc': 'flag in hole',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026F8\U0000FE0F', {
        'desc': 'ice skate',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True
    }),
    ('\U000026F8', {
        'desc': 'ice skate',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A3', {
        'desc': 'fishing pole',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3BD', {
        'desc': 'running shirt',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3BF', {
        'desc': 'skis',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6F7', {
        'desc': 'sled',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F94C', {
        'desc': 'curling stone',
        'group': 'Activities',
        'subgroup': 'sport',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3AF', {
        'desc': 'direct hit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B1', {
        'desc': 'pool 8 ball',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F52E', {
        'desc': 'crystal ball',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9FF', {
        'desc': 'nazar amulet',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3AE', {
        'desc': 'video game',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F579\U0000FE0F', {
        'desc': 'joystick',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True
    }),
    ('\U0001F579', {
        'desc': 'joystick',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B0', {
        'desc': 'slot machine',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B2', {
        'desc': 'game die',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9E9', {
        'desc': 'jigsaw',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F8', {
        'desc': 'teddy bear',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002660\U0000FE0F', {
        'desc': 'spade suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True
    }),
    ('\U00002660', {
        'desc': 'spade suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002665\U0000FE0F', {
        'desc': 'heart suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True
    }),
    ('\U00002665', {
        'desc': 'heart suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002666\U0000FE0F', {
        'desc': 'diamond suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True
    }),
    ('\U00002666', {
        'desc': 'diamond suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002663\U0000FE0F', {
        'desc': 'club suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True
    }),
    ('\U00002663', {
        'desc': 'club suit',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000265F\U0000FE0F', {
        'desc': 'chess pawn',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True
    }),
    ('\U0000265F', {
        'desc': 'chess pawn',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F0CF', {
        'desc': 'joker',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F004', {
        'desc': 'mahjong red dragon',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B4', {
        'desc': 'flower playing cards',
        'group': 'Activities',
        'subgroup': 'game',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3AD', {
        'desc': 'performing arts',
        'group': 'Activities',
        'subgroup': 'arts & crafts',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5BC\U0000FE0F', {
        'desc': 'framed picture',
        'group': 'Activities',
        'subgroup': 'arts & crafts',
        'fully-qualified': True
    }),
    ('\U0001F5BC', {
        'desc': 'framed picture',
        'group': 'Activities',
        'subgroup': 'arts & crafts',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A8', {
        'desc': 'artist palette',
        'group': 'Activities',
        'subgroup': 'arts & crafts',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F5', {
        'desc': 'thread',
        'group': 'Activities',
        'subgroup': 'arts & crafts',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F6', {
        'desc': 'yarn',
        'group': 'Activities',
        'subgroup': 'arts & crafts',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F507', {
        'desc': 'muted speaker',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F508', {
        'desc': 'speaker low volume',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F509', {
        'desc': 'speaker medium volume',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F50A', {
        'desc': 'speaker high volume',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E2', {
        'desc': 'loudspeaker',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E3', {
        'desc': 'megaphone',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4EF', {
        'desc': 'postal horn',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F514', {
        'desc': 'bell',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F515', {
        'desc': 'bell with slash',
        'group': 'Objects',
        'subgroup': 'sound',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3BC', {
        'desc': 'musical score',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B5', {
        'desc': 'musical note',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B6', {
        'desc': 'musical notes',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F399\U0000FE0F', {
        'desc': 'studio microphone',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True
    }),
    ('\U0001F399', {
        'desc': 'studio microphone',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F39A\U0000FE0F', {
        'desc': 'level slider',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True
    }),
    ('\U0001F39A', {
        'desc': 'level slider',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F39B\U0000FE0F', {
        'desc': 'control knobs',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True
    }),
    ('\U0001F39B', {
        'desc': 'control knobs',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A4', {
        'desc': 'microphone',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A7', {
        'desc': 'headphone',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4FB', {
        'desc': 'radio',
        'group': 'Objects',
        'subgroup': 'music',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B7', {
        'desc': 'saxophone',
        'group': 'Objects',
        'subgroup': 'musical-instrument',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B8', {
        'desc': 'guitar',
        'group': 'Objects',
        'subgroup': 'musical-instrument',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3B9', {
        'desc': 'musical keyboard',
        'group': 'Objects',
        'subgroup': 'musical-instrument',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3BA', {
        'desc': 'trumpet',
        'group': 'Objects',
        'subgroup': 'musical-instrument',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3BB', {
        'desc': 'violin',
        'group': 'Objects',
        'subgroup': 'musical-instrument',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F941', {
        'desc': 'drum',
        'group': 'Objects',
        'subgroup': 'musical-instrument',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F1', {
        'desc': 'mobile phone',
        'group': 'Objects',
        'subgroup': 'phone',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F2', {
        'desc': 'mobile phone with arrow',
        'group': 'Objects',
        'subgroup': 'phone',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000260E\U0000FE0F', {
        'desc': 'telephone',
        'group': 'Objects',
        'subgroup': 'phone',
        'fully-qualified': True
    }),
    ('\U0000260E', {
        'desc': 'telephone',
        'group': 'Objects',
        'subgroup': 'phone',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4DE', {
        'desc': 'telephone receiver',
        'group': 'Objects',
        'subgroup': 'phone',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4DF', {
        'desc': 'pager',
        'group': 'Objects',
        'subgroup': 'phone',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E0', {
        'desc': 'fax machine',
        'group': 'Objects',
        'subgroup': 'phone',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F50B', {
        'desc': 'battery',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F50C', {
        'desc': 'electric plug',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4BB', {
        'desc': 'laptop computer',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5A5\U0000FE0F', {
        'desc': 'desktop computer',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True
    }),
    ('\U0001F5A5', {
        'desc': 'desktop computer',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5A8\U0000FE0F', {
        'desc': 'printer',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True
    }),
    ('\U0001F5A8', {
        'desc': 'printer',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002328\U0000FE0F', {
        'desc': 'keyboard',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True
    }),
    ('\U00002328', {
        'desc': 'keyboard',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5B1\U0000FE0F', {
        'desc': 'computer mouse',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True
    }),
    ('\U0001F5B1', {
        'desc': 'computer mouse',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5B2\U0000FE0F', {
        'desc': 'trackball',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True
    }),
    ('\U0001F5B2', {
        'desc': 'trackball',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4BD', {
        'desc': 'computer disk',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4BE', {
        'desc': 'floppy disk',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4BF', {
        'desc': 'optical disk',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C0', {
        'desc': 'dvd',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9EE', {
        'desc': 'abacus',
        'group': 'Objects',
        'subgroup': 'computer',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A5', {
        'desc': 'movie camera',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F39E\U0000FE0F', {
        'desc': 'film frames',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True
    }),
    ('\U0001F39E', {
        'desc': 'film frames',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4FD\U0000FE0F', {
        'desc': 'film projector',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True
    }),
    ('\U0001F4FD', {
        'desc': 'film projector',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3AC', {
        'desc': 'clapper board',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4FA', {
        'desc': 'television',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F7', {
        'desc': 'camera',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F8', {
        'desc': 'camera with flash',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F9', {
        'desc': 'video camera',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4FC', {
        'desc': 'videocassette',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F50D', {
        'desc': 'magnifying glass tilted left',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F50E', {
        'desc': 'magnifying glass tilted right',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F56F\U0000FE0F', {
        'desc': 'candle',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True
    }),
    ('\U0001F56F', {
        'desc': 'candle',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A1', {
        'desc': 'light bulb',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F526', {
        'desc': 'flashlight',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3EE', {
        'desc': 'red paper lantern',
        'group': 'Objects',
        'subgroup': 'light & video',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D4', {
        'desc': 'notebook with decorative cover',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D5', {
        'desc': 'closed book',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D6', {
        'desc': 'open book',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D7', {
        'desc': 'green book',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D8', {
        'desc': 'blue book',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D9', {
        'desc': 'orange book',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4DA', {
        'desc': 'books',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D3', {
        'desc': 'notebook',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D2', {
        'desc': 'ledger',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C3', {
        'desc': 'page with curl',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4DC', {
        'desc': 'scroll',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C4', {
        'desc': 'page facing up',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F0', {
        'desc': 'newspaper',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5DE\U0000FE0F', {
        'desc': 'rolled-up newspaper',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True
    }),
    ('\U0001F5DE', {
        'desc': 'rolled-up newspaper',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D1', {
        'desc': 'bookmark tabs',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F516', {
        'desc': 'bookmark',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F7\U0000FE0F', {
        'desc': 'label',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': True
    }),
    ('\U0001F3F7', {
        'desc': 'label',
        'group': 'Objects',
        'subgroup': 'book-paper',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B0', {
        'desc': 'money bag',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B4', {
        'desc': 'yen banknote',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B5', {
        'desc': 'dollar banknote',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B6', {
        'desc': 'euro banknote',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B7', {
        'desc': 'pound banknote',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B8', {
        'desc': 'money with wings',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B3', {
        'desc': 'credit card',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9FE', {
        'desc': 'receipt',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B9', {
        'desc': 'chart increasing with yen',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B1', {
        'desc': 'currency exchange',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4B2', {
        'desc': 'heavy dollar sign',
        'group': 'Objects',
        'subgroup': 'money',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002709\U0000FE0F', {
        'desc': 'envelope',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True
    }),
    ('\U00002709', {
        'desc': 'envelope',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E7', {
        'desc': 'e-mail',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E8', {
        'desc': 'incoming envelope',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E9', {
        'desc': 'envelope with arrow',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E4', {
        'desc': 'outbox tray',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E5', {
        'desc': 'inbox tray',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E6', {
        'desc': 'package',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4EB', {
        'desc': 'closed mailbox with raised flag',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4EA', {
        'desc': 'closed mailbox with lowered flag',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4EC', {
        'desc': 'open mailbox with raised flag',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4ED', {
        'desc': 'open mailbox with lowered flag',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4EE', {
        'desc': 'postbox',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5F3\U0000FE0F', {
        'desc': 'ballot box with ballot',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': True
    }),
    ('\U0001F5F3', {
        'desc': 'ballot box with ballot',
        'group': 'Objects',
        'subgroup': 'mail',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000270F\U0000FE0F', {
        'desc': 'pencil',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': True
    }),
    ('\U0000270F', {
        'desc': 'pencil',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002712\U0000FE0F', {
        'desc': 'black nib',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': True
    }),
    ('\U00002712', {
        'desc': 'black nib',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F58B\U0000FE0F', {
        'desc': 'fountain pen',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': True
    }),
    ('\U0001F58B', {
        'desc': 'fountain pen',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F58A\U0000FE0F', {
        'desc': 'pen',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': True
    }),
    ('\U0001F58A', {
        'desc': 'pen',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F58C\U0000FE0F', {
        'desc': 'paintbrush',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': True
    }),
    ('\U0001F58C', {
        'desc': 'paintbrush',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F58D\U0000FE0F', {
        'desc': 'crayon',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': True
    }),
    ('\U0001F58D', {
        'desc': 'crayon',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4DD', {
        'desc': 'memo',
        'group': 'Objects',
        'subgroup': 'writing',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4BC', {
        'desc': 'briefcase',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C1', {
        'desc': 'file folder',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C2', {
        'desc': 'open file folder',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5C2\U0000FE0F', {
        'desc': 'card index dividers',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U0001F5C2', {
        'desc': 'card index dividers',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C5', {
        'desc': 'calendar',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C6', {
        'desc': 'tear-off calendar',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5D2\U0000FE0F', {
        'desc': 'spiral notepad',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U0001F5D2', {
        'desc': 'spiral notepad',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5D3\U0000FE0F', {
        'desc': 'spiral calendar',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U0001F5D3', {
        'desc': 'spiral calendar',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C7', {
        'desc': 'card index',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C8', {
        'desc': 'chart increasing',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4C9', {
        'desc': 'chart decreasing',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4CA', {
        'desc': 'bar chart',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4CB', {
        'desc': 'clipboard',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4CC', {
        'desc': 'pushpin',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4CD', {
        'desc': 'round pushpin',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4CE', {
        'desc': 'paperclip',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F587\U0000FE0F', {
        'desc': 'linked paperclips',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U0001F587', {
        'desc': 'linked paperclips',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4CF', {
        'desc': 'straight ruler',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4D0', {
        'desc': 'triangular ruler',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002702\U0000FE0F', {
        'desc': 'scissors',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U00002702', {
        'desc': 'scissors',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5C3\U0000FE0F', {
        'desc': 'card file box',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U0001F5C3', {
        'desc': 'card file box',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5C4\U0000FE0F', {
        'desc': 'file cabinet',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U0001F5C4', {
        'desc': 'file cabinet',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5D1\U0000FE0F', {
        'desc': 'wastebasket',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': True
    }),
    ('\U0001F5D1', {
        'desc': 'wastebasket',
        'group': 'Objects',
        'subgroup': 'office',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F512', {
        'desc': 'locked',
        'group': 'Objects',
        'subgroup': 'lock',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F513', {
        'desc': 'unlocked',
        'group': 'Objects',
        'subgroup': 'lock',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F50F', {
        'desc': 'locked with pen',
        'group': 'Objects',
        'subgroup': 'lock',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F510', {
        'desc': 'locked with key',
        'group': 'Objects',
        'subgroup': 'lock',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F511', {
        'desc': 'key',
        'group': 'Objects',
        'subgroup': 'lock',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5DD\U0000FE0F', {
        'desc': 'old key',
        'group': 'Objects',
        'subgroup': 'lock',
        'fully-qualified': True
    }),
    ('\U0001F5DD', {
        'desc': 'old key',
        'group': 'Objects',
        'subgroup': 'lock',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F528', {
        'desc': 'hammer',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026CF\U0000FE0F', {
        'desc': 'pick',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U000026CF', {
        'desc': 'pick',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002692\U0000FE0F', {
        'desc': 'hammer and pick',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U00002692', {
        'desc': 'hammer and pick',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6E0\U0000FE0F', {
        'desc': 'hammer and wrench',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U0001F6E0', {
        'desc': 'hammer and wrench',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5E1\U0000FE0F', {
        'desc': 'dagger',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U0001F5E1', {
        'desc': 'dagger',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002694\U0000FE0F', {
        'desc': 'crossed swords',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U00002694', {
        'desc': 'crossed swords',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F52B', {
        'desc': 'pistol',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F9', {
        'desc': 'bow and arrow',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6E1\U0000FE0F', {
        'desc': 'shield',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U0001F6E1', {
        'desc': 'shield',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F527', {
        'desc': 'wrench',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F529', {
        'desc': 'nut and bolt',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002699\U0000FE0F', {
        'desc': 'gear',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U00002699', {
        'desc': 'gear',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5DC\U0000FE0F', {
        'desc': 'clamp',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U0001F5DC', {
        'desc': 'clamp',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002696\U0000FE0F', {
        'desc': 'balance scale',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U00002696', {
        'desc': 'balance scale',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F517', {
        'desc': 'link',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026D3\U0000FE0F', {
        'desc': 'chains',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True
    }),
    ('\U000026D3', {
        'desc': 'chains',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F0', {
        'desc': 'toolbox',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F2', {
        'desc': 'magnet',
        'group': 'Objects',
        'subgroup': 'tool',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002697\U0000FE0F', {
        'desc': 'alembic',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': True
    }),
    ('\U00002697', {
        'desc': 'alembic',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9EA', {
        'desc': 'test tube',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9EB', {
        'desc': 'petri dish',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9EC', {
        'desc': 'dna',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F52C', {
        'desc': 'microscope',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F52D', {
        'desc': 'telescope',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4E1', {
        'desc': 'satellite antenna',
        'group': 'Objects',
        'subgroup': 'science',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F489', {
        'desc': 'syringe',
        'group': 'Objects',
        'subgroup': 'medical',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F48A', {
        'desc': 'pill',
        'group': 'Objects',
        'subgroup': 'medical',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6AA', {
        'desc': 'door',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6CF\U0000FE0F', {
        'desc': 'bed',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True
    }),
    ('\U0001F6CF', {
        'desc': 'bed',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6CB\U0000FE0F', {
        'desc': 'couch and lamp',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True
    }),
    ('\U0001F6CB', {
        'desc': 'couch and lamp',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6BD', {
        'desc': 'toilet',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6BF', {
        'desc': 'shower',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6C1', {
        'desc': 'bathtub',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F4', {
        'desc': 'lotion bottle',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F7', {
        'desc': 'safety pin',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9F9', {
        'desc': 'broom',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9FA', {
        'desc': 'basket',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9FB', {
        'desc': 'roll of paper',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9FC', {
        'desc': 'soap',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9FD', {
        'desc': 'sponge',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F9EF', {
        'desc': 'fire extinguisher',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6D2', {
        'desc': 'shopping cart',
        'group': 'Objects',
        'subgroup': 'household',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6AC', {
        'desc': 'cigarette',
        'group': 'Objects',
        'subgroup': 'other-object',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026B0\U0000FE0F', {
        'desc': 'coffin',
        'group': 'Objects',
        'subgroup': 'other-object',
        'fully-qualified': True
    }),
    ('\U000026B0', {
        'desc': 'coffin',
        'group': 'Objects',
        'subgroup': 'other-object',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000026B1\U0000FE0F', {
        'desc': 'funeral urn',
        'group': 'Objects',
        'subgroup': 'other-object',
        'fully-qualified': True
    }),
    ('\U000026B1', {
        'desc': 'funeral urn',
        'group': 'Objects',
        'subgroup': 'other-object',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F5FF', {
        'desc': 'moai',
        'group': 'Objects',
        'subgroup': 'other-object',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3E7', {
        'desc': 'ATM sign',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6AE', {
        'desc': 'litter in bin sign',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B0', {
        'desc': 'potable water',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000267F', {
        'desc': 'wheelchair symbol',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B9', {
        'desc': 'men’s room',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6BA', {
        'desc': 'women’s room',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6BB', {
        'desc': 'restroom',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6BC', {
        'desc': 'baby symbol',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6BE', {
        'desc': 'water closet',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6C2', {
        'desc': 'passport control',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6C3', {
        'desc': 'customs',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6C4', {
        'desc': 'baggage claim',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6C5', {
        'desc': 'left luggage',
        'group': 'Symbols',
        'subgroup': 'transport-sign',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026A0\U0000FE0F', {
        'desc': 'warning',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True
    }),
    ('\U000026A0', {
        'desc': 'warning',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B8', {
        'desc': 'children crossing',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026D4', {
        'desc': 'no entry',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6AB', {
        'desc': 'prohibited',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B3', {
        'desc': 'no bicycles',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6AD', {
        'desc': 'no smoking',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6AF', {
        'desc': 'no littering',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B1', {
        'desc': 'non-potable water',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6B7', {
        'desc': 'no pedestrians',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F5', {
        'desc': 'no mobile phones',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F51E', {
        'desc': 'no one under eighteen',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002622\U0000FE0F', {
        'desc': 'radioactive',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True
    }),
    ('\U00002622', {
        'desc': 'radioactive',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002623\U0000FE0F', {
        'desc': 'biohazard',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': True
    }),
    ('\U00002623', {
        'desc': 'biohazard',
        'group': 'Symbols',
        'subgroup': 'warning',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002B06\U0000FE0F', {
        'desc': 'up arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002B06', {
        'desc': 'up arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002197\U0000FE0F', {
        'desc': 'up-right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002197', {
        'desc': 'up-right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000027A1\U0000FE0F', {
        'desc': 'right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U000027A1', {
        'desc': 'right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002198\U0000FE0F', {
        'desc': 'down-right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002198', {
        'desc': 'down-right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002B07\U0000FE0F', {
        'desc': 'down arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002B07', {
        'desc': 'down arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002199\U0000FE0F', {
        'desc': 'down-left arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002199', {
        'desc': 'down-left arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002B05\U0000FE0F', {
        'desc': 'left arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002B05', {
        'desc': 'left arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002196\U0000FE0F', {
        'desc': 'up-left arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002196', {
        'desc': 'up-left arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002195\U0000FE0F', {
        'desc': 'up-down arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002195', {
        'desc': 'up-down arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002194\U0000FE0F', {
        'desc': 'left-right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002194', {
        'desc': 'left-right arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000021A9\U0000FE0F', {
        'desc': 'right arrow curving left',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U000021A9', {
        'desc': 'right arrow curving left',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000021AA\U0000FE0F', {
        'desc': 'left arrow curving right',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U000021AA', {
        'desc': 'left arrow curving right',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002934\U0000FE0F', {
        'desc': 'right arrow curving up',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002934', {
        'desc': 'right arrow curving up',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002935\U0000FE0F', {
        'desc': 'right arrow curving down',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True
    }),
    ('\U00002935', {
        'desc': 'right arrow curving down',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F503', {
        'desc': 'clockwise vertical arrows',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F504', {
        'desc': 'counterclockwise arrows button',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F519', {
        'desc': 'BACK arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F51A', {
        'desc': 'END arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F51B', {
        'desc': 'ON! arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F51C', {
        'desc': 'SOON arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F51D', {
        'desc': 'TOP arrow',
        'group': 'Symbols',
        'subgroup': 'arrow',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6D0', {
        'desc': 'place of worship',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000269B\U0000FE0F', {
        'desc': 'atom symbol',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U0000269B', {
        'desc': 'atom symbol',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F549\U0000FE0F', {
        'desc': 'om',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U0001F549', {
        'desc': 'om',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002721\U0000FE0F', {
        'desc': 'star of David',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U00002721', {
        'desc': 'star of David',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002638\U0000FE0F', {
        'desc': 'wheel of dharma',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U00002638', {
        'desc': 'wheel of dharma',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000262F\U0000FE0F', {
        'desc': 'yin yang',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U0000262F', {
        'desc': 'yin yang',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000271D\U0000FE0F', {
        'desc': 'latin cross',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U0000271D', {
        'desc': 'latin cross',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002626\U0000FE0F', {
        'desc': 'orthodox cross',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U00002626', {
        'desc': 'orthodox cross',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000262A\U0000FE0F', {
        'desc': 'star and crescent',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U0000262A', {
        'desc': 'star and crescent',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000262E\U0000FE0F', {
        'desc': 'peace symbol',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True
    }),
    ('\U0000262E', {
        'desc': 'peace symbol',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F54E', {
        'desc': 'menorah',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F52F', {
        'desc': 'dotted six-pointed star',
        'group': 'Symbols',
        'subgroup': 'religion',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002648', {
        'desc': 'Aries',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002649', {
        'desc': 'Taurus',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000264A', {
        'desc': 'Gemini',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000264B', {
        'desc': 'Cancer',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000264C', {
        'desc': 'Leo',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000264D', {
        'desc': 'Virgo',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000264E', {
        'desc': 'Libra',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000264F', {
        'desc': 'Scorpio',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002650', {
        'desc': 'Sagittarius',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002651', {
        'desc': 'Capricorn',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002652', {
        'desc': 'Aquarius',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002653', {
        'desc': 'Pisces',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026CE', {
        'desc': 'Ophiuchus',
        'group': 'Symbols',
        'subgroup': 'zodiac',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F500', {
        'desc': 'shuffle tracks button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F501', {
        'desc': 'repeat button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F502', {
        'desc': 'repeat single button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000025B6\U0000FE0F', {
        'desc': 'play button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000025B6', {
        'desc': 'play button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000023E9', {
        'desc': 'fast-forward button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023ED\U0000FE0F', {
        'desc': 'next track button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000023ED', {
        'desc': 'next track button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000023EF\U0000FE0F', {
        'desc': 'play or pause button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000023EF', {
        'desc': 'play or pause button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000025C0\U0000FE0F', {
        'desc': 'reverse button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000025C0', {
        'desc': 'reverse button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000023EA', {
        'desc': 'fast reverse button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023EE\U0000FE0F', {
        'desc': 'last track button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000023EE', {
        'desc': 'last track button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F53C', {
        'desc': 'upwards button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023EB', {
        'desc': 'fast up button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F53D', {
        'desc': 'downwards button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023EC', {
        'desc': 'fast down button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000023F8\U0000FE0F', {
        'desc': 'pause button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000023F8', {
        'desc': 'pause button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000023F9\U0000FE0F', {
        'desc': 'stop button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000023F9', {
        'desc': 'stop button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000023FA\U0000FE0F', {
        'desc': 'record button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000023FA', {
        'desc': 'record button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000023CF\U0000FE0F', {
        'desc': 'eject button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True
    }),
    ('\U000023CF', {
        'desc': 'eject button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3A6', {
        'desc': 'cinema',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F505', {
        'desc': 'dim button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F506', {
        'desc': 'bright button',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F6', {
        'desc': 'antenna bars',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F3', {
        'desc': 'vibration mode',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4F4', {
        'desc': 'mobile phone off',
        'group': 'Symbols',
        'subgroup': 'av-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002640\U0000FE0F', {
        'desc': 'female sign',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002640', {
        'desc': 'female sign',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002642\U0000FE0F', {
        'desc': 'male sign',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002642', {
        'desc': 'male sign',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002695\U0000FE0F', {
        'desc': 'medical symbol',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002695', {
        'desc': 'medical symbol',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000267E\U0000FE0F', {
        'desc': 'infinity',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U0000267E', {
        'desc': 'infinity',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000267B\U0000FE0F', {
        'desc': 'recycling symbol',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U0000267B', {
        'desc': 'recycling symbol',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000269C\U0000FE0F', {
        'desc': 'fleur-de-lis',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U0000269C', {
        'desc': 'fleur-de-lis',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F531', {
        'desc': 'trident emblem',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4DB', {
        'desc': 'name badge',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F530', {
        'desc': 'Japanese symbol for beginner',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002B55', {
        'desc': 'heavy large circle',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002705', {
        'desc': 'white heavy check mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002611\U0000FE0F', {
        'desc': 'ballot box with check',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002611', {
        'desc': 'ballot box with check',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002714\U0000FE0F', {
        'desc': 'heavy check mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002714', {
        'desc': 'heavy check mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002716\U0000FE0F', {
        'desc': 'heavy multiplication x',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002716', {
        'desc': 'heavy multiplication x',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000274C', {
        'desc': 'cross mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000274E', {
        'desc': 'cross mark button',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002795', {
        'desc': 'heavy plus sign',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002796', {
        'desc': 'heavy minus sign',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002797', {
        'desc': 'heavy division sign',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000027B0', {
        'desc': 'curly loop',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000027BF', {
        'desc': 'double curly loop',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0000303D\U0000FE0F', {
        'desc': 'part alternation mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U0000303D', {
        'desc': 'part alternation mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002733\U0000FE0F', {
        'desc': 'eight-spoked asterisk',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002733', {
        'desc': 'eight-spoked asterisk',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002734\U0000FE0F', {
        'desc': 'eight-pointed star',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002734', {
        'desc': 'eight-pointed star',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002747\U0000FE0F', {
        'desc': 'sparkle',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002747', {
        'desc': 'sparkle',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0000203C\U0000FE0F', {
        'desc': 'double exclamation mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U0000203C', {
        'desc': 'double exclamation mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002049\U0000FE0F', {
        'desc': 'exclamation question mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002049', {
        'desc': 'exclamation question mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002753', {
        'desc': 'question mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002754', {
        'desc': 'white question mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002755', {
        'desc': 'white exclamation mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002757', {
        'desc': 'exclamation mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00003030\U0000FE0F', {
        'desc': 'wavy dash',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00003030', {
        'desc': 'wavy dash',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000000A9\U0000FE0F', {
        'desc': 'copyright',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U000000A9', {
        'desc': 'copyright',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000000AE\U0000FE0F', {
        'desc': 'registered',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U000000AE', {
        'desc': 'registered',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00002122\U0000FE0F', {
        'desc': 'trade mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': True
    }),
    ('\U00002122', {
        'desc': 'trade mark',
        'group': 'Symbols',
        'subgroup': 'other-symbol',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00000023\U0000FE0F\U000020E3', {
        'desc': 'keycap: #',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000023\U000020E3', {
        'desc': 'keycap: #',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U0000002A\U0000FE0F\U000020E3', {
        'desc': 'keycap: *',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U0000002A\U000020E3', {
        'desc': 'keycap: *',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000030\U0000FE0F\U000020E3', {
        'desc': 'keycap: 0',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000030\U000020E3', {
        'desc': 'keycap: 0',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000031\U0000FE0F\U000020E3', {
        'desc': 'keycap: 1',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000031\U000020E3', {
        'desc': 'keycap: 1',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000032\U0000FE0F\U000020E3', {
        'desc': 'keycap: 2',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000032\U000020E3', {
        'desc': 'keycap: 2',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000033\U0000FE0F\U000020E3', {
        'desc': 'keycap: 3',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000033\U000020E3', {
        'desc': 'keycap: 3',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000034\U0000FE0F\U000020E3', {
        'desc': 'keycap: 4',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000034\U000020E3', {
        'desc': 'keycap: 4',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000035\U0000FE0F\U000020E3', {
        'desc': 'keycap: 5',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000035\U000020E3', {
        'desc': 'keycap: 5',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000036\U0000FE0F\U000020E3', {
        'desc': 'keycap: 6',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000036\U000020E3', {
        'desc': 'keycap: 6',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000037\U0000FE0F\U000020E3', {
        'desc': 'keycap: 7',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000037\U000020E3', {
        'desc': 'keycap: 7',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000038\U0000FE0F\U000020E3', {
        'desc': 'keycap: 8',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000038\U000020E3', {
        'desc': 'keycap: 8',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000039\U0000FE0F\U000020E3', {
        'desc': 'keycap: 9',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U00000039\U000020E3', {
        'desc': 'keycap: 9',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': False,
        'Emoji_Keycap_Sequence': True
    }),
    ('\U0001F51F', {
        'desc': 'keycap: 10',
        'group': 'Symbols',
        'subgroup': 'keycap',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4AF', {
        'desc': 'hundred points',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F520', {
        'desc': 'input latin uppercase',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F521', {
        'desc': 'input latin lowercase',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F522', {
        'desc': 'input numbers',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F523', {
        'desc': 'input symbols',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F524', {
        'desc': 'input latin letters',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F170\U0000FE0F', {
        'desc': 'A button (blood type)',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U0001F170', {
        'desc': 'A button (blood type)',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F18E', {
        'desc': 'AB button (blood type)',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F171\U0000FE0F', {
        'desc': 'B button (blood type)',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U0001F171', {
        'desc': 'B button (blood type)',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F191', {
        'desc': 'CL button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F192', {
        'desc': 'COOL button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F193', {
        'desc': 'FREE button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002139\U0000FE0F', {
        'desc': 'information',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U00002139', {
        'desc': 'information',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F194', {
        'desc': 'ID button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000024C2\U0000FE0F', {
        'desc': 'circled M',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U000024C2', {
        'desc': 'circled M',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F195', {
        'desc': 'NEW button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F196', {
        'desc': 'NG button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F17E\U0000FE0F', {
        'desc': 'O button (blood type)',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U0001F17E', {
        'desc': 'O button (blood type)',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F197', {
        'desc': 'OK button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F17F\U0000FE0F', {
        'desc': 'P button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U0001F17F', {
        'desc': 'P button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F198', {
        'desc': 'SOS button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F199', {
        'desc': 'UP! button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F19A', {
        'desc': 'VS button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F201', {
        'desc': 'Japanese “here” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F202\U0000FE0F', {
        'desc': 'Japanese “service charge” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U0001F202', {
        'desc': 'Japanese “service charge” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F237\U0000FE0F', {
        'desc': 'Japanese “monthly amount” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U0001F237', {
        'desc': 'Japanese “monthly amount” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F236', {
        'desc': 'Japanese “not free of charge” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F22F', {
        'desc': 'Japanese “reserved” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F250', {
        'desc': 'Japanese “bargain” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F239', {
        'desc': 'Japanese “discount” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F21A', {
        'desc': 'Japanese “free of charge” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F232', {
        'desc': 'Japanese “prohibited” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F251', {
        'desc': 'Japanese “acceptable” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F238', {
        'desc': 'Japanese “application” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F234', {
        'desc': 'Japanese “passing grade” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F233', {
        'desc': 'Japanese “vacancy” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00003297\U0000FE0F', {
        'desc': 'Japanese “congratulations” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U00003297', {
        'desc': 'Japanese “congratulations” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U00003299\U0000FE0F', {
        'desc': 'Japanese “secret” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True
    }),
    ('\U00003299', {
        'desc': 'Japanese “secret” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F23A', {
        'desc': 'Japanese “open for business” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F235', {
        'desc': 'Japanese “no vacancy” button',
        'group': 'Symbols',
        'subgroup': 'alphanum',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000025AA\U0000FE0F', {
        'desc': 'black small square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True
    }),
    ('\U000025AA', {
        'desc': 'black small square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000025AB\U0000FE0F', {
        'desc': 'white small square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True
    }),
    ('\U000025AB', {
        'desc': 'white small square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000025FB\U0000FE0F', {
        'desc': 'white medium square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True
    }),
    ('\U000025FB', {
        'desc': 'white medium square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000025FC\U0000FE0F', {
        'desc': 'black medium square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True
    }),
    ('\U000025FC', {
        'desc': 'black medium square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U000025FD', {
        'desc': 'white medium-small square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000025FE', {
        'desc': 'black medium-small square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002B1B', {
        'desc': 'black large square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U00002B1C', {
        'desc': 'white large square',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F536', {
        'desc': 'large orange diamond',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F537', {
        'desc': 'large blue diamond',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F538', {
        'desc': 'small orange diamond',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F539', {
        'desc': 'small blue diamond',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F53A', {
        'desc': 'red triangle pointed up',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F53B', {
        'desc': 'red triangle pointed down',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F4A0', {
        'desc': 'diamond with a dot',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F518', {
        'desc': 'radio button',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F532', {
        'desc': 'black square button',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F533', {
        'desc': 'white square button',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026AA', {
        'desc': 'white circle',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U000026AB', {
        'desc': 'black circle',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F534', {
        'desc': 'red circle',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F535', {
        'desc': 'blue circle',
        'group': 'Symbols',
        'subgroup': 'geometric',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3C1', {
        'desc': 'chequered flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F6A9', {
        'desc': 'triangular flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F38C', {
        'desc': 'crossed flags',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F4', {
        'desc': 'black flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': True,
        'Emoji': True,
        'Emoji_Presentation': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F3\U0000FE0F', {
        'desc': 'white flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': True
    }),
    ('\U0001F3F3', {
        'desc': 'white flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': False,
        'Emoji': True,
        'Extended_Pictographic': True
    }),
    ('\U0001F3F3\U0000FE0F\U0000200D\U0001F308', {
        'desc': 'rainbow flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3F3\U0000200D\U0001F308', {
        'desc': 'rainbow flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': False
    }),
    ('\U0001F3F4\U0000200D\U00002620\U0000FE0F', {
        'desc': 'pirate flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': True,
        'Emoji_ZWJ_Sequence': True
    }),
    ('\U0001F3F4\U0000200D\U00002620', {
        'desc': 'pirate flag',
        'group': 'Flags',
        'subgroup': 'flag',
        'fully-qualified': False
    }),
    ('\U0001F1E6\U0001F1E8', {
        'desc': 'Ascension Island',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1E9', {
        'desc': 'Andorra',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1EA', {
        'desc': 'United Arab Emirates',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1EB', {
        'desc': 'Afghanistan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1EC', {
        'desc': 'Antigua & Barbuda',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1EE', {
        'desc': 'Anguilla',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1F1', {
        'desc': 'Albania',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1F2', {
        'desc': 'Armenia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1F4', {
        'desc': 'Angola',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1F6', {
        'desc': 'Antarctica',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1F7', {
        'desc': 'Argentina',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1F8', {
        'desc': 'American Samoa',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1F9', {
        'desc': 'Austria',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1FA', {
        'desc': 'Australia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1FC', {
        'desc': 'Aruba',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1FD', {
        'desc': 'Åland Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E6\U0001F1FF', {
        'desc': 'Azerbaijan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1E6', {
        'desc': 'Bosnia & Herzegovina',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1E7', {
        'desc': 'Barbados',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1E9', {
        'desc': 'Bangladesh',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1EA', {
        'desc': 'Belgium',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1EB', {
        'desc': 'Burkina Faso',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1EC', {
        'desc': 'Bulgaria',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1ED', {
        'desc': 'Bahrain',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1EE', {
        'desc': 'Burundi',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1EF', {
        'desc': 'Benin',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F1', {
        'desc': 'St. Barthélemy',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F2', {
        'desc': 'Bermuda',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F3', {
        'desc': 'Brunei',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F4', {
        'desc': 'Bolivia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F6', {
        'desc': 'Caribbean Netherlands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F7', {
        'desc': 'Brazil',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F8', {
        'desc': 'Bahamas',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1F9', {
        'desc': 'Bhutan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1FB', {
        'desc': 'Bouvet Island',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1FC', {
        'desc': 'Botswana',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1FE', {
        'desc': 'Belarus',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E7\U0001F1FF', {
        'desc': 'Belize',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1E6', {
        'desc': 'Canada',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1E8', {
        'desc': 'Cocos (Keeling) Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1E9', {
        'desc': 'Congo - Kinshasa',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1EB', {
        'desc': 'Central African Republic',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1EC', {
        'desc': 'Congo - Brazzaville',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1ED', {
        'desc': 'Switzerland',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1EE', {
        'desc': 'Côte d’Ivoire',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1F0', {
        'desc': 'Cook Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1F1', {
        'desc': 'Chile',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1F2', {
        'desc': 'Cameroon',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1F3', {
        'desc': 'China',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1F4', {
        'desc': 'Colombia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1F5', {
        'desc': 'Clipperton Island',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1F7', {
        'desc': 'Costa Rica',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1FA', {
        'desc': 'Cuba',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1FB', {
        'desc': 'Cape Verde',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1FC', {
        'desc': 'Curaçao',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1FD', {
        'desc': 'Christmas Island',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1FE', {
        'desc': 'Cyprus',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E8\U0001F1FF', {
        'desc': 'Czechia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E9\U0001F1EA', {
        'desc': 'Germany',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E9\U0001F1EC', {
        'desc': 'Diego Garcia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E9\U0001F1EF', {
        'desc': 'Djibouti',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E9\U0001F1F0', {
        'desc': 'Denmark',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E9\U0001F1F2', {
        'desc': 'Dominica',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E9\U0001F1F4', {
        'desc': 'Dominican Republic',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1E9\U0001F1FF', {
        'desc': 'Algeria',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1E6', {
        'desc': 'Ceuta & Melilla',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1E8', {
        'desc': 'Ecuador',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1EA', {
        'desc': 'Estonia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1EC', {
        'desc': 'Egypt',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1ED', {
        'desc': 'Western Sahara',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1F7', {
        'desc': 'Eritrea',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1F8', {
        'desc': 'Spain',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1F9', {
        'desc': 'Ethiopia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EA\U0001F1FA', {
        'desc': 'European Union',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EB\U0001F1EE', {
        'desc': 'Finland',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EB\U0001F1EF', {
        'desc': 'Fiji',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EB\U0001F1F0', {
        'desc': 'Falkland Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EB\U0001F1F2', {
        'desc': 'Micronesia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EB\U0001F1F4', {
        'desc': 'Faroe Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EB\U0001F1F7', {
        'desc': 'France',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1E6', {
        'desc': 'Gabon',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1E7', {
        'desc': 'United Kingdom',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1E9', {
        'desc': 'Grenada',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1EA', {
        'desc': 'Georgia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1EB', {
        'desc': 'French Guiana',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1EC', {
        'desc': 'Guernsey',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1ED', {
        'desc': 'Ghana',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1EE', {
        'desc': 'Gibraltar',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F1', {
        'desc': 'Greenland',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F2', {
        'desc': 'Gambia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F3', {
        'desc': 'Guinea',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F5', {
        'desc': 'Guadeloupe',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F6', {
        'desc': 'Equatorial Guinea',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F7', {
        'desc': 'Greece',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F8', {
        'desc': 'South Georgia & South Sandwich Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1F9', {
        'desc': 'Guatemala',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1FA', {
        'desc': 'Guam',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1FC', {
        'desc': 'Guinea-Bissau',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EC\U0001F1FE', {
        'desc': 'Guyana',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1ED\U0001F1F0', {
        'desc': 'Hong Kong SAR China',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1ED\U0001F1F2', {
        'desc': 'Heard & McDonald Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1ED\U0001F1F3', {
        'desc': 'Honduras',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1ED\U0001F1F7', {
        'desc': 'Croatia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1ED\U0001F1F9', {
        'desc': 'Haiti',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1ED\U0001F1FA', {
        'desc': 'Hungary',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1E8', {
        'desc': 'Canary Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1E9', {
        'desc': 'Indonesia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1EA', {
        'desc': 'Ireland',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F1', {
        'desc': 'Israel',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F2', {
        'desc': 'Isle of Man',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F3', {
        'desc': 'India',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F4', {
        'desc': 'British Indian Ocean Territory',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F6', {
        'desc': 'Iraq',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F7', {
        'desc': 'Iran',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F8', {
        'desc': 'Iceland',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EE\U0001F1F9', {
        'desc': 'Italy',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EF\U0001F1EA', {
        'desc': 'Jersey',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EF\U0001F1F2', {
        'desc': 'Jamaica',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EF\U0001F1F4', {
        'desc': 'Jordan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1EF\U0001F1F5', {
        'desc': 'Japan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1EA', {
        'desc': 'Kenya',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1EC', {
        'desc': 'Kyrgyzstan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1ED', {
        'desc': 'Cambodia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1EE', {
        'desc': 'Kiribati',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1F2', {
        'desc': 'Comoros',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1F3', {
        'desc': 'St. Kitts & Nevis',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1F5', {
        'desc': 'North Korea',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1F7', {
        'desc': 'South Korea',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1FC', {
        'desc': 'Kuwait',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1FE', {
        'desc': 'Cayman Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F0\U0001F1FF', {
        'desc': 'Kazakhstan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1E6', {
        'desc': 'Laos',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1E7', {
        'desc': 'Lebanon',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1E8', {
        'desc': 'St. Lucia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1EE', {
        'desc': 'Liechtenstein',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1F0', {
        'desc': 'Sri Lanka',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1F7', {
        'desc': 'Liberia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1F8', {
        'desc': 'Lesotho',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1F9', {
        'desc': 'Lithuania',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1FA', {
        'desc': 'Luxembourg',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1FB', {
        'desc': 'Latvia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F1\U0001F1FE', {
        'desc': 'Libya',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1E6', {
        'desc': 'Morocco',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1E8', {
        'desc': 'Monaco',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1E9', {
        'desc': 'Moldova',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1EA', {
        'desc': 'Montenegro',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1EB', {
        'desc': 'St. Martin',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1EC', {
        'desc': 'Madagascar',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1ED', {
        'desc': 'Marshall Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F0', {
        'desc': 'Macedonia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F1', {
        'desc': 'Mali',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F2', {
        'desc': 'Myanmar (Burma)',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F3', {
        'desc': 'Mongolia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F4', {
        'desc': 'Macau SAR China',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F5', {
        'desc': 'Northern Mariana Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F6', {
        'desc': 'Martinique',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F7', {
        'desc': 'Mauritania',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F8', {
        'desc': 'Montserrat',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1F9', {
        'desc': 'Malta',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1FA', {
        'desc': 'Mauritius',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1FB', {
        'desc': 'Maldives',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1FC', {
        'desc': 'Malawi',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1FD', {
        'desc': 'Mexico',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1FE', {
        'desc': 'Malaysia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F2\U0001F1FF', {
        'desc': 'Mozambique',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1E6', {
        'desc': 'Namibia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1E8', {
        'desc': 'New Caledonia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1EA', {
        'desc': 'Niger',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1EB', {
        'desc': 'Norfolk Island',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1EC', {
        'desc': 'Nigeria',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1EE', {
        'desc': 'Nicaragua',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1F1', {
        'desc': 'Netherlands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1F4', {
        'desc': 'Norway',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1F5', {
        'desc': 'Nepal',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1F7', {
        'desc': 'Nauru',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1FA', {
        'desc': 'Niue',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F3\U0001F1FF', {
        'desc': 'New Zealand',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F4\U0001F1F2', {
        'desc': 'Oman',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1E6', {
        'desc': 'Panama',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1EA', {
        'desc': 'Peru',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1EB', {
        'desc': 'French Polynesia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1EC', {
        'desc': 'Papua New Guinea',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1ED', {
        'desc': 'Philippines',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1F0', {
        'desc': 'Pakistan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1F1', {
        'desc': 'Poland',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1F2', {
        'desc': 'St. Pierre & Miquelon',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1F3', {
        'desc': 'Pitcairn Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1F7', {
        'desc': 'Puerto Rico',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1F8', {
        'desc': 'Palestinian Territories',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1F9', {
        'desc': 'Portugal',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1FC', {
        'desc': 'Palau',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F5\U0001F1FE', {
        'desc': 'Paraguay',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F6\U0001F1E6', {
        'desc': 'Qatar',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F7\U0001F1EA', {
        'desc': 'Réunion',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F7\U0001F1F4', {
        'desc': 'Romania',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F7\U0001F1F8', {
        'desc': 'Serbia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F7\U0001F1FA', {
        'desc': 'Russia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F7\U0001F1FC', {
        'desc': 'Rwanda',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1E6', {
        'desc': 'Saudi Arabia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1E7', {
        'desc': 'Solomon Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1E8', {
        'desc': 'Seychelles',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1E9', {
        'desc': 'Sudan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1EA', {
        'desc': 'Sweden',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1EC', {
        'desc': 'Singapore',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1ED', {
        'desc': 'St. Helena',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1EE', {
        'desc': 'Slovenia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1EF', {
        'desc': 'Svalbard & Jan Mayen',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F0', {
        'desc': 'Slovakia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F1', {
        'desc': 'Sierra Leone',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F2', {
        'desc': 'San Marino',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F3', {
        'desc': 'Senegal',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F4', {
        'desc': 'Somalia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F7', {
        'desc': 'Suriname',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F8', {
        'desc': 'South Sudan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1F9', {
        'desc': 'São Tomé & Príncipe',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1FB', {
        'desc': 'El Salvador',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1FD', {
        'desc': 'Sint Maarten',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1FE', {
        'desc': 'Syria',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F8\U0001F1FF', {
        'desc': 'Swaziland',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1E6', {
        'desc': 'Tristan da Cunha',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1E8', {
        'desc': 'Turks & Caicos Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1E9', {
        'desc': 'Chad',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1EB', {
        'desc': 'French Southern Territories',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1EC', {
        'desc': 'Togo',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1ED', {
        'desc': 'Thailand',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1EF', {
        'desc': 'Tajikistan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1F0', {
        'desc': 'Tokelau',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1F1', {
        'desc': 'Timor-Leste',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1F2', {
        'desc': 'Turkmenistan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1F3', {
        'desc': 'Tunisia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1F4', {
        'desc': 'Tonga',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1F7', {
        'desc': 'Turkey',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1F9', {
        'desc': 'Trinidad & Tobago',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1FB', {
        'desc': 'Tuvalu',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1FC', {
        'desc': 'Taiwan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1F9\U0001F1FF', {
        'desc': 'Tanzania',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FA\U0001F1E6', {
        'desc': 'Ukraine',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FA\U0001F1EC', {
        'desc': 'Uganda',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FA\U0001F1F2', {
        'desc': 'U.S. Outlying Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FA\U0001F1F3', {
        'desc': 'United Nations',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FA\U0001F1F8', {
        'desc': 'United States',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FA\U0001F1FE', {
        'desc': 'Uruguay',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FA\U0001F1FF', {
        'desc': 'Uzbekistan',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FB\U0001F1E6', {
        'desc': 'Vatican City',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FB\U0001F1E8', {
        'desc': 'St. Vincent & Grenadines',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FB\U0001F1EA', {
        'desc': 'Venezuela',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FB\U0001F1EC', {
        'desc': 'British Virgin Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FB\U0001F1EE', {
        'desc': 'U.S. Virgin Islands',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FB\U0001F1F3', {
        'desc': 'Vietnam',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FB\U0001F1FA', {
        'desc': 'Vanuatu',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FC\U0001F1EB', {
        'desc': 'Wallis & Futuna',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FC\U0001F1F8', {
        'desc': 'Samoa',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FD\U0001F1F0', {
        'desc': 'Kosovo',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FE\U0001F1EA', {
        'desc': 'Yemen',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FE\U0001F1F9', {
        'desc': 'Mayotte',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FF\U0001F1E6', {
        'desc': 'South Africa',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FF\U0001F1F2', {
        'desc': 'Zambia',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F1FF\U0001F1FC', {
        'desc': 'Zimbabwe',
        'group': 'Flags',
        'subgroup': 'country-flag',
        'fully-qualified': True,
        'Emoji_Flag_Sequence': True
    }),
    ('\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F', {
        'desc': 'England',
        'group': 'Flags',
        'subgroup': 'subdivision-flag',
        'fully-qualified': True,
        'Emoji_Tag_Sequence': True
    }),
    ('\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F', {
        'desc': 'Scotland',
        'group': 'Flags',
        'subgroup': 'subdivision-flag',
        'fully-qualified': True,
        'Emoji_Tag_Sequence': True
    }),
    ('\U0001F3F4\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F', {
        'desc': 'Wales',
        'group': 'Flags',
        'subgroup': 'subdivision-flag',
        'fully-qualified': True,
        'Emoji_Tag_Sequence': True
    })
])
