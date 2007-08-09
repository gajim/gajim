from common import gajim, xmpp

def user_mood(items, name, jid):
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contact = gajim.contacts.get_contact(name, user, resource=resource)
	if not contact:
		return
	for item in items.getTags('item'):
		child = item.getTag('mood')
		if child is not None:
			if contact.mood.has_key('mood'):
				del contact.mood['mood']
			if contact.mood.has_key('text'):
				del contact.mood['text']
			for ch in child.getChildren():
				if ch.getName() != 'text':
					contact.mood['mood'] = ch.getName()
				else:
					contact.mood['text'] = ch.getData()

def user_tune(items, name, jid):
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contact = gajim.contacts.get_contact(name, user, resource=resource)
	if not contact:
		return
	for item in items.getTags('item'):
		child = item.getTag('tune')
		if child is not None:
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
			for ch in child.getChildren():
				if ch.getName() == 'artist':
					contact.tune['artist'] = ch.getData()
				elif ch.getName() == 'title':
					contact.tune['title'] = ch.getData()
				elif ch.getName() == 'source':
					contact.tune['source'] = ch.getData()
				elif ch.getName() == 'track':
					contact.tune['track'] = ch.getData()
				elif ch.getName() == 'length':
					contact.tune['length'] = ch.getData()

def user_geoloc(items, name, jid):
	pass

def user_activity(items, name, jid):
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contact = gajim.contacts.get_contact(name, user, resource=resource)
	if not contact:
		return
	for item in items.getTags('item'):
		child = item.getTag('activity')
		if child is not None:
			if contact.activity.has_key('activity'):
				del contact.activity['activity']
			if contact.activity.has_key('subactivity'):
				del contact.activity['subactivity']
			if contact.activity.has_key('text'):
				del contact.activity['text']
			for ch in child.getChildren():
				if ch.getName() != 'text':
					contact.activity['activity'] = ch.getName()
					for chi in ch.getChildren():
						contact.activity['subactivity'] = chi.getName()
				else:
					contact.activity['text'] = ch.getData()

def user_send_mood(account, mood, message = ''):
	print "Sending %s: %s" % (mood, message)
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
	if gajim.config.get('publish_tune') == False:
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
