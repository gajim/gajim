#!/usr/bin/env python
##	core/core.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
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

import sys, os

sys.path.append("..")
import time
import string
import logging

import common.hub
import common.jabber
import common.optparser

log = logging.getLogger('core.core')
log.setLevel(logging.DEBUG)

CONFPATH = "~/.gajim/config"
LOGPATH = os.path.expanduser("~/.gajim/logs/")

class GajimCore:
	"""Core"""
	def __init__(self):
		self.init_cfg_file()
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.hub = common.hub.GajimHub()
		self.parse()
		self.connected = {}
		#connexions {con: name, ...}
		self.connexions = {}
		for a in self.accounts:
			self.connected[a] = 0
		self.myVCardID = []
	# END __init__

	def init_cfg_file(self):
		"""Initialize configuration file"""
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
					print "Can't create %s" % path
					sys.exit
		try:
			os.stat(fname)
		except:
			print "creating %s" % fname
			fic = open(fname, "w")
			fic.write("[Profile]\naccounts = \n\n[Core]\ndelauth = 1\nalwaysauth = 0\nmodules = logger gtkgui\ndelroster = 1\n")
			fic.close()
	# END init_cfg_file

	def parse(self):
		"""Parse configuratoin file and create self.accounts"""
		self.cfgParser.parseCfgFile()
		self.accounts = {}
		accts = string.split(self.cfgParser.tab['Profile']['accounts'], ' ')
		if accts == ['']:
			accts = []
		for a in accts:
			self.accounts[a] = self.cfgParser.tab[a]

	def vCardCB(self, con, vc):
		"""Called when we recieve a vCard
		Parse the vCard and send it to plugins"""
		vcard = {'jid': vc.getFrom().getBasic()}
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
		self.hub.sendPlugin('MSG', self.connexions[con], \
			(msg.getFrom().getBasic(), msg.getBody()))
	# END messageCB

	def presenceCB(self, con, prs):
		"""Called when we recieve a presence"""
		who = str(prs.getFrom())
		type = prs.getType()
		if type == None: type = 'available'
		log.debug("PresenceCB : %s" % type)
		if type == 'available':
			if prs.getShow():
				show = prs.getShow()
			else:
				show = 'online'
			self.hub.sendPlugin('NOTIFY', self.connexions[con], \
				(prs.getFrom().getBasic(), show, prs.getStatus(), \
				prs.getFrom().getResource()))
		elif type == 'unavailable':
			self.hub.sendPlugin('NOTIFY', self.connexions[con], \
				(prs.getFrom().getBasic(), 'offline', prs.getStatus(), \
					prs.getFrom().getResource()))
		elif type == 'subscribe':
			log.debug("subscribe request from %s" % who)
			if self.cfgParser.Core['alwaysauth'] == 1 or \
				string.find(who, "@") <= 0:
				con.send(common.jabber.Presence(who, 'subscribed'))
				if string.find(who, "@") <= 0:
					self.hub.sendPlugin('NOTIFY', self.connexions[con], \
						(who, 'offline', 'offline', prs.getFrom().getResource()))
			else:
				txt = prs.getStatus()
				if not txt:
					txt = "I would like to add you to my roster."
				self.hub.sendPlugin('SUBSCRIBE', self.connexions[con], (who, 'txt'))
		elif type == 'subscribed':
			jid = prs.getFrom()
			self.hub.sendPlugin('SUBSCRIBED', self.connexions[con],\
				(jid.getBasic(), jid.getNode(), jid.getResource()))
			self.hub.queueIn.put(('UPDUSER', self.connexions[con], \
				(jid.getBasic(), jid.getNode(), ['general'])))
			#BE CAREFUL : no con.updateRosterItem() in a callback
			log.debug("we are now subscribed to %s" % who)
		elif type == 'unsubscribe':
			log.debug("unsubscribe request from %s" % who)
		elif type == 'unsubscribed':
			log.debug("we are now unsubscribed to %s" % who)
			self.hub.sendPlugin('UNSUBSCRIBED', self.connexions[con], \
				prs.getFrom().getBasic())
		elif type == 'error':
			errmsg = prs._node.kids[0].getData()
			self.hub.sendPlugin('NOTIFY', self.connexions[con], \
				(prs.getFrom().getBasic(), 'error', errmsg, \
					prs.getFrom().getResource()))
	# END presenceCB

	def disconnectedCB(self, con):
		"""Called when we are disconnected"""
		log.debug("disconnectedCB")
		if self.connected[self.connexions[con]] == 1:
			self.connected[self.connexions[con]] = 0
		self.hub.sendPlugin('STATUS', self.connexions[con], 'offline')
		if self.connexions.has_key(con):
			del self.connexions[con]
	# END disconenctedCB

	def connect(self, account):
		"""Connect and authentificate to the Jabber server"""
		hostname = self.cfgParser.tab[account]["hostname"]
		name = self.cfgParser.tab[account]["name"]
		password = self.cfgParser.tab[account]["password"]
		ressource = self.cfgParser.tab[account]["ressource"]
		con = common.jabber.Client(host = hostname, \
			debug = [], log = sys.stderr, \
#			debug = [common.jabber.DBG_ALWAYS], log = sys.stderr, \
			connection=common.xmlstream.TCP, port=5222)
			#debug = [common.jabber.DBG_ALWAYS], log = sys.stderr, \
			#connection=common.xmlstream.TCP_SSL, port=5223)
		try:
			con.connect()
		except IOError, e:
			log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.hub.sendPlugin('STATUS', account, 'offline')
			self.hub.sendPlugin('WARNING', None, "Couldn't connect to %s" \
				% hostname)
			return 0
		except common.xmlstream.socket.error, e:
			log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.hub.sendPlugin('STATUS', account, 'offline')
			self.hub.sendPlugin('WARNING', None, "Couldn't connect to %s : %s" \
				% (hostname, e))
			return 0
		else:
			log.debug("Connected to server")

			con.registerHandler('message', self.messageCB)
			con.registerHandler('presence', self.presenceCB)
			con.registerHandler('iq',self.vCardCB,'result')#common.jabber.NS_VCARD)
			con.setDisconnectHandler(self.disconnectedCB)
			#BUG in jabberpy library : if hostname is wrong : "boucle"
			if con.auth(name, password, ressource):
				con.requestRoster()
				roster = con.getRoster().getRaw()
				if not roster :
					roster = {}
				self.hub.sendPlugin('ROSTER', account, roster)
				con.sendInitPresence()
				self.hub.sendPlugin('STATUS', account, 'online')
				self.connexions[con] = account
				self.connected[account] = 1
				iq = common.jabber.Iq(type="get")
				iq._setTag('vCard', common.jabber.NS_VCARD)
				id = con.getAnID()
				iq.setID(id)
				con.send(iq)
				self.myVCardID.append(id)
				return con
			else:
				log.debug("Couldn't authentificate to %s" % hostname)
				self.hub.sendPlugin('STATUS', account, 'offline')
				self.hub.sendPlugin('WARNING', None, \
					'Authentification failed with %s, check your login and password'\
					% hostname)
				return 0
	# END connect

	def mainLoop(self):
		"""Main Loop : Read the incomming queue to execute commands comming from
		plugins and process Jabber"""
		while 1:
			if not self.hub.queueIn.empty():
				ev = self.hub.queueIn.get()
				if ev[1] and (ev[1] in self.connexions.values()):
					for con in self.connexions.keys():
						if ev[1] == self.connexions[con]:
							break
				else:
					con = None
				#('QUIT', account, ())
				if ev[0] == 'QUIT':
					for con in self.connexions.keys():
						if self.connected[self.connexions[con]] == 1:
							self.connected[self.connexions[con]] = 0
							con.disconnect()
					self.hub.sendPlugin('QUIT', None, ())
					return
				#('ASK_CONFIG', account, (who_ask, section, default_config))
				elif ev[0] == 'ASK_CONFIG':
					if ev[2][1] == 'accounts':
						self.hub.sendPlugin('CONFIG', None, (ev[2][0], self.accounts))
					else:
						if self.cfgParser.tab.has_key(ev[2][1]):
							self.hub.sendPlugin('CONFIG', None, (ev[2][0], \
								self.cfgParser.__getattr__(ev[2][1])))
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
								self.connected[a]= 0
					else:
						self.cfgParser.tab[ev[2][0]] = ev[2][1]
					self.cfgParser.writeCfgFile()
					#TODO: tell the changes to other plugins
				#('STATUS', account, (status, msg))
				elif ev[0] == 'STATUS':
					if (ev[2][0] != 'offline') and (self.connected[ev[1]] == 0):
						con = self.connect(ev[1])
					elif (ev[2][0] == 'offline') and (self.connected[ev[1]] == 1):
						self.connected[ev[1]] = 0
						con.disconnect()
						self.hub.sendPlugin('STATUS', ev[1], 'offline')
					if ev[2][0] != 'offline' and self.connected[ev[1]] == 1:
						p = common.jabber.Presence()
						p.setShow(ev[2][0])
						p.setStatus(ev[2][1])
						con.send(p)
						self.hub.sendPlugin('STATUS', ev[1], ev[2][0])
				#('MSG', account, (jid, msg))
				elif ev[0] == 'MSG':
					msg = common.jabber.Message(ev[2][0], ev[2][1])
					msg.setType('chat')
					con.send(msg)
					self.hub.sendPlugin('MSGSENT', ev[1], ev[2])
				#('SUB', account, (jid, txt))
				elif ev[0] == 'SUB':
					log.debug('subscription request for %s' % ev[2][0])
					pres = common.jabber.Presence(ev[2][0], 'subscribe')
					if ev[2][1]:
						pres.setStatus(ev[2][1])
					else:
						pres.setStatus("I would like to add you to my roster.")
					con.send(pres)
				#('REQ', account, jid)
				elif ev[0] == 'AUTH':
					con.send(common.jabber.Presence(ev[2], 'subscribed'))
				#('DENY', account, jid)
				elif ev[0] == 'DENY':
					con.send(common.jabber.Presence(ev[2], 'unsubscribed'))
				#('UNSUB', accountjid)
				elif ev[0] == 'UNSUB':
					if self.cfgParser.Core.has_key('delauth'):
						delauth = self.cfgParser.Core['delauth']
					else:
						delauth = 1
					if self.cfgParser.Core.has_key('delroster'):
						delroster = self.cfgParser.Core['delroster']
					else:
						delroster = 1
					if delauth:
						con.send(common.jabber.Presence(ev[2], 'unsubscribe'))
					if delroster:
						con.removeRosterItem(ev[2])
				#('UPDUSER', account, (jid, name, groups))
				elif ev[0] == 'UPDUSER':
					con.updateRosterItem(jid=ev[2][0], name=ev[2][1], \
						groups=ev[2][2])
				#('REQ_AGENTS', account, ())
				elif ev[0] == 'REQ_AGENTS':
					agents = con.requestAgents()
					self.hub.sendPlugin('AGENTS', ev[1], agents)
				#('REQ_AGENT_INFO', account, agent)
				elif ev[0] == 'REQ_AGENT_INFO':
					con.requestRegInfo(ev[2])
					agent_info = con.getRegInfo()
					self.hub.sendPlugin('AGENT_INFO', ev[1], (ev[2], agent_info))
				#('REG_AGENT', account, infos)
				elif ev[0] == 'REG_AGENT':
					con.sendRegInfo(ev[2])
				#('NEW_ACC', (hostname, login, password, name, ressource))
				elif ev[0] == 'NEW_ACC':
					c = common.jabber.Client(host = \
						ev[2][0], debug = False, log = sys.stderr)
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
						self.connexions[con] = self.connected[ev[2]]
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
				#('AGENT_LOGGING', account, (agent, type))
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
				else:
					log.debug("Unknown Command %s" % ev[0])
			else:
				for con in self.connexions:
					if self.connected[self.connexions[con]] == 1:
						con.process(1)
			time.sleep(0.1)
	# END main
# END GajimCore

def loadPlugins(gc):
	"""Load defaults plugins : plugins in 'modules' option of Core section 
	in ConfFile and register them to the hub"""
	modStr = gc.cfgParser.Core['modules']
	if modStr:
		mods = string.split (modStr, ' ')

		for mod in mods:
			modObj = gc.hub.newPlugin(mod)
			gc.hub.register(mod, 'ROSTER')
			gc.hub.register(mod, 'WARNING')
			gc.hub.register(mod, 'STATUS')
			gc.hub.register(mod, 'NOTIFY')
			gc.hub.register(mod, 'MSG')
			gc.hub.register(mod, 'MSGSENT')
			gc.hub.register(mod, 'SUBSCRIBED')
			gc.hub.register(mod, 'UNSUBSCRIBED')
			gc.hub.register(mod, 'SUBSCRIBE')
			gc.hub.register(mod, 'AGENTS')
			gc.hub.register(mod, 'AGENT_INFO')
			gc.hub.register(mod, 'QUIT')
			gc.hub.register(mod, 'ACC_OK')
			gc.hub.register(mod, 'CONFIG')
			gc.hub.register(mod, 'MYVCARD')
			gc.hub.register(mod, 'VCARD')
			gc.hub.register(mod, 'LOG_NB_LINE')
			gc.hub.register(mod, 'LOG_LINE')
			modObj.load()
# END loadPLugins

def start():
	"""Start the Core"""
	gc = GajimCore()
	loadPlugins(gc)
	try:
		gc.mainLoop()
	except KeyboardInterrupt:
		print "Keyboard Interrupt : Bye!"
		gc.hub.sendPlugin('QUIT', None, ())
		return 0
#	except:
#		print "Erreur survenue"
#		gc.hub.sendPlugin('QUIT', ())
# END start
