#!/usr/bin/env python
##	gajim.py
##
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov@gmail.com>
## Copyright (C) 2005 Travis Shirk <travis@pobox.com>
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
import urllib

import logging
consoleloghandler = logging.StreamHandler()
consoleloghandler.setLevel(1)
consoleloghandler.setFormatter(
logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s'))
log = logging.getLogger('gajim')
log.setLevel(logging.WARNING)
log.addHandler(consoleloghandler)
log.propagate = False
log = logging.getLogger('gajim.gajim')

# create intermediate loggers
logging.getLogger('gajim.c')
logging.getLogger('gajim.c.x')

import getopt
from common import i18n

def parseLogLevel(arg):
	if arg.isdigit():
		return int(arg)
	if arg.isupper():
		return getattr(logging, arg)
	raise ValueError(_("%s is not a valid loglevel"), repr(arg))

def parseLogTarget(arg):
	arg = arg.lower()
	if arg.startswith('.'): return arg[1:]
	if arg.startswith('gajim'): return arg
	return 'gajim.' + arg

def parseAndSetLogLevels(arg):
	for directive in arg.split(','):
		directive = directive.strip()
		targets, level = directive.rsplit('=', 1)
		level = parseLogLevel(level.strip())
		for target in targets.split('='):
			target = parseLogTarget(target.strip())
			if target == '':
				consoleloghandler.setLevel(level)
				print "consoleloghandler level set to %s" % level
			else:
				logger = logging.getLogger(target)
				logger.setLevel(level)
				print "Logger %s level set to %d" % (target, level)

def parseOpts():
	profile = ''
	verbose = False

	try:
		shortargs = 'hqvl:p:'
		longargs = 'help quiet verbose loglevel= profile='
		opts, args = getopt.getopt(sys.argv[1:], shortargs, longargs.split())
	except getopt.error, msg:
		print msg
		print 'for help use --help'
		sys.exit(2)
	for o, a in opts:
		if o in ('-h', '--help'):
			print 'gajim [--help] [--quiet] [--verbose] [--loglevel subsystem=level[,subsystem=level[...]]] [--profile name]'
			sys.exit()
		elif o in ('-q', '--quiet'):
			consoleloghandler.setLevel(logging.CRITICAL)
			verbose = False
		elif o in ('-v', '--verbose'):
			consoleloghandler.setLevel(logging.INFO)
			verbose = True
		elif o in ('-p', '--profile'): # gajim --profile name
			profile = a
		elif o in ('-l', '--loglevel'):
			parseAndSetLogLevels(a)
	return profile, verbose

profile, verbose = parseOpts()
del parseOpts, parseAndSetLogLevels, parseLogTarget, parseLogLevel

import message_control

from chat_control import ChatControlBase
from atom_window import AtomWindow

import negotiation

from common import exceptions
from common.zeroconf import connection_zeroconf
from common import dbus_support

if os.name == 'posix': # dl module is Unix Only
	try: # rename the process name to gajim
		import dl
		libc = dl.open('/lib/libc.so.6')
		libc.call('prctl', 15, 'gajim\0', 0, 0, 0)
	except:
		pass

try:
	import gtk
except RuntimeError, msg:
	if str(msg) == 'could not open display':
		print >> sys.stderr, _('Gajim needs X server to run. Quiting...')
		sys.exit()
pritext = ''
if gtk.pygtk_version < (2, 8, 0):
	pritext = _('Gajim needs PyGTK 2.8 or above')
	sectext = _('Gajim needs PyGTK 2.8 or above to run. Quiting...')
elif gtk.gtk_version < (2, 8, 0):
	pritext = _('Gajim needs GTK 2.8 or above')
	sectext = _('Gajim needs GTK 2.8 or above to run. Quiting...')

try:
	import gtk.glade # check if user has libglade (in pygtk and in gtk)
except ImportError:
	pritext = _('GTK+ runtime is missing libglade support')
	if os.name == 'nt':
		sectext = _('Please remove your current GTK+ runtime and install the latest stable version from %s') % 'http://gladewin32.sourceforge.net'
	else:
		sectext = _('Please make sure that GTK+ and PyGTK have libglade support in your system.')

try:
	from common import check_paths
except exceptions.PysqliteNotAvailable, e:
	pritext = _('Gajim needs PySQLite2 to run')
	sectext = str(e)

if os.name == 'nt':
	try:
		import winsound # windows-only built-in module for playing wav
		import win32api # do NOT remove. we req this module
	except:
		pritext = _('Gajim needs pywin32 to run')
		sectext = _('Please make sure that Pywin32 is installed on your system. You can get it at %s') % 'http://sourceforge.net/project/showfiles.php?group_id=78018'

if pritext:
	dlg = gtk.MessageDialog(None, 
		gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
		gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, message_format = pritext)

	dlg.format_secondary_text(sectext)
	dlg.run()
	dlg.destroy()
	sys.exit()

del pritext

path = os.getcwd()
if '.svn' in os.listdir(path) or '_svn' in os.listdir(path):
	# import gtkexcepthook only for those that run svn
	# those than run with --verbose run from terminal so no need to care
	# about those
	import gtkexcepthook
del path

import gobject

import re
import signal
import getopt
import time
import math

import gtkgui_helpers
import notify

import common.sleepy

from common.xmpp import idlequeue
from common import nslookup
from common import proxy65_manager
from common import socks5
from common import gajim
from common import helpers
from common import optparser

if verbose: gajim.verbose = True
del verbose

import locale
profile = unicode(profile, locale.getpreferredencoding())

import common.configpaths
common.configpaths.init_profile(profile)
del profile
gajimpaths = common.configpaths.gajimpaths

pid_filename = gajimpaths['PID_FILE']
config_filename = gajimpaths['CONFIG_FILE']

import traceback
import errno

import dialogs
def pid_alive():
	try:
		pf = open(pid_filename)
	except:
		# probably file not found
		return False

	try:
		pid = int(pf.read().strip())
		pf.close()
	except:
		traceback.print_exc()
		# PID file exists, but something happened trying to read PID
		# Could be 0.10 style empty PID file, so assume Gajim is running
		return True

	if os.name == 'nt':
		try:
			from ctypes import (windll, c_ulong, c_int, Structure, c_char, POINTER, pointer, )
		except:
			return True

		class PROCESSENTRY32(Structure):
			_fields_ = [
				('dwSize', c_ulong, ),
				('cntUsage', c_ulong, ),
				('th32ProcessID', c_ulong, ),
				('th32DefaultHeapID', c_ulong, ),
				('th32ModuleID', c_ulong, ),
				('cntThreads', c_ulong, ),
				('th32ParentProcessID', c_ulong, ),
				('pcPriClassBase', c_ulong, ),
				('dwFlags', c_ulong, ),
				('szExeFile', c_char*512, ),
				]
			def __init__(self):
				Structure.__init__(self, 512+9*4)

		k = windll.kernel32
		k.CreateToolhelp32Snapshot.argtypes = c_ulong, c_ulong,
		k.CreateToolhelp32Snapshot.restype = c_int
		k.Process32First.argtypes = c_int, POINTER(PROCESSENTRY32),
		k.Process32First.restype = c_int
		k.Process32Next.argtypes = c_int, POINTER(PROCESSENTRY32),
		k.Process32Next.restype = c_int

		def get_p(p):
			h = k.CreateToolhelp32Snapshot(2, 0) # TH32CS_SNAPPROCESS
			assert h > 0, 'CreateToolhelp32Snapshot failed'
			b = pointer(PROCESSENTRY32())
			f = k.Process32First(h, b)
			while f:
				if b.contents.th32ProcessID == p:
					return b.contents.szExeFile
				f = k.Process32Next(h, b)

		if get_p(pid) in ('python.exe', 'gajim.exe'):
			return True
		return False
	try:
		if not os.path.exists('/proc'):
			return True # no /proc, assume Gajim is running

		try:
			f = open('/proc/%d/cmdline'% pid) 
		except IOError, e:
			if e.errno == errno.ENOENT:
				return False # file/pid does not exist
			raise 

		n = f.read().lower()
		f.close()
		if n.find('gajim') < 0:
			return False
		return True # Running Gajim found at pid
	except:
		traceback.print_exc()

	# If we are here, pidfile exists, but some unexpected error occured.
	# Assume Gajim is running.
	return True

if pid_alive():
	path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps/gajim.png')
	pix = gtk.gdk.pixbuf_new_from_file(path_to_file)
	gtk.window_set_default_icon(pix) # set the icon to all newly opened wind
	pritext = _('Gajim is already running')
	sectext = _('Another instance of Gajim seems to be running\nRun anyway?')
	dialog = dialogs.YesNoDialog(pritext, sectext)
	if dialog.get_response() != gtk.RESPONSE_YES:
		sys.exit(3)
	# run anyway, delete pid and useless global vars
	if os.path.exists(pid_filename):
		os.remove(pid_filename)
	del path_to_file
	del pix
	del pritext
	del sectext
	dialog.destroy()

# Create .gajim dir
pid_dir =  os.path.dirname(pid_filename)
if not os.path.exists(pid_dir):
	check_paths.create_path(pid_dir)
# Create pid file
f = open(pid_filename, 'w')
f.write(str(os.getpid()))
f.close()
del pid_dir
del f

def on_exit():
	# delete pid file on normal exit
	if os.path.exists(pid_filename):
		os.remove(pid_filename)

import atexit
atexit.register(on_exit)

parser = optparser.OptionsParser(config_filename)

import roster_window
import profile_window
import config

class GlibIdleQueue(idlequeue.IdleQueue):
	''' 
	Extends IdleQueue to use glib io_add_wath, instead of select/poll
	In another, `non gui' implementation of Gajim IdleQueue can be used safetly.
	'''
	def init_idle(self):
		''' this method is called at the end of class constructor.
		Creates a dict, which maps file/pipe/sock descriptor to glib event id'''
		self.events = {}
		# time() is already called in glib, we just get the last value 
		# overrides IdleQueue.current_time()
		self.current_time = lambda: gobject.get_current_time()
			
	def add_idle(self, fd, flags):
		''' this method is called when we plug a new idle object.
		Start listening for events from fd
		'''
		res = gobject.io_add_watch(fd, flags, self.process_events, 
			priority=gobject.PRIORITY_LOW)
		# store the id of the watch, so that we can remove it on unplug
		self.events[fd] = res
	
	def remove_idle(self, fd):
		''' this method is called when we unplug a new idle object.
		Stop listening for events from fd
		'''
		gobject.source_remove(self.events[fd])
		del(self.events[fd])
	
	def process(self):
		self.check_time_events()
	
class Interface:
	def handle_event_roster(self, account, data):
		#('ROSTER', account, array)
		self.roster.fill_contacts_and_groups_dicts(data, account)
		self.roster.add_account_contacts(account)
		self.roster.fire_up_unread_messages_events(account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Roster', (account, data))

	def handle_event_warning(self, unused, data):
		#('WARNING', account, (title_text, section_text))
		dialogs.WarningDialog(data[0], data[1])

	def handle_event_error(self, unused, data):
		#('ERROR', account, (title_text, section_text))
		dialogs.ErrorDialog(data[0], data[1])

	def handle_event_information(self, unused, data):
		#('INFORMATION', account, (title_text, section_text))
		dialogs.InformationDialog(data[0], data[1])
		
	def handle_event_ask_new_nick(self, account, data):
		#('ASK_NEW_NICK', account, (room_jid, title_text, prompt_text, proposed_nick))
		room_jid = data[0]
		title = data[1]
		prompt = data[2]
		proposed_nick = data[3]
		gc_control = self.msg_win_mgr.get_control(room_jid, account)
		if gc_control: # user may close the window before we are here
			gc_control.show_change_nick_input_dialog(title, prompt, proposed_nick)

	def handle_event_http_auth(self, account, data):
		#('HTTP_AUTH', account, (method, url, transaction_id, iq_obj, msg))
		def response(widget, account, iq_obj, answer):
			self.dialog.destroy()
			gajim.connections[account].build_http_auth_answer(iq_obj, answer)

		sec_msg = _('Do you accept this request?')
		if data[4]:
			sec_msg = data[4] + '\n' + sec_msg
		self.dialog = dialogs.YesNoDialog(_('HTTP (%s) Authorization for %s (id: %s)') \
			% (data[0], data[1], data[2]), sec_msg,
			on_response_yes = (response, account, data[3], 'yes'),
			on_response_no = (response, account, data[3], 'no'))

	def handle_event_error_answer(self, account, array):
		#('ERROR_ANSWER', account, (id, jid_from, errmsg, errcode))
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
					(jid_from, file_props, errmsg))
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
		ctrl = self.msg_win_mgr.get_control(jid_from, account)
		if ctrl and ctrl.type_id == message_control.TYPE_GC:
			ctrl.print_conversation('Error %s: %s' % (array[2], array[1]))

	def handle_event_con_type(self, account, con_type):
		# ('CON_TYPE', account, con_type) which can be 'ssl', 'tls', 'tcp'
		gajim.con_types[account] = con_type
		self.roster.draw_account(account)

	def handle_event_connection_lost(self, account, array):
		# ('CONNECTION_LOST', account, [title, text])
		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
			'connection_lost.png')
		path = gtkgui_helpers.get_path_to_generic_or_avatar(path)
		notify.popup(_('Connection Failed'), account, account,
			'connection_failed', path, array[0], array[1])

	def unblock_signed_in_notifications(self, account):
		gajim.block_signed_in_notifications[account] = False

	def handle_event_status(self, account, status): # OUR status
		#('STATUS', account, status)
		model = self.roster.status_combobox.get_model()
		if status == 'offline':
			# sensitivity for this menuitem
			if gajim.get_number_of_connected_accounts() == 0:
				model[self.roster.status_message_menuitem_iter][3] = False
			gajim.block_signed_in_notifications[account] = True
		else:
			# 30 seconds after we change our status to sth else than offline
			# we stop blocking notifications of any kind
			# this prevents from getting the roster items as 'just signed in'
			# contacts. 30 seconds should be enough time
			gobject.timeout_add(30000, self.unblock_signed_in_notifications, account)
			# sensitivity for this menuitem
			model[self.roster.status_message_menuitem_iter][3] = True

		# Inform all controls for this account of the connection state change
		for ctrl in self.msg_win_mgr.get_controls():
			if ctrl.account == account:
				if status == 'offline' or (status == 'invisible' and \
						gajim.connections[account].is_zeroconf):
					ctrl.got_disconnected()
				else:
					# Other code rejoins all GCs, so we don't do it here
					if not ctrl.type_id == message_control.TYPE_GC:
						ctrl.got_connected()
				ctrl.parent_win.redraw_tab(ctrl)

		self.roster.on_status_changed(account, status)
		if account in self.show_vcard_when_connect:
			self.edit_own_details(account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('AccountPresence', (status, account))
	
	def edit_own_details(self, account):
		jid = gajim.get_jid_from_account(account)
		if not self.instances[account].has_key('profile'):
			self.instances[account]['profile'] = \
				profile_window.ProfileWindow(account)
			gajim.connections[account].request_vcard(jid)

	def handle_event_notify(self, account, array):
		# 'NOTIFY' (account, (jid, status, status message, resource, priority,
		# keyID, timestamp, contact_nickname))
		# if we're here it means contact changed show
		statuss = ['offline', 'error', 'online', 'chat', 'away', 'xa', 'dnd',
			'invisible']
		# Ignore invalid show
		if array[1] not in statuss:
			return
		old_show = 0
		new_show = statuss.index(array[1])
		status_message = array[2]
		jid = array[0].split('/')[0]
		keyID = array[5]
		contact_nickname = array[7]
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		if jid in attached_keys:
			keyID = attached_keys[attached_keys.index(jid) + 1]
		resource = array[3]
		if not resource:
			resource = ''
		priority = array[4]
		if gajim.jid_is_transport(jid):
			# It must be an agent
			ji = jid.replace('@', '')
		else:
			ji = jid

		# Update contact
		jid_list = gajim.contacts.get_jid_list(account)
		if ji in jid_list or jid == gajim.get_jid_from_account(account):
			lcontact = gajim.contacts.get_contacts_from_jid(account, ji)
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
				if contact_nickname is not None and \
				contact1.contact_name != contact_nickname:
					contact1.contact_name = contact_nickname
					self.roster.draw_contact(jid, account)
				if old_show == new_show and contact1.status == status_message and \
				contact1.priority == priority: # no change
					return
			else:
				contact1 = gajim.contacts.get_first_contact_from_jid(account, ji)
				if not contact1:
					# presence of another resource of our jid
					if resource == gajim.connections[account].server_resource:
						return
					contact1 = gajim.contacts.create_contact(jid = ji,
						name = gajim.nicks[account], groups = [],
						show = array[1], status = status_message, sub = 'both',
						ask = 'none', priority = priority, keyID = keyID,
						resource = resource)
					old_show = 0
					gajim.contacts.add_contact(account, contact1)
					lcontact.append(contact1)
					self.roster.add_self_contact(account)
				elif contact1.show in statuss:
					old_show = statuss.index(contact1.show)
				if (resources != [''] and (len(lcontact) != 1 or 
				lcontact[0].show != 'offline')) and jid.find('@') > 0:
					old_show = 0
					contact1 = gajim.contacts.copy_contact(contact1)
					lcontact.append(contact1)
				contact1.resource = resource
			if contact1.jid.find('@') > 0 and len(lcontact) == 1:
				# It's not an agent
				if old_show == 0 and new_show > 1:
					if not contact1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].append(contact1.jid)
					if contact1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].remove(contact1.jid)
					gobject.timeout_add(5000, self.roster.remove_newly_added,
						contact1.jid, account)
				elif old_show > 1 and new_show == 0 and gajim.connections[account].\
					connected > 1:
					if not contact1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].append(contact1.jid)
					if contact1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].remove(contact1.jid)
					self.roster.draw_contact(contact1.jid, account)
					gobject.timeout_add(5000, self.roster.really_remove_contact,
						contact1, account)
			contact1.show = array[1]
			contact1.status = status_message
			contact1.priority = priority
			contact1.keyID = keyID
			timestamp = array[6]
			if timestamp:
				contact1.last_status_time = timestamp
			elif not gajim.block_signed_in_notifications[account]:
				# We're connected since more that 30 seconds
				contact1.last_status_time = time.localtime()
			contact1.contact_nickname = contact_nickname
		if gajim.jid_is_transport(jid):
			# It must be an agent
			if ji in jid_list:
				# Update existing iter
				self.roster.draw_contact(ji, account)
				self.roster.draw_group(_('Transports'), account)
				if new_show > 1 and ji in gajim.transport_avatar[account]:
					# transport just signed in. request avatars
					for jid_ in gajim.transport_avatar[account][ji]:
						gajim.connections[account].request_vcard(jid_)
				# transport just signed in/out, don't show popup notifications
				# for 30s
				account_ji = account + '/' + ji
				gajim.block_signed_in_notifications[account_ji] = True
				gobject.timeout_add(30000, self.unblock_signed_in_notifications,
					account_ji)
			locations = (self.instances, self.instances[account])
			for location in locations:
				if location.has_key('add_contact'):
					if old_show == 0 and new_show > 1:
						location['add_contact'].transport_signed_in(jid)
						break
					elif old_show > 1 and new_show == 0:
						location['add_contact'].transport_signed_out(jid)
						break
		elif ji in jid_list:
			# It isn't an agent
			# reset chatstate if needed:
			# (when contact signs out or has errors)
			if array[1] in ('offline', 'error'):
				contact1.our_chatstate = contact1.chatstate = \
					contact1.composing_jep = None
				gajim.connections[account].remove_transfers_for_contact(contact1)
			self.roster.chg_contact_status(contact1, array[1], status_message,
				account)
			# Notifications
			if old_show < 2 and new_show > 1:
				notify.notify('contact_connected', jid, account, status_message)
				if self.remote_ctrl:
					self.remote_ctrl.raise_signal('ContactPresence',
						(account, array))

			elif old_show > 1 and new_show < 2:
				notify.notify('contact_disconnected', jid, account, status_message)
				if self.remote_ctrl:
					self.remote_ctrl.raise_signal('ContactAbsence', (account, array))
				# FIXME: stop non active file transfers
			elif new_show > 1: # Status change (not connected/disconnected or error (<1))
				notify.notify('status_change', jid, account, [new_show,
					status_message])
		else:
			# FIXME: Msn transport (CMSN1.2.1 and PyMSN0.10) doesn't follow the JEP
			# remove in 2007
			# It's maybe a GC_NOTIFY (specialy for MSN gc)
			self.handle_event_gc_notify(account, (jid, array[1], status_message,
				array[3], None, None, None, None, None, None, None, None))


	def handle_event_msg(self, account, array):
		# 'MSG' (account, (jid, msg, time, encrypted, msg_type, subject,
		# chatstate, msg_id, composing_jep, user_nick, xhtml, session))
		# user_nick is JEP-0172

		full_jid_with_resource = array[0]
		jid = gajim.get_jid_without_resource(full_jid_with_resource)
		resource = gajim.get_resource_from_jid(full_jid_with_resource)

		message = array[1]
		encrypted = array[3]
		msg_type = array[4]
		subject = array[5]
		chatstate = array[6]
		msg_id = array[7]
		composing_jep = array[8]
		xhtml = array[10]
		session = array[11]
		if gajim.config.get('ignore_incoming_xhtml'):
			xhtml = None
		if gajim.jid_is_transport(jid):
			jid = jid.replace('@', '')

		groupchat_control = self.msg_win_mgr.get_control(jid, account)
		if not groupchat_control and \
		gajim.interface.minimized_controls.has_key(account) and \
		jid in gajim.interface.minimized_controls[account]:
			groupchat_control = gajim.interface.minimized_controls[account][jid]
		pm = False
		if groupchat_control and groupchat_control.type_id == \
		message_control.TYPE_GC:
			# It's a Private message
			pm = True
			msg_type = 'pm'

		chat_control = None
		jid_of_control = full_jid_with_resource
		highest_contact = gajim.contacts.get_contact_with_highest_priority(
			account, jid)
		# Look for a chat control that has the given resource, or default to one
		# without resource
		ctrl = self.msg_win_mgr.get_control(full_jid_with_resource, account)
		if ctrl:
			chat_control = ctrl
		elif not pm and (not highest_contact or not highest_contact.resource):
			# unknow contact or offline message
			jid_of_control = jid
			chat_control = self.msg_win_mgr.get_control(jid, account)
		elif highest_contact and resource != highest_contact.resource and \
		highest_contact.show != 'offline':
			jid_of_control = full_jid_with_resource
			chat_control = None
		elif not pm:
			jid_of_control = jid
			chat_control = self.msg_win_mgr.get_control(jid, account)

		# Handle chat states  
		contact = gajim.contacts.get_contact(account, jid, resource)
		if contact and isinstance(contact, list):
			contact = contact[0]
		if contact:
			if contact.composing_jep != 'JEP-0085': # We cache xep85 support
				contact.composing_jep = composing_jep
			if chat_control and chat_control.type_id == message_control.TYPE_CHAT:
				if chatstate is not None:
					# other peer sent us reply, so he supports jep85 or jep22
					contact.chatstate = chatstate
					if contact.our_chatstate == 'ask': # we were jep85 disco?
						contact.our_chatstate = 'active' # no more
					chat_control.handle_incoming_chatstate()
				elif contact.chatstate != 'active':
					# got no valid jep85 answer, peer does not support it
					contact.chatstate = False
			elif chatstate == 'active':
				# Brand new message, incoming.  
				contact.our_chatstate = chatstate
				contact.chatstate = chatstate
				if msg_id: # Do not overwrite an existing msg_id with None
					contact.msg_id = msg_id

		# THIS MUST BE AFTER chatstates handling
		# AND BEFORE playsound (else we ear sounding on chatstates!)
		if not message: # empty message text
			return

		if gajim.config.get('ignore_unknown_contacts') and \
			not gajim.contacts.get_contact(account, jid) and not pm:
			return
		if not contact:
			# contact is not in the roster, create a fake one to display
			# notification
			contact = common.contacts.Contact(jid = jid, resource = resource) 
		advanced_notif_num = notify.get_advanced_notification('message_received',
			account, contact)

		# Is it a first or next message received ?
		first = False
		if msg_type == 'normal':
			if not gajim.events.get_events(account, jid, ['normal']):
				first = True
		elif not chat_control and not gajim.events.get_events(account, 
		jid_of_control, [msg_type]): # msg_type can be chat or pm
			first = True

		if pm:
			nickname = resource
			groupchat_control.on_private_message(nickname, message, array[2],
				xhtml)
		else:
			# array: (jid, msg, time, encrypted, msg_type, subject)
			if encrypted:
				self.roster.on_message(jid, message, array[2], account, array[3],
					msg_type, subject, resource, msg_id, array[9],
					advanced_notif_num, session = session)
			else:
				# xhtml in last element
				self.roster.on_message(jid, message, array[2], account, array[3],
					msg_type, subject, resource, msg_id, array[9],
					advanced_notif_num, xhtml = xhtml, session = session)
			nickname = gajim.get_name_from_jid(account, jid)
		# Check and do wanted notifications
		msg = message
		if subject:
			msg = _('Subject: %s') % subject + '\n' + msg
		notify.notify('new_message', jid_of_control, account, [msg_type,
			first, nickname, msg], advanced_notif_num)

		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('NewMessage', (account, array))

	def handle_event_msgerror(self, account, array):
		#'MSGERROR' (account, (jid, error_code, error_msg, msg, time))
		full_jid_with_resource = array[0]
		jids = full_jid_with_resource.split('/', 1)
		jid = jids[0]
		gc_control = self.msg_win_mgr.get_control(jid, account)
		if gc_control and gc_control.type_id != message_control.TYPE_GC:
			gc_control = None
		if gc_control:
			if len(jids) > 1: # it's a pm
				nick = jids[1]
				if not self.msg_win_mgr.get_control(full_jid_with_resource,
				account):
					tv = gc_control.list_treeview
					model = tv.get_model()
					iter = gc_control.get_contact_iter(nick)
					if iter:
						show = model[iter][3]
					else:
						show = 'offline'
					gc_c = gajim.contacts.create_gc_contact(room_jid = jid,
						name = nick, show = show)
					self.roster.new_private_chat(gc_c, account)
				ctrl = self.msg_win_mgr.get_control(full_jid_with_resource, account)
				ctrl.print_conversation('Error %s: %s' % (array[1], array[2]),
							'status')
				return

			gc_control.print_conversation('Error %s: %s' % (array[1], array[2]))
			if gc_control.parent_win.get_active_jid() == jid:
				gc_control.set_subject(gc_control.subject)
			return

		if gajim.jid_is_transport(jid):
			jid = jid.replace('@', '')
		msg = array[2]
		if array[3]:
			msg = _('error while sending %s ( %s )') % (array[3], msg)
		self.roster.on_message(jid, msg, array[4], account, \
			msg_type='error')
		
	def handle_event_msgsent(self, account, array):
		#('MSGSENT', account, (jid, msg, keyID))
		msg = array[1]
		# do not play sound when standalone chatstate message (eg no msg)
		if msg and gajim.config.get_per('soundevents', 'message_sent', 'enabled'):
			helpers.play_sound('message_sent')

	def handle_event_msgnotsent(self, account, array):
		#('MSGNOTSENT', account, (jid, ierror_msg, msg, time))
		msg = _('error while sending %s ( %s )') % (array[2], array[1])
		self.roster.on_message(array[0], msg, array[3], account,
			msg_type='error')

	def handle_event_subscribe(self, account, array):
		#('SUBSCRIBE', account, (jid, text, user_nick)) user_nick is JEP-0172
		dialogs.SubscriptionRequestWindow(array[0], array[1], account, array[2])
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Subscribe', (account, array))

	def handle_event_subscribed(self, account, array):
		#('SUBSCRIBED', account, (jid, resource))
		jid = array[0]
		if jid in gajim.contacts.get_jid_list(account):
			c = gajim.contacts.get_first_contact_from_jid(account, jid)
			c.resource = array[1]
			self.roster.remove_contact(c, account)
			if _('Not in Roster') in c.groups:
				c.groups.remove(_('Not in Roster'))
			self.roster.add_contact_to_roster(c.jid, account)
		else:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			name = jid.split('@', 1)[0]
			name = name.split('%', 1)[0]
			contact1 = gajim.contacts.create_contact(jid = jid, name = name,
				groups = [], show = 'online', status = 'online',
				ask = 'to', resource = array[1], keyID = keyID)
			gajim.contacts.add_contact(account, contact1)
			self.roster.add_contact_to_roster(jid, account)
		dialogs.InformationDialog(_('Authorization accepted'),
				_('The contact "%s" has authorized you to see his or her status.')
				% jid)
		if not gajim.config.get_per('accounts', account, 'dont_ack_subscription'):
			gajim.connections[account].ack_subscribed(jid)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Subscribed', (account, array))

	def handle_event_unsubscribed(self, account, jid):
		dialogs.InformationDialog(_('Contact "%s" removed subscription from you')\
			% jid, _('You will always see him or her as offline.'))
		# FIXME: Per RFC 3921, we can "deny" ack as well, but the GUI does not show deny
		gajim.connections[account].ack_unsubscribed(jid)
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

	def handle_event_agent_removed(self, account, agent):
		# remove transport's contacts from treeview
		jid_list = gajim.contacts.get_jid_list(account)
		for jid in jid_list:
			if jid.endswith('@' + agent):
				c = gajim.contacts.get_first_contact_from_jid(account, jid)
				gajim.log.debug(
					'Removing contact %s due to unregistered transport %s'\
					% (jid, agent))
				gajim.connections[account].unsubscribe(c.jid)
				# Transport contacts can't have 2 resources
				if c.jid in gajim.to_be_removed[account]:
					# This way we'll really remove it
					gajim.to_be_removed[account].remove(c.jid)
				gajim.contacts.remove_jid(account, c.jid)
				self.roster.remove_contact(c, account)

	def handle_event_register_agent_info(self, account, array):
		# ('REGISTER_AGENT_INFO', account, (agent, infos, is_form))
		# info in a dataform if is_form is True
		if array[2] or array[1].has_key('instructions'):
			config.ServiceRegistrationWindow(array[0], array[1], account,
				array[2])
		else:
			dialogs.ErrorDialog(_('Contact with "%s" cannot be established') \
				% array[0], _('Check your connection or try again later.'))

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
		if array.has_key('NICKNAME') and array['NICKNAME']:
			gajim.nicks[account] = array['NICKNAME']
		elif array.has_key('FN') and array['FN']:
			gajim.nicks[account] = array['FN']
		if self.instances[account].has_key('profile'):
			win = self.instances[account]['profile']
			win.set_values(array)
			if account in self.show_vcard_when_connect:
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
		ctrl = None
		if resource and self.msg_win_mgr.has_window(
		jid + '/' + resource, account):
			win = self.msg_win_mgr.get_window(jid + '/' + resource,
				account)
			ctrl = win.get_control(jid + '/' + resource, account)
		elif self.msg_win_mgr.has_window(jid, account):
			win = self.msg_win_mgr.get_window(jid, account)
			ctrl = win.get_control(jid, account)
		if win and ctrl.type_id != message_control.TYPE_GC:
			ctrl.show_avatar()

		# Show avatar in roster or gc_roster
		gc_ctrl = self.msg_win_mgr.get_control(jid, account)
		if gc_ctrl and gc_ctrl.type_id == message_control.TYPE_GC:
			gc_ctrl.draw_avatar(resource)
		else:
			self.roster.draw_avatar(jid, account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('VcardInfo', (account, vcard))

	def handle_event_last_status_time(self, account, array):
		# ('LAST_STATUS_TIME', account, (jid, resource, seconds, status))
		win = None
		if self.instances[account]['infos'].has_key(array[0]):
			win = self.instances[account]['infos'][array[0]]
		elif self.instances[account]['infos'].has_key(array[0] + '/' + array[1]):
			win = self.instances[account]['infos'][array[0] + '/' + array[1]]
		if win:
			c = gajim.contacts.get_contact(account, array[0], array[1])
			# c is a list when no resource is given. it probably means that contact
			# is offline, so only on Contact instance
			if isinstance(c, list) and len(c):
				c = c[0]
			if c: # c can be none if it's a gc contact
				c.last_status_time = time.localtime(time.time() - array[2])
				if array[3]:
					c.status = array[3]
				win.set_last_status_time()
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('LastStatusTime', (account, array))

	def handle_event_os_info(self, account, array):
		#'OS_INFO' (account, (jid, resource, client_info, os_info))
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
		#'GC_NOTIFY' (account, (room_jid, show, status, nick,
		# role, affiliation, jid, reason, actor, statusCode, newNick, avatar_sha))
		nick = array[3]
		if not nick:
			return
		room_jid = array[0]
		fjid = room_jid + '/' + nick
		show = array[1]
		status = array[2]

		# Get the window and control for the updated status, this may be a
		# PrivateChatControl
		control = self.msg_win_mgr.get_control(room_jid, account)
		if not control and \
		self.minimized_controls.has_key(account) and \
		room_jid in self.minimized_controls[account]:
			control = self.minimized_controls[account][room_jid]

		if control and control.type_id != message_control.TYPE_GC:
			return
		if control:
			control.chg_contact_status(nick, show, status, array[4], array[5],
				array[6], array[7], array[8], array[9], array[10], array[11])
		if control and not control.parent_win:
			gajim.interface.roster.draw_contact(room_jid, account)

		ctrl = self.msg_win_mgr.get_control(fjid, account)

		# print status in chat window and update status/GPG image
		if ctrl:
			contact = ctrl.contact
			contact.show = show
			contact.status = status
			uf_show = helpers.get_uf_show(show)
			if status:
				ctrl.print_conversation(_('%s is now %s (%s)') % (nick, uf_show,
					status), 'status')
			else:
				ctrl.print_conversation(_('%s is now %s') % (nick, uf_show),
					'status')
			ctrl.parent_win.redraw_tab(ctrl)
			ctrl.update_ui()
			if self.remote_ctrl:
				self.remote_ctrl.raise_signal('GCPresence', (account, array))

	def handle_event_gc_msg(self, account, array):
		# ('GC_MSG', account, (jid, msg, time, has_timestamp, htmlmsg))
		jids = array[0].split('/', 1)
		room_jid = jids[0]

		gc_control = self.msg_win_mgr.get_control(room_jid, account)
		if not gc_control and \
		self.minimized_controls.has_key(account) and \
		room_jid in self.minimized_controls[account]:
			gc_control = self.minimized_controls[account][room_jid]

		if not gc_control:
			return
		xhtml = array[4]

		if gajim.config.get('ignore_incoming_xhtml'):
			xhtml = None
		if len(jids) == 1:
			# message from server
			nick = ''
		else:
			# message from someone
			nick = jids[1]

		gc_control.on_message(nick, array[1], array[2], array[3], xhtml)

		contact = gajim.contacts.\
			get_contact_with_highest_priority(account, room_jid)
		if contact:
			gajim.interface.roster.draw_contact(room_jid, account)

		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('GCMessage', (account, array))

	def handle_event_gc_subject(self, account, array):
		#('GC_SUBJECT', account, (jid, subject, body, has_timestamp))
		jids = array[0].split('/', 1)
		jid = jids[0]

		gc_control = self.msg_win_mgr.get_control(jid, account)

		if not gc_control and \
		self.minimized_controls.has_key(account) and \
		jid in self.minimized_controls[account]:
			gc_control = self.minimized_controls[account][jid]

		contact = gajim.contacts.\
			get_contact_with_highest_priority(account, jid)
		if contact:
			contact.status = array[1]
			gajim.interface.roster.draw_contact(jid, account)

		if not gc_control:
			return
		gc_control.set_subject(array[1])
		# Standard way, the message comes from the occupant who set the subject
		text = None
		if len(jids) > 1:
			text = '%s has set the subject to %s' % (jids[1], array[1])
		# Workaround for psi bug http://flyspray.psi-im.org/task/595 , to be 
		# deleted one day. We can receive a subject with a body that contains 
		# "X has set the subject to Y" ...
		elif array[2]:
			text = array[2]
		if text is not None:
			if array[3]:
				gc_control.print_old_conversation(text)
			else:
				gc_control.print_conversation(text)

	def handle_event_gc_config(self, account, array):
		#('GC_CONFIG', account, (jid, form))  config is a dict
		room_jid = array[0].split('/')[0]
		if room_jid in gajim.automatic_rooms[account]:
			# use default configuration
			gajim.connections[account].send_gc_config(room_jid, array[1])
			# invite contacts
			if gajim.automatic_rooms[account][room_jid].has_key('invities'):
				for jid in gajim.automatic_rooms[account][room_jid]['invities']:
					gajim.connections[account].send_invite(room_jid, jid)
			del gajim.automatic_rooms[account][room_jid]
		elif not self.instances[account]['gc_config'].has_key(room_jid):
			self.instances[account]['gc_config'][room_jid] = \
			config.GroupchatConfigWindow(account, room_jid, array[1])

	def handle_event_gc_affiliation(self, account, array):
		#('GC_AFFILIATION', account, (room_jid, affiliation, list)) list is list
		room_jid = array[0]
		if self.instances[account]['gc_config'].has_key(room_jid):
			self.instances[account]['gc_config'][room_jid].\
				affiliation_list_received(array[1], array[2])

	def handle_event_gc_invitation(self, account, array):
		#('GC_INVITATION', (room_jid, jid_from, reason, password))
		jid = gajim.get_jid_without_resource(array[1])
		room_jid = array[0]
		if helpers.allow_popup_window(account) or not self.systray_enabled:
			dialogs.InvitationReceivedDialog(account, room_jid, jid, array[3],
				array[2])
			return

		self.add_event(account, jid, 'gc-invitation', (room_jid, array[2],
			array[3]))

		if helpers.allow_showing_notification(account):
			path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
				'gc_invitation.png')
			path = gtkgui_helpers.get_path_to_generic_or_avatar(path)
			event_type = _('Groupchat Invitation')
			notify.popup(event_type, jid, account, 'gc-invitation', path,
				event_type, room_jid)

	def handle_event_bad_passphrase(self, account, array):
		use_gpg_agent = gajim.config.get('use_gpg_agent')
		if use_gpg_agent:
			return
		keyID = gajim.config.get_per('accounts', account, 'keyid')
		self.roster.forget_gpg_passphrase(keyID)
		dialogs.WarningDialog(_('Your passphrase is incorrect'),
			_('You are currently connected without your OpenPGP key.'))

	def handle_event_roster_info(self, account, array):
		#('ROSTER_INFO', account, (jid, name, sub, ask, groups))
		jid = array[0]
		name = array[1]
		sub = array[2]
		ask = array[3]
		groups = array[4]
		contacts = gajim.contacts.get_contacts_from_jid(account, jid)
		# contact removes us.
		if (not sub or sub == 'none') and (not ask or ask == 'none') and \
		not name and not groups:
			if contacts:
				c = contacts[0]
				self.roster.remove_contact(c, account)
				gajim.contacts.remove_jid(account, jid)
				self.roster.draw_account(account)
				if gajim.events.get_events(account, c.jid):
					keyID = ''
					attached_keys = gajim.config.get_per('accounts', account,
						'attached_gpg_keys').split()
					if jid in attached_keys:
						keyID = attached_keys[attached_keys.index(jid) + 1]
					contact = gajim.contacts.create_contact(jid = c.jid,
						name = '', groups = [_('Not in Roster')],
						show = 'not in roster', status = '', sub = 'none',
						keyID = keyID)
					gajim.contacts.add_contact(account, contact)
					self.roster.add_contact_to_roster(contact.jid, account)
				#FIXME if it was the only one in its group, remove the group
				return
		elif not contacts:
			if sub == 'remove':
				return
			# Add it to roster
			contact = gajim.contacts.create_contact(jid = jid, name = name,
				groups = groups, show = 'offline', sub = sub, ask = ask)
			gajim.contacts.add_contact(account, contact)
			self.roster.add_contact_to_roster(jid, account)
		else:
			re_add = False
			# if sub changed: remove and re-add, maybe observer status changed
			if contacts[0].sub != sub:
				self.roster.remove_contact(contacts[0], account)
				re_add = True
			for contact in contacts:
				if not name:
					name = ''
				contact.name = name
				contact.sub = sub
				contact.ask = ask
				if groups:
					contact.groups = groups
			if re_add:
				self.roster.add_contact_to_roster(jid, account)
		self.roster.draw_contact(jid, account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('RosterInfo', (account, array))

	def handle_event_bookmarks(self, account, bms):
		# ('BOOKMARKS', account, [{name,jid,autojoin,password,nick}, {}])
		# We received a bookmark item from the server (JEP48)
		# Auto join GC windows if neccessary
		
		self.roster.actions_menu_needs_rebuild = True
		invisible_show = gajim.SHOW_LIST.index('invisible')
		# do not autojoin if we are invisible
		if gajim.connections[account].connected == invisible_show:
			return

		# join autojoinable rooms
		for bm in bms:
			if bm['autojoin'] in ('1', 'true'):
				self.roster.join_gc_room(account, bm['jid'], bm['nick'],
					bm['password'],
					minimize = gajim.config.get('minimize_autojoined_rooms'))
								
	def handle_event_file_send_error(self, account, array):
		jid = array[0]
		file_props = array[1]
		ft = self.instances['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')

		if helpers.allow_popup_window(account):
			ft.show_send_error(file_props)
			return

		self.add_event(account, jid, 'file-send-error', file_props)

		if helpers.allow_showing_notification(account):
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events', 'ft_error.png')
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			event_type = _('File Transfer Error')
			notify.popup(event_type, jid, account, 'file-send-error', path,
				event_type, file_props['name'])

	def handle_event_gmail_notify(self, account, array):
		jid = array[0]
		gmail_new_messages = int(array[1])
		gmail_messages_list = array[2]
		if gajim.config.get('notify_on_new_gmail_email'):
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
				'new_email_recv.png')
			title = _('New mail on %(gmail_mail_address)s') % \
				{'gmail_mail_address': jid}
			text = i18n.ngettext('You have %d new mail conversation',
				'You have %d new mail conversations', gmail_new_messages,
				gmail_new_messages, gmail_new_messages)
			
			if gajim.config.get('notify_on_new_gmail_email_extra'):
				for gmessage in gmail_messages_list:
					#FIXME: emulate Gtalk client popups. find out what they parse and how
					#they decide what to show
					# each message has a 'From', 'Subject' and 'Snippet' field
					text += _('\nFrom: %(from_address)s') % \
						{'from_address': gmessage['From']}
					
			if gajim.config.get_per('soundevents', 'gmail_received', 'enabled'):
				helpers.play_sound('gmail_received')
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			notify.popup(_('New E-mail'), jid, account, 'gmail',
				path_to_image = path, title = title, text = text)

		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('NewGmail', (account, array))

	def save_avatar_files(self, jid, photo_decoded, puny_nick = None):
		'''Save the decoded avatar to a separate file, and generate files for dbus notifications'''
		puny_jid = helpers.sanitize_filename(jid)
		path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid)
		if puny_nick:
			path_to_file = os.path.join(path_to_file, puny_nick)
		# remove old avatars
		for typ in ('jpeg', 'png'):
			path_to_original_file = path_to_file + '.' + typ
			if os.path.isfile(path_to_original_file):
				os.remove(path_to_original_file)
		pixbuf, typ = gtkgui_helpers.get_pixbuf_from_data(photo_decoded,
			want_type = True)
		if pixbuf is None:
			return
		if typ not in ('jpeg', 'png'):
			gajim.log.debug('gtkpixbuf cannot save other than jpeg and png formats. saving %s\'avatar as png file (originaly %s)' % (jid, typ))
			typ = 'png'
		path_to_original_file = path_to_file + '.' + typ
		pixbuf.save(path_to_original_file, typ)
		# Generate and save the resized, color avatar
		pixbuf = gtkgui_helpers.get_scaled_pixbuf(
			gtkgui_helpers.get_pixbuf_from_data(photo_decoded), 'notification')
		if pixbuf:
			path_to_normal_file = path_to_file + '_notif_size_colored.png'
			pixbuf.save(path_to_normal_file, 'png')
			# Generate and save the resized, black and white avatar
			bwbuf = gtkgui_helpers.get_scaled_pixbuf(
				gtkgui_helpers.make_pixbuf_grayscale(pixbuf), 'notification')
			if bwbuf:
				path_to_bw_file = path_to_file + '_notif_size_bw.png'
				bwbuf.save(path_to_bw_file, 'png')

	def remove_avatar_files(self, jid, puny_nick = None):
		'''remove avatar files of a jid'''
		puny_jid = helpers.sanitize_filename(jid)
		path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid)
		if puny_nick:
			path_to_file = os.path.join(path_to_file, puny_nick)
		for ext in ('.jpeg', '.png', '_notif_size_colored.png',
		'_notif_size_bw.png'):
			path_to_original_file = path_to_file + ext
			if os.path.isfile(path_to_original_file):
				os.remove(path_to_original_file)

	def add_event(self, account, jid, type_, event_args):
		'''add an event to the gajim.events var'''
		# We add it to the gajim.events queue
		# Do we have a queue?
		jid = gajim.get_jid_without_resource(jid)
		no_queue = len(gajim.events.get_events(account, jid)) == 0
		event_type = None
		# type_ can be gc-invitation file-send-error file-error file-request-error
		# file-request file-completed file-stopped
		# event_type can be in advancedNotificationWindow.events_list
		event_types = {'file-request': 'ft_request',
			'file-completed': 'ft_finished'}
		if type_ in event_types:
			event_type = event_types[type_]
		show_in_roster = notify.get_show_in_roster(event_type, account, jid)
		show_in_systray = notify.get_show_in_systray(event_type, account, jid)
		event = gajim.events.create_event(type_, event_args,
			show_in_roster = show_in_roster,
			show_in_systray = show_in_systray)
		gajim.events.add_event(account, jid, event)

		self.roster.show_title()
		if no_queue: # We didn't have a queue: we change icons
			if not gajim.contacts.get_contact_with_highest_priority(account, jid):
				# add contact to roster ("Not In The Roster") if he is not
				self.roster.add_to_not_in_the_roster(account, jid) 
			self.roster.draw_contact(jid, account)

		# Show contact in roster (if he is invisible for example) and select line
		path = self.roster.get_path(jid, account)		
		self.roster.show_and_select_path(path, jid, account)

	def remove_first_event(self, account, jid, type_ = None):
		event = gajim.events.get_first_event(account, jid, type_)
		self.remove_event(account, jid, event)

	def remove_event(self, account, jid, event):
		if gajim.events.remove_events(account, jid, event):
			# No such event found
			return
		# no other event?
		if not len(gajim.events.get_events(account, jid)):
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
			show_transport = gajim.config.get('show_transports_group')
			if contact and (contact.show in ('error', 'offline') and \
			not gajim.config.get('showoffline') or (
			gajim.jid_is_transport(jid) and not show_transport)):
				self.roster.really_remove_contact(contact, account)
		self.roster.show_title()
		self.roster.draw_contact(jid, account)

	def handle_event_file_request_error(self, account, array):
		# ('FILE_REQUEST_ERROR', account, (jid, file_props, error_msg))
		jid, file_props, errmsg = array
		ft = self.instances['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')
		errno = file_props['error']

		if helpers.allow_popup_window(account):
			if errno in (-4, -5):
				ft.show_stopped(jid, file_props, errmsg)
			else:
				ft.show_request_error(file_props)
			return

		if errno in (-4, -5):
			msg_type = 'file-error'
		else:
			msg_type = 'file-request-error'

		self.add_event(account, jid, msg_type, file_props)

		if helpers.allow_showing_notification(account):
			# check if we should be notified
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events', 'ft_error.png')

			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			event_type = _('File Transfer Error')
			notify.popup(event_type, jid, account, msg_type, path,
				title = event_type, text = file_props['name'])

	def handle_event_file_request(self, account, array):
		jid = array[0]
		if jid not in gajim.contacts.get_jid_list(account):
			return
		file_props = array[1]
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)

		if helpers.allow_popup_window(account):
			self.instances['file_transfers'].show_file_request(account, contact,
				file_props)
			return

		self.add_event(account, jid, 'file-request', file_props)

		if helpers.allow_showing_notification(account):
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
				'ft_request.png')
			txt = _('%s wants to send you a file.') % gajim.get_name_from_jid(
				account, jid)
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			event_type = _('File Transfer Request')
			notify.popup(event_type, jid, account, 'file-request',
				path_to_image = path, title = event_type, text = txt)

	def handle_event_file_progress(self, account, file_props):
		if time.time() - self.last_ftwindow_update > 0.5:
			# update ft window every 500ms
			self.last_ftwindow_update = time.time()
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
		if file_props['type'] == 'r': # we receive a file
			jid = unicode(file_props['sender'])
		else: # we send a file
			jid = unicode(file_props['receiver'])

		if helpers.allow_popup_window(account):
			if file_props['error'] == 0:
				if gajim.config.get('notify_on_file_complete'):
					ft.show_completed(jid, file_props)
			elif file_props['error'] == -1:
				ft.show_stopped(jid, file_props)
			return

		msg_type = ''
		event_type = ''
		if file_props['error'] == 0 and gajim.config.get(
		'notify_on_file_complete'):
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

		if file_props is not None:
			if file_props['type'] == 'r':
				# get the name of the sender, as it is in the roster
				sender = unicode(file_props['sender']).split('/')[0]
				name = gajim.contacts.get_first_contact_from_jid(account,
					sender).get_shown_name()
				filename = os.path.basename(file_props['file-name'])
				if event_type == _('File Transfer Completed'):
					txt = _('You successfully received %(filename)s from %(name)s.')\
						% {'filename': filename, 'name': name}
					img = 'ft_done.png'
				else: # ft stopped
					txt = _('File transfer of %(filename)s from %(name)s stopped.')\
						% {'filename': filename, 'name': name}
					img = 'ft_stopped.png'
			else:
				receiver = file_props['receiver']
				if hasattr(receiver, 'jid'):
					receiver = receiver.jid
				receiver = receiver.split('/')[0]
				# get the name of the contact, as it is in the roster
				name = gajim.contacts.get_first_contact_from_jid(account,
					receiver).get_shown_name()
				filename = os.path.basename(file_props['file-name'])
				if event_type == _('File Transfer Completed'):
					txt = _('You successfully sent %(filename)s to %(name)s.')\
						% {'filename': filename, 'name': name}
					img = 'ft_done.png'
				else: # ft stopped
					txt = _('File transfer of %(filename)s to %(name)s stopped.')\
						% {'filename': filename, 'name': name}
					img = 'ft_stopped.png'
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events', img)
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
		else:
			txt = ''

		if gajim.config.get('notify_on_file_complete') and \
			(gajim.config.get('autopopupaway') or \
			gajim.connections[account].connected in (2, 3)):
			# we want to be notified and we are online/chat or we don't mind
			# bugged when away/na/busy
			notify.popup(event_type, jid, account, msg_type, path_to_image = path,
				title = event_type, text = txt)

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
		if self.instances[account].has_key('profile'):
			win = self.instances[account]['profile']
			win.vcard_published()
		for gc_control in self.msg_win_mgr.get_controls(message_control.TYPE_GC):
			if gc_control.account == account:
				show = gajim.SHOW_LIST[gajim.connections[account].connected]
				status = gajim.connections[account].status
				gajim.connections[account].send_gc_status(gc_control.nick,
					gc_control.room_jid, show, status)

	def handle_event_vcard_not_published(self, account, array):
		if self.instances[account].has_key('profile'):
			win = self.instances[account]['profile']
			win.vcard_not_published()

	def handle_event_signed_in(self, account, empty):
		'''SIGNED_IN event is emitted when we sign in, so handle it'''
		# block signed in notifications for 30 seconds
		gajim.block_signed_in_notifications[account] = True
		self.roster.actions_menu_needs_rebuild = True
		if self.sleeper.getState() != common.sleepy.STATE_UNKNOWN and \
		gajim.connections[account].connected in (2, 3):
			# we go online or free for chat, so we activate auto status
			gajim.sleeper_state[account] = 'online'
		else:
			gajim.sleeper_state[account] = 'off'
		invisible_show = gajim.SHOW_LIST.index('invisible')
		# We cannot join rooms if we are invisible
		if gajim.connections[account].connected == invisible_show:
			return
		# join already open groupchats
		for gc_control in self.msg_win_mgr.get_controls(message_control.TYPE_GC):
			if account != gc_control.account:
				continue
			room_jid = gc_control.room_jid
			if gajim.gc_connected[account].has_key(room_jid) and\
					gajim.gc_connected[account][room_jid]:
				continue
			nick = gc_control.nick
			password = ''
			if gajim.gc_passwords.has_key(room_jid):
				password = gajim.gc_passwords[room_jid]
			gajim.connections[account].join_gc(nick, room_jid, password)

	def handle_event_metacontacts(self, account, tags_list):
		gajim.contacts.define_metacontacts(account, tags_list)

	def handle_atom_entry(self, account, data):
		atom_entry, = data
		AtomWindow.newAtomEntry(atom_entry)

	def handle_session_negotiation(self, account, data):
		jid, session, form = data
	
		if form.getField('accept') and not form['accept'] in ('1', 'true'):
			dialogs.InformationDialog(_('Session negotiation cancelled'),
					_('The client at %s cancelled the session negotiation.') % (jid))
			session.cancelled_negotiation()
			return

		# encrypted session states. these are described in stanza_session.py

		# bob responds
		if form.getType() == 'form' and u'e2e' in \
		map(lambda x: x[1], form.getField('security').getOptions()):
			contact = gajim.contacts.get_contact(account, jid.getStripped(), jid.getResource())

			if gajim.SHOW_LIST[gajim.connections[account].connected] == 'invisible' or \
			contact.sub not in ('from', 'both'):
				return

			negotiated, not_acceptable, ask_user = session.verify_options_bob(form)

			if ask_user:
				def accept_nondefault_options(widget):
					negotiated.update(ask_user)
					session.respond_e2e_bob(form, negotiated, not_acceptable)
					
					dialog.destroy()

				def reject_nondefault_options(widget):
					for key in ask_user.keys():
						not_acceptable.append(key)
					session.respond_e2e_bob(form, negotiated, not_acceptable)

					dialog.destroy()

				dialog = dialogs.YesNoDialog(_('Confirm these session options'),
					_('''The remote client wants to negotiate an session with these features:

%s

Are these options acceptable?''') % (negotiation.describe_features(ask_user)),
						on_response_yes = accept_nondefault_options,
						on_response_no = reject_nondefault_options)
			else:
				session.respond_e2e_bob(form, negotiated, not_acceptable)

			return

		# alice accepts
		elif session.status == 'requested-e2e' and form.getType() == 'submit':
			negotiated, not_acceptable, ask_user = session.verify_options_alice(form)

			if ask_user:
				def accept_nondefault_options(widget):
					dialog.destroy()

					negotiated.update(ask_user)
					session.accept_e2e_alice(form, negotiated)

					negotiation.show_sas_dialog(jid, session.sas)

				def reject_nondefault_options(widget):
					session.reject_negotiation()
					dialog.destroy()

				dialog = dialogs.YesNoDialog(_('Confirm these session options'),
						_('The remote client selected these options:\n\n%s\n\nContinue with the session?') % (negotiation.describe_features(ask_user)),
						on_response_yes = accept_nondefault_options,
						on_response_no = reject_nondefault_options)
			else:
				session.accept_e2e_alice(form, negotiated)
				
				negotiation.show_sas_dialog(jid, session.sas)

			return
		elif session.status == 'responded-e2e' and form.getType() == 'result':
			session.accept_e2e_bob(form)
			negotiation.show_sas_dialog(jid, session.sas)
			return
		elif session.status == 'identified-alice' and form.getType() == 'result':
			session.final_steps_alice(form)
			return
		
		if form.getField('terminate'):
			if form.getField('terminate').getValue() in ('1', 'true'):
				session.acknowledge_termination()

				gajim.connections[account].delete_session(str(jid), session.thread_id)
			
				ctrl = gajim.interface.msg_win_mgr.get_control(str(jid), account)

				if ctrl:
					ctrl.session = gajim.connections[self.account].make_new_session(str(jid))

				return

		# non-esession negotiation. this isn't very useful, but i'm keeping it around
		# to test my test suite.
		if form.getType() == 'form':
			ctrl = gajim.interface.msg_win_mgr.get_control(str(jid), account)
			if not ctrl:
				resource = jid.getResource()
				contact = gajim.contacts.get_contact(account, str(jid), resource)
				if not contact:
					connection = gajim.connections[account]
					contact = gajim.contacts.create_contact(jid = jid.getStripped(), resource = resource, show = connection.get_status())
				self.roster.new_chat(contact, account, resource = resource)

				ctrl = gajim.interface.msg_win_mgr.get_control(str(jid), account)

			ctrl.set_session(session)

			negotiation.FeatureNegotiationWindow(account, jid, session, form)

	def handle_event_privacy_lists_received(self, account, data):
		# ('PRIVACY_LISTS_RECEIVED', account, list)
		if not self.instances.has_key(account):
			return
		if self.instances[account].has_key('privacy_lists'):
			self.instances[account]['privacy_lists'].privacy_lists_received(data)

	def handle_event_privacy_list_received(self, account, data):
		# ('PRIVACY_LISTS_RECEIVED', account, (name, rules))
		if not self.instances.has_key(account):
			return
		name = data[0]
		rules = data[1]
		if self.instances[account].has_key('privacy_list_%s' % name):
			self.instances[account]['privacy_list_%s' % name].\
				privacy_list_received(rules)
		if name == 'block':
			gajim.connections[account].blocked_contacts = []
			gajim.connections[account].blocked_groups = []
			gajim.connections[account].blocked_list = []
			for rule in rules:
				if rule['type'] == 'jid' and rule['action'] == 'deny':
					gajim.connections[account].blocked_contacts.append(rule['value'])
				if rule['type'] == 'group' and rule['action'] == 'deny':
					gajim.connections[account].blocked_groups.append(rule['value'])
				gajim.connections[account].blocked_list.append(rule)
				#elif rule['type'] == "group" and action == "deny":
				#	text_item = _('%s group "%s"') % _(rule['action']), rule['value']
				#	self.store.append([text_item])
				#	self.global_rules.append(rule)
				#else:
				#	self.global_rules_to_append.append(rule) 
			if self.instances[account].has_key('blocked_contacts'):
				self.instances[account]['blocked_contacts'].\
					privacy_list_received(rules)

	def handle_event_privacy_lists_active_default(self, account, data):
		if not data:
			return
		# Send to all privacy_list_* windows as we can't know which one asked
		for win in self.instances[account]:
			if win.startswith('privacy_list_'):
				self.instances[account][win].check_active_default(data)

	def handle_event_privacy_list_removed(self, account, name):
		# ('PRIVACY_LISTS_REMOVED', account, name)
		if not self.instances.has_key(account):
			return
		if self.instances[account].has_key('privacy_lists'):
			self.instances[account]['privacy_lists'].privacy_list_removed(name)

	def handle_event_zc_name_conflict(self, account, data):
		dlg = dialogs.InputDialog(_('Username Conflict'),
			_('Please type a new username for your local account'), 
			is_modal = True)
		dlg.input_entry.set_text(data)
		response = dlg.get_response()
		if response == gtk.RESPONSE_OK:
			new_name = dlg.input_entry.get_text()
			gajim.config.set_per('accounts', account, 'name', new_name)
			status = gajim.connections[account].status
			gajim.connections[account].username = new_name
			gajim.connections[account].change_status(status, '')
		else:
			gajim.connections[account].change_status('offline','')

	def handle_event_ping_sent(self, account, contact):
		ctrl = self.msg_win_mgr.get_control(contact.get_full_jid(), account)
		if ctrl == None:
			ctrl = self.msg_win_mgr.get_control(contact.jid, account)
		ctrl.print_conversation(_('Ping?'), 'status')

	def handle_event_ping_reply(self, account, data):
		contact = data[0]
		seconds = data[1]
		ctrl = self.msg_win_mgr.get_control(contact.get_full_jid(), account)
		if ctrl == None:
			ctrl = self.msg_win_mgr.get_control(contact.jid, account)
		ctrl.print_conversation(_('Pong! (%s s.)') % seconds, 'status')

	def handle_event_ping_error(self, account, contact):
		ctrl = self.msg_win_mgr.get_control(contact.get_full_jid(), account)
		if ctrl == None:
			ctrl = self.msg_win_mgr.get_control(contact.jid, account)
		ctrl.print_conversation(_('Error.'), 'status')

	def handle_event_search_form(self, account, data):
		# ('SEARCH_FORM', account, (jid, dataform, is_dataform))
		if not self.instances[account]['search'].has_key(data[0]):
			return
		self.instances[account]['search'][data[0]].on_form_arrived(data[1],
			data[2])

	def handle_event_search_result(self, account, data):
		# ('SEARCH_RESULT', account, (jid, dataform, is_dataform))
		if not self.instances[account]['search'].has_key(data[0]):
			return
		self.instances[account]['search'][data[0]].on_result_arrived(data[1],
			data[2])

	def handle_event_resource_conflict(self, account, data):
		# ('RESOURCE_CONFLICT', account, ())
		# First we go offline, but we don't overwrite status message
		self.roster.send_status(account, 'offline',
			gajim.connections[account].status)
		def on_ok(new_resource):
			gajim.config.set_per('accounts', account, 'resource', new_resource)
			self.roster.send_status(account, gajim.connections[account].old_show,
				gajim.connections[account].status)
		dlg = dialogs.InputDialog(_('Resource Conflict'),
			_('You are already connected to this account with the same resource. Please type a new one'), input_str = gajim.connections[account].server_resource,
			is_modal = False, ok_handler = on_ok)

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
				# we go online
				self.roster.send_status(account, 'online',
					gajim.status_before_autoaway[account])
				gajim.status_before_autoaway[account] = ''
				gajim.sleeper_state[account] = 'online'
			elif state == common.sleepy.STATE_AWAY and \
				gajim.sleeper_state[account] == 'online' and \
				gajim.config.get('autoaway'):
				# we save out online status
				gajim.status_before_autoaway[account] = \
					gajim.connections[account].status
				# we go away (no auto status) [we pass True to auto param]
				auto_message = gajim.config.get('autoaway_message')
				if not auto_message:
					auto_message = gajim.connections[account].status
				self.roster.send_status(account, 'away', auto_message, auto=True)
				gajim.sleeper_state[account] = 'autoaway'
			elif state == common.sleepy.STATE_XA and (\
				gajim.sleeper_state[account] == 'autoaway' or \
				gajim.sleeper_state[account] == 'online') and \
				gajim.config.get('autoxa'):
				# we go extended away [we pass True to auto param]
				auto_message = gajim.config.get('autoxa_message')
				if not auto_message:
					auto_message = gajim.connections[account].status
				self.roster.send_status(account, 'xa', auto_message, auto=True)
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
			if message == None:
				return
			for a in gajim.connections:
				if gajim.config.get_per('accounts', a, 'autoconnect'):
					self.roster.send_status(a, 'online', message)
		return False

	def show_systray(self):
		self.systray_enabled = True
		self.systray.show_icon()

	def hide_systray(self):
		self.systray_enabled = False
		self.systray.hide_icon()
	
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

		prefixes = '|'.join((r'http://', r'https://', r'gopher://', r'news://',
			r'ftp://', r'ed2k://', r'irc://', r'magnet:', r'sip:', r'www\.',
			r'ftp\.'))
		# NOTE: it's ok to catch www.gr such stuff exist!
		
		#FIXME: recognize xmpp: and treat it specially
		
		links = r'\b(%s)\S*[\w\/\=]|' % prefixes
		#2nd one: at_least_one_char@at_least_one_char.at_least_one_char
		mail = r'\bmailto:\S*[^\s\W]|' r'\b\S+@\S+\.\S*[^\s\W]'

		#detects eg. *b* *bold* *bold bold* test *bold* *bold*! (*bold*)
		#doesn't detect (it's a feature :P) * bold* *bold * * bold * test*bold*
		formatting = r'|(?<!\w)' r'\*[^\s*]' r'([^*]*[^\s*])?' r'\*(?!\w)|'\
			r'(?<!\w|\<)' r'/[^\s/]' r'([^/]*[^\s/])?' r'/(?!\w)|'\
			r'(?<!\w)' r'_[^\s_]' r'([^_]*[^\s_])?' r'_(?!\w)'

		latex = r'|\$\$.*\$\$'
		
		basic_pattern = links + mail
		
		if gajim.config.get('use_latex'):
			basic_pattern += latex
		
		if gajim.config.get('ascii_formatting'):
			basic_pattern += formatting
		self.basic_pattern_re = re.compile(basic_pattern, re.IGNORECASE)
		
		emoticons_pattern = ''
		if gajim.config.get('emoticons_theme'):
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
				emoticon_escaped = re.escape(emoticon) # espace regexp metachars
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
		self.emot_and_basic_re = re.compile(emot_and_basic_pattern, re.IGNORECASE)
		
		# at least one character in 3 parts (before @, after @, after .)
		self.sth_at_sth_dot_sth_re = re.compile(r'\S+@\S+\.\S*[^\s)?]')
		
		re.purge() # clear the regular expression cache

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

	def popup_emoticons_under_button(self, button, parent_win):
		''' pops emoticons menu under button, located in parent_win'''
		gtkgui_helpers.popup_emoticons_under_button(self.emoticons_menu, 
			button, parent_win)
	
	def prepare_emoticons_menu(self):
		menu = gtk.Menu()
		def emoticon_clicked(w, str_):
			if self.emoticon_menuitem_clicked:
				self.emoticon_menuitem_clicked(str_)
				# don't keep reference to CB of object
				# this will prevent making it uncollectable
				self.emoticon_menuitem_clicked = None
		def selection_done(widget):
			# remove reference to CB of object, which will
			# make it uncollectable
			self.emoticon_menuitem_clicked = None
		counter = 0
		# Calculate the side lenght of the popup to make it a square
		size = int(round(math.sqrt(len(self.emoticons_images))))
		for image in self.emoticons_images:
			item = gtk.MenuItem()
			img = gtk.Image()
			if type(image[1]) == gtk.gdk.PixbufAnimation:
				img.set_from_animation(image[1])
			else:
				img.set_from_pixbuf(image[1])
			item.add(img)
			item.connect('activate', emoticon_clicked, image[0])
			#FIXME: add tooltip with ascii
			menu.attach(item, counter % size, counter % size + 1,
				counter / size, counter / size + 1)
			counter += 1
		menu.connect('selection-done', selection_done)
		menu.show_all()
		return menu

	def init_emoticons(self, need_reload = False):
		emot_theme = gajim.config.get('emoticons_theme')
		if not emot_theme:
			return

		#initialize emoticons dictionary and unique images list
		self.emoticons_images = list()
		self.emoticons = dict()
		self.emoticons_animations = dict()

		path = os.path.join(gajim.DATA_DIR, 'emoticons', emot_theme)
		if not os.path.exists(path):
			# It's maybe a user theme
			path = os.path.join(gajim.MY_EMOTS_PATH, emot_theme)
			if not os.path.exists(path): # theme doesn't exist, disable emoticons
				gajim.config.set('emoticons_theme', '')
				return
		sys.path.append(path)
		import emoticons
		if need_reload:
			# we need to reload else that doesn't work when changing emoticon set
			reload(emoticons) 
		emots = emoticons.emoticons
		for emot in emots:
			emot_file = os.path.join(path, emots[emot])
			if not self.image_is_ok(emot_file):
				continue
			# This avoids duplicated emoticons with the same image eg. :) and :-)
			if not emot_file in self.emoticons.values():
				if emot_file.endswith('.gif'):
					pix = gtk.gdk.PixbufAnimation(emot_file)
				else:
					pix = gtk.gdk.pixbuf_new_from_file(emot_file)
				self.emoticons_images.append((emot, pix))
			self.emoticons[emot.upper()] = emot_file
		sys.path.remove(path)
		del emoticons
		if self.emoticons_menu:
			self.emoticons_menu.destroy()
		self.emoticons_menu = self.prepare_emoticons_menu()
	
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
			'MSGNOTSENT': self.handle_event_msgnotsent,
			'SUBSCRIBED': self.handle_event_subscribed,
			'UNSUBSCRIBED': self.handle_event_unsubscribed,
			'SUBSCRIBE': self.handle_event_subscribe,
			'AGENT_ERROR_INFO': self.handle_event_agent_info_error,
			'AGENT_ERROR_ITEMS': self.handle_event_agent_items_error,
			'AGENT_REMOVED': self.handle_event_agent_removed,
			'REGISTER_AGENT_INFO': self.handle_event_register_agent_info,
			'AGENT_INFO_ITEMS': self.handle_event_agent_info_items,
			'AGENT_INFO_INFO': self.handle_event_agent_info_info,
			'QUIT': self.handle_event_quit,
			'ACC_OK': self.handle_event_acc_ok,
			'ACC_NOT_OK': self.handle_event_acc_not_ok,
			'MYVCARD': self.handle_event_myvcard,
			'VCARD': self.handle_event_vcard,
			'LAST_STATUS_TIME': self.handle_event_last_status_time,
			'OS_INFO': self.handle_event_os_info,
			'GC_NOTIFY': self.handle_event_gc_notify,
			'GC_MSG': self.handle_event_gc_msg,
			'GC_SUBJECT': self.handle_event_gc_subject,
			'GC_CONFIG': self.handle_event_gc_config,
			'GC_INVITATION': self.handle_event_gc_invitation,
			'GC_AFFILIATION': self.handle_event_gc_affiliation,
			'BAD_PASSPHRASE': self.handle_event_bad_passphrase,
			'ROSTER_INFO': self.handle_event_roster_info,
			'BOOKMARKS': self.handle_event_bookmarks,
			'CON_TYPE': self.handle_event_con_type,
			'CONNECTION_LOST': self.handle_event_connection_lost,
			'FILE_REQUEST': self.handle_event_file_request,
			'GMAIL_NOTIFY': self.handle_event_gmail_notify,
			'FILE_REQUEST_ERROR': self.handle_event_file_request_error,
			'FILE_SEND_ERROR': self.handle_event_file_send_error,
			'STANZA_ARRIVED': self.handle_event_stanza_arrived,
			'STANZA_SENT': self.handle_event_stanza_sent,
			'HTTP_AUTH': self.handle_event_http_auth,
			'VCARD_PUBLISHED': self.handle_event_vcard_published,
			'VCARD_NOT_PUBLISHED': self.handle_event_vcard_not_published,
			'ASK_NEW_NICK': self.handle_event_ask_new_nick,
			'SIGNED_IN': self.handle_event_signed_in,
			'METACONTACTS': self.handle_event_metacontacts,
			'ATOM_ENTRY': self.handle_atom_entry,
			'PRIVACY_LISTS_RECEIVED': self.handle_event_privacy_lists_received,
			'PRIVACY_LIST_RECEIVED': self.handle_event_privacy_list_received,
			'PRIVACY_LISTS_ACTIVE_DEFAULT': \
				self.handle_event_privacy_lists_active_default,
			'PRIVACY_LIST_REMOVED': self.handle_event_privacy_list_removed,
			'ZC_NAME_CONFLICT': self.handle_event_zc_name_conflict,
			'PING_SENT': self.handle_event_ping_sent,
			'PING_REPLY': self.handle_event_ping_reply,
			'PING_ERROR': self.handle_event_ping_error,
			'SEARCH_FORM': self.handle_event_search_form,
			'SEARCH_RESULT': self.handle_event_search_result,
			'RESOURCE_CONFLICT': self.handle_event_resource_conflict,
			'SESSION_NEG': self.handle_session_negotiation,
		}
		gajim.handlers = self.handlers

	def process_connections(self):
		''' called each foo (200) miliseconds. Check for idlequeue timeouts.
		'''
		gajim.idlequeue.process()
		return True # renew timeout (loop for ever)

	def save_config(self):
		err_str = parser.write()
		if err_str is not None:
			print >> sys.stderr, err_str
			# it is good to notify the user
			# in case he or she cannot see the output of the console
			dialogs.ErrorDialog(_('Could not save your settings and preferences'),
				err_str)
			sys.exit()

	def handle_event(self, account, fjid, type_):
		w = None
		resource = gajim.get_resource_from_jid(fjid)
		jid = gajim.get_jid_without_resource(fjid)
		if type_ in ('printed_gc_msg', 'printed_marked_gc_msg', 'gc_msg'):
			w = self.msg_win_mgr.get_window(jid, account)
		elif type_ in ('printed_chat', 'chat', ''):
			# '' is for log in/out notifications
			if self.msg_win_mgr.has_window(fjid, account):
				w = self.msg_win_mgr.get_window(fjid, account)
			else:
				highest_contact = gajim.contacts.get_contact_with_highest_priority(
					account, jid)
				# jid can have a window if this resource was lower when he sent
				# message and is now higher because the other one is offline
				if resource and highest_contact.resource == resource and \
				not self.msg_win_mgr.has_window(jid, account):
					# remove resource of events too
					gajim.events.change_jid(account, fjid, jid)
					resource = None
					fjid = jid
				contact = gajim.contacts.get_contact(account, jid, resource)
				if not contact or isinstance(contact, list):
					contact = highest_contact
				self.roster.new_chat(contact, account, resource = resource)
				w = self.msg_win_mgr.get_window(fjid, account)
				gajim.last_message_time[account][jid] = 0 # long time ago
		elif type_ in ('printed_pm', 'pm'):
			if self.msg_win_mgr.has_window(fjid, account):
				w = self.msg_win_mgr.get_window(fjid, account)
			else:
				room_jid = jid
				nick = resource
				gc_contact = gajim.contacts.get_gc_contact(account, room_jid,
					nick)
				if gc_contact:
					show = gc_contact.show
				else:
					show = 'offline'
					gc_contact = gajim.contacts.create_gc_contact(
						room_jid = room_jid, name = nick, show = show)
				c = gajim.contacts.contact_from_gc_contact(gc_contact)
				self.roster.new_chat(c, account, private_chat = True)
				w = self.msg_win_mgr.get_window(fjid, account)
		elif type_ in ('normal', 'file-request', 'file-request-error',
		'file-send-error', 'file-error', 'file-stopped', 'file-completed'):
			# Get the first single message event
			event = gajim.events.get_first_event(account, fjid, type_)
			if not event:
				# default to jid without resource
				event = gajim.events.get_first_event(account, jid, type_)
				# Open the window
				self.roster.open_event(account, jid, event)
			else:
				# Open the window
				self.roster.open_event(account, fjid, event)
		elif type_ == 'gmail':
			url = 'http://mail.google.com/mail?account_id=%s' % urllib.quote(
				gajim.config.get_per('accounts', account, 'name'))
			helpers.launch_browser_mailer('url', url)
		elif type_ == 'gc-invitation':
			event = gajim.events.get_first_event(account, jid, type_)
			data = event.parameters
			dialogs.InvitationReceivedDialog(account, data[0], jid, data[2],
				data[1])
			gajim.events.remove_events(account, jid, event)
			self.roster.draw_contact(jid, account)
		if w:
			w.set_active_tab(fjid, account)
			w.window.present()
			w.window.window.focus()
			ctrl = w.get_control(fjid, account)
			# Using isinstance here because we want to catch all derived types
			if isinstance(ctrl, ChatControlBase):
				tv = ctrl.conv_textview
				tv.scroll_to_end()

	def __init__(self):
		gajim.interface = self
		# This is the manager and factory of message windows set by the module
		self.msg_win_mgr = None
		self.emoticons_menu = None
		# handler when an emoticon is clicked in emoticons_menu
		self.emoticon_menuitem_clicked = None
		self.minimized_controls = {}
		self.default_colors = {
			'inmsgcolor': gajim.config.get('inmsgcolor'),
			'outmsgcolor': gajim.config.get('outmsgcolor'),
			'statusmsgcolor': gajim.config.get('statusmsgcolor'),
			'urlmsgcolor': gajim.config.get('urlmsgcolor'),
		}

		parser.read()
		# Do not set gajim.verbose to False if -v option was given
		if gajim.config.get('verbose'):
			gajim.verbose = True

		# Is Gajim default app?
		if os.name != 'nt' and gajim.config.get('check_if_gajim_is_default'):
			gtkgui_helpers.possibly_set_gajim_as_xmpp_handler()

		# Is gnome configured to activate row on single click ?
		try:
			import gconf
			client = gconf.client_get_default()
			click_policy = client.get_string(
				'/apps/nautilus/preferences/click_policy')
			if click_policy == 'single':
				gajim.single_click = True
		except:
			pass
		# add default status messages if there is not in the config file
		if len(gajim.config.get_per('statusmsg')) == 0:
			for msg in gajim.config.statusmsg_default:
				gajim.config.add_per('statusmsg', msg)
				gajim.config.set_per('statusmsg', msg, 'message', 
					gajim.config.statusmsg_default[msg])
		#add default themes if there is not in the config file
		theme = gajim.config.get('roster_theme')
		if not theme in gajim.config.get_per('themes'):
			gajim.config.set('roster_theme', 'gtk+')
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
		
		# pygtk2.8+ on win, breaks io_add_watch.
		# We use good old select.select()
		if os.name == 'nt':
			gajim.idlequeue = idlequeue.SelectIdleQueue()
		else:
			# in a nongui implementation, just call:
			# gajim.idlequeue = IdleQueue() , and
			# gajim.idlequeue.process() each foo miliseconds
			gajim.idlequeue = GlibIdleQueue()
		# resolve and keep current record of resolved hosts
		gajim.resolver = nslookup.Resolver(gajim.idlequeue)
		gajim.socks5queue = socks5.SocksQueue(gajim.idlequeue,
			self.handle_event_file_rcv_completed, 
			self.handle_event_file_progress)
		gajim.proxy65_manager = proxy65_manager.Proxy65Manager(gajim.idlequeue)
		self.register_handlers()
		if gajim.config.get('enable_zeroconf'):
			gajim.connections[gajim.ZEROCONF_ACC_NAME] = common.zeroconf.connection_zeroconf.ConnectionZeroconf(gajim.ZEROCONF_ACC_NAME)
		for account in gajim.config.get_per('accounts'):
			if not gajim.config.get_per('accounts', account, 'is_zeroconf'):
				gajim.connections[account] = common.connection.Connection(account)

		# gtk hooks
		gtk.about_dialog_set_email_hook(self.on_launch_browser_mailer, 'mail')
		gtk.about_dialog_set_url_hook(self.on_launch_browser_mailer, 'url')
		if gtk.pygtk_version >= (2, 10, 0) and gtk.gtk_version >= (2, 10, 0):
			gtk.link_button_set_uri_hook(self.on_launch_browser_mailer, 'url')
		
		self.instances = {'logs': {}}
		
		for a in gajim.connections:
			self.instances[a] = {'infos': {}, 'disco': {}, 'gc_config': {},
				'search': {}}
			gajim.contacts.add_account(a)
			gajim.groups[a] = {}
			gajim.gc_connected[a] = {}
			gajim.automatic_rooms[a] = {}
			gajim.newly_added[a] = []
			gajim.to_be_removed[a] = []
			gajim.nicks[a] = gajim.config.get_per('accounts', a, 'name')
			gajim.block_signed_in_notifications[a] = True
			gajim.sleeper_state[a] = 0
			gajim.encrypted_chats[a] = []
			gajim.last_message_time[a] = {}
			gajim.status_before_autoaway[a] = ''
			gajim.transport_avatar[a] = {}

		self.roster = roster_window.RosterWindow()
		
		if gajim.config.get('remote_control'):
			try:
				import remote_control
				self.remote_ctrl = remote_control.Remote()
			except:
				self.remote_ctrl = None
		else:
			self.remote_ctrl = None

		if gajim.config.get('networkmanager_support') and dbus_support.supported:
			try:
				import network_manager_listener
			except:
				print >> sys.stderr, _('Network Manager support not available')

		self.show_vcard_when_connect = []

		path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps', 'gajim.png')
		pix = gtk.gdk.pixbuf_new_from_file(path_to_file)
		# set the icon to all newly opened windows
		gtk.window_set_default_icon(pix)
		self.roster.window.set_icon_from_file(path_to_file) # and to roster window
		self.sleeper = common.sleepy.Sleepy(
			gajim.config.get('autoawaytime') * 60, # make minutes to seconds
			gajim.config.get('autoxatime') * 60)

		self.systray_enabled = False
		self.systray_capabilities = False
		
		if os.name == 'nt' and gtk.pygtk_version >= (2, 10, 0) and\
		gtk.gtk_version >= (2, 10, 0):
			import statusicon 
			self.systray = statusicon.StatusIcon() 
			self.systray_capabilities = True
		else: # use ours, not GTK+ one
			# [FIXME: remove this when we migrate to 2.10 and we can do
			# cool tooltips somehow and (not dying to keep) animation]
			import systray
			self.systray_capabilities = systray.HAS_SYSTRAY_CAPABILITIES
			if self.systray_capabilities:
				self.systray = systray.Systray()

		if self.systray_capabilities and gajim.config.get('trayicon'):
			self.show_systray()

		self.init_emoticons()
		self.make_regexps()
		
		# get instances for windows/dialogs that will show_all()/hide()
		self.instances['file_transfers'] = dialogs.FileTransfersWindow()

		# get transports type from DB
		gajim.transport_type = gajim.logger.get_transports_type()

		# test is dictionnary is present for speller
		if gajim.config.get('use_speller'):
			lang = gajim.config.get('speller_language')
			if not lang:
				lang = gajim.LANG
			tv = gtk.TextView()
			try:
				import gtkspell
				spell = gtkspell.Spell(tv, lang)
			except:
				dialogs.AspellDictError(lang)
		self.last_ftwindow_update = 0

		gobject.timeout_add(100, self.autoconnect)
		gobject.timeout_add(200, self.process_connections)
		gobject.timeout_add(500, self.read_sleepy)

if __name__ == '__main__':
	def sigint_cb(num, stack):
		sys.exit(5)
	# ^C exits the application normally to delete pid file
	signal.signal(signal.SIGINT, sigint_cb)

	if gajim.verbose:
		print >> sys.stderr, "Encodings: d:%s, fs:%s, p:%s" % \
		(sys.getdefaultencoding(), sys.getfilesystemencoding(), locale.getpreferredencoding())

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
			
			path_to_gajim_script = gtkgui_helpers.get_abspath_for_script(
				'gajim')
			
			if path_to_gajim_script:
				argv = [path_to_gajim_script]
				# FIXME: remove this typeerror catch when gnome python is old and
				# not bad patched by distro men [2.12.0 + should not need all that
				# NORMALLY]
				try:
					cli.set_restart_command(argv)
				except AttributeError:
					cli.set_restart_command(len(argv), argv)
		
	check_paths.check_and_possibly_create_paths()

	Interface()
	gtk.main()
