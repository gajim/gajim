##	common/helpers.py
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
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

import sre
import os
import urllib
import errno
import select
import sys
import sha
from encodings.punycode import punycode_encode

import gajim
import i18n
from xmpp_stringprep import nodeprep, resourceprep, nameprep

try:
	import winsound # windows-only built-in module for playing wav
	import win32api
	import win32con
except:
	pass

_ = i18n._
Q_ = i18n.Q_

special_groups = (_('Transports'), _('Not in Roster'), _('Observers'))

class InvalidFormat(Exception):
	pass

def parse_jid(jidstring):
	'''Perform stringprep on all JID fragments from a string
	and return the full jid'''
	# This function comes from http://svn.twistedmatrix.com/cvs/trunk/twisted/words/protocols/jabber/jid.py

	user = None
	server = None
	resource = None

	# Search for delimiters
	user_sep = jidstring.find('@')
	res_sep = jidstring.find('/')

	if user_sep == -1:
		if res_sep == -1:
			# host
			server = jidstring
		else:
			# host/resource
			server = jidstring[0:res_sep]
			resource = jidstring[res_sep + 1:] or None
	else:
		if res_sep == -1:
			# user@host
			user = jidstring[0:user_sep] or None
			server = jidstring[user_sep + 1:]
		else:
			if user_sep < res_sep:
				# user@host/resource
				user = jidstring[0:user_sep] or None
				server = jidstring[user_sep + 1:user_sep + (res_sep - user_sep)]
				resource = jidstring[res_sep + 1:] or None
			else:
				# server/resource (with an @ in resource)
				server = jidstring[0:res_sep]
				resource = jidstring[res_sep + 1:] or None

	return prep(user, server, resource)

def parse_resource(resource):
	'''Perform stringprep on resource and return it'''
	if resource:
		try:
			return resourceprep.prepare(unicode(resource))
		except UnicodeError:
			raise InvalidFormat, 'Invalid character in resource.'

def prep(user, server, resource):
	'''Perform stringprep on all JID fragments and return the full jid'''
	# This function comes from
	#http://svn.twistedmatrix.com/cvs/trunk/twisted/words/protocols/jabber/jid.py

	if user:
		try:
			user = nodeprep.prepare(unicode(user))
		except UnicodeError:
			raise InvalidFormat, _('Invalid character in username.')
	else:
		user = None

	if not server:
		raise InvalidFormat, _('Server address required.')
	else:
		try:
			server = nameprep.prepare(unicode(server))
		except UnicodeError:
			raise InvalidFormat, _('Invalid character in hostname.')

	if resource:
		try:
			resource = resourceprep.prepare(unicode(resource))
		except UnicodeError:
			raise InvalidFormat, _('Invalid character in resource.')
	else:
		resource = None

	if user:
		if resource:
			return '%s@%s/%s' % (user, server, resource)
		else:
			return '%s@%s' % (user, server)
	else:
		if resource:
			return '%s/%s' % (server, resource)
		else:
			return server

def temp_failure_retry(func, *args, **kwargs):
	while True:
		try:
			return func(*args, **kwargs)
		except (os.error, IOError, select.error), ex:
			if ex.errno == errno.EINTR:
				continue
			else:
				raise

def convert_bytes(string):
	suffix = ''
	# IEC standard says KiB = 1024 bytes KB = 1000 bytes
	# but do we use the standard?
	use_kib_mib = gajim.config.get('use_kib_mib')
	align = 1024.
	bytes = float(string)
	if bytes >= align:
		bytes = round(bytes/align, 1)
		if bytes >= align:
			bytes = round(bytes/align, 1)
			if bytes >= align:
				bytes = round(bytes/align, 1)
				if use_kib_mib:
					#GiB means gibibyte
					suffix = _('%s GiB')
				else:
					#GB means gigabyte
					suffix = _('%s GB')
			else:
				if use_kib_mib:
					#MiB means mibibyte
					suffix = _('%s MiB')
				else:
					#MB means megabyte
					suffix = _('%s MB')
		else:
			if use_kib_mib:
					#KiB means kibibyte
					suffix = _('%s KiB')
			else:
				#KB means kilo bytes
				suffix = _('%s KB')
	else:
		#B means bytes
		suffix = _('%s B')
	return suffix % unicode(bytes)


def get_contact_dict_for_account(account):
	''' create a dict of jid, nick -> contact with all contacts of account.
	Can be used for completion lists'''
	contacts_dict = {}
	for jid in gajim.contacts.get_jid_list(account):
		contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
		contacts_dict[jid] = contact
		name = contact.name
		if contacts_dict.has_key(name):
			contact1 = contacts_dict[name]
			del contacts_dict[name]
			contacts_dict['%s (%s)' % (name, contact1.jid)] = contact1
			contacts_dict['%s (%s)' % (name, jid)] = contact
		else:
			contacts_dict[name] = contact
	return contacts_dict

def get_uf_show(show, use_mnemonic = False):
	'''returns a userfriendly string for dnd/xa/chat
	and makes all strings translatable
	if use_mnemonic is True, it adds _ so GUI should call with True
	for accessibility issues'''
	if show == 'dnd':
		if use_mnemonic:
			uf_show = _('_Busy')
		else:
			uf_show = _('Busy')
	elif show == 'xa':
		if use_mnemonic:
			uf_show = _('_Not Available')
		else:
			uf_show = _('Not Available')
	elif show == 'chat':
		if use_mnemonic:
			uf_show = _('_Free for Chat')
		else:
			uf_show = _('Free for Chat')
	elif show == 'online':
		if use_mnemonic:
			uf_show = _('_Available')
		else:
			uf_show = _('Available')
	elif show == 'connecting':
			uf_show = _('Connecting')
	elif show == 'away':
		if use_mnemonic:
			uf_show = _('A_way')
		else:
			uf_show = _('Away')
	elif show == 'offline':
		if use_mnemonic:
			uf_show = _('_Offline')
		else:
			uf_show = _('Offline')
	elif show == 'invisible':
		if use_mnemonic:
			uf_show = _('_Invisible')
		else:
			uf_show = _('Invisible')
	elif show == 'not in roster':
		uf_show = _('Not in Roster')
	elif show == 'requested':
		uf_show = Q_('?contact has status:Unknown')
	else:
		uf_show = Q_('?contact has status:Has errors')
	return unicode(uf_show)

def get_uf_sub(sub):
	if sub == 'none':
		uf_sub = Q_('?Subscription we already have:None')
	elif sub == 'to':
		uf_sub = _('To')
	elif sub == 'from':
		uf_sub = _('From')
	elif sub == 'both':
		uf_sub = _('Both')
	else:
		uf_sub = sub

	return unicode(uf_sub)

def get_uf_ask(ask):
	if ask is None:
		uf_ask = Q_('?Ask (for Subscription):None')
	elif ask == 'subscribe':
		uf_ask = _('Subscribe')
	else:
		uf_ask = ask

	return unicode(uf_ask)

def get_uf_role(role, plural = False):
	''' plural determines if you get Moderators or Moderator'''
	if role == 'none':
		role_name = Q_('?Group Chat Contact Role:None')
	elif role == 'moderator':
		if plural:
			role_name = _('Moderators')
		else:
			role_name = _('Moderator')
	elif role == 'participant':
		if plural:
			role_name = _('Participants')
		else:
			role_name = _('Participant')
	elif role == 'visitor':
		if plural:
			role_name = _('Visitors')
		else:
			role_name = _('Visitor')
	return role_name

def get_sorted_keys(adict):
	keys = adict.keys()
	keys.sort()
	return keys

def to_one_line(msg):
	msg = msg.replace('\\', '\\\\')
	msg = msg.replace('\n', '\\n')
	# s1 = 'test\ntest\\ntest'
	# s11 = s1.replace('\\', '\\\\')
	# s12 = s11.replace('\n', '\\n')
	# s12
	# 'test\\ntest\\\\ntest'
	return msg

def from_one_line(msg):
	# (?<!\\) is a lookbehind assertion which asks anything but '\'
	# to match the regexp that follows it

	# So here match '\\n' but not if you have a '\' before that
	re = sre.compile(r'(?<!\\)\\n')
	msg = re.sub('\n', msg)
	msg = msg.replace('\\\\', '\\')
	# s12 = 'test\\ntest\\\\ntest'
	# s13 = re.sub('\n', s12)
	# s14 s13.replace('\\\\', '\\')
	# s14
	# 'test\ntest\\ntest'
	return msg

def get_uf_chatstate(chatstate):
	'''removes chatstate jargon and returns user friendly messages'''
	if chatstate == 'active':
		return _('is paying attention to the conversation')
	elif chatstate == 'inactive':
		return _('is doing something else')
	elif chatstate == 'composing':
		return _('is composing a message...')
	elif chatstate == 'paused':
		#paused means he or she was compoing but has stopped for a while
		return _('paused composing a message')
	elif chatstate == 'gone':
		return _('has closed the chat window or tab')
	return ''

def is_in_path(name_of_command, return_abs_path = False):
	# if return_abs_path is True absolute path will be returned
	# for name_of_command
	# on failures False is returned
	is_in_dir = False
	found_in_which_dir = None
	path = os.getenv('PATH').split(':')
	for path_to_directory in path:
		try:
			contents = os.listdir(path_to_directory)
		except OSError: # user can have something in PATH that is not a dir
			pass
		else:
			is_in_dir = name_of_command in contents
		if is_in_dir:
			if return_abs_path:
				found_in_which_dir = path_to_directory
			break

	if found_in_which_dir:
		abs_path = os.path.join(path_to_directory, name_of_command)
		return abs_path
	else:
		return is_in_dir

def launch_browser_mailer(kind, uri):
	#kind = 'url' or 'mail'
	if os.name == 'nt':
		try:
			os.startfile(uri) # if pywin32 is installed we open
		except:
			pass

	else:
		if kind == 'mail' and not uri.startswith('mailto:'):
			uri = 'mailto:' + uri

		if gajim.config.get('openwith') == 'gnome-open':
			command = 'gnome-open'
		elif gajim.config.get('openwith') == 'kfmclient exec':
			command = 'kfmclient exec'
		elif gajim.config.get('openwith') == 'custom':
			if kind == 'url':
				command = gajim.config.get('custombrowser')
			if kind == 'mail':
				command = gajim.config.get('custommailapp')
			if command == '': # if no app is configured
				return
		# we add the uri in "" so we have good parsing from shell
		uri = uri.replace('"', '\\"') # escape "
		command = command + ' "' + uri + '" &'
		try: #FIXME: when we require python2.4+ use subprocess module
			os.system(command)
		except:
			pass

def launch_file_manager(path_to_open):
	if os.name == 'nt':
		try:
			os.startfile(path_to_open) # if pywin32 is installed we open
		except:
			pass
	else:
		if gajim.config.get('openwith') == 'gnome-open':
			command = 'gnome-open'
		elif gajim.config.get('openwith') == 'kfmclient exec':
			command = 'kfmclient exec'
		elif gajim.config.get('openwith') == 'custom':
			command = gajim.config.get('custom_file_manager')
		if command == '': # if no app is configured
			return
		# we add the path in "" so we have good parsing from shell
		path_to_open = path_to_open.replace('"', '\\"') # escape "
		command = command + ' "' + path_to_open + '" &'
		try: #FIXME: when we require python2.4+ use subprocess module
			os.system(command)
		except:
			pass

def play_sound(event):
	if not gajim.config.get('sounds_on'):
		return
	path_to_soundfile = gajim.config.get_per('soundevents', event, 'path')
	if path_to_soundfile == 'beep':
		print '\a' # make a speaker beep
		return
	if path_to_soundfile is None or not os.path.exists(path_to_soundfile):
		return
	if os.name == 'nt':
		try:
			winsound.PlaySound(path_to_soundfile,
				winsound.SND_FILENAME|winsound.SND_ASYNC)
		except:
			pass
	elif os.name == 'posix':
		if gajim.config.get('soundplayer') == '':
			return
		player = gajim.config.get('soundplayer')
		# we add the path in "" so we have good parsing from shell
		path_to_soundfile = path_to_soundfile.replace('"', '\\"') # escape "
		command = player + ' "' + path_to_soundfile + '" &'
		#FIXME: when we require 2.4+ use subprocess module
		os.system(command)

def get_file_path_from_dnd_dropped_uri(uri):
	path = urllib.url2pathname(uri) # escape special chars
	path = path.strip('\r\n\x00') # remove \r\n and NULL
	# get the path to file
	if path.startswith('file:\\\\\\'): # windows
		path = path[8:] # 8 is len('file:///')
	elif path.startswith('file://'): # nautilus, rox
		path = path[7:] # 7 is len('file://')
	elif path.startswith('file:'): # xffm
		path = path[5:] # 5 is len('file:')
	return path

def from_xs_boolean_to_python_boolean(value):
	# this is xs:boolean so 'true', 'false', '1', '0'
	# convert those to True/False (python booleans)
	if value in ('1', 'true'):
		val = True
	else: # '0', 'false' or anything else
		val = False

	return val

def ensure_unicode_string(s):
	# py23 u'abc'.decode('utf-8') raises
	# python24 does not. if python23 is ooold we can remove this func
	# FIXME: remove this when we abandon py23
	if isinstance(s, str):
		s = s.decode('utf-8')
	return s

def get_xmpp_show(show):
	if show in ('online', 'offline'):
		return None
	return show

def get_output_of_command(command):
	try:
		child_stdin, child_stdout = os.popen2(command)
	except ValueError:
		return None

	output = child_stdout.readlines()
	child_stdout.close()
	child_stdin.close()

	return output

def get_global_show():
	maxi = 0
	for account in gajim.connections:
		if not gajim.config.get_per('accounts', account,
			'sync_with_global_status'):
			continue
		connected = gajim.connections[account].connected
		if connected > maxi:
			maxi = connected
	return gajim.SHOW_LIST[maxi]

def get_global_status():
	maxi = 0
	for account in gajim.connections:
		if not gajim.config.get_per('accounts', account,
			'sync_with_global_status'):
			continue
		connected = gajim.connections[account].connected
		if connected > maxi:
			maxi = connected
			status = gajim.connections[account].status
	return status

def get_icon_name_to_show(contact, account = None):
	'''Get the icon name to show in online, away, requested, ...'''
	if account and gajim.awaiting_events[account].has_key(contact.jid):
		return 'message'
	if account and gajim.awaiting_events[account].has_key(
	contact.get_full_jid()):
		return 'message'
	if contact.jid.find('@') <= 0: # if not '@' or '@' starts the jid ==> agent
		return contact.show
	if contact.sub in ('both', 'to'):
		return contact.show
	if contact.ask == 'subscribe':
		return 'requested'
	transport = gajim.get_transport_name_from_jid(contact.jid)
	if transport:
		return contact.show
	return 'not in roster'

def decode_string(string):
	'''try to decode (to make it Unicode instance) given string'''
	# by the time we go to iso15 it better be the one else we show bad characters
	encodings = (sys.getfilesystemencoding(), 'utf-8', 'iso-8859-15')
	for encoding in encodings:
		try:
			string = string.decode(encoding)
		except UnicodeError:
			continue
		break

	return string

def get_windows_reg_env(varname, default=''):
	'''asks for paths commonly used but not exposed as ENVs
	in english Windows 2003 those are:
	'AppData' = %USERPROFILE%\Application Data (also an ENV)
	'Desktop' = %USERPROFILE%\Desktop
	'Favorites' = %USERPROFILE%\Favorites
	'NetHood' = %USERPROFILE%\NetHood
	'Personal' = D:\My Documents (PATH TO MY DOCUMENTS)
	'PrintHood' = %USERPROFILE%\PrintHood
	'Programs' = %USERPROFILE%\Start Menu\Programs
	'Recent' = %USERPROFILE%\Recent
	'SendTo' = %USERPROFILE%\SendTo
	'Start Menu' = %USERPROFILE%\Start Menu
	'Startup' = %USERPROFILE%\Start Menu\Programs\Startup
	'Templates' = %USERPROFILE%\Templates
	'My Pictures' = D:\My Documents\My Pictures
	'Local Settings' = %USERPROFILE%\Local Settings
	'Local AppData' = %USERPROFILE%\Local Settings\Application Data
	'Cache' = %USERPROFILE%\Local Settings\Temporary Internet Files
	'Cookies' = %USERPROFILE%\Cookies
	'History' = %USERPROFILE%\Local Settings\History
	'''

	if os.name != 'nt':
		return ''

	val = default
	try:
		rkey = win32api.RegOpenKey(win32con.HKEY_CURRENT_USER,
r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders')
		try:
			val = str(win32api.RegQueryValueEx(rkey, varname)[0])
			val = win32api.ExpandEnvironmentStrings(val) # expand using environ
		except:
			pass
	finally:
		win32api.RegCloseKey(rkey)
	return val
 
def get_my_pictures_path():
	'''windows-only atm. [Unix lives in the past]'''
	return get_windows_reg_env('My Pictures')

def get_desktop_path():
	if os.name == 'nt':
		path = get_windows_reg_env('Desktop')
	else:
		path = os.path.join(os.path.expanduser('~'), 'Desktop')
	return path

def get_documents_path():
	if os.name == 'nt':
		path = get_windows_reg_env('Personal')
	else:
		path = os.path.expanduser('~')
	return path

# moved from connection.py
def get_full_jid_from_iq(iq_obj):
	'''return the full jid (with resource) from an iq as unicode'''
	return parse_jid(str(iq_obj.getFrom()))

def get_jid_from_iq(iq_obj):
	'''return the jid (without resource) from an iq as unicode'''
	jid = get_full_jid_from_iq(iq_obj)
	return gajim.get_jid_without_resource(jid)

def get_auth_sha(sid, initiator, target):
	''' return sha of sid + initiator + target used for proxy auth'''
	return sha.new("%s%s%s" % (sid, initiator, target)).hexdigest()


distro_info = {
	'Arch Linux': '/etc/arch-release',
	'Aurox Linux': '/etc/aurox-release',
	'Conectiva Linux': '/etc/conectiva-release',
	'CRUX': '/usr/bin/crux',
	'Debian GNU/Linux': '/etc/debian_release',
	'Debian GNU/Linux': '/etc/debian_version',
	'Fedora Linux': '/etc/fedora-release',
	'Gentoo Linux': '/etc/gentoo-release',
	'Linux from Scratch': '/etc/lfs-release',
	'Mandrake Linux': '/etc/mandrake-release',
	'Slackware Linux': '/etc/slackware-release',
	'Slackware Linux': '/etc/slackware-version',
	'Solaris/Sparc': '/etc/release',
	'Source Mage': '/etc/sourcemage_version',
	'SUSE Linux': '/etc/SuSE-release',
	'Sun JDS': '/etc/sun-release',
	'PLD Linux': '/etc/pld-release',
	'Yellow Dog Linux': '/etc/yellowdog-release',
	# many distros use the /etc/redhat-release for compatibility
	# so Redhat is the last
	'Redhat Linux': '/etc/redhat-release'
}

def get_random_string_16():
	''' create random string of length 16'''
	rng = range(65, 90)
	rng.extend(range(48, 57))
	char_sequence = map(lambda e:chr(e), rng)
	from random import sample
	return reduce(lambda e1, e2: e1 + e2, 
			sample(char_sequence, 16))
	
def get_os_info():
	if os.name == 'nt':
		ver = os.sys.getwindowsversion()
		ver_format = ver[3], ver[0], ver[1]
		win_version = {
			(1, 4, 0): '95',
			(1, 4, 10): '98',
			(1, 4, 90): 'ME',
			(2, 4, 0): 'NT',
			(2, 5, 0): '2000',
			(2, 5, 1): 'XP',
			(2, 5, 2): '2003'
		}
		if win_version.has_key(ver_format):
			return 'Windows' + ' ' + win_version[ver_format]
		else:
			return 'Windows'
	elif os.name == 'posix':
		executable = 'lsb_release'
		params = ' --id --codename --release --short'
		full_path_to_executable = is_in_path(executable, return_abs_path = True)
		if full_path_to_executable:
			command = executable + params
			child_stdin, child_stdout = os.popen2(command)
			output = temp_failure_retry(child_stdout.readline).strip()
			child_stdout.close()
			child_stdin.close()
			# some distros put n/a in places, so remove those
			output = output.replace('n/a', '').replace('N/A', '')
			return output

		# lsb_release executable not available, so parse files
		for distro_name in distro_info:
			path_to_file = distro_info[distro_name]
			if os.path.exists(path_to_file):
				if os.access(path_to_file, os.X_OK):
					# the file is executable (f.e. CRUX)
					# yes, then run it and get the first line of output.
					text = get_output_of_command(path_to_file)[0]
				else:
					fd = open(path_to_file)
					text = fd.readline().strip() # get only first line
					fd.close()
					if path_to_file.endswith('version'):
						# sourcemage_version has all the info we need
						if not os.path.basename(path_to_file).startswith('sourcemage'):
							text = distro_name + ' ' + text
					elif path_to_file.endswith('aurox-release'):
						# file doesn't have version
						text = distro_name
					elif path_to_file.endswith('lfs-release'): # file just has version
						text = distro_name + ' ' + text
				return text

		# our last chance, ask uname and strip it
		uname_output = get_output_of_command('uname -a | cut -d" " -f1,3')
		if uname_output is not None:
			return uname_output[0] # only first line
	return 'N/A'

def sanitize_filename(filename):
	'''makes sure the filename we will write does contain only
	acceptable and latin characters'''
	filename = punycode_encode(filename) # make it latin chars only
	filename = filename.replace('/', '_')
	if os.name == 'nt':
		filename = filename.replace('?', '_').replace(':', '_')\
			.replace('\\', '_').replace('"', "'").replace('|', '_')\
			.replace('*', '_').replace('<', '_').replace('>', '_')
	   # 48 is the limit
		if len(filename) > 48:
			extension = filename.split('.')[-1]
			filename = filename[0:48]
	
	return filename

def allow_showing_notification(account):
	'''is it allowed to show nofication?
	check OUR status and if we allow notifications for that status'''
	if gajim.config.get('autopopupaway'): # always show notification
		return True
	if gajim.connections[account].connected in (2, 3): # we're online or chat
		return True
	return False

def allow_popup_window(account):
	'''is it allowed to popup windows?'''
	autopopup = gajim.config.get('autopopup')
	autopopupaway = gajim.config.get('autopopupaway')
	if autopopup and (autopopupaway or \
	gajim.connections[account].connected in (2, 3)): # we're online or chat
		return True
	return False
