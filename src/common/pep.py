# -*- coding:utf-8 -*-
## src/common/pep.py
##
## Copyright (C) 2007 Piotr Gaczkowski <doomhammerng AT gmail.com>
## Copyright (C) 2007-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jean-Marie Traissard <jim AT lapin.org>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##                    Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from common import gajim, xmpp

MOODS = {
	'afraid':			_('Afraid'),			'amazed':		_('Amazed'),
	'angry':				_('Angry'),				'annoyed':		_('Annoyed'),
	'anxious':			_('Anxious'),			'aroused':		_('Aroused'),
	'ashamed':			_('Ashamed'),			'bored':			_('Bored'),
	'brave':				_('Brave'),				'calm':			_('Calm'),
	'cold':				_('Cold'),				'confused':		_('Confused'),
	'contented':		_('Contented'),		'cranky':		_('Cranky'),
	'curious':			_('Curious'),			'depressed':	_('Depressed'),
	'disappointed':	_('Disappointed'),	'disgusted':	_('Disgusted'),
	'distracted':		_('Distracted'),		'embarrassed':	_('Embarrassed'),
	'excited':			_('Excited'),			'flirtatious':	_('Flirtatious'),
	'frustrated':		_('Frustrated'),		'grumpy':		_('Grumpy'),
	'guilty':			_('Guilty'),			'happy':			_('Happy'),
	'hot':				_('Hot'),				'humbled':		_('Humbled'),
	'humiliated':		_('Humiliated'),		'hungry':		_('Hungry'),
	'hurt':				_('Hurt'),				'impressed':	_('Impressed'),
	'in_awe':			_('In Awe'),			'in_love':		_('In Love'),
	'indignant':		_('Indignant'),		'interested':	_('Interested'),
	'intoxicated':		_('Intoxicated'),		'invincible':	_('Invincible'),
	'jealous':			_('Jealous'),			'lonely':		_('Lonely'),
	'mean':				_('Mean'),				'moody':			_('Moody'),
	'nervous':			_('Nervous'),			'neutral':		_('Neutral'),
	'offended':			_('Offended'),			'playful':		_('Playful'),
	'proud':				_('Proud'),				'relieved':		_('Relieved'),
	'remorseful':		_('Remorseful'),		'restless':		_('Restless'),
	'sad':				_('Sad'),				'sarcastic':	_('Sarcastic'),
	'serious':			_('Serious'),			'shocked':		_('Shocked'),
	'shy':				_('Shy'),				'sick':			_('Sick'),
	'sleepy':			_('Sleepy'),			'stressed':		_('Stressed'),
	'surprised':		_('Surprised'),		'thirsty':		_('Thirsty'),
	'thoughtful':		_('Thoughtful'),		'worried':		_('Worried')}

# These moods are only available in the Gajim namespace
GAJIM_MOODS = ['thoughtful']

ACTIVITIES = {
	'doing_chores': {'category':			_('Doing Chores'),
		'buying_groceries':					_('Buying Groceries'),
		'cleaning':								_('Cleaning'),
		'cooking':								_('Cooking'),
		'doing_maintenance':					_('Doing Maintenance'),
		'doing_the_dishes':					_('Doing the Dishes'),
		'doing_the_laundry':					_('Doing the Laundry'),
		'gardening':							_('Gardening'),
		'running_an_errand':					_('Running an Errand'),
		'walking_the_dog':					_('Walking the Dog')},
	'drinking': {'category':				_('Drinking'),
		'having_a_beer':						_('Having a Beer'),
		'having_coffee':						_('Having Coffee'),
		'having_tea':							_('Having Tea')},
	'eating': {'category':					_('Eating'),
		'having_a_snack':						_('Having a Snack'),
		'having_breakfast':					_('Having Breakfast'),
		'having_dinner':						_('Having Dinner'),
		'having_lunch':						_('Having Lunch')},
	'exercising': {'category':				_('Exercising'),
		'cycling':								_('Cycling'),
		'hiking':								_('Hiking'),
		'jogging':								_('Jogging'),
		'playing_sports':						_('Playing Sports'),
		'running':								_('Running'),
		'skiing':								_('Skiing'),
		'swimming':								_('Swimming'),
		'working_out':							_('Working out')},
	'grooming': {'category':				_('Grooming'),
		'at_the_spa':							_('At the Spa'),
		'brushing_teeth':						_('Brushing Teeth'),
		'getting_a_haircut':					_('Getting a Haircut'),
		'shaving':								_('Shaving'),
		'taking_a_bath':						_('Taking a Bath'),
		'taking_a_shower':					_('Taking a Shower')},
	'having_appointment': {'category':	_('Having an Appointment')},
	'inactive': {'category':				_('Inactive'),
		'day_off':								_('Day Off'),
		'hanging_out':							_('Hanging out'),
		'on_vacation':							_('On Vacation'),
		'scheduled_holiday':					_('Scheduled Holiday'),
		'sleeping':								_('Sleeping')},
	'relaxing': {'category':				_('Relaxing'),
		'gaming':								_('Gaming'),
		'going_out':							_('Going out'),
		'partying':								_('Partying'),
		'reading':								_('Reading'),
		'rehearsing':							_('Rehearsing'),
		'shopping':								_('Shopping'),
		'socializing':							_('Socializing'),
		'sunbathing':							_('Sunbathing'),
		'watching_tv':							_('Watching TV'),
		'watching_a_movie':					_('Watching a Movie')},
	'talking': {'category':					_('Talking'),
		'in_real_life':						_('In Real Life'),
		'on_the_phone':						_('On the Phone'),
		'on_video_phone':						_('On Video Phone')},
	'traveling': {'category':				_('Traveling'),
		'commuting':							_('Commuting'),
		'cycling':								_('Cycling'),
		'driving':								_('Driving'),
		'in_a_car':								_('In a Car'),
		'on_a_bus':								_('On a Bus'),
		'on_a_plane':							_('On a Plane'),
		'on_a_train':							_('On a Train'),
		'on_a_trip':							_('On a Trip'),
		'walking':								_('Walking')},
	'working': {'category':					_('Working'),
		'coding':								_('Coding'),
		'in_a_meeting':						_('In a Meeting'),
		'studying':								_('Studying'),
		'writing':								_('Writing')}}

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
			if 'mood' in acc.mood:
				del acc.mood['mood']
			if 'text' in acc.mood:
				del acc.mood['text']
			if mood is not None:
				acc.mood['mood'] = mood
			if text is not None:
				acc.mood['text'] = text
		elif retract:
			if 'mood' in acc.mood:
				del acc.mood['mood']
			if 'text' in acc.mood:
				del acc.mood['text']

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	for contact in gajim.contacts.get_contacts(name, user):
		if has_child:
			if 'mood' in contact.mood:
				del contact.mood['mood']
			if 'text' in contact.mood:
				del contact.mood['text']
			if mood is not None:
				contact.mood['mood'] = mood
			if text is not None:
				contact.mood['text'] = text
		elif retract:
			if 'mood' in contact.mood:
				del contact.mood['mood']
			if 'text' in contact.mood:
				del contact.mood['text']

	if jid == gajim.get_jid_from_account(name):
		gajim.interface.roster.draw_account(name)
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
			if 'artist' in acc.tune:
				del acc.tune['artist']
			if 'title' in acc.tune:
				del acc.tune['title']
			if 'source' in acc.tune:
				del acc.tune['source']
			if 'track' in acc.tune:
				del acc.tune['track']
			if 'length' in acc.tune:
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
			if 'artist' in acc.tune:
				del acc.tune['artist']
			if 'title' in acc.tune:
				del acc.tune['title']
			if 'source' in acc.tune:
				del acc.tune['source']
			if 'track' in acc.tune:
				del acc.tune['track']
			if 'length' in acc.tune:
				del acc.tune['length']

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	for contact in gajim.contacts.get_contacts(name, user):
		if has_child:
			if 'artist' in contact.tune:
				del contact.tune['artist']
			if 'title' in contact.tune:
				del contact.tune['title']
			if 'source' in contact.tune:
				del contact.tune['source']
			if 'track' in contact.tune:
				del contact.tune['track']
			if 'length' in contact.tune:
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
			if 'artist' in contact.tune:
				del contact.tune['artist']
			if 'title' in contact.tune:
				del contact.tune['title']
			if 'source' in contact.tune:
				del contact.tune['source']
			if 'track' in contact.tune:
				del contact.tune['track']
			if 'length' in contact.tune:
				del contact.tune['length']

	if jid == gajim.get_jid_from_account(name):
		gajim.interface.roster.draw_account(name)
	gajim.interface.roster.draw_tune(user, name)
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
			if 'activity' in acc.activity:
				del acc.activity['activity']
			if 'subactivity' in acc.activity:
				del acc.activity['subactivity']
			if 'text' in acc.activity:
				del acc.activity['text']
			if activity is not None:
				acc.activity['activity'] = activity
			if subactivity is not None:
				acc.activity['subactivity'] = subactivity
			if text is not None:
				acc.activity['text'] = text
		elif retract:
			if 'activity' in acc.activity:
				del acc.activity['activity']
			if 'subactivity' in acc.activity:
				del acc.activity['subactivity']
			if 'text' in acc.activity:
				del acc.activity['text']

	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)
	for contact in gajim.contacts.get_contacts(name, user):
		if has_child:
			if 'activity' in contact.activity:
				del contact.activity['activity']
			if 'subactivity' in contact.activity:
				del contact.activity['subactivity']
			if 'text' in contact.activity:
				del contact.activity['text']
			if activity is not None:
				contact.activity['activity'] = activity
			if subactivity is not None:
				contact.activity['subactivity'] = subactivity
			if text is not None:
				contact.activity['text'] = text
		elif retract:
			if 'activity' in contact.activity:
				del contact.activity['activity']
			if 'subactivity' in contact.activity:
				del contact.activity['subactivity']
			if 'text' in contact.activity:
				del contact.activity['text']

	if jid == gajim.get_jid_from_account(name):
		gajim.interface.roster.draw_account(name)
	gajim.interface.roster.draw_activity(user, name)
	ctrl = gajim.interface.msg_win_mgr.get_control(user, name)
	if ctrl:
		ctrl.update_activity()

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
	if not gajim.connections[account].pep_supported:
		return
	item = xmpp.Node('mood', {'xmlns': xmpp.NS_MOOD})
	if mood != '':
		if mood in GAJIM_MOODS:
			ns = 'http://gajim.org/moods'
		else:
			ns = None
		item.addChild(mood, namespace = ns)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	gajim.connections[account].send_pb_publish('', xmpp.NS_MOOD, item, '0')

def user_send_activity(account, activity, subactivity = '', message = ''):
	if not gajim.connections[account].pep_supported:
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
	if not gajim.connections[account].pep_supported:
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

def delete_pep(jid, name):
	(user, resource) = gajim.get_room_and_nick_from_fjid(jid)

	if jid == gajim.get_jid_from_account(name):
		acc = gajim.connections[name]
		del acc.activity
		acc.activity = {}
		del acc.tune
		acc.tune = {}
		del acc.mood
		acc.mood = {}

	for contact in gajim.contacts.get_contacts(name, user):
		del contact.activity
		contact.activity = {}
		del contact.tune
		contact.tune = {}
		del contact.mood
		contact.mood = {}

	if jid == gajim.get_jid_from_account(name):
		gajim.interface.roster.draw_account(name)

	gajim.interface.roster.draw_activity(user, name)
	gajim.interface.roster.draw_tune(user, name)
	gajim.interface.roster.draw_mood(user, name)
	ctrl = gajim.interface.msg_win_mgr.get_control(user, name)
	if ctrl:
		ctrl.update_activity()
		ctrl.update_tune()
		ctrl.update_mood()

# vim: se ts=3:
