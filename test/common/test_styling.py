import unittest
from unittest.mock import MagicMock

from gajim.common import app  # Avoids circular imports from common.helpers
from gajim.common import styling
from gajim.common.styling import EmphasisSpan
from gajim.common.styling import Hyperlink
from gajim.common.styling import PlainBlock
from gajim.common.styling import PreBlock
from gajim.common.styling import PreTextSpan
from gajim.common.styling import process_uris
from gajim.common.styling import QuoteBlock
from gajim.common.styling import StrikeSpan
from gajim.common.styling import StrongSpan
from gajim.common.util.text import escape_iri_query

app.settings = MagicMock()
# additional_uri_schemes
app.settings.get = MagicMock(return_value='a a- a. scheme')

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
                Hyperlink(start=18, start_byte=18, end=42, end_byte=42, text='http://foo.com/blah_blah', uri='http://foo.com/blah_blah')
            ])
        ]
    },

    'plain with uri don’t consider comma': {
        'input': 'some kind of link http://foo.com/blah_blah,',
        'tokens': [
            PlainBlock(start=0, end=43, text='some kind of link http://foo.com/blah_blah,', spans=[], uris=[
                Hyperlink(start=18, start_byte=18, end=42, end_byte=42, text='http://foo.com/blah_blah', uri='http://foo.com/blah_blah')
            ])
        ]
    },

    'plain with uri and styling': {
        'input': 'some *kind* of link http://foo.com/blah_blah',
        'tokens': [
            PlainBlock(start=0, end=44, text='some *kind* of link http://foo.com/blah_blah', spans=[
                StrongSpan(start=5, start_byte=5, end=11, end_byte=11, text='*kind*')
            ], uris=[
                Hyperlink(start=20, start_byte=20, end=44, end_byte=44, text='http://foo.com/blah_blah', uri='http://foo.com/blah_blah')
            ])
        ]
    },

    'plain with multiple uris': {
        'input': 'some http://foo.com/blah_blah and http://foo.com/blah_blah/123',
        'tokens': [
            PlainBlock(start=0, end=62, text='some http://foo.com/blah_blah and http://foo.com/blah_blah/123', spans=[], uris=[
                Hyperlink(start=5, start_byte=5, end=29, end_byte=29, text='http://foo.com/blah_blah', uri='http://foo.com/blah_blah'),
                Hyperlink(start=34, start_byte=34, end=62, end_byte=62, text='http://foo.com/blah_blah/123', uri='http://foo.com/blah_blah/123')
            ])
        ]
    },

}


# Most of the URI/JID test sets belong in test_regex.py, and should be imported
# here somehow (TODO).
URIS = [
    'a:b',
    'a-:b',
    'a.:b',
    'xmpp:conference.gajim.org',
    'xmpp:asd@at',
    'xmpp:asd@asd.at',
    'xmpp:asd-asd@asd.asdasd.at.',
    'xmpp:me@%5B::1%5D',
    'xmpp:myself@127.13.42.69',
    'xmpp:myself@127.13.42.69/localhost',
    'xmpp:%23room%25irc.example@biboumi.xmpp.example',
    'xmpp:+15551234567@cheogram.com',
    'xmpp:romeo@montague.net?message;subject=Test%20Message;body=Here%27s%20a%20test%20message',
    'geo:1,2',
    'geo:1,2,3',
    'file:/foo/bar/baz',  # xffm
    'file:///foo/bar/baz',  # nautilus, rox
    'file:///x:/foo/bar/baz',  # windows
    'file://localhost/foo/bar/baz',
    'file://nonlocalhost/foo/bar/baz',
    'about:ambiguous-address?a@b.c',

    # These seem to be from https://mathiasbynens.be/demo/url-regex
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
    "http://-.~_!$&'()*+,;=:%40:80%2f::::::@example.com",
    'http://1337.net',
    'http://a.b-c.de',
    'http://223.255.255.254',

    'https://foo_bar.example.com/',

    # These are from https://rfc-editor.org/rfc/rfc3513#section-2.2
    'http://[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]',
    'http://[1080:0:0:0:8:800:200C:417A]',
    'http://[1080:0:0:0:8:800:200C:417A]',
    'http://[FF01:0:0:0:0:0:0:101]',
    'http://[0:0:0:0:0:0:0:1]',
    'http://[0:0:0:0:0:0:0:0]',
    'http://[1080::8:800:200C:417A]',
    'http://[FF01::101]',
    'http://[::1]',
    'http://[::]',
    'http://[0:0:0:0:0:0:13.1.68.3]',
    'http://[0:0:0:0:0:FFFF:129.144.52.38]',
    'http://[::13.1.68.3]',
    'http://[::FFFF:129.144.52.38]',

    # These are from https://rfc-editor.org/rfc/rfc3986#section-1.1.2
    'ftp://ftp.is.co.za/rfc/rfc1808.txt',
    'http://www.ietf.org/rfc/rfc2396.txt',
    'ldap://[2001:db8::7]/c=GB?objectClass?one',
    'mailto:John.Doe@example.com',
    'news:comp.infosystems.www.servers.unix',
    'tel:+1-816-555-1212',
    'telnet://192.0.2.16:80/',
    'urn:oasis:names:specification:docbook:dtd:xml:4.1.2',
]


# * non-URI foos
# * non-absolute URIs
NONURIS = [
    '',
    ' ',
    '.',
    ':',
    '://',
    'Böblingen:🌥',
    'Bo\u0308blingen:🌥',  # finds blingen:🌥 but rejects an unregistered scheme
    'path/to/file_na.me:123',
    '_sche.me:body_',
    '_sche+me:body_',
    '.scheme:body',
    '+scheme:body',

    # These are from https://mathiasbynens.be/demo/url-regex
    '//',
    '//a',
    '///a',
    '///',
    'foo.com',
]


# * valid scheme-only URIs
# * valid generic URIs that fail requirements of their specific scheme.
UNACCEPTABLE_URIS = [
    'scheme:',

    # These are from https://mathiasbynens.be/demo/url-regex
    'http://',
    'http://?',
    'http://??',
    'http://??/',
    'http://#',
    'http://##',
    'http://##/',
    'http:///a',

    'geo:1,',
    'geo:,2',
    # 'geo:1,2,',  FIXME: wrongly parsed as valid
    'geo:1,,3',
    'geo:,2,3',
    'geo:1,,',
    'geo:,2,',
    'geo:,,3',
    'geo:,,',

    'file:',
    'file:a',
    'file:a/',
    'file:a/b',

    'about:',
    'about:asdfasdf',
    'about:ambiguous-address',
    'about:ambiguous-address?',

    'mailtomailto:foo@bar.com.uk',
]


JIDS = [
    'asd@at',
    'asd@asd.at',
    'asd@asd.asd.at',
    'asd@asd.asd-asd.at',
    'asd.asd@asd.asd-asd.at',
    'asd-asd@asd.asdasd.at',
    'asd-asd@asd.asdasd.at.',
    'me@[::1]',
    'myself@127.13.42.69',
    '#room%irc.example@biboumi.xmpp.example',
    '+15551234567@cheogram.com',

    # These are from https://rfc-editor.org/rfc/rfc7622#section-3.5
    'fußball@example.com',
    'π@example.com',

    # These are from https://xmpp.org/extensions/xep-0106.html#examples
    r'space\20cadet@example.com',
    r'call\20me\20\22ishmael\22@example.com',
    r'at\26t\20guy@example.com',
    r'd\27artagnan@example.com',
    r'\2f.fanboy@example.com',
    r'\3a\3afoo\3a\3a@example.com',
    r'\3cfoo\3e@example.com',
    r'user\40host@example.com',
    r'c\3a\net@example.com',
    r'c\3a\\net@example.com',
    r'c\3a\cool\20stuff@example.com',
    r'c\3a\5c5commas@example.com',
    r'here\27s_a_wild_\26_\2fcr%zy\2f_address@example.com',
    r'here\27s_a_wild_\26_\2fcr%zy\2f_address_for\3a\3cwv\3e(\22IMPS\22)@example.com',
    # Some more from the same document
    r'tréville\40musketeers.lit@smtp.gascon.fr',
    r'\5c3and\2is\5c5cool@example.com',
    r'CN=D\27Artagnan\20Saint-Andr\E9,O=Example\20\26\20Company,\20Inc.,DC=example,DC=com@st.example.com',
    r'somenick!user\22\26\27\2f\3a\3c\3e\5c3address@example.com',

    # https://en.wikipedia.org/wiki/E-mail_address#Internationalization_examples
    # Do note that these are *e-mail* addresses and might not all be valid JIDs.
    'Pelé@example.com',
    'δοκιμή@παράδειγμα.δοκιμή',
    '我買@屋企.香港',
    '二ノ宮@黒川.日本',
    'медведь@с-балалайкой.рф',
    # 'संपर्क@डाटामेल.भारत',  fails because of the 2 combining chars in localpart
]

NONJIDS = [
    '',
    '@',

    # These are from https://rfc-editor.org/rfc/rfc7622#section-3.5
    '"juliet"@example.com',
    '@example.com',
    'henryⅣ@example.com',  # localpart has a compatibility-decomposable cp
    '♚@example.com',        # localpart has a symbol cp
    'juliet@',
]


URIS_WITH_TEXT = [
    ('write to my email mailto:foo@bar.com.uk (but not to mailto:bar@foo.com)',
     ['mailto:foo@bar.com.uk', 'mailto:bar@foo.com']),
    ('see this http://userid@example.com/ link', ['http://userid@example.com/']),
    ('see this http://userid@example.com/, and ..', ['http://userid@example.com/']),
    ('<http://userid@example.com/>', ['http://userid@example.com/']),
    ('"http://userid@example.com/"', ['http://userid@example.com/']),
    ('regexes are useless (see https://en.wikipedia.org/wiki/Recursion_(computer_science)), but comfy', ['https://en.wikipedia.org/wiki/Recursion_(computer_science)']),
    ('(scheme:body)', ['scheme:body']),
    ('/scheme:body', ['scheme:body']),
    ('!scheme:body', ['scheme:body']),
]


class Test(unittest.TestCase):
    @staticmethod
    def wrap(link: str) -> str:
        return f'Prologue (link: {link}), and epilogue!'

    def test_styling(self):
        for _name, params in STYLING.items():
            result = styling.process(params['input'])
            self.assertEqual(result.blocks, params['tokens'])

    def test_uris(self):
        for uri in URIS:
            text = self.wrap(uri)
            hlinks = process_uris(text)
            self.assertEqual([link.uri for link in hlinks], [uri], text)

    def test_invalid_uris(self):
        for foo in NONURIS + UNACCEPTABLE_URIS:
            text = self.wrap(foo)
            hlinks = process_uris(text)
            self.assertEqual([link.text for link in hlinks], [], text)

    def test_jids(self):
        for jidlike in JIDS:
            text = self.wrap(jidlike)
            uri = 'about:ambiguous-address?' + escape_iri_query(jidlike)
            hlinks = process_uris(text)
            self.assertEqual([(link.text, link.uri) for link in hlinks],
                             [(jidlike, uri)], text)

    def test_nonjids(self):
        for foo in NONJIDS:
            text = self.wrap(foo)
            hlinks = process_uris(text)
            self.assertEqual([link.text for link in hlinks], [], text)

    def test_uris_with_text(self):
        for text, results in URIS_WITH_TEXT:
            hlinks = process_uris(text)
            self.assertEqual([link.text for link in hlinks], results, text)


if __name__ == '__main__':
    unittest.main()
