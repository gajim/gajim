#!/bin/sh
''':'
exec python -OOt "$0" ${1+"$@"}
' '''
##	gajim.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
		
import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import pango
import gobject
import os
import sre
import signal
import common.sleepy
import check_for_new_version
import sys
import getopt

from common import gajim
from common import connection
from common import i18n
i18n.init()
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

from common import optparser

profile = ''
try:
       opts, args = getopt.getopt(sys.argv[1:], "hp:", [ "help", "profile=" ])
except getopt.error, msg:
       print msg
       print "for help use --help"
       sys.exit(2)
for o, a in opts:
       if o in ("-h", "--help"):
               print "gajim [--help] [--profile name]"
               sys.exit(0)
       elif o in ("-p", "--profile"): # gajim --profile name
               profile = a

config_name = "~/.gajim/config"
if profile:
       config_name += ".%s" % profile

parser = optparser.OptionsParser(config_name)

try:
	import winsound # windows-only built-in module for playing wav
except ImportError:
	pass

class User:
	'''Information concerning each users'''
	def __init__(self, *args):
		if len(args) == 0:
			self.jid = ''
			self.name = ''
			self.groups = []
			self.show = ''
			self.status = ''
			self.sub = ''
			self.ask = ''
			self.resource = ''
			self.priority = 1
			self.keyID = ''
		elif len(args) == 10:
			self.jid = args[0]
			self.name = args[1]
			self.groups = args[2]
			self.show = args[3]
			self.status = args[4]
			self.sub = args[5]
			self.ask = args[6]
			self.resource = args[7]
			self.priority = args[8]
			self.keyID = args[9]
		else: raise TypeError, _('bad arguments')

import roster_window
import systray
import dialogs
import config

GTKGUI_GLADE = 'gtkgui.glade'


class Interface:
	def launch_browser_mailer(self, kind, url):
		#kind = 'url' or 'mail'
		if gajim.config.get('openwith') == 'gnome-open':
			app = 'gnome-open'
			args = ['gnome-open']
			args.append(url)
		elif gajim.config.get('openwith') == 'kfmclient exec':
			app = 'kfmclient'
			args = ['kfmclient', 'exec']
		elif gajim.config.get('openwith') == 'custom':
			if kind == 'url':
				conf = gajim.config.get('custombrowser')
			if kind == 'mail':
				conf = gajim.config.get('custommailapp')
			if conf == '': # if no app is configured
				return
			args = conf.split()
			app = args[0]
		args.append(url)
		try:
			if os.name == 'posix':
				os.spawnvp(os.P_NOWAIT, app, args)
			else:
				os.spawnv(os.P_NOWAIT, app, args)
		except:
			pass

	def play_timeout(self, pid):
		pidp, r = os.waitpid(pid, os.WNOHANG)
		return False

	def play_sound(self, event):
		if not gajim.config.get('sounds_on'):
			return
		path_to_soundfile = gajim.config.get_per('soundevents', event, 'path')
		if not os.path.exists(path_to_soundfile):
			return
		if os.name  == 'nt':
			winsound.PlaySound(path_to_soundfile, \
									winsound.SND_FILENAME|winsound.SND_ASYNC)
		elif os.name == 'posix':
			if gajim.config.get('soundplayer') == '':
				return
			argv = gajim.config.get('soundplayer').split()
			argv.append(path_to_soundfile)
			pid = os.spawnvp(os.P_NOWAIT, argv[0], argv)
			pidp, r = os.waitpid(pid, os.WNOHANG)
			if pidp == 0:
				gobject.timeout_add(10000, self.play_timeout, pid)

	def handle_event_roster(self, account, data):
		#('ROSTER', account, array)
		self.roster.mklists(data, account)
		self.roster.draw_roster()
	
	def handle_event_warning(self, unused, msg):
		dialogs.Warning_dialog(msg)
	
	def handle_event_error(self, unused, msg):
		dialogs.Error_dialog(msg)
	
	def handle_event_error_answer(self, account, array):
		#('ERROR_ANSWER', account, (jid_from. errmsg, errcode))
		jid_from = array[0]
		if jid_from in self.windows[account]['gc']:
			self.windows[account]['gc'][jid_from].print_conversation(
				'Error %s: %s' % (array[2], array[1]), jid_from)

	def allow_notif(self, account):
		self.allow_notifications[account] = True

	def handle_event_status(self, account, status): # OUR status
		#('STATUS', account, status)
		if status != 'offline':
			gobject.timeout_add(30000, self.allow_notif, account)
		self.roster.on_status_changed(account, status)
	
	def handle_event_notify(self, account, array):
		#('NOTIFY', account, (jid, status, message, resource, priority, keyID, 
		# role, affiliation, real_jid, reason, actor, statusCode))
		statuss = ['offline', 'error', 'online', 'chat', 'away', 'xa', 'dnd', 'invisible']
		old_show = 0
		new_show = statuss.index(array[1])
		jid = array[0].split('/')[0]
		keyID = array[5]
		resource = array[3]
		if not resource:
			resource = ''
		priority = array[4]
		if jid.find('@') <= 0:
			#It must be an agent
			ji = jid.replace('@', '')
		else:
			ji = jid
		#Update user
		if self.roster.contacts[account].has_key(ji):
			luser = self.roster.contacts[account][ji]
			user1 = None
			resources = []
			for u in luser:
				resources.append(u.resource)
				if u.resource == resource:
					user1 = u
					break
			if user1:
				if user1.show in statuss:
					old_show = statuss.index(user1.show)
			else:
				user1 = self.roster.contacts[account][ji][0]
				if user1.show in statuss:
					old_show = statuss.index(user1.show)
				if (resources != [''] and (len(luser) != 1 or 
					luser[0].show != 'offline')) and not jid.find('@') <= 0:
					old_show = 0
					user1 = User(user1.jid, user1.name, user1.groups, user1.show, \
					user1.status, user1.sub, user1.ask, user1.resource, \
						user1.priority, user1.keyID)
					luser.append(user1)
				user1.resource = resource
			if user1.jid.find('@') > 0 and len(luser) == 1: # It's not an agent
				if old_show == 0 and new_show > 1:
					if not user1.jid in self.roster.newly_added[account]:
						self.roster.newly_added[account].append(user1.jid)
					if user1.jid in self.roster.to_be_removed[account]:
						self.roster.to_be_removed[account].remove(user1.jid)
					gobject.timeout_add(5000, self.roster.remove_newly_added, \
						user1.jid, account)
				if old_show > 1 and new_show == 0 and gajim.connections[account].\
					connected > 1:
					if not user1.jid in self.roster.to_be_removed[account]:
						self.roster.to_be_removed[account].append(user1.jid)
					if user1.jid in self.roster.newly_added[account]:
						self.roster.newly_added[account].remove(user1.jid)
					self.roster.draw_contact(user1.jid, account)
					if not self.queues[account].has_key(jid):
						gobject.timeout_add(5000, self.roster.really_remove_user, \
							user1, account)
			user1.show = array[1]
			user1.status = array[2]
			user1.priority = priority
			user1.keyID = keyID
		if jid.find('@') <= 0:
			#It must be an agent
			if self.roster.contacts[account].has_key(ji):
				#Update existing iter
				self.roster.draw_contact(ji, account)
		elif self.roster.contacts[account].has_key(ji):
			#It isn't an agent
			self.roster.chg_user_status(user1, array[1], array[2], account)
			#play sound
			if old_show < 2 and new_show > 1:
				if gajim.config.get_per('soundevents', 'contact_connected',
												'enabled'):
					self.play_sound('contact_connected')
				if not self.windows[account]['chats'].has_key(jid) and \
					not self.queues[account].has_key(jid) and \
					gajim.config.get('notify_on_online') and \
					self.allow_notifications[account]:
					show_notification = False
					# check OUR status and if we allow notifications for that status
					if gajim.config.get('autopopupaway'): # always notify
						show_notification = True
					elif gajim.connections[account].connected in (2, 3): # we're online or chat
						show_notification = True
					if show_notification:
						instance = dialogs.Popup_notification_window(self,
														'Contact signed in', jid, account)
						self.roster.popup_notification_windows.append(instance)
						
			elif old_show > 1 and new_show < 2:
				if gajim.config.get_per('soundevents', 'contact_disconnected',
												'enabled'):
					self.play_sound('contact_disconnected')
				if not self.windows[account]['chats'].has_key(jid) and \
					not self.queues[account].has_key(jid) and \
					gajim.config.get('notify_on_offline'):
					show_notification = False
					# check OUR status and if we allow notifications for that status
					if gajim.config.get('autopopupaway'): # always notify
						show_notification = True
					elif gajim.connections[account].connected in (2, 3): # we're online or chat
						show_notification = True
					if show_notification:
						instance = dialogs.Popup_notification_window(self,
											 		'Contact signed out', jid, account)
						self.roster.popup_notification_windows.append(instance)
				
		elif self.windows[account]['gc'].has_key(ji):
			#it is a groupchat presence
			self.windows[account]['gc'][ji].chg_user_status(ji, resource, \
				array[1], array[2], array[6], array[7], array[8], array[9], \
				array[10], array[11], account)

	def handle_event_msg(self, account, array):
		#('MSG', account, (user, msg, time))
		jid = array[0].split('/')[0]
		if jid.find('@') <= 0:
			jid = jid.replace('@', '')
		if gajim.config.get('ignore_unknown_contacts') and \
			not self.roster.contacts[account].has_key(jid):
			return

		first = False
		if not self.windows[account]['chats'].has_key(jid) and \
						not self.queues[account].has_key(jid):
			first = True
			if gajim.config.get('notify_on_new_message'):
				show_notification = False
				# check OUR status and if we allow notifications for that status
				if gajim.config.get('autopopupaway'): # always show notification
					show_notification = True
				elif gajim.connections[account].connected in (2, 3): # we're online or chat
					show_notification = True
				if show_notification:
					instance = dialogs.Popup_notification_window(self,
																	'New Message', jid, account)
					self.roster.popup_notification_windows.append(instance)
		self.roster.on_message(jid, array[1], array[2], account)
		if gajim.config.get_per('soundevents', 'first_message_received', \
			'enabled') and first:
			self.play_sound('first_message_received')
		if gajim.config.get_per('soundevents', 'next_message_received', \
			'enabled') and not first:
			self.play_sound('next_message_received')
		
	def handle_event_msgerror(self, account, array):
		#('MSGERROR', account, (jid, error_code, error_msg, msg, time))
		jid = array[0].split('/')[0]
		if jid in self.windows[account]['gc']:
			self.windows[account]['gc'][jid].print_conversation('Error %s: %s' % \
				(array[1], array[2]), jid)
			if self.windows[account]['gc'][jid].get_active_jid() == jid:
				self.windows[account]['gc'][jid].set_subject(jid, \
					self.windows[account]['gc'][jid].subjects[jid])
			return
		if jid.find('@') <= 0:
			jid = jid.replace('@', '')
		self.roster.on_message(jid, _('error while sending') + \
			' \"%s\" ( %s )' % (array[3], array[2]), array[4], account)
		
	def handle_event_msgsent(self, account, array):
		#('MSG', account, (jid, msg, keyID))
		if gajim.config.get_per('soundevents', 'message_sent', 'enabled'):
			self.play_sound('message_sent')
		
	def handle_event_subscribe(self, account, array):
		#('SUBSCRIBE', account, (jid, text))
		dialogs.subscription_request_window(self, array[0], array[1], account)

	def handle_event_subscribed(self, account, array):
		#('SUBSCRIBED', account, (jid, resource))
		jid = array[0]
		if self.roster.contacts[account].has_key(jid):
			u = self.roster.contacts[account][jid][0]
			u.resource = array[1]
			self.roster.remove_user(u, account)
			if 'not in the roster' in u.groups:
				u.groups.remove('not in the roster')
			if len(u.groups) == 0:
				u.groups = ['General']
			self.roster.add_user_to_roster(u.jid, account)
			gajim.connections[account].update_user(u.jid, u.name, u.groups)
		else:
			user1 = User(jid, jid, ['General'], 'online', \
				'online', 'to', '', array[1], 0, '')
			self.roster.contacts[account][jid] = [user1]
			self.roster.add_user_to_roster(jid, account)
		dialogs.Information_dialog(_('You are now authorized by %s') % jid)

	def handle_event_unsubscribed(self, account, jid):
		dialogs.Information_dialog(_('You are now unsubscribed by %s') % jid)

	def handle_event_agent_info(self, account, array):
		#('AGENT_INFO', account, (agent, identities, features, items))
		if self.windows[account].has_key('disco'):
			self.windows[account]['disco'].agent_info(array[0], array[1], \
				array[2], array[3])

	def handle_event_register_agent_info(self, account, array):
		#('AGENT_INFO', account, (agent, infos))
		if array[1].has_key('instructions'):
			config.Service_registration_window(array[0], array[1], self, account)
		else:
			dialogs.Error_dialog(_('error contacting %s') % array[0])

	def handle_event_agent_info_items(self, account, array):
		#('AGENT_INFO_ITEMS', account, (agent, node, items))
		if self.windows[account].has_key('disco'):
			self.windows[account]['disco'].agent_info_items(array[0], array[1], 
				array[2])

	def handle_event_agent_info_info(self, account, array):
		#('AGENT_INFO_INFO', account, (agent, node, identities, features))
		if self.windows[account].has_key('disco'):
			self.windows[account]['disco'].agent_info_info(array[0], array[1], \
				array[2], array[3])

	def handle_event_acc_ok(self, account, array):
		#('ACC_OK', account, (name, config))
		name = array[0]
		gajim.config.add_per('accounts', name)
		for opt in array[1]:
			gajim.config.set_per('accounts', name, opt, array[1][opt])
		if self.windows.has_key('account_modification'):
			self.windows['account_modification'].account_is_ok(array[0])
		self.windows[name] = {'infos': {}, 'chats': {}, 'gc': {}, 'gc_config': {}}
		self.queues[name] = {}
		gajim.connections[name].connected = 0
		self.nicks[name] = array[1]['name']
		self.allow_notifications[name] = False
		self.roster.groups[name] = {}
		self.roster.contacts[name] = {}
		self.roster.newly_added[name] = []
		self.roster.to_be_removed[name] = []
		self.sleeper_state[name] = 0
		if self.windows.has_key('accounts'):
			self.windows['accounts'].init_accounts()
		self.roster.draw_roster()

	def handle_event_quit(self, p1, p2):
		self.roster.quit_gtkgui_plugin()

	def handle_event_myvcard(self, account, array):
		nick = ''
		if array.has_key('NICKNAME'):
			nick = array['NICKNAME']
		if nick == '':
			nick = gajim.config.get_per('accounts', account, 'name')
		self.nicks[account] = nick

	def handle_event_vcard(self, account, array):
		if self.windows[account]['infos'].has_key(array['jid']):
			self.windows[account]['infos'][array['jid']].set_values(array)

	def handle_event_os_info(self, account, array):
		if self.windows[account]['infos'].has_key(array[0]):
			self.windows[account]['infos'][array[0]].set_os_info(array[1], \
				array[2], array[3])

	def handle_event_gc_msg(self, account, array):
		#('GC_MSG', account, (jid, msg, time))
		jids = array[0].split('/')
		jid = jids[0]
		if not self.windows[account]['gc'].has_key(jid):
			return
		if len(jids) == 1:
			#message from server
			self.windows[account]['gc'][jid].print_conversation(array[1], jid, \
				tim = array[2])
		else:
			#message from someone
			self.windows[account]['gc'][jid].print_conversation(array[1], jid, \
				jids[1], array[2])

	def handle_event_gc_subject(self, account, array):
		#('GC_SUBJECT', account, (jid, subject))
		jids = array[0].split('/')
		jid = jids[0]
		if not self.windows[account]['gc'].has_key(jid):
			return
		self.windows[account]['gc'][jid].set_subject(jid, array[1])
		if len(jids) > 1:
			self.windows[account]['gc'][jid].print_conversation(\
				'%s has set the subject to %s' % (jids[1], array[1]), jid)

	def handle_event_gc_config(self, account, array):
		#('GC_CONFIG', account, (jid, config))  config is a dict
		jid = array[0].split('/')[0]
		if not self.windows[account]['gc_config'].has_key(jid):
			self.windows[account]['gc_config'][jid] = \
			config.Groupchat_config_window(self, account, jid, array[1])

	def handle_event_bad_passphrase(self, account, array):
		dialogs.Warning_dialog(_('Your GPG passphrase is wrong, so you are connected without your GPG key.'))

	def handle_event_roster_info(self, account, array):
		#('ROSTER_INFO', account, (jid, name, sub, ask, groups))
		jid = array[0]
		if not self.roster.contacts[account].has_key(jid):
			return
		users = self.roster.contacts[account][jid]
		if not (array[2] or array[3]):
			self.roster.remove_user(users[0], account)
			del self.roster.contacts[account][jid]
			#TODO if it was the only one in its group, remove the group
			return
		for user in users:
			name = array[1]
			if name:
				user.name = name
			user.sub = array[2]
			user.ask = array[3]
			if array[4]:
				user.groups = array[4]
		self.roster.draw_contact(jid, account)

	def read_sleepy(self):	
		'''Check if we are idle'''
		if not self.sleeper.poll():
			return True # renew timeout (loop for ever)
		state = self.sleeper.getState()
		for account in gajim.connections:
			if not self.sleeper_state[account]:
				continue
			if state == common.sleepy.STATE_AWAKE and \
				self.sleeper_state[account] > 1:
				#we go online
				gajim.connections[account].change_status('online', 'Online')
				self.sleeper_state[account] = 1
			elif state == common.sleepy.STATE_AWAY and \
				self.sleeper_state[account] == 1 and \
				gajim.config.get('autoaway'):
				#we go away
				gajim.connections[account].change_status('away', 'auto away (idle)')
				self.sleeper_state[account] = 2
			elif state == common.sleepy.STATE_XAWAY and (\
				self.sleeper_state[account] == 2 or \
				self.sleeper_state[account] == 1) and \
				gajim.config.get('autoxa'):
				#we go extended away
				gajim.connections[account].change_status('xa', 'auto away (idle)')
				self.sleeper_state[account] = 3
		return True # renew timeout (loop for ever)

	def autoconnect(self):
		'''auto connect at startup'''
		ask_message = 0
		for a in gajim.connections:
			if gajim.config.get_per('accounts', a, 'autoconnect'):
				ask_message = 1
				break
		if ask_message:
			message = self.roster.get_status_message('online')
			if message == -1:
				return
			for a in gajim.connections:
				if gajim.config.get_per('accounts', a, 'autoconnect'):
					self.roster.send_status(a, 'online', message)
		return False

	def show_systray(self):
		self.systray.show_icon()
		self.systray_enabled = True

	def hide_systray(self):
		self.systray.hide_icon()
		self.systray_enabled = False
	
	def image_is_ok(self, image):
		if not os.path.exists(image):
			return False
		img = gtk.Image()
		try:
			img.set_from_file(image)
		except:
			return True
		if img.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = img.get_pixbuf()
		else:
			return False
		if pix.get_width() > 24 or pix.get_height() > 24:
			return False
		return True
		
	def make_regexps(self):
		# regexp meta characters are:  . ^ $ * + ? { } [ ] \ | ( )
		# one escapes the metachars with \
		# \S matches anything but ' ' '\t' '\n' '\r' '\f' and '\v'
		# \s matches any whitespace character
		# \w any alphanumeric character
		# \W any non-alphanumeric character
		# \b means word boundary. This is a zero-width assertion that
		# 					matches only at the beginning or end of a word.
		# ^ matches at the beginning of lines
		#
		# * means 0 or more times
		# + means 1 or more times
		# ? means 0 or 1 time
		# | means or
		# [^*] anything but '*'   (inside [] you don't have to escape metachars)
		# [^\s*] anything but whitespaces and '*'
		# (?<!\S) is a one char lookbehind assertion and asks for any leading whitespace
		# and mathces beginning of lines so we have correct formatting detection
		# even if the the text is just '*foo*'
		# (?!\S) is the same thing but it's a lookahead assertion
		# \S*[^\s)?!,.;] --> in the matching string don't match ? or ) etc.. if at the end
		# so http://be) will match http://be and http://be)be) will match http://be)be
		links = r'\bhttp://\S*[^\s)?!,.;]|' r'\bhttps://\S*[^\s)?!,.;]|' r'\bnews://\S*[^\s)?!,.;]|' r'\bftp://\S*[^\s)?!,.;]|' r'\bed2k://\S*[^\s)?!,.;]|' r'\bwww\.\S*[^\s)?!,.;]|' r'\bftp\.\S*[^\s)?!,.;]|'
		#2nd one: at_least_one_char@at_least_one_char.at_least_one_char
		mail = r'\bmailto:\S*[^\s)?!,.;]|' r'\b\S+@\S+\.\S*[^\s)?]|'

		#detects eg. *b* *bold* *bold bold* test *bold*
		#doesn't detect (it's a feature :P) * bold* *bold * * bold * test*bold*
		formatting = r'(?<!\S)\*[^\s*]([^*]*[^\s*])?\*(?!\S)|' r'(?<!\S)/[^\s/]([^/]*[^\s/])?/(?!\S)|' r'(?<!\S)_[^\s_]([^_]*[^\s_])?_(?!\S)'

		basic_pattern = links + mail + formatting
		self.basic_pattern_re = sre.compile(basic_pattern, sre.IGNORECASE)
		
		emoticons_pattern = ''
		for emoticon in self.emoticons: # travel thru emoticons list
			emoticon_escaped = sre.escape(emoticon) # espace regexp metachars
			emoticons_pattern += emoticon_escaped + '|'# | means or in regexp

		emot_and_basic_pattern = emoticons_pattern + basic_pattern
		self.emot_and_basic_re = sre.compile(emot_and_basic_pattern,\
															sre.IGNORECASE)
		
		# at least one character in 3 parts (before @, after @, after .)
		self.sth_at_sth_dot_sth_re = sre.compile(r'\S+@\S+\.\S*[^\s)?]')

	def on_launch_browser_mailer(self, widget, url, kind):
		self.launch_browser_mailer(kind, url)

	def init_regexp(self):
		#initialize emoticons dictionary
		self.emoticons = dict()
		emots = gajim.config.get_per('emoticons')
		for emot in emots:
			emot_file = gajim.config.get_per('emoticons', emot, 'path')
			if not self.image_is_ok(emot_file):
				continue
			pix = gtk.gdk.pixbuf_new_from_file(emot_file)
			self.emoticons[emot] = pix
		
		# update regular expressions
		self.make_regexps()

	def register_handlers(self, conn):
		conn.register_handler('ROSTER', self.handle_event_roster)
		conn.register_handler('WARNING', self.handle_event_warning)
		conn.register_handler('ERROR', self.handle_event_error)
		conn.register_handler('ERROR_ANSWER', self.handle_event_error_answer)
		conn.register_handler('STATUS', self.handle_event_status)
		conn.register_handler('NOTIFY', self.handle_event_notify)
		conn.register_handler('MSG', self.handle_event_msg)
		conn.register_handler('MSGERROR', self.handle_event_msgerror)
		conn.register_handler('MSGSENT', self.handle_event_msgsent)
		conn.register_handler('SUBSCRIBED', self.handle_event_subscribed)
		conn.register_handler('UNSUBSCRIBED', self.handle_event_unsubscribed)
		conn.register_handler('SUBSCRIBE', self.handle_event_subscribe)
		conn.register_handler('AGENT_INFO', self.handle_event_agent_info)
		conn.register_handler('REGISTER_AGENT_INFO',
			self.handle_event_register_agent_info)
		conn.register_handler('AGENT_INFO_ITEMS',
			self.handle_event_agent_info_items)
		conn.register_handler('AGENT_INFO_INFO',
			self.handle_event_agent_info_info)
		conn.register_handler('QUIT', self.handle_event_quit)
		conn.register_handler('ACC_OK', self.handle_event_acc_ok)
		conn.register_handler('MYVCARD', self.handle_event_myvcard)
		conn.register_handler('VCARD', self.handle_event_vcard)
		conn.register_handler('OS_INFO', self.handle_event_os_info)
		conn.register_handler('GC_MSG', self.handle_event_gc_msg)
		conn.register_handler('GC_SUBJECT', self.handle_event_gc_subject)
		conn.register_handler('GC_CONFIG', self.handle_event_gc_config)
		conn.register_handler('BAD_PASSPHRASE', self.handle_event_bad_passphrase)
		conn.register_handler('ROSTER_INFO', self.handle_event_roster_info)

	def process_connections(self):
		try:
			for account in gajim.connections:
				if gajim.connections[account].connected:
					gajim.connections[account].process(0.01)
			return True # renew timeout (loop for ever)
		except KeyboardInterrupt:
			sys.exit()

	def save_config(self):
		parser.write()

	def __init__(self):
		self.default_values = {
			'inmsgcolor': gajim.config.get('inmsgcolor'),
			'outmsgcolor': gajim.config.get('outmsgcolor'),
			'statusmsgcolor': gajim.config.get('statusmsgcolor'),
		}
		parser.read()
		
		for account in gajim.config.get_per('accounts'):
			gajim.connections[account] = common.connection.Connection(account)
	
		if gtk.pygtk_version >= (2, 6, 0):
			gtk.about_dialog_set_email_hook(self.on_launch_browser_mailer, 'mail')
			gtk.about_dialog_set_url_hook(self.on_launch_browser_mailer, 'url')
		self.windows = {'logs':{}}
		self.queues = {}
		self.nicks = {}
		self.allow_notifications = {}
		self.sleeper_state = {} #whether we pass auto away / xa or not
		for a in gajim.connections:
			self.windows[a] = {'infos': {}, 'chats': {}, 'gc': {}, 'gc_config': {}}
			self.queues[a] = {}
			self.nicks[a] = gajim.config.get_per('accounts', a, 'name')
			self.allow_notifications[a] = False
			self.sleeper_state[a] = 0	#0:don't use sleeper for this account
												#1:online and use sleeper
												#2:autoaway and use sleeper
												#3:autoxa and use sleeper

		iconset = gajim.config.get('iconset')
		path = '../data/iconsets/' + iconset + '/'
		files = [path + 'online.gif', path + 'online.png', path + 'online.xpm']
		pix = None
		for fname in files:
			if os.path.exists(fname):
				pix = gtk.gdk.pixbuf_new_from_file(fname)
				break
		if pix:
			gtk.window_set_default_icon(pix)
		self.roster = roster_window.Roster_window(self)
		self.sleeper = common.sleepy.Sleepy( \
			gajim.config.get('autoawaytime') * 60, \
			gajim.config.get('autoxatime') * 60)
		self.systray_enabled = False
		try:
			import egg.trayicon as trayicon # use gnomepythonextras trayicon
		except:
			try:
				import trayicon # use yann's
			except: # user doesn't have trayicon capabilities
				self.systray_capabilities = False
			else:
				self.systray_capabilities = True
				self.systray = systray.Systray(self)
		else:
			self.systray_capabilities = True
			self.systray = systray.Systray(self)
		if self.systray_capabilities:
			self.show_systray()

		if gajim.config.get('check_for_new_version'):
			check_for_new_version.Check_for_new_version_dialog(self)

		self.init_regexp()
		
		# get instances for windows/dialogs that will show_all()/hide()
		self.windows['preferences'] = config.Preferences_window(self)
		self.windows['add_remove_emoticons'] = \
			config.Add_remove_emoticons_window(self)
		self.windows['roster'] = self.roster
		
		for account in gajim.connections:
			self.register_handlers(gajim.connections[account])

		gobject.timeout_add(100, self.autoconnect)
		gobject.timeout_add(200, self.process_connections)
		gobject.timeout_add(500, self.read_sleepy)

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application

	try: 	# Import Psyco if available
		import psyco
		psyco.full()
	except ImportError:
		pass
	
	Interface()
	gtk.main()
