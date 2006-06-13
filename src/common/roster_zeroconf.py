from common import zeroconf

class Roster:
	def __init__(self, zeroconf):
		self._data = {}
		self.zeroconf = zeroconf 	  	 # our zeroconf instance

	def update_roster(self):
		for (jid, dom, interf, proto, host, addr, port, txt) in self.zeroconf.get_contacts().values():
			self.setItem(jid)

	def getRoster(self):
		print 'roster_zeroconf.py: getRoster'
		self.update_roster()
		return self

	def getDiffs(self):
		'''	update the roster with new data and return dict with
		jid -> new status pairs to do notifications and stuff '''

		diffs = {}
		old_data = self._data.copy()
		self.update_roster()
		for key in old_data.keys():
			if self._data.has_key(key):
				if old_data[key] != self._data[key]:
					diffs[key] = self._data[key]['status']
		print 'roster_zeroconf.py: diffs:',
		print diffs
		return diffs
		
	def setItem(self, jid, name = '', groups = ''):
		#print 'roster_zeroconf.py: setItem %s' % jid
		(service_jid, domain, interface, protocol, host, address, port, txt)  \
			= self.zeroconf.get_contact(jid)

		self._data[jid]={}
		self._data[jid]['name']=jid[:jid.find('@')]
		self._data[jid]['ask'] = 'no'  #?
		self._data[jid]['subscription'] = 'both'
		self._data[jid]['groups'] = []
		self._data[jid]['resources'] = {}
		self._data[jid]['address'] = address
		self._data[jid]['host'] = host
		self._data[jid]['port'] = port
		txt_dict = self.zeroconf.txt_array_to_dict(txt)
		if txt_dict.has_key('status'):
			status = txt_dict['status']
		else:
			status = ''
		if status == 'avail': status = 'online'
		self._data[jid]['txt_dict'] = txt_dict
		self._data[jid]['status'] = status
		self._data[jid]['show'] = status

		# print self._data[jid]

	def delItem(self, jid):
		print 'roster_zeroconf.py: delItem %s' % jid
		if self._data.has_key(jid):
			del self._data[jid]
		
	def getItem(self, jid):
		print 'roster_zeroconf.py: getItem: %s' % jid
		if self._data.has_key(jid):
			return self._data[jid]

	def __getitem__(self,jid):
		print 'roster_zeroconf.py: __getitem__'
		return self._data[jid]
	
	def getItems(self):
		print 'roster_zeroconf.py: getItems'
		# Return list of all [bare] JIDs that the roster currently tracks.
		return self._data.keys()
	
	def keys(self):
		print 'roster_zeroconf.py: keys'
		return self._data.keys()
	
	def getRaw(self):
		print 'roster_zeroconf.py: getRaw'
		return self._data

	def getResources(self, jid):
		print 'roster_zeroconf.py: getResources(%s)' % jid
		return {}
		
	def getGroups(self, jid):
		return self._data[jid]['groups']
	
	def getStatus(self, jid):
		return self._data[jid]['status']

	def getShow(self, jid):
		print 'roster_zeroconf.py: getShow'
		return getStatus(jid)

	def getPriority(jid):
		return 5

	def getSubscription(self,jid):
		print 'roster_zeroconf.py: getSubscription'
		return 'both'

	def Subscribe(self,jid):
		pass
		
	def Unsubscribe(self,jid):
		pass
	
	def Authorize(self,jid):
		pass

	def Unauthorize(self,jid):
		pass
