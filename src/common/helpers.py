# -*- coding:utf-8 -*-
## src/common/helpers.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

import re
import locale
import os
import subprocess
import urllib
import errno
import select
import sha
import base64
import sys
from encodings.punycode import punycode_encode

import gajim
from i18n import Q_
from i18n import ngettext
import xmpp

try:
	# Python 2.5
	import hashlib
	hash_md5  = hashlib.md5
	hash_sha1 = hashlib.sha1
except ImportError:
	# Python 2.4
	import md5
	import sha
	hash_md5 = md5.new
	hash_sha1 = sha.new

try:
	from osx import nsapp
except ImportError:
	pass

try:
	import winsound # windows-only built-in module for playing wav
	import win32api
	import win32con
except Exception:
	pass

special_groups = (_('Transports'), _('Not in Roster'), _('Observers'), _('Groupchats'))

class InvalidFormat(Exception):
	pass

def decompose_jid(jidstring):
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
	return user, server, resource

def parse_jid(jidstring):
	'''Perform stringprep on all JID fragments from a string
	and return the full jid'''
	# This function comes from http://svn.twistedmatrix.com/cvs/trunk/twisted/words/protocols/jabber/jid.py

	return prep(*decompose_jid(jidstring))

def idn_to_ascii(host):
	'''convert IDN (Internationalized Domain Names) to ACE
	(ASCII-compatible encoding)'''
	from encodings import idna
	labels = idna.dots.split(host)
	converted_labels = []
	for label in labels:
		converted_labels.append(idna.ToASCII(label))
	return ".".join(converted_labels)

def ascii_to_idn(host):
	'''convert ACE (ASCII-compatible encoding) to IDN
	(Internationalized Domain Names)'''
	from encodings import idna
	labels = idna.dots.split(host)
	converted_labels = []
	for label in labels:
		converted_labels.append(idna.ToUnicode(label))
	return ".".join(converted_labels)

def parse_resource(resource):
	'''Perform stringprep on resource and return it'''
	if resource:
		try:
			from xmpp_stringprep import resourceprep
			return resourceprep.prepare(unicode(resource))
		except UnicodeError:
			raise InvalidFormat, 'Invalid character in resource.'

def prep(user, server, resource):
	'''Perform stringprep on all JID fragments and return the full jid'''
	# This function comes from
	#http://svn.twistedmatrix.com/cvs/trunk/twisted/words/protocols/jabber/jid.py

	if user:
		try:
			from xmpp_stringprep import nodeprep
			user = nodeprep.prepare(unicode(user))
		except UnicodeError:
			raise InvalidFormat, _('Invalid character in username.')
	else:
		user = None

	if not server:
		raise InvalidFormat, _('Server address required.')
	else:
		try:
			from xmpp_stringprep import nameprep
			server = nameprep.prepare(unicode(server))
		except UnicodeError:
			raise InvalidFormat, _('Invalid character in hostname.')

	if resource:
		try:
			from xmpp_stringprep import resourceprep
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
		if name in contacts_dict:
			contact1 = contacts_dict[name]
			del contacts_dict[name]
			contacts_dict['%s (%s)' % (name, contact1.jid)] = contact1
			contacts_dict['%s (%s)' % (name, jid)] = contact
		else:
			if contact.name == gajim.get_nick_from_jid(jid):
				del contacts_dict[jid]
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
	
def get_uf_affiliation(affiliation):
	'''Get a nice and translated affilition for muc'''
	if affiliation == 'none': 
		affiliation_name = Q_('?Group Chat Contact Affiliation:None')
	elif affiliation == 'owner':
		affiliation_name = _('Owner')
	elif affiliation == 'admin':
		affiliation_name = _('Administrator')
	elif affiliation == 'member':
		affiliation_name = _('Member')
	else: # Argl ! An unknown affiliation !
		affiliation_name = affiliation.capitalize()
	return affiliation_name

def get_sorted_keys(adict):
	keys = sorted(adict.keys())
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
	expr = re.compile(r'(?<!\\)\\n')
	msg = expr.sub('\n', msg)
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
		#paused means he or she was composing but has stopped for a while
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
	path = os.getenv('PATH').split(os.pathsep)
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

def exec_command(command):
	subprocess.Popen(command, shell = True)

def build_command(executable, parameter):
	# we add to the parameter (can hold path with spaces)
	# "" so we have good parsing from shell
	parameter = parameter.replace('"', '\\"') # but first escape "
	command = '%s "%s"' % (executable, parameter)
	return command

def launch_browser_mailer(kind, uri):
	#kind = 'url' or 'mail'
	if os.name == 'nt':
		try:
			os.startfile(uri) # if pywin32 is installed we open
		except Exception:
			pass

	else:
		if kind == 'mail' and not uri.startswith('mailto:'):
			uri = 'mailto:' + uri

		if gajim.config.get('openwith') == 'gnome-open':
			command = 'gnome-open'
		elif gajim.config.get('openwith') == 'kfmclient exec':
			command = 'kfmclient exec'
		elif gajim.config.get('openwith') == 'exo-open':
			command = 'exo-open'
		elif ((sys.platform == 'darwin') and\
		(gajim.config.get('openwith') == 'open')):
			command = 'open'
		elif gajim.config.get('openwith') == 'custom':
			if kind == 'url':
				command = gajim.config.get('custombrowser')
			if kind == 'mail':
				command = gajim.config.get('custommailapp')
			if command == '': # if no app is configured
				return

		command = build_command(command, uri)
		try:
			exec_command(command)
		except Exception:
			pass

def launch_file_manager(path_to_open):
	if os.name == 'nt':
		try:
			os.startfile(path_to_open) # if pywin32 is installed we open
		except Exception:
			pass
	else:
		if gajim.config.get('openwith') == 'gnome-open':
			command = 'gnome-open'
		elif gajim.config.get('openwith') == 'kfmclient exec':
			command = 'kfmclient exec'
		elif gajim.config.get('openwith') == 'exo-open':
			command = 'exo-open'
		elif ((sys.platform == 'darwin') and\
		(gajim.config.get('openwith') == 'open')):
			command = 'open'
		elif gajim.config.get('openwith') == 'custom':
			command = gajim.config.get('custom_file_manager')
		if command == '': # if no app is configured
			return
		command = build_command(command, path_to_open)
		try:
			exec_command(command)
		except Exception:
			pass

def play_sound(event):
	if not gajim.config.get('sounds_on'):
		return
	path_to_soundfile = gajim.config.get_per('soundevents', event, 'path')
	play_sound_file(path_to_soundfile)

def play_sound_file(path_to_soundfile):
	if path_to_soundfile == 'beep':
		exec_command('beep')
		return
	if path_to_soundfile is None or not os.path.exists(path_to_soundfile):
		return
	if sys.platform == 'darwin':
		try:
			nsapp.playFile(path_to_soundfile)
		except NameError:
			pass
	elif os.name == 'nt':
		try:
			winsound.PlaySound(path_to_soundfile,
				winsound.SND_FILENAME|winsound.SND_ASYNC)
		except Exception:
			pass
	elif os.name == 'posix':
		if gajim.config.get('soundplayer') == '':
			return
		player = gajim.config.get('soundplayer')
		command = build_command(player, path_to_soundfile)
		exec_command(command)

def get_file_path_from_dnd_dropped_uri(uri):
	path = urllib.unquote(uri) # escape special chars
	path = path.strip('\r\n\x00') # remove \r\n and NULL
	# get the path to file
	if re.match('^file:///[a-zA-Z]:/', path): # windows
		path = path[8:] # 8 is len('file:///')
	elif path.startswith('file://'): # nautilus, rox
		if sys.platform == 'darwin':
			# OS/X includes hostname in file:// URI
			path = re.sub('file://[^/]*', '', path)
		else:
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

def statuses_unified(): 
	'''testing if all statuses are the same.'''
	reference = None
	for account in gajim.connections:
		if not gajim.config.get_per('accounts', account,
		'sync_with_global_status'):
			continue
		if reference is None:
			reference = gajim.connections[account].connected
		elif reference != gajim.connections[account].connected:
			return False
	return True

def get_icon_name_to_show(contact, account = None):
	'''Get the icon name to show in online, away, requested, ...'''
	if account and gajim.events.get_nb_roster_events(account, contact.jid):
		return 'event'
	if account and gajim.events.get_nb_roster_events(account,
	contact.get_full_jid()):
		return 'event'
	if account and account in gajim.interface.minimized_controls and \
	contact.jid in gajim.interface.minimized_controls[account] and gajim.interface.\
		minimized_controls[account][contact.jid].get_nb_unread_pm() > 0:
		return 'event'
	if account and contact.jid in gajim.gc_connected[account]:
		if gajim.gc_connected[account][contact.jid]:
			return 'muc_active'
		else:
			return 'muc_inactive'
	if contact.jid.find('@') <= 0: # if not '@' or '@' starts the jid ==> agent
		return contact.show
	if contact.sub in ('both', 'to'):
		return contact.show
	if contact.ask == 'subscribe':
		return 'requested'
	transport = gajim.get_transport_name_from_jid(contact.jid)
	if transport:
		return contact.show
	if contact.show in gajim.SHOW_LIST:
		return contact.show
	return 'not in roster'

def decode_string(string):
	'''try to decode (to make it Unicode instance) given string'''
	if isinstance(string, unicode):
		return string
	# by the time we go to iso15 it better be the one else we show bad characters
	encodings = (locale.getpreferredencoding(), 'utf-8', 'iso-8859-15')
	for encoding in encodings:
		try:
			string = string.decode(encoding)
		except UnicodeError:
			continue
		break

	return string

def ensure_utf8_string(string):
	'''make sure string is in UTF-8'''
	try:
		string = decode_string(string).encode('utf-8')
	except Exception:
		pass
	return string

def remove_invalid_xml_chars(string):
	if string:
		string = re.sub(gajim.interface.invalid_XML_chars_re, '', string)
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
		except Exception:
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
	return ''.join(sample(char_sequence, 16))
	
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
			(2, 5, 2): '2003',
			(2, 6, 0): 'Vista',
		}
		if ver_format in win_version:
			return 'Windows' + ' ' + win_version[ver_format]
		else:
			return 'Windows'
	elif os.name == 'posix':
		executable = 'lsb_release'
		params = ' --description --codename --release --short'
		full_path_to_executable = is_in_path(executable, return_abs_path = True)
		if full_path_to_executable:
			command = executable + params
			p = subprocess.Popen([command], shell=True, stdin=subprocess.PIPE, 
				stdout=subprocess.PIPE, close_fds=True) 
			p.wait() 
			output = temp_failure_retry(p.stdout.readline).strip()
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
						# sourcemage_version and slackware-version files
						# have all the info we need (name and version of distro)
						if not os.path.basename(path_to_file).startswith(
						'sourcemage') or not\
						os.path.basename(path_to_file).startswith('slackware'):
							text = distro_name + ' ' + text
					elif path_to_file.endswith('aurox-release') or \
					path_to_file.endswith('arch-release'):
						# file doesn't have version
						text = distro_name
					elif path_to_file.endswith('lfs-release'): # file just has version
						text = distro_name + ' ' + text
				return text.replace('\n', '')

		# our last chance, ask uname and strip it
		uname_output = get_output_of_command('uname -sr')
		if uname_output is not None:
			return uname_output[0] # only first line
	return 'N/A'

def sanitize_filename(filename):
	'''makes sure the filename we will write does contain only acceptable and 
	latin characters, and is not too long (in that case hash it)'''
	# 48 is the limit
	if len(filename) > 48:
		hash = hash_md5(filename)
		filename = base64.b64encode(hash.digest())

	filename = punycode_encode(filename) # make it latin chars only
	filename = filename.replace('/', '_')
	if os.name == 'nt':
		filename = filename.replace('?', '_').replace(':', '_')\
			.replace('\\', '_').replace('"', "'").replace('|', '_')\
			.replace('*', '_').replace('<', '_').replace('>', '_')
	
	return filename

def allow_showing_notification(account, type_ = 'notify_on_new_message',
advanced_notif_num = None, is_first_message = True):
	'''is it allowed to show nofication?
	check OUR status and if we allow notifications for that status
	type is the option that need to be True e.g.: notify_on_signing
	is_first_message: set it to false when it's not the first message'''
	if advanced_notif_num is not None:
		popup = gajim.config.get_per('notifications', str(advanced_notif_num),
			'popup')
		if popup == 'yes':
			return True
		if popup == 'no':
			return False
	if type_ and (not gajim.config.get(type_) or not is_first_message):
		return False
	if gajim.config.get('autopopupaway'): # always show notification
		return True
	if gajim.connections[account].connected in (2, 3): # we're online or chat
		return True
	return False

def allow_popup_window(account, advanced_notif_num = None):
	'''is it allowed to popup windows?'''
	if advanced_notif_num is not None:
		popup = gajim.config.get_per('notifications', str(advanced_notif_num),
			'auto_open')
		if popup == 'yes':
			return True
		if popup == 'no':
			return False
	autopopup = gajim.config.get('autopopup')
	autopopupaway = gajim.config.get('autopopupaway')
	if autopopup and (autopopupaway or \
	gajim.connections[account].connected in (2, 3)): # we're online or chat
		return True
	return False

def allow_sound_notification(sound_event, advanced_notif_num = None):
	if advanced_notif_num is not None:
		sound = gajim.config.get_per('notifications', str(advanced_notif_num),
			'sound')
		if sound == 'yes':
			return True
		if sound == 'no':
			return False
	if gajim.config.get_per('soundevents', sound_event, 'enabled'):
		return True
	return False

def get_chat_control(account, contact):
	full_jid_with_resource = contact.jid
	if contact.resource:
		full_jid_with_resource += '/' + contact.resource
	highest_contact = gajim.contacts.get_contact_with_highest_priority(
		account, contact.jid)

	# Look for a chat control that has the given resource, or default to
	# one without resource
	ctrl = gajim.interface.msg_win_mgr.get_control(full_jid_with_resource,
		account)

	if ctrl:
		return ctrl
	elif highest_contact and highest_contact.resource and \
	contact.resource != highest_contact.resource:
		return None
	else:
		# unknown contact or offline message
		return gajim.interface.msg_win_mgr.get_control(contact.jid, account)

def reduce_chars_newlines(text, max_chars = 0, max_lines = 0):
	'''Cut the chars after 'max_chars' on each line
	and show only the first 'max_lines'.
	If any of the params is not present (None or 0) the action
	on it is not performed'''

	def _cut_if_long(string):
		if len(string) > max_chars:
			string = string[:max_chars - 3] + '...'
		return string

	if isinstance(text, str):
		text = text.decode('utf-8')

	if max_lines == 0:
		lines = text.split('\n')
	else:
		lines = text.split('\n', max_lines)[:max_lines]
	if max_chars > 0:
		if lines:
			lines = map(lambda e: _cut_if_long(e), lines)
	if lines:
		reduced_text = '\n'.join(lines)
		if reduced_text != text:
			reduced_text += '...'
	else:
		reduced_text = ''
	return reduced_text

def get_account_status(account):
	status = reduce_chars_newlines(account['status_line'], 100, 1)
	return status

def get_notification_icon_tooltip_dict():
	'''returns a dict of the form {acct: {'show': show, 'message': message, 
	'event_lines': [list of text lines to show in tooltip]}'''
	# How many events must there be before they're shown summarized, not per-user
	max_ungrouped_events = 10

	accounts = get_accounts_info()

	# Gather events. (With accounts, when there are more.)
	for account in accounts:
		account_name = account['name']
		account['event_lines'] = []
		# Gather events per-account
		pending_events = gajim.events.get_events(account = account_name)
		messages, non_messages, total_messages, total_non_messages = {}, {}, 0, 0
		for jid in pending_events:
			for event in pending_events[jid]:
				if event.type_.count('file') > 0:
					# This is a non-messagee event.
					messages[jid] = non_messages.get(jid, 0) + 1
					total_non_messages = total_non_messages + 1
				else:
					# This is a message.
					messages[jid] = messages.get(jid, 0) + 1
					total_messages = total_messages + 1
		# Display unread messages numbers, if any
		if total_messages > 0:
			if total_messages > max_ungrouped_events:
				text = ngettext(
					'%d message pending',
					'%d messages pending',
					total_messages, total_messages, total_messages)
				account['event_lines'].append(text)
			else:
				for jid in messages.keys():
					text = ngettext(
						'%d message pending',
						'%d messages pending',
						messages[jid], messages[jid], messages[jid])
					contact = gajim.contacts.get_first_contact_from_jid(
						account['name'], jid)
					if jid in gajim.gc_connected[account['name']]:
						text += _(' from room %s') % (jid)
					elif contact:
						name = contact.get_shown_name()
						text += _(' from user %s') % (name)
					else:
						text += _(' from %s') % (jid)
					account['event_lines'].append(text)
		
		# Display unseen events numbers, if any
		if total_non_messages > 0:
			if total_non_messages > max_ungrouped_events:
				text = ngettext(
					'%d event pending',
					'%d events pending',
					total_non_messages, total_non_messages, total_non_messages)
				accounts[account]['event_lines'].append(text)
			else:
				for jid in non_messages.keys():
					text = ngettext(
						'%d event pending',
						'%d events pending',
						non_messages[jid], non_messages[jid], non_messages[jid])
					text += _(' from user %s') % (jid)
					accounts[account]['event_lines'].append(text)

	return accounts

def get_notification_icon_tooltip_text():
	text = None
	# How many events must there be before they're shown summarized, not per-user
	max_ungrouped_events = 10
	# Character which should be used to indent in the tooltip.
	indent_with = ' '

	accounts = get_notification_icon_tooltip_dict()

	if len(accounts) == 0:
		# No configured account
		return _('Gajim')

	# at least one account present

	# Is there more that one account?
	if len(accounts) == 1:
		show_more_accounts = False
	else:
		show_more_accounts = True

	# If there is only one account, its status is shown on the first line.
	if show_more_accounts:
		text = _('Gajim')
	else:		
		text = _('Gajim - %s') % (get_account_status(accounts[0]))

	# Gather and display events. (With accounts, when there are more.)
	for account in accounts:
		account_name = account['name']
		# Set account status, if not set above
		if (show_more_accounts):
			message = '\n' + indent_with + ' %s - %s'
			text += message % (account_name, get_account_status(account))
			# Account list shown, messages need to be indented more
			indent_how = 2
		else:
			# If no account list is shown, messages could have default indenting.
			indent_how = 1
		for line in account['event_lines']:
			text += '\n' + indent_with * indent_how + ' '
			text += line
	return text

def get_accounts_info():
	'''helper for notification icon tooltip'''
	accounts = []
	accounts_list = sorted(gajim.contacts.get_accounts())
	for account in accounts_list:
		status_idx = gajim.connections[account].connected
		# uncomment the following to hide offline accounts
		# if status_idx == 0: continue
		status = gajim.SHOW_LIST[status_idx]
		message = gajim.connections[account].status
		single_line = get_uf_show(status)
		if message is None:
			message = ''
		else:
			message = message.strip()
		if message != '':
			single_line += ': ' + message
		accounts.append({'name': account, 'status_line': single_line, 
				'show': status, 'message': message})
	return accounts

def get_avatar_path(prefix):
	'''Returns the filename of the avatar, distinguishes between user- and
	contact-provided one.  Returns None if no avatar was found at all.
	prefix is the path to the requested avatar just before the ".png" or
	".jpeg".'''
	# First, scan for a local, user-set avatar
	for type_ in ('jpeg', 'png'):
		file_ = prefix + '_local.' + type_
		if os.path.exists(file_):
			return file_
	# If none available, scan for a contact-provided avatar
	for type_ in ('jpeg', 'png'):
		file_ = prefix + '.' + type_
		if os.path.exists(file_):
			return file_
	return None

def datetime_tuple(timestamp):
	'''Converts timestamp using strptime and the format: %Y%m%dT%H:%M:%S
	Because of various datetime formats are used the following exceptions
	are handled:
		- Optional milliseconds appened to the string are removed
		- Optional Z (that means UTC) appened to the string are removed
		- XEP-082 datetime strings have all '-' cahrs removed to meet
		  the above format.'''
	timestamp = timestamp.split('.')[0]
	timestamp = timestamp.replace('-', '')
	timestamp = timestamp.replace('z', '')
	timestamp = timestamp.replace('Z', '')
	from time import strptime
	return strptime(timestamp, '%Y%m%dT%H:%M:%S')

def get_iconset_path(iconset):
	if os.path.isdir(os.path.join(gajim.DATA_DIR, 'iconsets', iconset)):
		return os.path.join(gajim.DATA_DIR, 'iconsets', iconset)
	elif os.path.isdir(os.path.join(gajim.MY_ICONSETS_PATH, iconset)):
		return os.path.join(gajim.MY_ICONSETS_PATH, iconset)

def get_mood_iconset_path(iconset):
	if os.path.isdir(os.path.join(gajim.DATA_DIR, 'moods', iconset)):
		return os.path.join(gajim.DATA_DIR, 'moods', iconset)
	elif os.path.isdir(os.path.join(gajim.MY_MOOD_ICONSETS_PATH, iconset)):
		return os.path.join(gajim.MY_MOOD_ICONSETS_PATH, iconset)

def get_activity_iconset_path(iconset):
	if os.path.isdir(os.path.join(gajim.DATA_DIR, 'activities', iconset)):
		return os.path.join(gajim.DATA_DIR, 'activities', iconset)
	elif os.path.isdir(os.path.join(gajim.MY_ACTIVITY_ICONSETS_PATH,
	iconset)):
		return os.path.join(gajim.MY_ACTIVITY_ICONSETS_PATH, iconset)

def get_transport_path(transport):
	if os.path.isdir(os.path.join(gajim.DATA_DIR, 'iconsets', 'transports',
	transport)):
		return os.path.join(gajim.DATA_DIR, 'iconsets', 'transports', transport)
	elif os.path.isdir(os.path.join(gajim.MY_ICONSETS_PATH, 'transports',
	transport)):
		return os.path.join(gajim.MY_ICONSETS_PATH, 'transports', transport)
	# No transport folder found, use default jabber one
	return get_iconset_path(gajim.config.get('iconset'))

def prepare_and_validate_gpg_keyID(account, jid, keyID):
	'''Returns an eight char long keyID that can be used with for GPG encryption with this contact.
	If the given keyID is None, return UNKNOWN; if the key does not match the assigned key
	XXXXXXXXMISMATCH is returned. If the key is trusted and not yet assigned, assign it'''
	if gajim.connections[account].USE_GPG:	
		if keyID and len(keyID) == 16:
			keyID = keyID[8:]
		
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		
		if jid in attached_keys and keyID:
			attachedkeyID = attached_keys[attached_keys.index(jid) + 1]
			if attachedkeyID != keyID:
				# Mismatch! Another gpg key was expected
				keyID += 'MISMATCH'
		elif jid in attached_keys:
			# An unsigned presence, just use the assigned key
			keyID = attached_keys[attached_keys.index(jid) + 1]
		elif keyID: 
			public_keys = gajim.connections[account].ask_gpg_keys()
			# Assign the corresponding key, if we have it in our keyring
			if keyID in public_keys:
				for u in gajim.contacts.get_contacts(account, jid):
					u.keyID = keyID
				keys_str = gajim.config.get_per('accounts', account, 'attached_gpg_keys')
				keys_str += jid + ' ' + keyID + ' '
				gajim.config.set_per('accounts', account, 'attached_gpg_keys', keys_str)
		elif keyID is None:
			keyID = 'UNKNOWN'
	return keyID

def sort_identities_func(i1, i2):
	cat1 = i1['category']
	cat2 = i2['category']
	if cat1 < cat2:
		return -1
	if cat1 > cat2:
		return 1
	type1 = i1.get('type', '')
	type2 = i2.get('type', '')
	if type1 < type2:
		return -1
	if type1 > type2:
		return 1
	lang1 = i1.get('xml:lang', '')
	lang2 = i2.get('xml:lang', '')
	if lang1 < lang2:
		return -1
	if lang1 > lang2:
		return 1
	return 0

def sort_dataforms_func(d1, d2):
	f1 = d1.getField('FORM_TYPE')
	f2 = d2.getField('FORM_TYPE')
	if f1 and f2 and (f1.getValue() < f2.getValue()):
		return -1
	return 1

def compute_caps_hash(identities, features, dataforms=[], hash_method='sha-1'):
	'''Compute caps hash according to XEP-0115, V1.5
	
	dataforms are xmpp.DataForms objects as common.dataforms don't allow several
	values without a field type list-multi'''
	S = ''
	identities.sort(cmp=sort_identities_func)
	for i in identities:
		c = i['category']
		type_ = i.get('type', '')
		lang = i.get('xml:lang', '')
		name = i.get('name', '')
		S += '%s/%s/%s/%s<' % (c, type_, lang, name)
	features.sort()
	for f in features:
		S += '%s<' % f
	dataforms.sort(cmp=sort_dataforms_func)
	for dataform in dataforms:
		# fields indexed by var
		fields = {}
		for f in dataform.getChildren():
			fields[f.getVar()] = f
		form_type = fields.get('FORM_TYPE')
		if form_type:
			S += form_type.getValue() + '<'
			del fields['FORM_TYPE']
		vars = sorted(fields.keys())
		for var in vars:
			S += '%s<' % var
			values = sorted(fields[var].getValues())
			for value in values:
				S += '%s<' % value

	if hash_method == 'sha-1':
		hash = hash_sha1(S)
	elif hash_method == 'md5':
		hash = hash_md5(S)
	else:
		return ''
	return base64.b64encode(hash.digest())

def update_optional_features(account = None):
	if account:
		accounts = [account]
	else:
		accounts = [a for a in gajim.connections]
	for a in accounts:
		gajim.gajim_optional_features[a] = []
		if gajim.config.get_per('accounts', a, 'subscribe_mood'):
			gajim.gajim_optional_features[a].append(xmpp.NS_MOOD + '+notify')
		if gajim.config.get_per('accounts', a, 'subscribe_activity'):
			gajim.gajim_optional_features[a].append(xmpp.NS_ACTIVITY + '+notify')
		if gajim.config.get_per('accounts', a, 'publish_tune'):
			gajim.gajim_optional_features[a].append(xmpp.NS_TUNE)
		if gajim.config.get_per('accounts', a, 'subscribe_tune'):
			gajim.gajim_optional_features[a].append(xmpp.NS_TUNE + '+notify')
		if gajim.config.get_per('accounts', a, 'subscribe_nick'):
			gajim.gajim_optional_features[a].append(xmpp.NS_NICK + '+notify')
		if gajim.config.get('outgoing_chat_state_notifactions') != 'disabled':
			gajim.gajim_optional_features[a].append(xmpp.NS_CHATSTATES)
		if not gajim.config.get('ignore_incoming_xhtml'):
			gajim.gajim_optional_features[a].append(xmpp.NS_XHTML_IM)
		if gajim.HAVE_PYCRYPTO \
		and gajim.config.get_per('accounts', a, 'enable_esessions'):
			gajim.gajim_optional_features[a].append(xmpp.NS_ESESSION)
		if gajim.config.get_per('accounts', a, 'answer_receipts'):
			gajim.gajim_optional_features[a].append(xmpp.NS_RECEIPTS)
		gajim.caps_hash[a] = compute_caps_hash([gajim.gajim_identity],
			gajim.gajim_common_features + gajim.gajim_optional_features[a])
		# re-send presence with new hash
		connected = gajim.connections[a].connected
		if connected > 1 and gajim.SHOW_LIST[connected] != 'invisible':
			gajim.connections[a].change_status(gajim.SHOW_LIST[connected],
				gajim.connections[a].status)

# vim: se ts=3:
