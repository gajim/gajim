##	common/connection.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##  - Dimitur Kirov <dkirov@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
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

import sys
import os
import time
import sre
import traceback
import threading
import select


from calendar import timegm

import common.xmpp

from common import helpers
from common import gajim
from common import GnuPG
from xmpp import socks5
USE_GPG = GnuPG.USE_GPG

from common import i18n
_ = i18n._


STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible']

distro_info = {
	'Arch Linux': '/etc/arch-release',
	'Aurox Linux': '/etc/aurox-release',
	'Conectiva Linux': '/etc/conectiva-release',
	'Debian GNU/Linux': '/etc/debian_release',
	'Debian GNU/Linux': '/etc/debian_version',
	'Fedora Linux': '/etc/fedora-release',
	'Gentoo Linux': '/etc/gentoo-release',
	'Linux from Scratch': '/etc/lfs-release',
	'Mandrake Linux': '/etc/mandrake-release',
	'Slackware Linux': '/etc/slackware-release',
	'Slackware Linux': '/etc/slackware-version',
	'Solaris/Sparc': '/etc/release',
	'Source Mage': '/etc/sourcemage_version',
	'SUSE Linux': '/etc/SuSE-release',
	'Sun JDS': '/etc/sun-release',
	'PLD Linux': '/etc/pld-release',
	'Yellow Dog Linux': '/etc/yellowdog-release',
	# many distros use the /etc/redhat-release for compatibility
	# so Redhat is the last
	'Redhat Linux': '/etc/redhat-release'
}

def get_os_info():
	if os.name == 'nt':
		win_version = {
			(1, 4, 0): '95',
			(1, 4, 10): '98',
			(1, 4, 90): 'ME',
			(2, 4, 0): 'NT',
			(2, 5, 0): '2000',
			(2, 5, 1): 'XP'
		}[	os.sys.getwindowsversion()[3],
			os.sys.getwindowsversion()[0],
			os.sys.getwindowsversion()[1] ]
		return 'Windows' + ' ' + win_version
	elif os.name == 'posix':
		executable = 'lsb_release'
		params = ' --id --codename --release --short'
		for path in os.environ['PATH'].split(':'):
			full_path_to_executable = os.path.join(path, executable)
			if os.path.exists(full_path_to_executable):
				command = executable + params
				child_stdin, child_stdout = os.popen2(command)
				output = child_stdout.readline().strip()
				child_stdout.close()
				child_stdin.close()
				# some distros put n/a in places so remove them
				pattern = sre.compile(r' n/a', sre.IGNORECASE)
				output = sre.sub(pattern, '', output)
				return output
		# lsb_release executable not available, so parse files
		for distro_name in distro_info:
			path_to_file = distro_info[distro_name]
			if os.path.exists(path_to_file):
				fd = open(path_to_file)
				text = fd.readline().strip() #get only first line
				fd.close()
				if path_to_file.endswith('version'):
					# sourcemage_version has all the info we need
					if not os.path.basename(path_to_file).startswith('sourcemage'):
						text = distro_name + ' ' + text
				elif path_to_file.endswith('aurox-release'):
					# file doesn't have version
					text = distro_name
				elif path_to_file.endswith('lfs-release'): # file just has version
					text = distro_name + ' ' + text
				return text
	return 'N/A'

class Connection:
	"""Connection class"""
	def __init__(self, name):
		# dict of function to be called for each event
		self.handlers = {'ROSTER': [], 'WARNING': [], 'ERROR': [], 
			'INFORMATION': [], 'STATUS': [], 'NOTIFY': [], 'MSG': [],
			'MSGERROR': [], 'MSGSENT': [] , 'SUBSCRIBED': [], 'UNSUBSCRIBED': [],
			'SUBSCRIBE': [], 'AGENT_INFO': [], 'REGISTER_AGENT_INFO': [],
			'AGENT_INFO_ITEMS': [], 'AGENT_INFO_INFO': [], 'QUIT': [],
			'ACC_OK': [], 'MYVCARD': [], 'OS_INFO': [], 'VCARD': [], 'GC_MSG': [],
			'GC_SUBJECT': [], 'GC_CONFIG': [], 'BAD_PASSPHRASE': [],
			'ROSTER_INFO': [], 'ERROR_ANSWER': [], 'BOOKMARKS': [], 'CON_TYPE': [],
			'FILE_REQUEST': [], 'FILE_RCV_COMPLETED': []
			}
		self.name = name
		self.connected = 0 # offline
		self.connection = None # xmpppy instance
		self.gpg = None
		self.status = ''
		self.myVCardID = []
		self.new_account_info = None
		self.bookmarks = []
		self.on_purpose = False
		self.last_incoming = time.time()
		self.keep_alive_sent = False
		self.to_be_sent = []
		self.last_sent = []
		self.password = gajim.config.get_per('accounts', name, 'password')
		self.privacy_rules_supported = False
		self.receiver = socks5.SocksQueue(self.complete_file_transfer)
		if USE_GPG:
			self.gpg = GnuPG.GnuPG()
			gajim.config.set('usegpg', True)
		else:
			gajim.config.set('usegpg', False)
	# END __init__

	def dispatch(self, event, data):
		'''always passes account name as first param'''
		if not event in self.handlers:
			print event, 'is not in:', self.handlers
			return
		for handler in self.handlers[event]:
			handler(self.name, data)

	# this is in features.py but it is blocking
	def _discover(self, ns, jid, node = None): 
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get', to = jid, queryNS = ns)
		if node:
			iq.setQuerynode(node)
		self.to_be_sent.append(iq)

	def discoverItems(self, jid, node = None):
		'''According to JEP-0030: jid is mandatory, 
											name, node, action is optional.'''
		self._discover(common.xmpp.NS_DISCO_ITEMS, jid, node)
	
	def discoverInfo(self, jid, node = None):
		'''According to JEP-0030:
			For identity: category, name is mandatory, type is optional.
			For feature: var is mandatory'''
		self._discover(common.xmpp.NS_DISCO_INFO, jid, node)

	def _vCardCB(self, con, vc):
		"""Called when we receive a vCard
		Parse the vCard and send it to plugins"""
		frm_iq = vc.getFrom()
		resource = ''
		if frm_iq:
			frm = frm_iq.getStripped()
			resource = frm_iq.getResource()
		else:
			name = gajim.config.get_per('accounts', self.name, 'name')
			hostname = gajim.config.get_per('accounts', self.name, 'hostname')
			frm = name + '@' + hostname
		vcard = {'jid': frm, 'resource': resource}
		if not vc.getTag('vCard'):
			return
		if vc.getTag('vCard').getNamespace() == common.xmpp.NS_VCARD:
			card = vc.getChildren()[0]
			for info in card.getChildren():
				name = info.getName()
				if name in ['ADR', 'TEL', 'EMAIL']: # we can have several
					if not vcard.has_key(name):
						vcard[name] = []
					entry = {}
					for c in info.getChildren():
						 entry[c.getName()] = c.getData()
					vcard[name].append(entry)
				elif info.getChildren() == []:
					vcard[name] = info.getData()
				else:
					vcard[name] = {}
					for c in info.getChildren():
						 vcard[name][c.getName()] = c.getData()
			if vc.getID() in self.myVCardID:
				self.myVCardID.remove(vc.getID())
				self.dispatch('MYVCARD', vcard)
			else:
				self.dispatch('VCARD', vcard)


	def _messageCB(self, con, msg):
		"""Called when we receive a message"""
		msgtxt = msg.getBody()
		mtype = msg.getType()
		subject = msg.getSubject() # if not there, it's None
		tim = msg.getTimestamp()
		tim = time.strptime(tim, '%Y%m%dT%H:%M:%S')
		tim = time.localtime(timegm(tim))
		encrypted = False
		chatstate = None
		xtags = msg.getTags('x')
		encTag = None
		decmsg = ''
		for xtag in xtags:
			if xtag.getNamespace() == common.xmpp.NS_ENCRYPTED:
				encTag = xtag
				break

		# chatstates - look for chatstate tags in a message
		children = msg.getChildren()
		for child in children:
			if child.getNamespace() == 'http://jabber.org/protocol/chatstates':
				chatstate = child.getName()
				break
			
		if encTag and USE_GPG:
			#decrypt
			encmsg = encTag.getData()
			
			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				decmsg = self.gpg.decrypt(encmsg, keyID)
		if decmsg:
			msgtxt = decmsg
			encrypted = True
		if mtype == 'error':
			self.dispatch('MSGERROR', (str(msg.getFrom()),
				msg.getErrorCode(), msg.getError(), msgtxt, tim))
		elif mtype == 'groupchat':
			if subject:
				self.dispatch('GC_SUBJECT', (str(msg.getFrom()), subject))
			else:
				if not msg.getTag('body'): #no <body>
					return
				self.dispatch('GC_MSG', (str(msg.getFrom()), msgtxt, tim))
				gajim.logger.write('gc', msgtxt, str(msg.getFrom()), tim = tim)
		elif mtype == 'normal': # it's single message
			log_msgtxt = msgtxt
			if subject:
				log_msgtxt = _('Subject: %s\n%s') % (subject, msgtxt)
			gajim.logger.write('incoming', log_msgtxt, str(msg.getFrom()),
				tim = tim)
			self.dispatch('MSG', (str(msg.getFrom()), msgtxt, tim, encrypted,
				mtype, subject, None))
		else: # it's type 'chat'
			if not msg.getTag('body') and chatstate is None: #no <body>
				return
			log_msgtxt = msgtxt
			if subject:
				log_msgtxt = _('Subject: %s\n%s') % (subject, msgtxt)
			if msg.getTag('body'):
				gajim.logger.write('incoming', log_msgtxt, str(msg.getFrom()),
					tim = tim)
			self.dispatch('MSG', (str(msg.getFrom()), msgtxt, tim, encrypted,
				mtype, subject, chatstate))
	# END messageCB

	def _presenceCB(self, con, prs):
		"""Called when we receive a presence"""
		who = str(prs.getFrom())
		prio = prs.getPriority()
		if not prio:
			prio = 0
		ptype = prs.getType()
		if ptype == 'available': ptype = None
		gajim.log.debug('PresenceCB: %s' % ptype)
		xtags = prs.getTags('x')
		sigTag = None
		keyID = ''
		status = prs.getStatus()
		for xtag in xtags:
			if xtag.getNamespace() == common.xmpp.NS_SIGNED:
				sigTag = xtag
				break
		if sigTag and USE_GPG:
			#verify
			sigmsg = sigTag.getData()
			keyID = self.gpg.verify(status, sigmsg)
		show = prs.getShow()
		if not show in STATUS_LIST:
			show = '' # We ignore unknown show
		if not ptype and not show:
			show = 'online'
		elif ptype == 'unavailable':
			show = 'offline'
		elif ptype == 'subscribe':
			gajim.log.debug('subscribe request from %s' % who)
			if gajim.config.get('alwaysauth') or who.find("@") <= 0:
				if self.connection:
					self.to_be_sent.append(common.xmpp.Presence(who,
						'subscribed'))
				if who.find("@") <= 0:
					self.dispatch('NOTIFY',
						(prs.getFrom().getStripped().encode('utf8'), 'offline',
						'offline', prs.getFrom().getResource().encode('utf8'), prio,
						keyID, None, None, None, None, None, None))
			else:
				if not status:
					status = _('I would like to add you to my roster.')
				self.dispatch('SUBSCRIBE', (who, status))
		elif ptype == 'subscribed':
			jid = prs.getFrom()
			self.dispatch('SUBSCRIBED', (jid.getStripped().encode('utf8'),
				jid.getResource().encode('utf8')))
			self.dispatch('UPDUSER', (jid.getStripped().encode('utf8'),
				jid.getNode(), [_('General')]))
			#BE CAREFUL: no con.updateRosterItem() in a callback
			gajim.log.debug(_('we are now subscribed to %s') % who)
		elif ptype == 'unsubscribe':
			gajim.log.debug(_('unsubscribe request from %s') % who)
		elif ptype == 'unsubscribed':
			gajim.log.debug(_('we are now unsubscribed from %s') % who)
			self.dispatch('UNSUBSCRIBED', prs.getFrom().getStripped())
		elif ptype == 'error':
			errmsg = prs.getError()
			errcode = prs.getErrorCode()
			if errcode == '409':	#conflict:	Nick Conflict
				self.dispatch('ERROR', (errmsg, ''))
			elif errcode == '502': # Internal Timeout:
				self.dispatch('NOTIFY', (prs.getFrom().getStripped().encode('utf8'),
					'error', errmsg, prs.getFrom().getResource().encode('utf8'),
					prio, keyID, prs.getRole(), prs.getAffiliation(), prs.getJid(),
					prs.getReason(), prs.getActor(), prs.getStatusCode(),
					prs.getNewNick()))
			else:
				self.dispatch('ERROR_ANSWER', (prs.getFrom().getStripped(), errmsg,
																					errcode))
		if not ptype or ptype == 'unavailable':
			jid = prs.getFrom()
			gajim.logger.write('status', status, str(jid).encode('utf8'), show)
			account = prs.getFrom().getStripped().encode('utf8')
			resource =  prs.getFrom().getResource().encode('utf8')
			self.dispatch('NOTIFY', ( account, show, status,
				resource, prio, keyID, prs.getRole(),
				prs.getAffiliation(), prs.getJid(), prs.getReason(),
				prs.getActor(), prs.getStatusCode(), prs.getNewNick()))
	# END presenceCB

	def _disconnectedCB(self):
		"""Called when we are disconnected"""
		gajim.log.debug('disconnectedCB')
		if not self.connection:
			return
		self.connected = 0
		self.dispatch('STATUS', 'offline')
		self.connection = None
		if not self.on_purpose:
			self.dispatch('ERROR', 
			(_('Connection with account "%s" has been lost') % self.name,
			_('To continue sending and receiving messages, you will need to reconnect.')))
		self.on_purpose = False
	# END disconenctedCB
	
	def _bytestreamSetCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamSetCB')
		target = str(iq_obj.getAttr('to'))
		id = str(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		sid = str(query.getAttr('sid'))
		file_props = self.receiver.get_file_props(sid)
		if file_props is None:
			return
			# todo - error
		streamhosts=[]
		for item in query.getChildren():
			if item.getName() == 'streamhost':
				host_dict={}
				for attr in item.getAttrs():
					val = item.getAttr(attr)
					if type(val) == unicode:
						val = val.encode('utf-8')
					if type(attr) == unicode:
						attr = attr.encode('utf-8')
					host_dict[attr] = val
				streamhosts.append(host_dict)
		
		for streamhost in streamhosts:
			sock5 = socks5.Socks5Receiver(host = streamhost['host'], \
				port = int(streamhost['port']), initiator = streamhost['jid'], 
				target = target, sid = sid, file_props = file_props)
			ret = self.receiver.add_receiver(sock5)
			if ret is None:
				continue
			iq = common.xmpp.Iq(to = streamhost['jid'], typ = 'result', frm = target)
			iq.setAttr('id', id)
			query = iq.setTag('query')
			query.setNamespace(common.xmpp.NS_BYTESTREAM)
			stream_tag = query.setTag('streamhost-used')
			stream_tag.setAttr('jid', streamhost['jid'])
			self.to_be_sent.append(iq)
			raise common.xmpp.NodeProcessed

	def _discoGetCB(self, con, iq_obj):
		''' get disco info '''
		frm = str(iq_obj.getFrom())
		to = str(iq_obj.getAttr('to'))
		id = str(iq_obj.getAttr('id'))
		iq = common.xmpp.Iq(to = frm, typ = 'result', queryNS =\
			common.xmpp.NS_DISCO, frm = to)
		iq.setAttr('id', id)
		# bytestream transfers
		feature = common.xmpp.Node('feature')
		feature.setNamespace(common.xmpp.NS_SI)
		iq.addChild(node=feature)
		# filetransfers transfers
		_feature = common.xmpp.Node('feature')
		_feature.setNamespace(common.xmpp.NS_FILE)
		iq.addChild(node=_feature)
		self.to_be_sent.append(iq)
		raise common.xmpp.NodeProcessed
		
	def _siSetCB(self, con, iq_obj):
		gajim.log.debug('_siSetCB')
		jid = iq_obj.getFrom().getStripped().encode('utf8')
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		mime_type = si.getAttr('mime-type')
		if profile != NS_FILE:
			return
		feature = si.getTag('feature')
		file_tag = si.getTag('file')
		file_props = {}
		for attribute in file_tag.getAttrs():
			attribute = attribute.encode('utf-8')
			if attribute in ['name', 'size', 'hash', 'date']:
				val = file_tag.getAttr(attribute)
				if val is None:
					continue
				if type(val) is unicode:
					val = val.encode('utf-8')
				file_props[attribute] = val
		file_desc_tag = file_tag.getTag('desc')
		if file_desc_tag is not None:
			file_props['desc'] = file_desc_tag.getData()
		
		if mime_type is not None:
			file_props['mime-type'] = mime_type
			
		file_props['sender'] = iq_obj.getFrom()
		file_props['request-id'] = str(iq_obj.getAttr('id'))
		file_props['sid'] = str(si.getAttr('id'))
		self.receiver.add_file_props(file_props)
		self.dispatch('FILE_REQUEST', (jid, file_props))
		raise common.xmpp.NodeProcessed
	
	def complete_file_transfer(self, file_props):
		''' file transfer is completed or stopped '''
		self.dispatch('FILE_RCV_COMPLETED', file_props)
	
	def send_file_rejection(self, file_props):
		''' informs sender that we refuse to download the file '''
		iq = common.xmpp.Protocol(name = 'iq', to = str(file_props['sender']), \
			typ = 'error')
		iq.setAttr('id', file_props['request-id'])
		err = common.xmpp.ErrorNode(code = '406', typ = 'auth', name = 'not-acceptable')
		iq.addChild(node=err)
		self.to_be_sent.append(iq)

	def send_file_approval(self, file_props):
		''' comfirm that we want to download the file '''
		iq = common.xmpp.Protocol(name = 'iq', to = str(file_props['sender']), \
			typ = 'result')
		iq.setAttr('id', file_props['request-id'])
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		file_tag = si.setTag('file')
		file_tag.setNamespace(common.xmpp.NS_FILE)
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='submit')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.delAttr('type')
		field.setValue('http://jabber.org/protocol/bytestreams')
		self.to_be_sent.append(iq)
		
	def _rosterSetCB(self, con, iq_obj):
		gajim.log.debug('rosterSetCB')
		for item in iq_obj.getTag('query').getChildren():
			jid  = item.getAttr('jid').encode('utf8')
			name = item.getAttr('name')
			if name:
				name = name.encode('utf8')
			sub  = item.getAttr('subscription').encode('utf8')
			ask  = item.getAttr('ask')
			if ask:
				ask = ask.encode('utf8')
			groups = []
			for group in item.getTags('group'):
				groups.append(group.getData().encode('utf8'))
			self.dispatch('ROSTER_INFO', (jid, name, sub, ask, groups))
		raise common.xmpp.NodeProcessed

	def _BrowseResultCB(self, con, iq_obj):
		gajim.log.debug('BrowseResultCB')
		identities, features, items = [], [], []
		for q in iq_obj.getChildren():
			if q.getNamespace() != common.xmpp.NS_BROWSE:
				continue
			attr = {}
			for key in q.getAttrs().keys():
				attr[key.encode('utf8')] = q.getAttr(key).encode('utf8')
			identities = [attr]
			for node in q.getChildren():
				if node.getName() == 'ns':
					features.append(node.getData())
				else:
					infos = {}
					for key in node.getAttrs().keys():
						infos[key.encode('utf8')] = node.getAttr(key).encode('utf8')
					infos['category'] = node.getName()
					items.append(infos)
			jid = str(iq_obj.getFrom())
			self.dispatch('AGENT_INFO', (jid, identities, features, items))

	def _DiscoverItemsCB(self, con, iq_obj):
		gajim.log.debug('DiscoverItemsCB')
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qp = iq_obj.getQueryPayload()
		items = []
		if not qp:
			qp = []
		for i in qp:
			attr = {}
			for key in i.getAttrs():
				attr[key.encode('utf8')] = i.getAttrs()[key].encode('utf8')
			items.append(attr)
		jid = str(iq_obj.getFrom())
		self.dispatch('AGENT_INFO_ITEMS', (jid, node, items))

	def _DiscoverInfoErrorCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoErrorCB')
		iq = common.xmpp.Iq(to = iq_obj.getFrom(), typ = 'get', queryNS =\
			common.xmpp.NS_AGENTS)
		self.to_be_sent.append(iq)

	def _DiscoverInfoCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoCB')
		# According to JEP-0030:
		# For identity: category, name is mandatory, type is optional.
		# For feature: var is mandatory
		identities, features = [], []
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qc = iq_obj.getQueryChildren()
		if not qc:
			qc = []
		for i in qc:
			if i.getName() == 'identity':
				attr = {}
				for key in i.getAttrs().keys():
					attr[key.encode('utf8')] = i.getAttr(key).encode('utf8')
				identities.append(attr)
			elif i.getName() == 'feature':
				features.append(i.getAttr('var'))
		jid = str(iq_obj.getFrom())
		if not identities:
			self.to_be_sent.append(common.xmpp.Iq(typ = 'get', queryNS = \
				common.xmpp.NS_AGENTS))
		else:
			self.dispatch('AGENT_INFO_INFO', (jid, node, identities, features))
			self.discoverItems(jid, node)

	def _VersionCB(self, con, iq_obj):
		gajim.log.debug('VersionCB')
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		qp.setTagData('name', 'Gajim')
		qp.setTagData('version', gajim.version)
		send_os = gajim.config.get('send_os_info')
		if send_os:
			qp.setTagData('os', get_os_info())
		self.to_be_sent.append(iq_obj)
		raise common.xmpp.NodeProcessed

	def _VersionResultCB(self, con, iq_obj):
		gajim.log.debug('VersionResultCB')
		client_info = ''
		os_info = ''
		qp = iq_obj.getTag('query')
		if qp.getTag('name'):
			client_info += qp.getTag('name').getData()
		if qp.getTag('version'):
			client_info += ' ' + qp.getTag('version').getData()
		if qp.getTag('os'):
			os_info += qp.getTag('os').getData()
		jid = iq_obj.getFrom().getStripped()
		resource = iq_obj.getFrom().getResource()
		self.dispatch('OS_INFO', (jid, resource, client_info, os_info))
	
	def _MucOwnerCB(self, con, iq_obj):
		gajim.log.debug('MucOwnerCB')
		qp = iq_obj.getQueryPayload()
		node = None
		for q in qp:
			if q.getNamespace() == common.xmpp.NS_DATA:
				node = q
		if not node:
			return
		# Parse the form
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
						if data in ['yes', 'true', 'assent', '1']:
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
					if label:
						dic[i]['options'][j]['label'] = label
					tags = option_tag.getTags('value')
					dic[i]['options'][j]['values'] = []
					for tag in tags:
						dic[i]['options'][j]['values'].append(tag.getData())
					j += 1
			i += 1
		self.dispatch('GC_CONFIG', (str(iq_obj.getFrom()), dic))

	def _MucErrorCB(self, con, iq_obj):
		gajim.log.debug('MucErrorCB')
		jid = str(iq_obj.getFrom())
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		self.dispatch('MSGERROR', (jid, errcode, errmsg))

	def _getRosterCB(self, con, iq_obj):
		if not self.connection:
			return
		roster = self.connection.getRoster().getRaw()
		if not roster:
			roster = {}
		else:
			for i in roster.keys():
				props = roster[i]
				if props.has_key('name') and props['name']:
					props['name'] = props['name'].encode('utf8')
				if props.has_key('groups') and props['groups']:
					props['groups'] = map(lambda e:e.encode('utf8'), props['groups'])
				if props.has_key('resources') and props['resources']:
					props['resources'] = map(lambda e:e.encode('utf8'),
						props['resources'])
				del roster[i]
				roster[i.encode('utf8')] = props
				
		name = gajim.config.get_per('accounts', self.name, 'name')
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		if roster.has_key(name + '@' + hostname):
			del roster[name + '@' + hostname]
		self.dispatch('ROSTER', roster)

	def _PrivateCB(self, con, iq_obj):
		'''
		Private Data (JEP 048 and 049)
		'''
		gajim.log.debug('PrivateCB')
		storage = iq_obj.getTag('query').getTag('storage')
		try:
			ns = storage.getNamespace() 
		except AttributeError:
			#Its a result for a 'set' Iq, so we don't do anything here
			return
		
		if ns == 'storage:bookmarks':
			#Bookmarked URLs and Conferences
			#http://www.jabber.org/jeps/jep-0048.html
			confs = storage.getTags('conference')
			urls = storage.getTags('url')
			for conf in confs:
				bm = { 'name': conf.getAttr('name'),
				       'jid': conf.getAttr('jid'),
				       'autojoin': conf.getAttr('autojoin'),
				       'password': conf.getTagData('password'),
				       'nick': conf.getTagData('nick') }

				self.bookmarks.append(bm)
			self.dispatch('BOOKMARKS', self.bookmarks)

		elif ns == 'gajim:prefs':
			#Preferences data
			#http://www.jabber.org/jeps/jep-0049.html
			#TODO: implement this
			pass 

	def _ErrorCB(self, con, iq_obj):
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		jid_from = str(iq_obj.getFrom())
		self.dispatch('ERROR_ANSWER', (jid_from, errmsg, errcode))
		
	def _StanzaArrivedCB(self, con, obj):
		self.last_incoming = time.time()
		self.keep_alive_sent = False

	def _event_dispatcher(self, realm, event, data):
		if realm == common.xmpp.NS_REGISTER:
			if event == common.xmpp.features.REGISTER_DATA_RECEIVED:
				# data is (agent, DataFrom)
				if self.new_account_info and\
				self.new_account_info['hostname'] == data[0]:
					#it's a new account
					req = data[1].asDict()
					req['username'] = self.new_account_info['name']
					req['password'] = self.new_account_info['password']
					if not common.xmpp.features.register(self.connection, data[0],
						req):
						self.dispatch('ERROR', (_('Error:'), self.connection.lastErr))
						return
					self.connected = 0
					self.password = self.new_account_info['password']
					if USE_GPG:
						self.gpg = GnuPG.GnuPG()
						gajim.config.set('usegpg', True)
					else:
						gajim.config.set('usegpg', False)
					gajim.connections[self.name] = self
					self.dispatch('ACC_OK', (self.name, self.new_account_info))
					self.new_account_info = None
					return
				self.dispatch('REGISTER_AGENT_INFO', (data[0], data[1].asDict()))

	def connect(self):
		"""Connect and authenticate to the Jabber server
		Returns connection, and connection type ('tls', 'ssl', 'tcp', '')"""
		name = gajim.config.get_per('accounts', self.name, 'name')
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		resource = gajim.config.get_per('accounts', self.name, 'resource')
		usessl = gajim.config.get_per('accounts', self.name, 'usessl')
		try_connecting_for_foo_secs = gajim.config.get_per('accounts', self.name,
			'try_connecting_for_foo_secs')

		#create connection if it doesn't already exist
		if self.connection:
			return self.connection
		self.connected = 1
		p = gajim.config.get_per('accounts', self.name, 'proxy')
		if p and p in gajim.config.get_per('proxies'):
			proxy = {'host': gajim.config.get_per('proxies', p, 'host')}
			proxy['port'] = gajim.config.get_per('proxies', p, 'port')
			proxy['user'] = gajim.config.get_per('proxies', p, 'user')
			proxy['password'] = gajim.config.get_per('proxies', p, 'pass')
		else:
			proxy = None
		if gajim.verbose:
			con = common.xmpp.Client(hostname)
		else:
			con = common.xmpp.Client(hostname, debug = [])
		common.xmpp.dispatcher.DefaultTimeout = try_connecting_for_foo_secs
		con.UnregisterDisconnectHandler(con.DisconnectHandler)
		con.RegisterDisconnectHandler(self._disconnectedCB)

		h = hostname
		p = 5222
		secur = None # autodetect [for SSL in 5223/443 and for TLS if broadcasted]
		if usessl:
			p = 5223
			secur=1 #1 means force SSL no matter what the port will be
		if gajim.config.get_per('accounts', self.name, 'use_custom_host'):
			h = gajim.config.get_per('accounts', self.name, 'custom_host')
			p = gajim.config.get_per('accounts', self.name, 'custom_port')

		con_type = con.connect((h, p), proxy = proxy, secure=secur) #FIXME: blocking
		if not con_type:
			gajim.log.debug("Couldn't connect to %s" % self.name)
			self.connected = 0
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', (_('Could not connect to "%s"') % self.name,
				_('Check your connection or try again later')))
			return None

		gajim.log.debug(_('Connected to server with %s'), con_type)

		self.dispatch('CON_TYPE', con_type) # notify the gui about con_type

		con.RegisterHandler('message', self._messageCB)
		con.RegisterHandler('presence', self._presenceCB)
		con.RegisterHandler('iq', self._vCardCB, 'result',
			common.xmpp.NS_VCARD)
		con.RegisterHandler('iq', self._rosterSetCB, 'set',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._siSetCB, 'set', 
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._discoGetCB, 'get', 
			common.xmpp.NS_DISCO)
		con.RegisterHandler('iq', self._bytestreamSetCB, 'set', 
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._BrowseResultCB, 'result',
			common.xmpp.NS_BROWSE)
		con.RegisterHandler('iq', self._DiscoverItemsCB, 'result',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverInfoCB, 'result',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._DiscoverInfoErrorCB, 'error',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._VersionCB, 'get',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._VersionResultCB, 'result',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._MucOwnerCB, 'result',
			common.xmpp.NS_MUC_OWNER)
		con.RegisterHandler('iq', self._getRosterCB, 'result',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._PrivateCB, 'result',
			common.xmpp.NS_PRIVATE)
		con.RegisterHandler('iq', self._ErrorCB, 'error')
		con.RegisterHandler('iq', self._StanzaArrivedCB)
		con.RegisterHandler('presence', self._StanzaArrivedCB)
		con.RegisterHandler('message', self._StanzaArrivedCB)
		con.RegisterEventHandler(self._event_dispatcher)

		try:
			#FIXME: blocking
			auth = con.auth(name, self.password, resource, 1)
		except IOError: #probably a timeout
			self.connected = 0
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', (_('Could not connect to "%s"') % self.name,
				_('Check your connection or try again later')))
			return None
		if auth:
			con.initRoster()
			self.last_incoming = time.time()
			self.connected = 2
			return con # return connection
		else:
			gajim.log.debug("Couldn't authenticate to %s" % self.name)
			self.connected = 0
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', (_('Authentication failed with "%s"') % \
				self.name,
				_('Please check your login and password for correctness.')))
			return None
	# END connect

	def register_handler(self, event, function):
		if event in self.handlers:
			self.handlers[event].append(function)

	def unregister_handler(self, event, function):
		if event in self.handlers:
			if function in self.handlers[event]:
				self.handlers[event].remove(function)

	def quit(self, kill_core):
		if kill_core:
			if self.connected > 1:
				self.connected = 0
				self.connection.disconnect()
			return

	def ask_roster(self):
		roster = {}
		if self.connection:
			roster = self.connection.getRoster().getRaw()
		return roster

	def build_privacy_rule(self, name, action):
		'''Build a Privacy rule stanza for invisibility'''
		iq = common.xmpp.Iq('set', common.xmpp.NS_PRIVACY, xmlns = '')
		l = iq.getTag('query').setTag('list', {'name': name})
		i = l.setTag('item', {'action': action, 'order': '1'})
		i.setTag('presence-out')
		return iq

	def activate_privacy_rule(self, name):
		'''activate a privacy rule'''
		iq = common.xmpp.Iq('set', common.xmpp.NS_PRIVACY, xmlns = '')
		iq.getTag('query').setTag('active', {'name': name})
		self.connection.send(iq)

	def send_invisible_presence(self, msg, signed, initial = False):
		# try to set the privacy rule
		iq = self.build_privacy_rule('invisible', 'deny')
		self.connection.SendAndCallForResponse(iq, self._continue_invisible,
			{'msg': msg, 'signed': signed, 'initial': initial})
	
	def _continue_invisible(self, con, iq_obj, msg, signed, initial):
		ptype = ''
		show = ''
		# FIXME: JEP 126 need some modifications (see http://lists.jabber.ru/pipermail/ejabberd/2005-July/001252.html). So I disable it for the moment
		if 1 or iq_obj.getType() == 'error': #server doesn't support privacy lists
			# We use the old way which is not xmpp complient
			ptype = 'invisible'
			show = 'invisible'
		else:
			# active the privacy rule
			self.privacy_rules_supported = True
			self.activate_privacy_rule('invisible')
		prio = str(gajim.config.get_per('accounts', self.name, 'priority'))
		p = common.xmpp.Presence(typ = ptype, priority = prio, show = show)
		if msg:
			p.setStatus(msg)
		if signed:
			p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
		self.connection.send(p)
		self.dispatch('STATUS', 'invisible')
		if initial:
			#ask our VCard
			iq = self.request_vcard(None)
			self.myVCardID.append(iq.getID())

			#Get bookmarks from private namespace
			self.get_bookmarks()
	
	def change_status(self, show, msg, sync = False):
		if sync:
			self.change_status2(show, msg)
		else:
			t = threading.Thread(target=self.change_status2, args = (show, msg))
			t.start()

	def change_status2(self, show, msg):
		if not show in STATUS_LIST:
			return -1
		sshow = show # show to be send
		if show == 'online':
			sshow = None
		signed = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG:
			if self.connected < 2 and self.gpg.passphrase is None:
				# We didn't set a passphrase
				self.dispatch('ERROR', (_('OpenPGP Key was not given'),
					_('You will be connected to %s without OpenPGP.') % self.name))
			else:
				if not msg:
					lowered_uf_status_msg = helpers.get_uf_show(show).lower()
					msg = _("I'm %s") % lowered_uf_status_msg
				signed = self.gpg.sign(msg, keyID)
				if signed == 'BAD_PASSPHRASE':
					signed = ''
					if self.connected < 2:
						self.dispatch('BAD_PASSPHRASE', ())
		self.status = msg
		if show != 'offline' and not self.connected:
			self.connection = self.connect()
			if self.connected == 2:
				self.connected = STATUS_LIST.index(show)
				#send our presence
				ptype = None
				if show == 'invisible':
					self.send_invisible_presence(msg, signed, True)
					return
				prio = str(gajim.config.get_per('accounts', self.name, 'priority'))
				p = common.xmpp.Presence(typ = ptype, priority = prio, show = sshow)
				if msg:
					p.setStatus(msg)
				if signed:
				    p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)

				if self.connection:
					self.connection.send(p)
				self.dispatch('STATUS', show)
				#ask our VCard
				iq = self.request_vcard(None)
				self.myVCardID.append(iq.getID())

				#Get bookmarks from private namespace
				self.get_bookmarks()
				
		elif show == 'offline' and self.connected:
			self.connected = 0
			if self.connection:
				self.on_purpose = True
				p = common.xmpp.Presence(typ = 'unavailable')
				if msg:
					p.setStatus(msg)
				if self.connection:
					self.connection.send(p)
				try:
					self.connection.disconnect()
				except:
					pass
			self.dispatch('STATUS', 'offline')
			self.connection = None
		elif show != 'offline' and self.connected:
			was_invisible = self.connected == STATUS_LIST.index('invisible')
			self.connected = STATUS_LIST.index(show)
			ptype = None
			if show == 'invisible':
				self.send_invisible_presence(msg, signed)
				return
			if was_invisible and self.privacy_rules_supported:
				iq = self.build_privacy_rule('visible', 'allow')
				self.connection.send(iq)
				self.activate_privacy_rule('visible')
			prio = str(gajim.config.get_per('accounts', self.name, 'priority'))
			p = common.xmpp.Presence(typ = ptype, priority = prio, show = sshow)
			if msg:
				p.setStatus(msg)
			if signed:
				p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
			if self.connection:
				self.connection.send(p)
			self.dispatch('STATUS', show)

	def send_message(self, jid, msg, keyID, type = 'chat', subject='', chatstate = None):
		if not self.connection:
			return
		if not msg and chatstate is None:
			return
		msgtxt = msg
		msgenc = ''
		if keyID and USE_GPG:
			#encrypt
			msgenc = self.gpg.encrypt(msg, [keyID])
			if msgenc:
				msgtxt = '[This message is encrypted]'
				lang = os.getenv('LANG')
				if lang is not None or lang != 'en': # we're not english
					msgtxt = _('[This message is encrypted]') +\
						' ([This message is encrypted])' # one  in locale and one en
		if type == 'chat':
			msg_iq = common.xmpp.Message(to = jid, body = msgtxt, typ = type)
		else:
			if subject:
				msg_iq = common.xmpp.Message(to = jid, body = msgtxt,
					typ = 'normal', subject = subject)
			else:
				msg_iq = common.xmpp.Message(to = jid, body = msgtxt,
					typ = 'normal')
		if msgenc:
			msg_iq.setTag(common.xmpp.NS_ENCRYPTED + ' x').setData(msgenc)

		# chatstates - if peer supports jep85, send chatstates
		# please note that the only valid tag inside a message containing a <body> tag is the active event
		if chatstate is not None:
			msg_iq.setTag(chatstate, {},
				namespace = 'http://jabber.org/protocol/chatstates')
		
		self.to_be_sent.append(msg_iq)
		if msg:
			gajim.logger.write('outgoing', msg, jid)
		self.dispatch('MSGSENT', (jid, msg, keyID))

	def send_stanza(self, stanza):
		''' send a stanza untouched '''
		if not self.connection:
			return
		self.to_be_sent.append(stanza)

	def request_subscription(self, jid, msg):
		if not self.connection:
			return
		gajim.log.debug('subscription request for %s' % jid)
		pres = common.xmpp.Presence(jid, 'subscribe')
		if not msg:
			msg = _('I would like to add you to my roster.')
		pres.setStatus(msg)
		self.to_be_sent.append(pres)

	def send_authorization(self, jid):
		if not self.connection:
			return
		self.to_be_sent.append(common.xmpp.Presence(jid, 'subscribed'))

	def refuse_authorization(self, jid):
		if not self.connection:
			return
		self.to_be_sent.append(common.xmpp.Presence(jid, 'unsubscribed'))

	def unsubscribe(self, jid):
		if not self.connection:
			return
		delauth = gajim.config.get('delauth')
		delroster = gajim.config.get('delroster')
		if delauth:
			self.connection.getRoster().Unsubscribe(jid)
		if delroster:
			self.connection.getRoster().delItem(jid)

	def _continue_unsubscribe(self, con, iq_obj, agent):
		self.connection.getRoster().delItem(agent)
		self.dispatch('AGENT_REMOVED', agent)

	def unsubscribe_agent(self, agent):
		if not self.connection:
			return
		iq = common.xmpp.Iq('set', common.xmpp.NS_REGISTER, to = agent)
		iq.getTag('query').setTag('remove')
		self.connection.SendAndCallForResponse(iq, self._continue_unsubscribe,
			{'agent': agent})
		return

	def update_contact(self, jid, name, groups):
		if self.connection:
			self.connection.getRoster().setItem(jid = jid, name = name,
				groups = groups)

	def request_agents(self, jid, node):
		if self.connection:
			self.to_be_sent.append(common.xmpp.Iq(to = jid, typ = 'get', 
				queryNS = common.xmpp.NS_BROWSE))
			self.discoverInfo(jid, node)

	def request_register_agent_info(self, agent):
		if not self.connection:
			return None
		common.xmpp.features.getRegInfo(self.connection, agent, sync = False)

	def register_agent(self, agent, info):
		if not self.connection:
			return
		# FIXME: Blocking
		common.xmpp.features.register(self.connection, agent, info)

	def new_account(self, name, config, sync = False):
		if sync:
			self.new_account2(name, config)
		else:
			t = threading.Thread(target=self.new_account2, args = (name, config))
			t.start()

	def new_account2(self, name, config):
		# If a connection already exist we cannot create a new account
		if self.connection:
			return
		p = config['proxy']
		if p and p in gajim.config.get_per('proxies'):
			proxy = {'host': gajim.config.get_per('proxies', p, 'host')}
			proxy['port'] = gajim.config.get_per('proxies', p, 'port')
			proxy['user'] = gajim.config.get_per('proxies', p, 'user')
			proxy['password'] = gajim.config.get_per('proxies', p, 'pass')
		else:
			proxy = None
		if gajim.verbose:
			c = common.xmpp.Client(server = config['hostname'])
		else:
			c = common.xmpp.Client(server = config['hostname'], debug = [])
		common.xmpp.dispatcher.DefaultTimeout = 45
		c.UnregisterDisconnectHandler(c.DisconnectHandler)
		c.RegisterDisconnectHandler(self._disconnectedCB)
		h = config['hostname']
		p = 5222
		usessl = None
		if usessl: #FIXME: we cannot create an account if we want ssl connection to create it
			p = 5223
		if config['use_custom_host']:
			h = config['custom_host']
			p = config['custom_port']
		secur = None # autodetect [for SSL in 5223/443 and for TLS if broadcasted]
		if usessl:
			secur=1 #1 means force SSL no matter what the port is
		con_type = c.connect((h, p), proxy = proxy, secure=secur)#FIXME: blocking
		if not con_type:
			gajim.log.debug("Couldn't connect to %s" % name)
			self.dispatch('ERROR', (_('Could not connect to "%s"') % name,
				_('Check your connection or try again later.')))
			return False
		gajim.log.debug(_('Connected to server with %s'), con_type)

		c.RegisterEventHandler(self._event_dispatcher)
		self.new_account_info = config
		self.connection = c
		self.name = name
		common.xmpp.features.getRegInfo(c, config['hostname'])

	def account_changed(self, new_name):
		self.name = new_name

	def request_os_info(self, jid, resource):
		if not self.connection:
			return
		to_whom_jid = jid
		if resource:
			to_whom_jid += '/' + resource
		iq = common.xmpp.Iq(to=to_whom_jid, typ = 'get', queryNS =\
			common.xmpp.NS_VERSION)
		self.to_be_sent.append(iq)

	def request_vcard(self, jid = None):
		'''request the VCARD and return the iq'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get')
		if jid:
			iq.setTo(jid)
		iq.setTag(common.xmpp.NS_VCARD + ' vCard')
		self.to_be_sent.append(iq)
		return iq
			#('VCARD', {entry1: data, entry2: {entry21: data, ...}, ...})
	
	def send_vcard(self, vcard):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set')
		iq2 = iq.setTag(common.xmpp.NS_VCARD + ' vCard')
		for i in vcard:
			if i == 'jid':
				continue
			if type(vcard[i]) == type({}):
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
		self.to_be_sent.append(iq)

	def get_settings(self):
		''' Get Gajim settings as described in JEP 0049 '''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='gajim', namespace='gajim:prefs')
		self.to_be_sent.append(iq)

	def get_bookmarks(self):
		''' Get Bookmarks from storage as described in JEP 0048 '''
		self.bookmarks = [] #avoid multiple bookmarks when re-connecting
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name="query", namespace="jabber:iq:private")
		iq3 = iq2.addChild(name="storage", namespace="storage:bookmarks")
		self.to_be_sent.append(iq)

	def store_bookmarks(self):
		''' Send bookmarks to the storage namespace '''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='set')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='storage', namespace='storage:bookmarks')
		for bm in self.bookmarks:
			iq4 = iq3.addChild(name = "conference")
			iq4.setAttr('jid', bm['jid'])
			iq4.setAttr('autojoin', bm['autojoin'])
			iq4.setAttr('name', bm['name'])
			iq5 = iq4.setTagData('nick', bm['nick'])
			iq5 = iq4.setTagData('password', bm['password'])
		self.to_be_sent.append(iq)

	def send_agent_status(self, agent, ptype):
		if not self.connection:
			return
		p = common.xmpp.Presence(to = agent, typ = ptype)
		self.to_be_sent.append(p)

	def join_gc(self, nick, room, server, password):
		if not self.connection:
			return
		show = STATUS_LIST[self.connected]
		ptype = None
		if show == 'online':
			show = None
		p = common.xmpp.Presence(to = '%s@%s/%s' % (room, server, nick),
			show = show, status = self.status)
		t = p.setTag(common.xmpp.NS_MUC + ' x')
		if password:
			t.setTagData('password', password)
		self.to_be_sent.append(p)

	def send_gc_message(self, jid, msg):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(jid, msg, typ = 'groupchat')
		self.to_be_sent.append(msg_iq)
		self.dispatch('MSGSENT', (jid, msg))

	def send_gc_subject(self, jid, subject):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(jid,typ = 'groupchat', subject = subject)
		self.to_be_sent.append(msg_iq)

	def request_gc_config(self, room_jid):
		iq = common.xmpp.Iq(typ = 'get', queryNS = common.xmpp.NS_MUC_OWNER,
			to = room_jid)
		self.to_be_sent.append(iq)

	def change_gc_nick(self, room_jid, nick):
		if not self.connection:
			return
		self.to_be_sent.append(common.xmpp.Presence(to = '%s/%s' % (room_jid,
			nick)))

	def send_gc_status(self, nick, jid, show, status):
		if not self.connection:
			return
		ptype = None
		if show == 'offline':
			ptype = 'unavailable'
			show = None
		if show == 'online':
			show = None
		self.to_be_sent.append(common.xmpp.Presence(to = '%s/%s' % (jid, nick),
			typ = ptype, show = show, status = status))

	def gc_set_role(self, room_jid, nick, role, reason = ''):
		'''role is for all the life of the room so it's based on nick'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('nick', nick)
		item.setAttr('role', role)
		if reason:
			item.addChild(name = 'reason', payload = reason)
		self.to_be_sent.append(iq)

	def gc_set_affiliation(self, room_jid, jid, affiliation, reason = ''):
		'''affiliation is for all the life of the room so it's based on jid'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('jid', jid)
		item.setAttr('affiliation', affiliation)
		if reason:
			item.addChild(name = 'reason', payload = reason)
		self.to_be_sent.append(iq)

	def send_gc_config(self, room_jid, config):
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_OWNER)
		query = iq.getTag('query')
		# FIXME: should really use XData class
		x = query.setTag(common.xmpp.NS_DATA + ' x', attrs = {'type': 'submit'})
		i = 0
		while config.has_key(i):
			if not config[i].has_key('type'):
				i += 1
				continue
			if config[i]['type'] == 'fixed':
				i += 1
				continue
			tag = x.addChild('field')
			if config[i].has_key('var'):
				tag.setAttr('var', config[i]['var'])
			if config[i].has_key('values'):
				for val in  config[i]['values']:
					if val == False:
						val = '0'
					elif val == True:
						val = '1'
					tag.setTagData('value', val)
			i += 1
		self.to_be_sent.append(iq)

	def gpg_passphrase(self, passphrase):
		if USE_GPG:
			self.gpg.passphrase = passphrase

	def ask_gpg_keys(self):
		if USE_GPG:
			keys = self.gpg.get_keys()
			return keys
		return None

	def ask_gpg_secrete_keys(self):
		if USE_GPG:
			keys = self.gpg.get_secret_keys()
			return keys
		return None

	def change_password(self, password, username):
		if not self.connection:
			return
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		iq = common.xmpp.Iq(typ = 'set', to = hostname)
		q = iq.setTag(common.xmpp.NS_REGISTER + ' query')
		q.setTagData('username',username)
		q.setTagData('password',password)
		self.to_be_sent.append(iq)

	def unregister_account(self):
		if self.connected == 0:
			self.connection = self.connect()
		if self.connected > 1:
			hostname = gajim.config.get_per('accounts', self.name, 'hostname')
			iq = common.xmpp.Iq(typ = 'set', to = hostname)
			q = iq.setTag(common.xmpp.NS_REGISTER + ' query').setTag('remove')
			self.to_be_sent.append(iq)

	def send_keepalive(self):
		# we received nothing for the last foo seconds (60 secs by default)
		hostname = gajim.config.get_per('accounts', self.name,
			'hostname')
		iq = common.xmpp.Iq('get', common.xmpp.NS_LAST, to = hostname)
		self.to_be_sent.append(iq)
		self.keep_alive_sent = True

	def process(self, timeout):
		if not self.connection:
			return
		if self.connected:
			now = time.time()
			l = []
			for t in self.last_sent:
				if (now - t) < 1:
					l.append(t)
			self.last_sent = l
			t_limit = time.time() + timeout
			while time.time() < t_limit and len(self.to_be_sent) and \
					len(self.last_sent) < gajim.config.get_per('accounts',
						self.name, 'max_stanza_per_sec'):
				tosend = self.to_be_sent.pop(0)
				
				self.connection.send(tosend)
				self.last_sent.append(time.time())
			try:
				if gajim.config.get_per('accounts', self.name,
				'keep_alives_enabled'): # do we want keepalives?
					keep_alive_every_foo_secs = gajim.config.get_per('accounts',
						self.name,'keep_alive_every_foo_secs')
					#should we send keepalive?
					if time.time() > (self.last_incoming + \
							keep_alive_every_foo_secs) and not self.keep_alive_sent:
						self.send_keepalive()

					# did the server reply to the keepalive? if no disconnect
					keep_alive_disconnect_after_foo_secs = gajim.config.get_per(
						'accounts', self.name,
						'keep_alive_disconnect_after_foo_secs') # 2 mins by default
					if time.time() > (self.last_incoming + \
							keep_alive_disconnect_after_foo_secs):
						self.connection.disconnect() # disconnect if no answer
						msg = _('%s seconds have passed and server did not reply to our keepalive. Gajim disconnected from %s') % (str(keep_alive_disconnect_after_foo_secs), self.name)
						gajim.log.debug(msg)
						return
				if self.connection:
					self.connection.Process(timeout)
				if self.receiver.connected > 0:
					self.receiver.process(timeout)
			except:
				gajim.log.debug(_('error appeared while processing xmpp:'))
				traceback.print_exc()
				self.connected = 0
				self.dispatch('STATUS', 'offline')
				if not self.connection:
					return
				try:
					self.connection.disconnect()
				except:
					gajim.log.debug(_('error appeared while processing xmpp:'))
					traceback.print_exc()
				self.connection = None
# END Connection
