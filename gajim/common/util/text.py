# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import math
import random
import re
import string

import emoji
from gi.repository import GLib

from gajim.common import regex

# from RFC 3986, 3.3. Path (pchar without unreserved and pct-encoded):
_reserved_chars_allowed_in_path_segment = regex.sub_delims + ':@'


def remove_invalid_xml_chars(input_string: str) -> str:
    if input_string:
        return re.sub(regex.INVALID_XML_CHARS_REGEX, '', input_string)
    return input_string


def escape_iri_path_segment(s: str) -> str:
    return GLib.Uri.escape_string(
        s, _reserved_chars_allowed_in_path_segment, True)


def escape_iri_path(s: str) -> str:
    return GLib.Uri.escape_string(
        s, _reserved_chars_allowed_in_path_segment + '/', True)


def escape_iri_query(s: str) -> str:
    return GLib.Uri.escape_string(
        s, _reserved_chars_allowed_in_path_segment + '/?', True)


def jid_to_iri(jid: str) -> str:
    return 'xmpp:' + escape_iri_path(jid)


def quote_text(text: str) -> str:
    return '> ' + text.replace('\n', '\n> ') + '\n'


def format_duration(ns: float, total_ns: float) -> str:
    seconds = ns / 1e9
    minutes = seconds / 60
    hours = minutes / 60

    total_minutes = total_ns / 1e9 / 60
    total_hours = total_minutes / 60

    i_seconds = int(seconds) % 60
    i_minutes = int(minutes) % 60
    i_hours = int(hours)

    if total_hours >= 1:
        width = len(str(int(total_hours)))
        return (f'%0{width}d' % i_hours) + f':{i_minutes:02d}:{i_seconds:02d}'

    if total_minutes >= 1:
        width = len(str(int(total_minutes)))
        return (f'%0{width}d' % i_minutes) + f':{i_seconds:02d}'

    return f'0:{i_seconds:02d}'


def format_bytes_as_hex(bytes_: bytes, line_count: int = 1) -> str:
    line_length = math.ceil(len(bytes_) / line_count)

    hex_list = [f'{b:02X}' for b in bytes_]

    lines: list[str] = []
    for pos in range(0, len(bytes_), line_length):
        lines.append(':'.join(hex_list[pos:pos + line_length]))
    return '\n'.join(lines)


def normalize_reactions(reactions: list[str]) -> tuple[set[str], set[str]]:
    valid: set[str] = set()
    invalid: set[str] = set()
    # Set arbitrary limit of max reactions to prevent
    # performance problems when loading and displaying them.
    reactions = reactions[:10]
    for reaction in reactions:
        # Remove emoji variant selectors. They are not needed because
        # reactions are required to be shown as emoji representation.
        # Furthermore it allows us to unify both versions.
        reaction = reaction.strip('\uFE0E\uFE0F')
        if not emoji.is_emoji(reaction):
            invalid.add(reaction)
            continue
        valid.add(reaction)

    return valid, invalid


def convert_to_codepoints(string: str) -> str:
    return ''.join(f'\\u{ord(c):04x}' for c in string)


def get_country_flag_from_code(country_code: str) -> str:
        '''Returns a flag emoji for a two-letter country code.'''
        emoji_letters = {
            'A': '🇦',
            'B': '🇧',
            'C': '🇨',
            'D': '🇩',
            'E': '🇪',
            'F': '🇫',
            'G': '🇬',
            'H': '🇭',
            'I': '🇮',
            'J': '🇯',
            'K': '🇰',
            'L': '🇱',
            'M': '🇲',
            'N': '🇳',
            'O': '🇴',
            'P': '🇵',
            'Q': '🇶',
            'R': '🇷',
            'S': '🇸',
            'T': '🇹',
            'U': '🇺',
            'V': '🇻',
            'W': '🇼',
            'X': '🇽',
            'Y': '🇾',
            'Z': '🇿',
        }

        if len(country_code) != 2:
            return country_code.upper()

        first = emoji_letters.get(country_code[0].upper())
        second = emoji_letters.get(country_code[1].upper())
        if first is None or second is None:
            return country_code.upper()

        return f'{first}{second}'


def to_one_line(msg: str) -> str:
    return " ".join(msg.splitlines())


def from_one_line(msg: str) -> str:
    # (?<!\\) is a lookbehind assertion which asks anything but '\'
    # to match the regexp that follows it

    # So here match '\\n' but not if you have a '\' before that
    expr = re.compile(r'(?<!\\)\\n')
    msg = expr.sub('\n', msg)
    return msg.replace('\\\\', '\\')


def get_random_string(count: int = 16) -> str:
    '''
    Create random string of length 'count'

    WARNING: Don't use this for security purposes
    '''
    allowed = string.ascii_uppercase + string.digits
    return ''.join(random.choice(allowed) for _char in range(count))
