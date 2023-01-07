import unittest

from gajim.gtk.util import get_first_grapheme


class Test(unittest.TestCase):
    def test_get_first_grapheme(self):
        self.assertEqual(
            get_first_grapheme(''), '', '<empty string>')
        self.assertEqual(
            get_first_grapheme('a'), 'a', 'a')
        self.assertEqual(
            get_first_grapheme('ab'), 'a', 'ab -> a')

        über = 'u\u0308ber'
        self.assertEqual(
            get_first_grapheme(über), 'u\u0308', über + ' -> ü')

        woman = '\U0001F469'
        zwj = '\u200D'
        vs16 = '\uFE0F'
        fitz4 = '\U0001F3FD'

        farmeress = f'{woman}{zwj}\U0001F33E{vs16}'
        self.assertEqual(
            get_first_grapheme(farmeress), farmeress, '👩‍🌾️')

        longass = f'{woman}{fitz4}{zwj}\u2764{vs16}{zwj}\U0001F468{fitz4}'
        self.assertEqual(
            get_first_grapheme(longass), longass, '👩🏽‍❤️‍👨🏽')

        # The following are from
        # https://www.unicode.org/reports/tr29/#Table_Sample_Grapheme_Clusters

        hangul_gag = '\u1100\u1161\u11A8'
        self.assertEqual(
            get_first_grapheme(hangul_gag), hangul_gag, '각')

        tamil_ni = '\u0BA8\u0BBF'
        self.assertEqual(
            get_first_grapheme(tamil_ni), tamil_ni, 'நி')

        # Fails 🤷 (returns the first char)
        # thai_kam = '\u0E01\u0E33'
        # self.assertEqual(
        #    get_first_grapheme(thai_kam), thai_kam, 'กำ')

        devanagari_ssi = '\u0937\u093F'
        self.assertEqual(
            get_first_grapheme(devanagari_ssi), devanagari_ssi, 'षि')

        # Only in some locales (e.g., Slovak):
        # self.assertEqual(
        #    get_first_grapheme('ch'), 'ch', 'ch -> ch')
        # Actually, Gtk.TextIter.forward_cursor_position() doesn't seem to use
        # tailored algorithms anyway, so even with LANG=sk_SK.UTF-8 this
        # returns 'c', not 'ch'.

        # In most locales (say, any western one):
        devanagari_kshi = '\u0915\u094D' + devanagari_ssi
        self.assertEqual(
            get_first_grapheme(devanagari_kshi), '\u0915\u094D', 'क्षि -> क् ')
        # This probably won't fail on *any* locale, ever, again because the
        # implementation doesn't seem locale-specific.


if __name__ == '__main__':
    unittest.main()
