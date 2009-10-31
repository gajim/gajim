# -*- coding:utf-8 -*-
## src/common/optparser.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
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
import locale
import re
from common import gajim
from common import helpers
from common import caps

import exceptions
try:
	import sqlite3 as sqlite # python 2.5
except ImportError:
	try:
		from pysqlite2 import dbapi2 as sqlite
	except ImportError:
		raise exceptions.PysqliteNotAvailable
import logger

class OptionsParser:
	def __init__(self, filename):
		self.__filename = filename
		self.old_values = {}	# values that are saved in the file and maybe
								# no longer valid

	def read(self):
		try:
			fd = open(self.__filename)
		except Exception:
			if os.path.exists(self.__filename):
				#we talk about a file
				print _('error: cannot open %s for reading') % self.__filename
			return False

		new_version = gajim.config.get('version')
		new_version = new_version.split('-', 1)[0]
		seen = set()
		regex = re.compile(r"(?P<optname>[^.]+)(?:(?:\.(?P<key>.+))?\.(?P<subname>[^.]+))?\s=\s(?P<value>.*)")

		for line in fd:
			try:
				line = line.decode('utf-8')
			except UnicodeDecodeError:
				line = line.decode(locale.getpreferredencoding())
			optname, key, subname, value = regex.match(line).groups()
			if key is None:
				self.old_values[optname] = value
				gajim.config.set(optname, value)
			else:
				if (optname, key) not in seen:
					gajim.config.add_per(optname, key)
					seen.add((optname, key))
				gajim.config.set_per(optname, key, subname, value)

		old_version = gajim.config.get('version')
		old_version = old_version.split('-', 1)[0]

		self.update_config(old_version, new_version)
		self.old_values = {} # clean mem

		fd.close()
		return True

	def write_line(self, fd, opt, parents, value):
		if value is None:
			return
		value = value[1]
		# convert to utf8 before writing to file if needed
		if isinstance(value, unicode):
			value = value.encode('utf-8')
		else:
			value = str(value)
		if isinstance(opt, unicode):
			opt = opt.encode('utf-8')
		s = ''
		if parents:
			if len(parents) == 1:
				return
			for p in parents:
				if isinstance(p, unicode):
					p = p.encode('utf-8')
				s += p + '.'
		s += opt
		fd.write(s + ' = ' + value + '\n')

	def write(self):
		(base_dir, filename) = os.path.split(self.__filename)
		self.__tempfile = os.path.join(base_dir, '.' + filename)
		try:
			f = open(self.__tempfile, 'w')
		except IOError, e:
			return str(e)
		try:
			gajim.config.foreach(self.write_line, f)
		except IOError, e:
			return str(e)
		f.close()
		if os.path.exists(self.__filename):
			# win32 needs this
			try:
				os.remove(self.__filename)
			except Exception:
				pass
		try:
			os.rename(self.__tempfile, self.__filename)
		except IOError, e:
			return str(e)
		os.chmod(self.__filename, 0600)

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

		gajim.logger.init_vars()
		gajim.config.set('version', new_version)

		caps.capscache.initialize_from_db()

	def update_config_x_to_09(self):
		# Var name that changed:
		# avatar_width /height -> chat_avatar_width / height
		if 'avatar_width' in self.old_values:
			gajim.config.set('chat_avatar_width', self.old_values['avatar_width'])
		if 'avatar_height' in self.old_values:
			gajim.config.set('chat_avatar_height', self.old_values['avatar_height'])
		if 'use_dbus' in self.old_values:
			gajim.config.set('remote_control', self.old_values['use_dbus'])
		# always_compact_view -> always_compact_view_chat / _gc
		if 'always_compact_view' in self.old_values:
			gajim.config.set('always_compact_view_chat',
				self.old_values['always_compact_view'])
			gajim.config.set('always_compact_view_gc',
				self.old_values['always_compact_view'])
		# new theme: grocery, plain
		d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
			'accountfontattrs', 'grouptextcolor', 'groupbgcolor', 'groupfont',
			'groupfontattrs', 'contacttextcolor', 'contactbgcolor', 'contactfont',
			'contactfontattrs', 'bannertextcolor', 'bannerbgcolor', 'bannerfont',
			'bannerfontattrs']
		for theme_name in (_('grocery'), _('default')):
			if theme_name not in gajim.config.get_per('themes'):
				gajim.config.add_per('themes', theme_name)
				theme = gajim.config.themes_default[theme_name]
				for o in d:
					gajim.config.set_per('themes', theme_name, o, theme[d.index(o)])
		# Remove cyan theme if it's not the current theme
		if 'cyan' in gajim.config.get_per('themes'):
			gajim.config.del_per('themes', 'cyan')
		if _('cyan') in gajim.config.get_per('themes'):
			gajim.config.del_per('themes', _('cyan'))
		# If we removed our roster_theme, choose the default green one or another
		# one if doesn't exists in config
		if gajim.config.get('roster_theme') not in gajim.config.get_per('themes'):
			theme = _('green')
			if theme not in gajim.config.get_per('themes'):
				theme = gajim.config.get_per('themes')[0]
			gajim.config.set('roster_theme', theme)
		# new proxies in accounts.name.file_transfer_proxies
		for account in gajim.config.get_per('accounts'):
			proxies = gajim.config.get_per('accounts', account,
				'file_transfer_proxies')
			if proxies.find('proxy.netlab.cz') < 0:
				proxies += ', ' + 'proxy.netlab.cz'
			gajim.config.set_per('accounts', account, 'file_transfer_proxies',
				proxies)

		gajim.config.set('version', '0.9')

	def assert_unread_msgs_table_exists(self):
		'''create table unread_messages if there is no such table'''
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
			gajim.logger.init_vars()
		except sqlite.OperationalError:
			pass
		con.close()

	def update_config_09_to_010(self):
		if 'usetabbedchat' in self.old_values and not \
		self.old_values['usetabbedchat']:
			gajim.config.set('one_message_window', 'never')
		if 'autodetect_browser_mailer' in self.old_values and \
		self.old_values['autodetect_browser_mailer'] is True:
			gajim.config.set('autodetect_browser_mailer', False)
		if 'useemoticons' in self.old_values and \
		not self.old_values['useemoticons']:
			gajim.config.set('emoticons_theme', '')
		if 'always_compact_view_chat' in self.old_values and \
		self.old_values['always_compact_view_chat'] != 'False':
			gajim.config.set('always_hide_chat_buttons', True)
		if 'always_compact_view_gc' in self.old_values and \
		self.old_values['always_compact_view_gc'] != 'False':
			gajim.config.set('always_hide_groupchat_buttons', True)

		for account in gajim.config.get_per('accounts'):
			proxies_str = gajim.config.get_per('accounts', account,
				'file_transfer_proxies')
			proxies = proxies_str.split(',')
			for i in range(0, len(proxies)):
				proxies[i] = proxies[i].strip()
			for wrong_proxy in ('proxy65.jabber.autocom.pl',
				'proxy65.jabber.ccc.de'):
				if wrong_proxy in proxies:
					proxies.remove(wrong_proxy)
			if not 'transfer.jabber.freenet.de' in proxies:
				proxies.append('transfer.jabber.freenet.de')
			proxies_str = ', '.join(proxies)
			gajim.config.set_per('accounts', account, 'file_transfer_proxies',
				proxies_str)
		# create unread_messages table if needed
		self.assert_unread_msgs_table_exists()

		gajim.config.set('version', '0.10')

	def update_config_to_01011(self):
		if 'print_status_in_muc' in self.old_values and \
			self.old_values['print_status_in_muc'] in (True, False):
			gajim.config.set('print_status_in_muc', 'in_and_out')
		gajim.config.set('version', '0.10.1.1')

	def update_config_to_01012(self):
		# See [6456]
		if 'emoticons_theme' in self.old_values and \
			self.old_values['emoticons_theme'] == 'Disabled':
			gajim.config.set('emoticons_theme', '')
		gajim.config.set('version', '0.10.1.2')

	def update_config_to_01013(self):
		'''create table transports_cache if there is no such table'''
		#FIXME see #2812
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
		gajim.config.set('version', '0.10.1.3')

	def update_config_to_01014(self):
		'''apply indeces to the logs database'''
		print _('migrating logs database to indices')
		#FIXME see #2812
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
		gajim.config.set('version', '0.10.1.4')

	def update_config_to_01015(self):
		'''clean show values in logs database'''
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
		gajim.config.set('version', '0.10.1.5')

	def update_config_to_01016(self):
		'''#2494 : Now we play gc_received_message sound even if
		notify_on_all_muc_messages is false. Keep precedent behaviour.'''
		if 'notify_on_all_muc_messages' in self.old_values and \
		self.old_values['notify_on_all_muc_messages'] == 'False' and \
		gajim.config.get_per('soundevents', 'muc_message_received', 'enabled'):
			gajim.config.set_per('soundevents',\
				'muc_message_received', 'enabled', False)
		gajim.config.set('version', '0.10.1.6')

	def update_config_to_01017(self):
		'''trayicon_notification_on_new_messages ->
		trayicon_notification_on_events '''
		if 'trayicon_notification_on_new_messages' in self.old_values:
			gajim.config.set('trayicon_notification_on_events',
				self.old_values['trayicon_notification_on_new_messages'])
		gajim.config.set('version', '0.10.1.7')

	def update_config_to_01018(self):
		'''chat_state_notifications -> outgoing_chat_state_notifications'''
		if 'chat_state_notifications' in self.old_values:
			gajim.config.set('outgoing_chat_state_notifications',
				self.old_values['chat_state_notifications'])
		gajim.config.set('version', '0.10.1.8')

	def update_config_to_01101(self):
		'''fill time_stamp from before_time and after_time'''
		if 'before_time' in self.old_values:
			gajim.config.set('time_stamp', '%s%%X%s ' % (
				self.old_values['before_time'], self.old_values['after_time']))
		gajim.config.set('version', '0.11.0.1')

	def update_config_to_01102(self):
		'''fill time_stamp from before_time and after_time'''
		if 'ft_override_host_to_send' in self.old_values:
			gajim.config.set('ft_add_hosts_to_send',
				self.old_values['ft_override_host_to_send'])
		gajim.config.set('version', '0.11.0.2')

	def update_config_to_01111(self):
		'''always_hide_chatbuttons -> compact_view'''
		if 'always_hide_groupchat_buttons' in self.old_values and \
		'always_hide_chat_buttons' in self.old_values:
			gajim.config.set('compact_view', self.old_values['always_hide_groupchat_buttons'] and \
			self.old_values['always_hide_chat_buttons'])
		gajim.config.set('version', '0.11.1.1')

	def update_config_to_01112(self):
		'''gtk+ theme is renamed to default'''
		if 'roster_theme' in self.old_values and \
		self.old_values['roster_theme'] == 'gtk+':
			gajim.config.set('roster_theme', _('default'))
		gajim.config.set('version', '0.11.1.2')

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
		gajim.config.set('version', '0.11.1.3')

	def update_config_to_01114(self):
		# add default theme if it doesn't exist
		d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
			'accountfontattrs', 'grouptextcolor', 'groupbgcolor', 'groupfont',
			'groupfontattrs', 'contacttextcolor', 'contactbgcolor', 'contactfont',
			'contactfontattrs', 'bannertextcolor', 'bannerbgcolor', 'bannerfont',
			'bannerfontattrs']
		theme_name = _('default')
		if theme_name not in gajim.config.get_per('themes'):
			gajim.config.add_per('themes', theme_name)
			if gajim.config.get_per('themes', 'gtk+'):
				# copy from old gtk+ theme
				for o in d:
					val = gajim.config.get_per('themes', 'gtk+', o)
					gajim.config.set_per('themes', theme_name, o, val)
				gajim.config.del_per('themes', 'gtk+')
			else:
				# copy from default theme
				theme = gajim.config.themes_default[theme_name]
				for o in d:
					gajim.config.set_per('themes', theme_name, o, theme[d.index(o)])
		gajim.config.set('version', '0.11.1.4')

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
		gajim.config.set('version', '0.11.1.5')

	def update_config_to_01121(self):
		# remove old unencrypted secrets file
		from common.configpaths import gajimpaths

		new_file = gajimpaths['SECRETS_FILE']

		old_file = os.path.dirname(new_file) + '/secrets'

		if os.path.exists(old_file):
			os.remove(old_file)

		gajim.config.set('version', '0.11.2.1')

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
		gajim.config.set('version', '0.11.4.1')

	def update_config_to_01142(self):
		'''next_message_received sound event is splittedin 2 events'''
		gajim.config.add_per('soundevents', 'next_message_received_focused')
		gajim.config.add_per('soundevents', 'next_message_received_unfocused')
		if gajim.config.get_per('soundevents', 'next_message_received'):
			enabled = gajim.config.get_per('soundevents', 'next_message_received',
				'enabled')
			path = gajim.config.get_per('soundevents', 'next_message_received',
				'path')
			gajim.config.del_per('soundevents', 'next_message_received')
			gajim.config.set_per('soundevents', 'next_message_received_focused',
				'enabled', enabled)
			gajim.config.set_per('soundevents', 'next_message_received_focused',
				'path', path)
		gajim.config.set('version', '0.11.1.2')

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
		gajim.config.set('version', '0.11.4.3')

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
		except sqlite.OperationalError, e:
			pass
		con.close()
		gajim.config.set('version', '0.11.4.4')

	def update_config_to_01201(self):
		if 'uri_schemes' in self.old_values:
			new_values = self.old_values['uri_schemes'].replace(' mailto', '').\
				replace(' xmpp', '')
			gajim.config.set('uri_schemes', new_values)
		gajim.config.set('version', '0.12.0.1')

	def update_config_to_01211(self):
		if 'trayicon' in self.old_values:
			if self.old_values['trayicon'] == 'False':
				gajim.config.set('trayicon', 'never')
			else:
				gajim.config.set('trayicon', 'always')
		gajim.config.set('version', '0.12.1.1')

	def update_config_to_01212(self):
		for opt in ('ignore_unknown_contacts', 'send_os_info',
		'log_encrypted_sessions'):
			if opt in self.old_values:
				val = self.old_values[opt]
				for account in gajim.config.get_per('accounts'):
					gajim.config.set_per('accounts', account, opt, val)
		gajim.config.set('version', '0.12.1.2')

	def update_config_to_01213(self):
		msgs = gajim.config.statusmsg_default
		for msg_name in gajim.config.get_per('statusmsg'):
			if msg_name in msgs:
				gajim.config.set_per('statusmsg', msg_name, 'activity',
					msgs[msg_name][1])
				gajim.config.set_per('statusmsg', msg_name, 'subactivity',
					msgs[msg_name][2])
				gajim.config.set_per('statusmsg', msg_name, 'activity_text',
					msgs[msg_name][3])
				gajim.config.set_per('statusmsg', msg_name, 'mood',
					msgs[msg_name][4])
				gajim.config.set_per('statusmsg', msg_name, 'mood_text',
					msgs[msg_name][5])
		gajim.config.set('version', '0.12.1.3')

	def update_config_to_01214(self):
		for status in ['online', 'chat', 'away', 'xa', 'dnd', 'invisible',
		'offline']:
			if 'last_status_msg_' + status in self.old_values:
				gajim.config.add_per('statusmsg', '_last_' + status)
				gajim.config.set_per('statusmsg', '_last_' + status, 'message',
					self.old_values['last_status_msg_' + status])
		gajim.config.set('version', '0.12.1.4')

	def update_config_to_01215(self):
		'''Remove hardcoded ../data/sounds from config'''
		dirs = ('../data', gajim.gajimpaths.root, gajim.DATA_DIR)
		for evt in gajim.config.get_per('soundevents'):
			path = gajim.config.get_per('soundevents', evt ,'path')
			# absolute and relative passes are necessary
			path = helpers.strip_soundfile_path(path, dirs, abs=False)
			path = helpers.strip_soundfile_path(path, dirs, abs=True)
			gajim.config.set_per('soundevents', evt, 'path', path)
		gajim.config.set('version', '0.12.1.5')

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
		gajim.config.set('version', '0.12.3.1')

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
		gajim.config.set('version', '0.12.5.1')

	def update_config_to_01252(self):
		if 'alwaysauth' in self.old_values:
			val = self.old_values['alwaysauth']
			for account in gajim.config.get_per('accounts'):
				gajim.config.set_per('accounts', account, 'autoauth', val)
		gajim.config.set('version', '0.12.5.2')

	def update_config_to_01253(self):
		if 'enable_zeroconf' in self.old_values:
			val = self.old_values['enable_zeroconf']
			for account in gajim.config.get_per('accounts'):
				if gajim.config.get_per('accounts', account, 'is_zeroconf'):
					gajim.config.set_per('accounts', account, 'active', val)
				else:
					gajim.config.set_per('accounts', account, 'active', True)
		gajim.config.set('version', '0.12.5.3')

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
				gajim.config.set(c, vals[c][1])
		gajim.config.set('version', '0.12.5.4')

	def update_config_to_01255(self):
		vals = {'statusmsgcolor': ['#73d216', '#4e9a06'],
			'outmsgtxtcolor': ['#a2a2a2', '#555753']}
		for c in vals:
			if c not in self.old_values:
				continue
			val = self.old_values[c]
			if val == vals[c][0]:
				# We didn't change default value, so update it with new default
				gajim.config.set(c, vals[c][1])
		gajim.config.set('version', '0.12.5.5')

	def update_config_to_01256(self):
		vals = {'gc_nicknames_colors': ['#4e9a06:#f57900:#ce5c00:#3465a4:#204a87:#75507b:#5c3566:#c17d11:#8f5902:#ef2929:#cc0000:#a40000', '#f57900:#ce5c00:#204a87:#75507b:#5c3566:#c17d11:#8f5902:#ef2929:#cc0000:#a40000']}
		for c in vals:
			if c not in self.old_values:
				continue
			val = self.old_values[c]
			if val == vals[c][0]:
				# We didn't change default value, so update it with new default
				gajim.config.set(c, vals[c][1])
		gajim.config.set('version', '0.12.5.6')

	def update_config_to_01257(self):
		if 'iconset' in self.old_values:
			if self.old_values['iconset'] in ('nuvola', 'crystal', 'gossip',
			'simplebulb', 'stellar'):
				gajim.config.set('iconset', gajim.config.DEFAULT_ICONSET)
		gajim.config.set('version', '0.12.5.7')
# vim: se ts=3:
