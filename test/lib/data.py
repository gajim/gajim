# -*- coding: utf-8 -*-
account1 = u'acc1'
account2 = u'Cool"chârßéµö'

contacts = {}
contacts[account1] = {
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

# vim: se ts=3:
