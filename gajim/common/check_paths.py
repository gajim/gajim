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
import sys
import sqlite3

from gajim.common import app
from gajim.common import logger
from gajim.common import configpaths
from gajim.common.const import PathType


def create_log_db():
    print(_('creating logs database'))
    con = sqlite3.connect(logger.LOG_DB_PATH)
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
                    account_id INTEGER,
                    jid_id INTEGER,
                    contact_name TEXT,
                    time INTEGER,
                    kind INTEGER,
                    show INTEGER,
                    message TEXT,
                    subject TEXT,
                    additional_data TEXT,
                    stanza_id TEXT,
                    encryption TEXT,
                    encryption_state TEXT,
                    marker INTEGER
            );

            CREATE TABLE last_archive_message(
                    jid_id INTEGER PRIMARY KEY UNIQUE,
                    last_mam_id TEXT,
                    oldest_mam_timestamp TEXT,
                    last_muc_timestamp TEXT
            );

            CREATE INDEX idx_logs_jid_id_time ON logs (jid_id, time DESC);
            '''
            )

    con.commit()
    con.close()

def create_cache_db():
    print(_('creating cache database'))
    con = sqlite3.connect(logger.CACHE_DB_PATH)
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
                    avatar_sha TEXT,
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

def check_and_possibly_create_paths():
    LOG_DB_PATH = configpaths.get('LOG_DB')
    CACHE_DB_PATH = configpaths.get('CACHE_DB')

    for path in configpaths.get_paths(PathType.FOLDER):
        if not os.path.exists(path):
            create_path(path)
        elif os.path.isfile(path):
            print(_('%s is a file but it should be a directory') % path)
            print(_('Gajim will now exit'))
            sys.exit()

    if not os.path.exists(LOG_DB_PATH):
        if os.path.exists(CACHE_DB_PATH):
            os.remove(CACHE_DB_PATH)
        create_log_db()
        app.logger.init_vars()
    elif os.path.isdir(LOG_DB_PATH):
        print(_('%s is a directory but should be a file') % LOG_DB_PATH)
        print(_('Gajim will now exit'))
        sys.exit()

    if not os.path.exists(CACHE_DB_PATH):
        create_cache_db()
        app.logger.attach_cache_database()
    elif os.path.isdir(CACHE_DB_PATH):
        print(_('%s is a directory but should be a file') % CACHE_DB_PATH)
        print(_('Gajim will now exit'))
        sys.exit()

def create_path(directory):
    head, tail = os.path.split(directory)
    if not os.path.exists(head):
        create_path(head)
    if os.path.exists(directory):
        return
    print(('creating %s directory') % directory)
    os.mkdir(directory, 0o700)
