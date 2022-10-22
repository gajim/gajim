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

from gi.repository import GLib
from gajim.common import regex

# from RFC 3986, 3.3. Path (pchar without unreserved and pct-encoded):
_reserved_chars_allowed_in_path_segment = regex.sub_delims + ':@'


def escape_iri_path_segment(s: str) -> str:
    return GLib.Uri.escape_string(
        s, _reserved_chars_allowed_in_path_segment, True)


def escape_iri_path(s: str) -> str:
    return GLib.Uri.escape_string(
        s, _reserved_chars_allowed_in_path_segment + '/', True)


def jid_to_iri(jid: str) -> str:
    return 'xmpp:' + escape_iri_path(jid)
