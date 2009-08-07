# -*- coding:utf-8 -*-
## src/common/fuzzyclock.py
##
## Copyright (C) 2006 Christoph Neuroth <delmonico AT gmx.net>
## Copyright (C) 2006-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
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
Homepage: http://home.gna.org/fuzzyclock/
Project Page: http://gna.org/projects/fuzzyclock

The class has been ported from PHP code by
Henrique Recidive <henrique at recidive.com> which was
in turn based on the Fuzzy Clock Applet of Frerich Raabe (KDE).
So most of the credit goes to this guys, thanks :-)
'''

import time

class FuzzyClock:
	def __init__(self):
		self.__hour = 0
		self.__minute = 0
		self.__dayOfWeek = 0

		self.__hourNames = [ _('one'), _('two'), _('three'), _('four'), _('five'), _('six'),
			_('seven'), _('eight'), _('nine'), _('ten'), _('eleven'),
			_('twelve')]

		#Strings to use for the output. $0 will be replaced with the preceding hour (e.g. "x PAST $0"), $1 with the coming hour (e.g. "x TO $1). '''
		self.__normalFuzzy = [ _("$0 o'clock"), _('five past $0'),
			_('ten past $0'), _('quarter past $0'),
			_('twenty past $0'), _('twenty five past $0'),
			_('half past $0'), _('twenty five to $1'),
			_('twenty to $1'), _('quarter to $1'),
			_('ten to $1'), _('five to $1'), _("$1 o'clock") ]

		#A "singular-form". It is used when talking about hour 0
		self.__normalFuzzyOne = [ _("$0 o'clock"), _('five past $0'),
			_('ten past $0'), _('quarter past $0'),
			_('twenty past $0'), _('twenty five past $0'),
			_('half past $0'), _('twenty five to $1'),
			_('twenty to $1'), _('quarter to $1'),
			_('ten to $1'), _('five to $1'),
			_("$1 o'clock") ]


		self.__dayTime = [ _('Night'), _('Early morning'), _('Morning'), _('Almost noon'),
			_('Noon'), _('Afternoon'), _('Evening'), _('Late evening') ]

		self.__fuzzyWeek = [ _('Start of week'), _('Middle of week'), _('End of week'),
			_('Weekend!') ]

		self.setCurrent()

	def setHour(self,hour):
		self.__hour = int(hour)

	def setMinute(self,minute):
		self.__minute=int(minute)

	def setDayOfWeek(self,day):
		self.__dayOfWeek=int(day)

	def setTime(self,time):
		timeArray = time.split(":")
		self.setHour(timeArray[0])
		self.setMinute(timeArray[1])

	def setCurrent(self):
		hour=time.strftime("%H")
		minute=time.strftime("%M")
		day=time.strftime("%w")

		self.setTime(hour+":"+minute)
		self.setDayOfWeek(day)

	def getFuzzyTime(self, fuzzyness = 1):
		sector = 0
		realHour = 0

		if fuzzyness == 1 or fuzzyness == 2:
			if fuzzyness == 1:
				if self.__minute >2:
					sector = (self.__minute - 3) / 5 +1
			else:
				if self.__minute > 6:
					sector = ((self.__minute - 7) / 15 + 1) * 3

			newTimeStr = self.__normalFuzzy[sector]
			#$0 or $1?
			deltaHour = int(newTimeStr[newTimeStr.find("$")+1])

			if (self.__hour + deltaHour) % 12 > 0:
				realHour = (self.__hour + deltaHour) % 12 - 1
			else:
				realHour = 12 - ((self.__hour + deltaHour) % 12 + 1)

			if realHour == 0:
				newTimeStr = self.__normalFuzzyOne[sector]

			newTimeStr = newTimeStr.replace("$"+str(deltaHour),
				self.__hourNames[realHour])


		elif fuzzyness == 3:
			newTimeStr = self.__dayTime[self.__hour / 3]

		else:
			dayOfWeek = self.__dayOfWeek
			if dayOfWeek == 1:
				newTimeStr = self.__fuzzyWeek[0]
			elif dayOfWeek >= 2 and dayOfWeek <= 4:
				newTimeStr = self.__fuzzyWeek[1]
			elif dayOfWeek == 5:
				newTimeStr = self.__fuzzyWeek[2]
			else:
				newTimeStr = self.__fuzzyWeek[3]

		return newTimeStr

# vim: se ts=3:
