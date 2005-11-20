## logger.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
##      Copyright (C) 2003-2005 Gajim Team
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

import os
import time

import common.gajim
from common import i18n
_ = i18n._
import helpers


class Logger:
	def __init__(self):
		pass

	def write(self, kind, msg, jid, show = None, tim = None):
		jid = jid.lower()
		if not tim:
			tim = time.time()
		else:
			tim = time.mktime(tim)

		if not msg:
			msg = ''

		msg = helpers.to_one_line(msg)
		if len(jid.split('/')) > 1:
			ji, nick = jid.split('/', 1)
		else:
			ji = jid
			nick = ''
		files = []
		if kind == 'status': # we save time:jid:show:msg
			if not show:
				show = 'online'
			if common.gajim.config.get('log_notif_in_user_file'):
				path_to_file = os.path.join(common.gajim.LOGPATH, ji)
				if os.path.isdir(path_to_file):
					jid = 'gcstatus'
					msg = show + ':' + msg
					show = nick
					files.append(ji + '/' + ji)
					if os.path.isfile(jid):
						files.append(jid)
				else:
					files.append(ji)
			if common.gajim.config.get('log_notif_in_sep_file'):
				files.append('notify.log')
		elif kind == 'incoming': # we save time:recv:message
			path_to_file = os.path.join(common.gajim.LOGPATH, ji)
			if os.path.isdir(path_to_file):
				files.append(jid)
			else:
				files.append(ji)
			jid = 'recv'
			show = msg
			msg = ''
		elif kind == 'outgoing': # we save time:sent:message
			path_to_file = os.path.join(common.gajim.LOGPATH, ji)
			if os.path.isdir(path_to_file):
				files.append(jid)
			else:
				files.append(ji)
			jid = 'sent'
			show = msg
			msg = ''
		elif kind == 'gc': # we save time:gc:nick:message
			# create the folder if needed
			ji_fn = os.path.join(common.gajim.LOGPATH, ji)
			if os.path.isfile(ji_fn):
				os.remove(ji_fn)
			if not os.path.isdir(ji_fn):
				os.mkdir(ji_fn, 0700)
			files.append(ji + '/' + ji)
			jid = 'gc'
			show = nick
		# convert to utf8 before writing to file if needed
		if isinstance(tim, unicode):
			tim = tim.encode('utf-8')
		if isinstance(jid, unicode):
			jid = jid.encode('utf-8')
		if isinstance(show, unicode):
			show = show.encode('utf-8')
		if msg and isinstance(msg, unicode):
			msg = msg.encode('utf-8')
		for f in files:
			path_to_file = os.path.join(common.gajim.LOGPATH, f)
			if os.path.isdir(path_to_file):
				return
			# this does it rw-r-r by default but is in a dir with 700 so it's ok
			fil = open(path_to_file, 'a')
			fil.write('%s:%s:%s' % (tim, jid, show))
			if msg:
				fil.write(':' + msg)
			fil.write('\n')
			fil.close()

	def __get_path_to_file(self, fjid):
		jid = fjid.split('/')[0]
		path_to_file = os.path.join(common.gajim.LOGPATH, jid)
		if os.path.isdir(path_to_file):
			if fjid == jid: # we want to read the gc history
				path_to_file = os.path.join(common.gajim.LOGPATH, jid + '/' + jid)
			else: #we want to read pm history
				path_to_file = os.path.join(common.gajim.LOGPATH, fjid)
		return path_to_file

	def get_no_of_lines(self, fjid):
		'''returns total number of lines in a log file
		returns 0 if log file does not exist'''
		fjid = fjid.lower()
		path_to_file = self.__get_path_to_file(fjid)
		if not os.path.isfile(path_to_file):
			return 0
		f = open(path_to_file, 'r')
		return len(f.readlines()) # number of lines

	# FIXME: remove me when refactor in TC is done
	def read_from_line_to_line(self, fjid, begin_from_line, end_line):
		'''returns the text in the lines (list),
		returns empty list if log file does not exist'''
		fjid = fjid.lower()
		path_to_file = self.__get_path_to_file(fjid)
		if not os.path.isfile(path_to_file):
			return []

		lines = []
		
		fil = open(path_to_file, 'r')
		#fil.readlines(begin_from_line) # skip the previous lines
		no_of_lines = begin_from_line # number of lines between being and end
		while (no_of_lines < begin_from_line and fil.readline()):
			no_of_lines += 1
		
		print begin_from_line, end_line
		while no_of_lines < end_line:
			line = fil.readline().decode('utf-8')
			print `line`, '@', no_of_lines
			if line:
				line = helpers.from_one_line(line)
				lineSplited = line.split(':')
				if len(lineSplited) > 2:
					lines.append(lineSplited)
				no_of_lines += 1
			else: # emplty line (we are at the end of file)
				break
		return lines

	def get_last_conversation_lines(self, jid, how_many_lines, timeout):
		'''accepts how many lines to restore and when to time them out
		(mark them as too old),	returns the lines (list), empty list if log file
		does not exist'''
		fjid = fjid.lower()
		path_to_file = self.__get_path_to_file(fjid)
		if not os.path.isfile(path_to_file):
			return []
		

	def get_conversation_for_date(self, fjid, year, month, day):
		'''returns the text in the lines (list),
		returns empty list if log file does not exist'''
		fjid = fjid.lower()
		path_to_file = self.__get_path_to_file(fjid)
		if not os.path.isfile(path_to_file):
			return []
		
		lines = []
		f = open(path_to_file, 'r')
		done = False
		found_first_line_that_matches = False
		while not done:
			line = f.readline().decode('utf-8')
			if line:
				line = helpers.from_one_line(line)
				splitted_line = line.split(':')
				if len(splitted_line) > 2:
					if splitted_line:
						# line[0] is date, line[1] is type of message
						# line[2:] is message
						date = splitted_line[0]
						# eg. 2005
						line_year = int(time.strftime('%Y', time.localtime(float(date))))
						# (01 - 12)
						line_month = int(time.strftime('%m', time.localtime(float(date))))
						# (01 - 31)
						line_day = int(time.strftime('%d', time.localtime(float(date))))
						
						# now check if that line is one of the lines we want
						# (if it is in the date we want)
						if line_year == year and line_month == month and line_day == day:
							if found_first_line_that_matches is False:
								found_first_line_that_matches = True
							lines.append(splitted_line)
						else:
							if found_first_line_that_matches:
								done = True
			
			else:
				done = True

		return lines
