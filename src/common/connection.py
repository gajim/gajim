##	common/connection.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
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

import common.jabber

from common import gajim
from common import GnuPG
USE_GPG = GnuPG.USE_GPG

from common import i18n
_ = i18n._


STATUS_LIST = ['offline', 'connecting', 'online', 'away', 'xa', 'dnd', \
	'invisible']

distro_info = {
	'Arch Linux': '/etc/arch-release',\
	'Aurox Linux': '/etc/aurox-release',\
	'Conectiva Linux': '/etc/conectiva-release',\
	'Debian GNU/Linux': '/etc/debian_release',\
	'Debian GNU/Linux': '/etc/debian_version',\
	'Fedora Linux': '/etc/fedora-release',\
	'Gentoo Linux': '/etc/gentoo-release',\
	'Mandrake Linux': '/etc/mandrake-release',\
	'Slackware Linux': '/etc/slackware-release',\
	'Slackware Linux': '/etc/slackware-version',\
	'Solaris/Sparc': '/etc/release',\
	'Sun JDS': '/etc/sun-release',\
	'Novell SUSE Linux': '/etc/SuSE-release',\
	'PLD Linux': '/etc/pld-release',\
	'SUSE Linux': '/etc/SuSE-release',\
	'Yellow Dog Linux': '/etc/yellowdog-release',\
	# many distros use the /etc/redhat-release for compatibility
	# so Redhat is the last
	'Redhat Linux': '/etc/redhat-release'\
}

def get_os_info():
	if os.name =='nt':
		return 'windows'
	elif os.name =='posix':
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
				return output
		# lsb_release executable not available, so parse files
		for distro in distro_info:
			path_to_file = distro_info[distro]
			if os.path.exists(path_to_file):
				fd = open(path_to_file)
				text = fd.read().strip()
				fd.close()
				if path_to_file.endswith('version'):
					text = distro + ' ' + text
				return text
	return ''

class connection:
	"""connection"""
	def __init__(self, name = None):
		# dict of function to be calledfor each event
		self.handlers = {'ROSTER': [], 'WARNING': [], 'ERROR': [], 'STATUS': [], \
			'NOTIFY': [], 'MSG': [], 'MSGERROR': [], 'MSGSENT': [] , \
			'SUBSCRIBED': [], 'UNSUBSCRIBED': [], 'SUBSCRIBE': [], \
			'AGENT_INFO': [], 'AGENT_INFO_ITEMS': [], 'AGENT_INFO_INFO': [], \
			'QUIT': [], 'ACC_OK': [], 'MYVCARD': [], 'OS_INFO': [], 'VCARD': [], \
			'GC_MSG': [], 'GC_SUBJECT': [], 'BAD_PASSPHRASE': [], \
			'ROSTER_INFO': []}
		self.name = name
		self.connected = 0 # offline
		self.connection = None # Jabber.py instance
		self.gpg = None
		self.myVCardID = []
		if name:
			self.password = gajim.config.get_per('accounts', name, 'hostname')
			if USE_GPG:
				self.gpg = GnuPG.GnuPG()
				gajim.config.set('usegpg', True)
			else:
				gajim.config.set('usegpg', False)
	# END __init__

	def dispatch(self, event, data):
		if not event in self.handlers:
			return
		for handler in self.handlers[event]:
			handler(self.name, data)

	def _vCardCB(self, con, vc):
		"""Called when we recieve a vCard
		Parse the vCard and send it to plugins"""
		vcard = {'jid': vc.getFrom().getStripped()}
		if vc._getTag('vCard') == common.jabber.NS_VCARD:
			card = vc.getChildren()[0]
			for info in card.getChildren():
				if info.getChildren() == []:
					vcard[info.getName()] = info.getData()
				else:
					vcard[info.getName()] = {}
					for c in info.getChildren():
						 vcard[info.getName()][c.getName()] = c.getData()
			if vc.getID() in self.myVCardID:
				self.myVCardID.remove(vc.getID())
				self.dispatch('MYVCARD', vcard)
			else:
				self.dispatch('VCARD', vcard)

	def _messageCB(self, con, msg):
		"""Called when we recieve a message"""
		mtype = msg.getType()
		tim = msg.getTimestamp()
		tim = time.strptime(tim, '%Y%m%dT%H:%M:%S')
		msgtxt = msg.getBody()
		xtags = msg.getXNodes()
		encTag = None
		decmsg = ''
		for xtag in xtags:
			if xtag.getNamespace() == common.jabber.NS_XENCRYPTED:
				encTag = xtag
				break
		if encTag and USE_GPG:
			#decrypt
			encmsg = encTag.getData()
			
			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				decmsg = self.gpg.decrypt(encmsg, keyID)
		if decmsg:
			msgtxt = decmsg
		if mtype == 'error':
			self.dispatch('MSGERROR', (str(msg.getFrom()), \
				msg.getErrorCode(), msg.getError(), msgtxt, tim))
		elif mtype == 'groupchat':
			subject = msg.getSubject()
			if subject:
				self.dispatch('GC_SUBJECT', (str(msg.getFrom()), subject))
			else:
				self.dispatch('GC_MSG', (str(msg.getFrom()), msgtxt, tim))
		else:
			self.dispatch('MSG', (str(msg.getFrom()), msgtxt, tim))
	# END messageCB

	def _presenceCB(self, con, prs):
		"""Called when we recieve a presence"""
#		if prs.getXNode(common.jabber.NS_DELAY): return
		who = str(prs.getFrom())
		prio = prs.getPriority()
		if not prio:
			prio = 0
		ptype = prs.getType()
		if ptype == None: ptype = 'available'
		gajim.log.debug('PresenceCB : %s' % ptype)
		xtags = prs.getXNodes()
		sigTag = None
		keyID = ''
		status = prs.getStatus()
		for xtag in xtags:
			if xtag.getNamespace() == common.jabber.NS_XSIGNED:
				sigTag = xtag
				break
		if sigTag and USE_GPG:
			#verify
			sigmsg = sigTag.getData()
			keyID = self.gpg.verify(status, sigmsg)
		if ptype == 'available':
			show = prs.getShow()
			if not show:
				show = 'online'
			self.dispatch('NOTIFY', (prs.getFrom().getStripped(), show, status, \
				prs.getFrom().getResource(), prio, keyID, prs.getRole(), \
				prs.getAffiliation(), prs.getJid(), prs.getReason(), \
				prs.getActor(), prs.getStatusCode()))
		elif ptype == 'unavailable':
			self.dispatch('NOTIFY', (prs.getFrom().getStripped(), 'offline', \
				status, prs.getFrom().getResource(), prio, keyID, prs.getRole(), \
				prs.getAffiliation(), prs.getJid(), prs.getReason(), \
				prs.getActor(), prs.getStatusCode()))
		elif ptype == 'subscribe':
			gajim.log.debug('subscribe request from %s' % who)
			if gajim.config.get('alwaysauth') or who.find("@") <= 0:
				if self.connection:
					self.connection.send(common.jabber.Presence(who, 'subscribed'))
				if who.find("@") <= 0:
					self.dispatch('NOTIFY', (prs.getFrom().getStripped(), \
						'offline', 'offline', prs.getFrom().getResource(), prio, \
						keyID, None, None, None, None, None, None))
			else:
				if not status:
					status = _('I would like to add you to my roster.')
				self.dispatch('SUBSCRIBE', (who, status))
		elif ptype == 'subscribed':
			jid = prs.getFrom()
			self.dispatch('SUBSCRIBED', (jid.getStripped(), jid.getResource()))
			self.dispatch('UPDUSER', (jid.getStripped(), jid.getNode(), \
				['General']))
			#BE CAREFUL : no con.updateRosterItem() in a callback
			gajim.log.debug('we are now subscribed to %s' % who)
		elif ptype == 'unsubscribe':
			gajim.log.debug('unsubscribe request from %s' % who)
		elif ptype == 'unsubscribed':
			gajim.log.debug('we are now unsubscribed to %s' % who)
			self.dispatch('UNSUBSCRIBED', prs.getFrom().getStripped())
		elif ptype == 'error':
			errmsg = prs.getError()
			errcode = prs.getErrorCode()
			if errcode == '400': #Bad Request: JID Malformed or Private message when not allowed
				pass
			elif errcode == '401': #No Password Provided
				pass
			elif errcode == '403':	#forbidden :	User is Banned
											#					Unauthorized Subject Change
											#					Attempt by Mere Member to Invite Others to a Members-Only Room
											#					Configuration Access to Non-Owner
											#					Attempt by Non-Owner to Modify Owner List
											#					Attempt by Non-Owner to Modify Admin List
											#					Destroy Request Submitted by Non-Owner
				pass
			elif errcode == '404':	#item not found :	Room Does Not Exist
				pass
			elif errcode == '405':	#Not allowed :	Attempt to Kick Moderator, Admin, or Owner
											#					Attempt to Ban an Admin or Owner
											#					Attempt to Revoke Voice from an Admin, Owner, or User with a Higher Affiliation
											#					Attempt to Revoke Moderator Privileges from an Admin or Owner
				pass
			elif errcode == '407':	#registration required :	User Is Not on Member List
											#									
				pass
			elif errcode == '409':	#conflict :	Nick Conflict
				self.dispatch('ERROR', errmsg)
			else:
				self.dispatch('NOTIFY', (prs.getFrom().getStripped(), 'error', \
					errmsg, prs.getFrom().getResource(), prio, keyID, None, None, \
					None,  None, None, None))
	# END presenceCB

	def _disconnectedCB(self, con):
		"""Called when we are disconnected"""
		gajim.log.debug('disconnectedCB')
		if self.connection:
			self.connected = 0
			self.dispatch('STATUS', 'offline')
	# END disconenctedCB

	def _rosterSetCB(self, con, iq_obj):
		for item in iq_obj.getQueryNode().getChildren():
			jid  = item.getAttr('jid')
			name = item.getAttr('name')
			sub  = item.getAttr('subscription')
			ask  = item.getAttr('ask')
			groups = []
			for group in item.getTags('group'):
				groups.append(group.getData())
			self.dispatch('ROSTER_INFO', (jid, name, sub, ask, groups))

	def _BrowseResultCB(self, con, iq_obj):
		identities, features, items = [], [], []
		q = iq_obj.getTag('service')
		if not q:
			return identities, features, items
		attr = {}
		for key in q.attrs:
			attr[key.encode('utf8')] = q.attrs[key].encode('utf8')
		identities = [attr]
		for node in q.kids:
			if node.getName() == 'ns':
				features.append(node.getData())
			else:
				infos = {}
				for key in node.attrs:
					infos[key.encode('utf8')] = node.attrs[key].encode('utf8')
				infos['category'] = node.getName()
				items.append(infos)
		jid = str(iq_obj.getFrom())
		self.dispatch('AGENT_INFO', (jid, identities, features, items))

	def _DiscoverItemsCB(self, con, iq_obj):
		qp = iq_obj.getQueryPayload()
		items = []
		if not qp:
			qp = []
		for i in qp:
			attr = {}
			for key in i.attrs:
				attr[key.encode('utf8')] = i.attrs[key].encode('utf8')
			items.append(attr)
		jid = str(iq_obj.getFrom())
		self.dispatch('AGENT_INFO_ITEMS', (jid, items))

	def _DiscoverInfoErrorCB(self, con, iq_obj):
		jid = str(iq_obj.getFrom())
		con.browseAgents(jid)

	def _DiscoverInfoCB(self, con, iq_obj):
		# According to JEP-0030:
		# For identity: category, name is mandatory, type is optional.
		# For feature: var is mandatory
		identities, features = [], []
		qp = iq_obj.getQueryPayload()
		if not qp:
			qp = []
		for i in qp:
			if i.getName() == 'identity':
				attr = {}
				for key in i.attrs:
					attr[key.encode('utf8')] = i.attrs[key].encode('utf8')
				identities.append(attr)
			elif i.getName() == 'feature':
				features.append(i.getAttr('var'))
		jid = str(iq_obj.getFrom())
		if not identities:
			self.connection.browseAgents(jid)
		else:
			self.dispatch('AGENT_INFO_INFO', (jid, identities, features))
			self.connection.discoverItems(jid)

	def _VersionCB(self, con, iq_obj):
		f = iq_obj.getFrom()
		iq_obj.setFrom(iq_obj.getTo())
		iq_obj.setTo(f)
		iq_obj.setType('result')
		qp = iq_obj.getTag('query')
		qp.insertTag('name').insertData('Gajim')
		qp.insertTag('version').insertData(version.version)
		no_send_os = gajim.config.get('do_not_send_os_info')
		if not no_send_os:
			qp.insertTag('os').insertData(get_os_info())
		self.connection.send(iq_obj)

	def _VersionResultCB(self, con, iq_obj):
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
		self.dispatch('OS_INFO', (jid, client_info, os_info))

	def connect(self):
		"""Connect and authentificate to the Jabber server"""
		self.connected = 1
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		resource = gajim.config.get_per('accounts', self.name, 'resource')

		#create connexion if it doesn't already existe
		if not self.connection:
			if gajim.config.get_per('accounts', self.name, 'use_proxy'):
				proxy = {'host': gajim.config.get_per('accounts', self.name, \
					'proxyhost')}
				proxy['port'] = gajim.config.get_per('accounts', self.name, \
					'proxyport')
			else:
				proxy = None
			if gajim.log:
				self.connection = common.jabber.Client(host = hostname, debug = [],\
				log = sys.stderr, connection=common.xmlstream.TCP, port=5222, \
				proxy = proxy)
			else:
				con = common.jabber.Client(host = hostname, debug = [], log = None,\
				connection=common.xmlstream.TCP, port=5222, proxy = proxy)
				#debug = [common.jabber.DBG_ALWAYS], log = sys.stderr, \
				#connection=common.xmlstream.TCP_SSL, port=5223, proxy = proxy)
			self.connection.setDisconnectHandler(self.disconnectedCB)
			self.connection.registerHandler('message', self.messageCB)
			self.connection.registerHandler('presence', self.presenceCB)
			self.connection.registerHandler('iq',self.vCardCB,'result')
			self.connection.registerHandler('iq',self.rosterSetCB,'set', \
				common.jabber.NS_ROSTER)
			self.connection.registerHandler('iq',self.BrowseResultCB,'result', \
				common.jabber.NS_BROWSE)
			self.connection.registerHandler('iq',self.DiscoverItemsCB,'result', \
				common.jabber.NS_P_DISC_ITEMS)
			self.connection.registerHandler('iq',self.DiscoverInfoCB,'result', \
				common.jabber.NS_P_DISC_INFO)
			self.connection.registerHandler('iq',self.DiscoverInfoErrorCB,'error',\
				common.jabber.NS_P_DISC_INFO)
			self.connection.registerHandler('iq',self.VersionCB,'get', \
				common.jabber.NS_VERSION)
			self.connection.registerHandler('iq',self.VersionResultCB,'result', \
				common.jabber.NS_VERSION)
		try:
			self.connection.connect()
		except:
			gajim.log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', _('Couldn\'t connect to %s') \
				% hostname)
			self.connected = 0
			return -1

		gajim.log.debug('Connected to server')

		if self.connection.auth(self.name, self.password, resource):
			self.connection.requestRoster()
			roster = self.connection.getRoster().getRaw()
			if not roster :
				roster = {}
			self.dispatch('ROSTER', (0, roster))
			self.connected = 2
			return 0
		else:
			log.debug('Couldn\'t authentificate to %s' % hostname)
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', _('Authentification failed with %s, check your login and password') % hostname)
			self.connected = 0
			return -1
# END connect

	def register_handler(self, event, funtion):
		if event in self.handlers:
			self.handlers[event].append(function)

	def unregister_handler(self, event, funtion):
		if event in self.handlers:
			if function in self.handlers[event]:
				self.handlers[event].remove(function)

	def quit(self, kill_core):
		if kill_core:
			if self.connected > 1:
				self.connected = 0
				self.connection.disconnect('Disconnected')
			self.dispatch('QUIT', ())
			return

	def ask_roster(self):
		roster = {}
		if self.connection:
			roster = self.connection.getRoster().getRaw()
		return roster
	
	def change_status(self, status, msg):
		if not status in STATUS_LIST:
			return -1
		if not msg:
			msg = status
		signed = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG:
			signed = self.gpg.sign(msg, keyID)
			if signed == 'BAD_PASSPHRASE':
				signed = ''
				if self.connected < 2:
					self.dispatch('BAD_PASSPHRASE', ())
		if (status != 'offline') and (self.connected == 0):
			self.connect()
			if self.connected == 2:
				self.connected = STATUS_LIST.index(status)
				#send our presence
				ptype = 'available'
				if status == 'invisible':
					ptype = 'invisible'
				prio = gajim.config.get_per('accounts', self.name, 'priority')
				self.connection.sendPresence(ptype, prio, status, msg, signed)
				self.dispatch('STATUS', status)
				#ask our VCard
				iq = common.jabber.Iq(type='get')
				iq._setTag('vCard', common.jabber.NS_VCARD)
				id = con.getAnID()
				iq.setID(id)
				con.send(iq)
				self.myVCardID.append(id)
		elif (status == 'offline') and self.connected:
			self.connected = 0
			self.connection.disconnect(msg)
			self.dispatch('STATUS', 'offline')
		elif status != 'offline' and self.connected:
			self.connected = STATUS_LIST.index(status)
			ptype = 'available'
			if status == 'invisible':
				ptype = 'invisible'
			prio = gajim.config.get_per('accounts', self.name, 'priority')
			self.connection.sendPresence(ptype, prio, status, msg, signed)
			self.dispatch('STATUS', status)

	def send_message(jid, msg, keyID):
		if not self.connection:
			return
		msgtxt = msg
		msgenc = ''
		if keyID and USE_GPG:
			#encrypt
			msgenc = self.gpg.encrypt(msg, keyID)
			if msgenc: msgtxt = _('[this message is encrypted]')
		msg_iq = common.jabber.Message(to = jid, body = msgtxt, type = 'chat')
		if msgenc:
			msg_iq.setX(common.jabber.NS_XENCRYPTED).insertData(msgenc)
		self.connection.send(msg_iq)
		self.dispatch('MSGSENT', (jid, msg, keyID))

	def request_subscription(self, jid, msg):
		if not self.connection:
			return
		gajim.log.debug('subscription request for %s' % jid)
		pres = common.jabber.Presence(jid, 'subscribe')
		if not msg:
			msg = _('I would like to add you to my roster.')
		pres.setStatus(msg)
		self.connection.send(pres)

	def send_authorization(self, jid):
		if not self.connection:
			return
		self.connection.send(common.jabber.Presence(jid, 'subscribed'))

	def refuse_authorization(self, jid):
		if not self.connection:
			return
		self.connection.send(common.jabber.Presence(jid, 'unsubscribed'))

	def unsubscribe(self, jid):
		if not self.connection:
			return
		delauth = gajim.config.get('delauth')
		delroster = gajim.config.get('delroster')
		if delauth:
			self.connection.send(common.jabber.Presence(jid, 'unsubscribe'))
		if delroster:
			self.connection.removeRosterItem(jid)

	def unsubscribe_agent(self, agent):
		if not self.connection:
			return
		self.connection.removeRosterItem(agent)
		self.connection.requestRegInfo(agent)
		agent_info = self.connection.getRegInfo()
		if not agent_info:
			return
		key = agent_info['key']
		iq = common.jabber.Iq(to=agent, type='set')
		q = iq.setQuery(common.jabber.NS_REGISTER)
		q.insertTag('remove')
		q.insertTag('key').insertData(key)
		id = self.connection.getAnID()
		iq.setID(id)
		self.connection.send(iq)
		self.dispatch('AGENT_REMOVED', agent)

	def update_user(self, jid, name, groups):
		if self.connection:
			self.connection.updateRosterItem(jid=jid, name=name, groups=groups)

	def request_agents(self, jid):
		if self.connection:
			self.connection.discoverInfo(jid)

	def ask_register_agent_info(self, agent):
		if not self.connection:
			return None
		self.connection.requestRegInfo(agent)
		agent_info = self.connection.getRegInfo()
		return agent_info

	def register_agent(self, info):
		if not self.connection:
			return
		self.connection.sendRegInfo(info)

	def new_account(self, hostname, login, password, name, resource, prio, \
		use_proxy, proxyhost, proxyport):
		# If a connection already exist we cannot create a new account
		if self.connection:
			return
		if use_proxy:
			proxy = {'host': proxyhost, 'port': proxyport}
		else:
			proxy = None
		c = common.jabber.Client(host = hostname, debug = [], \
			log = None, proxy = proxy)
		try:
			c.connect()
		except:
			gajim.log.debug('Couldn\'t connect to %s' % hostname)
			self.dispatch('ERROR', _('Couldn\'t connect to ') + hostname)
			return 0
		else:
			gajim.log.debug(_('Connected to server'))
			c.requestRegInfo()
			req = c.getRegInfo()
			c.setRegInfo( 'username', login)
			c.setRegInfo( 'password', password)
			if not c.sendRegInfo():
				self.dispatch('ERROR', _('Error: ') + c.lastErr)
			else:
				self.name = name
				self.connected = 0
				self.password = ''
				if USE_GPG:
					self.gpg = GnuPG.GnuPG()
					gajim.config.set('usegpg', True)
				else:
					gajim.config.set('usegpg', False)
				self.dispatch('ACC_OK', (hostname, login, password, name, \
					resource, prio, use_proxy, proxyhost, proxyport))

	def account_changed(self, new_name):
		self.name = new_name

	def request_os_info(self, jid, resource):
		if not self.connection:
			return
		iq = common.jabber.Iq(to=jid + '/' + resource, type = 'get', \
			query = common.jabber.NS_VERSION)
		iq.setID(self.connection.getAnID())
		self.connection.send(iq)

	def request_vcard(self, jid):
		if not self.connection:
			return
		iq = common.jabber.Iq(to = jid, type = 'get')
		iq._setTag('vCard', common.jabber.NS_VCARD)
		iq.setID(self.connection.getAnID())
		self.connection.send(iq)
			#('VCARD', {entry1: data, entry2: {entry21: data, ...}, ...})
	
	def send_vcard(self, vcard):
		if not self.connection:
			return
		iq = common.jabber.Iq(type = 'set')
		iq.setID(self.connection.getAnID())
		iq2 = iq._setTag('vCard', common.jabber.NS_VCARD)
		for i in vcard.keys():
			if i != 'jid':
				if type(vcard[i]) == type({}):
					iq3 = iq2.insertTag(i)
					for j in vcard[i].keys():
						iq3.insertTag(j).putData(vcard[i][j])
				else:
					iq2.insertTag(i).putData(vcard[i])
		self.connection.send(iq)

	def send_agent_status(self, agent, ptype):
		if not self.connection:
			return
		if not ptype:
			ptype = 'available';
		p = common.jabber.Presence(to = agent, type = ptype)
		self.connection.send(p)

	def join_gc(self, nick, room, server, passwd):
		if not self.connection:
			return
		p = common.jabber.Presence(to = '%s@%s/%s' % (room, server, password))
		self.connection.send(p)

	def send_gc_message(self, jid, msg):
		if not self.connection:
			return
		msg_iq = common.jabber.Message(jid, msg)
		msg_iq.setType('groupchat')
		self.connection.send(msg_iq)
		self.dispatch('MSGSENT', (jid, msg))

	def send_gc_subject(self, jid, subject):
		if not self.connection:
			return
		msg_iq = common.jabber.Message(jid)
		msg_iq.setType('groupchat')
		msg_iq.setSubject(subject)
		self.connection.send(msg_iq)

	def send_gc_status(self, nick, jid, show, status):
		if not self.connection:
			return
		if show == 'offline':
			ptype = 'unavailable'
			show = None
		else:
			ptype = 'available'
		self.connection.send(common.jabber.Presence(to = '%s/%s' % (jid, nick), \
			type = ptype, show = show, status = status))

	def gc_set_role(self, room_jid, nick, role):
		if not self.connection:
			return
		iq = common.jabber.Iq(type = 'set', to = room_jid)
		item = iq.setQuery(common.jabber.NS_P_MUC_ADMIN).insertTag('item')
		item.putAttr('nick', nick)
		item.putAttr('role', role)
		id = self.connection.getAnID()
		iq.setID(id)
		self.connection.send(iq)

	def gc_set_affiliation(self, room_jid, jid, affiliation):
		if not self.connection:
			return
		iq = common.jabber.Iq(type = 'set', to = room_jid)
		item = iq.setQuery(common.jabber.NS_P_MUC_ADMIN).insertTag('item')
		item.putAttr('jid', jid)
		item.putAttr('affiliation', affiliation)
		id = self.connection.getAnID()
		iq.setID(id)
		self.connection.send(iq)

	def gpg_passphrase(self, passphrase):
		if USE_GPG:
			self.gpg.passphrase = passphrase

	def ask_gpg_secrete_keys(self):
		if USE_GPG:
			keys = self.gpg.get_secret_keys()
			return keys
		return None

	def change_password(self, password, username):
		if not self.connection:
			return
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		iq = common.jabber.Iq(type = 'set', to = hostname)
		q = iq.setQuery(common.jabber.NS_REGISTER)
		q.insertTag('username').insertData(username)
		q.insertTag('password').insertData(password)
		id = self.connection.getAnID()
		iq.setID(id)
		self.connection.send(iq)

	def process(self):
		if not self.connection:
			return
		if self.connected:
			self.connection.process(1)
# END GajimCore
