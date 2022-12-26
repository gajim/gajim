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

import re
from typing import Any


COMMAND_REGEX = re.compile(r'^/[a-z]+')

INVALID_XML_CHARS_REGEX = re.compile(
    '[\x00-\x08]|[\x0b-\x0c]|[\x0e-\x1f]|[\ud800-\udfff]|[\ufffe-\uffff]')


# Universal/Internationalized Resource Identifiers and their components, as
# defined in [ABNF for IRI References and IRIs]
# <https://rfc-editor.org/rfc/rfc3987#section-2.2> and
# [Representing IPv6 Zone Identifiers in Address Literals and URIs]
# <https://www.rfc-editor.org/rfc/rfc6874>.
ALPHA          = r'[A-Za-z]'
HEXDIG         = r'[0-9A-Fa-f]'
sub_delims     = r"!$&'()*+,;="
ucschar        = r'\xA0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF'\
    r'\U00010000-\U0001FFFD\U00020000-\U0002FFFD\U00030000-\U0003FFFD'\
    r'\U00040000-\U0004FFFD\U00050000-\U0005FFFD\U00060000-\U0006FFFD'\
    r'\U00070000-\U0007FFFD\U00080000-\U0008FFFD\U00090000-\U0009FFFD'\
    r'\U000A0000-\U000AFFFD\U000B0000-\U000BFFFD\U000C0000-\U000CFFFD'\
    r'\U000D0000-\U000DFFFD\U000E1000-\U000EFFFD'
iprivate       = r'\uE000-\uF8FF'\
    r'\U000F0000-\U000FFFFD\U00100000-\U0010FFFD'
unreserved     = r'A-Za-z0-9\-._~'
iunreserved    = fr'{unreserved}{ucschar}'
pct_encoded    = fr'%{HEXDIG}{HEXDIG}'
ipchar         = fr'(?:[{iunreserved}{sub_delims}:@]|{pct_encoded})'
iuserinfo      = fr'(?:[{iunreserved}{sub_delims}:]|{pct_encoded})*'
ireg_name      = fr'(?:[{iunreserved}{sub_delims}]|{pct_encoded})*'
dec_octet      = r'(?:25[0-5]'\
                 r'|2[0-4][0-9]'\
                 r'|1[0-9][0-9]'\
                 r'|[1-9][0-9]'\
                 r'|[0-9])'
IPv4address    = fr'{dec_octet}(?:\.{dec_octet}){{3}}'
h16            = fr'{HEXDIG}{{1,4}}'
ls32           = fr'(?:{h16}:{h16}|{IPv4address})'
IPv6address    =\
                              fr'(?:(?:{h16}:){{6}}{ls32}'\
                              fr'|::(?:{h16}:){{5}}{ls32}'\
                    fr'|(?:{h16})?::(?:{h16}:){{4}}{ls32}'\
    fr'|(?:(?:{h16}:){{,1}}{h16})?::(?:{h16}:){{3}}{ls32}'\
    fr'|(?:(?:{h16}:){{,2}}{h16})?::(?:{h16}:){{2}}{ls32}'\
    fr'|(?:(?:{h16}:){{,3}}{h16})?::{h16}:{ls32}'\
    fr'|(?:(?:{h16}:){{,4}}{h16})?::{ls32}'\
    fr'|(?:(?:{h16}:){{,5}}{h16})?::{h16}'\
    fr'|(?:(?:{h16}:){{,6}}{h16})?::)'  # noqa: E126,E127,E131
ZoneID         = fr'(?:{unreserved}|{pct_encoded})+'
IPv6addrz      = fr'{IPv6address}%25{ZoneID}'
IPvFuture      = fr'[Vv]{HEXDIG}+\.[{unreserved}{sub_delims}:]+'
IP_literal     = fr'\[(?:{IPv6address}|{IPv6addrz}|{IPvFuture})\]'
# ihost        = fr'(?P<host>{IP_literal}|{IPv4address}|{ireg_name})'
# The below is equivalent to the above for the purpose of validation, but
# better for the purpose of search: e.g., matches 'foo://1.2.3.4.5' completely.
ihost          = fr'(?P<host>{IP_literal}|{ireg_name})'
port           = r'[0-9]*'
iauthority     = fr'(?:{iuserinfo}@)?{ihost}(?::{port})?'
isegment       = fr'{ipchar}*'
isegment_nz    = fr'{ipchar}+'
ipath_abempty  = fr'(?:/{isegment})*'
ipath_absolute = fr'/(?:{isegment_nz}(?:/{isegment})*)?'
ipath_rootless = fr'{isegment_nz}(?:/{isegment})*'
ipath_empty    = r''
ihier_part     = fr'(?://{iauthority}{ipath_abempty}'\
                 fr'|{ipath_absolute}'\
                 fr'|{ipath_rootless}'\
                 fr'|{ipath_empty})'
iquery         = fr'(?:{ipchar}|[/?{iprivate}])*'
ifragment      = fr'(?:{ipchar}|[/?])*'
scheme         = fr'(?P<scheme>{ALPHA}[a-zA-Z0-9+.-]*)'
IRI            = fr'{scheme}:{ihier_part}(?:\?{iquery})?(?:#{ifragment})?'


# <https://rfc-editor.org/rfc/rfc7564#section-4.2>
class PRECIS:
    LetterDigits = r'\w'  # roughly (e.g., includes '_' as an extra)
    Spaces       = r'\s'  # roughly?
    Symbols      = r'♚'   # let's make that test pass!
    HasCompat    = r'Ⅳ'  # and that one!
    IdentifierClass: Any


class PRECISIdentifierClass:
    _p = PRECIS
    Valid      = fr'{_p.LetterDigits}\x21-\x7e'
    Disallowed = fr'{_p.Spaces}{_p.Symbols}{_p.HasCompat}'  # there's a ton more


PRECIS.IdentifierClass = PRECISIdentifierClass


# (Rough approximation of) Jabber IDs, as defined in [XMPP: Address Format]
# <https://rfc-editor.org/rfc/rfc7622#section-3>.
class XMPP:
    _id = PRECIS.IdentifierClass
    _excl      = '"&\'/:<>@'  # <#section-3.3.1>
    localpart  = fr'(?:(?![{_excl}{_id.Disallowed}])[{_id.Valid}])+'
    # ^ doesn't take into account "contextual rules" <rfc7564#section-4.2.2>
    ifqdn      = fr'[{iunreserved}{sub_delims}]+'
    # ^ probably correct
    domainpart = fr'(?:{IP_literal}|{IPv4address}|{ifqdn})'
    jid        = fr'(?P<local>{localpart})@(?P<domain>{domainpart})'
    # ^ notably, doesn't include resourcepart (TODO)
