# -*- coding: utf-8 -*-
account1 = u'acc1'
account2 = u'Cool"chârßéµö'
account3 = u'dingdong.org'

contacts = {}
contacts[account1] = {
	u'myjid@'+account1: {
			  'ask': None, 'groups': [], 'name': None, 'resources': {},
			  'subscription': u'both'},
	u'default1@gajim.org': {
			  'ask': None, 'groups': [], 'name': None, 'resources': {},
			  'subscription': u'both'},
	u'default2@gajim.org': {
			  'ask': None, 'groups': [u'GroupA',], 'name': None, 'resources': {},
			  'subscription': u'both'},
	u'Cool"chârßéµö@gajim.org': {
			  'ask': None, 'groups': [u'<Cool"chârßéµö', u'GroupB'],
			  'name': None, 'resources': {}, 'subscription': u'both'},
	u'samejid@gajim.org': {
			  'ask': None, 'groups': [u'GroupA',], 'name': None, 'resources': {},
			  'subscription': u'both'}
}
contacts[account2] = {
	u'myjid@'+account2: {
			  'ask': None, 'groups': [], 'name': None, 'resources': {},
			  'subscription': u'both'},
	u'default3@gajim.org': {
			  'ask': None, 'groups': [u'GroupC',], 'name': None, 'resources': {},
			  'subscription': u'both'},
	u'asksubfrom@gajim.org': {
			  'ask': u'subscribe', 'groups': [u'GroupA',], 'name': None,
			  'resources': {}, 'subscription': u'from'},
	u'subto@gajim.org': {
			  'ask': None, 'groups': [u'GroupB'], 'name': None, 'resources': {},
			  'subscription': u'to'},
	u'samejid@gajim.org': {
			  'ask': None, 'groups': [u'GroupA', u'GroupB'], 'name': None,
			  'resources': {}, 'subscription': u'both'}
}
contacts[account3] = {
	#u'guypsych0\\40h.com@msn.dingdong.org': {
	#		  'ask': None, 'groups': [], 'name': None, 'resources': {},
	#		  'subscription': u'both'},
	u'guypsych0%h.com@msn.delx.cjb.net': {
			  'ask': u'subscribe', 'groups': [], 'name': None,
			  'resources': {}, 'subscription': u'from'},
	#u'guypsych0%h.com@msn.jabber.wiretrip.org': {
	#		  'ask': None, 'groups': [], 'name': None, 'resources': {},
	#		  'subscription': u'to'},
	#u'guypsycho\\40g.com@gtalk.dingdong.org': {
	#		  'ask': None, 'groups': [], 'name': None,
	#		  'resources': {}, 'subscription': u'both'}
}

# We have contacts that are not in roster but only specified in the metadata
metacontact_data = [
	[{'account': account3,
	  'jid': u'guypsych0\\40h.com@msn.dingdong.org',
	  'order': 0},
	 {'account': account3,
	  'jid': u'guypsych0%h.com@msn.delx.cjb.net',
	  'order': 0},
	 {'account': account3,
	  'jid': u'guypsych0%h.com@msn.jabber.wiretrip.org',
	  'order': 0},
	 {'account': account3,
	  'jid': u'guypsycho\\40g.com@gtalk.dingdong.org',
	  'order': 0}],

	[{'account': account1,
	  'jid': u'samejid@gajim.org',
	  'order': 0},
	 {'account': account2,
	  'jid': u'samejid@gajim.org',
	  'order': 0}]
	]

# vim: se ts=3:
