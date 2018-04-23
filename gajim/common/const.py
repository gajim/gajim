from enum import IntEnum, unique
from collections import namedtuple

Option = namedtuple('Option', 'kind label type value name callback data desc enabledif props')
Option.__new__.__defaults__ = (None,) * len(Option._fields)

@unique
class OptionKind(IntEnum):
    ENTRY = 0
    SWITCH = 1
    SPIN = 2
    ACTION = 3
    LOGIN = 4
    DIALOG = 5
    CALLBACK = 6
    PROXY = 7
    HOSTNAME = 8
    PRIORITY = 9
    FILECHOOSER = 10
    CHANGEPASSWORD = 11
    GPG = 12

@unique
class OptionType(IntEnum):
    ACCOUNT_CONFIG = 0
    CONFIG = 1
    VALUE = 2
    ACTION = 3
    DIALOG = 4

class AvatarSize(IntEnum):
    TAB = 16
    ROSTER = 32
    CHAT = 48
    NOTIFICATION = 48
    PROFILE = 64
    TOOLTIP = 125
    VCARD = 200

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


THANKS = u"""\
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

ARTISTS = u"""\
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

DEVS_CURRENT = u"""\
Yann Leboulanger (asterix AT lagaule.org)
Philipp Hörist (philipp AT hoerist.com)
""".strip().split("\n")

DEVS_PAST = u"""\
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
