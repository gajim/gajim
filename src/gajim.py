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
## - Dimitur Kirov <dkirov@gmail.com>
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
		
import sys
import pygtk
import os
if not os.name == 'nt': # py2exe only in windows
		pygtk.require('2.0') # py2exe fails on this
try:
	import gtk
except RuntimeError, msg:
	if str(msg) == 'could not open display':
		print 'Gajim needs Xserver to run. Exiting...'
		sys.exit()
		
import gobject
import pango
import sre
import signal
import getopt
import time

from common import socks5
import gtkgui_helpers

from common import i18n
i18n.init()
_ = i18n._

import common.sleepy
import check_for_new_version
from common import gajim
from common import connection
from common import helpers

from common import optparser

profile = ''
try:
	opts, args = getopt.getopt(sys.argv[1:], 'hvp:', ['help', 'verbose',
		'profile='])
except getopt.error, msg:
	print msg
	print 'for help use --help'
	sys.exit(2)
for o, a in opts:
	if o in ('-h', '--help'):
		print 'gajim [--help] [--verbose] [--profile name]'
		sys.exit()
	elif o in ('-v', '--verbose'):
		gajim.verbose = True
	elif o in ('-p', '--profile'): # gajim --profile name
		profile = a


config_filename = os.path.expanduser('~/.gajim/config')
if os.name == 'nt':
	try:
		# Documents and Settings\[User Name]\Application Data\Gajim\logs
		config_filename = os.environ['appdata'] + '/Gajim/config'
	except KeyError:
		# win9x so ./config
		config_filename = 'config'

if profile:
	config_filename += '.%s' % profile

parser = optparser.OptionsParser(config_filename)

try:
	import winsound # windows-only built-in module for playing wav
except ImportError:
	pass

class Contact:
	'''Information concerning each contact'''
	def __init__(self, jid='', name='', groups=[], show='', status='', sub='',\
			ask='', resource='', priority=5, keyID='', role='', affiliation='',\
			chatstate=None):
		self.jid = jid
		self.name = name
		self.groups = groups
		self.show = show
		self.status = status
		self.sub = sub
		self.ask = ask
		self.resource = resource
		self.priority = priority
		self.keyID = keyID
		self.role = role
		self.affiliation = affiliation

		# please read jep-85 http://www.jabber.org/jeps/jep-0085.html
		# we keep track of jep85 support by the peer by three extra states:
		# None, False and 'ask'
		# None if no info about peer
		# False if peer does not support jep85
		# 'ask' if we sent the first 'active' chatstate and are waiting for reply
		# this holds what WE SEND to contact (the current chatstate)
		self.chatstate = chatstate

import roster_window
import systray
import dialogs
import config

GTKGUI_GLADE = 'gtkgui.glade'


class Interface:
	def handle_event_roster(self, account, data):
		#('ROSTER', account, array)
		self.roster.fill_contacts_and_groups_dicts(data, account)
		self.roster.draw_roster()
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('Roster', (account, data))

	def handle_event_warning(self, unused, data):
		#('WARNING', account, (title_text, section_text))
		dialogs.WarningDialog(data[0], data[1]).get_response()

	def handle_event_error(self, unused, data):
		#('ERROR', account, (title_text, section_text))
		dialogs.ErrorDialog(data[0], data[1]).get_response()

	def handle_event_information(self, unused, data):
		#('INFORMATION', account, (title_text, section_text))
		dialogs.InformationDialog(data[0], data[1])

	def handle_event_http_auth(self, account, data):
		#('HTTP_AUTH', account, (method, url, iq_obj))
		dialog = dialogs.ConfirmationDialog(_('HTTP (%s) Authorization for %s') \
			% (data[0], data[1]), _('Do you accept this request?'))
		if dialog.get_response() == gtk.RESPONSE_OK:
			answer = 'yes'
		else:
			answer = 'no'
		gajim.connections[account].build_http_auth_answer(data[2], answer)

	def handle_event_error_answer(self, account, array):
		#('ERROR_ANSWER', account, (id, jid_from. errmsg, errcode))
		id, jid_from, errmsg, errcode = array
		if unicode(errcode) in ['403', '406'] and id:
			# show the error dialog
			ft = self.windows['file_transfers']
			sid = id
			if len(id) > 3 and id[2] == '_':
				sid = id[3:]
			if ft.files_props['s'].has_key(sid):
				file_props = ft.files_props['s'][sid]
				file_props['error'] = -4
				self.handle_event_file_request_error(account, 
					(jid_from, file_props))
				conn = gajim.connections[account]
				conn.disconnect_transfer(file_props)
				return
		elif unicode(errcode) == '404':
			conn = gajim.connections[account]
			sid = id
			if len(id) > 3 and id[2] == '_':
				sid = id[3:]
			if conn.files_props.has_key(sid):
				file_props = conn.files_props[sid]
				self.handle_event_file_send_error(account, 
					(jid_from, file_props))
				conn.disconnect_transfer(file_props)
				return
		
		if jid_from in self.windows[account]['gc']:
			self.windows[account]['gc'][jid_from].print_conversation(
				_('Error %s: %s') % (array[2], array[1]), jid_from)

	def handle_event_con_type(self, account, con_type):
		# ('CON_TYPE', account, con_type) which can be 'ssl', 'tls', 'tcp'
		gajim.con_types[account] = con_type

	def allow_notif(self, account):
		gajim.allow_notifications[account] = True

	def handle_event_status(self, account, status): # OUR status
		#('STATUS', account, status)
		if status != 'offline':
			gobject.timeout_add(30000, self.allow_notif, account)
		else:
			gajim.allow_notifications[account] = False
			# we are disconnected from all gc
			for room_jid in gajim.gc_connected[account]:
				if self.windows[account]['gc'].has_key(room_jid):
					self.windows[account]['gc'][room_jid].got_disconnected(room_jid)
		self.roster.on_status_changed(account, status)
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('AccountPresence', (status, account))
	
	def handle_event_notify(self, account, array):
		#('NOTIFY', account, (jid, status, message, resource, priority, keyID, 
		# role, affiliation, real_jid, reason, actor, statusCode, new_nick))
		# if we're here it means contact changed show
		statuss = ['offline', 'error', 'online', 'chat', 'away', 'xa', 'dnd',
			'invisible']
		old_show = 0
		new_show = statuss.index(array[1])
		jid = array[0].split('/')[0]
		keyID = array[5]
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		if jid in attached_keys:
			keyID = attached_keys[attached_keys.index(jid) + 1]
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
		if gajim.contacts[account].has_key(ji):
			luser = gajim.contacts[account][ji]
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
				if old_show == new_show and user1.status == array[2]: #no change
					return
			else:
				user1 = gajim.contacts[account][ji][0]
				if user1.show in statuss:
					old_show = statuss.index(user1.show)
				if (resources != [''] and (len(luser) != 1 or 
					luser[0].show != 'offline')) and jid.find('@') > 0:
					old_show = 0
					user1 = Contact(jid = user1.jid, name = user1.name,
						groups = user1.groups, show = user1.show,
						status = user1.status, sub = user1.sub, ask = user1.ask,
						resource = user1.resource, priority = user1.priority,
						keyID = user1.keyID)
					luser.append(user1)
				user1.resource = resource
			if user1.jid.find('@') > 0 and len(luser) == 1: # It's not an agent
				if old_show == 0 and new_show > 1:
					if not user1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].append(user1.jid)
					if user1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].remove(user1.jid)
					gobject.timeout_add(5000, self.roster.remove_newly_added, \
						user1.jid, account)
				if old_show > 1 and new_show == 0 and gajim.connections[account].\
					connected > 1:
					if not user1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].append(user1.jid)
					if user1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].remove(user1.jid)
					self.roster.draw_contact(user1.jid, account)
					if not gajim.awaiting_messages[account].has_key(jid):
						gobject.timeout_add(5000, self.roster.really_remove_contact, \
							user1, account)
			user1.show = array[1]
			user1.status = array[2]
			user1.priority = priority
			user1.keyID = keyID
		if jid.find('@') <= 0:
			#It must be an agent
			if gajim.contacts[account].has_key(ji):
				#Update existing iter
				self.roster.draw_contact(ji, account)
		elif gajim.contacts[account].has_key(ji):
			#It isn't an agent
			self.roster.chg_contact_status(user1, array[1], array[2], account)
			#play sound
			if old_show < 2 and new_show > 1:
				if gajim.config.get_per('soundevents', 'contact_connected',
												'enabled'):
					helpers.play_sound('contact_connected')
				if not self.windows[account]['chats'].has_key(jid) and \
					not gajim.awaiting_messages[account].has_key(jid) and \
					gajim.config.get('notify_on_signin') and \
					gajim.allow_notifications[account]:
					show_notification = False
					# check OUR status and if we allow notifications for that status
					if gajim.config.get('autopopupaway'): # always notify
						show_notification = True
					elif gajim.connections[account].connected in (2, 3): # we're online or chat
						show_notification = True
					if show_notification:
						instance = dialogs.PopupNotificationWindow(self,
														_('Contact Signed In'), jid, account)
						self.roster.popup_notification_windows.append(instance)
				if self.remote and self.remote.is_enabled():
					self.remote.raise_signal('ContactPresence',
						(account, array))
				
				# when contact signs out we reset his chatstate
				contact = gajim.get_first_contact_instance_from_jid(account, jid)
				contact.chatstate = None
				
			elif old_show > 1 and new_show < 2:
				if gajim.config.get_per('soundevents', 'contact_disconnected',
												'enabled'):
					helpers.play_sound('contact_disconnected')
				if not self.windows[account]['chats'].has_key(jid) and \
					not gajim.awaiting_messages[account].has_key(jid) and \
					gajim.config.get('notify_on_signout'):
					show_notification = False
					# check OUR status and if we allow notifications for that status
					if gajim.config.get('autopopupaway'): # always notify
						show_notification = True
					elif gajim.connections[account].connected in (2, 3): # we're online or chat
						show_notification = True
					if show_notification:
						instance = dialogs.PopupNotificationWindow(self,
											 		_('Contact Signed Out'), jid, account)
						self.roster.popup_notification_windows.append(instance)
				if self.remote and self.remote.is_enabled():
					self.remote.raise_signal('ContactAbsence', (account, array))
				# stop non active file transfers
				
		elif self.windows[account]['gc'].has_key(ji): # ji is then room_jid
			#it is a groupchat presence
			#FIXME: upgrade the chat instances (for pm)
			#FIXME: real_jid can be None
			self.windows[account]['gc'][ji].chg_contact_status(ji, resource,
				array[1], array[2], array[6], array[7], array[8], array[9],
				array[10], array[11], array[12], account)
			if self.remote and self.remote.is_enabled():
				self.remote.raise_signal('GCPresence', (account, array))

	def handle_event_msg(self, account, array):
		#('MSG', account, (jid, msg, time, encrypted, msg_type, subject, chatstate))
		jid = gajim.get_jid_without_resource(array[0])
		msg_type = array[4]
		chatstate = array[6]
		if jid.find('@') <= 0:
			jid = jid.replace('@', '')

		if self.windows[account]['gc'].has_key(jid): # it's a Private Message
			nick = array[0].split('/', 1)[1]
			fjid = jid + '/' + nick
			if self.windows[account]['chats'].has_key(fjid):
				chat_win = self.windows[account]['chats'][fjid]
				chat_win.print_conversation(array[1], fjid, tim = array[2])
				return
			qs = gajim.awaiting_messages[account]
			if not qs.has_key(fjid):
				qs[fjid] = []
			qs[fjid].append((array[1], array[2], array[3]))
			self.roster.nb_unread += 1
			show = gajim.gc_contacts[account][jid][nick].show
			c = Contact(jid = fjid, name = nick, groups = ['none'], show = show,
				ask = 'none')
			self.roster.new_chat(c, account)
			return
				
		if gajim.config.get('ignore_unknown_contacts') and \
			not gajim.contacts[account].has_key(jid):
			return

		# Handle chat states
		contact = gajim.get_first_contact_instance_from_jid(account, jid)
		if self.windows[account]['chats'].has_key(jid):
			chat_win = self.windows[account]['chats'][jid]
			if chatstate is not None: # he sent us reply, so he supports jep85
				if contact.chatstate == 'ask': # we were jep85 disco?
					contact.chatstate = 'active' # no more
				
				chat_win.handle_incoming_chatstate(account, jid, chatstate)
			else:
				# got no valid jep85 answer, peer does not support it
				contact.chatstate = False
		else:
			# Brand new message, incoming.
			if chatstate == 'active':
				contact.chatstate = chatstate

		if not array[1]: #empty message text
			return

		first = False
		if not self.windows[account]['chats'].has_key(jid) and \
						not gajim.awaiting_messages[account].has_key(jid):
			first = True
			if gajim.config.get('notify_on_new_message'):
				show_notification = False
				# check OUR status and if we allow notifications for that status
				if gajim.config.get('autopopupaway'): # always show notification
					show_notification = True
				elif gajim.connections[account].connected in (2, 3): # we're online or chat
					show_notification = True
				if show_notification:
					if msg_type == 'normal': # single message
						instance = dialogs.PopupNotificationWindow(self,
							_('New Single Message'), jid, account, msg_type)
					else: # chat message
						instance = dialogs.PopupNotificationWindow(self,
							_('New Message'), jid, account, msg_type)

					self.roster.popup_notification_windows.append(instance)

		# array : (contact, msg, time, encrypted, msg_type, subject)
		self.roster.on_message(jid, array[1], array[2], account, array[3],
			array[4], array[5])
		if gajim.config.get_per('soundevents', 'first_message_received',
			'enabled') and first:
			helpers.play_sound('first_message_received')
		if gajim.config.get_per('soundevents', 'next_message_received',
			'enabled') and not first:
			helpers.play_sound('next_message_received')
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('NewMessage', (account, array))

	def handle_event_msgerror(self, account, array):
		#('MSGERROR', account, (jid, error_code, error_msg, msg, time))
		fjid = array[0]
		jids = fjid.split('/', 1)
		jid = jids[0]
		gcs = self.windows[account]['gc']
		if jid in gcs:
			if len(jids) > 1: # it's a pm
				nick = jids[1]
				if not self.windows[account]['chats'].has_key(fjid):
					gc = gcs[jid]
					tv = gc.list_treeview[jid]
					model = tv.get_model()
					i = gc.get_contact_iter(jid, nick)
					if i:
						show = model[i][3]
					else:
						show = 'offline'
					c = Contact(jid = fjid, name = nick, groups = ['none'],
						show = show, ask = 'none')
					self.roster.new_chat(c, account)
				self.windows[account]['chats'][fjid].print_conversation(
					'Error %s: %s' % (array[1], array[2]), fjid, 'status')
				return
			gcs[jid].print_conversation('Error %s: %s' % \
				(array[1], array[2]), jid)
			if gcs[jid].get_active_jid() == jid:
				gcs[jid].set_subject(jid,
					gcs[jid].subjects[jid])
			return
		if jid.find('@') <= 0:
			jid = jid.replace('@', '')
		self.roster.on_message(jid, _('error while sending') + \
			' \"%s\" ( %s )' % (array[3], array[2]), array[4], account)
		
	def handle_event_msgsent(self, account, array):
		#('MSGSENT', account, (jid, msg, keyID))
		msg = array[1]
		# do not play sound when standalone chatstate message (eg no msg)
		if msg and gajim.config.get_per('soundevents', 'message_sent', 'enabled'):
			helpers.play_sound('message_sent')
		
	def handle_event_subscribe(self, account, array):
		#('SUBSCRIBE', account, (jid, text))
		dialogs.SubscriptionRequestWindow(self, array[0], array[1], account)
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('Subscribe', (account, array))

	def handle_event_subscribed(self, account, array):
		#('SUBSCRIBED', account, (jid, resource))
		jid = array[0]
		if gajim.contacts[account].has_key(jid):
			c = gajim.get_first_contact_instance_from_jid(account, jid)
			c.resource = array[1]
			self.roster.remove_contact(c, account)
			if _('not in the roster') in c.groups:
				c.groups.remove(_('not in the roster'))
			if len(c.groups) == 0:
				c.groups = [_('General')]
			self.roster.add_contact_to_roster(c.jid, account)
			gajim.connections[account].update_contact(c.jid, c.name, c.groups)
		else:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact1 = Contact(jid = jid, name = jid.split('@')[0],
				groups = [_('General')], show = 'online', status = 'online',
				ask = 'to', resource = array[1], keyID = keyID)
			gajim.contacts[account][jid] = [contact1]
			self.roster.add_contact_to_roster(jid, account)
		dialogs.InformationDialog(_('Authorization accepted'),
				_('The contact "%s" has authorized you to see his status.')
				% jid)
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('Subscribed', (account, array))

	def handle_event_unsubscribed(self, account, jid):
		dialogs.InformationDialog(_('Contact "%s" removed subscription from you') % jid,
				_('You will always see him as offline.'))
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('Unsubscribed', (account, jid))

	def handle_event_agent_info(self, account, array):
		#('AGENT_INFO', account, (agent, identities, features, items))
		if self.windows[account].has_key('disco'):
			self.windows[account]['disco'].agent_info(array[0], array[1], \
				array[2], array[3])

	def handle_event_register_agent_info(self, account, array):
		#('AGENT_INFO', account, (agent, infos))
		if array[1].has_key('instructions'):
			config.ServiceRegistrationWindow(array[0], array[1], self, account)
		else:
			dialogs.ErrorDialog(_('Contact with "%s" cannot be established'\
% array[0]), _('Check your connection or try again later.')).get_response()

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
		dialogs.InformationDialog(_('Account registration successful'),
			_('The account "%s" has been registered with the Jabber server.') % name)
		gajim.config.add_per('accounts', name)
		for opt in array[1]:
			gajim.config.set_per('accounts', name, opt, array[1][opt])
		if self.windows.has_key('account_modification'):
			self.windows['account_modification'].account_is_ok(array[0])
		self.windows[name] = {'infos': {}, 'chats': {}, 'gc': {}, 'gc_config': {}}
		self.windows[name]['xml_console'] = dialogs.XMLConsoleWindow(self, name)
		gajim.awaiting_messages[name] = {}
		# disconnect from server - our status in roster is offline
		gajim.connections[name].connected = 1
		gajim.gc_contacts[name] = {}
		gajim.gc_connected[name] = {}
		gajim.nicks[name] = array[1]['name']
		gajim.allow_notifications[name] = False
		gajim.groups[name] = {}
		gajim.contacts[name] = {}
		gajim.newly_added[name] = []
		gajim.to_be_removed[name] = []
		gajim.sleeper_state[name] = 'off'
		gajim.encrypted_chats[name] = []
		gajim.last_message_time[name] = {}
		gajim.status_before_autoaway[name] = ''
		gajim.events_for_ui[name] = []
		gajim.connections[name].change_status('offline', None, True)
		gajim.connections[name].connected = 0
		if self.windows.has_key('accounts'):
			self.windows['accounts'].init_accounts()
		self.roster.draw_roster()
		
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('NewAccount', (account, array))

	def handle_event_quit(self, p1, p2):
		self.roster.quit_gtkgui_plugin()

	def handle_event_myvcard(self, account, array):
		nick = ''
		if array.has_key('NICKNAME'):
			nick = array['NICKNAME']
			if nick:
				gajim.nicks[account] = nick
		if self.windows[account]['infos'].has_key(array['jid']):
			 win = self.windows[account]['infos'][array['jid']]
			 win.set_values(array)

	def handle_event_vcard(self, account, array):
		win = None
		if self.windows[account]['infos'].has_key(array['jid']):
			win = self.windows[account]['infos'][array['jid']]
		elif self.windows[account]['infos'].has_key(array['jid'] + '/' + \
				array['resource']):
			win = self.windows[account]['infos'][array['jid'] + '/' + \
				array['resource']]
		if win:
			win.set_values(array)

		#show avatar in chat
		win = None
		if self.windows[account]['chats'].has_key(array['jid']):
			win = self.windows[account]['chats'][array['jid']]
		elif self.windows[account]['chats'].has_key(array['jid'] + '/' + \
				array['resource']):
			win = self.windows[account]['chats'][array['jid'] + '/' + \
				array['resource']]
		if win:
			win.set_avatar(array)

	def handle_event_os_info(self, account, array):
		win = None
		if self.windows[account]['infos'].has_key(array[0]):
			win = self.windows[account]['infos'][array[0]]
		elif self.windows[account]['infos'].has_key(array[0] + '/' + array[1]):
			win = self.windows[account]['infos'][array[0] + '/' + array[1]]
		if win:
			win.set_os_info(array[1], array[2], array[3])
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('OsInfo', (account, array))

	def handle_event_gc_msg(self, account, array):
		#('GC_MSG', account, (jid, msg, time))
		jids = array[0].split('/', 1)
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
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('GCMessage', (account, array))

	def handle_event_gc_subject(self, account, array):
		#('GC_SUBJECT', account, (jid, subject))
		jids = array[0].split('/', 1)
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
			config.GroupchatConfigWindow(self, account, jid, array[1])

	def handle_event_bad_passphrase(self, account, array):
		use_gpg_agent = gajim.config.get('use_gpg_agent')
		if use_gpg_agent:
		  return
		keyID = gajim.config.get_per('accounts', account, 'keyid')
		self.roster.forget_gpg_passphrase(keyID)
		dialogs.WarningDialog(_('Your passphrase is incorrect'),
			_('You are currently connected without your OpenPGP key.')).get_response()

	def handle_event_roster_info(self, account, array):
		#('ROSTER_INFO', account, (jid, name, sub, ask, groups))
		jid = array[0]
		if not gajim.contacts[account].has_key(jid):
			return
		users = gajim.contacts[account][jid]
		if not (array[2] or array[3]):
			self.roster.remove_contact(users[0], account)
			del gajim.contacts[account][jid]
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
		if self.remote and self.remote.is_enabled():
			self.remote.raise_signal('RosterInfo', (account, array))

	def handle_event_bookmarks(self, account, bms):
		# ('BOOKMARKS', account, [{name,jid,autojoin,password,nick}, {}])
		# We received a bookmark item from the server (JEP48)
		# Auto join GC windows if neccessary
		for bm in bms:
			if bm['autojoin'] in ('1', 'true'):
				self.roster.join_gc_room(account, bm['jid'], bm['nick'],
					bm['password'])
		self.roster.make_menu()
								
	def handle_event_file_send_error(self, account, array):
		jid = array[0]
		file_props = array[1]
		ft = self.windows['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')
		if gajim.config.get('notify_on_new_message'):
			# check if we should be notified
			instance = dialogs.PopupNotificationWindow(self,
					_('File Transfer Error'), jid, account, 'file-send-error', file_props)
			self.roster.popup_notification_windows.append(instance)
		elif (gajim.connections[account].connected in (2, 3)
			and gajim.config.get('autopopup')) or \
			gajim.config.get('autopopupaway'):
			self.windows['file_transfers'].show_send_error(file_props)
		
	def handle_event_file_request_error(self, account, array):
		jid = array[0]
		file_props = array[1]
		errno = file_props['error']
		ft = self.windows['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')
		if gajim.config.get('notify_on_new_message'):
			# check if we should be notified
			if errno == -4 or errno == -5:
				msg_type = 'file-error'
			else:
				msg_type = 'file-request-error'
			instance = dialogs.PopupNotificationWindow(self,
					_('File Transfer Error'), jid, account, msg_type, file_props)
			self.roster.popup_notification_windows.append(instance)
		elif (gajim.connections[account].connected in (2, 3)
			and gajim.config.get('autopopup')) or \
			gajim.config.get('autopopupaway'):
			if errno == -4 or errno == -5:
				self.windows['file_transfers'].show_stopped(jid, file_props)
			else:
				self.windows['file_transfers'].show_request_error(file_props)
		
	def handle_event_file_request(self, account, array):
		jid = array[0]
		if not gajim.contacts[account].has_key(jid):
			return
		file_props = array[1]
		# FIXME: in 0.9 we'll have a queue for that
#		if gajim.config.get('notify_on_new_message'):
#			# check if we should be notified
#			instance = dialogs.PopupNotificationWindow(self,
#					_('File Transfer Request'), jid, account, 'file', file_props)
#			self.roster.popup_notification_windows.append(instance)
#		elif (gajim.connections[account].connected in (2, 3)
#			and gajim.config.get('autopopup')) or \
#			gajim.config.get('autopopupaway'):
#			contact = gajim.contacts[account][jid][0]
#			self.windows['file_transfers'].show_file_request(
#				account, contact, file_props)
		contact = gajim.contacts[account][jid][0]
		self.windows['file_transfers'].show_file_request(
			account, contact, file_props)
				
	def handle_event_file_progress(self, account, file_props):
		self.windows['file_transfers'].set_progress(file_props['type'], 
			file_props['sid'], file_props['received-len'])
			
	def handle_event_file_rcv_completed(self, account, file_props):
		ft = self.windows['file_transfers']
		if file_props['error'] == 0:
			ft.set_progress(file_props['type'], file_props['sid'], 
				file_props['received-len'])
		else:
			ft.set_status(file_props['type'], file_props['sid'], 'stop')
		if file_props.has_key('stalled') and file_props['stalled'] or \
			file_props.has_key('paused') and file_props['paused']:
			return
		jid = unicode(file_props['sender'])
		if gajim.config.get('notify_on_file_complete'):
			if (gajim.connections[account].connected in (2, 3)
			and gajim.config.get('autopopup')) or \
			gajim.config.get('autopopupaway'):
				if file_props['error'] == 0:
					ft.show_completed(jid, file_props)
				elif file_props['error'] == -1:
					ft.show_stopped(jid, file_props)
				return
			if file_props['error'] == 0:
				msg_type = 'file-completed'
				event_type = _('File Transfer Completed')
			elif file_props['error'] == -1:
				msg_type = 'file-stopped'
				event_type = _('File Transfer Stopped')
			instance = dialogs.PopupNotificationWindow(self, event_type, 
				jid, account, msg_type, file_props)
			self.roster.popup_notification_windows.append(instance)

	def handle_event_stanza_arrived(self, account, stanza):
		if not self.windows.has_key(account):
			return
		if self.windows[account].has_key('xml_console'):
			self.windows[account]['xml_console'].print_stanza(stanza, 'incoming')

	def handle_event_stanza_sent(self, account, stanza):
		if not self.windows.has_key(account):
			return
		if self.windows[account].has_key('xml_console'):
			self.windows[account]['xml_console'].print_stanza(stanza, 'outgoing')

	def read_sleepy(self):	
		'''Check idle status and change that status if needed'''
		if not self.sleeper.poll():
			return True # renew timeout (loop for ever)
		state = self.sleeper.getState()
		for account in gajim.connections:
			if not gajim.sleeper_state.has_key(account) or \
					not gajim.sleeper_state[account]:
				continue
			if state == common.sleepy.STATE_AWAKE and \
				gajim.sleeper_state[account] in ('autoaway', 'autoxa'):
				#we go online [we pass True to auto param]
				self.roster.send_status(account, 'online',
					gajim.status_before_autoaway[account], True)
				gajim.sleeper_state[account] = 'online'
			elif state == common.sleepy.STATE_AWAY and \
				gajim.sleeper_state[account] == 'online' and \
				gajim.config.get('autoaway'):
				#we save out online status
				gajim.status_before_autoaway[account] = \
					gajim.connections[account].status
				#we go away (no auto status) [we pass True to auto param]
				self.roster.send_status(account, 'away',
					gajim.config.get('autoaway_message'), True)
				gajim.sleeper_state[account] = 'autoaway'
			elif state == common.sleepy.STATE_XAWAY and (\
				gajim.sleeper_state[account] == 'autoaway' or \
				gajim.sleeper_state[account] == 'online') and \
				gajim.config.get('autoxa'):
				#we go extended away [we pass True to auto param]
				self.roster.send_status(account, 'xa',
					gajim.config.get('autoxa_message'), True)
				gajim.sleeper_state[account] = 'autoxa'
		return True # renew timeout (loop for ever)

	def autoconnect(self):
		'''auto connect at startup'''
		ask_message = False
		for a in gajim.connections:
			if gajim.config.get_per('accounts', a, 'autoconnect'):
				ask_message = True
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
			return False
		t = img.get_storage_type()
		if t != gtk.IMAGE_PIXBUF and t != gtk.IMAGE_ANIMATION:
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
		# \S*[^\s\W] --> in the matching string don't match ? or ) etc.. if at the end
		# so http://be) will match http://be and http://be)be) will match http://be)be
		links = r'\bhttp://\S*[^\s\W]|' r'\bhttps://\S*[^\s\W]|' r'\bnews://\S*[^\s\W]|' r'\bftp://\S*[^\s\W]|' r'\bed2k://\S*[^\s\W]|' r'\bwww\.\S*[^\s\W]|' r'\bftp\.\S*[^\s\W]|'
		#2nd one: at_least_one_char@at_least_one_char.at_least_one_char
		mail = r'\bmailto:\S*[^\s\W]|' r'\b\S+@\S+\.\S*[^\s\W]|'

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
		self.emot_and_basic_re = sre.compile(emot_and_basic_pattern,
															sre.IGNORECASE)
		
		# at least one character in 3 parts (before @, after @, after .)
		self.sth_at_sth_dot_sth_re = sre.compile(r'\S+@\S+\.\S*[^\s)?]')

	def on_launch_browser_mailer(self, widget, url, kind):
		helpers.launch_browser_mailer(kind, url)

	def init_regexp(self):
		#initialize emoticons dictionary
		self.emoticons = dict()
		emots = gajim.config.get_per('emoticons')
		for emot in emots:
			emot_file = gajim.config.get_per('emoticons', emot, 'path')
			if not self.image_is_ok(emot_file):
				continue
			self.emoticons[emot] = emot_file
		
		# update regular expressions
		self.make_regexps()

	def register_handlers(self, con):
		self.handlers = {
			'ROSTER': self.handle_event_roster,
			'WARNING': self.handle_event_warning,
			'ERROR': self.handle_event_error,
			'INFORMATION': self.handle_event_information,
			'ERROR_ANSWER': self.handle_event_error_answer,
			'STATUS': self.handle_event_status,
			'NOTIFY': self.handle_event_notify,
			'MSG': self.handle_event_msg,
			'MSGERROR': self.handle_event_msgerror,
			'MSGSENT': self.handle_event_msgsent,
			'SUBSCRIBED': self.handle_event_subscribed,
			'UNSUBSCRIBED': self.handle_event_unsubscribed,
			'SUBSCRIBE': self.handle_event_subscribe,
			'AGENT_INFO': self.handle_event_agent_info,
			'REGISTER_AGENT_INFO': self.handle_event_register_agent_info,
			'AGENT_INFO_ITEMS': self.handle_event_agent_info_items,
			'AGENT_INFO_INFO': self.handle_event_agent_info_info,
			'QUIT': self.handle_event_quit,
			'ACC_OK': self.handle_event_acc_ok,
			'MYVCARD': self.handle_event_myvcard,
			'VCARD': self.handle_event_vcard,
			'OS_INFO': self.handle_event_os_info,
			'GC_MSG': self.handle_event_gc_msg,
			'GC_SUBJECT': self.handle_event_gc_subject,
			'GC_CONFIG': self.handle_event_gc_config,
			'BAD_PASSPHRASE': self.handle_event_bad_passphrase,
			'ROSTER_INFO': self.handle_event_roster_info,
			'BOOKMARKS': self.handle_event_bookmarks,
			'CON_TYPE': self.handle_event_con_type,
			'FILE_REQUEST': self.handle_event_file_request,
			'FILE_REQUEST_ERROR': self.handle_event_file_request_error,
			'FILE_SEND_ERROR': self.handle_event_file_send_error,
			'STANZA_ARRIVED': self.handle_event_stanza_arrived,
			'STANZA_SENT': self.handle_event_stanza_sent,
			'HTTP_AUTH': self.handle_event_http_auth,
		}

	def exec_event(self, account):
		ev = gajim.events_for_ui[account].pop(0)
		self.handlers[ev[0]](account, ev[1])

	def process_connections(self):
		try:
			# We copy the list of connections because one can disappear while we 
			# process()
			accounts = []
			for account in gajim.connections:
				accounts.append(account)
			for account in accounts:
				if gajim.connections[account].connected:
					gajim.connections[account].process(0.01)
				if gajim.socks5queue.connected:
					gajim.socks5queue.process(0.01)
			for account in gajim.events_for_ui: #when we create a new account we don't have gajim.connection
				while len(gajim.events_for_ui[account]):
					gajim.mutex_events_for_ui.lock(self.exec_event, account)
					gajim.mutex_events_for_ui.unlock()
			time.sleep(0.01) # so threads in connection.py have time to run
			return True # renew timeout (loop for ever)
		except KeyboardInterrupt:
			sys.exit()
		return False

	def save_config(self):
		err_code = parser.write()
		if err_code is not None:
			strerr = os.strerror(err_code)
			print strerr
			# it is good to notify the user
			# in case he cannot see the output of the console
			dialogs.ErrorDialog(_('Cannot save your preferences'),
				strerr).get_response()
			sys.exit(1)

	def enable_dbus(self):
		if 'remote_control' not in globals():
			import remote_control
		if not hasattr(self, 'remote') or not self.remote:
			try:
				self.remote = remote_control.Remote(self)
			except remote_control.DbusNotSupported:
				self.remote = None
				return False
			except remote_control.SessionBusNotPresent:
				self.remote = None
				return False
		else:
			# enable the previously disabled object
			self.remote.set_enabled(True)
		return True

	def disable_dbus(self):
		if hasattr(self, 'remote') and self.remote is not None:
			# just tell the remote object to skip remote messages
			self.remote.set_enabled(False)
		else:
			self.remote = None

	def __init__(self):
		self.default_values = {
			'inmsgcolor': gajim.config.get('inmsgcolor'),
			'outmsgcolor': gajim.config.get('outmsgcolor'),
			'statusmsgcolor': gajim.config.get('statusmsgcolor'),
		}
		parser.read()
		# Do not set gajim.verbose to False if -v option was given
		if gajim.config.get('verbose'):
			gajim.verbose = True
		#add default emoticons if there is not in the config file
		if len(gajim.config.get_per('emoticons')) == 0:
			for emot in gajim.config.emoticons_default:
				gajim.config.add_per('emoticons', emot)
				gajim.config.set_per('emoticons', emot, 'path', gajim.config.emoticons_default[emot])
		#add default status messages if there is not in the config file
		if len(gajim.config.get_per('statusmsg')) == 0:
			for msg in gajim.config.statusmsg_default:
				gajim.config.add_per('statusmsg', msg)
				gajim.config.set_per('statusmsg', msg, 'message', gajim.config.statusmsg_default[msg])
		#add default themes if there is not in the config file
		theme = gajim.config.get('roster_theme')
		if not theme in gajim.config.get_per('themes'):
			gajim.config.set('roster_theme', 'green')
		if len(gajim.config.get_per('themes')) == 0:
			d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
				'grouptextcolor', 'groupbgcolor', 'groupfont', 'contacttextcolor',
				'contactbgcolor', 'contactfont', 'bannertextcolor', 'bannerbgcolor']
			
			font_str = gtkgui_helpers.get_default_font()
			if font_str is None:
				font_str = 'Sans 10'
			font = pango.FontDescription(font_str)
			font_normal = font.to_string()
			font.set_style(pango.STYLE_ITALIC)
			font_italic = font.to_string()
			font.set_style(pango.STYLE_NORMAL)
			font.set_weight(pango.WEIGHT_BOLD)
			font_bold = font.to_string()
			
			default = gajim.config.themes_default
			for theme_name in default:
				gajim.config.add_per('themes', theme_name)
				theme = default[theme_name]
				theme[d.index('accountfont')] = font_bold
				theme[d.index('groupfont')] = font_italic
				theme[d.index('contactfont')] = font_normal
				for o in d:
					gajim.config.set_per('themes', theme_name, o,
						theme[d.index(o)])
			
		if gajim.config.get('autodetect_browser_mailer'):
			gtkgui_helpers.autodetect_browser_mailer()

		if gajim.verbose:
			gajim.log.setLevel(gajim.logging.DEBUG)
		else:
			gajim.log.setLevel(None)
		gajim.socks5queue = socks5.SocksQueue(
			self.handle_event_file_rcv_completed, 
			self.handle_event_file_progress)
		for account in gajim.config.get_per('accounts'):
			gajim.connections[account] = common.connection.Connection(account)
															
		if gtk.pygtk_version >= (2, 6, 0):
			gtk.about_dialog_set_email_hook(self.on_launch_browser_mailer, 'mail')
			gtk.about_dialog_set_url_hook(self.on_launch_browser_mailer, 'url')
		self.windows = {'logs':{}}
		
		for a in gajim.connections:
			self.windows[a] = {'infos': {}, 'chats': {}, 'gc': {}, 'gc_config': {}}
			gajim.contacts[a] = {}
			gajim.groups[a] = {}
			gajim.gc_contacts[a] = {}
			gajim.gc_connected[a] = {}
			gajim.newly_added[a] = []
			gajim.to_be_removed[a] = []
			gajim.awaiting_messages[a] = {}
			gajim.nicks[a] = gajim.config.get_per('accounts', a, 'name')
			gajim.allow_notifications[a] = False
			gajim.sleeper_state[a] = 0
			gajim.encrypted_chats[a] = []
			gajim.last_message_time[a] = {}
			gajim.status_before_autoaway[a] = ''
			gajim.events_for_ui[a] = []

		self.roster = roster_window.RosterWindow(self)
		if gajim.config.get('use_dbus'):
			self.enable_dbus()
		else:
			self.disable_dbus()

		path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps/gajim.png')
		pix = gtk.gdk.pixbuf_new_from_file(path_to_file)
		gtk.window_set_default_icon(pix) # set the icon to all newly opened windows
		self.roster.window.set_icon_from_file(path_to_file) # and to roster window
		self.sleeper = common.sleepy.Sleepy(
			gajim.config.get('autoawaytime') * 60,
			gajim.config.get('autoxatime') * 60)

		self.systray_enabled = False
		self.systray_capabilities = False
		
		if os.name == 'nt':
			try:
				import systraywin32
			except: # user doesn't have trayicon capabilities
				pass
			else:
				self.systray_capabilities = True
				self.systray = systraywin32.SystrayWin32(self)
		else:
			try:
				import egg.trayicon # use gnomepythonextras trayicon
			except:
				try:
					import trayicon # use the one we distribute
				except: # user doesn't have trayicon capabilities
					pass
				else:
					self.systray_capabilities = True
					self.systray = systray.Systray(self)
			else:
				self.systray_capabilities = True
				self.systray = systray.Systray(self)

		if self.systray_capabilities and gajim.config.get('trayicon'):
			self.show_systray()
		if gajim.config.get('check_for_new_version'):
			check_for_new_version.Check_for_new_version_dialog(self)

		self.init_regexp()
		
		# get instances for windows/dialogs that will show_all()/hide()
		self.windows['file_transfers'] = dialogs.FileTransfersWindow(self)
		self.windows['preferences'] = config.PreferencesWindow(self)
		self.windows['add_remove_emoticons'] = \
			config.ManageEmoticonsWindow(self)
		self.windows['roster'] = self.roster
		
		for account in gajim.connections:
			self.windows[account]['xml_console'] = \
				dialogs.XMLConsoleWindow(self, account)
			self.register_handlers(gajim.connections[account])

		gobject.timeout_add(100, self.autoconnect)
		gobject.timeout_add(200, self.process_connections)
		gobject.timeout_add(500, self.read_sleepy)

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application

	try: # Import Psyco if available
		import psyco
		psyco.full()
	except ImportError:
		pass
	
	Interface()
	gtk.main()
