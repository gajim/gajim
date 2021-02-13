import re

def _get_link_pattern():
    # regexp meta characters are:  . ^ $ * + ? { } [ ] \ | ( )
    # one escapes the metachars with \
    # \S matches anything but ' ' '\t' '\n' '\r' '\f' and '\v'
    # \s matches any whitespace character
    # \w any alphanumeric character
    # \W any non-alphanumeric character
    # \b means word boundary. This is a zero-width assertion that
    #    matches only at the beginning or end of a word.
    # ^ matches at the beginning of lines
    #
    # * means 0 or more times
    # + means 1 or more times
    # ? means 0 or 1 time
    # | means or
    # [^*] anything but '*' (inside [] you don't have to escape metachars)
    # [^\s*] anything but whitespaces and '*'
    # (?<!\S) is a one char lookbehind assertion and asks for any leading
    #         whitespace
    # and matches beginning of lines so we have correct formatting detection
    # even if the text is just '*foo*'
    # (?!\S) is the same thing but it's a lookahead assertion
    # \S*[^\s\W] --> in the matching string don't match ? or ) etc.. if at
    #                the end
    # so http://be) will match http://be and http://be)be) will match
    # http://be)be

    legacy_prefixes = r"((?<=\()(www|ftp)\.([A-Za-z0-9\.\-_~:/\?#\[\]@!\$"\
        r"&'\(\)\*\+,;=]|%[A-Fa-f0-9]{2})+(?=\)))"\
        r"|((www|ftp)\.([A-Za-z0-9\.\-_~:/\?#\[\]@!\$&'\(\)\*\+,;=]"\
        r"|%[A-Fa-f0-9]{2})+"\
        r"\.([A-Za-z0-9\.\-_~:/\?#\[\]@!\$&'\(\)\*\+,;=]|%[A-Fa-f0-9]{2})+)"
    # NOTE: it's ok to catch www.gr such stuff exist!

    # FIXME: recognize xmpp: and treat it specially
    links = r"((?<=\()[A-Za-z][A-Za-z0-9\+\.\-]*:"\
        r"([\w\.\-_~:/\?#\[\]@!\$&'\(\)\*\+,;=]|%[A-Fa-f0-9]{2})+"\
        r"(?=\)))|(\w[\w\+\.\-]*:([^<>\s]|%[A-Fa-f0-9]{2})+)"

    # 2nd one: at_least_one_char@at_least_one_char.at_least_one_char
    mail = r'\bmailto:\S*[^\s\W]|' r'\b\S+@\S+\.\S*[^\s\W]'

    link_pattern = links + '|' + mail + '|' + legacy_prefixes
    return link_pattern

def _get_basic_pattern():
    basic_pattern = _get_link_pattern()
    # detects eg. *b* *bold* *bold bold* test *bold* *bold*! (*bold*)
    # doesn't detect (it's a feature :P) * bold* *bold * * bold * test*bold*
    formatting = r'|(?<!\w)' r'\*[^\s*]' r'([^*]*[^\s*])?' r'\*(?!\w)|'\
        r'(?<!\S)' r'~[^\s~]' r'([^~]*[^\s~])?' r'~(?!\S)|'\
        r'(?<!\w)' r'_[^\s_]' r'([^_]*[^\s_])?' r'_(?!\w)'
    return basic_pattern + formatting

def _get_emot_and_basic_pattern(use_ascii_formatting=True):
    from gajim.gui.emoji_data import emoji_data
    # because emoticons match later (in the string) they need to be after
    # basic matches that may occur earlier
    emoticons = emoji_data.get_regex()

    if use_ascii_formatting:
        pattern = _get_basic_pattern()
    else:
        pattern = _get_link_pattern()

    return '%s|%s' % (pattern, emoticons)

LINK_REGEX = re.compile(_get_link_pattern(), re.I | re.U)

# link pattern + ASCII formatting
BASIC_REGEX = re.compile(_get_basic_pattern(), re.IGNORECASE)

# emoticons + link pattern
EMOT_AND_LINK_REGEX = re.compile(_get_emot_and_basic_pattern(False),
                                          re.IGNORECASE)

# emoticons + link pattern + ASCII formatting
EMOT_AND_BASIC_REGEX = re.compile(_get_emot_and_basic_pattern(True),
                                          re.IGNORECASE)

INVALID_XML_CHARS_REGEX = re.compile(
    '[\x00-\x08]|[\x0b-\x0c]|[\x0e-\x1f]|[\ud800-\udfff]|[\ufffe-\uffff]')

# at least one character in 3 parts (before @, after @, after .)
STH_AT_STH_DOT_STH_REGEX = re.compile(
    r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
