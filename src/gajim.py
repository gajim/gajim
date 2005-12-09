#!/bin/sh
''':'
exec python -OOt "$0" ${1+"$@"}
' '''
##	gajim.py
##
## Contributors for this file:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
## - Dimitur Kirov <dkirov@gmail.com>
## - Travis Shirk <travis@pobox.com>
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
import os
import pygtk

from common import exceptions
from common import i18n
i18n.init()
_ = i18n._

try:
	import gtk
except RuntimeError, msg:
	if str(msg) == 'could not open display':
		print >> sys.stderr, _('Gajim needs Xserver to run. Quiting...')
		sys.exit()
pritext = ''
if gtk.pygtk_version < (2, 6, 0):
	pritext = _('Gajim needs PyGTK 2.6 or above')
	sectext = _('Gajim needs PyGTK 2.6 or above to run. Quiting...')
elif gtk.gtk_version < (2, 6, 0):
	pritext = _('Gajim needs GTK 2.6 or above')
	sectext = _('Gajim needs GTK 2.6 or above to run. Quiting...')

try:
	import gtk.glade # check if user has libglade (in pygtk and in gtk)
except ImportError:
	pritext = _('GTK+ runtime is missing libglade support')
	if os.name == 'nt':
		sectext = _('Please remove your current GTK+ runtime and install the latest stable version from %s') % 'http://gladewin32.sourceforge.net'
	else:
		sectext = _('Please make sure that gtk and pygtk have libglade support in your system.')

try:
	from common import check_paths
except exceptions.PysqliteNotAvailable, e:
	pritext = _('Gajim needs PySQLite2 to run')
	sectext = str(e)

if pritext:
	dlg = gtk.MessageDialog(None, 
				gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
				gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, message_format = pritext)

	dlg.format_secondary_text(sectext)
	dlg.run()
	dlg.destroy()
	sys.exit()

path = os.getcwd()
if '.svn' in os.listdir(path) or '_svn' in os.listdir(path):
	# import gtkexcepthook only for those that run svn
	# those than run with --verbose run from terminal so no need to care
	# about those
	import gtkexcepthook
del path

import gobject
if sys.version[:4] >= '2.4': # FIXME: remove me when we abandon python23
	gobject.threads_init()

import pango
import sre
import signal
import getopt
import time
import threading

import gtkgui_helpers
import notify

import common.sleepy

from common import socks5
from common import gajim
from common import connection
from common import helpers
from common import optparser

profile = ''
try:
	opts, args = getopt.getopt(sys.argv[1:], 'hvp:', ['help', 'verbose',
		'profile=', 'sm-config-prefix=', 'sm-client-id='])
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

class Contact:
	'''Information concerning each contact'''
	def __init__(self, jid='', name='', groups=[], show='', status='', sub='',
			ask='', resource='', priority=5, keyID='', role='', affiliation='',
			our_chatstate=None, chatstate=None):
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
		# this holds what WE SEND to contact (our current chatstate)
		self.our_chatstate = our_chatstate
		# this is contact's chatstate
		self.chatstate = chatstate

import roster_window
import systray
import dialogs
import vcard
import config
import disco

GTKGUI_GLADE = 'gtkgui.glade'


class Interface:
	def handle_event_roster(self, account, data):
		#('ROSTER', account, array)
		self.roster.fill_contacts_and_groups_dicts(data, account)
		self.roster.draw_roster()
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Roster', (account, data))

	def handle_event_warning(self, unused, data):
		#('WARNING', account, (title_text, section_text))
		dialogs.WarningDialog(data[0], data[1]).get_response()

	def handle_event_error(self, unused, data):
		#('ERROR', account, (title_text, section_text))
		dialogs.ErrorDialog(data[0], data[1]).get_response()

	def handle_event_information(self, unused, data):
		#('INFORMATION', account, (title_text, section_text))
		dialogs.InformationDialog(data[0], data[1])
		
	def handle_event_ask_new_nick(self, account, data):
		#('ASK_NEW_NICK', account, (room_jid, title_text, prompt_text, proposed_nick))
		room_jid = data[0]
		title = data[1]
		prompt = data[2]
		proposed_nick = data[3]
		w = self.instances[account]['gc']
		if w.has_key(room_jid): # user may close the window before we are here
			w[room_jid].show_change_nick_input_dialog(title, prompt, proposed_nick,
				room_jid)

	def handle_event_http_auth(self, account, data):
		#('HTTP_AUTH', account, (method, url, transaction_id, iq_obj))
		dialog = dialogs.ConfirmationDialog(_('HTTP (%s) Authorization for %s (id: %s)') \
			% (data[0], data[1], data[2]), _('Do you accept this request?'))
		if dialog.get_response() == gtk.RESPONSE_OK:
			answer = 'yes'
		else:
			answer = 'no'
		gajim.connections[account].build_http_auth_answer(data[3], answer)

	def handle_event_error_answer(self, account, array):
		#('ERROR_ANSWER', account, (id, jid_from. errmsg, errcode))
		id, jid_from, errmsg, errcode = array
		if unicode(errcode) in ('403', '406') and id:
			# show the error dialog
			ft = self.instances['file_transfers']
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
		if jid_from in self.instances[account]['gc']:
			self.instances[account]['gc'][jid_from].print_conversation(
				'Error %s: %s' % (array[2], array[1]), jid_from)

	def handle_event_con_type(self, account, con_type):
		# ('CON_TYPE', account, con_type) which can be 'ssl', 'tls', 'tcp'
		gajim.con_types[account] = con_type

	def allow_notif(self, account):
		gajim.allow_notifications[account] = True

	def handle_event_status(self, account, status): # OUR status
		#('STATUS', account, status)
		model = self.roster.status_combobox.get_model()
		if status == 'offline':
			model[self.roster.status_message_menuitem_iter][3] = False # sensitivity for this menuitem
			gajim.allow_notifications[account] = False
			# we are disconnected from all gc
			if not gajim.gc_connected.has_key(account):
				return
			for room_jid in gajim.gc_connected[account]:
				if self.instances[account]['gc'].has_key(room_jid):
					self.instances[account]['gc'][room_jid].got_disconnected(room_jid)
		else:
			gobject.timeout_add(30000, self.allow_notif, account)
			model[self.roster.status_message_menuitem_iter][3] = True # sensitivity for this menuitem
		self.roster.on_status_changed(account, status)
		if account in self.show_vcard_when_connect:
			jid = gajim.get_jid_from_account(account)
			if not self.instances[account]['infos'].has_key(jid):
				self.instances[account]['infos'][jid] = \
					vcard.VcardWindow(jid, account, True)
				gajim.connections[account].request_vcard(jid)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('AccountPresence', (status, account))
	
	def handle_event_notify(self, account, array):
		#('NOTIFY', account, (jid, status, message, resource, priority, keyID))
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
			# It must be an agent
			ji = jid.replace('@', '')
		else:
			ji = jid
		# Update contact
		if gajim.contacts[account].has_key(ji):
			lcontact = gajim.contacts[account][ji]
			contact1 = None
			resources = []
			for c in lcontact:
				resources.append(c.resource)
				if c.resource == resource:
					contact1 = c
					break
			if contact1:
				if contact1.show in statuss:
					old_show = statuss.index(contact1.show)
				if old_show == new_show and contact1.status == array[2]: #no change
					return
			else:
				contact1 = gajim.contacts[account][ji][0]
				if contact1.show in statuss:
					old_show = statuss.index(contact1.show)
				if (resources != [''] and (len(lcontact) != 1 or 
					lcontact[0].show != 'offline')) and jid.find('@') > 0:
					old_show = 0
					contact1 = Contact(jid = contact1.jid, name = contact1.name,
						groups = contact1.groups, show = contact1.show,
						status = contact1.status, sub = contact1.sub,
						ask = contact1.ask, resource = contact1.resource,
						priority = contact1.priority, keyID = contact1.keyID)
					lcontact.append(contact1)
				contact1.resource = resource
			if contact1.jid.find('@') > 0 and len(lcontact) == 1: # It's not an agent
				if old_show == 0 and new_show > 1:
					if not contact1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].append(contact1.jid)
					if contact1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].remove(contact1.jid)
					gobject.timeout_add(5000, self.roster.remove_newly_added,
						contact1.jid, account)
				if old_show > 1 and new_show == 0 and gajim.connections[account].\
					connected > 1:
					if not contact1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].append(contact1.jid)
					if contact1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].remove(contact1.jid)
					self.roster.draw_contact(contact1.jid, account)
					if not gajim.awaiting_events[account].has_key(jid):
						gobject.timeout_add(5000, self.roster.really_remove_contact,
							contact1, account)
			contact1.show = array[1]
			contact1.status = array[2]
			contact1.priority = priority
			contact1.keyID = keyID
		if jid.find('@') <= 0:
			# It must be an agent
			if gajim.contacts[account].has_key(ji):
				# Update existing iter
				self.roster.draw_contact(ji, account)
		elif jid == gajim.get_jid_from_account(account):
			# It's another of our resources.  We don't need to see that!
			return
		elif gajim.contacts[account].has_key(ji):
			# It isn't an agent
			# reset chatstate if needed:
			# (when contact signs out or has errors)
			if array[1] in ('offline', 'error'):
				contact1.our_chatstate = contact1.chatstate = None
			self.roster.chg_contact_status(contact1, array[1], array[2], account)
			# play sound
			if old_show < 2 and new_show > 1:
				if gajim.config.get_per('soundevents', 'contact_connected',
					'enabled'):
					helpers.play_sound('contact_connected')
				if not self.instances[account]['chats'].has_key(jid) and \
					not gajim.awaiting_events[account].has_key(jid) and \
					gajim.config.get('notify_on_signin') and \
					gajim.allow_notifications[account]:
					show_notification = False
					# check OUR status and if we allow notifications for that status
					if gajim.config.get('autopopupaway'): # always notify
						show_notification = True
					elif gajim.connections[account].connected in (2, 3): # we're online or chat
						show_notification = True
					if show_notification:
						notify.notify(_('Contact Signed In'), jid, account)
				if self.remote_ctrl:
					self.remote_ctrl.raise_signal('ContactPresence',
						(account, array))
				
			elif old_show > 1 and new_show < 2:
				if gajim.config.get_per('soundevents', 'contact_disconnected',
						'enabled'):
					helpers.play_sound('contact_disconnected')
				if not self.instances[account]['chats'].has_key(jid) and \
					not gajim.awaiting_events[account].has_key(jid) and \
					gajim.config.get('notify_on_signout'):
					show_notification = False
					# check OUR status and if we allow notifications for that status
					if gajim.config.get('autopopupaway'): # always notify
						show_notification = True
					elif gajim.connections[account].connected in (2, 3): # we're online or chat
						show_notification = True
					if show_notification:
						notify.notify(_('Contact Signed Out'), jid, account)
				if self.remote_ctrl:
					self.remote_ctrl.raise_signal('ContactAbsence', (account, array))
				# FIXME: stop non active file transfers
		else:
			# FIXME: Msn transport (CMSN1.2.1 and PyMSN0.10) doesn't follow the JEP
			# remove in 2007
			# It's maybe a GC_NOTIFY (specialy for MSN gc)
			self.handle_event_gc_notify(account, (jid, array[1], array[2], array[3], None, None, None, None, None, None, None))
			

	def handle_event_msg(self, account, array):
		# ('MSG', account, (jid, msg, time, encrypted, msg_type, subject,
		# chatstate))
		jid = gajim.get_jid_without_resource(array[0])
		resource = gajim.get_resource_from_jid(array[0])
		msg_type = array[4]
		chatstate = array[6]
		if jid.find('@') <= 0:
			jid = jid.replace('@', '')

		show_notification = False
		if gajim.config.get('notify_on_new_message'):
			# check OUR status and if we allow notifications for that status
			if gajim.config.get('autopopupaway'): # always show notification
				show_notification = True
			elif gajim.connections[account].connected in (2, 3): # we're online or chat
				show_notification = True

		if self.instances[account]['gc'].has_key(jid): # it's a Private Message
			nick = gajim.get_nick_from_fjid(array[0])
			fjid = array[0]
			if not self.instances[account]['chats'].has_key(fjid) and \
				not gajim.awaiting_events[account].has_key(fjid):
				if show_notification:
					notify.notify(_('New Private Message'), fjid, account, 'pm')

			self.instances[account]['gc'][jid].on_private_message(jid, nick,
				array[1], array[2])
			return
				
		if gajim.config.get('ignore_unknown_contacts') and \
			not gajim.contacts[account].has_key(jid):
			return

		# Handle chat states  
		contact = gajim.get_first_contact_instance_from_jid(account, jid)
		if self.instances[account]['chats'].has_key(jid):
			chat_win = self.instances[account]['chats'][jid]
			if chatstate is not None: # he or she sent us reply, so he supports jep85
				contact.chatstate = chatstate
				if contact.our_chatstate == 'ask': # we were jep85 disco?
					contact.our_chatstate = 'active' # no more
				
				chat_win.handle_incoming_chatstate(account, contact)
			elif contact.chatstate != 'active':
				# got no valid jep85 answer, peer does not support it
				contact.chatstate = False
		elif contact and chatstate == 'active':
			# Brand new message, incoming.  
			contact.our_chatstate = chatstate
			contact.chatstate = chatstate

		if not array[1]: #empty message text
			return

		first = False
		if not self.instances[account]['chats'].has_key(jid) and \
			not gajim.awaiting_events[account].has_key(jid):
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
						notify.notify(_('New Single Message'), jid, account, msg_type)
					else: # chat message
						notify.notify(_('New Message'), jid, account, msg_type)

		# array : (contact, msg, time, encrypted, msg_type, subject)
		self.roster.on_message(jid, array[1], array[2], account, array[3],
			msg_type, array[5], resource)
		if gajim.config.get_per('soundevents', 'first_message_received',
			'enabled') and first:
			helpers.play_sound('first_message_received')
		if gajim.config.get_per('soundevents', 'next_message_received',
			'enabled') and not first:
			helpers.play_sound('next_message_received')
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('NewMessage', (account, array))

	def handle_event_msgerror(self, account, array):
		#('MSGERROR', account, (jid, error_code, error_msg, msg, time))
		fjid = array[0]
		jids = fjid.split('/', 1)
		jid = jids[0]
		gcs = self.instances[account]['gc']
		if jid in gcs:
			if len(jids) > 1: # it's a pm
				nick = jids[1]
				if not self.instances[account]['chats'].has_key(fjid):
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
				self.instances[account]['chats'][fjid].print_conversation(
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
			' \"%s\" ( %s )' % (array[3], array[2]), array[4], account, \
			msg_type='error')
		
	def handle_event_msgsent(self, account, array):
		#('MSGSENT', account, (jid, msg, keyID))
		msg = array[1]
		# do not play sound when standalone chatstate message (eg no msg)
		if msg and gajim.config.get_per('soundevents', 'message_sent', 'enabled'):
			helpers.play_sound('message_sent')
		
	def handle_event_subscribe(self, account, array):
		#('SUBSCRIBE', account, (jid, text))
		dialogs.SubscriptionRequestWindow(array[0], array[1], account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Subscribe', (account, array))

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
			name = jid.split('@', 1)[0]
			name = name.split('%', 1)[0]
			contact1 = Contact(jid = jid, name = name, groups = [_('General')],
				show = 'online', status = 'online', ask = 'to',
				resource = array[1], keyID = keyID)
			gajim.contacts[account][jid] = [contact1]
			self.roster.add_contact_to_roster(jid, account)
		dialogs.InformationDialog(_('Authorization accepted'),
				_('The contact "%s" has authorized you to see his or her status.')
				% jid)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Subscribed', (account, array))

	def handle_event_unsubscribed(self, account, jid):
		dialogs.InformationDialog(_('Contact "%s" removed subscription from you') % jid,
				_('You will always see him or her as offline.'))
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Unsubscribed', (account, jid))
	
	def handle_event_agent_info_error(self, account, agent):
		#('AGENT_ERROR_INFO', account, (agent))
		try:
			gajim.connections[account].services_cache.agent_info_error(agent)
		except AttributeError:
			return
	
	def handle_event_agent_items_error(self, account, agent):
		#('AGENT_ERROR_INFO', account, (agent))
		try:
			gajim.connections[account].services_cache.agent_items_error(agent)
		except AttributeError:
			return

	def handle_event_register_agent_info(self, account, array):
		#('REGISTER_AGENT_INFO', account, (agent, infos, is_form))
		if array[1].has_key('instructions'):
			config.ServiceRegistrationWindow(array[0], array[1], account,
				array[2])
		else:
			dialogs.ErrorDialog(_('Contact with "%s" cannot be established'\
% array[0]), _('Check your connection or try again later.')).get_response()

	def handle_event_agent_info_items(self, account, array):
		#('AGENT_INFO_ITEMS', account, (agent, node, items))
		try:
			gajim.connections[account].services_cache.agent_items(array[0],
				array[1], array[2])
		except AttributeError:
			return

	def handle_event_agent_info_info(self, account, array):
		#('AGENT_INFO_INFO', account, (agent, node, identities, features, data))
		try:
			gajim.connections[account].services_cache.agent_info(array[0],
				array[1], array[2], array[3], array[4])
		except AttributeError:
			return

	def handle_event_acc_ok(self, account, array):
		#('ACC_OK', account, (config))
		if self.instances.has_key('account_creation_wizard'):
			self.instances['account_creation_wizard'].acc_is_ok(array)

		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('NewAccount', (account, array))

	def handle_event_acc_not_ok(self, account, array):
		#('ACC_NOT_OK', account, (reason))
		if self.instances.has_key('account_creation_wizard'):
			self.instances['account_creation_wizard'].acc_is_not_ok(array)

	def handle_event_quit(self, p1, p2):
		self.roster.quit_gtkgui_interface()

	def handle_event_myvcard(self, account, array):
		nick = ''
		if array.has_key('NICKNAME'):
			nick = array['NICKNAME']
			if nick:
				gajim.nicks[account] = nick
		if self.instances[account]['infos'].has_key(array['jid']):
			win = self.instances[account]['infos'][array['jid']]
			win.set_values(array)
			if account in self.show_vcard_when_connect:
				win.xml.get_widget('information_notebook').set_current_page(-1)
				win.xml.get_widget('set_avatar_button').clicked()
				self.show_vcard_when_connect.remove(account)

	def handle_event_vcard(self, account, vcard):
		# ('VCARD', account, data)
		'''vcard holds the vcard data'''
		jid = vcard['jid']
		resource = ''
		if vcard.has_key('resource'):
			resource = vcard['resource']
		
		# vcard window
		win = None
		if self.instances[account]['infos'].has_key(jid):
			win = self.instances[account]['infos'][jid]
		elif resource and self.instances[account]['infos'].has_key(
			jid + '/' + resource):
			win = self.instances[account]['infos'][jid + '/' + resource]
		if win:
			win.set_values(vcard)

		# show avatar in chat
		win = None
		if self.instances[account]['chats'].has_key(jid):
			win = self.instances[account]['chats'][jid]
		elif resource and self.instances[account]['chats'].has_key(
			jid + '/' + resource):
			win = self.instances[account]['chats'][jid + '/' + resource]
		if win:
			win.show_avatar(jid, resource)
		# Show avatar in roster
		self.roster.draw_avatar(jid, account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('VcardInfo', (account, vcard))

	def handle_event_os_info(self, account, array):
		win = None
		if self.instances[account]['infos'].has_key(array[0]):
			win = self.instances[account]['infos'][array[0]]
		elif self.instances[account]['infos'].has_key(array[0] + '/' + array[1]):
			win = self.instances[account]['infos'][array[0] + '/' + array[1]]
		if win:
			win.set_os_info(array[1], array[2], array[3])
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('OsInfo', (account, array))

	def handle_event_gc_notify(self, account, array):
		#('GC_NOTIFY', account, (jid, status, message, resource,
		# role, affiliation, jid, reason, actor, statusCode, newNick))
		jid = array[0].split('/')[0]
		resource = array[3]
		if not resource:
			resource = ''
		if self.instances[account]['gc'].has_key(jid): # ji is then room_jid
			#FIXME: upgrade the chat instances (for pm)
			#FIXME: real_jid can be None
			self.instances[account]['gc'][jid].chg_contact_status(jid, resource,
				array[1], array[2], array[4], array[5], array[6], array[7],
				array[8], array[9], array[10], account)
			if self.remote_ctrl:
				self.remote_ctrl.raise_signal('GCPresence', (account, array))

	def handle_event_gc_msg(self, account, array):
		# ('GC_MSG', account, (jid, msg, time))
		jids = array[0].split('/', 1)
		room_jid = jids[0]
		if not self.instances[account]['gc'].has_key(room_jid):
			return
		if len(jids) == 1:
			# message from server
			nick = ''
		else:
			# message from someone
			nick = jids[1]
		self.instances[account]['gc'][room_jid].on_message(room_jid, nick,
			array[1], array[2])
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('GCMessage', (account, array))

	def handle_event_gc_subject(self, account, array):
		#('GC_SUBJECT', account, (jid, subject))
		jids = array[0].split('/', 1)
		jid = jids[0]
		if not self.instances[account]['gc'].has_key(jid):
			return
		self.instances[account]['gc'][jid].set_subject(jid, array[1])
		if len(jids) > 1:
			self.instances[account]['gc'][jid].print_conversation(
				'%s has set the subject to %s' % (jids[1], array[1]), jid)

	def handle_event_gc_config(self, account, array):
		#('GC_CONFIG', account, (jid, config))  config is a dict
		jid = array[0].split('/')[0]
		if not self.instances[account]['gc_config'].has_key(jid):
			self.instances[account]['gc_config'][jid] = \
			config.GroupchatConfigWindow(account, jid, array[1])
	
	def handle_event_gc_invitation(self, account, array):
		#('GC_INVITATION', (room_jid, jid_from, reason, password))
		dialogs.InvitationReceivedDialog(account, array[0], array[1],
			array[3], array[2])
	
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
		contacts = gajim.contacts[account][jid]
		if not (array[2] or array[3]):
			self.roster.remove_contact(contacts[0], account)
			del gajim.contacts[account][jid]
			#FIXME if it was the only one in its group, remove the group
			return
		for contact in contacts:
			name = array[1]
			if name:
				contact.name = name
			contact.sub = array[2]
			contact.ask = array[3]
			if array[4]:
				contact.groups = array[4]
		self.roster.draw_contact(jid, account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('RosterInfo', (account, array))

	def handle_event_bookmarks(self, account, bms):
		# ('BOOKMARKS', account, [{name,jid,autojoin,password,nick}, {}])
		# We received a bookmark item from the server (JEP48)
		# Auto join GC windows if neccessary
		
		self.roster.make_menu() # update the menu to show our bookmarks
		invisible_show = gajim.SHOW_LIST.index('invisible')
		# do not autojoin if we are invisible
		if gajim.connections[account].connected == invisible_show:
			return

		# join autojoinable rooms
		for bm in bms:
			if bm['autojoin'] in ('1', 'true'):
				self.roster.join_gc_room(account, bm['jid'], bm['nick'],
					bm['password'])
								
	def handle_event_file_send_error(self, account, array):
		jid = array[0]
		file_props = array[1]
		ft = self.instances['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')

		if gajim.popup_window(account):
			ft.show_send_error(file_props)
			return

		self.add_event(account, jid, 'file-send-error', file_props)

		if gajim.show_notification(account):
			notify.notify(_('File Transfer Error'),
				jid, account, 'file-send-error', file_props)

	def add_event(self, account, jid, typ, args):
		'''add an event to the awaiting_events var'''
		# We add it to the awaiting_events queue
		# Do we have a queue?
		qs = gajim.awaiting_events[account]
		no_queue = False
		if not qs.has_key(jid):
			no_queue = True
			qs[jid] = []
		qs[jid].append((typ, args))
		self.roster.nb_unread += 1

		self.roster.show_title()
		if no_queue: # We didn't have a queue: we change icons
			self.roster.draw_contact(jid, account)
		if self.systray_enabled:
			self.systray.add_jid(jid, account, typ)

	def remove_first_event(self, account, jid, typ = None):
		qs = gajim.awaiting_events[account]
		event = gajim.get_first_event(account, jid, typ)
		qs[jid].remove(event)
		self.roster.nb_unread -= 1
		self.roster.show_title()
		# Is it the last event?
		if not len(qs[jid]):
			del qs[jid]
		self.roster.draw_contact(jid, account)
		if self.systray_enabled:
			self.systray.remove_jid(jid, account, typ)

	def handle_event_file_request_error(self, account, array):
		jid = array[0]
		file_props = array[1]
		ft = self.instances['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')
		errno = file_props['error']

		if gajim.popup_window(account):
			if errno in (-4, -5):
				ft.show_stopped(jid, file_props)
			else:
				ft.show_request_error(file_props)
			return

		if errno in (-4, -5):
			msg_type = 'file-error'
		else:
			msg_type = 'file-request-error'

		self.add_event(account, jid, msg_type, file_props)

		if gajim.show_notification(account):
			# check if we should be notified
			notify.notify(_('File Transfer Error'),
				jid, account, msg_type, file_props)

	def handle_event_file_request(self, account, array):
		jid = array[0]
		if not gajim.contacts[account].has_key(jid):
			return
		file_props = array[1]
		contact = gajim.contacts[account][jid][0]

		if gajim.popup_window(account):
			self.instances['file_transfers'].show_file_request(account, contact,
				file_props)
			return

		self.add_event(account, jid, 'file-request', file_props)

		if gajim.show_notification(account):
			notify.notify(_('File Transfer Request'),
				jid, account, 'file-request')

	def handle_event_file_progress(self, account, file_props):
		self.instances['file_transfers'].set_progress(file_props['type'], 
			file_props['sid'], file_props['received-len'])
			
	def handle_event_file_rcv_completed(self, account, file_props):
		ft = self.instances['file_transfers']
		if file_props['error'] == 0:
			ft.set_progress(file_props['type'], file_props['sid'], 
				file_props['received-len'])
		else:
			ft.set_status(file_props['type'], file_props['sid'], 'stop')
		if file_props.has_key('stalled') and file_props['stalled'] or \
			file_props.has_key('paused') and file_props['paused']:
			return
		jid = unicode(file_props['sender'])

		if gajim.popup_window(account):
			if file_props['error'] == 0:
				if gajim.config.get('notify_on_file_complete'):
					ft.show_completed(jid, file_props)
			elif file_props['error'] == -1:
				ft.show_stopped(jid, file_props)
			return

		msg_type = ''
		event_type = ''
		if file_props['error'] == 0 and gajim.config.get('notify_on_file_complete'):
			msg_type = 'file-completed'
			event_type = _('File Transfer Completed')
		elif file_props['error'] == -1:
			msg_type = 'file-stopped'
			event_type = _('File Transfer Stopped')
		
		if event_type == '': 
			# FIXME: ugly workaround (this can happen Gajim sent, Gaim recvs)
			# this should never happen but it does. see process_result() in socks5.py
			# who calls this func (sth is really wrong unless this func is also registered
			# as progress_cb
			return

		if msg_type:
			self.add_event(account, jid, msg_type, file_props)

		if gajim.config.get('notify_on_file_complete') and \
			(gajim.config.get('autopopupaway') or \
			gajim.connections[account].connected in (2, 3)):
			# we want to be notified and we are online/chat or we don't mind
			# bugged when away/na/busy
			notify.notify(event_type, jid, account, msg_type, file_props)

	def handle_event_stanza_arrived(self, account, stanza):
		if not self.instances.has_key(account):
			return
		if self.instances[account].has_key('xml_console'):
			self.instances[account]['xml_console'].print_stanza(stanza, 'incoming')

	def handle_event_stanza_sent(self, account, stanza):
		if not self.instances.has_key(account):
			return
		if self.instances[account].has_key('xml_console'):
			self.instances[account]['xml_console'].print_stanza(stanza, 'outgoing')

	def handle_event_vcard_published(self, account, array):
		dialogs.InformationDialog(_('vCard publication succeeded'), _('Your personal information has been published successfully.'))

	def handle_event_vcard_not_published(self, account, array):
		dialogs.InformationDialog(_('vCard publication failed'), _('There was an error while publishing your personal information, try again later.'))

	def handle_event_signed_in(self, account, empty):
		'''SIGNED_IN event is emitted when we sign in, so handle it'''
		# join already open groupchats
		for room_jid in self.instances[account]['gc']:
			if room_jid == 'tabbed':
				continue
			if gajim.gc_connected[account][room_jid]:
				continue
			room, server = gajim.get_room_name_and_server_from_room_jid(
				room_jid)
			nick = self.instances[account]['gc'][room_jid].nicks[room_jid]
			password = ''
			if gajim.gc_passwords.has_key(room_jid):
				password = gajim.gc_passwords[room_jid]
			gajim.connections[account].join_gc(nick, room, server, password)

	def read_sleepy(self):	
		'''Check idle status and change that status if needed'''
		if not self.sleeper.poll():
			# idle detection is not supported in that OS
			return False # stop looping in vain
		state = self.sleeper.getState()
		for account in gajim.connections:
			if not gajim.sleeper_state.has_key(account) or \
					not gajim.sleeper_state[account]:
				continue
			if state == common.sleepy.STATE_AWAKE and \
				gajim.sleeper_state[account] in ('autoaway', 'autoxa'):
				#we go online
				self.roster.send_status(account, 'online',
					gajim.status_before_autoaway[account])
				gajim.sleeper_state[account] = 'online'
			elif state == common.sleepy.STATE_AWAY and \
				gajim.sleeper_state[account] == 'online' and \
				gajim.config.get('autoaway'):
				#we save out online status
				gajim.status_before_autoaway[account] = \
					gajim.connections[account].status
				#we go away (no auto status) [we pass True to auto param]
				self.roster.send_status(account, 'away',
					gajim.config.get('autoaway_message'), auto=True)
				gajim.sleeper_state[account] = 'autoaway'
			elif state == common.sleepy.STATE_XA and (\
				gajim.sleeper_state[account] == 'autoaway' or \
				gajim.sleeper_state[account] == 'online') and \
				gajim.config.get('autoxa'):
				#we go extended away [we pass True to auto param]
				self.roster.send_status(account, 'xa',
					gajim.config.get('autoxa_message'), auto=True)
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

		prefixes = (r'http://', r'https://', r'news://', r'ftp://', r'ed2k://',
			r'magnet:', r'www\.', r'ftp\.')
		# NOTE: it's ok to catch www.gr such stuff exist!
		
		#FIXME: recognize xmpp: and treat it specially
		
		prefix_pattern = ''
		for prefix in prefixes:
			prefix_pattern += prefix + '|'
		
		prefix_pattern = prefix_pattern[:-1] # remove last |
		prefix_pattern = '(' + prefix_pattern + ')'
			
		links = r'\b' + prefix_pattern + r'\S*[^\s\W]|'
		#2nd one: at_least_one_char@at_least_one_char.at_least_one_char
		mail = r'\bmailto:\S*[^\s\W]|' r'\b\S+@\S+\.\S*[^\s\W]|'

		#detects eg. *b* *bold* *bold bold* test *bold* *bold*! (*bold*)
		#doesn't detect (it's a feature :P) * bold* *bold * * bold * test*bold*
		formatting = r'(?<!\w)' r'\*[^\s*]' r'([^*]*[^\s*])?' r'\*(?!\w)|'\
			r'(?<!\w|\<)' r'/[^\s/]' r'([^/]*[^\s/])?' r'/(?!\w)|'\
			r'(?<!\w)' r'_[^\s_]' r'([^_]*[^\s_])?' r'_(?!\w)'

		basic_pattern = links + mail + formatting
		self.basic_pattern_re = sre.compile(basic_pattern, sre.IGNORECASE)
		
		emoticons_pattern = ''
		if gajim.config.get('useemoticons'):
			# When an emoticon is bordered by an alpha-numeric character it is NOT
			# expanded.  e.g., foo:) NO, foo :) YES, (brb) NO, (:)) YES, etc.
			# We still allow multiple emoticons side-by-side like :P:P:P
			# sort keys by length so :qwe emot is checked before :q
			keys = self.emoticons.keys()
			keys.sort(self.on_emoticon_sort)
			emoticons_pattern_prematch = ''
			emoticons_pattern_postmatch = ''
			emoticon_length = 0
			for emoticon in keys: # travel thru emoticons list
				emoticon_escaped = sre.escape(emoticon) # espace regexp metachars
				emoticons_pattern += emoticon_escaped + '|'# | means or in regexp
				if (emoticon_length != len(emoticon)):
					# Build up expressions to match emoticons next to other emoticons
					emoticons_pattern_prematch  = emoticons_pattern_prematch[:-1]  + ')|(?<='
					emoticons_pattern_postmatch = emoticons_pattern_postmatch[:-1] + ')|(?='
					emoticon_length = len(emoticon)
				emoticons_pattern_prematch += emoticon_escaped  + '|'
				emoticons_pattern_postmatch += emoticon_escaped + '|'
			# We match from our list of emoticons, but they must either have
			# whitespace, or another emoticon next to it to match successfully
			# [\w.] alphanumeric and dot (for not matching 8) in (2.8))
			emoticons_pattern = '|' + \
				'(?:(?<![\w.]' + emoticons_pattern_prematch[:-1]   + '))' + \
				'(?:'       + emoticons_pattern[:-1]            + ')'  + \
				'(?:(?![\w.]'  + emoticons_pattern_postmatch[:-1]  + '))'
		
		# because emoticons match later (in the string) they need to be after
		# basic matches that may occur earlier
		emot_and_basic_pattern = basic_pattern + emoticons_pattern
		self.emot_and_basic_re = sre.compile(emot_and_basic_pattern, sre.IGNORECASE)
		
		# at least one character in 3 parts (before @, after @, after .)
		self.sth_at_sth_dot_sth_re = sre.compile(r'\S+@\S+\.\S*[^\s)?]')
		
		sre.purge() # clear the regular expression cache

	def on_emoticon_sort(self, emot1, emot2):
		len1 = len(emot1)
		len2 = len(emot2)
		if len1 < len2:
			return 1
		elif len1 > len2:
			return -1
		return 0

	def on_launch_browser_mailer(self, widget, url, kind):
		helpers.launch_browser_mailer(kind, url)

	def init_emoticons(self):
		if not gajim.config.get('useemoticons'):
			return
	
		#initialize emoticons dictionary and unique images list
		self.emoticons_images = list()
		self.emoticons = dict()
	
		emots = gajim.config.get_per('emoticons')
		for emot in emots:
			emot_file = gajim.config.get_per('emoticons', emot, 'path')
			if not self.image_is_ok(emot_file):
				continue
			# This avoids duplicated emoticons with the same image eg. :) and :-)
			if not emot_file in self.emoticons.values():
				pix = gtk.gdk.pixbuf_new_from_file(emot_file)
				if emot_file.endswith('.gif'):
					pix = gtk.gdk.PixbufAnimation(emot_file)
				self.emoticons_images.append((emot, pix))
			self.emoticons[emot.upper()] = emot_file
	
	def register_handlers(self):
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
			'AGENT_ERROR_INFO': self.handle_event_agent_info_error,
			'AGENT_ERROR_ITEMS': self.handle_event_agent_items_error,
			'REGISTER_AGENT_INFO': self.handle_event_register_agent_info,
			'AGENT_INFO_ITEMS': self.handle_event_agent_info_items,
			'AGENT_INFO_INFO': self.handle_event_agent_info_info,
			'QUIT': self.handle_event_quit,
			'ACC_OK': self.handle_event_acc_ok,
			'ACC_NOT_OK': self.handle_event_acc_not_ok,
			'MYVCARD': self.handle_event_myvcard,
			'VCARD': self.handle_event_vcard,
			'OS_INFO': self.handle_event_os_info,
			'GC_NOTIFY': self.handle_event_gc_notify,
			'GC_MSG': self.handle_event_gc_msg,
			'GC_SUBJECT': self.handle_event_gc_subject,
			'GC_CONFIG': self.handle_event_gc_config,
			'GC_INVITATION': self.handle_event_gc_invitation,
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
			'VCARD_PUBLISHED': self.handle_event_vcard_published,
			'VCARD_NOT_PUBLISHED': self.handle_event_vcard_not_published,
			'ASK_NEW_NICK': self.handle_event_ask_new_nick,
			'SIGNED_IN': self.handle_event_signed_in,
		}

	def exec_event(self, account):
		ev = gajim.events_for_ui[account].pop(0)
		self.handlers[ev[0]](account, ev[1])

	def process_connections(self):
		# We copy the list of connections because one can disappear while we 
		# process()
		accounts = []
		for account in gajim.connections:
			accounts.append(account)
		for account in accounts:
			if gajim.connections[account].connected:
				gajim.connections[account].process(0.01)
			if gajim.socks5queue.connected:
				gajim.socks5queue.process(0)
		for account in gajim.events_for_ui: #when we create a new account we don't have gajim.connection
			while len(gajim.events_for_ui[account]):
				gajim.mutex_events_for_ui.lock(self.exec_event, account)
				gajim.mutex_events_for_ui.unlock()
		time.sleep(0.01) # so threads in connection.py have time to run
		return True # renew timeout (loop for ever)

	def save_config(self):
		err_str = parser.write()
		if err_str is not None:
			print >> sys.stderr, err_str
			# it is good to notify the user
			# in case he or she cannot see the output of the console
			dialogs.ErrorDialog(_('Could not save your settings and preferences'),
				err_str).get_response()
			sys.exit()

	def __init__(self):
		gajim.interface = self
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
				gajim.config.set_per('emoticons', emot, 'path',
					gajim.config.emoticons_default[emot])
		#add default status messages if there is not in the config file
		if len(gajim.config.get_per('statusmsg')) == 0:
			for msg in gajim.config.statusmsg_default:
				gajim.config.add_per('statusmsg', msg)
				gajim.config.set_per('statusmsg', msg, 'message', 
					gajim.config.statusmsg_default[msg])
		#add default themes if there is not in the config file
		theme = gajim.config.get('roster_theme')
		if not theme in gajim.config.get_per('themes'):
			gajim.config.set('roster_theme', 'green')
		if len(gajim.config.get_per('themes')) == 0:
			d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
				'accountfontattrs', 'grouptextcolor', 'groupbgcolor', 'groupfont',
				'groupfontattrs', 'contacttextcolor', 'contactbgcolor', 
				'contactfont', 'contactfontattrs', 'bannertextcolor',
				'bannerbgcolor']
			
			default = gajim.config.themes_default
			for theme_name in default:
				gajim.config.add_per('themes', theme_name)
				theme = default[theme_name]
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
		self.register_handlers()
		for account in gajim.config.get_per('accounts'):
			gajim.connections[account] = common.connection.Connection(account)
															
		gtk.about_dialog_set_email_hook(self.on_launch_browser_mailer, 'mail')
		gtk.about_dialog_set_url_hook(self.on_launch_browser_mailer, 'url')
		
		self.instances = {'logs': {}}
		
		for a in gajim.connections:
			self.instances[a] = {'infos': {}, 'disco': {}, 'chats': {},
				'gc': {}, 'gc_config': {}}
			gajim.contacts[a] = {}
			gajim.groups[a] = {}
			gajim.gc_contacts[a] = {}
			gajim.gc_connected[a] = {}
			gajim.newly_added[a] = []
			gajim.to_be_removed[a] = []
			gajim.awaiting_events[a] = {}
			gajim.nicks[a] = gajim.config.get_per('accounts', a, 'name')
			gajim.allow_notifications[a] = False
			gajim.sleeper_state[a] = 0
			gajim.encrypted_chats[a] = []
			gajim.last_message_time[a] = {}
			gajim.status_before_autoaway[a] = ''
			gajim.events_for_ui[a] = []

		self.roster = roster_window.RosterWindow()
		
		if gajim.config.get('remote_control'):
			try:
				import remote_control
				self.remote_ctrl = remote_control.Remote()
			except (exceptions.DbusNotSupported, exceptions.SessionBusNotPresent):
				self.remote_ctrl = None
		else:
			self.remote_ctrl = None

		self.show_vcard_when_connect = []

		path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps/gajim.png')
		pix = gtk.gdk.pixbuf_new_from_file(path_to_file)
		gtk.window_set_default_icon(pix) # set the icon to all newly opened windows
		self.roster.window.set_icon_from_file(path_to_file) # and to roster window
		self.sleeper = common.sleepy.Sleepy(
			gajim.config.get('autoawaytime') * 60, # make minutes to seconds
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
				self.systray = systraywin32.SystrayWin32()
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
					self.systray = systray.Systray()
			else:
				self.systray_capabilities = True
				self.systray = systray.Systray()

		if self.systray_capabilities and gajim.config.get('trayicon'):
			self.show_systray()

		self.init_emoticons()
		self.make_regexps()
		
		# get instances for windows/dialogs that will show_all()/hide()
		self.instances['file_transfers'] = dialogs.FileTransfersWindow()
		self.instances['preferences'] = config.PreferencesWindow()
		
		for account in gajim.connections:
			self.instances[account]['xml_console'] = dialogs.XMLConsoleWindow(
				account)

		gobject.timeout_add(100, self.autoconnect)
		gobject.timeout_add(200, self.process_connections)
		gobject.timeout_add(500, self.read_sleepy)

def wait_migration(migration):
	if not migration.DONE:
		return True # loop for ever
	dialog.done(_('Logs have been successfully migrated to the database.'))
	dialog.dialog.run()
	dialog.dialog.destroy()
	gtk.main_quit()

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application

	try: # Import Psyco if available
		import psyco
		psyco.full()
	except ImportError:
		pass

	if os.name != 'nt':
		# Session Management support
		try:
			import gnome.ui
		except ImportError:
			print >> sys.stderr, _('Session Management support not available (missing gnome.ui module)')
		else:
			def die_cb(cli):
				gtk.main_quit()
			gnome.program_init('gajim', gajim.version)
			cli = gnome.ui.master_client()
			cli.connect('die', die_cb)
			
			path_to_gajim_script = gtkgui_helpers.get_abspath_for_script('gajim')
			
			if path_to_gajim_script:
				argv = [path_to_gajim_script]
				# FIXME: remove this typeerror catch when gnome python is old and
				# not bad patched by distro men [2.12.0 + should not need all that
				# NORMALLY]
				try:
					cli.set_restart_command(argv)
				except TypeError:
					cli.set_restart_command(len(argv), argv)
	
		# register (by default only the first time) xmmpi: to Gajim
		try:
			import gconf
			# in try because daemon may not be there
			client = gconf.client_get_default()
		
			we_set = False
			if gajim.config.get('set_xmpp://_handler_everytime'):
				we_set = True
			elif client.get_string('/desktop/gnome/url-handlers/xmpp/command') is None:
				we_set = True
			
			if we_set:
				path_to_gajim_script, type = gtkgui_helpers.get_abspath_for_script(
					'gajim-remote', True)
				if path_to_gajim_script:
					if type == 'svn':
						command = path_to_gajim_script + ' open_chat %s'
					else: # 'installed'
						command = 'gajim-remote open_chat %s'
					client.set_bool('/desktop/gnome/url-handlers/xmpp/enabled', True)
					client.set_string('/desktop/gnome/url-handlers/xmpp/command', command)
					client.set_bool('/desktop/gnome/url-handlers/xmpp/needs_terminal', False)
		except:
			pass
	
	# Migrate old logs if we have such olds logs
	from common import logger
	LOG_DB_PATH = logger.LOG_DB_PATH
	if not os.path.exists(LOG_DB_PATH):
		from common import migrate_logs_to_dot9_db
		if os.path.isdir(migrate_logs_to_dot9_db.PATH_TO_LOGS_BASE_DIR):
			import Queue
			q = Queue.Queue(100)
			m = migrate_logs_to_dot9_db.Migration()
			dialog = dialogs.ProgressDialog(_('Migrating Logs...'), _('Please wait while logs are being migrated...'), q)
			t = threading.Thread(target = m.migrate, args = (q,))
			t.start()
			gobject.timeout_add(500, wait_migration, m)
			gtk.main()
			# Init logger values (self.con/cur, jid_already_in)
			gajim.logger.init_vars()
	check_paths.check_and_possibly_create_paths()

	Interface()
	gtk.main()
