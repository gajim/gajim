from common import gajim, xmpp

def user_mood(items, name, jid):
	has_child = False
	mood = None
	text = None
	for item in items.getTags('item'):
		child = item.getTag('mood')
		if child is not None:
			has_child = True
			for ch in child.getChildren():
				if ch.getName() != 'text':
					mood = ch.getName()
				else:
					text = ch.getData()
	if jid == gajim.get_jid_from_account(name):
		acc = gajim.connections[name]
		if has_child:
			if acc.mood.has_key('mood'):
				del acc.mood['mood']
			if acc.mood.has_key('text'):
				del acc.mood['text']
			if mood != None:
				acc.mood['mood'] = mood
			if text != None:
				acc.mood['text'] = text

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contact = gajim.contacts.get_contact(name, user, resource=resource)
	if not contact:
		return
	if has_child:
		if contact.mood.has_key('mood'):
			del contact.mood['mood']
		if contact.mood.has_key('text'):
			del contact.mood['text']
		if mood != None:
			contact.mood['mood'] = mood
		if text != None:
			contact.mood['text'] = text

def user_tune(items, name, jid):
	has_child = False
	artist = None
	title = None
	source = None
	track = None
	length = None

	for item in items.getTags('item'):
		child = item.getTag('tune')
		if child is not None:
			has_child = True
			for ch in child.getChildren():
				if ch.getName() == 'artist':
					artist = ch.getData()
				elif ch.getName() == 'title':
					title = ch.getData()
				elif ch.getName() == 'source':
					source = ch.getData()
				elif ch.getName() == 'track':
					track = ch.getData()
				elif ch.getName() == 'length':
					length = ch.getData()

	if jid == gajim.get_jid_from_account(name):
		acc = gajim.connections[name]
		if has_child:
			if acc.tune.has_key('artist'):
				del acc.tune['artist']
			if acc.tune.has_key('title'):
				del acc.tune['title']
			if acc.tune.has_key('source'):
				del acc.tune['source']
			if acc.tune.has_key('track'):
				del acc.tune['track']
			if acc.tune.has_key('length'):
				del acc.tune['length']
			if artist != None:
				acc.tune['artist'] = artist
			if title != None:
				acc.tune['title'] = title
			if source != None:
				acc.tune['source'] = source
			if track != None:
				acc.tune['track'] = track
			if length != None:
				acc.tune['length'] = length

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contact = gajim.contacts.get_contact(name, user, resource=resource)
	if not contact:
		return
	if has_child:
		if contact.tune.has_key('artist'):
			del contact.tune['artist']
		if contact.tune.has_key('title'):
			del contact.tune['title']
		if contact.tune.has_key('source'):
			del contact.tune['source']
		if contact.tune.has_key('track'):
			del contact.tune['track']
		if contact.tune.has_key('length'):
			del contact.tune['length']
		if artist != None:
			contact.tune['artist'] = artist
		if title != None:
			contact.tune['title'] = title
		if source != None:
			contact.tune['source'] = source
		if track != None:
			contact.tune['track'] = track
		if length != None:
			contact.tune['length'] = length

def user_geoloc(items, name, jid):
	pass

def user_activity(items, name, jid):
	has_child = False
	activity = None
	subactivity = None
	text = None

	for item in items.getTags('item'):
		child = item.getTag('activity')
		if child is not None:
			has_child = True
			for ch in child.getChildren():
				if ch.getName() != 'text':
					activity = ch.getName()
					for chi in ch.getChildren():
						subactivity = chi.getName()
				else:
					text = ch.getData()

	if jid == gajim.get_jid_from_account(name):
		acc = gajim.connections[name]
		if has_child:
			if acc.activity.has_key('activity'):
				del acc.activity['activity']
			if acc.activity.has_key('subactivity'):
				del acc.activity['subactivity']
			if acc.activity.has_key('text'):
				del acc.activity['text']
			if activity != None:
				acc.activity['activity'] = activity
			if subactivity != None:
				acc.activity['subactivity'] = subactivity
			if text != None:
				acc.activity['text'] = text

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contact = gajim.contacts.get_contact(name, user, resource=resource)
	if not contact:
		return
	if has_child:
		if contact.activity.has_key('activity'):
			del contact.activity['activity']
		if contact.activity.has_key('subactivity'):
			del contact.activity['subactivity']
		if contact.activity.has_key('text'):
			del contact.activity['text']
		if activity != None:
			contact.activity['activity'] = activity
		if subactivity != None:
			contact.activity['subactivity'] = subactivity
		if text != None:
			contact.activity['text'] = text

def user_send_mood(account, mood, message = ''):
	if gajim.config.get('publish_mood') == False:
		return
	item = xmpp.Node('mood', {'xmlns': xmpp.NS_MOOD})
	if mood != '':
		item.addChild(mood)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_MOOD, item, '0')

def user_send_activity(account, activity, subactivity = '', message = ''):
	if gajim.config.get('publish_activity') == False:
		return
	item = xmpp.Node('activity', {'xmlns': xmpp.NS_ACTIVITY})
	if activity != '':
		i = item.addChild(activity)
	if subactivity != '':
		i.addChild(subactivity)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_ACTIVITY, item, '0')

def user_send_tune(account, artist = '', title = '', source = '', track = 0,length = 0, items = None):
	if (gajim.config.get('publish_tune') == False) or \
	(gajim.connections[account].pep_supported == False):
		return
	item = xmpp.Node('tune', {'xmlns': xmpp.NS_TUNE})
	if artist != '':
		i = item.addChild('artist')
		i.addData(artist)
	if title != '':
		i = item.addChild('title')
		i.addData(title)
	if source != '':
		i = item.addChild('source')
		i.addData(source)
	if track != 0:
		i = item.addChild('track')
		i.addData(track)
	if length != 0:
		i = item.addChild('length')
		i.addData(length)
	if items is not None:
		item.addChild(payload=items)

	gajim.connections[account].send_pb_publish('', xmpp.NS_TUNE, item, '0')
