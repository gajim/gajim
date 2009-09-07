# -*- coding:utf-8 -*-
## src/common/fuzzyclock.py
##
## Copyright (C) 2006 Christoph Neuroth <delmonico AT gmx.net>
## Copyright (C) 2006-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2009 Benjamin Richter <br AT waldteufel-online.net>
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

'''
Python class to show a "fuzzy clock".
Homepage of the original: http://home.gna.org/fuzzyclock/
Project Page of the original: http://gna.org/projects/fuzzyclock

The class is based on a port from PHP code by
Henrique Recidive <henrique at recidive.com> which was
in turn based on the Fuzzy Clock Applet of Frerich Raabe (KDE).
So most of the credit goes to this guys, thanks :-)
'''

import time

class FuzzyClock:
	HOUR_NAMES = [ _('twelve'), _('one'), _('two'), _('three'), _('four'),
		_('five'), _('six'), _('seven'), _('eight'), _('nine'), _('ten'),
		_('eleven') ]

	#Strings to use for the output. %(0)s will be replaced with the preceding hour
	#(e.g. "x PAST %(0)s"), %(1)s with the coming hour (e.g. "x TO %(0)s"). '''
	FUZZY_TIME = [ _("%(0)s o'clock"), _('five past %(0)s'), _('ten past %(0)s'),
		_('quarter past %(0)s'), _('twenty past %(0)s'), _('twenty five past %(0)s'),
		_('half past %(0)s'), _('twenty five to %(1)s'), _('twenty to %(1)s'),
		_('quarter to %(1)s'), _('ten to %(1)s'), _('five to %(1)s'), _("%(1)s o'clock") ]

	FUZZY_DAYTIME = [ _('Night'), _('Early morning'), _('Morning'), 
		_('Almost noon'), _('Noon'), _('Afternoon'), _('Evening'),
		_('Late evening'), _('Night') ]

	FUZZY_WEEK = [ _('Start of week'), _('Middle of week'), _('Middle of week'),
		_('Middle of week'), _('End of week'), _('Weekend!'), _('Weekend!') ]

	def fuzzy_time(self, fuzzyness, now):
		if fuzzyness == 1 or fuzzyness == 2:
			if fuzzyness == 1:
				sector = int(round(now.tm_min / 5.0))
			else:
				sector = int(round(now.tm_min / 15.0)) * 3

			return self.FUZZY_TIME[sector] % {
				'0': self.HOUR_NAMES[now.tm_hour % 12],
				'1': self.HOUR_NAMES[(now.tm_hour + 1) % 12]}

		elif fuzzyness == 3:
			return self.FUZZY_DAYTIME[int(round(now.tm_hour / 3.0))]

		else:
			return self.FUZZY_WEEK[now.tm_wday]

# vim: se ts=3:
