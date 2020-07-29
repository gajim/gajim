# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Philipp Hörist <philipp @ hoerist.com>
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
from typing import List  # pylint: disable=unused-import
from typing import Optional  # pylint: disable=unused-import
from typing import cast

import os
import sys
import logging
import uuid
from pathlib import Path
from collections import namedtuple

import nbxmpp
from gi.repository import Gdk

import gajim
from gajim.common import config as c_config
from gajim.common import configpaths
from gajim.common import ged as ged_module
from gajim.common.i18n import LANG
from gajim.common.const import Display
from gajim.common.events import Events
from gajim.common.types import NetworkEventsControllerT  # pylint: disable=unused-import
from gajim.common.types import InterfaceT  # pylint: disable=unused-import
from gajim.common.types import LoggerT  # pylint: disable=unused-import
from gajim.common.types import ConnectionT  # pylint: disable=unused-import
from gajim.common.types import LegacyContactsAPIT  # pylint: disable=unused-import
from gajim.common.types import SettingsT  # pylint: disable=unused-import

interface = cast(InterfaceT, None)
thread_interface = lambda *args: None # Interface to run a thread and then a callback
config = c_config.Config()
settings = cast(SettingsT, None)
version = gajim.__version__
connections = {}  # type: Dict[str, ConnectionT]
avatar_cache = {}  # type: Dict[str, Dict[str, Any]]
bob_cache = {} # type: Dict[str, bytes]
ipython_window = None
app = None  # Gtk.Application

ged = ged_module.GlobalEventsDispatcher() # Global Events Dispatcher
nec = cast(NetworkEventsControllerT, None)
plugin_manager = None # Plugins Manager

logger = cast(LoggerT, None)

css_config = None

transport_type = {}  # type: Dict[str, str]

# dict of time of the latest incoming message per jid
# {acct1: {jid1: time1, jid2: time2}, }
last_message_time = {}  # type: Dict[str, Dict[str, float]]

contacts = cast(LegacyContactsAPIT, None)

# tell if we are connected to the room or not
# {acct: {room_jid: True}}
gc_connected = {}  # type: Dict[str, Dict[str, bool]]

# dict of the pass required to enter a room
# {room_jid: password}
gc_passwords = {}  # type: Dict[str, str]

# dict of rooms that must be automatically configured
# and for which we have a list of invities
# {account: {room_jid: {'invities': []}}}
automatic_rooms = {}  # type: Dict[str, Dict[str, Dict[str, List[str]]]]

 # dict of groups, holds if they are expanded or not
groups = {}  # type: Dict[str, Dict[str, Dict[str, bool]]]

# list of contacts that has just signed in
newly_added = {}  # type: Dict[str, List[str]]

# list of contacts that has just signed out
to_be_removed = {}  # type: Dict[str, List[str]]

events = Events()

notification = None

# list of our nick names in each account
nicks = {}  # type: Dict[str, str]

# should we block 'contact signed in' notifications for this account?
# this is only for the first 30 seconds after we change our show
# to something else than offline
# can also contain account/transport_jid to block notifications for contacts
# from this transport
block_signed_in_notifications = {}  # type: Dict[str, bool]

proxy65_manager = None

cert_store = None

task_manager = None

# zeroconf account name
ZEROCONF_ACC_NAME = 'Local'

# These will be set in app.gui_interface.
idlequeue = None  # type: nbxmpp.idlequeue.IdleQueue
socks5queue = None

gupnp_igd = None

gsound_ctx = None

_dependencies = {
    'AVAHI': False,
    'PYBONJOUR': False,
    'FARSTREAM': False,
    'GST': False,
    'AV': False,
    'GEOCLUE': False,
    'UPNP': False,
    'GSOUND': False,
    'GSPELL': False,
    'IDLE': False,
}


def print_version():
    log('gajim').info('Gajim Version: %s', gajim.__version__)


def get_client(account):
    return connections[account]


def is_installed(dependency):
    if dependency == 'ZEROCONF':
        # Alias for checking zeroconf libs
        return _dependencies['AVAHI'] or _dependencies['PYBONJOUR']
    return _dependencies[dependency]


def is_flatpak():
    return gajim.IS_FLATPAK


def is_portable():
    return gajim.IS_PORTABLE


def is_display(display):
    # XWayland reports as Display X11, so try with env var
    is_wayland = os.environ.get('XDG_SESSION_TYPE') == 'wayland'
    if is_wayland and display == Display.WAYLAND:
        return True

    default = Gdk.Display.get_default()
    if default is None:
        log('gajim').warning('Could not determine window manager')
        return False
    return default.__class__.__name__ == display.value

def disable_dependency(dependency):
    _dependencies[dependency] = False

def detect_dependencies():
    import gi

    # ZEROCONF
    try:
        import pybonjour  # pylint: disable=unused-import
        _dependencies['PYBONJOUR'] = True
    except Exception:
        pass

    try:
        gi.require_version('Avahi', '0.6')
        from gi.repository import Avahi  # pylint: disable=unused-import
        _dependencies['AVAHI'] = True
    except Exception:
        pass

    try:
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        _dependencies['GST'] = True
    except Exception:
        pass

    try:
        gi.require_version('Farstream', '0.2')
        from gi.repository import Farstream
        _dependencies['FARSTREAM'] = True
    except Exception:
        pass

    try:
        if _dependencies['GST'] and _dependencies['FARSTREAM']:
            Gst.init(None)
            conference = Gst.ElementFactory.make('fsrtpconference', None)
            conference.new_session(Farstream.MediaType.AUDIO)
            _dependencies['AV'] = True
    except Exception as error:
        log('gajim').warning('AV dependency test failed: %s', error)

    # GEOCLUE
    try:
        gi.require_version('Geoclue', '2.0')
        from gi.repository import Geoclue  # pylint: disable=unused-import
        _dependencies['GEOCLUE'] = True
    except (ImportError, ValueError):
        pass

    # UPNP
    try:
        gi.require_version('GUPnPIgd', '1.0')
        from gi.repository import GUPnPIgd
        global gupnp_igd
        gupnp_igd = GUPnPIgd.SimpleIgd()
        _dependencies['UPNP'] = True
    except ValueError:
        pass

    # IDLE
    try:
        from gajim.common import idle
        if idle.Monitor.is_available():
            _dependencies['IDLE'] = True
    except Exception:
        pass

    # GSOUND
    try:
        gi.require_version('GSound', '1.0')
        from gi.repository import GLib
        from gi.repository import GSound
        global gsound_ctx
        gsound_ctx = GSound.Context()
        try:
            gsound_ctx.init()
            _dependencies['GSOUND'] = True
        except GLib.Error as error:
            log('gajim').warning('GSound init failed: %s', error)
    except (ImportError, ValueError):
        pass

    # GSPELL
    try:
        gi.require_version('Gspell', '1')
        from gi.repository import Gspell
        langs = Gspell.language_get_available()
        for lang in langs:
            log('gajim').info('%s (%s) dict available',
                              lang.get_name(), lang.get_code())
        if langs:
            _dependencies['GSPELL'] = True
    except (ImportError, ValueError):
        pass

    # Print results
    for dep, val in _dependencies.items():
        log('gajim').info('%-13s %s', dep, val)

    log('gajim').info('Used language: %s', LANG)

def detect_desktop_env():
    if sys.platform in ('win32', 'darwin'):
        return sys.platform

    desktop = os.environ.get('XDG_CURRENT_DESKTOP')
    if desktop is None:
        return None

    if 'gnome' in desktop.lower():
        return 'gnome'
    return desktop

desktop_env = detect_desktop_env()

def get_an_id():
    return str(uuid.uuid4())

def get_nick_from_jid(jid):
    pos = jid.find('@')
    return jid[:pos]

def get_server_from_jid(jid):
    pos = jid.find('@') + 1 # after @
    return jid[pos:]

def get_name_and_server_from_jid(jid):
    name = get_nick_from_jid(jid)
    server = get_server_from_jid(jid)
    return name, server

def get_room_and_nick_from_fjid(jid):
    # fake jid is the jid for a contact in a room
    # gaim@conference.jabber.no/nick/nick-continued
    # return ('gaim@conference.jabber.no', 'nick/nick-continued')
    l = jid.split('/', 1)
    if len(l) == 1: # No nick
        l.append('')
    return l

def get_real_jid_from_fjid(account, fjid):
    """
    Return real jid or returns None, if we don't know the real jid
    """
    room_jid, nick = get_room_and_nick_from_fjid(fjid)
    if not nick: # It's not a fake_jid, it is a real jid
        return fjid # we return the real jid
    real_jid = fjid
    if interface.msg_win_mgr.get_gc_control(room_jid, account):
        # It's a pm, so if we have real jid it's in contact.jid
        gc_contact = contacts.get_gc_contact(account, room_jid, nick)
        if not gc_contact:
            return
        # gc_contact.jid is None when it's not a real jid (we don't know real jid)
        real_jid = gc_contact.jid
    return real_jid

def get_room_from_fjid(jid):
    return get_room_and_nick_from_fjid(jid)[0]

def get_contact_name_from_jid(account, jid):
    c = contacts.get_first_contact_from_jid(account, jid)
    return c.name

def get_jid_without_resource(jid):
    return jid.split('/')[0]

def construct_fjid(room_jid, nick):
    # fake jid is the jid for a contact in a room
    # gaim@conference.jabber.org/nick
    return room_jid + '/' + nick

def get_resource_from_jid(jid):
    jids = jid.split('/', 1)
    if len(jids) > 1:
        return jids[1] # abc@doremi.org/res/res-continued
    return ''

def get_number_of_accounts():
    """
    Return the number of ALL accounts
    """
    return len(connections.keys())

def get_number_of_connected_accounts(accounts_list=None):
    """
    Returns the number of CONNECTED accounts. Uou can optionally pass an
    accounts_list and if you do those will be checked, else all will be checked
    """
    connected_accounts = 0
    if accounts_list is None:
        accounts = connections.keys()
    else:
        accounts = accounts_list
    for account in accounts:
        if account_is_connected(account):
            connected_accounts = connected_accounts + 1
    return connected_accounts

def get_available_clients():
    clients = []
    for client in connections.values():
        if client.state.is_available:
            clients.append(client)
    return clients

def get_connected_accounts(exclude_local=False):
    """
    Returns a list of CONNECTED accounts
    """
    account_list = []
    for account in connections:
        if account == 'Local' and exclude_local:
            continue
        if account_is_connected(account):
            account_list.append(account)
    return account_list

def get_accounts_sorted():
    '''
    Get all accounts alphabetically sorted with Local first
    '''
    account_list = config.get_per('accounts')
    account_list.sort(key=str.lower)
    if 'Local' in account_list:
        account_list.remove('Local')
        account_list.insert(0, 'Local')
    return account_list

def get_enabled_accounts_with_labels(exclude_local=True, connected_only=False,
                                     private_storage_only=False):
    """
    Returns a list with [account, account_label] entries.
    Order by account_label
    """
    accounts = []
    for acc in connections:
        if exclude_local and account_is_zeroconf(acc):
            continue
        if connected_only and not account_is_connected(acc):
            continue
        if private_storage_only and not account_supports_private_storage(acc):
            continue

        accounts.append([acc, get_account_label(acc)])

    accounts.sort(key=lambda xs: str.lower(xs[1]))
    return accounts

def get_account_label(account):
    return config.get_per('accounts', account, 'account_label') or account

def account_is_zeroconf(account):
    return connections[account].is_zeroconf

def account_supports_private_storage(account):
    # If Delimiter module is not available we can assume
    # Private Storage is not available
    return connections[account].get_module('Delimiter').available

def account_is_connected(account):
    if account not in connections:
        return False
    return (connections[account].state.is_connected or
            connections[account].state.is_available)

def account_is_available(account):
    if account not in connections:
        return False
    return connections[account].state.is_available

def account_is_disconnected(account):
    return not account_is_connected(account)

def zeroconf_is_connected():
    return account_is_connected(ZEROCONF_ACC_NAME) and \
            config.get_per('accounts', ZEROCONF_ACC_NAME, 'is_zeroconf')

def in_groupchat(account, room_jid):
    room_jid = str(room_jid)
    if room_jid not in gc_connected[account]:
        return False
    return gc_connected[account][room_jid]

def get_transport_name_from_jid(jid, use_config_setting=True):
    """
    Returns 'gg', 'irc' etc

    If JID is not from transport returns None.
    """
    #FIXME: jid can be None! one TB I saw had this problem:
    # in the code block # it is a groupchat presence in handle_event_notify
    # jid was None. Yann why?
    if not jid or (use_config_setting and not config.get('use_transports_iconsets')):
        return

    host = get_server_from_jid(jid)
    if host in transport_type:
        return transport_type[host]

    # host is now f.e. icq.foo.org or just icq (sometimes on hacky transports)
    host_splitted = host.split('.')
    if host_splitted:
        # now we support both 'icq.' and 'icq' but not icqsucks.org
        host = host_splitted[0]

    if host in ('irc', 'icq', 'sms', 'weather', 'mrim', 'facebook'):
        return host
    if host == 'gg':
        return 'gadu-gadu'
    if host == 'jit':
        return 'icq'
    if host == 'facebook':
        return 'facebook'
    return None

def jid_is_transport(jid):
    # if not '@' or '@' starts the jid then it is transport
    if jid.find('@') <= 0:
        return True
    return False

def get_jid_from_account(account_name):
    """
    Return the jid we use in the given account
    """
    name = config.get_per('accounts', account_name, 'name')
    hostname = config.get_per('accounts', account_name, 'hostname')
    jid = name + '@' + hostname
    return jid

def get_account_from_jid(jid):
    for account in config.get_per('accounts'):
        if jid == get_jid_from_account(account):
            return account

def get_our_jids():
    """
    Returns a list of the jids we use in our accounts
    """
    our_jids = list()
    for account in contacts.get_accounts():
        our_jids.append(get_jid_from_account(account))
    return our_jids

def get_hostname_from_account(account_name, use_srv=False):
    """
    Returns hostname (if custom hostname is used, that is returned)
    """
    if use_srv and connections[account_name].connected_hostname:
        return connections[account_name].connected_hostname
    if config.get_per('accounts', account_name, 'use_custom_host'):
        return config.get_per('accounts', account_name, 'custom_host')
    return config.get_per('accounts', account_name, 'hostname')

def get_notification_image_prefix(jid):
    """
    Returns the prefix for the notification images
    """
    transport_name = get_transport_name_from_jid(jid)
    if transport_name in ('icq', 'facebook'):
        prefix = transport_name
    else:
        prefix = 'jabber'
    return prefix

def get_name_from_jid(account, jid):
    """
    Return from JID's shown name and if no contact returns jids
    """
    contact = contacts.get_first_contact_from_jid(account, jid)
    if contact:
        actor = contact.get_shown_name()
    else:
        actor = jid
    return actor


def get_recent_groupchats(account):
    recent_groupchats = config.get_per(
        'accounts', account, 'recent_groupchats').split()

    RecentGroupchat = namedtuple('RecentGroupchat',
                                 ['room', 'server', 'nickname'])

    recent_list = []
    for groupchat in recent_groupchats:
        jid = nbxmpp.JID(groupchat)
        recent = RecentGroupchat(
            jid.getNode(), jid.getDomain(), jid.getResource())
        recent_list.append(recent)
    return recent_list

def add_recent_groupchat(account, room_jid, nickname):
    recent = config.get_per(
        'accounts', account, 'recent_groupchats').split()
    full_jid = room_jid + '/' + nickname
    if full_jid in recent:
        recent.remove(full_jid)
    recent.insert(0, full_jid)
    if len(recent) > 10:
        recent = recent[0:9]
    config_value = ' '.join(recent)
    config.set_per(
        'accounts', account, 'recent_groupchats', config_value)

def get_priority(account, show):
    """
    Return the priority an account must have
    """
    if not show:
        show = 'online'

    if show in ('online', 'chat', 'away', 'xa', 'dnd') and \
    config.get_per('accounts', account, 'adjust_priority_with_status'):
        prio = config.get_per('accounts', account, 'autopriority_' + show)
    else:
        prio = config.get_per('accounts', account, 'priority')
    if prio < -128:
        prio = -128
    elif prio > 127:
        prio = 127
    return prio

def log(domain):
    if domain != 'gajim':
        domain = 'gajim.%s' % domain
    return logging.getLogger(domain)

def prefers_app_menu():
    if sys.platform == 'darwin':
        return True
    if sys.platform == 'win32':
        return False
    return app.prefers_app_menu()

def load_css_config():
    global css_config
    from gajim.gtk.css_config import CSSConfig
    css_config = CSSConfig()

def set_debug_mode(enable: bool) -> None:
    debug_folder = Path(configpaths.get('DEBUG'))
    debug_enabled = debug_folder / 'debug-enabled'
    if enable:
        debug_enabled.touch()
    else:
        if debug_enabled.exists():
            debug_enabled.unlink()

def get_debug_mode() -> bool:
    debug_folder = Path(configpaths.get('DEBUG'))
    debug_enabled = debug_folder / 'debug-enabled'
    return debug_enabled.exists()

def get_stored_bob_data(algo_hash: str) -> Optional[bytes]:
    try:
        return bob_cache[algo_hash]
    except KeyError:
        filepath = Path(configpaths.get('BOB')) / algo_hash
        if filepath.exists():
            with open(str(filepath), 'r+b') as file:
                data = file.read()
            return data
    return None

def get_groupchat_control(account, jid):
    control = app.interface.msg_win_mgr.get_gc_control(jid, account)
    if control is not None:
        return control
    try:
        return app.interface.minimized_controls[account][jid]
    except Exception:
        return None
