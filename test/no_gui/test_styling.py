import unittest

import gajim.common.styling as styling
from gajim.common.styling import PlainBlock
from gajim.common.styling import PreBlock
from gajim.common.styling import QuoteBlock
from gajim.common.styling import PreTextSpan
from gajim.common.styling import StrongSpan
from gajim.common.styling import EmphasisSpan
from gajim.common.styling import StrikeSpan
from gajim.common.styling import Uri
from gajim.common.styling import URI_RX
from gajim.common.styling import ADDRESS_RX


STYLING = {
    'pre cannot have children':  {
        'input': '_no pre `with *children*`_',
        'tokens': [
            PlainBlock(start=0, end=26, text='_no pre `with *children*`_', spans=[
                PreTextSpan(start=8, start_byte=8, end=25, end_byte=25, text='`with *children*`'),
                EmphasisSpan(start=0, start_byte=0, end=26, end_byte=26, text='_no pre `with *children*`_')
            ])
        ]
    },

    'nested spans':  {
        'input': '_*~children~*_',
        'tokens': [
            PlainBlock(start=0, end=14, text='_*~children~*_', spans=[
                StrikeSpan(start=2, start_byte=2, end=12, end_byte=12, text='~children~'),
                StrongSpan(start=1, start_byte=1, end=13, end_byte=13, text='*~children~*'),
                EmphasisSpan(start=0, start_byte=0, end=14, end_byte=14, text='_*~children~*_'),
            ])
        ]
    },

    'spans': {
        'input': '*strong* _emph_~strike~  `pre`',
        'tokens': [
            PlainBlock(start=0, end=30, text='*strong* _emph_~strike~  `pre`', spans=[
                StrongSpan(start=0, start_byte=0, end=8, end_byte=8, text='*strong*'),
                EmphasisSpan(start=9, start_byte=9, end=15, end_byte=15, text='_emph_'),
                StrikeSpan(start=15, start_byte=15, end=23, end_byte=23, text='~strike~'),
                PreTextSpan(start=25, start_byte=25, end=30, end_byte=30, text='`pre`')
            ])
        ]
    },

    'spans lazily match': {
        'input': '*strong*plain*',
        'tokens': [
            PlainBlock(start=0, end=14, text='*strong*plain*', spans=[
                StrongSpan(start=0, start_byte=0, end=8, end_byte=8, text='*strong*')
            ])
        ]
    },

    'start span only': {
        'input': '*not strong',
        'tokens': [
            PlainBlock(start=0, end=11, text='*not strong', spans=[])
        ]
    },

    'byte pos is different': {
        'input': '*ö* *öö*',
        'tokens': [
            PlainBlock(start=0, end=8, text='*ö* *öö*', spans=[
                StrongSpan(start=0, start_byte=0, end=3, end_byte=4, text='*ö*'),
                StrongSpan(start=4, start_byte=5, end=8, end_byte=11, text='*öö*')
            ])
        ]
    },

    'byte pos is different with multiple blocks': {
        'input': '```\npre\n```\n*pláin*',
        'tokens': [
            PreBlock(start=0, end=12, text='```\npre\n```\n'),
            PlainBlock(start=12, end=19, text='*pláin*', spans=[
                StrongSpan(start=0, start_byte=0, end=7, end_byte=8, text='*pláin*')
            ])
        ]
    },

    'end span only': {
        'input': 'not strong*',
        'tokens': [
            PlainBlock(start=0, end=11, text='not strong*', spans=[])
        ]
    },

    'invalid end span': {
        'input': '*not *strong',
        'tokens': [
            PlainBlock(start=0, end=12, text='*not *strong', spans=[])
        ]
    },

    'empty span': {
        'input': '**',
        'tokens': [
            PlainBlock(start=0, end=2, text='**', spans=[])
        ]
    },

    '3 unmatched directives': {
        'input': '***',
        'tokens': [
            PlainBlock(start=0, end=3, text='***', spans=[])
        ]
    },

    '4 unmatched directives': {
        'input': '****',
        'tokens': [
            PlainBlock(start=0, end=4, text='****', spans=[])
        ]
    },

    'invalid diretives ignored': {
        'input': '* plain *strong*',
        'tokens': [
            PlainBlock(start=0, end=16, text='* plain *strong*', spans=[
                StrongSpan(start=8, start_byte=8, end=16, end_byte=16, text='*strong*')
            ])
        ]
    },

    'uneven start directives': {
        'input': '*this is *uneven*',
        'tokens': [
            PlainBlock(start=0, end=17, text='*this is *uneven*', spans=[
                StrongSpan(start=9, start_byte=9, end=17, end_byte=17, text='*uneven*')
            ])
        ]
    },

    'overlapping directives': {
        'input': '*this cannot _overlap*_',
        'tokens': [
            PlainBlock(start=0, end=23, text='*this cannot _overlap*_', spans=[
                StrongSpan(start=0, start_byte=0, end=22, end_byte=22, text='*this cannot _overlap*')
            ])
        ]
    },

    'plain blocks': {
        'input': 'one\nand two',
        'tokens': [
            PlainBlock(start=0, end=11, text='one\nand two', spans=[])
        ]
    },

    'pre block with closing': {
        'input': '```\npre *fmt* ```\n```\nplain',
        'tokens': [
            PreBlock(start=0, end=22, text='```\npre *fmt* ```\n```\n'),
            PlainBlock(start=22, end=27, text='plain', spans=[])
        ]
    },

    'pre block EOF': {
        'input': '````\na\n```',
        'tokens': [
            PreBlock(start=0, end=10, text='````\na\n```')
        ]
    },

    'pre block no terminator EOF': {
        'input': '```\na```',
        'tokens': [
            PlainBlock(start=0, end=8, text='```\na```', spans=[])
        ]
    },

    'pre block no body EOF': {
        'input': '```newtoken\n',
        'tokens': [
            PlainBlock(start=0, end=12, text='```newtoken\n', spans=[])
        ]
    },

    'single level block quote': {
        'input': '>  quoted\nnot quoted',
        'tokens': [
            QuoteBlock(start=0, end=10, text='>  quoted\n', blocks=[
                PlainBlock(start=0, end=8, text=' quoted\n', spans=[])
            ]),
            PlainBlock(start=10, end=20, text='not quoted', spans=[])
        ]
    },

    'multi level block quote': {
        'input': '>  quoted\n>>   quote > 2\n>quote 1\n\nnot quoted',
        'tokens': [
            QuoteBlock(start=0, end=34, text='>  quoted\n>>   quote > 2\n>quote 1\n', blocks=[
                PlainBlock(start=0, end=8, text=' quoted\n', spans=[]),
                QuoteBlock(start=8, end=22, text='>   quote > 2\n', blocks=[
                    PlainBlock(start=0, end=12, text='  quote > 2\n', spans=[])
                ]),
                PlainBlock(start=22, end=30, text='quote 1\n', spans=[])
            ]),
            PlainBlock(start=34, end=45, text='\nnot quoted', spans=[])
        ]
    },

    'quote start then EOF': {
        'input': '> ',
        'tokens': [
            QuoteBlock(start=0, end=2, text='> ', blocks=[])
        ]
    },

    'quote with children': {
        'input': '> ```\n> pre\n> ```\n> not pre',
        'tokens': [
            QuoteBlock(start=0, end=27, text='> ```\n> pre\n> ```\n> not pre', blocks=[
                PreBlock(start=0, end=12, text='```\npre\n```\n'),
                PlainBlock(start=12, end=19, text='not pre', spans=[])
            ])
        ]
    },

    'pre end of parent': {
        'input': '> ``` \n> pre\nplain',
        'tokens': [
            QuoteBlock(start=0, end=13, text='> ``` \n> pre\n', blocks=[
                PreBlock(start=0, end=9, text='``` \npre\n')
            ]),
            PlainBlock(start=13, end=18, text='plain', spans=[])
        ]
    },

    'span lines': {
        'input': '*not \n strong*',
        'tokens': [
            PlainBlock(start=0, end=14, text='*not \n strong*', spans=[])
        ]
    },

    'plain with uri': {
        'input': 'some kind of link http://foo.com/blah_blah',
        'tokens': [
            PlainBlock(start=0, end=42, text='some kind of link http://foo.com/blah_blah', spans=[], uris=[
                Uri(start=18, start_byte=18, end=42, end_byte=42, text='http://foo.com/blah_blah')
            ])
        ]
    },

    'plain with uri don’t consider comma': {
        'input': 'some kind of link http://foo.com/blah_blah,',
        'tokens': [
            PlainBlock(start=0, end=43, text='some kind of link http://foo.com/blah_blah,', spans=[], uris=[
                Uri(start=18, start_byte=18, end=42, end_byte=42, text='http://foo.com/blah_blah')
            ])
        ]
    },

    'plain with uri and styling': {
        'input': 'some *kind* of link http://foo.com/blah_blah',
        'tokens': [
            PlainBlock(start=0, end=44, text='some *kind* of link http://foo.com/blah_blah', spans=[
                StrongSpan(start=5, start_byte=5, end=11, end_byte=11, text='*kind*')
            ], uris=[
                Uri(start=20, start_byte=20, end=44, end_byte=44, text='http://foo.com/blah_blah')
            ])
        ]
    },

    'plain with multiple uris': {
        'input': 'some http://foo.com/blah_blah and http://foo.com/blah_blah/123',
        'tokens': [
            PlainBlock(start=0, end=62, text='some http://foo.com/blah_blah and http://foo.com/blah_blah/123', spans=[], uris=[
                Uri(start=5, start_byte=5, end=29, end_byte=29, text='http://foo.com/blah_blah'),
                Uri(start=34, start_byte=34, end=62, end_byte=62, text='http://foo.com/blah_blah/123')
            ])
        ]
    },

}


URLS = [
    'http://foo.com/blah_blah',
    'http://foo.com/blah_blah/',
    'http://foo.com/blah_blah_(wikipedia)',
    'http://foo.com/blah_blah_(wikipedia)_(again)',
    'http://www.example.com/wpstyle/?p=364',
    'https://www.example.com/foo/?bar=baz&inga=42&quux',
    'http://✪df.ws/123',
    'http://userid:password@example.com:8080',
    'http://userid:password@example.com:8080/',
    'http://userid@example.com',
    'http://userid@example.com/',
    'http://userid@example.com:8080',
    'http://userid@example.com:8080/',
    'http://userid:password@example.com',
    'http://userid:password@example.com/',
    'http://142.42.1.1/',
    'http://142.42.1.1:8080/',
    'http://➡.ws/䨹',
    'http://⌘.ws',
    'http://⌘.ws/',
    'http://foo.com/blah_(wikipedia)#cite-1',
    'http://foo.com/blah_(wikipedia)_blah#cite-1',
    'http://foo.com/unicode_(✪)_in_parens',
    'http://foo.com/(something)?after=parens',
    'http://☺.damowmow.com/',
    'http://code.google.com/events/#&product=browser',
    'http://j.mp',
    'ftp://foo.bar/baz',
    'http://foo.bar/?q=Test%20URL-encoded%20stuff',
    'http://مثال.إختبار',
    'http://例子.测试',
    'http://उदाहरण.परीक्षा',
    'http://-.~_!$&\'()*+,;=:%40:80%2f::::::@example.com',
    'http://1337.net',
    'http://a.b-c.de',
    'http://223.255.255.254',
    'https://foo_bar.example.com/',
]


EMAILS = [
    'asd@asd.at',
    'asd@asd.asd.at',
    'asd@asd.asd-asd.at',
    'asd-asd@asd.asdasd.at',
    'mailto:foo@bar.com.uk',
]

EMAILS_WITH_TEXT = [
    ('write to my email mailto:foo@bar.com.uk (but not to mailto:bar@foo.com)',
     ['mailto:foo@bar.com.uk', 'mailto:bar@foo.com']),
    ('write to my email mailtomailto:foo@bar.com.uk (but not to mailto:bar@foo.com)',
     ['foo@bar.com.uk', 'mailto:bar@foo.com']),
]


URL_WITH_TEXT = [
    ('see this http://userid@example.com/ link', 'http://userid@example.com/'),
    ('see this http://userid@example.com/, and ..', 'http://userid@example.com/'),
    ('<http://userid@example.com/>', 'http://userid@example.com/'),
]

XMPP_URIS = [
    ('see xmpp:romeo@montague.net?message;subject=Test%20Message;body=Here%27s%20a%20test%20message ...', 'xmpp:romeo@montague.net?message;subject=Test%20Message;body=Here%27s%20a%20test%20message'),
]


class Test(unittest.TestCase):
    def test_styling(self):
        for _name, params in STYLING.items():
            result = styling.process(params['input'])
            self.assertTrue(result.blocks == params['tokens'])

    def test_urls(self):
        for url in URLS:
            match = URI_RX.search(url)
            self.assertIsNotNone(match)
            start = match.start()
            end = match.end()
            self.assertTrue(url[start:end] == url)

    def test_emails(self):
        for email in EMAILS:
            match = ADDRESS_RX.search(email)
            self.assertIsNotNone(match)
            start = match.start()
            end = match.end()
            self.assertTrue(email[start:end] == email)

    def test_emails_with_text(self):
        for text, result in EMAILS_WITH_TEXT:
            match = ADDRESS_RX.findall(text)
            self.assertIsNotNone(match)
            for i, res in enumerate(result):
                self.assertTrue(match[i][0] == res)

    def test_url_with_text(self):
        for text, result in URL_WITH_TEXT:
            match = URI_RX.search(text)
            self.assertIsNotNone(match)
            start = match.start()
            end = match.end()
            self.assertTrue(text[start:end] == result)

    def test_xmpp_uris(self):
        for text, result in XMPP_URIS:
            match = ADDRESS_RX.search(text)
            self.assertIsNotNone(match)
            start = match.start()
            end = match.end()
            self.assertTrue(text[start:end] == result)


if __name__ == "__main__":
    unittest.main()
