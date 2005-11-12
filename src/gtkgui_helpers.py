##	gtkgui_helpers.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
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

import xml.sax.saxutils
import gtk
import gobject
import pango
import os
import sys

import vcard


HAS_PYWIN32 = True
if os.name == 'nt':
	try:
		import win32file
		import win32con
		import pywintypes
	except ImportError:
		HAS_PYWIN32 = False

from common import i18n
i18n.init()
_ = i18n._
from common import gajim
from common import helpers

screen_w = gtk.gdk.screen_width()
screen_h = gtk.gdk.screen_height()

def get_theme_font_for_option(theme, option):
	'''return string description of the font, stored in
	theme preferences'''
	font_name = gajim.config.get_per('themes', theme, option)
	font_desc = pango.FontDescription()
	font_prop_str =  gajim.config.get_per('themes', theme, option + 'attrs')
	if font_prop_str:
		if font_prop_str.find('B') != -1:
			font_desc.set_weight(pango.WEIGHT_BOLD)
		if font_prop_str.find('I') != -1:
			font_desc.set_style(pango.STYLE_ITALIC)
	fd = pango.FontDescription(font_name)
	fd.merge(font_desc, True)
	return fd.to_string()
	
def get_default_font():
	'''Get the desktop setting for application font
	first check for GNOME, then XFCE and last KDE
	it returns None on failure or else a string 'Font Size' '''
	
	try:
		import gconf
		# in try because daemon may not be there
		client = gconf.client_get_default()

		return helpers.ensure_unicode_string(
			client.get_string('/desktop/gnome/interface/font_name'))
	except:
		pass

	# try to get xfce default font
	# Xfce 4.2 adopts freedesktop.org's Base Directory Specification
	# see http://www.xfce.org/~benny/xfce/file-locations.html
	# and http://freedesktop.org/Standards/basedir-spec
	xdg_config_home = os.environ.get('XDG_CONFIG_HOME', '')
	if xdg_config_home == '':
		xdg_config_home = os.path.expanduser('~/.config') # default	
	xfce_config_file = os.path.join(xdg_config_home, 'xfce4/mcs_settings/gtk.xml')
	
	kde_config_file = os.path.expanduser('~/.kde/share/config/kdeglobals')
	
	if os.path.exists(xfce_config_file):
		try:
			for line in file(xfce_config_file):
				if line.find('name="Gtk/FontName"') != -1:
					start = line.find('value="') + 7
					return helpers.ensure_unicode_string(
						line[start:line.find('"', start)])
		except:
			#we talk about file
			print >> sys.stderr, _('Error: cannot open %s for reading') % xfce_config_file
	
	elif os.path.exists(kde_config_file):
		try:
			for line in file(kde_config_file):
				if line.find('font=') == 0: # font=Verdana,9,other_numbers
					start = 5 # 5 is len('font=')
					line = line[start:]
					values = line.split(',')
					font_name = values[0]
					font_size = values[1]
					font_string = '%s %s' % (font_name, font_size) # Verdana 9
					return helpers.ensure_unicode_string(font_string)
		except:
			#we talk about file
			print >> sys.stderr, _('Error: cannot open %s for reading') % kde_config_file
	
	return None
	
def reduce_chars_newlines(text, max_chars = 0, max_lines = 0, 
	widget = None):
	'''Cut the chars after 'max_chars' on each line
	and show only the first 'max_lines'. If there is more text
	to be shown, display the whole text in tooltip on 'widget'
	If any of the params is not present (None or 0) the action
	on it is not performed'''

	def _cut_if_long(str):
		if len(str) > max_chars:
			str = str[:max_chars - 3] + '...'
		return str
	
	if max_lines == 0:
		lines = text.split('\n')
	else:
		lines = text.split('\n', max_lines)[:max_lines]
	if max_chars > 0:
		if lines:
			lines = map(lambda e: _cut_if_long(e), lines)
	if lines:
		reduced_text = reduce(lambda e, e1: e + '\n' + e1, lines)
	else:
		reduced_text = ''
	if reduced_text != text and widget is not None:
		pass # FIXME show tooltip
	return reduced_text

def escape_for_pango_markup(string):
	# escapes < > & ' "
	# for pango markup not to break
	if string is None:
		return
	if gtk.pygtk_version >= (2, 8, 0) and gtk.gtk_version >= (2, 8, 0):
		escaped_str = gobject.markup_escape_text(string)
	else:
		escaped_str = xml.sax.saxutils.escape(string, {"'": '&apos;',
			'"': '&quot;'})
	
	return escaped_str

def autodetect_browser_mailer():
	# recognize the environment for appropriate browser/mailer
	if os.path.isdir('/proc'):
		# under Linux: checking if 'gnome-session' or
		# 'startkde' programs were run before gajim, by
		# checking /proc (if it exists)
		#
		# if something is unclear, read `man proc`;
		# if /proc exists, directories that have only numbers
		# in their names contain data about processes.
		# /proc/[xxx]/exe is a symlink to executable started
		# as process number [xxx].
		# filter out everything that we are not interested in:
		files = os.listdir('/proc')

		# files that doesn't have only digits in names...
		files = filter(str.isdigit, files)

		# files that aren't directories...
		files = filter(lambda f:os.path.isdir('/proc/' + f), files)

		# processes owned by somebody not running gajim...
		# (we check if we have access to that file)
		files = filter(lambda f:os.access('/proc/' + f +'/exe', os.F_OK), files)

		# be sure that /proc/[number]/exe is really a symlink
		# to avoid TBs in incorrectly configured systems
		files = filter(lambda f:os.path.islink('/proc/' + f + '/exe'), files)

		# list of processes
		processes = [os.path.basename(os.readlink('/proc/' + f +'/exe')) for f in files]
		if 'gnome-session' in processes:
			gajim.config.set('openwith', 'gnome-open')
		elif 'startkde' in processes:
			gajim.config.set('openwith', 'kfmclient exec')
		else:
			gajim.config.set('openwith', 'custom')

def move_window(window, x, y):
	'''moves the window but also checks if out of screen'''
	if x < 0:
		x = 0
	if y < 0:
		y = 0
	window.move(x, y)

def resize_window(window, w, h):
	'''resizes window but also checks if huge window or negative values'''
	if w > screen_w:
		w = screen_w
	if h > screen_h:
		h = screen_h
	window.resize(abs(w), abs(h))

def one_window_opened(typ):
	for account in gajim.connections:
		if not gajim.interface.windows[account].has_key(typ):
			continue
		if len(gajim.interface.windows[account][typ]):
			return True
	return False

class TagInfoHandler(xml.sax.ContentHandler):
	def __init__(self, tagname1, tagname2):
		xml.sax.ContentHandler.__init__(self)
		self.tagname1 = tagname1
		self.tagname2 = tagname2
		self.servers = []

	def startElement(self, name, attributes):
		if name == self.tagname1:
			for attribute in attributes.getNames():
				if attribute == 'jid':
					jid = attributes.getValue(attribute)
					# we will get the port next time so we just set it 0 here
					self.servers.append([jid, 0])
		elif name == self.tagname2:
			for attribute in attributes.getNames():
				if attribute == 'port':
					port = attributes.getValue(attribute)
					# we received the jid last time, so we now assign the port
					# number to the last jid in the list
					self.servers[-1][1] = port

	def endElement(self, name):
		pass

def parse_server_xml(path_to_file):
	try:
		handler = TagInfoHandler('item', 'active')
		xml.sax.parse(path_to_file, handler)
		return handler.servers
	# handle exception if unable to open file
	except IOError, message:
		print >> sys.stderr, _('Error reading file:'), message
	# handle exception parsing file
	except xml.sax.SAXParseException, message:
		print >> sys.stderr, _('Error parsing file:'), message

def set_unset_urgency_hint(window, unread_messages_no):
	'''sets/unsets urgency hint in window argument
	depending if we have unread messages or not'''
	if gtk.gtk_version >= (2, 8, 0) and gtk.pygtk_version >= (2, 8, 0):
		if unread_messages_no > 0:
			window.props.urgency_hint = True
		else:
			window.props.urgency_hint = False

def get_abspath_for_script(scriptname, want_type = False):
	'''checks if we are svn or normal user and returns abspath to asked script
	if want_type is True we return 'svn' or 'install' '''
	if os.path.isdir('.svn'): # we are svn user
		type = 'svn'
		cwd = os.getcwd() # it's always ending with src

		if scriptname == 'gajim-remote':
			path_to_script = cwd + '/gajim-remote.py'
		
		elif scriptname == 'gajim':
			script = '#!/bin/sh\n' # the script we may create
			script += 'cd %s' % cwd
			path_to_script = cwd + '/../scripts/gajim_sm_script'
				
			try:
				if os.path.exists(path_to_script):
					os.remove(path_to_script)

				f = open(path_to_script, 'w')
				script += '\nexec python -OOt gajim.py $0 $@\n'
				f.write(script)
				f.close()
				os.chmod(path_to_script, 0700)
			except OSError: # do not traceback (could be a permission problem)
				#we talk about a file here
				s = _('Could not write to %s. Session Management support will not work') % path_to_script
				print >> sys.stderr, s

	else: # normal user (not svn user)
		type = 'install'
		# always make it like '/usr/local/bin/gajim'
		path_to_script = helpers.is_in_path(scriptname, True)
		
	
	if want_type:
		return path_to_script, type
	else:
		return path_to_script

def get_pixbuf_from_data(file_data):
	'''Gets image data and returns gtk.gdk.Pixbuf'''
	pixbufloader = gtk.gdk.PixbufLoader()
	try:
		pixbufloader.write(file_data)
		pixbufloader.close()
		pixbuf = pixbufloader.get_pixbuf()
	except gobject.GError: # 'unknown image format'
		pixbuf = None

	return pixbuf

def get_invisible_cursor():
	pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
	color = gtk.gdk.Color()
	cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
	return cursor

def get_current_desktop(window):
	'''returns the current virtual desktop for given window
	NOTE: window is GDK window'''
	prop = window.property_get('_NET_CURRENT_DESKTOP')
	if prop is None: # it means it's normal window (not root window)
		# so we look for it's current virtual desktop in another property
		prop = window.property_get('_NET_WM_DESKTOP')

	if prop is not None:
		# f.e. prop is ('CARDINAL', 32, [0]) we want 0 or 1.. from [0]
		current_virtual_desktop_no = prop[2][0]
		return current_virtual_desktop_no

def possibly_move_window_in_current_desktop(window):
	'''moves GTK window to current virtual desktop if it is not in the
	current virtual desktop
	window is GTK window'''
	if os.name == 'nt':
		return

	root_window = gtk.gdk.screen_get_default().get_root_window()
	# current user's vd
	current_virtual_desktop_no = get_current_desktop(root_window)
	
	# vd roster window is in
	window_virtual_desktop = get_current_desktop(window.window)

	# if one of those is None, something went wrong and we cannot know
	# VD info, just hide it (default action) and not show it afterwards
	if None not in (window_virtual_desktop, current_virtual_desktop_no):
		if current_virtual_desktop_no != window_virtual_desktop:
			# we are in another VD that the window was
			# so show it in current VD
			window.show()

def file_is_locked(path_to_file):
	'''returns True if file is locked (WINDOWS ONLY)'''
	if os.name != 'nt': # just in case
		return
	
	if not HAS_PYWIN32:
		return
	
	secur_att = pywintypes.SECURITY_ATTRIBUTES()
	secur_att.Initialize()
	
	try:
		# try make a handle for READING the file
		hfile = win32file.CreateFile(
			path_to_file,					# path to file
			win32con.GENERIC_READ,			# open for reading
			0,								# do not share with other proc
			secur_att,
			win32con.OPEN_EXISTING,			# existing file only
			win32con.FILE_ATTRIBUTE_NORMAL,	# normal file
			0								# no attr. template
		)
	except pywintypes.error, e:
		return True
	else: # in case all went ok, close file handle (go to hell WinAPI)
		hfile.Close()
		return False

def _get_fade_color(treeview, selected, focused):
	'''get a gdk color that is between foreground and background in 0.3
	0.7 respectively colors of the cell for the given treeview'''
	style = treeview.style
	if selected:
		if focused: # is the window focused?
			state = gtk.STATE_SELECTED
		else: # is it not? NOTE: many gtk themes change bg on this
			state = gtk.STATE_ACTIVE
	else:
		state = gtk.STATE_NORMAL
	bg = style.base[state]
	fg = style.text[state]

	p = 0.3 # background
	q = 0.7 # foreground # p + q should do 1.0
	return gtk.gdk.Color(int(bg.red*p + fg.red*q),
			      int(bg.green*p + fg.green*q),
			      int(bg.blue*p + fg.blue*q))

def get_scaled_pixbuf(pixbuf, type):
	'''returns scaled pixbuf, keeping ratio etc
	type is either "chat" or "roster"'''
	
	# resize to a width / height for the avatar not to have distortion
	# (keep aspect ratio)
	ratio = float(pixbuf.get_width()) / float(pixbuf.get_height())
	if ratio > 1:
		w = gajim.config.get(type + '_avatar_width')
		h = int(w / ratio)
	else:
		h = gajim.config.get(type + '_avatar_height')
		w = int(h * ratio)
	scaled_buf = pixbuf.scale_simple(w, h, gtk.gdk.INTERP_HYPER)
	return scaled_buf

def get_avatar_pixbuf_from_cache(jid):
	'''checks if jid has cached avatar and if that avatar is valid image
	(can be shown)
	return None if there is no image in vcard
	return 'ask' if vcard is too old or if we don't have the vcard'''
	if jid not in os.listdir(gajim.VCARDPATH):
		return 'ask'

	vcard_dict = gajim.connections.values()[0].get_cached_vcard(jid)
	if not vcard_dict: # This can happen if cached vcard is too old
		return 'ask'
	if not vcard_dict.has_key('PHOTO'):
		return None
	pixbuf = vcard.get_avatar_pixbuf_encoded_mime(vcard_dict['PHOTO'])[0]
	return pixbuf
