#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Dedicated to Yann

import os
import sys

stats = False
update = False

def visit(arg, dirname, names):
	if dirname.find('.svn') != -1:
		return
	if dirname.endswith('LC_MESSAGES'):
		if 'gajim.po' in names:
			path_to_po = os.path.join(dirname, 'gajim.po')
			pos = path_to_po.find('po/') + 3 #3 = len('po/')
			name = path_to_po[pos:pos+2]
			if update:
				os.system('msgmerge -q -U ../po/'+name+'/LC_MESSAGES/gajim.po ../gajim.pot')
			if stats:
				print name, 'has now:'
				os.system('msgfmt --statistics ' + path_to_po)

def show_help():
	print sys.argv[0], '[help] [stats] [update]'
	sys.exit(0)

def update_pot():
	os.system('intltool-extract --type=gettext/glade ../src/gtkgui.glade')
	os.system('xgettext -k_ -kN_ -o gajim.pot ../src/*.py ../src/common/*.py ../src/gtkgui.glade.h')

if __name__ == '__main__':
	if os.path.basename(os.getcwd()) != 'scripts':
		print 'run me with cwd: scripts'
		sys.exit()

	path_to_dir = '../po'

	if len(sys.argv) == 2:
		if sys.argv[1].startswith('h'):
			show_help()

		param = sys.argv[1]
		if param == 'stats': # stats only
			stats = True
			os.path.walk(path_to_dir, visit, None)
		elif param == 'update': # update and no stats
			update_pot()
			update = True
			os.path.walk(path_to_dir, visit, None) # update each po & no stats
			print 'Done'

	elif len(sys.argv) ==1: # update & stats
		update_pot()
		update = True
		stats = True
		os.path.walk(path_to_dir, visit, None)
		print 'Done'

	else:
		show_help()

