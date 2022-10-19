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

from collections import defaultdict
from typing import Optional

import logging

from gi.repository import Gio
from gi.repository import GLib

from gajim.common.i18n import _
from gajim.common.i18n import get_default_lang
from gajim.common.i18n import get_short_lang_code

FALLBACK_LOCALE = 'en_US'

log = logging.getLogger('gajim.gui.emoji_data_gtk')

REPLACEMENT_CHARACTER = 0xFFFD

SKIN_TONE_MODIFIERS = {
    # The descriptions differ slightly from the official short names, see:
    # https://github.com/unicode-org/cldr/blob/main/common/annotations/en.xml
    0x1F3FB: _('light skin'),
    0x1F3FC: _('medium-light skin'),
    0x1F3FD: _('medium skin tone'),
    0x1F3FE: _('medium-dark skin'),
    0x1F3FF: _('dark skin')
}

SKIN_TONE_MODIFIERS_INV: dict[str, int] = {}
for cp, desc in SKIN_TONE_MODIFIERS.items():
    if not desc.endswith(' tone'):
        desc += ' tone'
    SKIN_TONE_MODIFIERS_INV[desc] = cp


def generate_unicode_sequence(c_sequence: list[int]) -> str:
    '''
    Generates a unicode sequence from a list of codepoints
    '''
    u_sequence = ''
    for codepoint in c_sequence:
        u_sequence += chr(codepoint)
    return u_sequence


def replace_skin_tone_placeholder(c_sequence: list[int],
                                  modifier: int
                                  ) -> list[int]:

    '''
    Replaces GTKs placeholder '0' for skin tone modifiers
    with a given modifier
    '''
    c_mod_sequence: list[int] = []
    for codepoint in c_sequence:
        if codepoint == 0:
            codepoint = modifier
        c_mod_sequence.append(codepoint)
    return c_mod_sequence


def get_emoji_data() -> dict[str, dict[str, str]]:
    '''
    Returns dict of `keyword` -> dict of `short_name` -> `emoji`, where
    `keyword` and `short_name` are as defined in
    <https://unicode.org/reports/tr35/tr35-general.html#Annotations>, and
    `emoji` is an emoji grapheme cluster.

    Short names are included among keywords.
    '''
    return emoji_data


def try_load_raw_emoji_data(locale: str) -> Optional[GLib.Bytes]:
    # Sources of emoji data can be found at:
    # https://gitlab.gnome.org/GNOME/gtk/-/tree/main/gtk/emoji
    emoji_data_resource = f'/org/gtk/libgtk/emoji/{locale}.data'

    try:
        bytes_ = Gio.resources_lookup_data(
            emoji_data_resource,
            Gio.ResourceLookupFlags.NONE)
        assert bytes_ is not None
        log.info('Loaded emoji data resource for locale %s', locale)
        return bytes_
    except GLib.Error as error:
        log.info('Loading emoji data resource for locale %s failed: %s',
                 locale, error)
        return None


def parse_emoji_data(bytes_data: GLib.Bytes) -> dict[str, dict[str, str]]:
    variant = GLib.Variant.new_from_bytes(
        # Reference for the data format:
        # https://gitlab.gnome.org/GNOME/gtk/-/blob/3.24.34/gtk/emoji/
        # convert-emoji.c#L111
        GLib.VariantType('a(ausasu)'),
        bytes_data,
        True)
    iterable: list[tuple[list[int], str, list[str], int]] = variant.unpack()

    emoji_data_dict: dict[str, dict[str, str]] = defaultdict(dict)
    for c_sequence, short_name, keywords, _group in iterable:
        # Example item:
        # ([128105, 0, 8205, 10084, 65039, 8205, 128104, 0],
        # 'couple with heart: woman, man',
        # ['couple', 'couple with heart', 'love', 'man', 'woman'],
        # 1),
        # GTK sets '0' as a placeholder for skin tone modifiers, see:
        # https://gitlab.gnome.org/GNOME/gtk/-/blob/main/gtk/emoji/
        # convert-emoji.c

        if c_sequence == [0]:
            # c_sequence *is* the skin tone placeholder itself... and we
            # don't know which. Let us find out!
            # Looks like a bug in GTK's data, present at least in 3.24.34.
            if short_name in SKIN_TONE_MODIFIERS_INV:
                c_sequence[0] = SKIN_TONE_MODIFIERS_INV[short_name]
                log.debug('Null codepoint for short name "%s", found U+%04X',
                          short_name, c_sequence[0])
            else:
                c_sequence[0] = REPLACEMENT_CHARACTER
                log.warning('Null codepoint for short name "%s", not found',
                            short_name)

        # Replace colon by comma to improve short name completion usability
        short_name = short_name.replace(':', ',')

        for keyword in keywords + [short_name]:
            keyword = keyword.casefold()

            if 0 not in c_sequence:
                # No skin tone modifiers present
                u_sequence = generate_unicode_sequence(c_sequence)
                emoji_data_dict[keyword][short_name] = u_sequence
                continue

            # Filter out 0 in order to generate basic (yellow) variation
            c_basic_sequence = [c for c in c_sequence if c != 0]
            u_sequence = generate_unicode_sequence(c_basic_sequence)
            emoji_data_dict[keyword][short_name] = u_sequence

            # Add variations with skin tone modifiers
            for modifier, mod_desc in SKIN_TONE_MODIFIERS.items():
                new_keyword = f'{keyword}, {mod_desc.casefold()}'
                new_short_name = f'{short_name}, {mod_desc}'
                c_mod_sequence = replace_skin_tone_placeholder(
                    c_sequence, modifier)
                u_mod_sequence = generate_unicode_sequence(c_mod_sequence)
                emoji_data_dict[new_keyword][new_short_name] = u_mod_sequence

    emoji_data_dict = dict(sorted(emoji_data_dict.items()))
    for keyword, entries in emoji_data_dict.items():
        emoji_data_dict[keyword] = dict(sorted(entries.items()))

    return emoji_data_dict


def get_locale_fallbacks(desired: str) -> list[str]:
    '''
    Returns full list of locales to try loading emoji data in, in the order of
    decreasing preference and specificity.  E.g., ['de_DE', 'de', 'en_US', 'en']
    for desired == 'de_DE'.
    '''
    result = [desired]
    lang = get_short_lang_code(desired)
    if lang not in result:
        result.append(lang)

    if FALLBACK_LOCALE not in result:
        result.append(FALLBACK_LOCALE)
    fallback_lang = get_short_lang_code(FALLBACK_LOCALE)
    if fallback_lang not in result:
        result.append(fallback_lang)

    return result


app_locale = get_default_lang()
log.info('Loading emoji data; application locale is %s', app_locale)
locales = get_locale_fallbacks(app_locale)
try:
    log.debug('Trying locales %s', locales)
    raw_emoji_data: Optional[GLib.Bytes] = None
    for loc in locales:
        raw_emoji_data = try_load_raw_emoji_data(loc)
        if raw_emoji_data:
            break
    if not raw_emoji_data:
        raise RuntimeError(f'No resource could be loaded; tried {locales}')

    emoji_data = parse_emoji_data(raw_emoji_data)
except Exception as err:
    log.warning('Unable to load emoji data: %s', err)
    emoji_data = {}
