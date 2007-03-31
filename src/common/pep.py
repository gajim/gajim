from common import gajim, xmpp

def user_mood(items, name, jid):
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contacts = gajim.contacts.get_contact(name, user, resource=resource)
	for item in items.getTags('item'):
		child = item.getTag('mood')
		if child is not None:
			for contact in contacts:
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
	pass

def user_geoloc(items, name, jid):
	pass

def user_activity(items, name, jid):
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contacts = gajim.contacts.get_contact(name, user, resource=resource)
	for item in items.getTags('item'):
		child = item.getTag('activity')
		if child is not None:
			for contact in contacts:
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
	item = xmpp.Node('mood', {'xmlns': xmpp.NS_MOOD})
	item.addChild(mood)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_MOOD, item, '0')

def user_send_activity(account, activity, subactivity = '', message = ''):
	item = xmpp.Node('activity', {'xmlns': xmpp.NS_ACTIVITY})
	i = item.addChild(activity)
	if subactivity != '':
		i.addChild(subactivity)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_ACTIVITY, item, '0')
