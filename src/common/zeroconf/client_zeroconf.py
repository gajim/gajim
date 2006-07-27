##      common/zeroconf/client_zeroconf.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
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


from common.zeroconf import roster_zeroconf

class ClientZeroconf:
	def __init__(self, zeroconf):
		self.roster = roster_zeroconf.Roster(zeroconf)
		
	def getRoster(self):
		return self.roster.getRoster()

	def send(self, str):
		pass
