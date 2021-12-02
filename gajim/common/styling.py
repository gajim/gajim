import string
import re
from dataclasses import dataclass
from dataclasses import field

PRE = '`'
STRONG = '*'
STRIKE = '~'
EMPH = '_'

QUOTE = '> '
PRE_TEXT = '```'

WHITESPACE = set(string.whitespace)
BLOCK_DIRS = set([QUOTE, PRE_TEXT])
SPAN_DIRS = set([PRE, STRONG, STRIKE, EMPH])
VALID_SPAN_START = WHITESPACE | SPAN_DIRS

SD = 0
SD_POS = 1

PRE_RX = r'(?P<pre>^```.+?(^```$(.|\Z)))'
PRE_NESTED_RX = r'(?P<pre>^```.+?((^```$(.|\Z))|\Z))'
QUOTE_RX = r'(?P<quote>^(?=>).*?(^|\Z)(?!>))'

BLOCK_RX = re.compile(PRE_RX + '|' + QUOTE_RX, re.S | re.M)
BLOCK_NESTED_RX = re.compile(PRE_NESTED_RX + '|' + QUOTE_RX, re.S | re.M)
UNQUOTE_RX = re.compile(r'^> |^>', re.M)

URI_RX = r'((?P<protocol>[\w-]+://?|www[.])[\S()<>]+?(?=[,]?(\s|\Z)+))'
URI_RX = re.compile(URI_RX)

ADDRESS_RX = r'(\b(?P<protocol>(xmpp|mailto)+:)?[\w-]*@(.*?\.)+[\w]+([\?].*?(?=([\s\),]|$)))?)'
ADDRESS_RX = re.compile(ADDRESS_RX)


@dataclass
class StyleObject:
    start: int
    end: int
    text: str


class URIMarkup:
    def get_markup_string(self):
        return f'<a href="{self.text}">{self.text}</a>'


@dataclass
class Uri(StyleObject, URIMarkup):
    name: str = field(default='uri', init=False)


@dataclass
class Address(StyleObject, URIMarkup):
    name: str = field(default='address', init=False)


@dataclass
class XMPPAddress(StyleObject, URIMarkup):
    name: str = field(default='xmppadr', init=False)


@dataclass
class MailAddress(StyleObject, URIMarkup):
    name: str = field(default='mailadr', init=False)


@dataclass
class Block(StyleObject):

    @classmethod
    def from_match(cls, match):
        return cls(start=match.start(),
                   end=match.end(),
                   text=str(match.group(cls.name)))


@dataclass
class PlainBlock(Block):
    name: str = field(default='plain', init=False)
    spans: list = field(default_factory=list)
    uris: list = field(default_factory=list)


@dataclass
class PreBlock(Block):
    name: str = field(default='pre', init=False)


@dataclass
class QuoteBlock(Block):
    name: str = field(default='quote', init=False)
    blocks: list = field(default_factory=list)

    def unquote(self):
        return UNQUOTE_RX.sub('', self.text)


@dataclass
class PlainSpan(StyleObject):
    name: str = field(default='plain', init=False)


@dataclass
class StrongSpan(StyleObject):
    name: str = field(default='strong', init=False)


@dataclass
class EmphasisSpan(StyleObject):
    name: str = field(default='emphasis', init=False)


@dataclass
class PreTextSpan(StyleObject):
    name: str = field(default='pre', init=False)


@dataclass
class StrikeSpan(StyleObject):
    name: str = field(default='strike', init=False)


SPAN_CLS_DICT = {
    STRONG: StrongSpan,
    EMPH: EmphasisSpan,
    PRE: PreTextSpan,
    STRIKE: StrikeSpan
}


@dataclass
class ParsingResult:
    text: str
    blocks: list


def process(text, nested=False):
    blocks = _parse_blocks(text, nested)
    for block in blocks:
        if isinstance(block, PlainBlock):
            offset = 0
            for line in block.text.splitlines(keepends=True):
                block.spans += _parse_line(line, offset)
                block.uris += _parse_uris(line, offset)
                offset += len(line)

        if isinstance(block, QuoteBlock):
            result = process(block.unquote(), nested=True)
            block.blocks = result.blocks

    return ParsingResult(text, blocks)


def _parse_blocks(text, nested):
    blocks = []
    text_len = len(text)
    last_end_pos = 0

    rx = BLOCK_NESTED_RX if nested else BLOCK_RX

    for match in rx.finditer(text):
        if match.start() != last_end_pos:
            blocks.append(PlainBlock(start=last_end_pos,
                                     end=match.start(),
                                     text=text[last_end_pos:match.start()]))

        last_end_pos = match.end()
        group_dict = match.groupdict()

        if group_dict.get('quote') is not None:
            blocks.append(QuoteBlock.from_match(match))

        if group_dict.get('pre') is not None:
            blocks.append(PreBlock.from_match(match))

    if last_end_pos != text_len:
        blocks.append(PlainBlock(start=last_end_pos,
                                 end=text_len,
                                 text=text[last_end_pos:]))
    return blocks


def _parse_line(line, offset):
    index = 0
    length = len(line)
    stack = []
    spans = []

    while index < length:
        sd = line[index]
        if sd not in SPAN_DIRS:
            index += 1
            continue

        is_valid_start = _is_valid_span_start(line, index)
        is_valid_end = _is_valid_span_end(line, index)

        if is_valid_start and is_valid_end:
            # Favor end over new start, this means parsing is done non-greedy
            if sd in [open_sd for open_sd, _ in stack]:
                is_valid_start = False

        if is_valid_start:
            if sd == PRE:
                index = _handle_pre_span(line, index, offset, spans)
                continue

            stack.append((sd, index))
            index += 1
            continue

        if is_valid_end:
            if sd not in [open_sd for open_sd, _ in stack]:
                index += 1
                continue

            if _is_span_empty(sd, index, stack):
                stack.pop()
                index += 1
                continue

            start_pos = _find_span_start_position(sd, stack)
            spans.append(_make_span(line, sd, start_pos, index, offset))

        index += 1

    return spans


def _parse_uris(line, offset):
    uris = []
    for match in URI_RX.finditer(line):
        uri = _make_uri(line, match.start(), match.end(), offset)
        uris.append(uri)

    for match in ADDRESS_RX.finditer(line):
        uri = _make_address(line, match.start(), match.end(), offset)
        uris.append(uri)

    return uris


def _handle_pre_span(line, index, offset, spans):
    # Scan ahead for the end
    end = line.find(PRE, index + 1)
    if end == -1:
        return index + 1

    if end - index == 1:
        # empty span
        return index + 1

    spans.append(_make_span(line, PRE, index, end, offset))
    return end + 1


def _make_span(line, sd, start, end, offset):
    text = line[start:end + 1]
    start += offset
    end += offset + 1
    span_class = SPAN_CLS_DICT.get(sd)
    return span_class(start=start, end=end, text=text)


def _make_uri(line, start, end, offset):
    text = line[start:end]
    start += offset
    end += offset
    return Uri(start=start, end=end, text=text)


def _make_address(line, start, end, offset):
    text = line[start:end]
    start += offset
    end += offset

    if text.startswith('xmpp'):
        return XMPPAddress(start=start, end=end, text=text)

    if text.startswith('mailto'):
        return MailAddress(start=start, end=end, text=text)

    return Address(start=start, end=end, text=text)


def _is_span_empty(sd, index, stack):
    start_sd = stack[-1][SD]
    if start_sd != sd:
        return False

    pos = stack[-1][SD_POS]
    return pos == index - 1


def _find_span_start_position(sd, stack):
    while stack:
        start_sd, pos = stack.pop()
        if start_sd == sd:
            return pos

    raise ValueError('Unable to find opening span')


def _is_valid_span_start(line, index):
    '''
    https://xmpp.org/extensions/xep-0393.html#span

    ... The opening styling directive MUST be located at the beginning
    of the line, after a whitespace character, or after a different opening
    styling directive. The opening styling directive MUST NOT be followed
    by a whitespace character ...
    '''

    try:
        char = line[index + 1]
    except IndexError:
        return False

    if char in WHITESPACE:
        return False

    if index == 0:
        return True

    char = line[index - 1]
    return char in VALID_SPAN_START


def _is_valid_span_end(line, index):
    '''
    https://xmpp.org/extensions/xep-0393.html#span

    ... and the closing styling directive MUST NOT be preceeded
    by a whitespace character ...
    '''

    if index == 0:
        return False

    char = line[index - 1]
    return char not in WHITESPACE
