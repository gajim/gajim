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

from typing import Literal

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


def format_sha_bytes(algo: Literal['sha1', 'sha256'], sha_bytes: bytes) -> str:
    if algo == 'sha1':
        stop, step = 20, 10
    elif algo == 'sha256':
        stop, step = 32, 8
    else:
        raise ValueError(f'Unknown algo: {algo}')

    lines: list[str] = []
    hex_list = [f'{b:02X}' for b in sha_bytes]
    for pos in range(0, stop, step):
        lines.append(':'.join(hex_list[pos:pos + step]))
    return '\n'.join(lines)
