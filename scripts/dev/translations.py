#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Initially written by Nikos Kouremenos
# Dedicated to Yann Le Boulanger
# Usage: './translations.py [help] [stats] [update]'

import os
import sys

stats = False
update = False
check = False
path_to_dir = '../../po'

def visit(files):
	for file in files:
		if file.endswith('.po'):
			path_to_po = os.path.join(path_to_dir, file)
			if update: # update an existing po file)
				os.system('msgmerge -q -U %s %s' % (path_to_po, os.path.join(path_to_dir, 'gajim.pot')))
			if stats:
				print file[:-3], 'has now:'
				os.system('msgfmt --statistics ' + path_to_po)
			if check:
				os.system('msgfmt -c ' + path_to_po)

def show_help():
	print sys.argv[0], '[help] [stats] [update] [check]'
	sys.exit(0)

def update_pot():
	# create header for glade strings
	os.system("""
	for i in `ls ../../data/glade/*.glade`;do 
		intltool-extract --type=gettext/glade $i
	done
	""")
	# update the pot
	os.system('make -C ../../po/ all gajim.pot')
	print 'gajim.pot was updated successfully'

if __name__ == '__main__':
	if os.path.basename(os.getcwd()) != 'dev':
		print 'run me with cwd: scripts/dev'
		sys.exit()

	path_to_dir = '../../po'

	files = os.listdir(path_to_dir)
	if len(sys.argv) == 2:
		if sys.argv[1].startswith('h'):
			show_help()

		param = sys.argv[1]
		if param == 'stats': # stats only
			stats = True
			visit(files)
		elif param == 'update': # update only
			update_pot()
			update = True
			visit(files)
			print 'Done'
		elif param == 'check':
			check = True
			visit(files)

	elif len(sys.argv) == 1: # update & stats & no check
		update_pot()
		update = True
		stats = True
		visit(files)
		print 'Done'

	else:
		show_help()

