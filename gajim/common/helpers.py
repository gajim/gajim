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

from typing import Any  # pylint: disable=unused-import
from typing import Dict  # pylint: disable=unused-import
from typing import Optional

import sys
import re
import os
import subprocess
import webbrowser
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
import string
from string import Template
import urllib
from urllib.parse import unquote
from encodings.punycode import punycode_encode
from functools import wraps
from packaging.version import Version as V

from nbxmpp.namespaces import Namespace
from nbxmpp.const import Role
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.structs import ProxyData
from nbxmpp.protocol import JID
from nbxmpp.protocol import InvalidJid
from OpenSSL.crypto import load_certificate
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
from gajim.common.const import Display
from gajim.common.const import URIType
from gajim.common.const import URIAction
from gajim.common.const import GIO_TLS_ERRORS
from gajim.common.const import SHOW_LIST
from gajim.common.structs import URI


log = logging.getLogger('gajim.c.helpers')

special_groups = (_('Transports'),
                  _('Not in contact list'),
                  _('Observers'),
                  _('Group chats'))

URL_REGEX = re.compile(
    r"(www\.(?!\.)|[a-z][a-z0-9+.-]*://)[^\s<>'\"]+[^!,\.\s<>\)'\"\]]")


class InvalidFormat(Exception):
    pass


def parse_jid(jidstring):
    try:
        return str(validate_jid(jidstring))
    except Exception as error:
        raise InvalidFormat(error)

def idn_to_ascii(host):
    """
    Convert IDN (Internationalized Domain Names) to ACE (ASCII-compatible
    encoding)
    """
    from encodings import idna
    labels = idna.dots.split(host)
    converted_labels = []
    for label in labels:
        if label:
            converted_labels.append(idna.ToASCII(label).decode('utf-8'))
        else:
            converted_labels.append('')
    return ".".join(converted_labels)

def ascii_to_idn(host):
    """
    Convert ACE (ASCII-compatible encoding) to IDN (Internationalized Domain
    Names)
    """
    from encodings import idna
    labels = idna.dots.split(host)
    converted_labels = []
    for label in labels:
        converted_labels.append(idna.ToUnicode(label))
    return ".".join(converted_labels)

def puny_encode_url(url):
    _url = url
    if '//' not in _url:
        _url = '//' + _url
    try:
        o = urllib.parse.urlparse(_url)
        p_loc = idn_to_ascii(o.netloc)
    except Exception:
        log.debug('urlparse failed: %s', url)
        return False
    return url.replace(o.netloc, p_loc)

def parse_resource(resource):
    """
    Perform stringprep on resource and return it
    """
    if not resource:
        return None

    try:
        return resource.encode('OpaqueString').decode('utf-8')
    except UnicodeError:
        raise InvalidFormat('Invalid character in resource.')

def windowsify(word):
    if os.name == 'nt':
        return word.capitalize()
    return word

def get_uf_show(show, use_mnemonic=False):
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

def get_uf_sub(sub):
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

def get_uf_ask(ask):
    if ask is None:
        uf_ask = Q_('?Ask (for Subscription):None')
    elif ask == 'subscribe':
        uf_ask = _('Subscribe')
    else:
        uf_ask = ask

    return uf_ask

def get_uf_role(role, plural=False):
    ''' plural determines if you get Moderators or Moderator'''
    if not isinstance(role, str):
        role = role.value

    if role == 'none':
        role_name = Q_('?Group Chat Contact Role:None')
    elif role == 'moderator':
        if plural:
            role_name = _('Moderators')
        else:
            role_name = _('Moderator')
    elif role == 'participant':
        if plural:
            role_name = _('Participants')
        else:
            role_name = _('Participant')
    elif role == 'visitor':
        if plural:
            role_name = _('Visitors')
        else:
            role_name = _('Visitor')
    return role_name

def get_uf_affiliation(affiliation, plural=False):
    '''Get a nice and translated affilition for muc'''
    if not isinstance(affiliation, str):
        affiliation = affiliation.value

    if affiliation == 'none':
        affiliation_name = Q_('?Group Chat Contact Affiliation:None')
    elif affiliation == 'owner':
        if plural:
            affiliation_name = _('Owners')
        else:
            affiliation_name = _('Owner')
    elif affiliation == 'admin':
        if plural:
            affiliation_name = _('Administrators')
        else:
            affiliation_name = _('Administrator')
    elif affiliation == 'member':
        if plural:
            affiliation_name = _('Members')
        else:
            affiliation_name = _('Member')
    return affiliation_name

def get_sorted_keys(adict):
    keys = sorted(adict.keys())
    return keys

def to_one_line(msg):
    msg = msg.replace('\\', '\\\\')
    msg = msg.replace('\n', '\\n')
    # s1 = 'test\ntest\\ntest'
    # s11 = s1.replace('\\', '\\\\')
    # s12 = s11.replace('\n', '\\n')
    # s12
    # 'test\\ntest\\\\ntest'
    return msg

def from_one_line(msg):
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

def get_uf_chatstate(chatstate):
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

def exec_command(command, use_shell=False, posix=True):
    """
    execute a command. if use_shell is True, we run the command as is it was
    typed in a console. So it may be dangerous if you are not sure about what
    is executed.
    """
    if use_shell:
        subprocess.Popen('%s &' % command, shell=True).wait()
    else:
        args = shlex.split(command, posix=posix)
        process = subprocess.Popen(args)
        app.thread_interface(process.wait)

def build_command(executable, parameter):
    # we add to the parameter (can hold path with spaces)
    # "" so we have good parsing from shell
    parameter = parameter.replace('"', '\\"') # but first escape "
    command = '%s "%s"' % (executable, parameter)
    return command

def get_file_path_from_dnd_dropped_uri(uri):
    path = urllib.parse.unquote(uri) # escape special chars
    path = path.strip('\r\n\x00') # remove \r\n and NULL
    # get the path to file
    if re.match('^file:///[a-zA-Z]:/', path): # windows
        path = path[8:] # 8 is len('file:///')
    elif path.startswith('file://'): # nautilus, rox
        path = path[7:] # 7 is len('file://')
    elif path.startswith('file:'): # xffm
        path = path[5:] # 5 is len('file:')
    return path

def sanitize_filename(filename):
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

def reduce_chars_newlines(text, max_chars=0, max_lines=0):
    """
    Cut the chars after 'max_chars' on each line and show only the first
    'max_lines'

    If any of the params is not present (None or 0) the action on it is not
    performed
    """
    def _cut_if_long(string_):
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

def get_account_status(account):
    status = reduce_chars_newlines(account['status_line'], 100, 1)
    return status

def get_contact_dict_for_account(account):
    """
    Create a dict of jid, nick -> contact with all contacts of account.

    Can be used for completion lists
    """
    contacts_dict = {}
    for jid in app.contacts.get_jid_list(account):
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        contacts_dict[jid] = contact
        name = contact.name
        if name in contacts_dict:
            contact1 = contacts_dict[name]
            del contacts_dict[name]
            contacts_dict['%s (%s)' % (name, contact1.jid)] = contact1
            contacts_dict['%s (%s)' % (name, jid)] = contact
        elif contact.name:
            if contact.name == app.get_nick_from_jid(jid):
                del contacts_dict[jid]
            contacts_dict[name] = contact
    return contacts_dict

def play_sound(event):
    if not app.config.get('sounds_on'):
        return
    path_to_soundfile = app.config.get_per('soundevents', event, 'path')
    play_sound_file(path_to_soundfile)

def check_soundfile_path(file_, dirs=None):
    """
    Check if the sound file exists

    :param file_: the file to check, absolute or relative to 'dirs' path
    :param dirs: list of knows paths to fallback if the file doesn't exists
                                     (eg: ~/.gajim/sounds/, DATADIR/sounds...).
    :return      the path to file or None if it doesn't exists.
    """
    if dirs is None:
        dirs = [configpaths.get('MY_DATA'),
                configpaths.get('DATA')]

    if not file_:
        return None
    if os.path.exists(file_):
        return file_

    for dir_ in dirs:
        dir_ = os.path.join(dir_, 'sounds', file_)
        if os.path.exists(dir_):
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

    name = os.path.basename(file_)
    for dir_ in dirs:
        dir_ = os.path.join(dir_, 'sounds', name)
        if abs_:
            dir_ = os.path.abspath(dir_)
        if file_ == dir_:
            return name
    return file_

def play_sound_file(path_to_soundfile):
    path_to_soundfile = check_soundfile_path(path_to_soundfile)
    if path_to_soundfile is None:
        return

    if sys.platform == 'win32':
        import winsound
        try:
            winsound.PlaySound(path_to_soundfile,
                               winsound.SND_FILENAME|winsound.SND_ASYNC)
        except Exception:
            log.exception('Sound Playback Error')

    elif sys.platform == 'darwin':
        try:
            from AppKit import NSSound
        except ImportError:
            log.exception('Sound Playback Error')
            return

        sound = NSSound.alloc()
        sound.initWithContentsOfFile_byReference_(path_to_soundfile, True)
        sound.play()

    elif app.is_installed('GSOUND'):
        try:
            app.gsound_ctx.play_simple({'media.filename' : path_to_soundfile})
        except GLib.Error as error:
            log.error('Could not play sound: %s', error.message)

def get_connection_status(account):
    con = app.connections[account]
    if con.state.is_reconnect_scheduled:
        return 'error'

    if con.state.is_connecting or con.state.is_connected:
        return 'connecting'

    if con.state.is_disconnected:
        return 'offline'
    return con.status

def get_global_show():
    maxi = 0
    for account in app.connections:
        if not app.config.get_per('accounts', account,
                                  'sync_with_global_status'):
            continue
        status = get_connection_status(account)
        index = SHOW_LIST.index(status)
        if index > maxi:
            maxi = index
    return SHOW_LIST[maxi]

def get_global_status_message():
    maxi = 0
    for account in app.connections:
        if not app.config.get_per('accounts', account,
                                  'sync_with_global_status'):
            continue
        status = app.connections[account].status
        index = SHOW_LIST.index(status)
        if index > maxi:
            maxi = index
            status_message = app.connections[account].status_message
    return status_message

def statuses_unified():
    """
    Test if all statuses are the same
    """
    reference = None
    for account in app.connections:
        if not app.config.get_per('accounts', account,
                                  'sync_with_global_status'):
            continue
        if reference is None:
            reference = app.connections[account].status
        elif reference != app.connections[account].status:
            return False
    return True

def get_icon_name_to_show(contact, account=None):
    """
    Get the icon name to show in online, away, requested, etc
    """
    if account and app.events.get_nb_roster_events(account, contact.jid):
        return 'event'
    if account and app.events.get_nb_roster_events(account,
                                                   contact.get_full_jid()):
        return 'event'
    if account and account in app.interface.minimized_controls and \
    contact.jid in app.interface.minimized_controls[account] and app.interface.\
            minimized_controls[account][contact.jid].get_nb_unread_pm() > 0:
        return 'event'
    if account and contact.jid in app.gc_connected[account]:
        if app.gc_connected[account][contact.jid]:
            return 'muc-active'
        return 'muc-inactive'
    if contact.jid.find('@') <= 0: # if not '@' or '@' starts the jid ==> agent
        return contact.show
    if contact.sub in ('both', 'to'):
        return contact.show
    if contact.ask == 'subscribe':
        return 'requested'
    transport = app.get_transport_name_from_jid(contact.jid)
    if transport:
        return contact.show
    if contact.show in SHOW_LIST:
        return contact.show
    return 'notinroster'

def get_full_jid_from_iq(iq_obj):
    """
    Return the full jid (with resource) from an iq
    """
    jid = iq_obj.getFrom()
    if jid is None:
        return None
    return parse_jid(str(iq_obj.getFrom()))

def get_jid_from_iq(iq_obj):
    """
    Return the jid (without resource) from an iq
    """
    jid = get_full_jid_from_iq(iq_obj)
    return app.get_jid_without_resource(jid)

def get_auth_sha(sid, initiator, target):
    """
    Return sha of sid + initiator + target used for proxy auth
    """
    return hashlib.sha1(("%s%s%s" % (sid, initiator, target)).encode('utf-8')).\
        hexdigest()

def remove_invalid_xml_chars(string_):
    if string_:
        string_ = re.sub(app.interface.invalid_XML_chars_re, '', string_)
    return string_

def get_random_string(count=16):
    """
    Create random string of count length

    WARNING: Don't use this for security purposes
    """
    allowed = string.ascii_uppercase + string.digits
    return ''.join(random.choice(allowed) for char in range(count))

@functools.lru_cache(maxsize=1)
def get_os_info():
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

def allow_showing_notification(account,
                               type_='notify_on_new_message',
                               is_first_message=True):
    """
    Is it allowed to show nofication?

    Check OUR status and if we allow notifications for that status type is the
    option that need to be True e.g.: notify_on_signing is_first_message: set it
    to false when it's not the first message
    """
    if type_ and (not app.config.get(type_) or not is_first_message):
        return False
    if app.config.get('autopopupaway'):
        return True
    if app.connections[account].status in ('online', 'chat'):
        return True
    return False

def allow_popup_window(account):
    """
    Is it allowed to popup windows?
    """
    autopopup = app.config.get('autopopup')
    autopopupaway = app.config.get('autopopupaway')
    if autopopup and (autopopupaway or \
    app.connections[account].status in ('online', 'chat')):
        return True
    return False

def allow_sound_notification(account, sound_event):
    if (app.config.get('sounddnd') or
            app.connections[account].status != 'dnd' and
            app.config.get_per('soundevents', sound_event, 'enabled')):
        return True
    return False

def get_notification_icon_tooltip_dict():
    """
    Return a dict of the form {acct: {'show': show, 'message': message,
    'event_lines': [list of text lines to show in tooltip]}
    """
    # How many events before we show summarized, not per-user
    max_ungrouped_events = 10

    accounts = get_accounts_info()

    # Gather events. (With accounts, when there are more.)
    for account in accounts:
        account_name = account['name']
        account['event_lines'] = []
        # Gather events per-account
        pending_events = app.events.get_events(account=account_name)
        messages, non_messages = {}, {}
        total_messages, total_non_messages = 0, 0
        for jid in pending_events:
            for event in pending_events[jid]:
                if event.type_.count('file') > 0:
                    # This is a non-messagee event.
                    messages[jid] = non_messages.get(jid, 0) + 1
                    total_non_messages = total_non_messages + 1
                else:
                    # This is a message.
                    messages[jid] = messages.get(jid, 0) + 1
                    total_messages = total_messages + 1
        # Display unread messages numbers, if any
        if total_messages > 0:
            if total_messages > max_ungrouped_events:
                text = ngettext('%d message pending',
                                '%d messages pending',
                                total_messages,
                                total_messages,
                                total_messages)
                account['event_lines'].append(text)
            else:
                for jid in messages:
                    text = ngettext('%d message pending',
                                    '%d messages pending',
                                    messages[jid],
                                    messages[jid],
                                    messages[jid])
                    contact = app.contacts.get_first_contact_from_jid(
                        account['name'], jid)
                    text += ' '
                    if jid in app.gc_connected[account['name']]:
                        text += _('from group chat %s') % (jid)
                    elif contact:
                        name = contact.get_shown_name()
                        text += _('from user %s') % (name)
                    else:
                        text += _('from %s') % (jid)
                    account['event_lines'].append(text)

        # Display unseen events numbers, if any
        if total_non_messages > 0:
            if total_non_messages > max_ungrouped_events:
                text = ngettext('%d event pending',
                                '%d events pending',
                                total_non_messages,
                                total_non_messages,
                                total_non_messages)
                account['event_lines'].append(text)
            else:
                for jid in non_messages:
                    text = ngettext('%d event pending',
                                    '%d events pending',
                                    non_messages[jid],
                                    non_messages[jid],
                                    non_messages[jid])
                    text += ' ' + _('from user %s') % (jid)
                    account[account]['event_lines'].append(text)

    return accounts

def get_accounts_info():
    """
    Helper for notification icon tooltip
    """
    accounts = []
    accounts_list = sorted(app.contacts.get_accounts())
    for account in accounts_list:

        status = get_connection_status(account)
        message = app.connections[account].status_message
        single_line = get_uf_show(status)
        if message is None:
            message = ''
        else:
            message = message.strip()
        if message != '':
            single_line += ': ' + message
        account_label = app.get_account_label(account)
        accounts.append({'name': account,
                         'account_label': account_label,
                         'status_line': single_line,
                         'show': status,
                         'message': message})
    return accounts

def get_current_show(account):
    if account not in app.connections:
        return 'offline'
    return app.connections[account].status

def get_optional_features(account):
    features = []
    if app.config.get_per('accounts', account, 'subscribe_mood'):
        features.append(Namespace.MOOD + '+notify')
    if app.config.get_per('accounts', account, 'subscribe_activity'):
        features.append(Namespace.ACTIVITY + '+notify')
    if app.config.get_per('accounts', account, 'subscribe_tune'):
        features.append(Namespace.TUNE + '+notify')

    features.append(Namespace.NICK + '+notify')

    if app.config.get_per('accounts', account, 'subscribe_location'):
        features.append(Namespace.LOCATION + '+notify')
    if app.connections[account].get_module('Bookmarks').using_bookmark_2:
        features.append(Namespace.BOOKMARKS_2 + '+notify')
    elif app.connections[account].get_module('Bookmarks').using_bookmark_1:
        features.append(Namespace.BOOKMARKS + '+notify')
    if app.is_installed('AV'):
        features.append(Namespace.JINGLE_RTP)
        features.append(Namespace.JINGLE_RTP_AUDIO)
        features.append(Namespace.JINGLE_RTP_VIDEO)
        features.append(Namespace.JINGLE_ICE_UDP)

    # Give plugins the possibility to add their features
    app.plugin_manager.extension_point('update_caps', account, features)
    return features

def jid_is_blocked(account, jid):
    con = app.connections[account]
    return jid in con.get_module('Blocking').blocked

def get_subscription_request_msg(account=None):
    s = app.config.get_per('accounts', account, 'subscription_request_msg')
    if s:
        return s
    s = _('I would like to add you to my contact list.')
    if account:
        s = _('Hello, I am $name.') + ' ' + s
        name = app.connections[account].get_module('VCardTemp').get_vard_name()
        nick = app.nicks[account]
        if name and nick:
            name += ' (%s)' % nick
        elif nick:
            name = nick
        s = Template(s).safe_substitute({'name': name})
        return s

def get_user_proxy(account):
    proxy_name = app.config.get_per('accounts', account, 'proxy')
    if not proxy_name:
        return None
    return get_proxy(proxy_name)

def get_proxy(proxy_name):
    proxy = app.config.get_per('proxies', proxy_name)
    if proxy is None:
        return None

    username, password = None, None
    if proxy['useauth']:
        username, password = proxy['user'], proxy['pass']

    return ProxyData(type=proxy['type'],
                     host='%s:%s' % (proxy['host'], proxy['port']),
                     username=username,
                     password=password)

def version_condition(current_version, required_version):
    if V(current_version) < V(required_version):
        return False
    return True

def get_available_emoticon_themes():
    emoticons_themes = ['font']
    files = []
    dir_iterator = os.scandir(configpaths.get('EMOTICONS'))
    for folder in dir_iterator:
        if not folder.is_dir():
            continue
        file_iterator = os.scandir(folder.path)
        for theme in file_iterator:
            if theme.is_file():
                files.append(theme.name)

    if os.path.isdir(configpaths.get('MY_EMOTS')):
        files += os.listdir(configpaths.get('MY_EMOTS'))

    for file in files:
        if file.endswith('.png'):
            emoticons_themes.append(file[:-4])
    emoticons_themes.sort()
    return emoticons_themes

def call_counter(func):
    def helper(self, restart=False):
        if restart:
            self._connect_machine_calls = 0
        self._connect_machine_calls += 1
        return func(self)
    return helper

def get_sync_threshold(jid, archive_info):
    disco_info = app.logger.get_last_disco_info(jid)
    if archive_info is None or archive_info.sync_threshold is None:
        if disco_info is not None and disco_info.muc_is_members_only:
            threshold = app.config.get('private_room_sync_threshold')
        else:
            threshold = app.config.get('public_room_sync_threshold')
        app.logger.set_archive_infos(jid, sync_threshold=threshold)
        return threshold
    return archive_info.sync_threshold

def load_json(path, key=None, default=None):
    try:
        with path.open('r') as file:
            json_dict = json.loads(file.read())
    except Exception:
        log.exception('Parsing error')
        return default

    if key is None:
        return json_dict
    return json_dict.get(key, default)

def ignore_contact(account, jid):
    jid = str(jid)
    known_contact = app.contacts.get_contacts(account, jid)
    ignore = app.config.get_per('accounts', account, 'ignore_unknown_contacts')
    if ignore and not known_contact:
        log.info('Ignore unknown contact %s', jid)
        return True
    return False

class AdditionalDataDict(collections.UserDict):
    def __init__(self, initialdata=None):
        collections.UserDict.__init__(self, initialdata)

    @staticmethod
    def _get_path_childs(full_path):
        path_childs = [full_path]
        if ':' in full_path:
            path_childs = full_path.split(':')
        return path_childs

    def set_value(self, full_path, key, value):
        path_childs = self._get_path_childs(full_path)
        _dict = self.data
        for path in path_childs:
            try:
                _dict = _dict[path]
            except KeyError:
                _dict[path] = {}
                _dict = _dict[path]
        _dict[key] = value

    def get_value(self, full_path, key, default=None):
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

    def remove_value(self, full_path, key):
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

    def copy(self):
        return copy.deepcopy(self)


def save_roster_position(window):
    if not app.config.get('save-roster-position'):
        return
    if app.is_display(Display.WAYLAND):
        return
    x_pos, y_pos = window.get_position()
    log.debug('Save roster position: %s %s', x_pos, y_pos)
    app.config.set('roster_x-position', x_pos)
    app.config.set('roster_y-position', y_pos)


class Singleton(type):
    _instances = {}  # type: Dict[Any, Any]
    def __call__(cls, *args, **kwargs):
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
                    if getattr(event, attr1) != getattr(self, '_%s' % attr2):
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


def parse_uri_actions(uri):
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


def parse_uri(uri):
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

    if app.interface.sth_at_sth_dot_sth_re.match(uri):
        return URI(type=URIType.AT, data=uri)

    if uri.startswith('geo:'):
        location = uri[4:]
        lat, _, lon = location.partition(',')
        if not lon:
            return URI(type=URIType.UNKNOWN, data=uri)

        uri = geo_provider_from_location(lat, lon)
        return URI(type=URIType.GEO, data=uri)

    if uri.startswith('file://'):
        return URI(type=URIType.FILE, data=uri)

    return URI(type=URIType.WEB, data=uri)


@catch_exceptions
def open_uri(uri, account=None):
    if not isinstance(uri, URI):
        uri = parse_uri(uri)

    if uri.type == URIType.FILE:
        open_file(uri.data)

    elif uri.type == URIType.MAIL:
        uri = 'mailto:%s' % uri.data
        if os.name == 'nt':
            webbrowser.open(uri)
        else:
            Gio.AppInfo.launch_default_for_uri(uri)

    elif uri.type in (URIType.WEB, URIType.GEO):
        if os.name == 'nt':
            webbrowser.open(uri.data)
        else:
            Gio.AppInfo.launch_default_for_uri(uri.data)

    elif uri.type == URIType.AT:
        app.interface.new_chat_from_jid(account, uri.data)

    elif uri.type == URIType.XMPP:
        if account is None:
            log.warning('Account must be specified to open XMPP uri')
            return

        if uri.action == URIAction.JOIN:
            app.app.activate_action(
                'groupchat-join',
                GLib.Variant('as', [account, uri.data['jid']]))
        elif uri.action == URIAction.MESSAGE:
            app.interface.new_chat_from_jid(account, uri.data['jid'],
                                            message=uri.data.get('body'))
        else:
            log.warning('Cant open URI: %s', uri)

    else:
        log.warning('Cant open URI: %s', uri)


@catch_exceptions
def open_file(path):
    if os.name == 'nt':
        os.startfile(path)
    else:
        # Call str() to make it work with pathlib.Path
        path = str(path)
        if not path.startswith('file://'):
            path = 'file://' + path
        Gio.AppInfo.launch_default_for_uri(path)


def geo_provider_from_location(lat, lon):
    return ('https://www.openstreetmap.org/?'
            'mlat=%s&mlon=%s&zoom=16') % (lat, lon)


def get_resource(account):
    resource = app.config.get_per('accounts', account, 'resource')
    if not resource:
        return None

    resource = Template(resource).safe_substitute(
        {'hostname': socket.gethostname(),
         'rand': get_random_string()})
    app.config.set_per('accounts', account, 'resource', resource)
    return resource


def get_default_muc_config():
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


def validate_jid(jid, type_=None):
    try:
        jid = JID(str(jid))
    except InvalidJid as error:
        raise ValueError(error)

    if type_ is None:
        return jid
    if type_ == 'bare' and jid.isBare:
        return jid
    if type_ == 'full' and jid.isFull:
        return jid
    if type_ == 'domain' and jid.isDomain:
        return jid

    raise ValueError('Not a %s JID' % type_)


def to_user_string(error):
    text = error.get_text(get_rfc5646_lang())
    if text:
        return text

    condition = error.condition
    if error.app_condition is not None:
        return '%s (%s)' % (condition, error.app_condition)
    return condition


def get_groupchat_name(con, jid):
    name = con.get_module('Bookmarks').get_name_from_bookmark(jid)
    if name:
        return name

    disco_info = app.logger.get_last_disco_info(jid)
    if disco_info is not None:
        if disco_info.muc_name:
            return disco_info.muc_name

    return jid.split('@')[0]


def get_alternative_venue(error):
    if error.condition == 'gone' and error.condition_data is not None:
        uri = parse_uri(error.condition_data)
        if uri.type == URIType.XMPP and uri.action == URIAction.JOIN:
            return uri.data['jid']
    return None


def is_affiliation_change_allowed(self_contact, contact, target_aff):
    if contact.affiliation.value == target_aff:
        # Contact has already the target affiliation
        return False

    if self_contact.affiliation.is_owner:
        return True

    if not self_contact.affiliation.is_admin:
        return False

    if target_aff in ('admin', 'owner'):
        # Admin can’t edit admin/owner list
        return False
    return self_contact.affiliation > contact.affiliation


def is_role_change_allowed(self_contact, contact):
    if self_contact.role < Role.MODERATOR:
        return False
    return self_contact.affiliation >= contact.affiliation


def get_tls_error_phrase(tls_error):
    phrase = GIO_TLS_ERRORS.get(tls_error)
    if phrase is None:
        return GIO_TLS_ERRORS.get(Gio.TlsCertificateFlags.GENERIC_ERROR)
    return phrase


class Observable:
    def __init__(self, log_=None):
        self._log = log_
        self._callbacks = defaultdict(list)

    def disconnect_signals(self):
        self._callbacks = defaultdict(list)

    def disconnect(self, object_):
        for signal_name, handlers in self._callbacks.items():
            for handler in list(handlers):
                func = handler()
                if func is None or func.__self__ == object_:
                    self._callbacks[signal_name].remove(handler)

    def connect(self, signal_name, func):
        weak_func = weakref.WeakMethod(func)
        self._callbacks[signal_name].append(weak_func)

    def notify(self, signal_name, *args, **kwargs):
        if self._log is not None:
            self._log.info('Signal: %s', signal_name)

        callbacks = self._callbacks.get(signal_name, [])
        for func in list(callbacks):
            if func() is None:
                self._callbacks[signal_name].remove(func)
                continue
            func()(self, signal_name, *args, **kwargs)


def write_file_async(path, data, callback, user_data=None):
    file = Gio.File.new_for_path(str(path))
    file.create_async(Gio.FileCreateFlags.PRIVATE,
                      GLib.PRIORITY_DEFAULT,
                      None,
                      _on_file_created,
                      (callback, data, user_data))

def _on_file_created(file, result, user_data):
    callback, data, user_data = user_data
    try:
        outputstream = file.create_finish(result)
    except GLib.Error as error:
        callback(False, error, user_data)
        return

    # Pass data as user_data to the callback, because
    # write_all_async() takes not reference to the data
    # and python gc collects it before the data are written
    outputstream.write_all_async(data,
                                 GLib.PRIORITY_DEFAULT,
                                 None,
                                 _on_write_finished,
                                 (callback, data, user_data))

def _on_write_finished(outputstream, result, user_data):
    callback, _data, user_data = user_data
    try:
        successful, _bytes_written = outputstream.write_all_finish(result)
    except GLib.Error as error:
        callback(False, error, user_data)
    else:
        callback(successful, None, user_data)


def load_file_async(path, callback, user_data=None):
    file = Gio.File.new_for_path(str(path))
    file.load_contents_async(None,
                             _on_load_finished,
                             (callback, user_data))


def _on_load_finished(file, result, user_data):
    callback, user_data = user_data
    try:
        _successful, contents, _etag = file.load_contents_finish(result)
    except GLib.Error as error:
        callback(None, error, user_data)
    else:
        callback(contents, None, user_data)


def get_encryption_method(account: str, jid: str) -> Optional[str]:
    config_key = '%s-%s' % (account, jid)
    state = app.config.get_per('encryption', config_key, 'encryption')
    return state or None


def convert_gio_to_openssl_cert(cert):
    cert = load_certificate(FILETYPE_PEM, cert.props.certificate_pem.encode())
    return cert


def get_custom_host(account):
    if not app.config.get_per('accounts', account, 'use_custom_host'):
        return None
    host = app.config.get_per('accounts', account, 'custom_host')
    port = app.config.get_per('accounts', account, 'custom_port')
    type_ = app.config.get_per('accounts', account, 'custom_type')

    protocol = ConnectionProtocol.TCP
    if host.startswith('ws://') or host.startswith('wss://'):
        protocol = ConnectionProtocol.WEBSOCKET

    return ('%s:%s' % (host, port),
            protocol,
            ConnectionType(type_))


def warn_about_plain_connection(account, connection_types):
    warn = app.config.get_per(
        'accounts', account, 'action_when_plain_connection') == 'warn'
    for type_ in connection_types:
        if type_.is_plain and warn:
            return True
    return False


def get_idle_status_message(state, status_message):
    message = app.config.get(f'auto{state}_message')
    if not message:
        message = status_message
    else:
        message = message.replace('$S', '%(status)s')
        message = message.replace('$T', '%(time)s')
        message = message % {
            'status': status_message,
            'time': app.config.get(f'auto{state}time')
        }
    return message


def should_log(account, jid):
    """
    Should conversations between a local account and a remote jid be logged?
    """
    no_log_for = app.config.get_per('accounts', account, 'no_log_for')

    if not no_log_for:
        no_log_for = ''

    no_log_for = no_log_for.split()

    return (account not in no_log_for) and (jid not in no_log_for)


def ask_for_status_message(status, signin=False):
    if status is None:
        # We try to change the message
        return True

    if signin:
        return app.config.get('ask_online_status')

    if status == 'offline':
        return app.config.get('ask_offline_status')

    return app.config.get('always_ask_for_status_message')
