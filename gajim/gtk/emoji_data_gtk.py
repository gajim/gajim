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

import logging
from packaging.version import Version as V

from gi.repository import Gio
from gi.repository import GLib

from .util import get_gtk_version

log = logging.getLogger('gajim.gui.emoji_data_gtk')

SKIN_TONE_MODIFIERS = {
    127995: 'light skin tone',
    127996: 'medium-light skin tone',
    127997: 'medium skin tone',
    127998: 'medium-dark skin tone',
    127999: 'dark skin tone'
}


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


def get_emoji_data() -> dict[str, str]:
    return emoji_data


def load_emoji_data() -> dict[str, str]:
    # Location of emoji data resource changed in GTK >= 3.24.30
    if V(get_gtk_version()) >= V('3.24.30'):
        emoji_data_resource = '/org/gtk/libgtk/emoji/en.data'
    else:
        emoji_data_resource = '/org/gtk/libgtk/emoji/emoji.data'

    try:
        bytes_ = Gio.resources_lookup_data(
            emoji_data_resource,
            Gio.ResourceLookupFlags.NONE)
        assert bytes_ is not None
        # We have to store bytes_data in a variable to make sure Python
        # keeps it until it is processed.
        bytes_data = bytes_.get_data()
    except GLib.Error as error:
        log.warning('Loading emoji resources failed: %s', error)
        return {}

    def _pass(_user_data: Any) -> None:
        pass

    variant = GLib.Variant.new_from_data(
        GLib.VariantType('a(auss)'),
        bytes_data,
        True,
        _pass)

    emoji_data_dict: dict[str, str] = {}
    for c_sequence, shortcode, _ in variant:
        # Example item:
        # ([128105, 0, 8205, 10084, 65039, 8205, 128104, 0],
        # 'couple with heart: woman, man',
        # 'couple'),
        # GTK sets '0' as a placeholder for skin tone modifiers, see:
        # https://gitlab.gnome.org/GNOME/gtk/-/blob/main/gtk/emoji/
        # convert-emoji.c

        # Replace colon by comma to improve emoji shortcode usability
        shortcode = shortcode.replace(':', ',')

        if 0 not in c_sequence:
            # No skin tone modifiers present
            u_sequence = generate_unicode_sequence(c_sequence)
            emoji_data_dict[shortcode] = u_sequence
            continue

        # Filter out 0 in order to generate basic (yellow) variation
        c_basic_sequence = [c for c in c_sequence if c != 0]
        u_sequence = generate_unicode_sequence(c_basic_sequence)
        emoji_data_dict[shortcode] = u_sequence

        # Add variations with skin tone modifiers
        for modifier, mod_shortcode in SKIN_TONE_MODIFIERS.items():
            new_shortcode = f'{shortcode}, {mod_shortcode}'
            c_mod_sequence = replace_skin_tone_placeholder(
                c_sequence, modifier)
            u_mod_sequence = generate_unicode_sequence(c_mod_sequence)
            emoji_data_dict[new_shortcode] = u_mod_sequence

    # Add commonly used shortcodes
    emoji_data_dict['+1'] = '\U0001F44D'
    emoji_data_dict['-1'] = '\U0001F44E'

    emoji_data_dict = dict(sorted(emoji_data_dict.items()))

    return emoji_data_dict


try:
    emoji_data = load_emoji_data()
except Exception as err:
    log.warning('Unable to load emoji data: %s', err)
    emoji_data = {}
