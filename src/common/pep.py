from common import gajim

def user_mood(items, name, jid):
	contacts = gajim.contacts.get_contact(name, jid)
	for item in items.getTags('item'):
		child = item.getTag('mood')
		if child is not None:
			for ch in child.getChildren():
				if ch.getName() != 'text':
					for contact in contacts:
						contact.mood = ch.getName()
				else:
					for contact in contacts:
						contact.mood_text = ch.getData()

def user_tune(items, name, jid):
	pass

def user_geoloc(items, name, jid):
	pass

def user_activity(items, name, jid):
	contacts = gajim.contacts.get_contact(name, jid)
	for item in items.getTags('item'):
		child = item.getTag('activity')
		if child is not None:
			for ch in child.getChildren():
				if ch.getName() != 'text':
					for contact in contacts:
						contact.activity = ch.getName()
				else:
					for contact in contacts:
						contact.activity_text = ch.getData()
