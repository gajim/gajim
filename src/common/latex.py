# -*- coding:utf-8 -*-
## src/common/latex.py
##
## Copyright (C) 2005 Norman Rasmussen <norman AT rasmussen.co.za>
## Copyright (C) 2005-2006 Alex Mauer <hawke AT hawkesnest.net>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
##                    Stephan Erb <steve-e AT h3c.de>
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

import os
import random
from tempfile import gettempdir
from subprocess import Popen, PIPE

import logging
log = logging.getLogger('gajim.c.latex')

import gajim
from exceptions import LatexError

# some latex commands are really bad
blacklist = ['\\def', '\\let', '\\futurelet',
	'\\newcommand', '\\renewcomment', '\\else', '\\fi', '\\write',
	'\\input', '\\include', '\\chardef', '\\catcode', '\\makeatletter',
	'\\noexpand', '\\toksdef', '\\every', '\\errhelp', '\\errorstopmode',
	'\\scrollmode', '\\nonstopmode', '\\batchmode', '\\read', '\\csname',
	'\\newhelp', '\\relax', '\\afterground', '\\afterassignment',
	'\\expandafter', '\\noexpand', '\\special', '\\command', '\\loop',
	'\\repeat', '\\toks', '\\output', '\\line', '\\mathcode', '\\name',
	'\\item', '\\section', '\\mbox', '\\DeclareRobustCommand', '\\[',
	'\\]']
# True if the string matches the blacklist
def check_blacklist(str_):
	for word in blacklist:
		if word in str_:
			return True
	return False

def get_tmpfile_name():
	random.seed()
	int_ = random.randint(0, 100)
	return os.path.join(gettempdir(), 'gajimtex_' + int_.__str__())

def write_latex(filename, str_):
	texstr = '\\documentclass[12pt]{article}\\usepackage[dvips]{graphicx}'
	texstr += '\\usepackage{amsmath}\\usepackage{amssymb}'
	texstr += '\\pagestyle{empty}'
	texstr += '\\begin{document}\\begin{large}\\begin{gather*}'
	texstr += str_
	texstr += '\\end{gather*}\\end{large}\\end{document}'

	file_ = open(filename, "w+")
	file_.write(texstr)
	file_.flush()
	file_.close()

# a wrapper for Popen so that no window gets opened on Windows
# (i think this is the reason we're using Popen rather than just system())
# stdout goes to a pipe so that it can be read
def popen_nt_friendly(command):
	if os.name == 'nt':
		# CREATE_NO_WINDOW
		return Popen(command, creationflags=0x08000000, cwd=gettempdir(), stdout=PIPE)
	else:
		return Popen(command, cwd=gettempdir(), stdout=PIPE)

def check_for_latex_support():
	'''check is latex is available and if it can create a picture.'''

	try:
		filename = latex_to_image("test")
		if filename:
			# we have a file, conversion succeeded
			os.remove(filename)
			return True
		return False
	except LatexError:
		return False

def latex_to_image(str_):
	result = None
	exitcode = 0

	# filter latex code with bad commands
	if check_blacklist(str_):
		# we triggered the blacklist, immediately return None
		return None

	tmpfile = get_tmpfile_name()

	# build latex string
	write_latex(os.path.join(tmpfile + '.tex'), str_)

	# convert TeX to dvi
	try:
		p = popen_nt_friendly(['latex', '--interaction=nonstopmode',
			tmpfile + '.tex'])
		out = p.communicate()[0]
		log.info(out)
		exitcode = p.wait()
	except Exception, e:
		exitcode = _('Error executing "%(command)s": %(error)s') % {
			'command': 'latex --interaction=nonstopmode %s.tex' % tmpfile,
			'error': str(e)}

	if exitcode == 0:
		# convert dvi to png
		latex_png_dpi = gajim.config.get('latex_png_dpi')
		try:
			p = popen_nt_friendly(['dvipng', '-bg', 'rgb 1.0 1.0 1.0', '-T',
				'tight', '-D', latex_png_dpi, tmpfile + '.dvi', '-o',
				tmpfile + '.png'])
			out = p.communicate()[0]
			log.info(out)
			exitcode = p.wait()
		except Exception, e:
			exitcode = _('Error executing "%(command)s": %(error)s') % {
				'command': 'dvipng -bg rgb 1.0 1.0 1.0 -T tight -D %s %s.dvi -o '
				'%s.png' % (latex_png_dpi, tmpfile, tmpfile), 'error': str(e)}

	# remove temp files created by us and TeX
	extensions = ['.tex', '.log', '.aux', '.dvi']
	for ext in extensions:
		try:
			os.remove(tmpfile + ext)
		except Exception:
			pass

	if isinstance(exitcode, (unicode, str)):
		raise LatexError(exitcode)

	if exitcode == 0:
		result = tmpfile + '.png'

	return result

# vim: se ts=3:
