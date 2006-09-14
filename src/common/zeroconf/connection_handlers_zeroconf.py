##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
##  - Stefan Bethge <stefan@lanpartei.de> 
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import os
import time
import base64
import sha
import socket
import sys

from calendar import timegm

#import socks5
import common.xmpp

from common import GnuPG
from common import helpers
from common import gajim

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible']
# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'
AGENT_REMOVED = 'agent_removed'
HAS_IDLE = True
try:
	import common.idle as idle # when we launch gajim from sources
except:
	try:
		import idle # when Gajim is installed
	except:
		gajim.log.debug(_('Unable to load idle module'))
		HAS_IDLE = False

class ConnectionVcard:
	def __init__(self):
		self.vcard_sha = None
		self.vcard_shas = {} # sha of contacts
		self.room_jids = [] # list of gc jids so that vcard are saved in a folder
		
	def add_sha(self, p, send_caps = True):
		'''
		c = p.setTag('x', namespace = common.xmpp.NS_VCARD_UPDATE)
		if self.vcard_sha is not None:
			c.setTagData('photo', self.vcard_sha)
		if send_caps:
			return self.add_caps(p)
		return p
		'''
		pass
	
	def add_caps(self, p):
		'''
		# advertise our capabilities in presence stanza (jep-0115)
		c = p.setTag('c', namespace = common.xmpp.NS_CAPS)
		c.setAttr('node', 'http://gajim.org/caps')
		c.setAttr('ext', 'ftrans')
		c.setAttr('ver', gajim.version)
		return p
		'''
		pass
	
	def node_to_dict(self, node):
		dict = {}
		'''
		for info in node.getChildren():
			name = info.getName()
			if name in ('ADR', 'TEL', 'EMAIL'): # we can have several
				if not dict.has_key(name):
					dict[name] = []
				entry = {}
				for c in info.getChildren():
					 entry[c.getName()] = c.getData()
				dict[name].append(entry)
			elif info.getChildren() == []:
				dict[name] = info.getData()
			else:
				dict[name] = {}
				for c in info.getChildren():
					 dict[name][c.getName()] = c.getData()
		'''
		return dict

	def save_vcard_to_hd(self, full_jid, card):
		jid, nick = gajim.get_room_and_nick_from_fjid(full_jid)
		puny_jid = helpers.sanitize_filename(jid)
		path = os.path.join(gajim.VCARD_PATH, puny_jid)
		if jid in self.room_jids or os.path.isdir(path):
			# remove room_jid file if needed
			if os.path.isfile(path):
				os.remove(path)
			# create folder if needed
			if not os.path.isdir(path):
				os.mkdir(path, 0700)
			puny_nick = helpers.sanitize_filename(nick)
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
		else:
			path_to_file = path
		fil = open(path_to_file, 'w')
		fil.write(str(card))
		fil.close()
	
	def get_cached_vcard(self, fjid, is_fake_jid = False):
		'''return the vcard as a dict
		return {} if vcard was too old
		return None if we don't have cached vcard'''
		jid, nick = gajim.get_room_and_nick_from_fjid(fjid)
		puny_jid = helpers.sanitize_filename(jid)
		if is_fake_jid:
			puny_nick = helpers.sanitize_filename(nick)
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
		else:
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid)
		if not os.path.isfile(path_to_file):
			return None
		# We have the vcard cached
		f = open(path_to_file)
		c = f.read()
		f.close()
		card = common.xmpp.Node(node = c)
		vcard = self.node_to_dict(card)
		if vcard.has_key('PHOTO'):
			if not isinstance(vcard['PHOTO'], dict):
				del vcard['PHOTO']
			elif vcard['PHOTO'].has_key('SHA'):
				cached_sha = vcard['PHOTO']['SHA']
				if self.vcard_shas.has_key(jid) and self.vcard_shas[jid] != \
					cached_sha:
					# user change his vcard so don't use the cached one
					return {}
		vcard['jid'] = jid
		vcard['resource'] = gajim.get_resource_from_jid(fjid)
		return vcard

	def request_vcard(self, jid = None, is_fake_jid = False):
		'''request the VCARD. If is_fake_jid is True, it means we request a vcard
		to a fake jid, like in private messages in groupchat'''
		if not self.connection:
			return
		'''
		iq = common.xmpp.Iq(typ = 'get')
		if jid:
			iq.setTo(jid)
		iq.setTag(common.xmpp.NS_VCARD + ' vCard')

		id = self.connection.getAnID()
		iq.setID(id)
		self.awaiting_answers[id] = (VCARD_ARRIVED, jid)
		if is_fake_jid:
			room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
			if not room_jid in self.room_jids:
				self.room_jids.append(room_jid)
		self.connection.send(iq)
			#('VCARD', {entry1: data, entry2: {entry21: data, ...}, ...})
		'''
		pass
		
	def send_vcard(self, vcard):
		if not self.connection:
			return
		'''
		iq = common.xmpp.Iq(typ = 'set')
		iq2 = iq.setTag(common.xmpp.NS_VCARD + ' vCard')
		for i in vcard:
			if i == 'jid':
				continue
			if isinstance(vcard[i], dict):
				iq3 = iq2.addChild(i)
				for j in vcard[i]:
					iq3.addChild(j).setData(vcard[i][j])
			elif type(vcard[i]) == type([]):
				for j in vcard[i]:
					iq3 = iq2.addChild(i)
					for k in j:
						iq3.addChild(k).setData(j[k])
			else:
				iq2.addChild(i).setData(vcard[i])

		id = self.connection.getAnID()
		iq.setID(id)
		self.connection.send(iq)

		# Add the sha of the avatar
		if vcard.has_key('PHOTO') and isinstance(vcard['PHOTO'], dict) and \
		vcard['PHOTO'].has_key('BINVAL'):
			photo = vcard['PHOTO']['BINVAL']
			photo_decoded = base64.decodestring(photo)
			our_jid = gajim.get_jid_from_account(self.name)
			gajim.interface.save_avatar_files(our_jid, photo_decoded)
			avatar_sha = sha.sha(photo_decoded).hexdigest()
			iq2.getTag('PHOTO').setTagData('SHA', avatar_sha)

		self.awaiting_answers[id] = (VCARD_PUBLISHED, iq2)
		'''
		pass
		
class ConnectionHandlersZeroconf(ConnectionVcard):
	def __init__(self):
		ConnectionVcard.__init__(self)
		# List of IDs we are waiting answers for {id: (type_of_request, data), }
		self.awaiting_answers = {}
		# List of IDs that will produce a timeout is answer doesn't arrive
		# {time_of_the_timeout: (id, message to send to gui), }
		self.awaiting_timeouts = {}
		# keep the jids we auto added (transports contacts) to not send the
		# SUBSCRIBED event to gui
		self.automatically_added = []
		try:
			idle.init()
		except:
			HAS_IDLE = False
	'''
	def build_http_auth_answer(self, iq_obj, answer):
		if answer == 'yes':
			iq = iq_obj.buildReply('result')
		elif answer == 'no':
			iq = iq_obj.buildReply('error')
			iq.setError('not-authorized', 401)
		self.connection.send(iq)
	'''
	
	def parse_data_form(self, node):
		dic = {}
		tag = node.getTag('title')
		if tag:
			dic['title'] = tag.getData()
		tag = node.getTag('instructions')
		if tag:
			dic['instructions'] = tag.getData()
		i = 0
		for child in node.getChildren():
			if child.getName() != 'field':
				continue
			var = child.getAttr('var')
			ctype = child.getAttr('type')
			label = child.getAttr('label')
			if not var and ctype != 'fixed': # We must have var if type != fixed
				continue
			dic[i] = {}
			if var:
				dic[i]['var'] = var
			if ctype:
				dic[i]['type'] = ctype
			if label:
				dic[i]['label'] = label
			tags = child.getTags('value')
			if len(tags):
				dic[i]['values'] = []
				for tag in tags:
					data = tag.getData()
					if ctype == 'boolean':
						if data in ('yes', 'true', 'assent', '1'):
							data = True
						else:
							data = False
					dic[i]['values'].append(data)
			tag = child.getTag('desc')
			if tag:
				dic[i]['desc'] = tag.getData()
			option_tags = child.getTags('option')
			if len(option_tags):
				dic[i]['options'] = {}
				j = 0
				for option_tag in option_tags:
					dic[i]['options'][j] = {}
					label = option_tag.getAttr('label')
					tags = option_tag.getTags('value')
					dic[i]['options'][j]['values'] = []
					for tag in tags:
						dic[i]['options'][j]['values'].append(tag.getData())
					if not label:
						label = dic[i]['options'][j]['values'][0]
					dic[i]['options'][j]['label'] = label
					j += 1
				if not dic[i].has_key('values'):
					dic[i]['values'] = [dic[i]['options'][0]['values'][0]]
			i += 1
		return dic
		
	def remove_transfers_for_contact(self, contact):
		''' stop all active transfer for contact '''
		'''for file_props in self.files_props.values():
			if self.is_transfer_stoped(file_props):
				continue
			receiver_jid = unicode(file_props['receiver']).split('/')[0]
			if contact.jid == receiver_jid:
				file_props['error'] = -5
				self.remove_transfer(file_props)
				self.dispatch('FILE_REQUEST_ERROR', (contact.jid, file_props))
			sender_jid = unicode(file_props['sender']).split('/')[0]
			if contact.jid == sender_jid:
				file_props['error'] = -3
				self.remove_transfer(file_props)
		'''
		pass
	
	def remove_all_transfers(self):
		''' stops and removes all active connections from the socks5 pool '''
		'''
		for file_props in self.files_props.values():
			self.remove_transfer(file_props, remove_from_list = False)
		del(self.files_props)
		self.files_props = {}
		'''
		pass
	
	def remove_transfer(self, file_props, remove_from_list = True):
		'''
		if file_props is None:
			return
		self.disconnect_transfer(file_props)
		sid = file_props['sid']
		gajim.socks5queue.remove_file_props(self.name, sid)

		if remove_from_list:
			if self.files_props.has_key('sid'):
				del(self.files_props['sid'])
		'''
		pass
			
