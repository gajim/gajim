# -*- coding:utf-8 -*-
## src/common/check_paths.py
##
## Copyright (C) 2005-2006 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2008 Jean-Marie Traissard <jim AT lapin.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import shutil
import sys
import stat

from common import gajim
from common import logger
from common import jingle_xtls

# DO NOT MOVE ABOVE OF import gajim
import sqlite3 as sqlite

def create_log_db():
    print(_('creating logs database'))
    con = sqlite.connect(logger.LOG_DB_PATH)
    os.chmod(logger.LOG_DB_PATH, 0o600) # rw only for us
    cur = con.cursor()
    # create the tables
    # kind can be
    # status, gcstatus, gc_msg, (we only recv for those 3),
    # single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
    # to meet all our needs
    # logs.jid_id --> jids.jid_id but Sqlite doesn't do FK etc so it's done in python code
    # jids.jid text column will be JID if TC-related, room_jid if GC-related,
    # ROOM_JID/nick if pm-related.
    # also check optparser.py, which updates databases on gajim updates
    cur.executescript(
            '''
            CREATE TABLE jids(
                    jid_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                    jid TEXT UNIQUE,
                    type INTEGER
            );

            CREATE TABLE unread_messages(
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                    jid_id INTEGER,
                    shown BOOLEAN default 0
            );

            CREATE INDEX idx_unread_messages_jid_id ON unread_messages (jid_id);

            CREATE TABLE logs(
                    log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                    jid_id INTEGER,
                    contact_name TEXT,
                    time INTEGER,
                    kind INTEGER,
                    show INTEGER,
                    message TEXT,
                    subject TEXT
            );

            CREATE INDEX idx_logs_jid_id_time ON logs (jid_id, time DESC);
            '''
            )

    con.commit()
    con.close()

def create_cache_db():
    print(_('creating cache database'))
    con = sqlite.connect(logger.CACHE_DB_PATH)
    os.chmod(logger.CACHE_DB_PATH, 0o600) # rw only for us
    cur = con.cursor()
    cur.executescript(
            '''
            CREATE TABLE transports_cache (
                    transport TEXT UNIQUE,
                    type INTEGER
            );

            CREATE TABLE caps_cache (
                    hash_method TEXT,
                    hash TEXT,
                    data BLOB,
                    last_seen INTEGER);

            CREATE TABLE rooms_last_message_time(
                    jid_id INTEGER PRIMARY KEY UNIQUE,
                    time INTEGER
            );

            CREATE TABLE IF NOT EXISTS roster_entry(
                    account_jid_id INTEGER,
                    jid_id INTEGER,
                    name TEXT,
                    subscription INTEGER,
                    ask BOOLEAN,
                    PRIMARY KEY (account_jid_id, jid_id)
            );

            CREATE TABLE IF NOT EXISTS roster_group(
                    account_jid_id INTEGER,
                    jid_id INTEGER,
                    group_name TEXT,
                    PRIMARY KEY (account_jid_id, jid_id, group_name)
            );
            '''
            )

    con.commit()
    con.close()

def split_db():
    print('spliting database')
    if os.name == 'nt':
        try:
            import configpaths
            OLD_LOG_DB_FOLDER = os.path.join(configpaths.fse(
                os.environ['appdata']), 'Gajim')
        except KeyError:
            OLD_LOG_DB_FOLDER = '.'
    else:
        OLD_LOG_DB_FOLDER = os.path.expanduser('~/.gajim')

    tmp = logger.CACHE_DB_PATH
    logger.CACHE_DB_PATH = os.path.join(OLD_LOG_DB_FOLDER, 'cache.db')
    create_cache_db()
    back = os.getcwd()
    os.chdir(OLD_LOG_DB_FOLDER)
    con = sqlite.connect('logs.db')
    os.chdir(back)
    cur = con.cursor()
    cur.execute('''SELECT name FROM sqlite_master WHERE type = 'table';''')
    tables = cur.fetchall() # we get [('jids',), ('unread_messages',), ...
    tables = [t[0] for t in tables]
    cur.execute("ATTACH DATABASE '%s' AS cache" % logger.CACHE_DB_PATH)
    for table in ('caps_cache', 'rooms_last_message_time', 'roster_entry',
    'roster_group', 'transports_cache'):
        if table not in tables:
            continue
        try:
            cur.executescript(
                    'INSERT INTO cache.%s SELECT * FROM %s;' % (table, table))
            con.commit()
            cur.executescript('DROP TABLE %s;' % table)
            con.commit()
        except sqlite.OperationalError as e:
            print('error moving table %s to cache.db: %s' % (table, str(e)),
                file=sys.stderr)
    con.close()
    logger.CACHE_DB_PATH = tmp

def check_and_possibly_move_config():
    LOG_DB_PATH = logger.LOG_DB_PATH
    CACHE_DB_PATH = logger.CACHE_DB_PATH
    vars = {}
    vars['VCARD_PATH'] = gajim.VCARD_PATH
    vars['AVATAR_PATH'] = gajim.AVATAR_PATH
    vars['MY_EMOTS_PATH'] = gajim.MY_EMOTS_PATH
    vars['MY_ICONSETS_PATH'] = gajim.MY_ICONSETS_PATH
    vars['MY_MOOD_ICONSETS_PATH'] = gajim.MY_MOOD_ICONSETS_PATH
    vars['MY_ACTIVITY_ICONSETS_PATH'] = gajim.MY_ACTIVITY_ICONSETS_PATH
    from common import configpaths
    MY_DATA = configpaths.gajimpaths['MY_DATA']
    MY_CONFIG = configpaths.gajimpaths['MY_CONFIG']
    MY_CACHE = configpaths.gajimpaths['MY_CACHE']

    if os.path.exists(LOG_DB_PATH):
        # File already exists
        return

    if os.name == 'nt':
        try:
            OLD_LOG_DB_FOLDER = os.path.join(configpaths.fse(
                os.environ['appdata']), 'Gajim')
        except KeyError:
            OLD_LOG_DB_FOLDER = '.'
    else:
        OLD_LOG_DB_FOLDER = os.path.expanduser('~/.gajim')
    if not os.path.exists(OLD_LOG_DB_FOLDER):
        return
    OLD_LOG_DB_PATH = os.path.join(OLD_LOG_DB_FOLDER, 'logs.db')
    OLD_CACHE_DB_PATH = os.path.join(OLD_LOG_DB_FOLDER, 'cache.db')
    vars['OLD_VCARD_PATH'] = os.path.join(OLD_LOG_DB_FOLDER, 'vcards')
    vars['OLD_AVATAR_PATH'] = os.path.join(OLD_LOG_DB_FOLDER, 'avatars')
    vars['OLD_MY_EMOTS_PATH'] = os.path.join(OLD_LOG_DB_FOLDER, 'emoticons')
    vars['OLD_MY_ICONSETS_PATH'] = os.path.join(OLD_LOG_DB_FOLDER, 'iconsets')
    vars['OLD_MY_MOOD_ICONSETS_PATH'] = os.path.join(OLD_LOG_DB_FOLDER, 'moods')
    vars['OLD_MY_ACTIVITY_ICONSETS_PATH'] = os.path.join(OLD_LOG_DB_FOLDER,
            'activities')
    OLD_CONFIG_FILES = []
    OLD_DATA_FILES = []
    for f in os.listdir(OLD_LOG_DB_FOLDER):
        if f == 'config' or f.startswith('config.'):
            OLD_CONFIG_FILES.append(f)
        if f == 'secrets' or f.startswith('secrets.'):
            OLD_DATA_FILES.append(f)
        if f == 'cacerts.pem':
            OLD_DATA_FILES.append(f)

    if not os.path.exists(OLD_LOG_DB_PATH):
        return

    if not os.path.exists(OLD_CACHE_DB_PATH):
        # split database
        split_db()

    to_move = {}
    to_move[OLD_LOG_DB_PATH] = LOG_DB_PATH
    to_move[OLD_CACHE_DB_PATH] = CACHE_DB_PATH

    for folder in ('VCARD_PATH', 'AVATAR_PATH', 'MY_EMOTS_PATH',
    'MY_ICONSETS_PATH', 'MY_MOOD_ICONSETS_PATH', 'MY_ACTIVITY_ICONSETS_PATH'):
        src = vars['OLD_' + folder]
        dst = vars[folder]
        to_move[src] = dst

    # move config files
    for f in OLD_CONFIG_FILES:
        src = os.path.join(OLD_LOG_DB_FOLDER, f)
        dst = os.path.join(MY_CONFIG, f)
        to_move[src] = dst

    # Move data files (secrets, cacert.pem)
    for f in OLD_DATA_FILES:
        src = os.path.join(OLD_LOG_DB_FOLDER, f)
        dst = os.path.join(MY_DATA, f)
        to_move[src] = dst

    for src, dst in to_move.items():
        if os.path.exists(dst):
            continue
        if not os.path.exists(src):
            continue
        print(_('moving %s to %s') % (src, dst))
        shutil.move(src, dst)
    gajim.logger.init_vars()
    gajim.logger.attach_cache_database()

def check_and_possibly_create_paths():
    LOG_DB_PATH = logger.LOG_DB_PATH
    LOG_DB_FOLDER, LOG_DB_FILE = os.path.split(LOG_DB_PATH)

    CACHE_DB_PATH = logger.CACHE_DB_PATH
    CACHE_DB_FOLDER, CACHE_DB_FILE = os.path.split(CACHE_DB_PATH)

    VCARD_PATH = gajim.VCARD_PATH
    AVATAR_PATH = gajim.AVATAR_PATH
    from common import configpaths
    MY_DATA = configpaths.gajimpaths['MY_DATA']
    MY_CONFIG = configpaths.gajimpaths['MY_CONFIG']
    MY_CACHE = configpaths.gajimpaths['MY_CACHE']
    XTLS_CERTS = configpaths.gajimpaths['MY_PEER_CERTS']
    LOCAL_XTLS_CERTS = configpaths.gajimpaths['MY_CERT']

    PLUGINS_CONFIG_PATH = gajim.PLUGINS_CONFIG_DIR

    if not os.path.exists(MY_DATA):
        create_path(MY_DATA)
    elif os.path.isfile(MY_DATA):
        print(_('%s is a file but it should be a directory') % MY_DATA)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(MY_CONFIG):
        create_path(MY_CONFIG)
    elif os.path.isfile(MY_CONFIG):
        print(_('%s is a file but it should be a directory') % MY_CONFIG)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(MY_CACHE):
        create_path(MY_CACHE)
    elif os.path.isfile(MY_CACHE):
        print(_('%s is a file but it should be a directory') % MY_CACHE)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(VCARD_PATH):
        create_path(VCARD_PATH)
    elif os.path.isfile(VCARD_PATH):
        print(_('%s is a file but it should be a directory') % VCARD_PATH)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(AVATAR_PATH):
        create_path(AVATAR_PATH)
    elif os.path.isfile(AVATAR_PATH):
        print(_('%s is a file but it should be a directory') % AVATAR_PATH)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(LOG_DB_FOLDER):
        create_path(LOG_DB_FOLDER)
    elif os.path.isfile(LOG_DB_FOLDER):
        print(_('%s is a file but it should be a directory') % LOG_DB_FOLDER)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(PLUGINS_CONFIG_PATH):
        create_path(PLUGINS_CONFIG_PATH)
    elif os.path.isfile(PLUGINS_CONFIG_PATH):
        print(_('%s is a file but it should be a directory') % PLUGINS_CONFIG_PATH)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(CACHE_DB_FOLDER):
        create_path(CACHE_DB_FOLDER)
    elif os.path.isfile(CACHE_DB_FOLDER):
        print(_('%s is a file but it should be a directory') % CACHE_DB_FOLDER)
        print(_('Gajim will now exit'))
        sys.exit()

    check_and_possibly_move_config()

    if not os.path.exists(LOG_DB_PATH):
        create_log_db()
        gajim.logger.init_vars()
    elif os.path.isdir(LOG_DB_PATH):
        print(_('%s is a directory but should be a file') % LOG_DB_PATH)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(CACHE_DB_PATH):
        create_cache_db()
        gajim.logger.attach_cache_database()
    elif os.path.isdir(CACHE_DB_PATH):
        print(_('%s is a directory but should be a file') % CACHE_DB_PATH)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(XTLS_CERTS):
        create_path(XTLS_CERTS)
    if not os.path.exists(LOCAL_XTLS_CERTS):
        create_path(LOCAL_XTLS_CERTS)
    cert_name = os.path.join(LOCAL_XTLS_CERTS,
        jingle_xtls.SELF_SIGNED_CERTIFICATE)
    if gajim.HAVE_PYOPENSSL and not (os.path.exists(cert_name + '.cert') and \
    os.path.exists(cert_name + '.pkey')):
        jingle_xtls.make_certs(cert_name, 'gajim')


def create_path(directory):
    head, tail = os.path.split(directory)
    if not os.path.exists(head):
        create_path(head)
    if os.path.exists(directory):
        return
    print(('creating %s directory') % directory)
    os.mkdir(directory, 0o700)
