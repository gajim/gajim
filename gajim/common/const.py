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

from __future__ import annotations

from typing import Any
from typing import Union
from typing import NamedTuple

from enum import IntEnum
from enum import Enum
from enum import unique
from functools import total_ordering

from gi.repository import Gio

from nbxmpp.namespaces import Namespace
from nbxmpp.const import PresenceShow
from nbxmpp.protocol import JID

from gajim.common.i18n import _
from gajim.common.i18n import Q_


STOP_EVENT = True
PROPAGATE_EVENT = False


class EncryptionData(NamedTuple):
    additional_data: Any = None


class Entity(NamedTuple):
    jid: JID
    node: str
    hash: str
    method: str


class RowHeaderType(IntEnum):
    ACTIVE = 0
    CONVERSATIONS = 1
    PINNED = 2


class AvatarSize(IntEnum):
    TAB = 16
    SHOW_CIRCLE = 24
    ROSTER = 32
    VCARD_HEADER = 40
    ACCOUNT_SIDE_BAR = 40
    WORKSPACE = 40
    WORKSPACE_EDIT = 100
    CHAT = 48
    NOTIFICATION = 48
    CALL = 100
    CALL_BIG = 200
    GROUP_INFO = 100
    TOOLTIP = 100
    ACCOUNT_PAGE = 150
    VCARD = 200
    PUBLISH = 200


class ArchiveState(IntEnum):
    NEVER = 0
    ALL = 1


@unique
class PathLocation(IntEnum):
    CONFIG = 0
    CACHE = 1
    DATA = 2


@unique
class PathType(IntEnum):
    FILE = 0
    FOLDER = 1
    FOLDER_OPTIONAL = 2


@unique
class KindConstant(IntEnum):
    STATUS = 0
    GCSTATUS = 1
    GC_MSG = 2
    SINGLE_MSG_RECV = 3
    CHAT_MSG_RECV = 4
    SINGLE_MSG_SENT = 5
    CHAT_MSG_SENT = 6
    ERROR = 7
    FILE_TRANSFER_INCOMING = 8
    FILE_TRANSFER_OUTGOING = 9
    CALL_INCOMING = 10
    CALL_OUTGOING = 11

    def __str__(self):
        return str(self.value)


@unique
class ShowConstant(IntEnum):
    ONLINE = 0
    CHAT = 1
    AWAY = 2
    XA = 3
    DND = 4
    OFFLINE = 5


@unique
class TypeConstant(IntEnum):
    AIM = 0
    GG = 1
    HTTP_WS = 2
    ICQ = 3
    MSN = 4
    QQ = 5
    SMS = 6
    SMTP = 7
    TLEN = 8
    YAHOO = 9
    NEWMAIL = 10
    RSS = 11
    WEATHER = 12
    MRIM = 13
    NO_TRANSPORT = 14


@unique
class SubscriptionConstant(IntEnum):
    NONE = 0
    TO = 1
    FROM = 2
    BOTH = 3


@unique
class JIDConstant(IntEnum):
    NORMAL_TYPE = 0
    ROOM_TYPE = 1


@unique
class StyleAttr(Enum):
    COLOR = 'color'
    BACKGROUND = 'background'
    FONT = 'font'


@unique
class CSSPriority(IntEnum):
    APPLICATION = 600
    APPLICATION_DARK = 601
    DEFAULT_THEME = 610
    DEFAULT_THEME_DARK = 611
    USER_THEME = 650


@unique
class ButtonAction(Enum):
    DESTRUCTIVE = 'destructive-action'
    SUGGESTED = 'suggested-action'


@unique
class IdleState(Enum):
    UNKNOWN = 'unknown'
    XA = 'xa'
    AWAY = 'away'
    AWAKE = 'online'


class SyncThreshold(IntEnum):
    NO_SYNC = -1
    NO_THRESHOLD = 0

    def __str__(self):
        return str(self.value)


class MUCUser(IntEnum):
    JID = 0
    NICK = 1
    REASON = 1
    NICK_OR_REASON = 1
    ROLE = 2
    AFFILIATION = 3
    AFFILIATION_TEXT = 4


@unique
class Trust(IntEnum):
    UNTRUSTED = 0
    UNDECIDED = 1
    BLIND = 2
    VERIFIED = 3


class Direction(IntEnum):
    NEXT = 0
    PREV = 1


class Display(Enum):
    X11 = 'X11Display'
    WAYLAND = 'GdkWaylandDisplay'
    WIN32 = 'GdkWin32Display'
    QUARTZ = 'GdkQuartzDisplay'


class URIType(Enum):
    UNKNOWN = 'unknown'
    XMPP = 'xmpp'
    MAIL = 'mail'
    GEO = 'geo'
    WEB = 'web'
    FILE = 'file'
    AT = 'at'
    TEL = 'tel'


class URIAction(Enum):
    MESSAGE = 'message'
    JOIN = 'join'
    SUBSCRIBE = 'subscribe'


class MUCJoinedState(Enum):
    JOINED = 'joined'
    NOT_JOINED = 'not joined'
    JOINING = 'joining'
    CREATING = 'creating'
    CAPTCHA_REQUEST = 'captcha in progress'
    CAPTCHA_FAILED = 'captcha failed'

    def __str__(self):
        return self.name

    @property
    def is_joined(self):
        return self == MUCJoinedState.JOINED

    @property
    def is_not_joined(self):
        return self == MUCJoinedState.NOT_JOINED

    @property
    def is_joining(self):
        return self == MUCJoinedState.JOINING

    @property
    def is_creating(self):
        return self == MUCJoinedState.CREATING

    @property
    def is_captcha_request(self):
        return self == MUCJoinedState.CAPTCHA_REQUEST

    @property
    def is_captcha_failed(self):
        return self == MUCJoinedState.CAPTCHA_FAILED


class ClientState(IntEnum):
    DISCONNECTING = 0
    DISCONNECTED = 1
    RECONNECT_SCHEDULED = 2
    CONNECTING = 3
    CONNECTED = 4
    AVAILABLE = 5

    @property
    def is_disconnecting(self):
        return self == ClientState.DISCONNECTING

    @property
    def is_disconnected(self):
        return self == ClientState.DISCONNECTED

    @property
    def is_reconnect_scheduled(self):
        return self == ClientState.RECONNECT_SCHEDULED

    @property
    def is_connecting(self):
        return self == ClientState.CONNECTING

    @property
    def is_connected(self):
        return self == ClientState.CONNECTED

    @property
    def is_available(self):
        return self == ClientState.AVAILABLE


class SimpleClientState(Enum):
    CONNECTING = 'connecting'
    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    RESUME_IN_PROGRESS = 'resume-in-progress'

    @property
    def is_connecting(self):
        return self == SimpleClientState.CONNECTING

    @property
    def is_connected(self):
        return self == SimpleClientState.CONNECTED

    @property
    def is_disconnected(self):
        return self == SimpleClientState.DISCONNECTED

    @property
    def is_resume_in_progress(self):
        return self == SimpleClientState.RESUME_IN_PROGRESS


class JingleState(Enum):
    NULL = 'stop'
    CONNECTING = 'connecting'
    CONNECTION_RECEIVED = 'connection_received'
    CONNECTED = 'connected'
    ERROR = 'error'

    def __str__(self):
        return self.value


class CallType(Enum):
    AUDIO = 'audio'
    VIDEO = 'video'


MUC_CREATION_EXAMPLES = [
    (Q_('?Group chat name:Team'),
     Q_('?Group chat description:Project discussion'),
     Q_('?Group chat address:team')),
    (Q_('?Group chat name:Family'),
     Q_('?Group chat description:Spring gathering'),
     Q_('?Group chat address:family')),
    (Q_('?Group chat name:Vacation'),
     Q_('?Group chat description:Trip planning'),
     Q_('?Group chat address:vacation')),
    (Q_('?Group chat name:Repairs'),
     Q_('?Group chat description:Local help group'),
     Q_('?Group chat address:repairs')),
    (Q_('?Group chat name:News'),
     Q_('?Group chat description:Local news and reports'),
     Q_('?Group chat address:news')),
]


MUC_DISCO_ERRORS = {
    'remote-server-not-found': _('Remote server not found'),
    'remote-server-timeout': _('Remote server timeout'),
    'service-unavailable': _('Address does not belong to a group chat server'),
    'subscription-required': _(
        'Address does not belong to a group chat server'),
    'not-muc-service': _('Address does not belong to a group chat server'),
    'already-exists': _('Group chat already exists'),
    'item-not-found': _('Group chat does not exist'),
    'gone': _('Group chat is closed'),
}


EME_MESSAGES = {
    'urn:xmpp:otr:0':
        _('This message was encrypted with OTR '
          'and could not be decrypted.'),
    'jabber:x:encrypted':
        _('This message was encrypted with Legacy '
          'OpenPGP and could not be decrypted. You can install '
          'the PGP plugin to handle those messages.'),
    'urn:xmpp:openpgp:0':
        _('This message was encrypted with '
          'OpenPGP for XMPP and could not be decrypted. You can install '
          'the OpenPGP plugin to handle those messages.'),
    'fallback':
        _('This message was encrypted with %s '
          'and could not be decrypted.')
}


LOCATION_DATA = {
    'accuracy': _('accuracy'),
    'alt': _('alt'),
    'area': _('area'),
    'bearing': _('bearing'),
    'building': _('building'),
    'country': _('country'),
    'countrycode': _('countrycode'),
    'datum': _('datum'),
    'description': _('description'),
    'error': _('error'),
    'floor': _('floor'),
    'lat': _('lat'),
    'locality': _('locality'),
    'lon': _('lon'),
    'postalcode': _('postalcode'),
    'region': _('region'),
    'room': _('room'),
    'speed': _('speed'),
    'street': _('street'),
    'text': _('text'),
    'timestamp': _('timestamp'),
    'uri': _('URI')
}


SSLError = {
    2: _("Unable to get issuer certificate"),
    3: _("Unable to get certificate CRL"),
    4: _("Unable to decrypt certificate's signature"),
    5: _("Unable to decrypt CRL's signature"),
    6: _("Unable to decode issuer public key"),
    7: _("Certificate signature failure"),
    8: _("CRL signature failure"),
    9: _("Certificate is not yet valid"),
    10: _("Certificate has expired"),
    11: _("CRL is not yet valid"),
    12: _("CRL has expired"),
    13: _("Format error in certificate's notBefore field"),
    14: _("Format error in certificate's notAfter field"),
    15: _("Format error in CRL's lastUpdate field"),
    16: _("Format error in CRL's nextUpdate field"),
    17: _("Out of memory"),
    18: _("Self signed certificate"),
    19: _("Self signed certificate in certificate chain"),
    20: _("Unable to get local issuer certificate"),
    21: _("Unable to verify the first certificate"),
    22: _("Certificate chain too long"),
    23: _("Certificate revoked"),
    24: _("Invalid CA certificate"),
    25: _("Path length constraint exceeded"),
    26: _("Unsupported certificate purpose"),
    27: _("Certificate not trusted"),
    28: _("Certificate rejected"),
    29: _("Subject issuer mismatch"),
    30: _("Authority and subject key identifier mismatch"),
    31: _("Authority and issuer serial number mismatch"),
    32: _("Key usage does not include certificate signing"),
    50: _("Application verification failure"),
}


VOWELS = 'aeiou'


CONSONANTS = 'bcdfghjklmnpqrstvwxyz'


THANKS = """\
Alexander Futász
Alexander V. Butenko
Alexey Nezhdanov
Alfredo Junix
Anaël Verrier
Anders Ström
Andrew Sayman
Anton Shmigirilov
Christian Bjälevik
Christophe Got
Christoph Neuroth
David Campey
Dennis Craven
Fabian Neumann
Filippos Papadopoulos
Francisco Alburquerque Parra (Membris Khan)
Frederic Lory
Fridtjof Bussefor
Geobert Quach
Guillaume Morin
Gustavo J. A. M. Carneiro
Ivo Anjo
Josef Vybíral
Juraj Michalek
Kjell Braden
Luis Peralta
Michael Scherer
Michele Campeotto
Mike Albon
Miguel Fonseca
Norman Rasmussen
Oscar Hellström
Peter Saint-Andre
Petr Menšík
Sergey Kuleshov
Stavros Giannouris
Stian B. Barmen
Thilo Molitor
Thomas Klein-Hitpaß
Urtzi Alfaro
Witold Kieraś
Yakov Bezrukov
Yavor Doganov
""".strip().split("\n")

ARTISTS = """\
Anders Ström
Christophe Got
Dennis Craven
Dmitry Korzhevin
Guillaume Morin
Gvorcek Spajreh
Josef Vybíral
Membris Khan
Rederick Asher
Jakub Szypulka
""".strip().split("\n")

DEVS_CURRENT = """\
Yann Leboulanger (asterix AT lagaule.org)
Philipp Hörist (philipp AT hoerist.com)
Daniel Brötzmann (wurstsalat AT posteo.de)
André Apitzsch
""".strip().split("\n")

DEVS_PAST = """\
Stefan Bethge (stefan AT lanpartei.de)
Alexander Cherniuk (ts33kr AT gmail.com)
Stephan Erb (steve-e AT h3c.de)
Vincent Hanquez (tab AT snarc.org)
Dimitur Kirov (dkirov AT gmail.com)
Nikos Kouremenos (kourem AT gmail.com)
Julien Pivotto (roidelapluie AT gmail.com)
Jonathan Schleifer (js-gajim AT webkeks.org)
Travis Shirk (travis AT pobox.com)
Brendan Taylor (whateley AT gmail.com)
Jean-Marie Traissard (jim AT lapin.org)
""".strip().split("\n")


RFC5646_LANGUAGE_TAGS = {
    'af': 'Afrikaans',
    'af-ZA': 'Afrikaans (South Africa)',
    'ar': 'Arabic',
    'ar-AE': 'Arabic (U.A.E.)',
    'ar-BH': 'Arabic (Bahrain)',
    'ar-DZ': 'Arabic (Algeria)',
    'ar-EG': 'Arabic (Egypt)',
    'ar-IQ': 'Arabic (Iraq)',
    'ar-JO': 'Arabic (Jordan)',
    'ar-KW': 'Arabic (Kuwait)',
    'ar-LB': 'Arabic (Lebanon)',
    'ar-LY': 'Arabic (Libya)',
    'ar-MA': 'Arabic (Morocco)',
    'ar-OM': 'Arabic (Oman)',
    'ar-QA': 'Arabic (Qatar)',
    'ar-SA': 'Arabic (Saudi Arabia)',
    'ar-SY': 'Arabic (Syria)',
    'ar-TN': 'Arabic (Tunisia)',
    'ar-YE': 'Arabic (Yemen)',
    'az': 'Azeri (Latin)',
    'az-AZ': 'Azeri (Latin) (Azerbaijan)',
    'az-Cyrl-AZ': 'Azeri (Cyrillic) (Azerbaijan)',
    'be': 'Belarusian',
    'be-BY': 'Belarusian (Belarus)',
    'bg': 'Bulgarian',
    'bg-BG': 'Bulgarian (Bulgaria)',
    'bs-BA': 'Bosnian (Bosnia and Herzegovina)',
    'ca': 'Catalan',
    'ca-ES': 'Catalan (Spain)',
    'cs': 'Czech',
    'cs-CZ': 'Czech (Czech Republic)',
    'cy': 'Welsh',
    'cy-GB': 'Welsh (United Kingdom)',
    'da': 'Danish',
    'da-DK': 'Danish (Denmark)',
    'de': 'German',
    'de-AT': 'German (Austria)',
    'de-CH': 'German (Switzerland)',
    'de-DE': 'German (Germany)',
    'de-LI': 'German (Liechtenstein)',
    'de-LU': 'German (Luxembourg)',
    'dv': 'Divehi',
    'dv-MV': 'Divehi (Maldives)',
    'el': 'Greek',
    'el-GR': 'Greek (Greece)',
    'en': 'English',
    'en-AU': 'English (Australia)',
    'en-BZ': 'English (Belize)',
    'en-CA': 'English (Canada)',
    'en-CB': 'English (Caribbean)',
    'en-GB': 'English (United Kingdom)',
    'en-IE': 'English (Ireland)',
    'en-JM': 'English (Jamaica)',
    'en-NZ': 'English (New Zealand)',
    'en-PH': 'English (Republic of the Philippines)',
    'en-TT': 'English (Trinidad and Tobago)',
    'en-US': 'English (United States)',
    'en-ZA': 'English (South Africa)',
    'en-ZW': 'English (Zimbabwe)',
    'eo': 'Esperanto',
    'es': 'Spanish',
    'es-AR': 'Spanish (Argentina)',
    'es-BO': 'Spanish (Bolivia)',
    'es-CL': 'Spanish (Chile)',
    'es-CO': 'Spanish (Colombia)',
    'es-CR': 'Spanish (Costa Rica)',
    'es-DO': 'Spanish (Dominican Republic)',
    'es-EC': 'Spanish (Ecuador)',
    'es-ES': 'Spanish (Spain)',
    'es-GT': 'Spanish (Guatemala)',
    'es-HN': 'Spanish (Honduras)',
    'es-MX': 'Spanish (Mexico)',
    'es-NI': 'Spanish (Nicaragua)',
    'es-PA': 'Spanish (Panama)',
    'es-PE': 'Spanish (Peru)',
    'es-PR': 'Spanish (Puerto Rico)',
    'es-PY': 'Spanish (Paraguay)',
    'es-SV': 'Spanish (El Salvador)',
    'es-UY': 'Spanish (Uruguay)',
    'es-VE': 'Spanish (Venezuela)',
    'et': 'Estonian',
    'et-EE': 'Estonian (Estonia)',
    'eu': 'Basque',
    'eu-ES': 'Basque (Spain)',
    'fa': 'Farsi',
    'fa-IR': 'Farsi (Iran)',
    'fi': 'Finnish',
    'fi-FI': 'Finnish (Finland)',
    'fo': 'Faroese',
    'fo-FO': 'Faroese (Faroe Islands)',
    'fr': 'French',
    'fr-BE': 'French (Belgium)',
    'fr-CA': 'French (Canada)',
    'fr-CH': 'French (Switzerland)',
    'fr-FR': 'French (France)',
    'fr-LU': 'French (Luxembourg)',
    'fr-MC': 'French (Principality of Monaco)',
    'gl': 'Galician',
    'gl-ES': 'Galician (Spain)',
    'gu': 'Gujarati',
    'gu-IN': 'Gujarati (India)',
    'he': 'Hebrew',
    'he-IL': 'Hebrew (Israel)',
    'hi': 'Hindi',
    'hi-IN': 'Hindi (India)',
    'hr': 'Croatian',
    'hr-BA': 'Croatian (Bosnia and Herzegovina)',
    'hr-HR': 'Croatian (Croatia)',
    'hu': 'Hungarian',
    'hu-HU': 'Hungarian (Hungary)',
    'hy': 'Armenian',
    'hy-AM': 'Armenian (Armenia)',
    'id': 'Indonesian',
    'id-ID': 'Indonesian (Indonesia)',
    'is': 'Icelandic',
    'is-IS': 'Icelandic (Iceland)',
    'it': 'Italian',
    'it-CH': 'Italian (Switzerland)',
    'it-IT': 'Italian (Italy)',
    'ja': 'Japanese',
    'ja-JP': 'Japanese (Japan)',
    'ka': 'Georgian',
    'ka-GE': 'Georgian (Georgia)',
    'kk': 'Kazakh',
    'kk-KZ': 'Kazakh (Kazakhstan)',
    'kn': 'Kannada',
    'kn-IN': 'Kannada (India)',
    'ko': 'Korean',
    'ko-KR': 'Korean (Korea)',
    'kok': 'Konkani',
    'kok-IN': 'Konkani (India)',
    'ky': 'Kyrgyz',
    'ky-KG': 'Kyrgyz (Kyrgyzstan)',
    'lt': 'Lithuanian',
    'lt-LT': 'Lithuanian (Lithuania)',
    'lv': 'Latvian',
    'lv-LV': 'Latvian (Latvia)',
    'mi': 'Maori',
    'mi-NZ': 'Maori (New Zealand)',
    'mk': 'FYRO Macedonian',
    'mk-MK': 'FYRO Macedonian (Former Yugoslav Republic of Macedonia)',
    'mn': 'Mongolian',
    'mn-MN': 'Mongolian (Mongolia)',
    'mr': 'Marathi',
    'mr-IN': 'Marathi (India)',
    'ms': 'Malay',
    'ms-BN': 'Malay (Brunei Darussalam)',
    'ms-MY': 'Malay (Malaysia)',
    'mt': 'Maltese',
    'mt-MT': 'Maltese (Malta)',
    'nb': 'Norwegian (Bokm?l)',
    'nb-NO': 'Norwegian (Bokm?l) (Norway)',
    'nl': 'Dutch',
    'nl-BE': 'Dutch (Belgium)',
    'nl-NL': 'Dutch (Netherlands)',
    'nn-NO': 'Norwegian (Nynorsk) (Norway)',
    'ns': 'Northern Sotho',
    'ns-ZA': 'Northern Sotho (South Africa)',
    'pa': 'Punjabi',
    'pa-IN': 'Punjabi (India)',
    'pl': 'Polish',
    'pl-PL': 'Polish (Poland)',
    'ps': 'Pashto',
    'ps-AR': 'Pashto (Afghanistan)',
    'pt': 'Portuguese',
    'pt-BR': 'Portuguese (Brazil)',
    'pt-PT': 'Portuguese (Portugal)',
    'qu': 'Quechua',
    'qu-BO': 'Quechua (Bolivia)',
    'qu-EC': 'Quechua (Ecuador)',
    'qu-PE': 'Quechua (Peru)',
    'ro': 'Romanian',
    'ro-RO': 'Romanian (Romania)',
    'ru': 'Russian',
    'ru-RU': 'Russian (Russia)',
    'sa': 'Sanskrit',
    'sa-IN': 'Sanskrit (India)',
    'se': 'Sami',
    'se-FI': 'Sami (Finland)',
    'se-NO': 'Sami (Norway)',
    'se-SE': 'Sami (Sweden)',
    'sk': 'Slovak',
    'sk-SK': 'Slovak (Slovakia)',
    'sl': 'Slovenian',
    'sl-SI': 'Slovenian (Slovenia)',
    'sq': 'Albanian',
    'sq-AL': 'Albanian (Albania)',
    'sr-BA': 'Serbian (Latin) (Bosnia and Herzegovina)',
    'sr-Cyrl-BA': 'Serbian (Cyrillic) (Bosnia and Herzegovina)',
    'sr-SP': 'Serbian (Latin) (Serbia and Montenegro)',
    'sr-Cyrl-SP': 'Serbian (Cyrillic) (Serbia and Montenegro)',
    'sv': 'Swedish',
    'sv-FI': 'Swedish (Finland)',
    'sv-SE': 'Swedish (Sweden)',
    'sw': 'Swahili',
    'sw-KE': 'Swahili (Kenya)',
    'syr': 'Syriac',
    'syr-SY': 'Syriac (Syria)',
    'ta': 'Tamil',
    'ta-IN': 'Tamil (India)',
    'te': 'Telugu',
    'te-IN': 'Telugu (India)',
    'th': 'Thai',
    'th-TH': 'Thai (Thailand)',
    'tl': 'Tagalog',
    'tl-PH': 'Tagalog (Philippines)',
    'tn': 'Tswana',
    'tn-ZA': 'Tswana (South Africa)',
    'tr': 'Turkish',
    'tr-TR': 'Turkish (Turkey)',
    'tt': 'Tatar',
    'tt-RU': 'Tatar (Russia)',
    'ts': 'Tsonga',
    'uk': 'Ukrainian',
    'uk-UA': 'Ukrainian (Ukraine)',
    'ur': 'Urdu',
    'ur-PK': 'Urdu (Islamic Republic of Pakistan)',
    'uz': 'Uzbek (Latin)',
    'uz-UZ': 'Uzbek (Latin) (Uzbekistan)',
    'uz-Cyrl-UZ': 'Uzbek (Cyrillic) (Uzbekistan)',
    'vi': 'Vietnamese',
    'vi-VN': 'Vietnamese (Viet Nam)',
    'xh': 'Xhosa',
    'xh-ZA': 'Xhosa (South Africa)',
    'zh': 'Chinese',
    'zh-CN': 'Chinese (S)',
    'zh-HK': 'Chinese (Hong Kong)',
    'zh-MO': 'Chinese (Macau)',
    'zh-SG': 'Chinese (Singapore)',
    'zh-TW': 'Chinese (T)',
    'zu': 'Zulu',
    'zu-ZA': 'Zulu (South Africa)'
}


GIO_TLS_ERRORS = {
    Gio.TlsCertificateFlags.UNKNOWN_CA: _(
        'The signing certificate authority is not known'),
    Gio.TlsCertificateFlags.REVOKED: _(
        'The certificate has been revoked'),
    Gio.TlsCertificateFlags.BAD_IDENTITY: _(
        'The certificate does not match the expected identity of the site'),
    Gio.TlsCertificateFlags.INSECURE: _(
        'The certificate’s algorithm is insecure'),
    Gio.TlsCertificateFlags.NOT_ACTIVATED: _(
        'The certificate’s activation time is in the future'),
    Gio.TlsCertificateFlags.GENERIC_ERROR: _('Unknown validation error'),
    Gio.TlsCertificateFlags.EXPIRED: _('The certificate has expired'),
}


class FTState(Enum):
    INIT = 'init'
    PREPARING = 'prepare'
    ENCRYPTING = 'encrypting'
    DECRYPTING = 'decrypting'
    STARTED = 'started'
    IN_PROGRESS = 'progress'
    FINISHED = 'finished'
    ERROR = 'error'
    CANCELLED = 'cancelled'

    @property
    def is_preparing(self):
        return self == FTState.PREPARING

    @property
    def is_encrypting(self):
        return self == FTState.ENCRYPTING

    @property
    def is_decrypting(self):
        return self == FTState.DECRYPTING

    @property
    def is_started(self):
        return self == FTState.STARTED

    @property
    def is_in_progress(self):
        return self == FTState.IN_PROGRESS

    @property
    def is_finished(self):
        return self == FTState.FINISHED

    @property
    def is_error(self):
        return self == FTState.ERROR

    @property
    def is_cancelled(self):
        return self == FTState.CANCELLED

    @property
    def is_active(self):
        return not (self.is_error or
                    self.is_cancelled or
                    self.is_finished)


SASL_ERRORS = {
    'aborted': _('Authentication aborted'),
    'account-disabled': _('Account disabled'),
    'credentials-expired': _('Credentials expired'),
    'encryption-required': _('Encryption required'),
    'incorrect-encoding': _('Authentication failed'),
    'invalid-authzid': _('Authentication failed'),
    'malformed-request': _('Authentication failed'),
    'invalid-mechanism': _('Authentication mechanism not supported'),
    'mechanism-too-weak': _('Authentication mechanism too weak'),
    'not-authorized': _('Authentication failed'),
    'temporary-auth-failure': _('Authentication currently not possible'),
}


COMMON_FEATURES = [
    Namespace.BYTESTREAM,
    Namespace.MUC,
    Namespace.COMMANDS,
    Namespace.DISCO_INFO,
    Namespace.LAST,
    Namespace.DATA,
    Namespace.ENCRYPTED,
    Namespace.PING,
    Namespace.CHATSTATES,
    Namespace.RECEIPTS,
    Namespace.TIME_REVISED,
    Namespace.VERSION,
    Namespace.ROSTERX,
    Namespace.SECLABEL,
    Namespace.CONFERENCE,
    Namespace.CORRECT,
    Namespace.CHATMARKERS,
    Namespace.EME,
    Namespace.XHTML_IM,
    Namespace.HASHES_2,
    Namespace.HASHES_MD5,
    Namespace.HASHES_SHA1,
    Namespace.HASHES_SHA256,
    Namespace.HASHES_SHA512,
    Namespace.HASHES_SHA3_256,
    Namespace.HASHES_SHA3_512,
    Namespace.HASHES_BLAKE2B_256,
    Namespace.HASHES_BLAKE2B_512,
    Namespace.JINGLE,
    Namespace.JINGLE_FILE_TRANSFER_5,
    Namespace.JINGLE_XTLS,
    Namespace.JINGLE_BYTESTREAM,
    Namespace.JINGLE_IBB,
    Namespace.AVATAR_METADATA + '+notify',
    Namespace.MESSAGE_MODERATE
]


SHOW_LIST = [
    'offline',
    'connecting',
    'away',
    'xa',
    'chat',
    'online',
    'dnd',
]

SHOW_STRING = {
    'dnd': _('Busy'),
    'xa': _('Not Available'),
    'chat': _('Free for Chat'),
    'online': Q_('?user status:Available'),
    'connecting': _('Connecting'),
    'away': _('Away'),
    'offline': _('Offline'),
}

SHOW_STRING_MNEMONIC = {
    'dnd': _('_Busy'),
    'xa': _('_Not Available'),
    'chat': _('_Free for Chat'),
    'online': Q_('?user status:_Available'),
    'connecting': _('Connecting'),
    'away': _('A_way'),
    'offline': _('_Offline'),
}

GAJIM_FAQ_URI = 'https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq'
GAJIM_WIKI_URI = 'https://dev.gajim.org/gajim/gajim/wikis'
GAJIM_SUPPORT_JID = 'gajim@conference.gajim.org'

URI_SCHEMES = {
    'aaa://',
    'aaas://',
    'acap://',
    'cap://',
    'cid:',
    'crid://',
    'data:',
    'dav:',
    'dict://',
    'dns:',
    'fax:',
    'file:/',
    'ftp://',
    'geo:',
    'go:',
    'gopher://',
    'h323:',
    'http://',
    'https://',
    'iax:',
    'icap://',
    'im:',
    'imap://',
    'info:',
    'ipp://',
    'iris:',
    'iris.beep:',
    'iris.xpc:',
    'iris.xpcs:',
    'iris.lwz:',
    'ldap://',
    'mailto:',
    'mid:',
    'modem:',
    'msrp://',
    'msrps://',
    'mtqp://',
    'mupdate://',
    'news:',
    'nfs://',
    'nntp://',
    'opaquelocktoken:',
    'pop://',
    'pres:',
    'prospero://',
    'rtsp://',
    'service:',
    'sip:',
    'sips:',
    'sms:',
    'snmp://',
    'soap.beep://',
    'soap.beeps://',
    'tag:',
    'tel:',
    'telnet://',
    'tftp://',
    'thismessage:/',
    'tip://',
    'tv:',
    'urn://',
    'vemmi://',
    'xmlrpc.beep://',
    'xmlrpc.beeps://',
    'xmpp:',
    'z39.50r://',
    'z39.50s://',
    'about:',
    'apt:',
    'cvs://',
    'daap://',
    'ed2k://',
    'feed:',
    'fish://',
    'git://',
    'iax2:',
    'irc://',
    'ircs://',
    'ldaps://',
    'magnet:',
    'mms://',
    'rsync://',
    'ssh://',
    'svn://',
    'sftp://',
    'smb://',
    'webcal://',
    'aesgcm://',
}


# This is an excerpt of Media Types from
# https://www.iana.org/assignments/media-types/media-types.xhtml
# plus some additions
MIME_TYPES = (
    # application/
    'application/calendar+json',
    'application/calendar+xml',
    'application/epub+zip',
    'application/json',
    'application/mp4',
    'application/msword',
    'application/octet-stream',
    'application/ogg',
    'application/pdf',
    'application/pgp-encrypted',
    'application/pgp-signature',
    'application/postscript',
    'application/rtf',
    'application/vcard+json',
    'application/vcard+xml',
    'application/vnd.amazon.mobi8-ebook',
    'application/vnd.google-earth.kml+xml',
    'application/vnd.google-earth.kmz',
    # Start office
    'application/vnd.ms-access',
    'application/vnd.ms-excel',
    'application/vnd.ms-excel.addin.macroEnabled.12',
    'application/vnd.ms-excel.sheet.binary.macroEnabled.12',
    'application/vnd.ms-excel.sheet.macroEnabled.12',
    'application/vnd.ms-excel.template.macroEnabled.12',
    'application/vnd.ms-powerpoint',
    'application/vnd.ms-powerpoint.addin.macroEnabled.12',
    'application/vnd.ms-powerpoint.presentation.macroEnabled.12',
    'application/vnd.ms-powerpoint.slideshow.macroEnabled.12',
    'application/vnd.ms-powerpoint.template.macroEnabled.12',
    'application/vnd.ms-word.document.macroEnabled.12',
    'application/vnd.ms-word.template.macroEnabled.12',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.presentationml.slideshow',
    'application/vnd.openxmlformats-officedocument.presentationml.template',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.template',
    'application/vnd.openxmlformats-officedocument.vmlDrawing',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.template',
    # End office
    'application/vnd.sqlite3',
    'application/zip',
    # audio/*
    'audio/aac',
    'audio/ac3',
    'audio/flac',
    'audio/mp4',
    'audio/mpeg',
    'audio/ogg',
    'audio/opus',
    'audio/wav',
    'audio/x-flac',
    'audio/x-m4a',
    'audio/x-matroska',
    # font/*
    'font/ttf',
    'font/woff',
    'font/woff2',
    # image/*
    'image/webp',
    'image/avif',
    'image/jxl',
    'image/bmp',
    'image/x-bmp',
    'image/x-ms-bmp',
    'image/gif',
    'image/heic',
    'image/heif',
    'image/jpeg',
    'image/png',
    'image/svg+xml',
    'image/tiff',
    'image/vnd.adobe.photoshop',
    'image/vnd.dwg',
    'image/vnd.dxf',
    'image/vnd.microsoft.icon',
    'image/x-icon',
    'image/x-xcf',
    # model/*
    'model/mtl',
    'model/obj',
    'model/stl',
    # text/*
    'text/calendar',
    'text/csv',
    'text/markdown',
    'text/rtf',
    'text/vcard',
    # video/*
    'video/H264',
    'video/H265',
    'video/mp4',
    'video/mpeg4-generic',
    'video/ogg',
    'video/quicktime',
    'video/vc1',
    'video/VP8',
    'video/webm',
    'video/x-matroska',
    'video/x-msvideo',
)


TRUST_SYMBOL_DATA = {
    Trust.UNTRUSTED: ('dialog-error-symbolic',
                      _('Untrusted'),
                      'error-color'),
    Trust.UNDECIDED: ('security-low-symbolic',
                      _('Trust Not Decided'),
                      'warning-color'),
    Trust.BLIND: ('security-medium-symbolic',
                  _('Unverified'),
                  'encrypted-color'),
    Trust.VERIFIED: ('security-high-symbolic',
                     _('Verified'),
                     'encrypted-color')
}


THRESHOLD_OPTIONS = {
    -1: _('No Sync'),
    1: _('1 Day'),
    2: _('2 Days'),
    7: _('1 Week'),
    30: _('1 Month'),
    0: _('No Threshold'),
}


@total_ordering
class PresenceShowExt(Enum):

    '''
    This extends nbxmpp.const.PresenceShow for convenience
    with an OFFLINE member
    '''

    OFFLINE = 'offline'

    @property
    def is_offline(self):
        return self == PresenceShowExt.OFFLINE

    def __lt__(self, other: Union[PresenceShowExt, PresenceShow]) -> bool:
        if isinstance(other, PresenceShowExt):
            return False
        if not isinstance(other, PresenceShow):  # pyright: ignore
            return NotImplemented
        return True
