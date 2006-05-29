from common import zeroconf

class Roster:
	def __init__(self, zeroconf):
		self._data = {}
		self.zeroconf = zeroconf 	  	 # our zeroconf instance

	def getRoster(self):
		print 'getRoster in Roster'
		self._data = self.zeroconf.get_contacts()
		return self

	def getItem(self, jid):
		print 'getItem(%s) in Roster' % jid
		if self._data.has_key(jid):
			return self._data[jid]

	def __getitem__(self,item):
		print '__getitem__ in Roster'
		return self._data[item]
			
	def getRaw(self):
		return self._data

	def getResources(self, jid):
		print 'getResources(%s) in Roster' % jid
#		return self
		
	'''	
	getRaw()
	delItem(jid)
	getItem(jid)
	getResources(jid)
	getStatus(jid)
	getPriority(jid)
	getShow(jid)
	'''
