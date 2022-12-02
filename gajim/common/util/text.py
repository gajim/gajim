# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import math
import re

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


def remove_fallback_text(text: str,
                         start: int | None,
                         end: int | None
                         ) -> str:

    if start is None:
        start = 0

    if end is None:
        return text[start:]

    before = text[:start]
    after = text[end:]
    return before + after


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
