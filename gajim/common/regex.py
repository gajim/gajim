# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import re

COMMAND_REGEX = re.compile(r'^/[a-z]+')

URL_REGEX = re.compile(
    r"(www\.(?!\.)|[a-z][a-z0-9+.-]*://)[^\s<>'\"]+[^!,\.\s<>\)'\"\]]")

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
urlchar = r"A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;="
pct_loose = fr'%[{urlchar}]'
pct_encoded    = fr'%{HEXDIG}{HEXDIG}'
ipchar_loose   = fr'(?:[{iunreserved}{sub_delims}:@]|{pct_loose})'
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
iquery         = fr'(?:{ipchar_loose}|[/?{iprivate}])*'
ifragment      = fr'(?:{ipchar}|[/?])*'
scheme         = fr'(?P<scheme>{ALPHA}[a-zA-Z0-9+.-]*)'
IRI            = fr'{scheme}:{ihier_part}(?:\?{iquery})?(?:#{ifragment})?'

IRI_RX = re.compile(IRI)

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


# Unicode characters of category: mark, non-spacing, see:
# https://en.wikipedia.org/wiki/Unicode_character_property#General_Category
NON_SPACING_MARKS = (
    r"\u0300-\u036F"
    r"\u0483-\u0487"
    r"\u0591-\u05BD"
    r"\u05BF"
    r"\u05C1-\u05C2"
    r"\u05C4-\u05C5"
    r"\u05C7"
    r"\u0610-\u061A"
    r"\u064B-\u065F"
    r"\u0670"
    r"\u06D6-\u06DC"
    r"\u06DF-\u06E4"
    r"\u06E7-\u06E8"
    r"\u06EA-\u06ED"
    r"\u0711"
    r"\u0730-\u074A"
    r"\u07A6-\u07B0"
    r"\u07EB-\u07F3"
    r"\u07FD "
    r"\u0816-\u0819"
    r"\u081B-\u0823"
    r"\u0825-\u0827"
    r"\u0829-\u082D"
    r"\u0859-\u085B"
    r"\u08D3-\u08E1"
    r"\u08E3-\u0902"
    r"\u093A"
    r"\u093C"
    r"\u0941-\u0948"
    r"\u094D"
    r"\u0951-\u0957"
    r"\u0962-\u0963"
    r"\u0981"
    r"\u09BC"
    r"\u09C1-\u09C4"
    r"\u09CD"
    r"\u09E2-\u09E3"
    r"\u09FE"
    r"\u0A01-\u0A02"
    r"\u0A3C"
    r"\u0A41-\u0A42"
    r"\u0A47-\u0A48"
    r"\u0A4B-\u0A4D"
    r"\u0A51"
    r"\u0A70-\u0A71"
    r"\u0A75"
    r"\u0A81-\u0A82"
    r"\u0ABC"
    r"\u0AC1-\u0AC5"
    r"\u0AC7-\u0AC8"
    r"\u0ACD"
    r"\u0AE2-\u0AE3"
    r"\u0AFA-\u0AFF"
    r"\u0B01"
    r"\u0B3C"
    r"\u0B3F"
    r"\u0B41-\u0B44"
    r"\u0B4D"
    r"\u0B55-\u0B56"
    r"\u0B62-\u0B63"
    r"\u0B82"
    r"\u0BC0"
    r"\u0BCD"
    r"\u0C00"
    r"\u0C04"
    r"\u0C3E-\u0C40"
    r"\u0C46-\u0C48"
    r"\u0C4A-\u0C4D"
    r"\u0C55-\u0C56"
    r"\u0C62-\u0C63"
    r"\u0C81"
    r"\u0CBC"
    r"\u0CBF"
    r"\u0CC6"
    r"\u0CCC-\u0CCD"
    r"\u0CE2-\u0CE3"
    r"\u0D00-\u0D01"
    r"\u0D3B-\u0D3C"
    r"\u0D41-\u0D44"
    r"\u0D4D"
    r"\u0D62-\u0D63"
    r"\u0D81"
    r"\u0DCA"
    r"\u0DD2-\u0DD4"
    r"\u0DD6"
    r"\u0E31"
    r"\u0E34-\u0E3A"
    r"\u0E47-\u0E4E"
    r"\u0EB1"
    r"\u0EB4-\u0EBC"
    r"\u0EC8-\u0ECD"
    r"\u0F18-\u0F19"
    r"\u0F35"
    r"\u0F37"
    r"\u0F39"
    r"\u0F71-\u0F7E"
    r"\u0F80-\u0F84"
    r"\u0F86-\u0F87"
    r"\u0F8D-\u0F97"
    r"\u0F99-\u0FBC"
    r"\u0FC6"
    r"\u102D-\u1030"
    r"\u1032-\u1037"
    r"\u1039-\u103A"
    r"\u103D-\u103E"
    r"\u1058-\u1059"
    r"\u105E-\u1060"
    r"\u1071-\u1074"
    r"\u1082"
    r"\u1085-\u1086"
    r"\u108D"
    r"\u109D"
    r"\u135D-\u135F"
    r"\u1712-\u1714"
    r"\u1732-\u1734"
    r"\u1752-\u1753"
    r"\u1772-\u1773"
    r"\u17B4-\u17B5"
    r"\u17B7-\u17BD"
    r"\u17C6"
    r"\u17C9-\u17D3"
    r"\u17DD"
    r"\u180B-\u180D"
    r"\u1885-\u1886"
    r"\u18A9"
    r"\u1920-\u1922"
    r"\u1927-\u1928"
    r"\u1932"
    r"\u1939-\u193B"
    r"\u1A17-\u1A18"
    r"\u1A1B"
    r"\u1A56"
    r"\u1A58-\u1A5E"
    r"\u1A60"
    r"\u1A62"
    r"\u1A65-\u1A6C"
    r"\u1A73-\u1A7C"
    r"\u1A7F"
    r"\u1AB0-\u1ABD"
    r"\u1ABF-\u1AC0"
    r"\u1B00-\u1B03"
    r"\u1B34"
    r"\u1B36-\u1B3A"
    r"\u1B3C"
    r"\u1B42"
    r"\u1B6B-\u1B73"
    r"\u1B80-\u1B81"
    r"\u1BA2-\u1BA5"
    r"\u1BA8-\u1BA9"
    r"\u1BAB-\u1BAD"
    r"\u1BE6"
    r"\u1BE8-\u1BE9"
    r"\u1BED"
    r"\u1BEF-\u1BF1"
    r"\u1C2C-\u1C33"
    r"\u1C36-\u1C37"
    r"\u1CD0-\u1CD2"
    r"\u1CD4-\u1CE0"
    r"\u1CE2-\u1CE8"
    r"\u1CED"
    r"\u1CF4"
    r"\u1CF8-\u1CF9"
    r"\u1DC0-\u1DF9"
    r"\u1DFB-\u1DFF"
    r"\u20D0-\u20DC"
    r"\u20E1"
    r"\u20E5-\u20F0"
    r"\u2CEF-\u2CF1"
    r"\u2D7F"
    r"\u2DE0-\u2DFF"
    r"\u302A-\u302D"
    r"\u3099-\u309A"
    r"\uA66F"
    r"\uA674-\uA67D"
    r"\uA69E-\uA69F"
    r"\uA6F0-\uA6F1"
    r"\uA802"
    r"\uA806"
    r"\uA80B"
    r"\uA825-\uA826"
    r"\uA82C"
    r"\uA8C4-\uA8C5"
    r"\uA8E0-\uA8F1"
    r"\uA8FF"
    r"\uA926-\uA92D"
    r"\uA947-\uA951"
    r"\uA980-\uA982"
    r"\uA9B3"
    r"\uA9B6-\uA9B9"
    r"\uA9BC-\uA9BD"
    r"\uA9E5"
    r"\uAA29-\uAA2E"
    r"\uAA31-\uAA32"
    r"\uAA35-\uAA36"
    r"\uAA43"
    r"\uAA4C"
    r"\uAA7C"
    r"\uAAB0"
    r"\uAAB2-\uAAB4"
    r"\uAAB7-\uAAB8"
    r"\uAABE-\uAABF"
    r"\uAAC1"
    r"\uAAEC-\uAAED"
    r"\uAAF6"
    r"\uABE5"
    r"\uABE8"
    r"\uABED"
    r"\uFB1E"
    r"\uFE00-\uFE0F"
    r"\uFE20-\uFE2F"
    r"\U000101FD"
    r"\U000102E0"
    r"\U00010376-\U0001037A"
    r"\U00010A01-\U00010A03"
    r"\U00010A05-\U00010A06"
    r"\U00010A0C-\U00010A0F"
    r"\U00010A38-\U00010A3A"
    r"\U00010A3F"
    r"\U00010AE5-\U00010AE6"
    r"\U00010D24-\U00010D27"
    r"\U00010EAB-\U00010EAC"
    r"\U00010F46-\U00010F50"
    r"\U00011001"
    r"\U00011038-\U00011046"
    r"\U0001107F-\U00011081"
    r"\U000110B3-\U000110B6"
    r"\U000110B9-\U000110BA"
    r"\U00011100-\U00011102"
    r"\U00011127-\U0001112B"
    r"\U0001112D-\U00011134"
    r"\U00011173"
    r"\U00011180-\U00011181"
    r"\U000111B6-\U000111BE"
    r"\U000111C9-\U000111CC"
    r"\U000111CF"
    r"\U0001122F-\U00011231"
    r"\U00011234"
    r"\U00011236-\U00011237"
    r"\U0001123E"
    r"\U000112DF"
    r"\U000112E3-\U000112EA"
    r"\U00011300-\U00011301"
    r"\U0001133B-\U0001133C"
    r"\U00011340"
    r"\U00011366-\U0001136C"
    r"\U00011370-\U00011374"
    r"\U00011438-\U0001143F"
    r"\U00011442-\U00011444"
    r"\U00011446"
    r"\U0001145E"
    r"\U000114B3-\U000114B8"
    r"\U000114BA"
    r"\U000114BF-\U000114C0"
    r"\U000114C2-\U000114C3"
    r"\U000115B2-\U000115B5"
    r"\U000115BC-\U000115BD"
    r"\U000115BF-\U000115C0"
    r"\U000115DC-\U000115DD"
    r"\U00011633-\U0001163A"
    r"\U0001163D"
    r"\U0001163F-\U00011640"
    r"\U000116AB"
    r"\U000116AD"
    r"\U000116B0-\U000116B5"
    r"\U000116B7"
    r"\U0001171D-\U0001171F"
    r"\U00011722-\U00011725"
    r"\U00011727-\U0001172B"
    r"\U0001182F-\U00011837"
    r"\U00011839-\U0001183A"
    r"\U0001193B-\U0001193C"
    r"\U0001193E"
    r"\U00011943"
    r"\U000119D4-\U000119D7"
    r"\U000119DA-\U000119DB"
    r"\U000119E0"
    r"\U00011A01-\U00011A0A"
    r"\U00011A33-\U00011A38"
    r"\U00011A3B-\U00011A3E"
    r"\U00011A47"
    r"\U00011A51-\U00011A56"
    r"\U00011A59-\U00011A5B"
    r"\U00011A8A-\U00011A96"
    r"\U00011A98-\U00011A99"
    r"\U00011C30-\U00011C36"
    r"\U00011C38-\U00011C3D"
    r"\U00011C3F"
    r"\U00011C92-\U00011CA7"
    r"\U00011CAA-\U00011CB0"
    r"\U00011CB2-\U00011CB3"
    r"\U00011CB5-\U00011CB6"
    r"\U00011D31-\U00011D36"
    r"\U00011D3A"
    r"\U00011D3C-\U00011D3D"
    r"\U00011D3F-\U00011D45"
    r"\U00011D47"
    r"\U00011D90-\U00011D91"
    r"\U00011D95"
    r"\U00011D97"
    r"\U00011EF3-\U00011EF4"
    r"\U00016AF0-\U00016AF4"
    r"\U00016B30-\U00016B36"
    r"\U00016F4F"
    r"\U00016F8F-\U00016F92"
    r"\U00016FE4"
    r"\U0001BC9D-\U0001BC9E"
    r"\U0001D167-\U0001D169"
    r"\U0001D17B-\U0001D182"
    r"\U0001D185-\U0001D18B"
    r"\U0001D1AA-\U0001D1AD"
    r"\U0001D242-\U0001D244"
    r"\U0001DA00-\U0001DA36"
    r"\U0001DA3B-\U0001DA6C"
    r"\U0001DA75"
    r"\U0001DA84"
    r"\U0001DA9B-\U0001DA9F"
    r"\U0001DAA1-\U0001DAAF"
    r"\U0001E000-\U0001E006"
    r"\U0001E008-\U0001E018"
    r"\U0001E01B-\U0001E021"
    r"\U0001E023-\U0001E024"
    r"\U0001E026-\U0001E02A"
    r"\U0001E130-\U0001E136"
    r"\U0001E2EC-\U0001E2EF"
    r"\U0001E8D0-\U0001E8D6"
    r"\U0001E944-\U0001E94A"
    r"\U000E0100-\U000E01EF"
)
NON_SPACING_MARKS_REGEX = re.compile(f" (?=[{NON_SPACING_MARKS}])")
