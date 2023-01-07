
import sys
import unittest
from unittest.mock import patch

from gajim.common.helpers import sanitize_filename


class SanitizeTest(unittest.TestCase):
    '''Tests for the sanitize_filename function.'''

    @patch.object(sys, 'platform', 'win32')
    def test_invalid_chars(self):
        '''Make sure invalid characters are removed in filenames'''
        self.assertEqual(sanitize_filename('A/B/C'), 'ABC')
        self.assertEqual(sanitize_filename('A*C.d'), 'AC.d')
        self.assertEqual(sanitize_filename('A?C.d'), 'AC.d')

    @patch.object(sys, 'platform', 'win32')
    def test_invalid_suffix(self):
        '''Dots are not allowed at the end'''
        self.assertEqual(sanitize_filename('def.'), 'def')
        self.assertEqual(sanitize_filename('def.ghi'), 'def.ghi')
        self.assertTrue(sanitize_filename('X' * 1000 + '.').endswith('X'))

    @patch.object(sys, 'platform', 'win32')
    def test_reserved_words(self):
        '''Make sure reserved Windows words are prefixed'''
        self.assertEqual(sanitize_filename('NUL'), '__NUL')
        self.assertEqual(sanitize_filename('..'), '__')

    @patch.object(sys, 'platform', 'win32')
    def test_long_names(self):
        '''Make sure long names are truncated'''
        self.assertEqual(len(sanitize_filename('X' * 300)), 50)
        self.assertEqual(len(sanitize_filename(
            '.'.join(['X' * 100, 'X' * 100, 'X' * 100]))), 50)
        self.assertEqual(len(sanitize_filename(
            '.'.join(['X' * 300, 'X' * 300, 'X' * 300]))), 50)
        self.assertEqual(len(sanitize_filename('.' * 300 + '.txt')), 50)

    @patch.object(sys, 'platform', 'win32')
    def test_unicode_normalization(self):
        '''Names should be NFKD normalized'''
        self.assertEqual(sanitize_filename('ў'), chr(1091) + chr(774))

    @patch.object(sys, 'platform', 'win32')
    def test_extensions(self):
        '''Filename extensions should be preserved when possible.'''
        really_long_name = 'X' * 1000 + '.pdf'
        self.assertTrue(sanitize_filename(really_long_name).endswith('.pdf'))
        self.assertTrue(sanitize_filename('X' * 1000).endswith('X'))
        self.assertTrue(sanitize_filename(
            'X' * 100 + '.' + 'X' * 100 + '.pdf').endswith('.pdf'))
        self.assertTrue(sanitize_filename(
            'X' * 100 + '.' + 'X' * 400).endswith('X'))
        self.assertTrue(sanitize_filename(
            'X' * 100 + '.' + 'X' * 400 + '.pdf').endswith('.pdf'))


if __name__ == '__main__':
    unittest.main()
