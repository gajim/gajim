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

import hashlib
import inspect
import json
import logging
import os
import random
import socket
import sys
import unicodedata
import uuid
import weakref
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from string import Template

import precis_i18n.codec  # noqa: F401
import qrcode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.const import Affiliation
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.const import Role
from nbxmpp.errors import StanzaError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import CommonError
from nbxmpp.structs import ProxyData
from qrcode.image.pil import PilImage as QrcPilImage

from gajim.common import app
from gajim.common import configpaths
from gajim.common import types
from gajim.common.const import CONSONANTS
from gajim.common.const import GIO_TLS_ERRORS
from gajim.common.const import VOWELS
from gajim.common.i18n import get_rfc5646_lang
from gajim.common.util.text import get_random_string

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


def get_auth_sha(sid: str, initiator: str, target: str) -> str:
    '''
    Return sha of sid + initiator + target used for proxy auth
    '''
    return hashlib.sha1(
        (f'{sid}{initiator}{target}').encode()).hexdigest()


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
    if proxy_name == 'no-proxy':
        return ProxyData(type='direct',
                         host='',
                         username=None,
                         password=None)

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


def get_uuid() -> str:
    return str(uuid.uuid4())
