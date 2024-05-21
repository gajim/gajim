# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    James Newton <redshodan AT gmail.com>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

import functools
import hashlib
import importlib.metadata
import inspect
import json
import logging
import os
import platform
import random
import re
import socket
import string
import sys
import unicodedata
import uuid
import weakref
import webbrowser
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import wraps
from pathlib import Path
from string import Template
from urllib.parse import unquote
from urllib.parse import urlparse

import precis_i18n.codec  # noqa: F401
import qrcode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Soup
from nbxmpp.const import Affiliation
from nbxmpp.const import Chatstate
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.const import Role
from nbxmpp.errors import StanzaError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import CommonError
from nbxmpp.structs import ProxyData
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version as V
from qrcode.image.pil import PilImage as QrcPilImage

from gajim.common import app
from gajim.common import configpaths
from gajim.common import iana
from gajim.common import types
from gajim.common.const import CONSONANTS
from gajim.common.const import GIO_TLS_ERRORS
from gajim.common.const import NONREGISTERED_URI_SCHEMES
from gajim.common.const import SHOW_LIST
from gajim.common.const import SHOW_STRING
from gajim.common.const import SHOW_STRING_MNEMONIC
from gajim.common.const import URIType
from gajim.common.const import VOWELS
from gajim.common.const import XmppUriQuery
from gajim.common.dbus.file_manager import DBusFileManager
from gajim.common.i18n import _
from gajim.common.i18n import get_rfc5646_lang
from gajim.common.i18n import ngettext
from gajim.common.i18n import p_
from gajim.common.structs import URI

if TYPE_CHECKING:
    from gajim.common.modules.util import LogAdapter

HAS_PYWIN32 = False
if os.name == 'nt':
    try:
        import pywintypes
        import win32con
        import win32file
        HAS_PYWIN32 = True
    except ImportError:
        pass

log = logging.getLogger('gajim.c.helpers')

URL_REGEX = re.compile(
    r"(www\.(?!\.)|[a-z][a-z0-9+.-]*://)[^\s<>'\"]+[^!,\.\s<>\)'\"\]]")
CURRENT_PYTHON_VERSION = platform.python_version()


class InvalidFormat(Exception):
    pass


def parse_jid(jidstring: str) -> str:
    try:
        return str(validate_jid(jidstring))
    except Exception as error:
        raise InvalidFormat(error)


def idn_to_ascii(host: str) -> str:
    '''
    Convert IDN (Internationalized Domain Names) to ACE (ASCII-compatible
    encoding)
    '''
    from encodings import idna
    labels = idna.dots.split(host)
    converted_labels: list[str] = []
    for label in labels:
        if label:
            converted_labels.append(idna.ToASCII(label).decode('utf-8'))
        else:
            converted_labels.append('')
    return '.'.join(converted_labels)


def ascii_to_idn(host: str) -> str:
    '''
    Convert ACE (ASCII-compatible encoding) to IDN (Internationalized Domain
    Names)
    '''
    from encodings import idna
    labels = idna.dots.split(host)
    converted_labels: list[str] = []
    for label in labels:
        converted_labels.append(idna.ToUnicode(label))
    return '.'.join(converted_labels)


def parse_resource(resource: str) -> str | None:
    '''
    Perform stringprep on resource and return it
    '''
    if not resource:
        return None

    try:
        return resource.encode('OpaqueString').decode('utf-8')
    except UnicodeError:
        raise InvalidFormat('Invalid character in resource.')


def get_uf_show(show: str, use_mnemonic: bool = False) -> str:
    if use_mnemonic:
        return SHOW_STRING_MNEMONIC[show]
    return SHOW_STRING[show]


def get_uf_sub(sub: str) -> str:
    if sub == 'none':
        return p_('Contact subscription', 'None')

    if sub == 'to':
        return p_('Contact subscription', 'To')

    if sub == 'from':
        return p_('Contact subscription', 'From')

    if sub == 'both':
        return p_('Contact subscription', 'Both')

    return p_('Contact subscription', 'Unknown')


def get_uf_ask(ask: str | None) -> str:
    if ask is None:
        return p_('Contact subscription', 'None')

    if ask == 'subscribe':
        return p_('Contact subscription', 'Subscribe')

    return ask


def get_uf_role(role: Role | str, plural: bool = False) -> str:
    ''' plural determines if you get Moderators or Moderator'''
    if not isinstance(role, str):
        role = role.value

    if role == 'none':
        return p_('Group chat contact role', 'None')
    if role == 'moderator':
        if plural:
            return p_('Group chat contact role', 'Moderators')
        return p_('Group chat contact role', 'Moderator')
    if role == 'participant':
        if plural:
            return p_('Group chat contact role', 'Participants')
        return p_('Group chat contact role', 'Participant')
    if role == 'visitor':
        if plural:
            return p_('Group chat contact role', 'Visitors')
        return p_('Group chat contact role', 'Visitor')
    return ''


def get_uf_affiliation(affiliation: Affiliation | str,
                       plural: bool = False
                       ) -> str:
    '''Get a nice and translated affilition for muc'''
    if not isinstance(affiliation, str):
        affiliation = affiliation.value

    if affiliation == 'none':
        return p_('Group chat contact affiliation', 'None')
    if affiliation == 'owner':
        if plural:
            return p_('Group chat contact affiliation', 'Owners')
        return p_('Group chat contact affiliation', 'Owner')
    if affiliation == 'admin':
        if plural:
            return p_('Group chat contact affiliation', 'Administrators')
        return p_('Group chat contact affiliation', 'Administrator')
    if affiliation == 'member':
        if plural:
            return p_('Group chat contact affiliation', 'Members')
        return p_('Group chat contact affiliation', 'Member')
    return ''


def get_uf_relative_time(date_time: datetime,
                         now: datetime | None = None
                         ) -> str:

    if now is None:  # used by unittest
        now = datetime.now()
    timespan = now - date_time

    if timespan < timedelta(minutes=1):
        return _('Just now')
    if timespan < timedelta(minutes=15):
        minutes = int(timespan.seconds / 60)
        return ngettext('%s min ago',
                        '%s mins ago',
                        minutes,
                        str(minutes),
                        str(minutes))
    today = now.date()
    if date_time.date() == today:
        format_string = app.settings.get('time_format')
        return date_time.strftime(format_string)
    yesterday = now.date() - timedelta(days=1)
    if date_time.date() == yesterday:
        return _('Yesterday')
    if timespan < timedelta(days=7):  # this week
        return date_time.strftime('%a')  # weekday
    if timespan < timedelta(days=365):  # this year
        return date_time.strftime('%b %d')
    return str(date_time.year)


def to_one_line(msg: str) -> str:
    msg = msg.replace('\\', '\\\\')
    return msg.replace('\n', '\\n')


def from_one_line(msg: str) -> str:
    # (?<!\\) is a lookbehind assertion which asks anything but '\'
    # to match the regexp that follows it

    # So here match '\\n' but not if you have a '\' before that
    expr = re.compile(r'(?<!\\)\\n')
    msg = expr.sub('\n', msg)
    return msg.replace('\\\\', '\\')


def chatstate_to_string(chatstate: Chatstate | None) -> str:
    if chatstate is None:
        return ''

    if chatstate == Chatstate.ACTIVE:
        return ''

    if chatstate == Chatstate.COMPOSING:
        return _('is composing a message…')

    if chatstate in (Chatstate.INACTIVE, Chatstate.GONE):
        return _('is doing something else')

    if chatstate == Chatstate.PAUSED:
        return _('paused composing a message')

    raise ValueError('unknown value: %s' % chatstate)


def sanitize_filename(filename: str) -> str:
    '''
    Sanitize filename of elements not allowed on Windows
    https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file
    Limit filename length to 50 chars on all systems
    '''
    if sys.platform == 'win32':
        blacklist = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\0']
        reserved_filenames = [
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
            'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
            'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
        ]
        filename = ''.join(char for char in filename if char not in blacklist)

        filename = ''.join(char for char in filename if ord(char) > 31)

        filename = unicodedata.normalize('NFKD', filename)
        filename = filename.rstrip('. ')
        filename = filename.strip()

        if all(char == '.' for char in filename):
            filename = f'__{filename}'
        if filename.upper() in reserved_filenames:
            filename = f'__{filename}'
        if len(filename) == 0:
            filename = '__'

    extension = Path(filename).suffix[:10]
    filename = Path(filename).stem
    final_length = 50 - len(extension)

    # Many Filesystems have a limit on filename length: keep it short
    filename = filename[:final_length]

    return f'{filename}{extension}'


def get_contact_dict_for_account(account: str) -> dict[str, types.BareContact]:
    '''
    Creates a dict of jid -> contact with all contacts of account
    Can be used for completion lists
    '''
    contacts_dict: dict[str, types.BareContact] = {}
    client = app.get_client(account)
    for contact in client.get_module('Roster').iter_contacts():
        contacts_dict[str(contact.jid)] = contact
    return contacts_dict


def generate_qr_code(content: str) -> GdkPixbuf.Pixbuf | None:
    qr = qrcode.QRCode(version=None,
                       error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=6,
                       border=4)
    qr.add_data(content)
    qr.make(fit=True)

    img = qr.make_image(image_factory=QrcPilImage).convert('RGB')
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(img.tobytes()),
        GdkPixbuf.Colorspace.RGB, False, 8,
        img.width, img.height, img.width*3)


def play_sound(sound_event: str,
               account: str | None = None,
               force: bool = False,
               loop: bool = False) -> None:

    if sound_event is None:
        return
    if (force or account is None or
            allow_sound_notification(account, sound_event)):
        play_sound_file(
            app.settings.get_soundevent_settings(sound_event)['path'], loop)


def check_soundfile_path(file_: str,
                         dirs: list[Path] | None = None
                         ) -> Path | None:
    '''
    Check if the sound file exists

    :param file_: the file to check, absolute or relative to 'dirs' path
    :param dirs: list of knows paths to fallback if the file doesn't exists
                                     (eg: ~/.gajim/sounds/, DATADIR/sounds...).
    :return      the path to file or None if it doesn't exists.
    '''
    if not file_:
        return None
    if Path(file_).exists():
        return Path(file_)

    if dirs is None:
        dirs = [configpaths.get('MY_DATA'),
                configpaths.get('DATA')]

    for dir_ in dirs:
        dir_ = dir_ / 'sounds' / file_
        if dir_.exists():
            return dir_
    return None


def strip_soundfile_path(file_: Path | str,
                         dirs: list[Path] | None = None,
                         abs_: bool = True):
    '''
    Remove knowns paths from a sound file

    Filechooser returns an absolute path.
    If path is a known fallback path, we remove it.
    So config has no hardcoded path to DATA_DIR and text in textfield is
    shorther.
    param: file_: the filename to strip
    param: dirs: list of knowns paths from which the filename should be stripped
    param: abs_: force absolute path on dirs
    '''

    if not file_:
        return None

    if dirs is None:
        dirs = [configpaths.get('MY_DATA'),
                configpaths.get('DATA')]

    file_ = Path(file_)
    name = file_.name
    for dir_ in dirs:
        dir_ = dir_ / 'sounds' / name
        if abs_:
            dir_ = dir_.absolute()
        if file_ == dir_:
            return name
    return file_


def play_sound_file(str_path_to_soundfile: str, loop: bool = False) -> None:
    path_to_soundfile = check_soundfile_path(str_path_to_soundfile)
    if path_to_soundfile is None:
        return

    from gajim.common import sound
    sound.play(path_to_soundfile, loop)


def get_client_status(account: str) -> str:
    client = app.get_client(account)
    if client.state.is_disconnected:
        return 'offline'

    if (client.state.is_reconnect_scheduled or
            client.state.is_connecting or
            client.state.is_connected):
        return 'connecting'

    return client.status


def get_global_show() -> str:
    maxi = 0
    for client in app.get_clients():
        if not app.settings.get_account_setting(client.account,
                                                'sync_with_global_status'):
            continue
        status = get_client_status(client.account)
        index = SHOW_LIST.index(status)
        if index > maxi:
            maxi = index
    return SHOW_LIST[maxi]


def get_global_status_message() -> str:
    maxi = 0
    status_message = ''
    for client in app.get_clients():
        if not app.settings.get_account_setting(client.account,
                                                'sync_with_global_status'):
            continue
        index = SHOW_LIST.index(client.status)
        if index > maxi:
            maxi = index
            status_message = client.status_message
    return status_message


def statuses_unified() -> bool:
    '''
    Test if all statuses are the same
    '''
    reference = None
    for client in app.get_clients():
        account = client.account
        if not app.settings.get_account_setting(account,
                                                'sync_with_global_status'):
            continue

        if reference is None:
            reference = get_client_status(account)

        elif reference != get_client_status(account):
            return False
    return True


def get_full_jid_from_iq(iq_obj: Iq) -> str | None:
    '''
    Return the full jid (with resource) from an iq
    '''
    jid = iq_obj.getFrom()
    if jid is None:
        return None
    return parse_jid(str(iq_obj.getFrom()))


def get_jid_from_iq(iq_obj: Iq) -> str | None:
    '''
    Return the jid (without resource) from an iq
    '''
    jid = get_full_jid_from_iq(iq_obj)
    if jid is None:
        return None
    return app.get_jid_without_resource(jid)


def get_auth_sha(sid: str, initiator: str, target: str) -> str:
    '''
    Return sha of sid + initiator + target used for proxy auth
    '''
    return hashlib.sha1(
        (f'{sid}{initiator}{target}').encode()).hexdigest()


def get_random_string(count: int = 16) -> str:
    '''
    Create random string of count length

    WARNING: Don't use this for security purposes
    '''
    allowed = string.ascii_uppercase + string.digits
    return ''.join(random.choice(allowed) for char in range(count))


@functools.lru_cache(maxsize=1)
def get_os_info() -> str:
    info = 'N/A'
    if sys.platform in ('win32', 'darwin'):
        info = f'{platform.system()} {platform.release()}'

    elif sys.platform == 'linux':
        try:
            import distro
            info = distro.name(pretty=True)
        except ImportError:
            info = platform.system()
    return info


def message_needs_highlight(text: str, nickname: str, own_jid: str) -> bool:
    '''
    Check whether 'text' contains 'nickname', 'own_jid', or any string of the
    'muc_highlight_words' setting.
    '''

    search_strings = app.settings.get('muc_highlight_words').split(';')
    search_strings.append(nickname)
    search_strings.append(own_jid)

    search_strings = [word.lower() for word in search_strings if word]
    text = text.lower()

    for search_string in search_strings:
        match = text.find(search_string)

        while match > -1:
            search_end = match + len(search_string)

            if match == 0 and search_end == len(text):
                # Text contains search_string only (exact match)
                return True

            char_before_allowed = bool(
                match == 0 or
                (not text[match - 1].isalpha() and
                text[match - 1] not in ('/', '-')))

            if char_before_allowed and search_end == len(text):
                # search_string found at the end of text and
                # char before search_string is allowed.
                return True

            if char_before_allowed and not text[search_end].isalpha():
                # char_before search_string is allowed and
                # char_after search_string is not alpha.
                return True

            start = match + 1
            match = text.find(search_string, start)

    return False


def allow_showing_notification(account: str) -> bool:
    if not app.settings.get('show_notifications'):
        return False
    if app.settings.get('show_notifications_away'):
        return True
    client = app.get_client(account)
    if client.status == 'online':
        return True
    return False


def allow_sound_notification(account: str, sound_event: str) -> bool:
    if not app.settings.get('sounds_on'):
        return False
    client = app.get_client(account)
    if client.status != 'online' and not app.settings.get('sounddnd'):
        return False
    if app.settings.get_soundevent_settings(sound_event)['enabled']:
        return True
    return False


def get_optional_features(account: str) -> list[str]:
    features: list[str] = []

    if app.settings.get_account_setting(account, 'request_user_data'):
        features.append(Namespace.TUNE + '+notify')
        features.append(Namespace.LOCATION + '+notify')

    features.append(Namespace.NICK + '+notify')

    client = app.get_client(account)

    if client.get_module('Bookmarks').nativ_bookmarks_used:
        features.append(Namespace.BOOKMARKS_1 + '+notify')
    elif client.get_module('Bookmarks').pep_bookmarks_used:
        features.append(Namespace.BOOKMARKS + '+notify')
    if app.is_installed('AV'):
        features.append(Namespace.JINGLE_RTP)
        features.append(Namespace.JINGLE_RTP_AUDIO)
        features.append(Namespace.JINGLE_RTP_VIDEO)
        features.append(Namespace.JINGLE_ICE_UDP)

    # Give plugins the possibility to add their features
    app.plugin_manager.extension_point('update_caps', account, features)
    return features


def jid_is_blocked(account: str, jid: str) -> bool:
    client = app.get_client(account)
    return jid in client.get_module('Blocking').blocked


def get_subscription_request_msg(account: str | None = None) -> str:
    if account is None:
        return _('I would like to add you to my contact list.')

    message = app.settings.get_account_setting(
        account, 'subscription_request_msg')
    if message:
        return message

    message = _('Hello, I am $name. %s') % message
    return Template(message).safe_substitute({'name': app.nicks[account]})


def get_moderation_text(by: str | JID | None,
                        reason: str | None) -> str:

    by_text = ''
    if by is not None:
        by_text = (' by %s') % by
    text = _('This message has been moderated%s.') % by_text
    if reason is not None:
        text += ' ' + _('Reason: %s') % reason
    return text


def get_global_proxy() -> ProxyData | None:
    proxy_name = app.settings.get('global_proxy')
    if not proxy_name:
        return None
    return get_proxy(proxy_name)


def get_account_proxy(account: str, fallback=True) -> ProxyData | None:
    proxy_name = app.settings.get_account_setting(account, 'proxy')
    if proxy_name:
        return get_proxy(proxy_name)

    if fallback:
        return get_global_proxy()
    return None


def get_proxy(proxy_name: str) -> ProxyData | None:
    try:
        settings = app.settings.get_proxy_settings(proxy_name)
    except ValueError:
        return None

    username, password = None, None
    if settings['useauth']:
        username, password = settings['user'], settings['pass']

    return ProxyData(type=settings['type'],
                     host=f"{settings['host']}:{settings['port']}",
                     username=username,
                     password=password)


def determine_proxy() -> ProxyData | None:
    # Use this method to find a proxy for non-account related http requests
    # When there is no global proxy and at least one active account does
    # not use a proxy, we assume no proxy is necessary.

    global_proxy = get_global_proxy()
    if global_proxy is not None:
        return global_proxy

    proxies: list[ProxyData] = []
    for client in app.get_clients():
        account_proxy = get_account_proxy(client.account, fallback=False)
        if account_proxy is None:
            return None

        proxies.append(account_proxy)

    return proxies[0] if proxies else None


def version_condition(current_version: str, required_version: str) -> bool:
    if V(current_version) < V(required_version):
        return False
    return True


def call_counter(func):
    def helper(self, restart=False):
        if restart:
            self._connect_machine_calls = 0
        self._connect_machine_calls += 1
        return func(self)
    return helper


def load_json(path: Path,
              key: str | None = None,
              default: Any | None = None) -> Any:
    try:
        with path.open('r', encoding='utf8') as file:
            json_dict = json.loads(file.read())
    except Exception:
        log.exception('Parsing error')
        return default

    if key is None:
        return json_dict
    return json_dict.get(key, default)


def delay_execution(milliseconds):
    # Delay the first call for `milliseconds`
    # ignore all other calls while the delay is active
    def delay_execution_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            def timeout_wrapper():
                func(*args, **kwargs)
                delattr(func_wrapper, 'source_id')

            if hasattr(func_wrapper, 'source_id'):
                return
            func_wrapper.source_id = GLib.timeout_add(
                milliseconds, timeout_wrapper)
        return func_wrapper
    return delay_execution_decorator


def event_filter(filter_: Any):
    def event_filter_decorator(func: Any) -> Any:
        @wraps(func)
        def func_wrapper(self, event: Any, *args: Any, **kwargs: Any) -> Any:
            for attr in filter_:
                if '=' in attr:
                    attr1, attr2 = attr.split('=')
                else:
                    attr1, attr2 = attr, attr
                try:
                    if getattr(event, attr1) != getattr(self, attr2):
                        return None
                except AttributeError:
                    if getattr(event, attr1) != getattr(self, f'_{attr2}'):
                        return None

            return func(self, event, *args, **kwargs)
        return func_wrapper
    return event_filter_decorator


def catch_exceptions(func):
    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
        except Exception as error:
            log.exception(error)
            return None
        return result
    return func_wrapper


def is_known_uri_scheme(scheme: str) -> bool:
    '''
    `scheme` is lower-case
    '''
    if scheme in iana.URI_SCHEMES:
        return True
    if scheme in NONREGISTERED_URI_SCHEMES:
        return True
    return scheme in app.settings.get('additional_uri_schemes').split()


def parse_xmpp_uri_query(pct_iquerycomp: str) -> tuple[str, dict[str, str]]:
    '''
    Parses 'mess%61ge;b%6Fdy=Hello%20%F0%9F%8C%90%EF%B8%8F' into
    ('message', {'body': 'Hello 🌐️'}), empty string into ('', {}).
    '''
    # Syntax and terminology from
    # <https://rfc-editor.org/rfc/rfc5122#section-2.2>; the pct_ prefix means
    # percent encoding not being undone yet.

    if not pct_iquerycomp:
        return '', {}

    pct_iquerytype, _, pct_ipairs = pct_iquerycomp.partition(';')
    iquerytype = unquote(pct_iquerytype, errors='strict')
    if not pct_ipairs:
        return iquerytype, {}

    pairs: dict[str, str] = {}
    for pct_ipair in pct_ipairs.split(';'):
        pct_ikey, _, pct_ival = pct_ipair.partition('=')
        pairs[
            unquote(pct_ikey, errors='strict')
        ] = unquote(pct_ival, errors='replace')
    return iquerytype, pairs


def parse_uri(uri: str) -> URI:
    try:
        urlparts = urlparse(uri)
    except Exception as err:
        return URI(URIType.INVALID, uri, data={'error': str(err)})

    if not urlparts.scheme:
        return URI(URIType.INVALID, uri, data={'error': 'Relative URI'})

    scheme = urlparts.scheme  # urlparse is expected to return it in lower case

    if not is_known_uri_scheme(scheme):
        return URI(URIType.INVALID, uri, data={'error': 'Unknown scheme'})

    if scheme in ('https', 'http'):
        if not urlparts.netloc:
            err = f'No host or empty host in an {scheme} URI'
            return URI(URIType.INVALID, uri, data={'error': err})
        return URI(URIType.WEB, uri)

    if scheme == 'xmpp':
        if not urlparts.path.startswith('/'):
            pct_jid = urlparts.path
        else:
            pct_jid = urlparts.path[1:]

        data: dict[str, str] = {}
        try:
            data['jid'] = unquote(pct_jid, errors='strict')
            validate_jid(data['jid'])
            qtype, qparams = parse_xmpp_uri_query(urlparts.query)
        except ValueError as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)

        return URI(URIType.XMPP, uri,
                   query_type=qtype,
                   query_params=qparams,
                   data=data)

    if scheme == 'mailto':
        data: dict[str, str] = {}
        try:
            data['addr'] = unquote(urlparts.path, errors='strict')
            validate_jid(data['addr'], 'bare')  # meh, good enough
        except ValueError as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)
        return URI(URIType.MAIL, uri, data=data)

    if scheme == 'tel':
        # https://rfc-editor.org/rfc/rfc3966#section-3
        # TODO: extract number
        return URI(URIType.TEL, uri)

    if scheme == 'geo':
        # TODO: unify with .preview_helpers.split_geo_uri
        # https://rfc-editor.org/rfc/rfc5870#section-3.3
        lat, _, lon_alt = urlparts.path.partition(',')
        if not lat or not lon_alt:
            return URI(URIType.INVALID, uri, data={
                       'error': 'No latitude or longitude'})
        lon, _, alt = lon_alt.partition(',')
        if not lon:
            return URI(URIType.INVALID, uri, data={'error': 'No longitude'})

        data = {'lat': lat, 'lon': lon, 'alt': alt}
        return URI(URIType.GEO, uri, data=data)

    if scheme == 'file':
        # https://rfc-editor.org/rfc/rfc8089.html#section-2
        data: dict[str, str] = {}
        try:
            data['netloc'] = urlparts.netloc
            data['path'] = Gio.File.new_for_uri(uri).get_path()
            assert data['path']
        except Exception as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)
        return URI(URIType.FILE, uri, data=data)

    if scheme == 'about':
        # https://rfc-editor.org/rfc/rfc6694#section-2.1
        data: dict[str, str] = {}
        try:
            token = unquote(urlparts.path, errors='strict')
            if token == 'ambiguous-address':  # noqa: S105
                data['addr'] = unquote(urlparts.query, errors='strict')
                validate_jid(data['addr'], 'bare')
                return URI(URIType.AT, uri, data=data)
            raise Exception(f'Unrecognized about-token "{token}"')
        except Exception as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)

    return URI(URIType.OTHER, uri)


def _handle_message_qtype(
        jid: str, params: dict[str, str], account: str) -> None:
    body = params.get('body')
    # ^ For JOIN, this is a non-standard, but nice extension
    app.window.start_chat_from_jid(account, jid, message=body)


_xmpp_query_type_handlers = {
    XmppUriQuery.NONE: _handle_message_qtype,
    XmppUriQuery.MESSAGE: _handle_message_qtype,
    XmppUriQuery.JOIN: _handle_message_qtype,
}


@catch_exceptions
def open_uri(uri: URI | str, account: str | None = None) -> None:
    if not isinstance(uri, URI):
        uri = parse_uri(uri)

    if uri.type == URIType.FILE:
        opt_name = 'allow_open_file_uris'
        if app.settings.get(opt_name):
            open_file_uri(uri.source)
        else:
            log.info('Blocked opening a file URI, see %s option', opt_name)

    elif uri.type in (URIType.MAIL, URIType.TEL, URIType.WEB, URIType.OTHER):
        open_uri_externally(uri.source)

    elif uri.type == URIType.GEO:
        if Gio.AppInfo.get_default_for_uri_scheme('geo'):
            open_uri_externally(uri.source)
        else:
            open_uri(
                geo_provider_from_location(uri.data['lat'], uri.data['lon']))

    elif uri.type in (URIType.XMPP, URIType.AT):
        if account is None:
            log.warning('Account must be specified to open XMPP uri')
            return

        if uri.type == URIType.XMPP:
            jid = uri.data['jid']
        else:
            jid = uri.data['addr']

        qtype, qparams = XmppUriQuery.from_str(uri.query_type), uri.query_params
        if not qtype:
            log.info('open_uri: can\'t "%s": '
                     'unsupported query type in %s', uri.query_type, uri)
            # From <rfc5122#section-2.5>:
            # > If the processing application does not understand [...] the
            # > specified query type, it MUST ignore the query component and
            # > treat the IRI/URI as consisting of, for example,
            # > <xmpp:example-node@example.com> rather than
            # > <xmpp:example-node@example.com?query>."
            qtype, qparams = XmppUriQuery.NONE, {}
        _xmpp_query_type_handlers[qtype](jid, qparams, account)

    elif uri.type == URIType.INVALID:
        log.warning('open_uri: Invalid %s', uri)
        # TODO: UI error instead

    else:
        log.error('open_uri: No handler for %s', uri)
        # TODO: this is a bug, so, `raise` maybe?


def open_uri_externally(uri: str) -> None:
    if sys.platform == 'win32':
        webbrowser.open(uri, new=2)
    else:
        try:
            Gio.AppInfo.launch_default_for_uri(uri)
        except GLib.Error as err:
            log.info('open_uri_externally: '
                     "Couldn't launch default for %s: %s", uri, err)


def open_file_uri(uri: str) -> None:
    try:
        if sys.platform != 'win32':
            Gio.AppInfo.launch_default_for_uri(uri)
        else:
            os.startfile(uri, 'open')  # noqa: S606
    except Exception as err:
        log.info("Couldn't open file URI %s: %s", uri, err)


@catch_exceptions
def open_file(path: Path) -> None:
    if not path.exists():
        log.warning('Unable to open file, path %s does not exist', path)
        return

    open_file_uri(path.as_uri())


def open_directory(path: Path) -> None:
    return open_file(path)


def show_in_folder(path: Path) -> None:
    if not DBusFileManager().show_items_sync([path.as_uri()]):
        # Fall back to just opening the containing folder
        open_directory(path.parent)


def filesystem_path_from_uri(uri: str) -> Path | None:
    puri = parse_uri(uri)
    if puri.type != URIType.FILE:
        return None

    netloc = puri.data['netloc']
    if netloc and netloc.lower() != 'localhost' and sys.platform != 'win32':
        return None
    return Path(puri.data['path'])


def get_file_path_from_dnd_dropped_uri(text: str) -> Path | None:
    uri = text.strip('\r\n\x00')  # remove \r\n and NULL
    return filesystem_path_from_uri(uri)


def file_is_locked(path_to_file: str) -> bool:
    '''
    Return True if file is locked
    NOTE: Windows only.
    '''
    if os.name != 'nt':
        return False

    if not HAS_PYWIN32:
        return False

    secur_att = pywintypes.SECURITY_ATTRIBUTES()
    secur_att.Initialize()

    try:
        # try create a handle for READING the file
        hfile = win32file.CreateFile(
            path_to_file,
            win32con.GENERIC_READ,  # open for reading
            0,  # do not share with other proc
            secur_att,
            win32con.OPEN_EXISTING,  # existing file only
            win32con.FILE_ATTRIBUTE_NORMAL,  # normal file
            0)  # no attr. template
    except pywintypes.error:
        return True
    else:  # in case all went ok, close file handle
        hfile.Close()
        return False


def geo_provider_from_location(lat: str, lon: str) -> str:
    return f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=16'


def get_resource(account: str) -> str | None:
    resource = app.settings.get_account_setting(account, 'resource')
    if not resource:
        return None

    resource = Template(resource).safe_substitute(
        {'hostname': socket.gethostname(),
         'rand': get_random_string()})
    app.settings.set_account_setting(account, 'resource', resource)
    return resource


def get_default_muc_config() -> dict[str, bool | str]:
    return {
        # XEP-0045 options
        # https://xmpp.org/registrar/formtypes.html

        'muc#roomconfig_allowinvites': True,
        'muc#roomconfig_allowpm': 'anyone',
        'muc#roomconfig_changesubject': False,
        'muc#roomconfig_enablelogging': False,
        'muc#roomconfig_membersonly': True,
        'muc#roomconfig_moderatedroom': False,
        'muc#roomconfig_passwordprotectedroom': False,
        'muc#roomconfig_persistentroom': True,
        'muc#roomconfig_publicroom': False,
        'muc#roomconfig_whois': 'moderators',

        # Ejabberd options
        'allow_voice_requests': False,
        'public_list': False,
        'mam': True,

        # Prosody options
        '{http://prosody.im/protocol/muc}roomconfig_allowmemberinvites': False,
        'muc#roomconfig_enablearchiving': True,
    }


def validate_jid(jid: str | JID, type_: str | None = None) -> JID:
    try:
        jid = JID.from_string(str(jid))
    except InvalidJid as error:
        raise ValueError(error)

    if type_ is None:
        return jid
    if type_ == 'bare' and jid.is_bare:
        return jid
    if type_ == 'full' and jid.is_full:
        return jid
    if type_ == 'domain' and jid.is_domain:
        return jid

    raise ValueError(f'Not a {type_} JID')


def to_user_string(error: CommonError | StanzaError) -> str:
    text = error.get_text(get_rfc5646_lang())
    if text:
        return text

    condition = error.condition
    if error.app_condition is not None:
        return f'{condition} ({error.app_condition})'
    return condition


def get_groupchat_name(client: types.Client, jid: JID) -> str:
    name = client.get_module('Bookmarks').get_name_from_bookmark(jid)
    if name:
        return name

    disco_info = app.storage.cache.get_last_disco_info(jid)
    if disco_info is not None:
        if disco_info.muc_name:
            return disco_info.muc_name

    return jid.localpart


def is_affiliation_change_allowed(self_contact: types.GroupchatParticipant,
                                  contact: types.GroupchatParticipant,
                                  target_aff: str | Affiliation) -> bool:
    if isinstance(target_aff, str):
        target_aff = Affiliation(target_aff)

    if contact.affiliation == target_aff:
        # Contact has already the target affiliation
        return False

    if self_contact.affiliation.is_owner:
        return True

    if not self_contact.affiliation.is_admin:
        return False

    if target_aff in (Affiliation.OWNER, Affiliation.ADMIN):
        # Admin can’t edit admin/owner list
        return False

    return self_contact.affiliation > contact.affiliation


def is_role_change_allowed(self_contact: types.GroupchatParticipant,
                           contact: types.GroupchatParticipant) -> bool:

    if self_contact.role < Role.MODERATOR:
        return False
    return self_contact.affiliation >= contact.affiliation


def is_moderation_allowed(self_contact: types.GroupchatParticipant,
                          contact: types.GroupchatParticipant) -> bool:

    if self_contact.role < Role.MODERATOR:
        return False
    return self_contact.affiliation >= contact.affiliation


def get_tls_error_phrases(tls_errors: set[Gio.TlsCertificateFlags]
                          ) -> list[str]:
    return [GIO_TLS_ERRORS[err] for err in tls_errors]


class Observable:
    def __init__(self, log_: logging.Logger | LogAdapter | None = None):
        self._log = log_
        self._callbacks: types.ObservableCbDict = defaultdict(list)

    def __disconnect(self,
                     obj: Any,
                     signals: set[str] | None = None
                     ) -> None:

        def _remove(handlers: list[weakref.WeakMethod[types.AnyCallableT]]
                    ) -> None:

            for handler in list(handlers):
                func = handler()
                # Don’t remove dead weakrefs from the handler list
                # notify() will remove dead refs, and __disconnect()
                # can be called from inside notify(), this can lead
                # to race conditions where later notfiy tries to remove
                # a dead ref which is not anymore in the list.
                if func is not None and func.__self__ is obj:
                    handlers.remove(handler)

        if signals is None:
            for handlers in self._callbacks.values():
                _remove(handlers)

        else:
            for signal in signals:
                _remove(self._callbacks.get(signal, []))

    def disconnect_signals(self) -> None:
        self._callbacks = defaultdict(list)

    def multi_disconnect(self,
                         obj: Any,
                         signals: set[str] | None
                         ) -> None:

        self.__disconnect(obj, signals)

    def disconnect_all_from_obj(self, obj: Any) -> None:
        self.__disconnect(obj)

    def disconnect(self, obj: Any) -> None:
        self.disconnect_all_from_obj(obj)

    def disconnect_signal(self, obj: Any, signal: str) -> None:
        self.__disconnect(obj, {signal})

    def connect_signal(self,
                       signal_name: str,
                       func: types.AnyCallableT) -> None:
        if not inspect.ismethod(func):
            raise ValueError('Only bound methods allowed')

        weak_func = weakref.WeakMethod(func)

        if weak_func in self._callbacks[signal_name]:
            # Don’t register handler multiple times
            return

        self._callbacks[signal_name].append(weak_func)

    def connect(self,
                signal_name: str,
                func: types.AnyCallableT) -> None:
        self.connect_signal(signal_name, func)

    def multi_connect(self, signal_dict: dict[str, types.AnyCallableT]):
        for signal_name, func in signal_dict.items():
            self.connect_signal(signal_name, func)

    def notify(self, signal_name: str, *args: Any, **kwargs: Any):
        signal_callbacks = self._callbacks.get(signal_name)
        if not signal_callbacks:
            return

        if self._log is not None:
            self._log.info('Signal: %s', signal_name)

        for weak_method in list(signal_callbacks):
            func = weak_method()
            if func is None:
                self._callbacks[signal_name].remove(weak_method)
                continue
            func(self, signal_name, *args, **kwargs)


def write_file_async(
        path: Path,
        data: bytes,
        callback: Callable[[bool, GLib.Error | None, Any], Any],
        user_data: Any | None = None):

    def _on_write_finished(outputstream: Gio.OutputStream,
                           result: Gio.AsyncResult,
                           _data: bytes) -> None:
        try:
            successful, _bytes_written = outputstream.write_all_finish(result)
        except GLib.Error as error:
            callback(False, error, user_data)
        else:
            callback(successful, None, user_data)

    def _on_file_created(file: Gio.File, result: Gio.AsyncResult) -> None:
        try:
            outputstream = file.create_finish(result)
        except GLib.Error as error:
            callback(False, error, user_data)
            return

        # Pass data as user_data to the callback, because
        # write_all_async() takes no reference to the data
        # and python gc collects it before the data is written
        outputstream.write_all_async(data,
                                     GLib.PRIORITY_DEFAULT,
                                     None,
                                     _on_write_finished,
                                     data)

    file = Gio.File.new_for_path(str(path))
    file.create_async(Gio.FileCreateFlags.PRIVATE,
                      GLib.PRIORITY_DEFAULT,
                      None,
                      _on_file_created)


def load_file_async(path: Path,
                    callback: Callable[[bytes | None,
                                        GLib.Error | None,
                                        Any | None], Any],
                    user_data: Any | None = None) -> None:

    def _on_load_finished(file: Gio.File,
                          result: Gio.AsyncResult) -> None:

        try:
            _, contents, _ = file.load_contents_finish(result)
        except GLib.Error as error:
            callback(None, error, user_data)
        else:
            callback(contents, None, user_data)

    file = Gio.File.new_for_path(str(path))
    file.load_contents_async(None, _on_load_finished)


def get_x509_cert_from_gio_cert(cert: Gio.TlsCertificate) -> x509.Certificate:
    glib_bytes = GLib.ByteArray.free_to_bytes(cert.props.certificate)
    return x509.load_der_x509_certificate(
        glib_bytes.get_data(), default_backend())


def get_custom_host(
    account: str
) -> tuple[str, ConnectionProtocol, ConnectionType] | None:

    if not app.settings.get_account_setting(account, 'use_custom_host'):
        return None
    host = app.settings.get_account_setting(account, 'custom_host')
    port = app.settings.get_account_setting(account, 'custom_port')
    type_ = app.settings.get_account_setting(account, 'custom_type')

    if host.startswith(('ws://', 'wss://')):
        protocol = ConnectionProtocol.WEBSOCKET
    else:
        host = f'{host}:{port}'
        protocol = ConnectionProtocol.TCP

    return (host, protocol, ConnectionType(type_))


def warn_about_plain_connection(account: str,
                                connection_types: list[ConnectionType]
                                ) -> bool:
    warn = app.settings.get_account_setting(
        account, 'confirm_unencrypted_connection')
    return any(type_.is_plain and warn for type_ in connection_types)


def get_idle_status_message(state: str, status_message: str) -> str:
    message = app.settings.get(f'auto{state}_message')
    if not message:
        return status_message

    message = message.replace('$S', '%(status)s')
    message = message.replace('$T', '%(time)s')
    return message % {
        'status': status_message,
        'time': app.settings.get(f'auto{state}time')
    }


def get_group_chat_nick(account: str, room_jid: JID | str) -> str:
    client = app.get_client(account)

    bookmark = client.get_module('Bookmarks').get_bookmark(room_jid)
    if bookmark is not None:
        if bookmark.nick is not None:
            return bookmark.nick

    return app.nicks[account]


def get_random_muc_localpart() -> str:
    rand = random.randrange(4)
    is_vowel = bool(random.getrandbits(1))
    result = ''
    for _n in range(rand * 2 + (5 - rand)):
        if is_vowel:
            result = f'{result}{VOWELS[random.randrange(len(VOWELS))]}'
        else:
            result = f'{result}{CONSONANTS[random.randrange(len(CONSONANTS))]}'
        is_vowel = not is_vowel
    return result


def get_start_of_day(date_time: datetime) -> datetime:
    return date_time.replace(hour=0,
                             minute=0,
                             second=0,
                             microsecond=0)


def get_os_name() -> str:
    if sys.platform in ('win32', 'darwin'):
        return platform.system()
    if os.name == 'posix':
        try:
            import distro
            return distro.name(pretty=True)
        except ImportError:
            return platform.system()
    return ''


def get_os_version() -> str:
    if sys.platform in ('win32', 'darwin'):
        return platform.version()
    if os.name == 'posix':
        try:
            import distro
            return distro.version(pretty=True)
        except ImportError:
            return platform.release()
    return ''


def get_gobject_version() -> str:
    return '.'.join(map(str, GObject.pygobject_version))


def get_glib_version() -> str:
    return '.'.join(map(str, [GLib.MAJOR_VERSION,
                              GLib.MINOR_VERSION,
                              GLib.MICRO_VERSION]))


def get_soup_version() -> str:
    return '.'.join(map(str, [Soup.get_major_version(),
                              Soup.get_minor_version(),
                              Soup.get_micro_version()]))


def package_version(requirement: str) -> bool:
    req = Requirement(requirement)

    try:
        installed_version = importlib.metadata.version(req.name)
    except importlib.metadata.PackageNotFoundError:
        return False

    return installed_version in req.specifier


def python_version(specifier_set: str) -> bool:
    spec = SpecifierSet(specifier_set)
    return CURRENT_PYTHON_VERSION in spec


def make_path_from_jid(base_path: Path, jid: JID) -> Path:
    assert jid.domain is not None
    domain = jid.domain[:50]

    if jid.localpart is None:
        return base_path / domain

    path = base_path / domain / jid.localpart[:50]
    if jid.resource is not None:
        return path / jid.resource[:30]
    return path


def format_idle_time(idle_time: datetime) -> str:
    now = datetime.now(timezone.utc)

    now_date = now.date()
    idle_date = idle_time.date()

    if idle_date == now_date:
        return idle_time.strftime(app.settings.get('time_format'))
    if idle_date == now_date - timedelta(days=1):
        return _('Yesterday (%s)') % idle_time.strftime(
            app.settings.get('time_format'))
    if idle_date >= now_date - timedelta(days=6):
        return idle_time.strftime(f'%a {app.settings.get("time_format")}')

    return idle_date.strftime(app.settings.get('date_format'))


def get_uuid() -> str:
    return str(uuid.uuid4())
