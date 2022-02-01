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
from typing import Callable
from typing import Optional
from typing import Union

import sys
import re
import os
import subprocess
import base64
import hashlib
import shlex
import socket
import logging
import json
import copy
import collections
import platform
import functools
from collections import defaultdict
import random
import weakref
import inspect
import string
import webbrowser
from string import Template
import urllib
from datetime import datetime
from datetime import timedelta
from urllib.parse import unquote
from encodings.punycode import punycode_encode
from functools import wraps
from pathlib import Path
from packaging.version import Version as V

from nbxmpp.namespaces import Namespace
from nbxmpp.const import Role
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.const import Affiliation
from nbxmpp.errors import StanzaError
from nbxmpp.structs import ProxyData
from nbxmpp.protocol import JID
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import Iq

from OpenSSL.crypto import X509, load_certificate
from OpenSSL.crypto import FILETYPE_PEM

from gi.repository import Gio
from gi.repository import GLib

import precis_i18n.codec  # pylint: disable=unused-import

from gajim.common import app
from gajim.common import configpaths
from gajim.common.i18n import Q_
from gajim.common.i18n import _
from gajim.common.i18n import ngettext
from gajim.common.i18n import get_rfc5646_lang
from gajim.common.const import ShowConstant
from gajim.common.const import URIType
from gajim.common.const import URIAction
from gajim.common.const import GIO_TLS_ERRORS
from gajim.common.const import SHOW_LIST
from gajim.common.regex import INVALID_XML_CHARS_REGEX
from gajim.common.regex import STH_AT_STH_DOT_STH_REGEX
from gajim.common.structs import URI
from gajim.common import types

HAS_PYWIN32 = False
if os.name == 'nt':
    try:
        import win32file
        import win32con
        import pywintypes
        HAS_PYWIN32 = True
    except ImportError:
        pass

log = logging.getLogger('gajim.c.helpers')

URL_REGEX = re.compile(
    r"(www\.(?!\.)|[a-z][a-z0-9+.-]*://)[^\s<>'\"]+[^!,\.\s<>\)'\"\]]")


class InvalidFormat(Exception):
    pass


def parse_jid(jidstring: str) -> str:
    try:
        return str(validate_jid(jidstring))
    except Exception as error:
        raise InvalidFormat(error)

def idn_to_ascii(host: str) -> str:
    """
    Convert IDN (Internationalized Domain Names) to ACE (ASCII-compatible
    encoding)
    """
    from encodings import idna
    labels = idna.dots.split(host)
    converted_labels: list[str] = []
    for label in labels:
        if label:
            converted_labels.append(idna.ToASCII(label).decode('utf-8'))
        else:
            converted_labels.append('')
    return ".".join(converted_labels)

def ascii_to_idn(host: str) -> str:
    """
    Convert ACE (ASCII-compatible encoding) to IDN (Internationalized Domain
    Names)
    """
    from encodings import idna
    labels = idna.dots.split(host)
    converted_labels: list[str] = []
    for label in labels:
        converted_labels.append(idna.ToUnicode(label))
    return ".".join(converted_labels)

def puny_encode_url(url: str) -> Optional[str]:
    _url = url
    if '//' not in _url:
        _url = '//' + _url
    try:
        o = urllib.parse.urlparse(_url)
        p_loc = idn_to_ascii(o.hostname)
    except Exception:
        log.debug('urlparse failed: %s', url)
        return None
    return url.replace(o.hostname, p_loc)

def parse_resource(resource: str) -> Optional[str]:
    """
    Perform stringprep on resource and return it
    """
    if not resource:
        return None

    try:
        return resource.encode('OpaqueString').decode('utf-8')
    except UnicodeError:
        raise InvalidFormat('Invalid character in resource.')

def windowsify(word: str) -> str:
    if os.name == 'nt':
        return word.capitalize()
    return word

def get_uf_show(show: Union[ShowConstant, str],
                use_mnemonic: bool = False) -> str:
    """
    Return a userfriendly string for dnd/xa/chat and make all strings
    translatable

    If use_mnemonic is True, it adds _ so GUI should call with True for
    accessibility issues
    """
    if isinstance(show, ShowConstant):
        show = show.name.lower()

    if show == 'dnd':
        if use_mnemonic:
            uf_show = _('_Busy')
        else:
            uf_show = _('Busy')
    elif show == 'xa':
        if use_mnemonic:
            uf_show = _('_Not Available')
        else:
            uf_show = _('Not Available')
    elif show == 'chat':
        if use_mnemonic:
            uf_show = _('_Free for Chat')
        else:
            uf_show = _('Free for Chat')
    elif show == 'online':
        if use_mnemonic:
            uf_show = Q_('?user status:_Available')
        else:
            uf_show = Q_('?user status:Available')
    elif show == 'connecting':
        uf_show = _('Connecting')
    elif show == 'away':
        if use_mnemonic:
            uf_show = _('A_way')
        else:
            uf_show = _('Away')
    elif show == 'offline':
        if use_mnemonic:
            uf_show = _('_Offline')
        else:
            uf_show = _('Offline')
    elif show == 'not in roster':
        uf_show = _('Not in contact list')
    elif show == 'requested':
        uf_show = Q_('?contact has status:Unknown')
    else:
        uf_show = Q_('?contact has status:Has errors')
    return uf_show

def get_uf_sub(sub: str) -> str:
    if sub == 'none':
        uf_sub = Q_('?Subscription we already have:None')
    elif sub == 'to':
        uf_sub = _('To')
    elif sub == 'from':
        uf_sub = _('From')
    elif sub == 'both':
        uf_sub = _('Both')
    else:
        uf_sub = _('Unknown')

    return uf_sub

def get_uf_ask(ask: Union[str, None]) -> str:
    if ask is None:
        uf_ask = Q_('?Ask (for Subscription):None')
    elif ask == 'subscribe':
        uf_ask = _('Subscribe')
    else:
        uf_ask = ask

    return uf_ask

def get_uf_role(role: Union[Role, str], plural: bool = False) -> str:
    ''' plural determines if you get Moderators or Moderator'''
    if not isinstance(role, str):
        role = role.value

    if role == 'none':
        return Q_('?Group Chat Contact Role:None')
    if role == 'moderator':
        if plural:
            return _('Moderators')
        return _('Moderator')
    if role == 'participant':
        if plural:
            return _('Participants')
        return _('Participant')
    if role == 'visitor':
        if plural:
            return _('Visitors')
        return _('Visitor')
    return ''

def get_uf_affiliation(affiliation: Union[Affiliation, str],
                       plural: bool = False
                       ) -> str:
    '''Get a nice and translated affilition for muc'''
    if not isinstance(affiliation, str):
        affiliation = affiliation.value

    if affiliation == 'none':
        return Q_('?Group Chat Contact Affiliation:None')
    if affiliation == 'owner':
        if plural:
            return _('Owners')
        return _('Owner')
    if affiliation == 'admin':
        if plural:
            return _('Administrators')
        return _('Administrator')
    if affiliation == 'member':
        if plural:
            return _('Members')
        return _('Member')
    return ''

def get_uf_relative_time(timestamp: float) -> str:
    date_time = datetime.fromtimestamp(timestamp)
    now = datetime.now()
    timespan = now - date_time

    if timespan > timedelta(days=365):
        return str(date_time.year)
    if timespan > timedelta(days=7):
        return date_time.strftime('%b %d')
    if timespan > timedelta(days=2):
        return date_time.strftime('%a')
    if date_time.strftime('%d') != now.strftime('%d'):
        return _('Yesterday')
    if timespan > timedelta(minutes=15):
        return date_time.strftime('%H:%M')
    if timespan > timedelta(minutes=1):
        minutes = int(timespan.seconds / 60)
        return ngettext('%i min ago',
                        '%i mins ago',
                        minutes,
                        minutes,
                        minutes)
    return _('Just now')

def get_sorted_keys(adict):
    keys = sorted(adict.keys())
    return keys

def to_one_line(msg: str) -> str:
    msg = msg.replace('\\', '\\\\')
    msg = msg.replace('\n', '\\n')
    # s1 = 'test\ntest\\ntest'
    # s11 = s1.replace('\\', '\\\\')
    # s12 = s11.replace('\n', '\\n')
    # s12
    # 'test\\ntest\\\\ntest'
    return msg

def from_one_line(msg: str) -> str:
    # (?<!\\) is a lookbehind assertion which asks anything but '\'
    # to match the regexp that follows it

    # So here match '\\n' but not if you have a '\' before that
    expr = re.compile(r'(?<!\\)\\n')
    msg = expr.sub('\n', msg)
    msg = msg.replace('\\\\', '\\')
    # s12 = 'test\\ntest\\\\ntest'
    # s13 = re.sub('\n', s12)
    # s14 s13.replace('\\\\', '\\')
    # s14
    # 'test\ntest\\ntest'
    return msg

def get_uf_chatstate(chatstate: str) -> str:
    """
    Remove chatstate jargon and returns user friendly messages
    """
    if chatstate == 'active':
        return _('is paying attention to the conversation')
    if chatstate == 'inactive':
        return _('is doing something else')
    if chatstate == 'composing':
        return _('is composing a message…')
    if chatstate == 'paused':
        #paused means he or she was composing but has stopped for a while
        return _('paused composing a message')
    if chatstate == 'gone':
        return _('has closed the chat window or tab')
    return ''

def exec_command(command: str,
                 use_shell: bool = False,
                 posix: bool = True
                 ) -> None:
    """
    execute a command. if use_shell is True, we run the command as is it was
    typed in a console. So it may be dangerous if you are not sure about what
    is executed.
    """
    if use_shell:
        subprocess.Popen(f'{command} &', shell=True).wait()
    else:
        args = shlex.split(command, posix=posix)
        process = subprocess.Popen(args)
        app.thread_interface(process.wait)

def build_command(executable: str, parameter: str) -> str:
    # we add to the parameter (can hold path with spaces)
    # "" so we have good parsing from shell
    parameter = parameter.replace('"', '\\"')  # but first escape "
    command = f'{executable} "{parameter}"'
    return command

def get_file_path_from_dnd_dropped_uri(uri: str) -> str:
    path = urllib.parse.unquote(uri)  # escape special chars
    path = path.strip('\r\n\x00')  # remove \r\n and NULL
    # get the path to file
    if re.match('^file:///[a-zA-Z]:/', path):  # windows
        path = path[8:]  # 8 is len('file:///')
    elif path.startswith('file://'):  # nautilus, rox
        path = path[7:]  # 7 is len('file://')
    elif path.startswith('file:'):  # xffm
        path = path[5:]  # 5 is len('file:')
    return path

def sanitize_filename(filename: str) -> str:
    """
    Make sure the filename we will write does contain only acceptable and latin
    characters, and is not too long (in that case hash it)
    """
    # 48 is the limit
    if len(filename) > 48:
        hash_ = hashlib.md5(filename.encode('utf-8'))
        filename = base64.b64encode(hash_.digest()).decode('utf-8')

    # make it latin chars only
    filename = punycode_encode(filename).decode('utf-8')
    filename = filename.replace('/', '_')
    if os.name == 'nt':
        filename = filename.replace('?', '_').replace(':', '_')\
                .replace('\\', '_').replace('"', "'").replace('|', '_')\
                .replace('*', '_').replace('<', '_').replace('>', '_')

    return filename

def reduce_chars_newlines(text: str, max_chars: int = 0,
                          max_lines: int = 0) -> str:
    """
    Cut the chars after 'max_chars' on each line and show only the first
    'max_lines'

    If any of the params is not present (None or 0) the action on it is not
    performed
    """
    def _cut_if_long(string_: str) -> str:
        if len(string_) > max_chars:
            string_ = string_[:max_chars - 3] + '…'
        return string_

    if max_lines == 0:
        lines = text.split('\n')
    else:
        lines = text.split('\n', max_lines)[:max_lines]
    if max_chars > 0:
        if lines:
            lines = [_cut_if_long(e) for e in lines]
    if lines:
        reduced_text = '\n'.join(lines)
        if reduced_text != text:
            reduced_text += '…'
    else:
        reduced_text = ''
    return reduced_text


def get_contact_dict_for_account(account: str) -> dict[str, types.BareContact]:
    """
    Creates a dict of jid -> contact with all contacts of account
    Can be used for completion lists
    """
    contacts_dict: dict[str, types.BareContact] = {}
    client = app.get_client(account)
    for contact in client.get_module('Roster').iter_contacts():
        contacts_dict[str(contact.jid)] = contact
    return contacts_dict


def play_sound(sound_event: str,
               account: Optional[str] = None,
               force: bool = False,
               loop: bool = False) -> None:

    if sound_event is None:
        return
    if (force or account is None or
            allow_sound_notification(account, sound_event)):
        play_sound_file(
            app.settings.get_soundevent_settings(sound_event)['path'], loop)


def check_soundfile_path(file_: str,
                         dirs: Optional[list[Path]] = None
                         ) -> Optional[Path]:
    """
    Check if the sound file exists

    :param file_: the file to check, absolute or relative to 'dirs' path
    :param dirs: list of knows paths to fallback if the file doesn't exists
                                     (eg: ~/.gajim/sounds/, DATADIR/sounds...).
    :return      the path to file or None if it doesn't exists.
    """
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

def strip_soundfile_path(file_, dirs=None, abs_=True):
    """
    Remove knowns paths from a sound file

    Filechooser returns an absolute path.
    If path is a known fallback path, we remove it.
    So config has no hardcoded path to DATA_DIR and text in textfield is
    shorther.
    param: file_: the filename to strip
    param: dirs: list of knowns paths from which the filename should be stripped
    param: abs_: force absolute path on dirs
    """

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

def get_connection_status(account: str) -> str:
    if not app.account_is_available(account):
        return 'error'
    con = app.connections[account]
    if con.state.is_reconnect_scheduled:
        return 'error'

    if con.state.is_connecting or con.state.is_connected:
        return 'connecting'

    if con.state.is_disconnected:
        return 'offline'
    return con.status

def get_global_show() -> str:
    maxi = 0
    for account in app.connections:
        if not app.settings.get_account_setting(account,
                                                'sync_with_global_status'):
            continue
        status = get_connection_status(account)
        index = SHOW_LIST.index(status)
        if index > maxi:
            maxi = index
    return SHOW_LIST[maxi]

def get_global_status_message() -> str:
    maxi = 0
    status_message = ''
    for account, con in app.connections.items():
        if not app.settings.get_account_setting(account,
                                                'sync_with_global_status'):
            continue
        index = SHOW_LIST.index(con.status)
        if index > maxi:
            maxi = index
            status_message = con.status_message
    return status_message

def statuses_unified() -> bool:
    """
    Test if all statuses are the same
    """
    reference = None
    for account, con in app.connections.items():
        if not app.settings.get_account_setting(account,
                                                'sync_with_global_status'):
            continue
        if reference is None:
            reference = con.status
        elif reference != con.status:
            return False
    return True


def get_full_jid_from_iq(iq_obj: Iq) -> Optional[str]:
    """
    Return the full jid (with resource) from an iq
    """
    jid = iq_obj.getFrom()
    if jid is None:
        return None
    return parse_jid(str(iq_obj.getFrom()))

def get_jid_from_iq(iq_obj: Iq) -> Optional[str]:
    """
    Return the jid (without resource) from an iq
    """
    jid = get_full_jid_from_iq(iq_obj)
    if jid is None:
        return None
    return app.get_jid_without_resource(jid)

def get_auth_sha(sid: str, initiator: str, target: str) -> str:
    """
    Return sha of sid + initiator + target used for proxy auth
    """
    return hashlib.sha1(
        (f'{sid}{initiator}{target}').encode('utf-8')).hexdigest()

def remove_invalid_xml_chars(string_: str) -> str:
    if string_:
        string_ = re.sub(INVALID_XML_CHARS_REGEX, '', string_)
    return string_

def get_random_string(count: int = 16) -> str:
    """
    Create random string of count length

    WARNING: Don't use this for security purposes
    """
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
    """
    Check text to see whether any of the words in (muc_highlight_words and
    nick) appear
    """
    special_words = app.settings.get('muc_highlight_words').split(';')
    special_words.append(nickname)
    special_words.append(own_jid)
    # Strip empties: ''.split(';') == [''] and would highlight everything.
    # Also lowercase everything for case insensitive compare.
    special_words = [word.lower() for word in special_words if word]
    text = text.lower()

    for special_word in special_words:
        found_here = text.find(special_word)
        while found_here > -1:
            end_here = found_here + len(special_word)
            if ((found_here == 0 or not text[found_here - 1].isalpha()) and
                    (end_here == len(text) or not text[end_here].isalpha())):
                # It is beginning of text or char before is not alpha AND
                # it is end of text or char after is not alpha
                return True
            # continue searching
            start = found_here + 1
            found_here = text.find(special_word, start)
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


def get_optional_features(account: str) -> list[Namespace]:
    features: list[str] = []

    if app.settings.get_account_setting(account, 'request_user_data'):
        features.append(Namespace.TUNE + '+notify')
        features.append(Namespace.LOCATION + '+notify')

    features.append(Namespace.NICK + '+notify')

    if app.connections[account].get_module('Bookmarks').nativ_bookmarks_used:
        features.append(Namespace.BOOKMARKS_1 + '+notify')
    elif app.connections[account].get_module('Bookmarks').pep_bookmarks_used:
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
    con = app.connections[account]
    return jid in con.get_module('Blocking').blocked

def get_subscription_request_msg(account: Optional[str] = None) -> str:
    message = _('I would like to add you to my contact list.')
    if account is None:
        return message

    message = app.settings.get_account_setting(
        account, 'subscription_request_msg')
    if message:
        return message

    message = _('Hello, I am $name. %s') % message
    return Template(message).safe_substitute({'name': app.nicks[account]})

def get_retraction_text(account: str, moderator_jid: str,
                        reason: Optional[str]) -> str:
    client = app.get_client(account)
    contact = client.get_module('Contacts').get_contact(
        moderator_jid, groupchat=True)
    text = _('This message has been retracted by %s.') % contact.name
    if reason is not None:
        text += ' ' + _('Reason: %s') % reason
    return text

def get_user_proxy(account: str) -> Optional[ProxyData]:
    proxy_name = app.settings.get_account_setting(account, 'proxy')
    if not proxy_name:
        return None
    return get_proxy(proxy_name)

def get_proxy(proxy_name: str) -> Optional[ProxyData]:
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

def version_condition(current_version: str, required_version: str) -> bool:
    if V(current_version) < V(required_version):
        return False
    return True

def get_available_emoticon_themes() -> list[str]:
    files: list[Path] = []
    for folder in configpaths.get('EMOTICONS').iterdir():
        if not folder.is_dir():
            continue
        files += [theme for theme in folder.iterdir() if theme.is_file()]

    my_emots = configpaths.get('MY_EMOTS')
    if my_emots.is_dir():
        files += list(my_emots.iterdir())

    emoticons_themes = ['font']
    emoticons_themes += [file.stem for file in files if file.suffix == '.png']
    return sorted(emoticons_themes)

def call_counter(func):
    def helper(self, restart=False):
        if restart:
            self._connect_machine_calls = 0
        self._connect_machine_calls += 1
        return func(self)
    return helper

def load_json(path: Path,
              key: Optional[str] = None,
              default: Optional[Any] = None) -> Any:
    try:
        with path.open('r') as file:
            json_dict = json.loads(file.read())
    except Exception:
        log.exception('Parsing error')
        return default

    if key is None:
        return json_dict
    return json_dict.get(key, default)


def ignore_contact(account: str, jid: JID) -> bool:
    client = app.get_client(account)
    contact = client.get_module('Contacts').get_contact(jid)

    ignore_unknown = app.settings.get_account_setting(
        account, 'ignore_unknown_contacts')
    if ignore_unknown and not contact.is_in_roster:
        log.info('Ignore unknown contact %s', str(jid))
        return True
    return False


class AdditionalDataDict(collections.UserDict):
    data: dict[str, Any]

    @staticmethod
    def _get_path_childs(full_path: str) -> list[str]:
        path_childs = [full_path]
        if ':' in full_path:
            path_childs = full_path.split(':')
        return path_childs

    def set_value(self, full_path: str, key: str, value: Optional[str]) -> None:
        path_childs = self._get_path_childs(full_path)
        _dict = self.data
        for path in path_childs:
            try:
                _dict = _dict[path]
            except KeyError:
                _dict[path] = {}
                _dict = _dict[path]
        _dict[key] = value

    def get_value(self,
                  full_path: str,
                  key: str,
                  default: Optional[str] = None) -> Optional[Any]:

        path_childs = self._get_path_childs(full_path)
        _dict = self.data
        for path in path_childs:
            try:
                _dict = _dict[path]
            except KeyError:
                return default
        try:
            return _dict[key]
        except KeyError:
            return default

    def remove_value(self, full_path: str, key: str) -> None:
        path_childs = self._get_path_childs(full_path)
        _dict = self.data
        for path in path_childs:
            try:
                _dict = _dict[path]
            except KeyError:
                return
        try:
            del _dict[key]
        except KeyError:
            return

    def copy(self) -> AdditionalDataDict:
        return copy.deepcopy(self)


class Singleton(type):

    _instances: dict[Any, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs)
        return cls._instances[cls]


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


def event_filter(filter_):
    def event_filter_decorator(func):
        @wraps(func)
        def func_wrapper(self, event, *args, **kwargs):
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


def parse_uri_actions(uri: str) -> tuple[str, dict[str, str]]:
    uri = uri[5:]
    if '?' not in uri:
        return 'message', {'jid': uri}

    jid, action = uri.split('?', 1)
    data = {'jid': jid}
    if ';' in action:
        action, keys = action.split(';', 1)
        action_keys = keys.split(';')
        for key in action_keys:
            if key.startswith('subject='):
                data['subject'] = unquote(key[8:])

            elif key.startswith('body='):
                data['body'] = unquote(key[5:])

            elif key.startswith('thread='):
                data['thread'] = key[7:]
    return action, data


def parse_uri(uri: str) -> URI:
    if uri.startswith('xmpp:'):
        action, data = parse_uri_actions(uri)
        try:
            validate_jid(data['jid'])
            return URI(type=URIType.XMPP,
                       action=URIAction(action),
                       data=data)
        except ValueError:
            # Unknown action
            return URI(type=URIType.UNKNOWN)

    if uri.startswith('mailto:'):
        uri = uri[7:]
        return URI(type=URIType.MAIL, data=uri)

    if uri.startswith('tel:'):
        uri = uri[4:]
        return URI(type=URIType.TEL, data=uri)

    if STH_AT_STH_DOT_STH_REGEX.match(uri):
        return URI(type=URIType.AT, data=uri)

    if uri.startswith('geo:'):
        location = uri[4:]
        lat, _, lon = location.partition(',')
        if not lon:
            return URI(type=URIType.UNKNOWN, data=uri)

        if Gio.AppInfo.get_default_for_uri_scheme('geo'):
            return URI(type=URIType.GEO, data=uri)

        uri = geo_provider_from_location(lat, lon)
        return URI(type=URIType.GEO, data=uri)

    if uri.startswith('file://'):
        return URI(type=URIType.FILE, data=uri)

    return URI(type=URIType.WEB, data=uri)


@catch_exceptions
def open_uri(uri: Union[URI, str], account: Optional[str] = None) -> None:
    if not isinstance(uri, URI):
        uri = parse_uri(uri)

    if uri.type == URIType.FILE:
        open_file(uri.data)

    elif uri.type == URIType.TEL:
        if sys.platform == 'win32':
            webbrowser.open(f'tel:{uri.data}')
        else:
            Gio.AppInfo.launch_default_for_uri(f'tel:{uri.data}')

    elif uri.type == URIType.MAIL:
        if sys.platform == 'win32':
            webbrowser.open(f'mailto:{uri.data}')
        else:
            Gio.AppInfo.launch_default_for_uri(f'mailto:{uri.data}')

    elif uri.type in (URIType.WEB, URIType.GEO):
        if sys.platform == 'win32':
            webbrowser.open(uri.data)
        else:
            Gio.AppInfo.launch_default_for_uri(uri.data)

    elif uri.type == URIType.AT:
        app.interface.start_chat_from_jid(account, uri.data)

    elif uri.type == URIType.XMPP:
        if account is None:
            log.warning('Account must be specified to open XMPP uri')
            return

        if isinstance(uri.data, dict):
            jid = uri.data['jid']
            message = uri.data.get('body')
        else:
            log.warning('Cant open URI: %s', uri)
        if uri.action == URIAction.JOIN:
            app.app.activate_action(
                'groupchat-join',
                GLib.Variant('as', [account, jid]))
        elif uri.action == URIAction.MESSAGE:
            app.interface.start_chat_from_jid(account, jid, message=message)
        else:
            log.warning('Cant open URI: %s', uri)

    else:
        log.warning('Cant open URI: %s', uri)


@catch_exceptions
def open_file(path: Union[str, Path]) -> None:
    if os.name == 'nt':
        os.startfile(path)
    else:
        # Call str() to make it work with pathlib.Path
        path = str(path)
        if not path.startswith('file://'):
            path = 'file://' + path
        Gio.AppInfo.launch_default_for_uri(path)


def file_is_locked(path_to_file: str) -> bool:
    """
    Return True if file is locked
    NOTE: Windows only.
    """
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


def get_resource(account: str) -> Optional[str]:
    resource = app.settings.get_account_setting(account, 'resource')
    if not resource:
        return None

    resource = Template(resource).safe_substitute(
        {'hostname': socket.gethostname(),
         'rand': get_random_string()})
    app.settings.set_account_setting(account, 'resource', resource)
    return resource


def get_default_muc_config() -> dict[str, Union[bool, str]]:
    return {
        # XEP-0045 options
        'muc#roomconfig_allowinvites': True,
        'muc#roomconfig_publicroom': False,
        'muc#roomconfig_membersonly': True,
        'muc#roomconfig_persistentroom': True,
        'muc#roomconfig_whois': 'anyone',
        'muc#roomconfig_moderatedroom': False,

        # Ejabberd options
        'allow_voice_requests': False,
        'public_list': False,

        # Prosody options
        '{http://prosody.im/protocol/muc}roomconfig_allowmemberinvites': True,
        'muc#roomconfig_enablearchiving': True,
    }


def validate_jid(jid: Union[str, JID], type_: Optional[str] = None) -> JID:
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


def to_user_string(error: StanzaError) -> str:
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
                                  target_aff: Union[str, Affiliation]) -> bool:
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


def is_retraction_allowed(self_contact: types.GroupchatParticipant,
                          contact: types.GroupchatParticipant) -> bool:

    if self_contact.role < Role.MODERATOR:
        return False
    return self_contact.affiliation >= contact.affiliation


def get_tls_error_phrase(tls_error: Gio.TlsCertificateFlags) -> str:
    phrase = GIO_TLS_ERRORS.get(tls_error)
    if phrase is None:
        return GIO_TLS_ERRORS[Gio.TlsCertificateFlags.GENERIC_ERROR]
    return phrase


class Observable:
    def __init__(self, log_: Optional[logging.Logger] = None):
        self._log = log_
        self._callbacks: types.ObservableCbDict = defaultdict(list)

    def disconnect_signals(self) -> None:
        self._callbacks = defaultdict(list)

    def disconnect_all_from_obj(self, obj: Any) -> None:
        for handlers in self._callbacks.values():
            for handler in list(handlers):
                func = handler()
                if func is None or func.__self__ is obj:
                    handlers.remove(handler)

    def disconnect(self, obj: Any) -> None:
        self.disconnect_all_from_obj(obj)

    def connect_signal(self,
                       signal_name: str,
                       func: types.AnyCallableT) -> None:
        if not inspect.ismethod(func):
            raise ValueError('Only bound methods allowed')

        weak_func = weakref.WeakMethod(func)

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
        callback: Callable[[bool, Optional[GLib.Error], Any], Any],
        user_data: Optional[Any] = None):

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
                    callback: Callable[[Optional[bytes],
                                        Optional[GLib.Error],
                                        Optional[Any]], Any],
                    user_data: Optional[Any] = None) -> None:

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


def convert_gio_to_openssl_cert(cert: Gio.TlsCertificate) -> X509:
    return load_certificate(FILETYPE_PEM, cert.props.certificate_pem.encode())


def get_custom_host(account: str) -> Optional[tuple[str,
                                                    ConnectionProtocol,
                                                    ConnectionType]]:
    if not app.settings.get_account_setting(account, 'use_custom_host'):
        return None
    host = app.settings.get_account_setting(account, 'custom_host')
    port = app.settings.get_account_setting(account, 'custom_port')
    type_ = app.settings.get_account_setting(account, 'custom_type')

    if host.startswith('ws://') or host.startswith('wss://'):
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
    for type_ in connection_types:
        if type_.is_plain and warn:
            return True
    return False


def get_idle_status_message(state: str, status_message: str) -> str:
    message = app.settings.get(f'auto{state}_message')
    if not message:
        message = status_message
    else:
        message = message.replace('$S', '%(status)s')
        message = message.replace('$T', '%(time)s')
        message = message % {
            'status': status_message,
            'time': app.settings.get(f'auto{state}time')
        }
    return message


def should_log(account: str, jid: str) -> bool:
    """
    Should conversations between a local account and a remote jid be logged?
    """
    no_log_for = app.settings.get_account_setting(account, 'no_log_for')

    if not no_log_for:
        no_log_for = ''

    no_log_for = no_log_for.split()

    return (account not in no_log_for) and (jid not in no_log_for)


def ask_for_status_message(status: str, signin: bool = False) -> bool:
    if status is None:
        # We try to change the message
        return True

    if signin:
        return app.settings.get('ask_online_status')

    if status == 'offline':
        return app.settings.get('ask_offline_status')

    return app.settings.get('always_ask_for_status_message')


def get_group_chat_nick(account: str, room_jid: Union[JID, str]) -> str:
    nick = app.nicks[account]

    client = app.get_client(account)

    bookmark = client.get_module('Bookmarks').get_bookmark(room_jid)
    if bookmark is not None:
        if bookmark.nick is not None:
            nick = bookmark.nick

    return nick


def get_muc_context(jid: JID) -> Optional[str]:
    disco_info = app.storage.cache.get_last_disco_info(jid)
    if disco_info is None:
        return None

    if (disco_info.muc_is_members_only and disco_info.muc_is_nonanonymous):
        return 'private'
    return 'public'


def get_start_of_day(date_time: datetime) -> datetime:
    return date_time.replace(hour=0,
                             minute=0,
                             second=0,
                             microsecond=0)
