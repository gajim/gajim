#!/usr/bin/env python
##	core/core.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@snarc.org>
##
##	Copyright (C) 2003 Gajim Team
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

import sys, os, time, string, logging

import common.hub, common.optparser
import common.jabber
import socket, select, pickle
import GnuPGInterface


from common import i18n
_ = i18n._

log = logging.getLogger('core.core')
log.setLevel(logging.DEBUG)

CONFPATH = "~/.gajim/config"
LOGPATH = os.path.expanduser("~/.gajim/logs/")

def XMLescape(txt):
	"Escape XML entities"
	txt = txt.replace("&", "&amp;")
	txt = txt.replace("<", "&lt;")
	txt = txt.replace(">", "&gt;")
	return txt

def XMLunescape(txt):
	"Unescape XML entities"
	txt = txt.replace("&gt;", ">")
	txt = txt.replace("&lt;", "<")
	txt = txt.replace("&amp;", "&")
	return txt

class  MyGnuPG(GnuPGInterface.GnuPG):
	def __init__(self):
		GnuPGInterface.GnuPG.__init__(self)
		self.setup_my_options()

	def setup_my_options(self):
		self.options.armor = 1
		self.options.meta_interactive = 0
		self.options.extra_args.append('--no-secmem-warning')

	def _read_response(self, child_stdout):
		# Internal method: reads all the output from GPG, taking notice
		# only of lines that begin with the magic [GNUPG:] prefix.
		# (See doc/DETAILS in the GPG distribution for info on GPG's
		# output when --status-fd is specified.)
		#
		# Returns a dictionary, mapping GPG's keywords to the arguments
		# for that keyword.

		resp = {}
		while 1:
			line = child_stdout.readline()
			if line == "": break
			line = string.rstrip( line )
			if line[0:9] == '[GNUPG:] ':
				# Chop off the prefix
				line = line[9:]
				L = string.split(line, None, 1)
				keyword = L[0]
				if len(L) > 1:
					resp[ keyword ] = L[1]
				else:
					resp[ keyword ] = ""
		return resp

	def encrypt(self, string, recipients):
		self.options.recipients = recipients   # a list!

		proc = self.run(['--encrypt'], create_fhs=['stdin', 'stdout'])
		proc.handles['stdin'].write(string)
		proc.handles['stdin'].close()

		output = proc.handles['stdout'].read()
		proc.handles['stdout'].close()

		try: proc.wait()
		except IOError: pass
		return self.stripHeaderFooter(output)

	def decrypt(self, string, keyID):
		proc = self.run(['--decrypt', '-q', '-u %s'%keyID], create_fhs=['stdin', 'stdout', 'status'])
		enc = self.addHeaderFooter(string, 'MESSAGE')
		proc.handles['stdin'].write(enc)
		proc.handles['stdin'].close()
		
		output = proc.handles['stdout'].read()
		proc.handles['stdout'].close()

		resp = proc.handles['status'].read()
		proc.handles['status'].close()

		try: proc.wait()
		except IOError: pass
		return output
	
	def sign(self, string, keyID):
		proc = self.run(['-b', '-u %s'%keyID], create_fhs=['stdin', 'stdout', 'status', 'stderr'])
		proc.handles['stdin'].write(string)
		proc.handles['stdin'].close()

		output = proc.handles['stdout'].read()
		proc.handles['stdout'].close()
		proc.handles['stderr'].close()

		stat = proc.handles['status']
		resp = self._read_response(stat)
		proc.handles['status'].close()

		try: proc.wait()
		except IOError: pass
		if resp.has_key('BAD_PASSPHRASE'):
			return 'BAD_PASSPHRASE'
		elif resp.has_key('GOOD_PASSPHRASE'):
			return self.stripHeaderFooter(output)

	def verify(self, str, sign):
		file = open('gpg_data', 'w+r')
		os.remove('gpg_data')
		fd = file.fileno()
		file.write(str)
		file.seek(0)
		
		proc = self.run(['--verify', '--enable-special-filenames', '-', '-&%s'%fd], create_fhs=['stdin', 'status', 'stderr'])

		file.close
		sign = self.addHeaderFooter(sign, 'SIGNATURE')
		proc.handles['stdin'].write(sign)
		proc.handles['stdin'].close()
		proc.handles['stderr'].close()

		stat = proc.handles['status']
		resp = self._read_response(stat)
		proc.handles['status'].close()

		try: proc.wait()
		except IOError: pass

		keyid = ''
		if resp.has_key('GOODSIG'):
			keyid = string.split(resp['GOODSIG'])[0]
		return keyid

	def stripHeaderFooter(self, data):
		"""Remove header and footer from data"""
		lines = string.split(data, '\n')
		while lines[0] != '':
			lines.remove(lines[0])
		while lines[0] == '':
			lines.remove(lines[0])
		i = 0
		for line in lines:
			if line:
				if line[0] == '-': break
			i = i+1
		line = string.join(lines[0:i], '\n')
		return line

	def addHeaderFooter(self, data, type):
		"""Add header and footer from data"""
		out = "-----BEGIN PGP %s-----\n" % type
		out = out + "Version: PGP\n"
		out = out + "\n"
		out = out + data + "\n"
		out = out + "-----END PGP %s-----\n" % type
		return out

class GajimCore:
	"""Core"""
	def __init__(self, mode='client'):
		self.mode = mode
		self.log = 0
		self.init_cfg_file()
		if mode == 'client':
			self.data = ''
			self.connect_core()
		self.hub = common.hub.GajimHub()
		if self.log:
			log.setLevel(logging.DEBUG)
		else:
			log.setLevel(None)
		if mode == 'server':
			self.connected = {}
			#connexions {con: name, ...}
			self.connexions = {}
			self.gpg = {}
			for a in self.accounts:
				self.connected[a] = 0 #0:offline, 1:online, 2:away,
											 #3:xa, 4:dnd, 5:invisible
				self.gpg[a] = MyGnuPG()
			self.myVCardID = []
			self.loadPlugins(self.cfgParser.tab['Core']['modules'])
		else:
			self.loadPlugins(self.cfgParser.tab['Core_client']['modules'])
	# END __init__

	def loadPlugins(self, moduleStr):
		"""Load defaults plugins : plugins in 'modules' option of Core section 
		in ConfFile and register them to the hub"""
		if moduleStr:
			mods = string.split (moduleStr, ' ')

			for mod in mods:
				try:
					modObj = self.hub.newPlugin(mod)
				except:
					print _("The plugin %s cannot be launched" % mod)
				if not modObj:
					print _("The plugin %s is already launched" % mod)
					return
				modObj.load()
	# END loadPLugins

	def connect_core(self):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect((self.cfgParser.tab['Core_client']['host'], \
			self.cfgParser.tab['Core_client']['port']))
	# END connect_core

	def init_cfg_file(self):
		"""Initialize configuration file"""
		if self.mode == 'server':
			default_tab = {'Profile': {'accounts': '', 'log': 0}, 'Core': \
				{'delauth': 1, 'alwaysauth': 0, 'modules': 'logger gtkgui', \
				'delroster': 1}}
		else:
			default_tab = {'Profile': {'log': 0}, 'Core_client': {'host': \
			'localhost', 'port': 8255, 'modules': 'gtkgui'}}
		fname = os.path.expanduser(CONFPATH)
		reps = string.split(fname, '/')
		del reps[0]
		path = ''
		while len(reps) > 1:
			path = path + '/' + reps[0]
			del reps[0]
			try:
				os.stat(os.path.expanduser(path))
			except OSError:
				try:
					os.mkdir(os.path.expanduser(path))
				except:
					print _("Can't create %s") % path
					sys.exit
		try:
			os.stat(fname)
		except:
			print _("creating %s") % fname
			fic = open(fname, "w")
			fic.close()
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.parse()
		for part in default_tab.keys():
			if not self.cfgParser.tab.has_key(part):
				self.cfgParser.tab[part] = {}
				self.cfgParser.writeCfgFile()
			for option in default_tab[part].keys():
				if not self.cfgParser.tab[part].has_key(option):
					self.cfgParser.tab[part][option] = default_tab[part][option]
				self.cfgParser.writeCfgFile()
		self.parse()
	# END init_cfg_file

	def parse(self):
		"""Parse configuratoin file and create self.accounts"""
		self.cfgParser.parseCfgFile()
		if self.cfgParser.tab.has_key('Profile'):
			if self.cfgParser.tab['Profile'].has_key('log'):
				self.log = self.cfgParser.tab['Profile']['log']
			if self.mode == 'server':
				self.accounts = {}
				if self.cfgParser.tab['Profile'].has_key('accounts'):
					accts = string.split(self.cfgParser.tab['Profile']['accounts'], ' ')
					if accts == ['']:
						accts = []
					for a in accts:
						self.accounts[a] = self.cfgParser.tab[a]

	def vCardCB(self, con, vc):
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
				self.hub.sendPlugin('MYVCARD', self.connexions[con], vcard)
			else:
				self.hub.sendPlugin('VCARD', self.connexions[con], vcard)

	def messageCB(self, con, msg):
		"""Called when we recieve a message"""
		typ = msg.getType()
		tim = msg.getTimestamp()
		tim = time.strptime(tim, "%Y%m%dT%H:%M:%S")
		msgtxt = msg.getBody()
		xtags = msg.getXNodes()
		encTag = None
		decmsg = ''
		for xtag in xtags:
			if xtag.getNamespace() == common.jabber.NS_XENCRYPTED:
				encTag = xtag
				break
		if encTag:
			#decrypt
			encmsg = encTag.getData()
			keyID = ''
			if self.cfgParser.tab[self.connexions[con]].has_key("keyid"):
				keyID = self.cfgParser.tab[self.connexions[con]]["keyid"]
			if keyID:
				decmsg = self.gpg[self.connexions[con]].decrypt(encmsg, keyID)
		if decmsg:
			msgtxt = decmsg
		if typ == 'error':
			self.hub.sendPlugin('MSGERROR', self.connexions[con], \
				(str(msg.getFrom()), msg.getErrorCode(), msg.getError(), msgtxt, tim))
		elif typ == 'groupchat':
			self.hub.sendPlugin('GC_MSG', self.connexions[con], \
				(str(msg.getFrom()), msgtxt, tim))
		else:
			self.hub.sendPlugin('MSG', self.connexions[con], \
				(str(msg.getFrom()), msgtxt, tim))
	# END messageCB

	def presenceCB(self, con, prs):
		"""Called when we recieve a presence"""
		who = str(prs.getFrom())
		prio = prs.getPriority()
		if not prio:
			prio = 0
		typ = prs.getType()
		if typ == None: typ = 'available'
		log.debug("PresenceCB : %s" % typ)
		xtags = prs.getXNodes()
		sigTag = None
		keyID = ''
		status = prs.getStatus()
		for xtag in xtags:
			if xtag.getNamespace() == common.jabber.NS_XSIGNED:
				sigTag = xtag
				break
		if sigTag:
			#verify
			sigmsg = sigTag.getData()
			keyID = self.gpg[self.connexions[con]].verify(status, sigmsg)
		if typ == 'available':
			show = prs.getShow()
			if not show:
				show = 'online'
			self.hub.sendPlugin('NOTIFY', self.connexions[con], \
				(prs.getFrom().getStripped(), show, status, \
				prs.getFrom().getResource(), prio, keyID, prs.getRole(), \
				prs.getAffiliation(), prs.getJid(), prs.getReason(), \
				prs.getActor(), prs.getStatusCode()))
		elif typ == 'unavailable':
			self.hub.sendPlugin('NOTIFY', self.connexions[con], \
				(prs.getFrom().getStripped(), 'offline', status, \
				prs.getFrom().getResource(), prio, keyID, prs.getRole(), \
				prs.getAffiliation(), prs.getJid(), prs.getReason(), \
				prs.getActor(), prs.getStatusCode()))
		elif typ == 'subscribe':
			log.debug("subscribe request from %s" % who)
			if self.cfgParser.Core['alwaysauth'] == 1 or \
				string.find(who, "@") <= 0:
				con.send(common.jabber.Presence(who, 'subscribed'))
				if string.find(who, "@") <= 0:
					self.hub.sendPlugin('NOTIFY', self.connexions[con], \
						(prs.getFrom().getStripped(), 'offline', 'offline', \
						prs.getFrom().getResource(), prio, keyID, None, None, None, \
						None, None, None))
			else:
				if not status:
					status = _("I would like to add you to my roster.")
				self.hub.sendPlugin('SUBSCRIBE', self.connexions[con], (who, \
					status))
		elif typ == 'subscribed':
			jid = prs.getFrom()
			self.hub.sendPlugin('SUBSCRIBED', self.connexions[con],\
				(jid.getStripped(), jid.getNode(), jid.getResource()))
			self.hub.queueIn.put(('UPDUSER', self.connexions[con], \
				(jid.getStripped(), jid.getNode(), ['general'])))
			#BE CAREFUL : no con.updateRosterItem() in a callback
			log.debug("we are now subscribed to %s" % who)
		elif typ == 'unsubscribe':
			log.debug("unsubscribe request from %s" % who)
		elif typ == 'unsubscribed':
			log.debug("we are now unsubscribed to %s" % who)
			self.hub.sendPlugin('UNSUBSCRIBED', self.connexions[con], \
				prs.getFrom().getStripped())
		elif typ == 'error':
			errmsg = prs.getError()
			errcode = prs.getErrorCode()
			if errcode == '400': #Bad Request : JID Malformed or Private message when not allowed
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
				self.hub.sendPlugin('WARNING', None, errmsg)
			else:
				self.hub.sendPlugin('NOTIFY', self.connexions[con], \
					(prs.getFrom().getStripped(), 'error', errmsg, \
					prs.getFrom().getResource(), prio, keyID, None, None, None, \
					None, None, None))
	# END presenceCB

	def disconnectedCB(self, con):
		"""Called when we are disconnected"""
		log.debug("disconnectedCB")
		if self.connexions.has_key(con):
			self.connected[self.connexions[con]] = 0
			self.hub.sendPlugin('STATUS', self.connexions[con], 'offline')
	# END disconenctedCB

	def connect(self, account):
		"""Connect and authentificate to the Jabber server"""
		hostname = self.cfgParser.tab[account]["hostname"]
		name = self.cfgParser.tab[account]["name"]
		password = self.cfgParser.tab[account]["password"]
		ressource = self.cfgParser.tab[account]["ressource"]

		#create connexion if it doesn't already existe
		con = None
		for conn in self.connexions:
			if self.connexions[conn] == account:
				con = conn
		if not con:
			if self.cfgParser.tab[account]["use_proxy"]:
				proxy = {"host":self.cfgParser.tab[account]["proxyhost"]}
				proxy["port"] = self.cfgParser.tab[account]["proxyport"]
			else:
				proxy = None
			if self.log:
				con = common.jabber.Client(host = hostname, debug = [], \
				log = sys.stderr, connection=common.xmlstream.TCP, port=5222, \
				proxy = proxy)
			else:
				con = common.jabber.Client(host = hostname, debug = [], log = None,\
				connection=common.xmlstream.TCP, port=5222, proxy = proxy)
				#debug = [common.jabber.DBG_ALWAYS], log = sys.stderr, \
				#connection=common.xmlstream.TCP_SSL, port=5223, proxy = proxy)
			con.setDisconnectHandler(self.disconnectedCB)
			con.registerHandler('message', self.messageCB)
			con.registerHandler('presence', self.presenceCB)
			con.registerHandler('iq',self.vCardCB,'result')#common.jabber.NS_VCARD)
		try:
			con.connect()
		except IOError, e:
			log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.hub.sendPlugin('STATUS', account, 'offline')
			self.hub.sendPlugin('WARNING', None, _("Couldn't connect to %s") \
				% hostname)
			return 0
		except common.xmlstream.socket.error, e:
			log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.hub.sendPlugin('STATUS', account, 'offline')
			self.hub.sendPlugin('WARNING', None, _("Couldn't connect to %s : %s") \
				% (hostname, e))
			return 0
		except common.xmlstream.error, e:
			log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.hub.sendPlugin('STATUS', account, 'offline')
			self.hub.sendPlugin('WARNING', None, _("Couldn't connect to %s : %s") \
				% (hostname, e))
			return 0
		except:
			sys.exc_info()[1][0]
			sys.exc_info()[1][1]
		else:
			log.debug("Connected to server")

			#BUG in jabberpy library : if hostname is wrong : "boucle"
			if con.auth(name, password, ressource):
				self.connexions[con] = account
				con.requestRoster()
				roster = con.getRoster().getRaw()
				if not roster :
					roster = {}
				self.hub.sendPlugin('ROSTER', account, (0, roster))
				self.connected[account] = 1
				return con
			else:
				log.debug("Couldn't authentificate to %s" % hostname)
				self.hub.sendPlugin('STATUS', account, 'offline')
				self.hub.sendPlugin('WARNING', None, \
					_("Authentification failed with %s, check your login and password") % hostname)
				return 0
	# END connect

	def send_to_socket(self, ev, sock):
		evp = pickle.dumps(ev)
		sock.send('<'+XMLescape(evp)+'>')

	def unparse_socket(self):
		list_ev = []
		while self.data:
			deb = self.data.find('<')
			if deb == -1:
				break
			end = self.data.find('>', deb)
			if end == -1:
				break
			list_ev.append(pickle.loads(self.data[deb+1:end]))
			self.data = self.data[end+1:]
		return list_ev

	def request_infos(self, account, con, jid):
		identities, features = con.discoverInfo(jid)
		if not identities:
			identities, features, items = con.browseAgent(jid)
		else:
			items = con.discoverItems(jid)
		self.hub.sendPlugin('AGENT_INFO', account, (jid, identities, features, items))
		for item in items:
			self.request_infos(account, con, item['jid'])

	def read_queue(self):
		while self.hub.queueIn.empty() == 0:
			ev = self.hub.queueIn.get()
			if self.mode == 'client':
				#('REG_MESSAGE', module, list_message)
				if ev[0] == 'REG_MESSAGE':
					for msg in ev[2]:
						self.hub.register(ev[1], msg)
#				ready_to_read, ready_to_write, in_error = select.select(
#					[], [self.socket], [])
				self.send_to_socket(ev, self.socket)
				return 0
			if ev[1] and (ev[1] in self.connexions.values()):
				for con in self.connexions.keys():
					if ev[1] == self.connexions[con]:
						break
			else:
				con = None
			#('QUIT', None, (plugin, kill_core ?))   kill core : 0 or 1
			if ev[0] == 'QUIT':
				self.hub.unregister(ev[2][0])
				if ev[2][1]:
					for con in self.connexions.keys():
						if self.connected[self.connexions[con]]:
							self.connected[self.connexions[con]] = 0
							con.disconnect()
					self.hub.sendPlugin('QUIT', None, ())
					return 1
			#('ASK_ROSTER', account, queue_for_response)
			elif ev[0] == 'ASK_ROSTER':
				roster = {}
				if con:
					roster = con.getRoster().getRaw()
				self.hub.sendPlugin('ROSTER', ev[1], (self.connected[ev[1]], \
					roster), ev[2])
			#('ASK_CONFIG', account, (who_ask, section, default_config))
			elif ev[0] == 'ASK_CONFIG':
				if ev[2][1] == 'accounts':
					self.hub.sendPlugin('CONFIG', None, (ev[2][0], self.accounts))
				else:
					if self.cfgParser.tab.has_key(ev[2][1]):
						config = self.cfgParser.__getattr__(ev[2][1])
						for item in ev[2][2].keys():
							if not config.has_key(item):
								config[item] = ev[2][2][item]
						self.hub.sendPlugin('CONFIG', None, (ev[2][0], config))
					else:
						self.cfgParser.tab[ev[2][1]] = ev[2][2]
						self.cfgParser.writeCfgFile()
						self.hub.sendPlugin('CONFIG', None, (ev[2][0], ev[2][2]))
			#('CONFIG', account, (section, config))
			elif ev[0] == 'CONFIG':
				if ev[2][0] == 'accounts':
					#Remove all old accounts
					accts = string.split(self.cfgParser.tab\
						['Profile']['accounts'], ' ')
					if accts == ['']:
						accts = []
					for a in accts:
						del self.cfgParser.tab[a]
					#Write all new accounts
					accts = ev[2][1].keys()
					self.cfgParser.tab['Profile']['accounts'] = \
						string.join(accts)
					for a in accts:
						self.cfgParser.tab[a] = ev[2][1][a]
						if not a in self.connected.keys():
							self.connected[a] = 0
				else:
					self.cfgParser.tab[ev[2][0]] = ev[2][1]
				self.cfgParser.writeCfgFile()
				#TODO: tell the changes to other plugins
			#('STATUS', account, (status, msg))
			elif ev[0] == 'STATUS':
				activ = 1
				signed = ''
				keyID = ''
				if self.cfgParser.tab[ev[1]].has_key("keyid"):
					keyID = self.cfgParser.tab[ev[1]]["keyid"]
				if keyID:
					signed = self.gpg[ev[1]].sign(ev[2][0], keyID)
					if signed == 'BAD_PASSPHRASE':
						signed = ''
						if self.connected[ev[1]] == 0:
							self.hub.sendPlugin('BAD_PASSPHRASE', ev[1], ())
				if self.cfgParser.tab[ev[1]].has_key('active'):
					activ = self.cfgParser.tab[ev[1]]['active']
				if (ev[2][0] != 'offline') and (self.connected[ev[1]] == 0) and \
					activ:
					con = self.connect(ev[1])
					if self.connected[ev[1]]:
						statuss = ['offline', 'online', 'away', 'xa', 'dnd', \
								'invisible']
						self.connected[ev[1]] = statuss.index(ev[2][0])
						#send our presence
						typ = 'available'
						if ev[2][0] == 'invisible':
							typ = 'invisible'
						prio = 0
						if self.cfgParser.tab[ev[1]].has_key('priority'):
							prio = str(self.cfgParser.tab[ev[1]]['priority'])
						con.sendPresence(typ, prio, ev[2][0], ev[2][1], signed)
						self.hub.sendPlugin('STATUS', ev[1], ev[2][0])
						#ask our VCard
						iq = common.jabber.Iq(type="get")
						iq._setTag('vCard', common.jabber.NS_VCARD)
						id = con.getAnID()
						iq.setID(id)
						con.send(iq)
						self.myVCardID.append(id)
				elif (ev[2][0] == 'offline') and (self.connected[ev[1]]):
					self.connected[ev[1]] = 0
					con.disconnect()
					self.hub.sendPlugin('STATUS', ev[1], 'offline')
				elif ev[2][0] != 'offline' and self.connected[ev[1]]:
					statuss = ['offline', 'online', 'away', 'xa', 'dnd', \
							'invisible']
					self.connected[ev[1]] = statuss.index(ev[2][0])
					typ = 'available'
					if ev[2][0] == 'invisible':
						typ = 'invisible'
					prio = 0
					if self.cfgParser.tab[ev[1]].has_key('priority'):
						prio = str(self.cfgParser.tab[ev[1]]['priority'])
					con.sendPresence(typ, prio, ev[2][0], ev[2][1], signed)
					self.hub.sendPlugin('STATUS', ev[1], ev[2][0])
			#('MSG', account, (jid, msg, keyID))
			elif ev[0] == 'MSG':
				msgtxt = ev[2][1]
				msgenc = ''
				if ev[2][2]:
					#encrypt
					msgenc = self.gpg[ev[1]].encrypt(ev[2][1], [ev[2][2]])
					if msgenc: msgtxt = '[this message is encrypted]'
				msg = common.jabber.Message(ev[2][0], msgtxt)
				msg.setType('chat')
				if msgenc:
					msg.setX(common.jabber.NS_XENCRYPTED).insertData(msgenc)
				con.send(msg)
				self.hub.sendPlugin('MSGSENT', ev[1], ev[2])
			#('SUB', account, (jid, txt))
			elif ev[0] == 'SUB':
				log.debug('subscription request for %s' % ev[2][0])
				pres = common.jabber.Presence(ev[2][0], 'subscribe')
				if ev[2][1]:
					pres.setStatus(ev[2][1])
				else:
					pres.setStatus(_("I would like to add you to my roster."))
				con.send(pres)
			#('REQ', account, jid)
			elif ev[0] == 'AUTH':
				con.send(common.jabber.Presence(ev[2], 'subscribed'))
			#('DENY', account, jid)
			elif ev[0] == 'DENY':
				con.send(common.jabber.Presence(ev[2], 'unsubscribed'))
			#('UNSUB', account, jid)
			elif ev[0] == 'UNSUB':
				delauth = 1
				if self.cfgParser.Core.has_key('delauth'):
					delauth = self.cfgParser.Core['delauth']
				delroster = 1
				if self.cfgParser.Core.has_key('delroster'):
					delroster = self.cfgParser.Core['delroster']
				if delauth:
					con.send(common.jabber.Presence(ev[2], 'unsubscribe'))
				if delroster:
					con.removeRosterItem(ev[2])
			#('UNSUB_AGENT', account, agent)
			elif ev[0] == 'UNSUB_AGENT':
				con.removeRosterItem(ev[2])
				con.requestRegInfo(ev[2])
				agent_info = con.getRegInfo()
				key = agent_info['key']
				iq = common.jabber.Iq(to=ev[2], type="set")
				q = iq.setQuery(common.jabber.NS_REGISTER)
				q.insertTag('remove')
				q.insertTag('key').insertData(key)
				id = con.getAnID()
				iq.setID(id)
				con.send(iq)
				self.hub.sendPlugin('AGENT_REMOVED', ev[1], ev[2])
			#('UPDUSER', account, (jid, name, groups))
			elif ev[0] == 'UPDUSER':
				con.updateRosterItem(jid=ev[2][0], name=ev[2][1], \
					groups=ev[2][2])
			#('REQ_AGENTS', account, ())
			elif ev[0] == 'REQ_AGENTS':
#				agents = con.requestAgents()
				#do we need that ?
				#con.discoverInfo('jabber.lagaule.org')
				agents = con.discoverItems('jabber.lagaule.org')
				self.hub.sendPlugin('AGENTS', ev[1], agents)
				for agent in agents:
					self.request_infos(ev[1], con, agent['jid'])
			#('REG_AGENT_INFO', account, agent)
			elif ev[0] == 'REG_AGENT_INFO':
				con.requestRegInfo(ev[2])
				agent_info = con.getRegInfo()
				self.hub.sendPlugin('REG_AGENT_INFO', ev[1], (ev[2], agent_info))
			#('REG_AGENT', account, infos)
			elif ev[0] == 'REG_AGENT':
				con.sendRegInfo(ev[2])
			#('NEW_ACC', (hostname, login, password, name, ressource, prio, \
			# use_proxy, proxyhost, proxyport))
			elif ev[0] == 'NEW_ACC':
				if ev[2][6]:
					proxy = {'host': ev[2][7], 'port': ev[2][8]}
				else:
					proxy = None
				c = common.jabber.Client(host = ev[2][0], debug = [], \
					log = None, proxy = proxy)
				try:
					c.connect()
				except IOError, e:
					log.debug("Couldn't connect to %s %s" % (hostname, e))
					return 0
				else:
					log.debug("Connected to server")
					c.requestRegInfo()
					req = c.getRegInfo()
					c.setRegInfo( 'username', ev[2][1])
					c.setRegInfo( 'password', ev[2][2])
					#FIXME: if users already exist, no error message :(
					if not c.sendRegInfo():
						print "error " + c.lastErr
					else:
						self.hub.sendPlugin('ACC_OK', ev[1], ev[2])
			#('ACC_CHG', old_account, new_account)
			elif ev[0] == 'ACC_CHG':
				self.connected[ev[2]] = self.connected[ev[1]]
				del self.connected[ev[1]]
				if con:
					self.connexions[con] = ev[2]
			#('ASK_VCARD', account, jid)
			elif ev[0] == 'ASK_VCARD':
				iq = common.jabber.Iq(to=ev[2], type="get")
				iq._setTag('vCard', common.jabber.NS_VCARD)
				iq.setID(con.getAnID())
				con.send(iq)
			#('VCARD', {entry1: data, entry2: {entry21: data, ...}, ...})
			elif ev[0] == 'VCARD':
				iq = common.jabber.Iq(type="set")
				iq.setID(con.getAnID())
				iq2 = iq._setTag('vCard', common.jabber.NS_VCARD)
				for i in ev[2].keys():
					if i != 'jid':
						if type(ev[2][i]) == type({}):
							iq3 = iq2.insertTag(i)
							for j in ev[2][i].keys():
								iq3.insertTag(j).putData(ev[2][i][j])
						else:
							iq2.insertTag(i).putData(ev[2][i])
				con.send(iq)
			#('AGENT_LOGGING', account, (agent, typ))
			elif ev[0] == 'AGENT_LOGGING':
				t = ev[2][1];
				if not t:
					t='available';
				p = common.jabber.Presence(to=ev[2][0], type=t)
				con.send(p)
			#('LOG_NB_LINE', account, jid)
			elif ev[0] == 'LOG_NB_LINE':
				fic = open(LOGPATH + ev[2], "r")
				nb = 0
				while (fic.readline()):
					nb = nb+1
				fic.close()
				self.hub.sendPlugin('LOG_NB_LINE', ev[1], (ev[2], nb))
			#('LOG_GET_RANGE', account, (jid, line_begin, line_end))
			elif ev[0] == 'LOG_GET_RANGE':
				fic = open(LOGPATH + ev[2][0], "r")
				nb = 0
				while (nb < ev[2][1] and fic.readline()):
					nb = nb+1
				while nb < ev[2][2]:
					line = fic.readline()
					nb = nb+1
					if line:
						lineSplited = string.split(line, ':')
						if len(lineSplited) > 2:
							self.hub.sendPlugin('LOG_LINE', ev[1], (ev[2][0], nb, \
								lineSplited[0], lineSplited[1], lineSplited[2:]))
				fic.close()
			#('REG_MESSAGE', module, list_message)
			elif ev[0] == 'REG_MESSAGE':
				for msg in ev[2]:
					self.hub.register(ev[1], msg)
			elif ev[0] == 'EXEC_PLUGIN':
				self.loadPlugins(ev[2])
			#('GC_JOIN', account, (nick, room, server, passwd))
			elif ev[0] == 'GC_JOIN':
				p = common.jabber.Presence(to='%s@%s/%s' % (ev[2][1], ev[2][2], \
					ev[2][0]))
				con.send(p)
			#('GC_MSG', account, (jid, msg))
			elif ev[0] == 'GC_MSG':
				msg = common.jabber.Message(ev[2][0], ev[2][1])
				msg.setType('groupchat')
				con.send(msg)
				self.hub.sendPlugin('MSGSENT', ev[1], ev[2])
			#('GC_STATUS', account, (nick, jid, show, status))
			elif ev[0] == 'GC_STATUS':
				if ev[2][2] == 'offline':
					con.send(common.jabber.Presence('%s/%s' % (ev[2][1], ev[2][0]), \
						'unavailable'))
				else:
					con.send(common.jabber.Presence('%s/%s' % (ev[2][1], ev[2][0]), \
						'available', show=ev[2][2], status = ev[2][3]))
			#('PASSPHRASE', account, passphrase)
			elif ev[0] == 'PASSPHRASE':
				self.gpg[ev[1]].passphrase = ev[2]
			else:
				log.debug(_("Unknown Command %s") % ev[0])
		if self.mode == 'server':
			for con in self.connexions:
				if self.connected[self.connexions[con]]:
					con.process(1)
			#remove connexion that have been broken
			for acc in self.connected:
				if self.connected[acc]:
					break
				for con in self.connexions:
						if self.connexions[con] == acc:
							del self.connexions[con]
							break
			
			time.sleep(0.1)
		return 0
		
	# END read_queue

	def read_socket(self):
		ready_to_read, ready_to_write, in_error = select.select(
			[self.socket], [], [], 0.1)
		for sock in ready_to_read:
			self.data += sock.recv(1024)
			if not self.data:
				continue
			while len(self.data) == 1024:
				self.data += sock.recv(1024)
			list_ev = self.unparse_socket()
			for ev in list_ev:
				self.hub.sendPlugin(ev[0], ev[1], ev[2])
				if ev[0] == 'QUIT':
					sock.close()
					return 1
		return 0
	# END read_socket


	def mainLoop(self):
		"""Main Loop : Read the incomming queue to execute commands comming from
		plugins and process Jabber"""
		end = 0
		while not end:
			end = self.read_queue()
			if self.mode == 'client':
				end = self.read_socket()
	# END main
# END GajimCore

def start(mode='server'):
	"""Start the Core"""
	gc = GajimCore(mode)
	try:
		gc.mainLoop()
	except KeyboardInterrupt:
		print _("Keyboard Interrupt : Bye!")
		gc.hub.sendPlugin('QUIT', None, ())
		return 0
#	except:
#		print "Erreur survenue"
#		gc.hub.sendPlugin('QUIT', ())
# END start
