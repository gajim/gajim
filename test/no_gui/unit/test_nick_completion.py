import unittest

from gajim.gui.util import NickCompletionGenerator

class Test(unittest.TestCase):

    def test_generate_suggestions(self):
        gen = NickCompletionGenerator('meeeee')

        l = ['aaaa', 'meeeee', 'fooo', 'xxxxz', 'xaaaz']
        for n in l:
            gen.record_message(n, False)
        l2 = ['xxx'] + l
        r = gen.generate_suggestions(nicks=l2, beginning='x')
        self.assertEqual(r, ['xaaaz', 'xxxxz', 'xxx'])

        r = gen.generate_suggestions(
            nicks=l2,
            beginning='m'
            )
        self.assertEqual(r, [])

        for n in ['xaaaz', 'xxxxz']:
            gen.record_message(n, True)

        r = gen.generate_suggestions(
            nicks=l2,
            beginning='x'
            )
        self.assertEqual(r, ['xxxxz', 'xaaaz', 'xxx'])
        r = gen.generate_suggestions(
            nicks=l2,
            beginning=''
            )
        self.assertEqual(r, ['xxxxz', 'xaaaz', 'aaaa', 'fooo', 'xxx'])

        l2[1] = 'bbbb'
        gen.contact_renamed('aaaa', 'bbbb')
        r = gen.generate_suggestions(
            nicks=l2,
            beginning=''
            )
        self.assertEqual(r, ['xxxxz', 'xaaaz', 'bbbb', 'fooo', 'xxx'])



if __name__ == "__main__":
    unittest.main()
