## common/sleepy.py
##
## Contributors for this file:
##      - Yann Le Boulanger <asterix@lagaule.org>
##      - Nikos Kouremenos <kourem@gmail.com>
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
STATE_XA   = 'extanted away'
STATE_AWAY   = 'away'
STATE_AWAKE    = 'awake'

SUPPORTED = True
try:
	import common.idle as idle # when we launch gajim from sources
except:
	try:
		import idle # when Gajim is installed
	except:
		gajim.log.debug('Unable to load idle module')
		SUPPORTED = False

class Sleepy:

	def __init__(self, away_interval = 60, xa_interval = 120):
		self.away_interval = away_interval
		self.xa_interval = xa_interval
		self.state = STATE_AWAKE # assume we are awake
		try:
			idle.init()
		except:
			SUPPORTED = False
			self.state = STATE_UNKNOWN

	def poll(self):
		'''checks to see if we should change state'''
		if not SUPPORTED:
			return False

		idleTime = idle.getIdleSec()
		
		# xa is stronger than away so check for xa first
		if idleTime > self.xa_interval:
			self.state = STATE_XA
		elif idleTime > self.away_interval:
			self.state = STATE_AWAY
		else:
			self.state = STATE_AWAKE
		return True

	def getState(self):
		return self.state

	def setState(self,val):
		self.state = val
