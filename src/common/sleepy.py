##      common/sleepy.py
##
## Gajim Team:
##      - Yann Le Boulanger <asterix@lagaule.org>
##      - Vincent Hanquez <tab@snarc.org>
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

from common import gajim


STATE_UNKNOWN  = 'OS probably not supported'
STATE_XAWAY   = 'extanted away'
STATE_AWAY   = 'away'
STATE_AWAKE    = 'awake'

SUPPORTED = 1
try:
	import common.idle as idle # when we launch gajim from sources
except:
	try:
		import idle # when Gajim is installed
	except:
		gajim.log.debug('Unable to load idle module')
		SUPPORTED = 0

class Sleepy:

	def __init__(self, interval1 = 60, interval2 = 120):

		self.interval1 = interval1
		self.interval2 = interval2
		self.state         = STATE_AWAKE ## assume were awake to stake with
		try:
			idle.init()
		except:
			SUPPORTED = 0
			self.state = STATE_UNKNOWN

	def poll(self):
		if not SUPPORTED: return 0

		idleTime = idle.getIdleSec()
		if idleTime > self.interval2:
			self.state = STATE_XAWAY
		elif idleTime > self.interval1:
			self.state = STATE_AWAY
		else:
			self.state = STATE_AWAKE
		return 1

	def getState(self):
		return self.state

	def setState(self,val):
		self.state = val
