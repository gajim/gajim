##	common/connection.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
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

# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'

import sys
import sha
import os
import time
import sre
import traceback
import threading
import select
import socket

from calendar import timegm

import common.xmpp

from common import helpers
from common import gajim
from common import GnuPG
import socks5
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
		full_path_to_executable = helpers.is_in_path(executable, return_abs_path = True)
		if full_path_to_executable:
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
		self.name = name
		self.connected = 0 # offline
		self.connection = None # xmpppy instance
		self.gpg = None
		self.vcard_sha = None
		self.status = ''
		self.old_show = ''
		self.time_to_reconnect = None
		self.new_account_info = None
		self.bookmarks = []
		self.on_purpose = False
		self.last_io = time.time()
		self.to_be_sent = []
		self.last_sent = []
		self.files_props = {}
		self.password = gajim.config.get_per('accounts', name, 'password')
		self.server_resource = gajim.config.get_per('accounts', name, 'resource')
		self.privacy_rules_supported = False
		#Do we continue connection when we get roster (send presence,get vcard...)
		self.continue_connect_info = None
		#List of IDs we are waiting answers for {id: type_of_request, }
		self.awaiting_answers = {}
		if USE_GPG:
			self.gpg = GnuPG.GnuPG()
			gajim.config.set('usegpg', True)
		else:
			gajim.config.set('usegpg', False)
		self.retrycount = 0
	# END __init__

	def put_event(self, ev):
		if gajim.events_for_ui.has_key(self.name):
			gajim.events_for_ui[self.name].append(ev)

	def dispatch(self, event, data):
		'''always passes account name as first param'''
		gajim.mutex_events_for_ui.lock(self.put_event, [event, data])
		gajim.mutex_events_for_ui.unlock()

	def add_sha(self, p):
		c = p.setTag('x', namespace = common.xmpp.NS_VCARD_UPDATE)
		if self.vcard_sha is not None:
			c.setTagData('photo', self.vcard_sha)
		return p

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
		our_jid = gajim.get_jid_from_account(self.name)
		resource = ''
		if frm_iq:
			frm = frm_iq.getStripped()
			resource = frm_iq.getResource()
		else:
			frm = our_jid
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
			if frm == our_jid:
				if vcard.has_key('PHOTO') and type(vcard['PHOTO']) == type({}) and \
				vcard['PHOTO'].has_key('BINVAL'):
					photo = vcard['PHOTO']['BINVAL']
					self.vcard_sha = sha.sha(photo).hexdigest()
				else:
					self.vcard_sha = ''
				self.dispatch('MYVCARD', vcard)
				#we re-send our presence with sha if we are not invisible
				if STATUS_LIST[self.connected] == 'invisible':
					return
				sshow = helpers.get_xmpp_show(STATUS_LIST[self.connected])
				prio = unicode(gajim.config.get_per('accounts', self.name,
					'priority'))
				p = common.xmpp.Presence(typ = None, priority = prio, show = sshow,
					status = self.status)
				p = self.add_sha(p)
				self.to_be_sent.append(p)
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
			self.dispatch('MSGERROR', (unicode(msg.getFrom()),
				msg.getErrorCode(), msg.getError(), msgtxt, tim))
		elif mtype == 'groupchat':
			if subject:
				self.dispatch('GC_SUBJECT', (unicode(msg.getFrom()), subject))
			else:
				if not msg.getTag('body'): #no <body>
					return
				self.dispatch('GC_MSG', (unicode(msg.getFrom()), msgtxt, tim))
				gajim.logger.write('gc', msgtxt, unicode(msg.getFrom()),
					tim = tim)
		elif mtype == 'normal': # it's single message
			log_msgtxt = msgtxt
			if subject:
				log_msgtxt = _('Subject: %s\n%s') % (subject, msgtxt)
			gajim.logger.write('incoming', log_msgtxt, unicode(msg.getFrom()),
				tim = tim)
			self.dispatch('MSG', (unicode(msg.getFrom()), msgtxt, tim,
				encrypted, mtype, subject, None))
		else: # it's type 'chat'
			if not msg.getTag('body') and chatstate is None: #no <body>
				return
			log_msgtxt = msgtxt
			if subject:
				log_msgtxt = _('Subject: %s\n%s') % (subject, msgtxt)
			if msg.getTag('body'):
				gajim.logger.write('incoming', log_msgtxt,
					unicode(msg.getFrom()), tim = tim)
			self.dispatch('MSG', (unicode(msg.getFrom()), msgtxt, tim,
				encrypted, mtype, subject, chatstate))
	# END messageCB

	def _presenceCB(self, con, prs):
		"""Called when we receive a presence"""
		who = unicode(prs.getFrom())
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
					p = common.xmpp.Presence(who, 'subscribed')
					p = self.add_sha(p)
					self.to_be_sent.append(p)
				if who.find("@") <= 0:
					self.dispatch('NOTIFY',
						(prs.getFrom().getStripped(), 'offline', 'offline',
						prs.getFrom().getResource(), prio, keyID, None, None,
						None, None, None, None))
			else:
				if not status:
					status = _('I would like to add you to my roster.')
				self.dispatch('SUBSCRIBE', (who, status))
		elif ptype == 'subscribed':
			jid = prs.getFrom()
			self.dispatch('SUBSCRIBED', (jid.getStripped(), jid.getResource()))
			# BE CAREFUL: no con.updateRosterItem() in a callback
			gajim.log.debug(_('we are now subscribed to %s') % who)
		elif ptype == 'unsubscribe':
			gajim.log.debug(_('unsubscribe request from %s') % who)
		elif ptype == 'unsubscribed':
			gajim.log.debug(_('we are now unsubscribed from %s') % who)
			self.dispatch('UNSUBSCRIBED', prs.getFrom().getStripped())
		elif ptype == 'error':
			errmsg = prs.getError()
			errcode = prs.getErrorCode()
			if errcode == '502': # Internal Timeout:
				self.dispatch('NOTIFY', (prs.getFrom().getStripped(),
					'error', errmsg, prs.getFrom().getResource(),
					prio, keyID, prs.getRole(), prs.getAffiliation(), prs.getJid(),
					prs.getReason(), prs.getActor(), prs.getStatusCode(),
					prs.getNewNick()))
			elif errcode == '401': # password required to join
				self.dispatch('ERROR', (_('Unable to join room'), 
					_('A password is required to join this room.')))
			elif errcode == '403': # we are banned
				self.dispatch('ERROR', (_('Unable to join room'), 
					_('You are banned from this room.')))
			elif errcode == '404': # room does not exist
				self.dispatch('ERROR', (_('Unable to join room'), 
					_('Such room does not exist.')))
			elif errcode == '405':
				self.dispatch('ERROR', (_('Unable to join room'), 
					_('Room creation is restricted.')))
			elif errcode == '406':
				self.dispatch('ERROR', (_('Unable to join room'), 
					_('Your registered nickname must be used.')))
			elif errcode == '407':
				self.dispatch('ERROR', (_('Unable to join room'), 
					_('You are not in the members list.')))
			elif errcode == '409': # nick conflict
				self.dispatch('ERROR', (_('Unable to join room'), 
				_('Your desired nickname is in use or registered by another user.')))
			else:	# print in the window the error
				self.dispatch('ERROR_ANSWER', ('', prs.getFrom().getStripped(),
					errmsg, errcode))
		if not ptype or ptype == 'unavailable':
			jid = unicode(prs.getFrom())
			gajim.logger.write('status', status, jid, show)
			account = prs.getFrom().getStripped()
			resource =  prs.getFrom().getResource()
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

	def _reconnect(self):
		# Do not try to reco while we are already trying
		self.time_to_reconnect = None
		t = threading.Thread(target=self._reconnect2)
		t.start()

	def _reconnect2(self):
		gajim.log.debug('reconnect')
		self.retrycount += 1
		signed = self.get_signed_msg(self.status)
		self.connect_and_init(self.old_show, self.status, signed)
		if self.connected < 2: #connection failed
			if self.retrycount > 10:
				self.connected = 0
				self.dispatch('STATUS', 'offline')
				self.dispatch('ERROR', 
				(_('Connection with account "%s" has been lost') % self.name,
				_('To continue sending and receiving messages, you will need to reconnect.')))
				self.retrycount = 0
				return
			if self.retrycount > 5:
				self.time_to_reconnect = time.time() + 20
			else:
				self.time_to_reconnect = time.time() + 10
		else:
			#reconnect succeeded
			self.time_to_reconnect = None
			self.retrycount = 0
	
	def _disconnectedReconnCB(self):
		"""Called when we are disconnected"""
		gajim.log.debug('disconnectedReconnCB')
		if not self.connection:
			return
		self.old_show = STATUS_LIST[self.connected]
		self.connected = 0
		self.dispatch('STATUS', 'offline')
		self.connection = None
		if not self.on_purpose:
			if gajim.config.get_per('accounts', self.name, 'autoreconnect'):
				self.connected = 1
				self.dispatch('STATUS', 'connecting')
				self.time_to_reconnect = time.time() + 10
			else:
				self.dispatch('ERROR', 
				(_('Connection with account "%s" has been lost') % self.name,
				_('To continue sending and receiving messages, you will need to reconnect.')))
		self.on_purpose = False
	# END disconenctedReconnCB
		
	def _bytestreamErrorCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamErrorCB')
		frm = unicode(iq_obj.getFrom())
		id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		streamhost =  query.getTag('streamhost')
		jid = iq_obj.getFrom().getStripped()
		id = id[3:]
		if not self.files_props.has_key(id):
			return
		file_props = self.files_props[id]
		file_props['error'] = -4
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props))
		raise common.xmpp.NodeProcessed
	
	def _bytestreamSetCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamSetCB')
		target = unicode(iq_obj.getAttr('to'))
		id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		sid = unicode(query.getAttr('sid'))
		file_props = gajim.socks5queue.get_file_props(
			self.name, sid)
		streamhosts=[]
		for item in query.getChildren():
			if item.getName() == 'streamhost':
				host_dict={
					'state': 0, 
					'target': target, 
					'id': id, 
					'sid': sid,
					'initiator': unicode(iq_obj.getFrom())
				}
				for attr in item.getAttrs():
					host_dict[attr] = item.getAttr(attr)
				streamhosts.append(host_dict)
		if file_props is None:
			if self.files_props.has_key(sid):
				file_props = self.files_props[sid]
				file_props['fast'] = streamhosts
				if file_props['type'] == 's':
					# only psi do this

					if file_props.has_key('streamhosts'):
						file_props['streamhosts'].extend(streamhosts)
					else:
						file_props['streamhosts'] = streamhosts
					if not gajim.socks5queue.get_file_props(self.name, sid):
						gajim.socks5queue.add_file_props(self.name, file_props)
					gajim.socks5queue.connect_to_hosts(self.name, sid, 
						self.send_success_connect_reply, None)
				raise common.xmpp.NodeProcessed
		fast = None
		try:
			fast = query.getTag('fast')
		except Exception, e:
			pass
		file_props['streamhosts'] = streamhosts
		conn_err = False
		if file_props['type'] == 'r':
			gajim.socks5queue.connect_to_hosts(self.name, sid, 
				self.send_success_connect_reply, self._connect_error)
		raise common.xmpp.NodeProcessed
	
	def send_success_connect_reply(self, streamhost):
		''' send reply to the initiator of FT that we 
		made a connection
		'''
		if streamhost is None:
			return None
		iq = common.xmpp.Iq(to = streamhost['initiator'], typ = 'result', 
			frm = streamhost['target'])
		iq.setAttr('id', streamhost['id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		stream_tag = query.setTag('streamhost-used')
		stream_tag.setAttr('jid', streamhost['jid'])
		self.to_be_sent.append(iq)
		
	def _connect_error(self, to, _id, sid, code = 404):
		msg_dict = {
			404: 'Could not connect to given hosts', 
			405: 'Cancel', 
			406: 'Not acceptable', 
		}
		msg = msg_dict[code]
		iq = None
		iq = common.xmpp.Protocol(name = 'iq', to = to, 
			typ = 'error')
		iq.setAttr('id', _id)
		err = iq.setTag('error')
		err.setAttr('code', unicode(code))
		err.setData(msg)
		self.to_be_sent.append(iq)
		if code == 404:
			file_props = gajim.socks5queue.get_file_props(self.name, sid)
			if file_props is not None:
				self.disconnect_transfer(file_props)
				file_props['error'] = -3
				self.dispatch('FILE_REQUEST_ERROR', (to, file_props))
		
	def _bytestreamResultCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamResultCB')
		frm = unicode(iq_obj.getFrom())
		real_id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		streamhost = None
		try:
			streamhost = query.getTag('streamhost')
		except: 
			pass
		if streamhost is not None: # this is a result for proxy request
			jid = None
			try:
				jid = streamhost.getAttr('jid')
			except:
				raise common.xmpp.NodeProcessed
			proxyhosts = []
			for item in query.getChildren():
				if item.getName() == 'streamhost':
					host = item.getAttr('host')
					port = item.getAttr('port')
					jid = item.getAttr('jid')
					conf = gajim.config
					conf.add_per('ft_proxies65_cache', jid)
					conf.set_per('ft_proxies65_cache', jid,
						'host', unicode(host))
					conf.set_per('ft_proxies65_cache', jid,
						'port', int(port))
					conf.set_per('ft_proxies65_cache', jid,
						'jid', unicode(jid))
			raise common.xmpp.NodeProcessed
		try:
			streamhost =  query.getTag('streamhost-used')
		except: # this bytestream result is not what we need
			pass
		id = real_id[3:]
		if self.files_props.has_key(id):
			file_props = self.files_props[id]
		else:
			raise common.xmpp.NodeProcessed
		if streamhost is None: 
			# proxy approves the activate query
			if real_id[:3] == 'au_':
				id = real_id[3:]
				if not file_props.has_key('streamhost-used') or \
					file_props['streamhost-used'] is False:
					raise common.xmpp.NodeProcessed
				if not file_props.has_key('proxyhosts'):
					raise common.xmpp.NodeProcessed
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and \
					unicode(query.getAttr('sid')) == file_props['sid']:
						gajim.socks5queue.activate_proxy(host['idx'])
						break
			raise common.xmpp.NodeProcessed
		jid = streamhost.getAttr('jid')
		if file_props.has_key('streamhost-used') and \
			file_props['streamhost-used'] is True:
			raise common.xmpp.NodeProcessed
			
		if real_id[:3] == 'au_':
			gajim.socks5queue.send_file(file_props, self.name)
			raise common.xmpp.NodeProcessed
			
		proxy = None
		if file_props.has_key('proxyhosts'):
			for proxyhost in file_props['proxyhosts']:
				if proxyhost['jid'] == jid:
					proxy = proxyhost
		
		if proxy != None:
			file_props['streamhost-used'] = True
			if not file_props.has_key('streamhosts'):
				file_props['streamhosts'] = []
			file_props['streamhosts'].append(proxy)
			file_props['is_a_proxy'] = True
			receiver = socks5.Socks5Receiver(proxy, file_props['sid'], file_props)
			gajim.socks5queue.add_receiver(self.name, receiver)
			proxy['idx'] = receiver.queue_idx
			gajim.socks5queue.on_success = self.proxy_auth_ok
			raise common.xmpp.NodeProcessed
			
		else:
			gajim.socks5queue.send_file(file_props, self.name)
			if file_props.has_key('fast'):
				fasts = file_props['fast']
				if len(fasts) > 0:
					self._connect_error(unicode(iq_obj.getFrom()),
						fasts[0]['id'], file_props['sid'], code = 406)
			
		raise common.xmpp.NodeProcessed
	
	def remove_all_transfers(self):
		''' stops and removes all active connections from the socks5 pool '''
		for file_props in self.files_props.values():
			self.remove_transfer(file_props, remove_from_list = False)
		del(self.files_props)
		self.files_props = {}
	
	def remove_transfer(self, file_props, remove_from_list = True):
		if file_props is None:
			return
		if file_props.has_key('hash'):
			gajim.socks5queue.remove_sender(file_props['hash'])
		
		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if host.has_key('idx') and host['idx'] > 0:
					gajim.socks5queue.remove_receiver(host['idx'])
					gajim.socks5queue.remove_sender(host['idx'])
		sid = file_props['sid']
		gajim.socks5queue.remove_file_props(self.name, sid)
		
		if remove_from_list:
			if self.files_props.has_key('sid'):
				del(self.files_props['sid'])
				
	def disconnect_transfer(self, file_props):
		if file_props is None:
			return
		if file_props.has_key('hash'):
			gajim.socks5queue.remove_sender(file_props['hash'])
		
		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if host.has_key('idx') and host['idx'] > 0:
					gajim.socks5queue.remove_receiver(host['idx'])
					gajim.socks5queue.remove_sender(host['idx'])
			
	def proxy_auth_ok(self, proxy):
		'''cb, called after authentication to proxy server '''
		file_props = self.files_props[proxy['sid']]
		iq = common.xmpp.Protocol(name = 'iq', to = proxy['initiator'], 
		typ = 'set')
		auth_id = "au_" + proxy['sid']
		iq.setID(auth_id)
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('sid',  proxy['sid'])
		activate = query.setTag('activate')
		activate.setData(file_props['proxy_receiver'])
		iq.setID(auth_id)
		self.to_be_sent.append(iq)
		
	def _discoGetCB(self, con, iq_obj):
		''' get disco info '''
		frm = unicode(iq_obj.getFrom())
		to = unicode(iq_obj.getAttr('to'))
		id = unicode(iq_obj.getAttr('id'))
		iq = common.xmpp.Iq(to = frm, typ = 'result', queryNS =\
			common.xmpp.NS_DISCO, frm = to)
		iq.setAttr('id', id)
		query = iq.setTag('query')
		# bytestream transfers
		feature = common.xmpp.Node('feature')
		feature.setAttr('var', common.xmpp.NS_BYTESTREAM)
		query.addChild(node=feature)
		# si methods
		feature = common.xmpp.Node('feature')
		feature.setAttr('var', common.xmpp.NS_SI)
		query.addChild(node=feature)
		# filetransfers transfers
		feature = common.xmpp.Node('feature')
		feature.setAttr('var', common.xmpp.NS_FILE)
		query.addChild(node=feature)
		
		self.to_be_sent.append(iq)
		raise common.xmpp.NodeProcessed
	
	def _siResultCB(self, con, iq_obj):
		gajim.log.debug('_siResultCB')
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return 
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		file_props['receiver'] = unicode(iq_obj.getFrom())
		jid = iq_obj.getFrom().getStripped()
		si = iq_obj.getTag('si')
		feature = si.setTag('feature')
		if feature.getNamespace() != common.xmpp.NS_FEATURE:
			return
		form_tag = feature.getTag('x')
		form = common.xmpp.DataForm(node=form_tag)
		field = form.getField('stream-method')
		if field.getValue() != common.xmpp.NS_BYTESTREAM:
			return
		self.send_socks5_info(file_props, fast = True)
		raise common.xmpp.NodeProcessed
	
	def _get_sha(self, sid, initiator, target):
		import sha
		return sha.new("%s%s%s" % (sid, initiator, target)).hexdigest()
		
	def result_socks5_sid(self, sid, hash_id):
		''' store the result of sha message from auth  '''
		if not self.files_props.has_key(sid):
			return
		file_props = self.files_props[sid]
		file_props['hash'] = hash_id
		return
	
	
	def get_cached_proxies(self, proxy):
		''' get cached entries for proxy and request the cache again '''
		host = gajim.config.get_per('ft_proxies65_cache', proxy, 'host')
		port = gajim.config.get_per('ft_proxies65_cache', proxy, 'port')
		jid = gajim.config.get_per('ft_proxies65_cache', proxy, 'jid')
		
		iq = common.xmpp.Protocol(name = 'iq', to = proxy, typ = 'get')
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		# FIXME bad logic - this should be somewhere else!
		# this line should be put somewhere else
		# self.to_be_sent.append(iq)
		# ensure that we don;t return empty vars
		if None not in (host, port, jid) or '' not in (host, port, jid):
			return (host, port, jid)
		return (None, None, None)
		
	def send_socks5_info(self, file_props, fast = True, receiver = None, 
		sender = None):
		''' send iq for the present streamhosts and proxies '''
		if type(self.peerhost) != tuple:
			return
		port = gajim.config.get('file_transfers_port')
		ft_override_host_to_send = gajim.config.get('ft_override_host_to_send')
		cfg_proxies = gajim.config.get_per('accounts', self.name, 'file_transfer_proxies')
		if receiver is None:
			receiver = file_props['receiver']
		if sender is None:
			sender = file_props['sender']
		proxyhosts = []
		if fast and cfg_proxies:
			proxies = map(lambda e:e.strip(), cfg_proxies.split(','))
			for proxy in proxies:
				(host, _port, jid) = self.get_cached_proxies(proxy)
				if host is None:
					continue
				host_dict={
					'state': 0, 
					'target': unicode(receiver), 
					'id': file_props['sid'], 
					'sid': file_props['sid'], 
					'initiator': proxy,
					'host': host,
					'port': unicode(_port),
					'jid': jid
				}
				proxyhosts.append(host_dict)
		sha_str = self._get_sha(file_props['sid'], sender, 
			receiver)
		file_props['sha_str'] = sha_str
		if not ft_override_host_to_send:
			ft_override_host_to_send = self.peerhost[0]
		ft_override_host_to_send = socket.gethostbyname(ft_override_host_to_send)
		listener = gajim.socks5queue.start_listener(self.peerhost[0], port, 
			sha_str, self.result_socks5_sid, file_props['sid'])
		if listener == None:
			file_props['error'] = -5
			self.dispatch('FILE_REQUEST_ERROR', (unicode(receiver), file_props))
			self._connect_error(unicode(receiver), file_props['sid'], 
				file_props['sid'], code = 406)
			return
		
		iq = common.xmpp.Protocol(name = 'iq', to = unicode(receiver), 
			typ = 'set')
		file_props['request-id'] = 'id_' + file_props['sid']
		iq.setID(file_props['request-id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('mode', 'tcp')
		query.setAttr('sid', file_props['sid'])
		streamhost = query.setTag('streamhost')
		streamhost.setAttr('port', unicode(port))
		streamhost.setAttr('host', ft_override_host_to_send)
		streamhost.setAttr('jid', sender)
		if fast and proxyhosts != []:
			file_props['proxy_receiver'] = unicode(receiver)
			file_props['proxy_sender'] = unicode(sender)
			file_props['proxyhosts'] = proxyhosts
			for proxyhost in proxyhosts:
				streamhost = common.xmpp.Node(tag = 'streamhost')
				query.addChild(node=streamhost)
				streamhost.setAttr('port', proxyhost['port'])
				streamhost.setAttr('host', proxyhost['host'])
				streamhost.setAttr('jid', proxyhost['jid'])
				
				# don't add the proxy child tag for streamhosts, which are proxies
				# proxy = streamhost.setTag('proxy')
				# proxy.setNamespace(common.xmpp.NS_STREAM)
		self.to_be_sent.append(iq)
			
	def _siSetCB(self, con, iq_obj):
		gajim.log.debug('_siSetCB')
		jid = iq_obj.getFrom().getStripped()
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		mime_type = si.getAttr('mime-type')
		if profile != common.xmpp.NS_FILE:
			return
		feature = si.getTag('feature')
		file_tag = si.getTag('file')
		file_props = {'type': 'r'}
		for attribute in file_tag.getAttrs():
			if attribute in ['name', 'size', 'hash', 'date']:
				val = file_tag.getAttr(attribute)
				if val is None:
					continue
				file_props[attribute] = val
		file_desc_tag = file_tag.getTag('desc')
		if file_desc_tag is not None:
			file_props['desc'] = file_desc_tag.getData()
		
		if mime_type is not None:
			file_props['mime-type'] = mime_type
		name = gajim.config.get_per('accounts', self.name, 'name')
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		resource = self.server_resource
		file_props['receiver'] = name + '@' + hostname + '/' + resource
		file_props['sender'] = iq_obj.getFrom()
		file_props['request-id'] = unicode(iq_obj.getAttr('id'))
		file_props['sid'] = unicode(si.getAttr('id'))
		gajim.socks5queue.add_file_props(self.name, file_props)
		self.dispatch('FILE_REQUEST', (jid, file_props))
		raise common.xmpp.NodeProcessed
	
	def _siErrorCB(self, con, iq_obj):
		gajim.log.debug('_siErrorCB')
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		if profile != common.xmpp.NS_FILE:
			return
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return 
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		jid = iq_obj.getFrom().getStripped()
		file_props['error'] = -3
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props))
		raise common.xmpp.NodeProcessed
	
	def send_file_rejection(self, file_props):
		''' informs sender that we refuse to download the file '''
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'error')
		iq.setAttr('id', file_props['request-id'])
		err = common.xmpp.ErrorNode(code = '406', typ = 'auth', name = 'not-acceptable')
		iq.addChild(node=err)
		self.to_be_sent.append(iq)

	def send_file_approval(self, file_props):
		''' comfirm that we want to download the file '''
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'result')
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
		
	def send_file_request(self, file_props):
		name = gajim.config.get_per('accounts', self.name, 'name')
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		resource = self.server_resource
		frm = name + '@' + hostname + '/' + resource
		file_props['sender'] = frm
		fjid = file_props['receiver'].jid + '/' + file_props['receiver'].resource
		iq = common.xmpp.Protocol(name = 'iq', to = fjid, 
			typ = 'set')
		iq.setID(file_props['sid'])
		self.files_props[file_props['sid']] = file_props
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		si.setAttr('profile', common.xmpp.NS_FILE)
		si.setAttr('id', file_props['sid'])
		file_tag = si.setTag('file')
		file_tag.setNamespace(common.xmpp.NS_FILE)
		file_tag.setAttr('name', file_props['name'])
		file_tag.setAttr('size', file_props['size'])
		desc = file_tag.setTag('desc')
		if file_props.has_key('desc'):
			desc.setData(file_props['desc'])
		file_tag.setTag('range')
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='form')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.setAttr('type', 'list-single')
		field.addOption('http://jabber.org/protocol/bytestreams')
		self.to_be_sent.append(iq)
		
	def _rosterSetCB(self, con, iq_obj):
		gajim.log.debug('rosterSetCB')
		for item in iq_obj.getTag('query').getChildren():
			jid  = item.getAttr('jid')
			name = item.getAttr('name')
			sub  = item.getAttr('subscription')
			ask  = item.getAttr('ask')
			groups = []
			for group in item.getTags('group'):
				groups.append(group.getData())
			self.dispatch('ROSTER_INFO', (jid, name, sub, ask, groups))
		raise common.xmpp.NodeProcessed

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
				attr[key] = i.getAttrs()[key]
			items.append(attr)
		jid = unicode(iq_obj.getFrom())
		self.dispatch('AGENT_INFO_ITEMS', (jid, node, items))

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
					attr[key] = i.getAttr(key)
				identities.append(attr)
			elif i.getName() == 'feature':
				features.append(i.getAttr('var'))
		jid = unicode(iq_obj.getFrom())
		if identities: #if not: an error occured
			self.dispatch('AGENT_INFO_INFO', (jid, node, identities, features))

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
		self.dispatch('GC_CONFIG', (unicode(iq_obj.getFrom()), dic))

	def _MucErrorCB(self, con, iq_obj):
		gajim.log.debug('MucErrorCB')
		jid = unicode(iq_obj.getFrom())
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		self.dispatch('MSGERROR', (jid, errcode, errmsg))

	def _getRosterCB(self, con, iq_obj):
		if not self.connection:
			return
		roster = self.connection.getRoster().getRaw()
		if not roster:
			roster = {}
			
		jid = gajim.get_jid_from_account(self.name)
		
		if roster.has_key(jid):
			del roster[jid]
		self.dispatch('ROSTER', roster)

		#continue connection
		if self.connected > 1 and self.continue_connect_info:
			show = self.continue_connect_info[0]
			msg = self.continue_connect_info[1]
			signed = self.continue_connect_info[2]
			self.connected = STATUS_LIST.index(show)
			sshow = helpers.get_xmpp_show(show)
			#send our presence
			if show == 'invisible':
				self.send_invisible_presence(msg, signed, True)
				return
			prio =  unicode(gajim.config.get_per('accounts', self.name,
				'priority'))
			p = common.xmpp.Presence(typ = None, priority = prio, show = sshow)
			p = self.add_sha(p)
			if msg:
				p.setStatus(msg)
			if signed:
			    p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)

			if self.connection:
				self.connection.send(p)
			self.dispatch('STATUS', show)
			#ask our VCard
			self.request_vcard(None)

			#Get bookmarks from private namespace
			self.get_bookmarks()
		self.continue_connect_info = None

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
				autojoin_val = conf.getAttr('autojoin')
				if autojoin_val is None: # not there (it's optional)
					autojoin_val == False
				bm = { 'name': conf.getAttr('name'),
				       'jid': conf.getAttr('jid'),
				       'autojoin': autojoin_val,
				       'password': conf.getTagData('password'),
				       'nick': conf.getTagData('nick') }

				self.bookmarks.append(bm)
			self.dispatch('BOOKMARKS', self.bookmarks)

		elif ns == 'gajim:prefs':
			#Preferences data
			#http://www.jabber.org/jeps/jep-0049.html
			#TODO: implement this
			pass
	
	def build_http_auth_answer(self, iq_obj, answer):
		if answer == 'yes':
			iq = iq_obj.buildReply('result')
		elif answer == 'no':
			iq = iq_obj.buildReply('error')
			iq.setError('not-authorized', 401)
		self.to_be_sent.append(iq)
	
	def _HttpAuthCB(self, con, iq_obj):
		gajim.log.debug('HttpAuthCB')
		opt = gajim.config.get_per('accounts', self.name, 'http_auth')
		if opt in ['yes', 'no']:
			self.build_http_auth_answer(iq_obj, opt)
		else:
			method = iq_obj.getTagAttr('confirm', 'method')
			url = iq_obj.getTagAttr('confirm', 'url')
			self.dispatch('HTTP_AUTH', (method, url, iq_obj));
		raise common.xmpp.NodeProcessed

	def _ErrorCB(self, con, iq_obj):
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		jid_from = unicode(iq_obj.getFrom())
		id = unicode(iq_obj.getID())
		self.dispatch('ERROR_ANSWER', (id, jid_from, errmsg, errcode))
		
	def _StanzaArrivedCB(self, con, obj):
		self.last_io = time.time()

	def _IqCB(self, con, iq_obj):
		id = iq_obj.getID()
		if id not in self.awaiting_answers:
			return
		if self.awaiting_answers[id] == VCARD_PUBLISHED:
			typ = iq_obj.getType()
			if iq_obj.getType() == 'result':
				self.dispatch('VCARD_PUBLISHED', ())
			elif iq_obj.getType() == 'error':
				self.dispatch('VCARD_NOT_PUBLISHED', ())
		del self.awaiting_answers[id]

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
		elif realm == '':
			if event == common.xmpp.transports.DATA_RECEIVED:
				self.dispatch('STANZA_ARRIVED', unicode(data))
			elif event == common.xmpp.transports.DATA_SENT:
				self.dispatch('STANZA_SENT', unicode(data))

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
		con.RegisterDisconnectHandler(self._disconnectedReconnCB)

		h = hostname
		p = 5222
		# autodetect [for SSL in 5223/443 and for TLS if broadcasted]
		secur = None
		if usessl:
			p = 5223
			secur=1 #1 means force SSL no matter what the port will be
		if gajim.config.get_per('accounts', self.name, 'use_custom_host'):
			h = gajim.config.get_per('accounts', self.name, 'custom_host')
			p = gajim.config.get_per('accounts', self.name, 'custom_port')

		con_type = con.connect((h, p), proxy = proxy, secure=secur) #FIXME: blocking
		if not con_type:
			gajim.log.debug("Couldn't connect to %s" % self.name)
			if not self.retrycount:
				self.connected = 0
				self.dispatch('STATUS', 'offline')
				self.dispatch('ERROR', (_('Could not connect to "%s"') % self.name,
					_('Check your connection or try again later.')))
			return None

		self.peerhost = con.get_peerhost()
		gajim.log.debug(_('Connected to server with %s') % con_type)

		# notify the gui about con_type
		self.dispatch('CON_TYPE', con_type)

		con.RegisterHandler('message', self._messageCB)
		con.RegisterHandler('presence', self._presenceCB)
		con.RegisterHandler('iq', self._vCardCB, 'result',
			common.xmpp.NS_VCARD)
		con.RegisterHandler('iq', self._rosterSetCB, 'set',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._siSetCB, 'set', 
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._siErrorCB, 'error', 
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._siResultCB, 'result', 
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._discoGetCB, 'get', 
			common.xmpp.NS_DISCO)
		con.RegisterHandler('iq', self._bytestreamSetCB, 'set', 
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamResultCB, 'result', 
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamErrorCB, 'error',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._DiscoverItemsCB, 'result',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverInfoCB, 'result',
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
		con.RegisterHandler('iq', self._HttpAuthCB, 'get',
			common.xmpp.NS_HTTP_AUTH)
		con.RegisterHandler('iq', self._ErrorCB, 'error')
		con.RegisterHandler('iq', self._IqCB)
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
		if hasattr(con, 'Resource'):
			self.server_resource = con.Resource
		con.RegisterEventHandler(self._event_dispatcher)
		if auth:
			con.initRoster()
			self.last_io = time.time()
			self.connected = 2
			return con # return connection
		else:
			gajim.log.debug("Couldn't authenticate to %s" % self.name)
			self.connected = 0
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', (_('Authentication failed with "%s"') % self.name,
				_('Please check your login and password for correctness.')))
			return None
	# END connect

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
		prio = unicode(gajim.config.get_per('accounts', self.name, 'priority'))
		p = common.xmpp.Presence(typ = ptype, priority = prio, show = show)
		p = self.add_sha(p)
		if msg:
			p.setStatus(msg)
		if signed:
			p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
		self.connection.send(p)
		self.dispatch('STATUS', 'invisible')
		if initial:
			#ask our VCard
			self.request_vcard(None)

			#Get bookmarks from private namespace
			self.get_bookmarks()

	def get_signed_msg(self, msg):
		signed = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG:
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if self.connected < 2 and self.gpg.passphrase is None and not use_gpg_agent:
				# We didn't set a passphrase
				self.dispatch('ERROR', (_('OpenPGP passphrase was not given'),
					#%s is the account name here
					_('You will be connected to %s without OpenPGP.') % self.name))
			elif self.gpg.passphrase is not None or use_gpg_agent:
				signed = self.gpg.sign(msg, keyID)
				if signed == 'BAD_PASSPHRASE':
					signed = ''
					if self.connected < 2:
						self.dispatch('BAD_PASSPHRASE', ())
		return signed

	def connect_and_init(self, show, msg, signed):
		self.continue_connect_info = [show, msg, signed]
		self.connection = self.connect()

	def change_status(self, show, msg, sync = False, auto = False):
		if sync:
			self.change_status2(show, msg, auto)
		else:
			t = threading.Thread(target=self.change_status2, args = (show, msg, auto))
			t.start()

	def change_status2(self, show, msg, auto = False):
		if not show in STATUS_LIST:
			return -1
		sshow = helpers.get_xmpp_show(show)
		if not msg:
			msg = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG and not msg:
			lowered_uf_status_msg = helpers.get_uf_show(show).lower()
			# do not show I'm invisible!
			if lowered_uf_status_msg == _('invisible'):
				lowered_uf_status_msg = _('offline')
			msg = _("I'm %s") % lowered_uf_status_msg
		signed = ''
		if not auto and not show == 'offline':
			signed = self.get_signed_msg(msg)
		self.status = msg
		if show != 'offline' and not self.connected:
			self.connect_and_init(show, msg, signed)

		elif show == 'offline' and self.connected:
			self.connected = 0
			if self.connection:
				self.on_purpose = True
				p = common.xmpp.Presence(typ = 'unavailable')
				p = self.add_sha(p)
				if msg:
					p.setStatus(msg)
				self.remove_all_transfers()
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
			if show == 'invisible':
				self.send_invisible_presence(msg, signed)
				return
			if was_invisible and self.privacy_rules_supported:
				iq = self.build_privacy_rule('visible', 'allow')
				self.connection.send(iq)
				self.activate_privacy_rule('visible')
			prio = unicode(gajim.config.get_per('accounts', self.name,
				'priority'))
			p = common.xmpp.Presence(typ = None, priority = prio, show = sshow)
			p = self.add_sha(p)
			if msg:
				p.setStatus(msg)
			if signed:
				p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
			if self.connection:
				self.connection.send(p)
			self.dispatch('STATUS', show)

	def send_motd(self, jid, subject = '', msg = ''):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(to = jid, body = msg, subject = subject)
		self.to_be_sent.append(msg_iq)

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
		p = common.xmpp.Presence(jid, 'subscribe')
		p = self.add_sha(p)
		if not msg:
			msg = _('I would like to add you to my roster.')
		p.setStatus(msg)
		self.to_be_sent.append(p)

	def send_authorization(self, jid):
		if not self.connection:
			return
		p = common.xmpp.Presence(jid, 'subscribed')
		p = self.add_sha(p)
		self.to_be_sent.append(p)

	def refuse_authorization(self, jid):
		if not self.connection:
			return
		p = common.xmpp.Presence(jid, 'unsubscribed')
		p = self.add_sha(p)
		self.to_be_sent.append(p)

	def unsubscribe(self, jid):
		if not self.connection:
			return
		if gajim.config.get('contact_mutual_removal'):
			self.connection.getRoster().delItem(jid)
		else:
			self.connection.getRoster().Unsubscribe(jid)

	def _continue_unsubscribe(self, con, iq_obj, agent):
		self.connection.getRoster().delItem(agent)

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
				queryNS = common.xmpp.NS_DISCO_ITEMS))

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
		id = self.connection.getAnID()
		iq.setID(id)
		self.awaiting_answers[str(id)] = VCARD_PUBLISHED
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
		p = self.add_sha(p)
		self.to_be_sent.append(p)

	def join_gc(self, nick, room, server, password):
		if not self.connection:
			return
		show = helpers.get_xmpp_show(STATUS_LIST[self.connected])
		ptype = None
		p = common.xmpp.Presence(to = '%s@%s/%s' % (room, server, nick),
			show = show, status = self.status)
		p = self.add_sha(p)
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
		p = common.xmpp.Presence(to = '%s/%s' % (room_jid, nick))
		p = self.add_sha(p)
		self.to_be_sent.append(p)

	def send_gc_status(self, nick, jid, show, status):
		if not self.connection:
			return
		ptype = None
		if show == 'offline':
			ptype = 'unavailable'
		show = helpers.get_xmpp_show(show)
		p = common.xmpp.Presence(to = '%s/%s' % (jid, nick), typ = ptype,
			show = show, status = status)
		p = self.add_sha(p)
		self.to_be_sent.append(p)

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
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if use_gpg_agent:
				self.gpg.passphrase = None
			else:
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

	def send_invite(self, room, to, reason=''):
		'''sends invitation'''
		message=common.xmpp.Message(to = room)
		message.addChild(name = 'x',namespace = common.xmpp.NS_MUC_USER)
		message.getChildren()[0].addChild(name = 'invite', attrs={'to' : to})
		if reason != '':
			message.getChildren()[0].getChildren()[0].addChild(name = 'reason')
			message.getChildren()[0].getChildren()[0].getChildren()[0].addData(reason)
		self.to_be_sent.append(message)

	def send_keepalive(self):
		# nothing received for the last foo seconds (60 secs by default)
		self.to_be_sent.append(' ')

	def process(self, timeout):
		if self.time_to_reconnect:
			if self.connected < 2:
				if time.time() > self.time_to_reconnect:
					self._reconnect()
			else:
				self.time_to_reconnect = None
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
				t = time.time()
				self.last_io = t
				self.last_sent.append(t)
			try:
				# do we want keepalives?
				if gajim.config.get_per('accounts', self.name, 														'keep_alives_enabled'):
					t = gajim.config.get_per('accounts', self.name,
													'keep_alive_every_foo_secs')
					# should we send keepalive?
					if time.time() > (self.last_io + t):
						self.send_keepalive()

				if self.connection:
					self.connection.Process(timeout)
			except:
				gajim.log.debug(_('A protocol error has occured:'))
				traceback.print_exc()
				self.connected = 0
				self.dispatch('STATUS', 'offline')
				if not self.connection:
					return
				try:
					self.connection.disconnect()
				except:
					gajim.log.debug(_('A protocol error has occured:'))
					traceback.print_exc()
				self.connection = None
# END Connection
