
from common.zeroconf import roster_zeroconf

class ClientZeroconf:
	def __init__(self, zeroconf):
		self.roster = roster_zeroconf.Roster(zeroconf)
		
	def getRoster(self):
		return self.roster.getRoster()

	def send(self, str):
		pass
