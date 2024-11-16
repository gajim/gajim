# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from gajim.common.util.text import escape_iri_path_segment
from gajim.common.util.text import format_bytes_as_hex
from gajim.common.util.text import format_duration
from gajim.common.util.text import jid_to_iri
from gajim.common.util.text import remove_invalid_xml_chars


class Test(unittest.TestCase):

    def test_remove_invalid_xml_chars(self) -> None:
        invalid_chars = [
            '\x0b',
            '\udfff',
            '\x08'
        ]
        for char in invalid_chars:
            self.assertEqual(remove_invalid_xml_chars(char), '')

        self.assertEqual(remove_invalid_xml_chars(''), '')
        self.assertEqual(remove_invalid_xml_chars('ä'), 'ä')

    def test_escape_iri_path_segment(self) -> None:
        self.assertEqual(escape_iri_path_segment(''), '', '<empty string>')

        ueber = 'u\u0308ber'
        self.assertEqual(escape_iri_path_segment(ueber), ueber)

        segment = ''.join(chr(c) for c in range(0x20, 0x7F))
        self.assertEqual(
            escape_iri_path_segment(segment),
            "%20!%22%23$%25&'()*+,-.%2F0123456789:;%3C=%3E%3F@ABCDEFGHIJKLMN"
            'OPQRSTUVWXYZ%5B%5C%5D%5E_%60abcdefghijklmnopqrstuvwxyz%7B%7C%7D~',
            'ASCII printable')

        self.assertEqual(escape_iri_path_segment(
            ''.join(chr(c) for c in range(0x01, 0x20)) + chr(0x7F)),
            ''.join('%%%02X' % c for c in range(0x01, 0x20)) + '%7F',
            'ASCII control (no null)')

    def test_jid_to_iri(self) -> None:
        jid = r'foo@bar'
        self.assertEqual(jid_to_iri(jid), fr'xmpp:{jid}', jid)
        jid = r'my\20self@[::1]/home'
        self.assertEqual(
            jid_to_iri(jid),
            r'xmpp:my%5C20self@%5B::1%5D/home', jid)

    def test_format_duration_width(self) -> None:
        def do(total_seconds: float, expected: str) -> None:
            self.assertEqual(format_duration(0.0, total_seconds*1e9), expected)

        do(0, '0:00')
        do(60, '0:00')
        do(10 * 60, '00:00')
        do(60 * 60, '0:00:00')
        do(10 * 60 * 60, '00:00:00')
        do(100 * 60 * 60, '000:00:00')

    def test_format_duration(self) -> None:
        def do(duration: float, expected: str) -> None:
            self.assertEqual(
                format_duration(duration, 100 * 60 * 60 * 1e9),
                expected)

        do(1.0, '000:00:00')
        do(999999999.0, '000:00:00')
        do(1000000000.0, '000:00:01')
        do(59999999999.0, '000:00:59')
        do(60000000000.0, '000:01:00')
        do(3599999999999.0, '000:59:59')
        do(3600000000000.0, '001:00:00')
        do(3599999999999999.0, '999:59:59')

    def test_format_bytes_as_hex(self) -> None:
        tests = [
            (b'U\xe9\xf4\xd6~\x17\xa6\xdf]\xc7\xfe\x9a\x01\r\x8b\xea\xfd\x8f@.',
             '55:E9:F4:D6:7E:17:A6:DF:5D:C7\nFE:9A:01:0D:8B:EA:FD:8F:40:2E'),
        ]

        for test in tests:
            bytes_, string = test
            hex_string = format_bytes_as_hex(bytes_, 2)
            self.assertEqual(hex_string, string)


if __name__ == '__main__':
    unittest.main()
