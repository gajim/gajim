# Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 James Newton <redshodan AT gmail.com>
#                    Brendan Taylor <whateley AT gmail.com>
#                    Tomasz Melcer <liori AT exroot.org>
#                    Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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

import os
import sys
import re
import logging
from pathlib import Path
from packaging.version import Version as V

from gi.repository import Gdk
from nbxmpp.util import text_to_color

from gajim.common import app
from gajim.common.i18n import _

log = logging.getLogger('gajim.c.optparser')


class OptionsParser:
    def __init__(self, filename):
        self.__filename = os.path.realpath(filename)
        self.old_values = {}    # values that are saved in the file and maybe
                                                        # no longer valid

    def read(self):
        try:
            fd = open(self.__filename, encoding='utf-8')
        except Exception:
            if os.path.exists(self.__filename):
                #we talk about a file
                print(_('Error: cannot open %s for reading') % self.__filename,
                    file=sys.stderr)
            return False

        new_version = app.config.get('version')
        new_version = new_version.split('+', 1)[0]
        seen = set()
        regex = re.compile(r"(?P<optname>[^.=]+)(?:(?:\.(?P<key>.+))?\.(?P<subname>[^.=]+))?\s=\s(?P<value>.*)")

        for line in fd:
            match = regex.match(line)
            if match is None:
                log.warning('Invalid configuration line, ignoring it: %s', line)
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
        if '+' in old_version:
            old_version = old_version.split('+', 1)[0]
        elif '-' in old_version:
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
        config_path = Path(self.__filename)
        tempfile = 'temp_%s' % config_path.name
        temp_filepath = config_path.parent / tempfile
        try:
            with open(str(temp_filepath), 'w', encoding='utf-8') as file:
                app.config.foreach(self.write_line, file)
        except IOError:
            log.exception('Failed to write config file')
            return False

        try:
            temp_filepath.replace(config_path)
        except Exception:
            log.exception('Failed to replace config file')
            return False

        log.info('Successful saved config file')
        return True

    def update_config(self, old_version, new_version):
        old = V(old_version)

        if old < V('0.16.4.1'):
            self.update_config_to_01641()
        if old < V('0.16.10.1'):
            self.update_config_to_016101()
        if old < V('0.16.10.2'):
            self.update_config_to_016102()
        if old < V('0.16.10.4'):
            self.update_config_to_016104()
        if old < V('0.16.10.5'):
            self.update_config_to_016105()
        if old < V('0.98.3'):
            self.update_config_to_0983()
        if old < V('1.1.93'):
            self.update_config_to_1193()
        if old < V('1.1.94'):
            self.update_config_to_1194()
        if old < V('1.1.95'):
            self.update_config_to_1195()

        app.config.set('version', new_version)

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

        app.config.set('version', '0.16.10.2')

    def update_config_to_016104(self):
        app.config.set('emoticons_theme', 'noto-emoticons')
        app.config.set('version', '0.16.10.4')

    def update_config_to_016105(self):
        app.config.set('muc_restore_timeout', -1)
        app.config.set('restore_timeout', -1)
        app.config.set('version', '0.16.10.5')

    def update_config_to_0983(self):
        for account in self.old_values['accounts'].keys():
            password = self.old_values['accounts'][account]['password']
            if password == "winvault:":
                app.config.set_per('accounts', account, 'password', 'keyring:')
            elif password == "libsecret:":
                app.config.set_per('accounts', account, 'password', '')
        app.config.set('version', '0.98.3')

    def update_config_to_1193(self):
        # add date to time_stamp, if user did not set a custom time_stamp
        if self.old_values['time_stamp'] == '[%X] ':
            app.config.set('time_stamp', '%x | %X  ')
        app.config.set('version', '1.1.93')

    def update_config_to_1194(self):
        # Delete all BOSH proxies
        proxies = self.old_values.get('proxies', [])
        for name in proxies:
            if self.old_values['proxies'][name]['type'] == 'bosh':
                app.config.del_per('proxies', name)
                for account in self.old_values['accounts']:
                    if self.old_values['accounts'][account]['proxy'] == name:
                        app.config.del_per('accounts', account, 'proxy')

        app.config.set('version', '1.1.94')

    def update_config_to_1195(self):
        # Add account color for every account
        for account in self.old_values['accounts'].keys():
            username = self.old_values['accounts'][account]['name']
            domain = self.old_values['accounts'][account]['hostname']
            if not (username is None or domain is None):
                account_string = '%s@%s' % (username, domain)
                # We cannot get the preferred theme at this point
                background = (1, 1, 1)
                col_r, col_g, col_b = text_to_color(account_string, background)
                rgba = Gdk.RGBA(red=col_r, green=col_g, blue=col_b)
                color = rgba.to_string()
                app.config.set_per('accounts', account, 'account_color', color)
        app.config.set('version', '1.1.95')
