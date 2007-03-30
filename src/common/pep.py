from common import gajim, xmpp

def user_mood(items, name, jid):
	#FIXME: text deletion
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contacts = gajim.contacts.get_contact(name, user, resource=resource)
	for item in items.getTags('item'):
		child = item.getTag('mood')
		if child is not None:
			for ch in child.getChildren():
				if ch.getName() != 'text':
					for contact in contacts:
						contact.mood['mood'] = ch.getName()
				else:
					for contact in contacts:
						contact.mood['text'] = ch.getData()

def user_tune(items, name, jid):
	pass

def user_geoloc(items, name, jid):
	pass

def user_activity(items, name, jid):
	#FIXME: text deletion
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	contacts = gajim.contacts.get_contact(name, user, resource=resource)
	for item in items.getTags('item'):
		child = item.getTag('activity')
		if child is not None:
			for ch in child.getChildren():
				if ch.getName() != 'text':
					for contact in contacts:
						contact.activity['activity'] = ch.getName()
					for chi in ch.getChildren():
						for contact in contacts:
							contact.activity['subactivity'] = chi.getName()
				else:
					for contact in contacts:
						contact.activity['text'] = ch.getData()

def user_send_mood(account, mood, message = ''):
	item = xmpp.Node('mood', {'xmlns': xmpp.NS_MOOD})
	item.addChild(mood)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_MOOD, item, '0')
