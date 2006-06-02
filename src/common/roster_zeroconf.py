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

	def setItem(self, jid, name = '', groups = ''):
		print 'setItem %s in Roster' % jid
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
		self._data[jid]['txt'] = txt
		txt_dict = self.zeroconf.txt_array_to_dict(txt)
		if txt_dict.has_key('status'):
			status = txt_dict['status']
		else:
			status = ''
		if status == 'avail': status = 'online'
		self._data[jid]['status'] = status
		self._data[jid]['show'] = status
		print self._data[jid]

	def delItem(self, jid):
		print 'delItem %s in Roster' % jid
		if self._data.has_key(jid):
			del self._data[jid]
		
	def __getitem__(self,jid):
		print '__getitem__ in Roster'
		return self._data[jid]
	
	def getItems(self):
		print 'getItems in Roster'	
		# Return list of all [bare] JIDs that the roster is currently tracks.
		return self._data.keys()
	
	def keys(self):
		print 'keys in Roster'
		return self._data.keys()
	
	def getRaw(self):
		print 'getRaw in Roster'
		return self._data

	def getResources(self, jid):
		print 'getResources(%s) in Roster' % jid
		return {}
	
	def getStatus(self, jid):
		print 'getStatus %s in Roster' % jid
		txt = self._data[jid]['txt']
		txt_dict = self.zeroconf.txt_array_to_dict(txt)
		if txt_dict.has_key('status'):
			status = txt_dict['status']
		else:
			status = ''
		
		if status == 'avail' or status == '':
			return 'online'
		else:
			return status

	def getShow(self, jid):
		print 'getShow in Roster'
		return getStatus(jid)


	def getPriority(jid):
		return 5

	def getSubscription(self,jid):
		print 'getSubscription in Roster'
		return 'both'

	def Subscribe(self,jid):
		pass
		
	def Unsubscribe(self,jid):
		pass
	
	def Authorize(self,jid):
		pass

	def Unauthorize(self,jid):
		pass
