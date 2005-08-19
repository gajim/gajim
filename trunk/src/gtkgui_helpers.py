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
import os
from common import i18n
i18n.init()
_ = i18n._
from common import gajim

def get_default_font():
	''' Get the desktop setting for application font
	first check for GNOME, then XFCE and last KDE
	it returns None on failure or else a string 'Font Size' '''
	
	try:
		import gconf
		# in try because daemon may not be there
		client = gconf.client_get_default()
	except:
		pass
	else:
		return client.get_string('/desktop/gnome/interface/font_name')

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
					return line[start:line.find('"', start)]
		except:
			#we talk about file
			print _('error: cannot open %s for reading') % xfce_config_file
	
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
					return font_string
		except:
			#we talk about file
			print _('error: cannot open %s for reading') % kde_config_file
	
	return None
	
def reduce_chars_newlines(text, max_chars = 0, max_lines = 0, 
	widget = None):
	''' Cut the chars after 'max_chars' on each line
	and show only the first 'max_lines'. If there is more text
	to be shown, display the whole text in tooltip on 'widget'
	If any of the params is not present(None or 0) the action
	on it is not performed
	'''
	# assure that we have only unicode text
	if type(text) == str:
		text = unicode(text, encoding='utf-8')
		
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
	# escapes < > & \ "
	# for pango markup not to break
	if string is None:
		return
	if gtk.pygtk_version >= (2, 8, 0) and gtk.gtk_version >= (2, 8, 0):
		escaped_str = gobject.markup_escape_text(string)
	else:
		escaped_str =xml.sax.saxutils.escape(string, {'\\': '&apos;',
			'"': '&quot;'})
	
	return escaped_str

def autodetect_browser_mailer():
	#recognize the environment for appropriate browser/mailer
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
