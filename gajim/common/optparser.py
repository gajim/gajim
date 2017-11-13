# -*- coding:utf-8 -*-
## src/common/optparser.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 James Newton <redshodan AT gmail.com>
##                    Brendan Taylor <whateley AT gmail.com>
##                    Tomasz Melcer <liori AT exroot.org>
##                    Stephan Erb <steve-e AT h3c.de>
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
import re
from time import time
from gajim.common import app
from gajim.common import helpers
from gajim.common import caps_cache

import sqlite3 as sqlite
from gajim.common import logger

import logging
log = logging.getLogger('gajim.c.optparser')

class OptionsParser:
    def __init__(self, filename):
        self.__filename = os.path.realpath(filename)
        self.old_values = {}    # values that are saved in the file and maybe
                                                        # no longer valid

    def read(self):
        try:
            fd = open(self.__filename)
        except Exception:
            if os.path.exists(self.__filename):
                #we talk about a file
                print(_('Error: cannot open %s for reading') % self.__filename,
                    file=sys.stderr)
            return False

        new_version = app.config.get('version')
        new_version = new_version.split('-', 1)[0]
        seen = set()
        regex = re.compile(r"(?P<optname>[^.=]+)(?:(?:\.(?P<key>.+))?\.(?P<subname>[^.=]+))?\s=\s(?P<value>.*)")

        for line in fd:
            match = regex.match(line)
            if match is None:
                log.warn('Invalid configuration line, ignoring it: %s', line)
                continue
            optname, key, subname, value = match.groups()
            if key is None:
                self.old_values[optname] = value
                app.config.set(optname, value)
            else:
                if (optname, key) not in seen:
                    if optname in self.old_values:
                        self.old_values[optname][key] = {}
                    else:
                        self.old_values[optname] = {key: {}}
                    app.config.add_per(optname, key)
                    seen.add((optname, key))
                self.old_values[optname][key][subname] = value
                app.config.set_per(optname, key, subname, value)

        old_version = app.config.get('version')
        old_version = old_version.split('-', 1)[0]

        self.update_config(old_version, new_version)
        self.old_values = {} # clean mem

        fd.close()
        return True

    def write_line(self, fd, opt, parents, value):
        if value is None:
            return
        # convert to utf8 before writing to file if needed
        value = str(value)
        s = ''
        if parents:
            if len(parents) == 1:
                return
            for p in parents:
                s += p + '.'
        s += opt
        fd.write(s + ' = ' + value + '\n')

    def write(self):
        (base_dir, filename) = os.path.split(self.__filename)
        self.__tempfile = os.path.join(base_dir, '.' + filename)
        try:
            f = os.fdopen(os.open(self.__tempfile,
                os.O_CREAT|os.O_WRONLY|os.O_TRUNC, 0o600), 'w')
        except IOError as e:
            return str(e)
        try:
            app.config.foreach(self.write_line, f)
        except IOError as e:
            return str(e)
        f.flush()
        os.fsync(f.fileno())
        f.close()
        if os.path.exists(self.__filename):
            if os.name == 'nt':
                # win32 needs this
                try:
                    os.remove(self.__filename)
                except Exception:
                    pass
        try:
            os.rename(self.__tempfile, self.__filename)
        except IOError as e:
            return str(e)

    def update_config(self, old_version, new_version):
        old_version_list = old_version.split('.') # convert '0.x.y' to (0, x, y)
        old = []
        while len(old_version_list):
            old.append(int(old_version_list.pop(0)))
        new_version_list = new_version.split('.')
        new = []
        while len(new_version_list):
            new.append(int(new_version_list.pop(0)))

        if old < [0, 9] and new >= [0, 9]:
            self.update_config_x_to_09()
        if old < [0, 10] and new >= [0, 10]:
            self.update_config_09_to_010()
        if old < [0, 10, 1, 1] and new >= [0, 10, 1, 1]:
            self.update_config_to_01011()
        if old < [0, 10, 1, 2] and new >= [0, 10, 1, 2]:
            self.update_config_to_01012()
        if old < [0, 10, 1, 3] and new >= [0, 10, 1, 3]:
            self.update_config_to_01013()
        if old < [0, 10, 1, 4] and new >= [0, 10, 1, 4]:
            self.update_config_to_01014()
        if old < [0, 10, 1, 5] and new >= [0, 10, 1, 5]:
            self.update_config_to_01015()
        if old < [0, 10, 1, 6] and new >= [0, 10, 1, 6]:
            self.update_config_to_01016()
        if old < [0, 10, 1, 7] and new >= [0, 10, 1, 7]:
            self.update_config_to_01017()
        if old < [0, 10, 1, 8] and new >= [0, 10, 1, 8]:
            self.update_config_to_01018()
        if old < [0, 11, 0, 1] and new >= [0, 11, 0, 1]:
            self.update_config_to_01101()
        if old < [0, 11, 0, 2] and new >= [0, 11, 0, 2]:
            self.update_config_to_01102()
        if old < [0, 11, 1, 1] and new >= [0, 11, 1, 1]:
            self.update_config_to_01111()
        if old < [0, 11, 1, 2] and new >= [0, 11, 1, 2]:
            self.update_config_to_01112()
        if old < [0, 11, 1, 3] and new >= [0, 11, 1, 3]:
            self.update_config_to_01113()
        if old < [0, 11, 1, 4] and new >= [0, 11, 1, 4]:
            self.update_config_to_01114()
        if old < [0, 11, 1, 5] and new >= [0, 11, 1, 5]:
            self.update_config_to_01115()
        if old < [0, 11, 2, 1] and new >= [0, 11, 2, 1]:
            self.update_config_to_01121()
        if old < [0, 11, 4, 1] and new >= [0, 11, 4, 1]:
            self.update_config_to_01141()
        if old < [0, 11, 4, 2] and new >= [0, 11, 4, 2]:
            self.update_config_to_01142()
        if old < [0, 11, 4, 3] and new >= [0, 11, 4, 3]:
            self.update_config_to_01143()
        if old < [0, 11, 4, 4] and new >= [0, 11, 4, 4]:
            self.update_config_to_01144()
        if old < [0, 12, 0, 1] and new >= [0, 12, 0, 1]:
            self.update_config_to_01201()
        if old < [0, 12, 1, 1] and new >= [0, 12, 1, 1]:
            self.update_config_to_01211()
        if old < [0, 12, 1, 2] and new >= [0, 12, 1, 2]:
            self.update_config_to_01212()
        if old < [0, 12, 1, 3] and new >= [0, 12, 1, 3]:
            self.update_config_to_01213()
        if old < [0, 12, 1, 4] and new >= [0, 12, 1, 4]:
            self.update_config_to_01214()
        if old < [0, 12, 1, 5] and new >= [0, 12, 1, 5]:
            self.update_config_to_01215()
        if old < [0, 12, 3, 1] and new >= [0, 12, 3, 1]:
            self.update_config_to_01231()
        if old < [0, 12, 5, 1] and new >= [0, 12, 5, 1]:
            self.update_config_from_0125()
            self.update_config_to_01251()
        if old < [0, 12, 5, 2] and new >= [0, 12, 5, 2]:
            self.update_config_to_01252()
        if old < [0, 12, 5, 3] and new >= [0, 12, 5, 3]:
            self.update_config_to_01253()
        if old < [0, 12, 5, 4] and new >= [0, 12, 5, 4]:
            self.update_config_to_01254()
        if old < [0, 12, 5, 5] and new >= [0, 12, 5, 5]:
            self.update_config_to_01255()
        if old < [0, 12, 5, 6] and new >= [0, 12, 5, 6]:
            self.update_config_to_01256()
        if old < [0, 12, 5, 7] and new >= [0, 12, 5, 7]:
            self.update_config_to_01257()
        if old < [0, 12, 5, 8] and new >= [0, 12, 5, 8]:
            self.update_config_to_01258()
        if old < [0, 13, 10, 0] and new >= [0, 13, 10, 0]:
            self.update_config_to_013100()
        if old < [0, 13, 10, 1] and new >= [0, 13, 10, 1]:
            self.update_config_to_013101()
        if old < [0, 13, 90, 1] and new >= [0, 13, 90, 1]:
            self.update_config_to_013901()
        if old < [0, 14, 0, 1] and new >= [0, 14, 0, 1]:
            self.update_config_to_01401()
        if old < [0, 14, 90, 0] and new >= [0, 14, 90, 0]:
            self.update_config_to_014900()
        if old < [0, 16, 0, 1] and new >= [0, 16, 0, 1]:
            self.update_config_to_01601()
        if old < [0, 16, 4, 1] and new >= [0, 16, 4, 1]:
            self.update_config_to_01641()
        if old < [0, 16, 10, 1] and new >= [0, 16, 10, 1]:
            self.update_config_to_016101()
        if old < [0, 16, 10, 2] and new >= [0, 16, 10, 2]:
            self.update_config_to_016102()
        if old < [0, 16, 10, 3] and new >= [0, 16, 10, 3]:
            self.update_config_to_016103()
        if old < [0, 16, 10, 4] and new >= [0, 16, 10, 4]:
            self.update_config_to_016104()
        if old < [0, 16, 10, 5] and new >= [0, 16, 10, 5]:
            self.update_config_to_016105()
        if old < [0, 16, 11, 1] and new >= [0, 16, 11, 1]:
            self.update_config_to_016111()
        if old < [0, 16, 11, 2] and new >= [0, 16, 11, 2]:
            self.update_config_to_016112()

        app.logger.init_vars()
        app.logger.attach_cache_database()
        app.config.set('version', new_version)

        caps_cache.capscache.initialize_from_db()

    @staticmethod
    def assert_unread_msgs_table_exists():
        """
        Create table unread_messages if there is no such table
        """
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    CREATE TABLE unread_messages (
                            message_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                            jid_id INTEGER
                    );
                    '''
            )
            con.commit()
            app.logger.init_vars()
        except sqlite.OperationalError:
            pass
        con.close()

    @staticmethod
    def update_ft_proxies(to_remove=None, to_add=None):
        if to_remove is None:
            to_remove = []
        if to_add is None:
            to_add = []
        for account in app.config.get_per('accounts'):
            proxies_str = app.config.get_per('accounts', account,
                    'file_transfer_proxies')
            proxies = [p.strip() for p in proxies_str.split(',')]
            for wrong_proxy in to_remove:
                if wrong_proxy in proxies:
                    proxies.remove(wrong_proxy)
            for new_proxy in to_add:
                if new_proxy not in proxies:
                    proxies.append(new_proxy)
            proxies_str = ', '.join(proxies)
            app.config.set_per('accounts', account, 'file_transfer_proxies',
                    proxies_str)

    def update_config_x_to_09(self):
        # Var name that changed:
        # avatar_width /height -> chat_avatar_width / height
        if 'avatar_width' in self.old_values:
            app.config.set('chat_avatar_width', self.old_values['avatar_width'])
        if 'avatar_height' in self.old_values:
            app.config.set('chat_avatar_height', self.old_values['avatar_height'])
        if 'use_dbus' in self.old_values:
            app.config.set('remote_control', self.old_values['use_dbus'])
        # always_compact_view -> always_compact_view_chat / _gc
        if 'always_compact_view' in self.old_values:
            app.config.set('always_compact_view_chat',
                    self.old_values['always_compact_view'])
            app.config.set('always_compact_view_gc',
                    self.old_values['always_compact_view'])
        # new theme: grocery, plain
        d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
                'accountfontattrs', 'grouptextcolor', 'groupbgcolor', 'groupfont',
                'groupfontattrs', 'contacttextcolor', 'contactbgcolor', 'contactfont',
                'contactfontattrs', 'bannertextcolor', 'bannerbgcolor', 'bannerfont',
                'bannerfontattrs']
        for theme_name in (_('grocery'), _('default')):
            if theme_name not in app.config.get_per('themes'):
                app.config.add_per('themes', theme_name)
                theme = app.config.themes_default[theme_name]
                for o in d:
                    app.config.set_per('themes', theme_name, o, theme[d.index(o)])
        # Remove cyan theme if it's not the current theme
        if 'cyan' in app.config.get_per('themes'):
            app.config.del_per('themes', 'cyan')
        if _('cyan') in app.config.get_per('themes'):
            app.config.del_per('themes', _('cyan'))
        # If we removed our roster_theme, choose the default green one or another
        # one if doesn't exists in config
        if app.config.get('roster_theme') not in app.config.get_per('themes'):
            theme = _('green')
            if theme not in app.config.get_per('themes'):
                theme = app.config.get_per('themes')[0]
            app.config.set('roster_theme', theme)
        # new proxies in accounts.name.file_transfer_proxies
        self.update_ft_proxies(to_add=['proxy.netlab.cz'])

        app.config.set('version', '0.9')

    def update_config_09_to_010(self):
        if 'usetabbedchat' in self.old_values and not \
        self.old_values['usetabbedchat']:
            app.config.set('one_message_window', 'never')
        if 'autodetect_browser_mailer' in self.old_values and \
        self.old_values['autodetect_browser_mailer'] is True:
            app.config.set('autodetect_browser_mailer', False)
        if 'useemoticons' in self.old_values and \
        not self.old_values['useemoticons']:
            app.config.set('emoticons_theme', '')
        if 'always_compact_view_chat' in self.old_values and \
        self.old_values['always_compact_view_chat'] != 'False':
            app.config.set('always_hide_chat_buttons', True)
        if 'always_compact_view_gc' in self.old_values and \
        self.old_values['always_compact_view_gc'] != 'False':
            app.config.set('always_hide_groupchat_buttons', True)

        self.update_ft_proxies(to_remove=['proxy65.jabber.autocom.pl',
                'proxy65.jabber.ccc.de'], to_add=['transfer.jabber.freenet.de'])
        # create unread_messages table if needed
        self.assert_unread_msgs_table_exists()

        app.config.set('version', '0.10')

    def update_config_to_01011(self):
        if 'print_status_in_muc' in self.old_values and \
                self.old_values['print_status_in_muc'] in (True, False):
            app.config.set('print_status_in_muc', 'in_and_out')
        app.config.set('version', '0.10.1.1')

    def update_config_to_01012(self):
        # See [6456]
        if 'emoticons_theme' in self.old_values and \
                self.old_values['emoticons_theme'] == 'Disabled':
            app.config.set('emoticons_theme', '')
        app.config.set('version', '0.10.1.2')

    def update_config_to_01013(self):
        """
        Create table transports_cache if there is no such table
        """
        # FIXME see #2812
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    CREATE TABLE transports_cache (
                            transport TEXT UNIQUE,
                            type INTEGER
                    );
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.10.1.3')

    def update_config_to_01014(self):
        """
        Apply indeces to the logs database
        """
        print(_('migrating logs database to indices'))
        # FIXME see #2812
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        # apply indeces
        try:
            cur.executescript(
                    '''
                    CREATE INDEX idx_logs_jid_id_kind ON logs (jid_id, kind);
                    CREATE INDEX idx_unread_messages_jid_id ON unread_messages (jid_id);
                    '''
            )

            con.commit()
        except Exception:
            pass
        con.close()
        app.config.set('version', '0.10.1.4')

    def update_config_to_01015(self):
        """
        Clean show values in logs database
        """
        #FIXME see #2812
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        status = dict((i[5:].lower(), logger.constants.__dict__[i]) for i in \
                logger.constants.__dict__.keys() if i.startswith('SHOW_'))
        for show in status:
            cur.execute('update logs set show = ? where show = ?;', (status[show],
                    show))
        cur.execute('update logs set show = NULL where show not in (0, 1, 2, 3, 4, 5);')
        con.commit()
        cur.close() # remove this in 2007 [pysqlite old versions need this]
        con.close()
        app.config.set('version', '0.10.1.5')

    def update_config_to_01016(self):
        """
        #2494 : Now we play gc_received_message sound even if
        notify_on_all_muc_messages is false. Keep precedent behaviour
        """
        if 'notify_on_all_muc_messages' in self.old_values and \
        self.old_values['notify_on_all_muc_messages'] == 'False' and \
        app.config.get_per('soundevents', 'muc_message_received', 'enabled'):
            app.config.set_per('soundevents',\
                    'muc_message_received', 'enabled', False)
        app.config.set('version', '0.10.1.6')

    def update_config_to_01017(self):
        """
        trayicon_notification_on_new_messages -> trayicon_notification_on_events
        """
        if 'trayicon_notification_on_new_messages' in self.old_values:
            app.config.set('trayicon_notification_on_events',
                    self.old_values['trayicon_notification_on_new_messages'])
        app.config.set('version', '0.10.1.7')

    def update_config_to_01018(self):
        """
        chat_state_notifications -> outgoing_chat_state_notifications
        """
        if 'chat_state_notifications' in self.old_values:
            app.config.set('outgoing_chat_state_notifications',
                    self.old_values['chat_state_notifications'])
        app.config.set('version', '0.10.1.8')

    def update_config_to_01101(self):
        """
        Fill time_stamp from before_time and after_time
        """
        if 'before_time' in self.old_values:
            app.config.set('time_stamp', '%s%%X%s ' % (
                    self.old_values['before_time'], self.old_values['after_time']))
        app.config.set('version', '0.11.0.1')

    def update_config_to_01102(self):
        """
        Fill time_stamp from before_time and after_time
        """
        if 'ft_override_host_to_send' in self.old_values:
            app.config.set('ft_add_hosts_to_send',
                    self.old_values['ft_override_host_to_send'])
        app.config.set('version', '0.11.0.2')

    def update_config_to_01111(self):
        """
        Always_hide_chatbuttons -> compact_view
        """
        if 'always_hide_groupchat_buttons' in self.old_values and \
        'always_hide_chat_buttons' in self.old_values:
            app.config.set('compact_view', self.old_values['always_hide_groupchat_buttons'] and \
            self.old_values['always_hide_chat_buttons'])
        app.config.set('version', '0.11.1.1')

    def update_config_to_01112(self):
        """
        GTK+ theme is renamed to default
        """
        if 'roster_theme' in self.old_values and \
        self.old_values['roster_theme'] == 'gtk+':
            app.config.set('roster_theme', _('default'))
        app.config.set('version', '0.11.1.2')

    def update_config_to_01113(self):
        # copy&pasted from update_config_to_01013, possibly 'FIXME see #2812' applies too
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    CREATE TABLE caps_cache (
                            node TEXT,
                            ver TEXT,
                            ext TEXT,
                            data BLOB
                    );
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.11.1.3')

    def update_config_to_01114(self):
        # add default theme if it doesn't exist
        d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
                'accountfontattrs', 'grouptextcolor', 'groupbgcolor', 'groupfont',
                'groupfontattrs', 'contacttextcolor', 'contactbgcolor', 'contactfont',
                'contactfontattrs', 'bannertextcolor', 'bannerbgcolor', 'bannerfont',
                'bannerfontattrs']
        theme_name = _('default')
        if theme_name not in app.config.get_per('themes'):
            app.config.add_per('themes', theme_name)
            if app.config.get_per('themes', 'gtk+'):
                # copy from old gtk+ theme
                for o in d:
                    val = app.config.get_per('themes', 'gtk+', o)
                    app.config.set_per('themes', theme_name, o, val)
                app.config.del_per('themes', 'gtk+')
            else:
                # copy from default theme
                theme = app.config.themes_default[theme_name]
                for o in d:
                    app.config.set_per('themes', theme_name, o, theme[d.index(o)])
        app.config.set('version', '0.11.1.4')

    def update_config_to_01115(self):
        # copy&pasted from update_config_to_01013, possibly 'FIXME see #2812' applies too
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    DELETE FROM caps_cache;
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.11.1.5')

    def update_config_to_01121(self):
        # remove old unencrypted secrets file
        from gajim.common.configpaths import gajimpaths

        new_file = gajimpaths['SECRETS_FILE']

        old_file = os.path.dirname(new_file) + '/secrets'

        if os.path.exists(old_file):
            os.remove(old_file)

        app.config.set('version', '0.11.2.1')

    def update_config_to_01141(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    CREATE TABLE IF NOT EXISTS caps_cache (
                            node TEXT,
                            ver TEXT,
                            ext TEXT,
                            data BLOB
                    );
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.11.4.1')

    def update_config_to_01142(self):
        """
        next_message_received sound event is splittedin 2 events
        """
        app.config.add_per('soundevents', 'next_message_received_focused')
        app.config.add_per('soundevents', 'next_message_received_unfocused')
        if app.config.get_per('soundevents', 'next_message_received'):
            enabled = app.config.get_per('soundevents', 'next_message_received',
                    'enabled')
            path = app.config.get_per('soundevents', 'next_message_received',
                    'path')
            app.config.del_per('soundevents', 'next_message_received')
            app.config.set_per('soundevents', 'next_message_received_focused',
                    'enabled', enabled)
            app.config.set_per('soundevents', 'next_message_received_focused',
                    'path', path)
        app.config.set('version', '0.11.1.2')

    def update_config_to_01143(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    CREATE TABLE IF NOT EXISTS rooms_last_message_time(
                            jid_id INTEGER PRIMARY KEY UNIQUE,
                            time INTEGER
                    );
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.11.4.3')

    def update_config_to_01144(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript('DROP TABLE caps_cache;')
            con.commit()
        except sqlite.OperationalError:
            pass
        try:
            cur.executescript(
                    '''
                    CREATE TABLE caps_cache (
                            hash_method TEXT,
                            hash TEXT,
                            data BLOB
                    );
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.11.4.4')

    def update_config_to_01201(self):
        if 'uri_schemes' in self.old_values:
            new_values = self.old_values['uri_schemes'].replace(' mailto', '').\
                    replace(' xmpp', '')
            app.config.set('uri_schemes', new_values)
        app.config.set('version', '0.12.0.1')

    def update_config_to_01211(self):
        if 'trayicon' in self.old_values:
            if self.old_values['trayicon'] == 'False':
                app.config.set('trayicon', 'never')
            else:
                app.config.set('trayicon', 'always')
        app.config.set('version', '0.12.1.1')

    def update_config_to_01212(self):
        for opt in ('ignore_unknown_contacts', 'send_os_info',
        'log_encrypted_sessions'):
            if opt in self.old_values:
                val = self.old_values[opt]
                for account in app.config.get_per('accounts'):
                    app.config.set_per('accounts', account, opt, val)
        app.config.set('version', '0.12.1.2')

    def update_config_to_01213(self):
        msgs = app.config.statusmsg_default
        for msg_name in app.config.get_per('statusmsg'):
            if msg_name in msgs:
                app.config.set_per('statusmsg', msg_name, 'activity',
                        msgs[msg_name][1])
                app.config.set_per('statusmsg', msg_name, 'subactivity',
                        msgs[msg_name][2])
                app.config.set_per('statusmsg', msg_name, 'activity_text',
                        msgs[msg_name][3])
                app.config.set_per('statusmsg', msg_name, 'mood',
                        msgs[msg_name][4])
                app.config.set_per('statusmsg', msg_name, 'mood_text',
                        msgs[msg_name][5])
        app.config.set('version', '0.12.1.3')

    def update_config_to_01214(self):
        for status in ['online', 'chat', 'away', 'xa', 'dnd', 'invisible',
        'offline']:
            if 'last_status_msg_' + status in self.old_values:
                app.config.add_per('statusmsg', '_last_' + status)
                app.config.set_per('statusmsg', '_last_' + status, 'message',
                        self.old_values['last_status_msg_' + status])
        app.config.set('version', '0.12.1.4')

    def update_config_to_01215(self):
        """
        Remove hardcoded ../data/sounds from config
        """
        dirs = ['../data', app.gajimpaths.data_root, app.DATA_DIR]
        if os.name != 'nt':
            dirs.append(os.path.expanduser('~/.gajim'))
        for evt in app.config.get_per('soundevents'):
            path = app.config.get_per('soundevents', evt, 'path')
            # absolute and relative passes are necessary
            path = helpers.strip_soundfile_path(path, dirs, abs=False)
            path = helpers.strip_soundfile_path(path, dirs, abs=True)
            app.config.set_per('soundevents', evt, 'path', path)
        app.config.set('version', '0.12.1.5')

    def update_config_to_01231(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
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
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.12.3.1')

    def update_config_from_0125(self):
        # All those functions need to be called for 0.12.5 to 0.13 transition
        self.update_config_to_01211()
        self.update_config_to_01213()
        self.update_config_to_01214()
        self.update_config_to_01215()
        self.update_config_to_01231()

    def update_config_to_01251(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    ALTER TABLE unread_messages
                    ADD shown BOOLEAN default 0;
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.12.5.1')

    def update_config_to_01252(self):
        if 'alwaysauth' in self.old_values:
            val = self.old_values['alwaysauth']
            for account in app.config.get_per('accounts'):
                app.config.set_per('accounts', account, 'autoauth', val)
        app.config.set('version', '0.12.5.2')

    def update_config_to_01253(self):
        if 'enable_zeroconf' in self.old_values:
            val = self.old_values['enable_zeroconf']
            for account in app.config.get_per('accounts'):
                if app.config.get_per('accounts', account, 'is_zeroconf'):
                    app.config.set_per('accounts', account, 'active', val)
                else:
                    app.config.set_per('accounts', account, 'active', True)
        app.config.set('version', '0.12.5.3')

    def update_config_to_01254(self):
        vals = {'inmsgcolor': ['#a34526', '#a40000'],
                'outmsgcolor': ['#164e6f', '#3465a4'],
                'restored_messages_color': ['grey', '#555753'],
                'statusmsgcolor': ['#1eaa1e', '#73d216'],
                'urlmsgcolor': ['#0000ff', '#204a87'],
                'gc_nicknames_colors': ['#a34526:#c000ff:#0012ff:#388a99:#045723:#7c7c7c:#ff8a00:#94452d:#244b5a:#32645a', '#4e9a06:#f57900:#ce5c00:#3465a4:#204a87:#75507b:#5c3566:#c17d11:#8f5902:#ef2929:#cc0000:#a40000']}
        for c in vals:
            if c not in self.old_values:
                continue
            val = self.old_values[c]
            if val == vals[c][0]:
                # We didn't change default value, so update it with new default
                app.config.set(c, vals[c][1])
        app.config.set('version', '0.12.5.4')

    def update_config_to_01255(self):
        vals = {'statusmsgcolor': ['#73d216', '#4e9a06'],
                'outmsgtxtcolor': ['#a2a2a2', '#555753']}
        for c in vals:
            if c not in self.old_values:
                continue
            val = self.old_values[c]
            if val == vals[c][0]:
                # We didn't change default value, so update it with new default
                app.config.set(c, vals[c][1])
        app.config.set('version', '0.12.5.5')

    def update_config_to_01256(self):
        vals = {'gc_nicknames_colors': ['#4e9a06:#f57900:#ce5c00:#3465a4:#204a87:#75507b:#5c3566:#c17d11:#8f5902:#ef2929:#cc0000:#a40000', '#f57900:#ce5c00:#204a87:#75507b:#5c3566:#c17d11:#8f5902:#ef2929:#cc0000:#a40000']}
        for c in vals:
            if c not in self.old_values:
                continue
            val = self.old_values[c]
            if val == vals[c][0]:
                # We didn't change default value, so update it with new default
                app.config.set(c, vals[c][1])
        app.config.set('version', '0.12.5.6')

    def update_config_to_01257(self):
        if 'iconset' in self.old_values:
            if self.old_values['iconset'] in ('nuvola', 'crystal', 'gossip',
            'simplebulb', 'stellar'):
                app.config.set('iconset', app.config.DEFAULT_ICONSET)
        app.config.set('version', '0.12.5.7')

    def update_config_to_01258(self):
        self.update_ft_proxies(to_remove=['proxy65.talkonaut.com',
                'proxy.jabber.org', 'proxy.netlab.cz', 'transfer.jabber.freenet.de',
                'proxy.jabber.cd.chalmers.se'], to_add=['proxy.eu.jabber.org',
                'proxy.jabber.ru', 'proxy.jabbim.cz'])
        app.config.set('version', '0.12.5.8')

    def update_config_to_013100(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    ALTER TABLE caps_cache
                    ADD last_seen INTEGER default %d;
                    ''' % int(time())
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.13.10.0')

    def update_config_to_013101(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    DROP INDEX IF EXISTS idx_logs_jid_id_kind;

                    CREATE INDEX IF NOT EXISTS
                    idx_logs_jid_id_time ON logs (jid_id, time DESC);
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.13.10.1')

    def update_config_to_013901(self):
        schemes = 'aaa:// aaas:// acap:// cap:// cid: crid:// data: dav: dict:// dns: fax: file:/ ftp:// geo: go: gopher:// h323: http:// https:// iax: icap:// im: imap:// info: ipp:// iris: iris.beep: iris.xpc: iris.xpcs: iris.lwz: ldap:// mid: modem: msrp:// msrps:// mtqp:// mupdate:// news: nfs:// nntp:// opaquelocktoken: pop:// pres: prospero:// rtsp:// service: shttp:// sip: sips: sms: snmp:// soap.beep:// soap.beeps:// tag: tel: telnet:// tftp:// thismessage:/ tip:// tv: urn:// vemmi:// xmlrpc.beep:// xmlrpc.beeps:// z39.50r:// z39.50s:// about: apt: cvs:// daap:// ed2k:// feed: fish:// git:// iax2: irc:// ircs:// ldaps:// magnet: mms:// rsync:// ssh:// svn:// sftp:// smb:// webcal://'
        app.config.set('uri_schemes', schemes)
        app.config.set('version', '0.13.90.1')

    def update_config_to_01401(self):
        if 'autodetect_browser_mailer' not in self.old_values or 'openwith' \
        not in self.old_values or \
        (self.old_values['autodetect_browser_mailer'] == False and \
        self.old_values['openwith'] != 'custom'):
            app.config.set('autodetect_browser_mailer', True)
            app.config.set('openwith', app.config.DEFAULT_OPENWITH)
        app.config.set('version', '0.14.0.1')

    def update_config_to_014900(self):
        if 'use_stun_server' in self.old_values and self.old_values[
        'use_stun_server'] and not self.old_values['stun_server']:
            app.config.set('use_stun_server', False)
        if os.name == 'nt':
            app.config.set('autodetect_browser_mailer', True)

    def update_config_to_01601(self):
        if 'last_mam_id' in self.old_values:
            last_mam_id = self.old_values['last_mam_id']
            for account in app.config.get_per('accounts'):
                app.config.set_per('accounts', account, 'last_mam_id',
                    last_mam_id)
        app.config.set('version', '0.16.0.1')

    def update_config_to_01641(self):
        for account in self.old_values['accounts'].keys():
            connection_types = self.old_values['accounts'][account][
            'connection_types'].split()
            if 'plain' in connection_types and len(connection_types) > 1:
                connection_types.remove('plain')
            app.config.set_per('accounts', account, 'connection_types',
                ' '.join(connection_types))
        app.config.set('version', '0.16.4.1')

    def update_config_to_016101(self):
        if 'video_input_device' in self.old_values:
            if self.old_values['video_input_device'] == 'autovideosrc ! videoscale ! ffmpegcolorspace':
                app.config.set('video_input_device', 'autovideosrc')
            if self.old_values['video_input_device'] == 'videotestsrc is-live=true ! video/x-raw-yuv,framerate=10/1':
                app.config.set('video_input_device', 'videotestsrc is-live=true ! video/x-raw,framerate=10/1')
        app.config.set('version', '0.16.10.1')

    def update_config_to_016102(self):
        for account in self.old_values['accounts'].keys():
            app.config.del_per('accounts', account, 'minimized_gc')

        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    ALTER TABLE logs ADD COLUMN 'additional_data' TEXT DEFAULT '{}';
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()

        app.config.set('version', '0.16.10.2')

    def update_config_to_016103(self):
        back = os.getcwd()
        os.chdir(logger.LOG_DB_FOLDER)
        con = sqlite.connect(logger.LOG_DB_FILE)
        os.chdir(back)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    ALTER TABLE logs ADD COLUMN 'stanza_id' TEXT;
                    ALTER TABLE logs ADD COLUMN 'mam_id' TEXT;
                    ALTER TABLE logs ADD COLUMN 'encryption' TEXT;
                    ALTER TABLE logs ADD COLUMN 'encryption_state' TEXT;
                    ALTER TABLE logs ADD COLUMN 'marker' INTEGER;
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            pass
        con.close()
        app.config.set('version', '0.16.10.3')

    def update_config_to_016104(self):
        app.config.set('emoticons_theme', 'noto-emoticons')
        app.config.set('version', '0.16.10.4')

    def update_config_to_016105(self):
        app.config.set('muc_restore_timeout', -1)
        app.config.set('restore_timeout', -1)
        app.config.set('version', '0.16.10.5')

    def update_config_to_016111(self):
        con = sqlite.connect(logger.CACHE_DB_PATH)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    ALTER TABLE roster_entry ADD COLUMN 'avatar_sha' TEXT;
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            log.exception('Error')
        con.close()
        app.config.set('version', '0.16.11.1')

    def update_config_to_016112(self):
        con = sqlite.connect(logger.LOG_DB_PATH)
        cur = con.cursor()
        try:
            cur.executescript(
                    '''
                    CREATE TABLE IF NOT EXISTS last_archive_message(
                        jid_id INTEGER PRIMARY KEY UNIQUE,
                        last_mam_id TEXT,
                        oldest_mam_timestamp TEXT,
                        last_muc_timestamp TEXT
                        );
                    '''
            )
            con.commit()
        except sqlite.OperationalError:
            log.exception('Error')
        con.close()
        app.config.set('version', '0.16.11.2')
