from common import gajim, xmpp

MOODS = ['afraid', 'amazed', 'angry', 'annoyed', 'anxious', 'aroused',
	'ashamed', 'bored', 'brave', 'calm', 'cold', 'confused', 'contented',
	'cranky', 'curious', 'depressed', 'disappointed', 'disgusted',
	'distracted', 'embarrassed', 'excited', 'flirtatious', 'frustrated', 
	'grumpy', 'guilty', 'happy', 'hot', 'humbled', 'humiliated', 'hungry',
	'hurt', 'impressed', 'in_awe', 'in_love', 'indignant', 'interested',
	'intoxicated', 'invincible', 'jealous', 'lonely', 'mean', 'moody', 
	'nervous', 'neutral', 'offended', 'playful', 'proud', 'relieved',
	'remorseful', 'restless', 'sad', 'sarcastic', 'serious', 'shocked',
	'shy', 'sick', 'sleepy', 'stressed', 'surprised', 'thirsty', 'worried']

def user_mood(items, name, jid):
	has_child = False
	retract = False
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
	if items.getTag('retract') is not None:
		retract = True

	if jid == gajim.get_jid_from_account(name):
		acc = gajim.connections[name]
		if has_child:
			if acc.mood.has_key('mood'):
				del acc.mood['mood']
			if acc.mood.has_key('text'):
				del acc.mood['text']
			if mood is not None:
				acc.mood['mood'] = mood
			if text is not None:
				acc.mood['text'] = text
		elif retract:
			if acc.mood.has_key('mood'):
				del acc.mood['mood']
			if acc.mood.has_key('text'):
				del acc.mood['text']

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	for contact in gajim.contacts.get_contacts(name, user):
		if has_child:
			if contact.mood.has_key('mood'):
				del contact.mood['mood']
			if contact.mood.has_key('text'):
				del contact.mood['text']
			if mood is not None:
				contact.mood['mood'] = mood
			if text is not None:
				contact.mood['text'] = text
		elif retract:
			if contact.mood.has_key('mood'):
				del contact.mood['mood']
			if contact.mood.has_key('text'):
				del contact.mood['text']

	gajim.interface.roster.draw_mood(user, name)
	ctrl = gajim.interface.msg_win_mgr.get_control(user, name)
	if ctrl:
		ctrl.update_mood()

def user_tune(items, name, jid):
	has_child = False
	retract = False
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
	if items.getTag('retract') is not None:
		retract = True

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
			if artist is not None:
				acc.tune['artist'] = artist
			if title is not None:
				acc.tune['title'] = title
			if source is not None:
				acc.tune['source'] = source
			if track is not None:
				acc.tune['track'] = track
			if length is not None:
				acc.tune['length'] = length
		elif retract:
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

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	for contact in gajim.contacts.get_contacts(name, user):
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
			if artist is not None:
				contact.tune['artist'] = artist
			if title is not None:
				contact.tune['title'] = title
			if source is not None:
				contact.tune['source'] = source
			if track is not None:
				contact.tune['track'] = track
			if length is not None:
				contact.tune['length'] = length
		elif retract:
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

	ctrl = gajim.interface.msg_win_mgr.get_control(user, name)
	if ctrl:
		ctrl.update_tune()

def user_geoloc(items, name, jid):
	pass

def user_activity(items, name, jid):
	has_child = False
	retract = False
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
	if items.getTag('retract') is not None:
		retract = True

	if jid == gajim.get_jid_from_account(name):
		acc = gajim.connections[name]
		if has_child:
			if acc.activity.has_key('activity'):
				del acc.activity['activity']
			if acc.activity.has_key('subactivity'):
				del acc.activity['subactivity']
			if acc.activity.has_key('text'):
				del acc.activity['text']
			if activity is not None:
				acc.activity['activity'] = activity
			if subactivity is not None:
				acc.activity['subactivity'] = subactivity
			if text is not None:
				acc.activity['text'] = text
		elif retract:
			if acc.activity.has_key('activity'):
				del acc.activity['activity']
			if acc.activity.has_key('subactivity'):
				del acc.activity['subactivity']
			if acc.activity.has_key('text'):
				del acc.activity['text']

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	for contact in gajim.contacts.get_contacts(name, user):
		if has_child:
			if contact.activity.has_key('activity'):
				del contact.activity['activity']
			if contact.activity.has_key('subactivity'):
				del contact.activity['subactivity']
			if contact.activity.has_key('text'):
				del contact.activity['text']
			if activity is not None:
				contact.activity['activity'] = activity
			if subactivity is not None:
				contact.activity['subactivity'] = subactivity
			if text is not None:
				contact.activity['text'] = text
		elif retract:
			if contact.activity.has_key('activity'):
				del contact.activity['activity']
			if contact.activity.has_key('subactivity'):
				del contact.activity['subactivity']
			if contact.activity.has_key('text'):
				del contact.activity['text']

def user_nickname(items, name, jid):
	has_child = False
	retract = False
	nick = None

	for item in items.getTags('item'):
		child = item.getTag('nick')
		if child is not None:
			has_child = True
			nick = child.getData()
			break

	if items.getTag('retract') is not None:
		retract = True

	if jid == gajim.get_jid_from_account(name):
		if has_child:
			gajim.nicks[name] = nick
		if retract:
			gajim.nicks[name] = gajim.config.get_per('accounts',
				name, 'name')

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	if has_child:
		if nick is not None:
			for contact in gajim.contacts.get_contacts(name, user):
				contact.contact_name = nick
			gajim.interface.roster.draw_contact(user, name)

			ctrl = gajim.interface.msg_win_mgr.get_control(user,
				name)
			if ctrl:
				ctrl.update_ui()
				win = ctrl.parent_win
				win.redraw_tab(ctrl)
				win.show_title()
	elif retract:
		contact.contact_name = ''

def user_send_mood(account, mood, message = ''):
	if not gajim.config.get_per('accounts', account, 'publish_mood'):
		return
	item = xmpp.Node('mood', {'xmlns': xmpp.NS_MOOD})
	if mood != '':
		item.addChild(mood)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_MOOD, item, '0')

def user_send_activity(account, activity, subactivity = '', message = ''):
	if not gajim.config.get_per('accounts', account, 'publish_activity'):
		return
	item = xmpp.Node('activity', {'xmlns': xmpp.NS_ACTIVITY})
	if activity != '':
		i = item.addChild(activity)
	if subactivity != '':
		i.addChild(subactivity)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_ACTIVITY,
		item, '0')

def user_send_tune(account, artist = '', title = '', source = '', track = 0,
length = 0, items = None):
	if not (gajim.config.get_per('accounts', account, 'publish_tune') and \
	gajim.connections[account].pep_supported):
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

def user_send_nickname(account, nick):
	if not (gajim.config.get_per('accounts', account, 'publish_nick') and \
	gajim.connections[account].pep_supported):
		return
	item = xmpp.Node('nick', {'xmlns': xmpp.NS_NICK})
	item.addData(nick)

	gajim.connections[account].send_pb_publish('', xmpp.NS_NICK, item, '0')

def user_retract_mood(account):
	gajim.connections[account].send_pb_retract('', xmpp.NS_MOOD, '0')

def user_retract_activity(account):
	gajim.connections[account].send_pb_retract('', xmpp.NS_ACTIVITY, '0')

def user_retract_tune(account):
	gajim.connections[account].send_pb_retract('', xmpp.NS_TUNE, '0')

def user_retract_nickname(account):
	gajim.connections[account].send_pb_retract('', xmpp.NS_NICK, '0')
