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

import sys

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

class GajimCore:
	"""Core"""
	def __init__(self):
		self.connected = 0
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.hub = common.hub.GajimHub()
		self.parse()
	# END __init__

	def parse(self):
		self.cfgParser.parseCfgFile()
		self.accounts = {}
		accts = self.cfgParser.tab['Profile']['accounts']
		for a in string.split(accts, ' '):
			self.accounts[a] = self.cfgParser.tab[a]

	def messageCB(self, con, msg):
		"""Called when we recieve a message"""
		self.hub.sendPlugin('MSG', (msg.getFrom().getBasic(), \
			msg.getBody()))
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
			self.hub.sendPlugin('NOTIFY', (prs.getFrom().getBasic(), \
				show, prs.getStatus(), prs.getFrom().getResource()))
		elif type == 'unavailable':
			self.hub.sendPlugin('NOTIFY', \
				(prs.getFrom().getBasic(), 'offline', prs.getStatus(), \
					prs.getFrom().getResource()))
		elif type == 'subscribe':
			log.debug("subscribe request from %s" % who)
			if self.cfgParser.Core['alwaysauth'] == 1 or \
				string.find(who, "@") <= 0:
				self.con.send(common.jabber.Presence(who, 'subscribed'))
				if string.find(who, "@") <= 0:
					self.hub.sendPlugin('NOTIFY', (who, 'offline', 'offline', \
						prs.getFrom().getResource()))
			else:
				self.hub.sendPlugin('SUBSCRIBE', who)
		elif type == 'subscribed':
			jid = prs.getFrom()
			self.hub.sendPlugin('SUBSCRIBED', {'jid':jid.getBasic(), \
				'nom':jid.getNode(), 'ressource':jid.getResource()})
			self.hub.queueIn.put(('UPDUSER', (jid.getBasic(), \
				jid.getNode(), ['general'])))
			#BE CAREFUL : no self.con.updateRosterItem() in a callback
			log.debug("we are now subscribed to %s" % who)
		elif type == 'unsubscribe':
			log.debug("unsubscribe request from %s" % who)
		elif type == 'unsubscribed':
			log.debug("we are now unsubscribed to %s" % who)
			self.hub.sendPlugin('UNSUBSCRIBED', prs.getFrom().getBasic())
		elif type == 'error':
			print "\n\n******** ERROR *******"
			#print "From : %s" % prs.getFrom()
			#print "To : %s" % prs.getTo()			
			#print "Status : %s" % prs.getStatus()
			#print "Show : %s" % prs.getShow()
			#print "X : %s" % prs.getX()
			#print "XNode : %s" % prs.getXNode()
			#print "XPayload : %s" % prs.getXPayload()
			#print "_node : %s" % prs._node.getData()
			#print "kids : %s" % prs._node.kids[0].getData()
			#print "\n\n"
			errmsg = prs._node.kids[0].getData()
	# END presenceCB

	def disconnectedCB(self, con):
		"""Called when we are disconnected"""
		log.debug("disconnectedCB")
		if self.connected == 1:
			self.connected = 0
			self.con.disconnect()
		self.hub.sendPlugin('STATUS', 'offline')
	# END disconenctedCB

	def connect(self, account):
		"""Connect and authentificate to the Jabber server"""
		hostname = self.cfgParser.tab[account]["hostname"]
		name = self.cfgParser.tab[account]["name"]
		password = self.cfgParser.tab[account]["password"]
		ressource = self.cfgParser.tab[account]["ressource"]
		self.con = common.jabber.Client(host = hostname, \
			debug = [common.jabber.DBG_ALWAYS], log = sys.stderr, \
			connection=common.xmlstream.TCP, port=5222)
			#debug = [common.jabber.DBG_ALWAYS], log = sys.stderr, \
			#connection=common.xmlstream.TCP_SSL, port=5223)
		try:
			self.con.connect()
		except IOError, e:
			log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.hub.sendPlugin('STATUS', 'offline')
			self.hub.sendPlugin('WARNING', "Couldn't connect to %s" % hostname)
			return 0
		except self.con.socket.gaierror, e:
			log.debug("Couldn't connect to %s %s" % (hostname, e))
			self.hub.sendPlugin('STATUS', 'offline')
			self.hub.sendPlugin('WARNING', "Couldn't connect to %s" % hostname)
			return 0
		else:
			log.debug("Connected to server")

			self.con.registerHandler('message', self.messageCB)
			self.con.registerHandler('presence', self.presenceCB)
			self.con.setDisconnectHandler(self.disconnectedCB)
			#BUG in jabberpy library : if hostname is wrong : "boucle"
			if self.con.auth(name, password, ressource):
				self.con.requestRoster()
				roster = self.con.getRoster().getRaw()
				if not roster :
					roster = {}
				self.hub.sendPlugin('ROSTER', roster)
				self.con.sendInitPresence()
				self.hub.sendPlugin('STATUS', 'online')
				self.connected = 1
			else:
				log.debug("Couldn't authentificate to %s" % hostname)
				self.hub.sendPlugin('STATUS', 'offline')
				self.hub.sendPlugin('WARNING', \
					'Authentification failed, check your login and password')
				return 0
	# END connect

	def mainLoop(self):
		"""Main Loop : Read the incomming queue to execute commands comming from
		plugins and process Jabber"""
		while 1:
			if not self.hub.queueIn.empty():
				ev = self.hub.queueIn.get()
				if ev[0] == 'QUIT':
					if self.connected == 1:
						self.connected = 0
						self.con.disconnect()
					self.hub.sendPlugin('QUIT', ())
					return
				#('ASK_CONFIG', section)
				elif ev[0] == 'ASK_CONFIG':
					if ev[1] == 'accounts':
						self.hub.sendPlugin('CONFIG', self.accounts)
					else:
						self.hub.sendPlugin('CONFIG', \
							self.cfgParser.__getattr__(ev[1]))
				#('CONFIG', (section, config))
				elif ev[0] == 'CONFIG':
					if ev[1][0] == 'accounts':
						#Remove all old accounts
						accts = string.split(self.cfgParser.tab\
							['Profile']['accounts'], ' ')
						for a in accts:
							del self.cfgParser.tab[a]
						#Write all new accounts
						accts = ev[1][1].keys()
						self.cfgParser.tab['Profile']['accounts'] = \
							string.join(accts)
						for a in accts:
							self.cfgParser.tab[a] = ev[1][1][a]
					else:
						self.cfgParser.tab[ev[1][0]] = ev[1][1]
					self.cfgParser.writeCfgFile()
					#TODO: tell the changes to other plugins
				#('STATUS', (status, msg, account))
				elif ev[0] == 'STATUS':
					if (ev[1][0] != 'offline') and (self.connected == 0):
						self.connect(ev[1][2])
					elif (ev[1][0] == 'offline') and (self.connected == 1):
						self.connected = 0
						self.con.disconnect()
						self.hub.sendPlugin('STATUS', 'offline')
					if ev[1][0] != 'offline' and self.connected == 1:
						p = common.jabber.Presence()
						p.setShow(ev[1][0])
						p.setStatus(ev[1][1])
						self.con.send(p)
						self.hub.sendPlugin('STATUS', ev[1][0])
				#('MSG', (jid, msg))
				elif ev[0] == 'MSG':
					msg = common.jabber.Message(ev[1][0], ev[1][1])
					msg.setType('chat')
					self.con.send(msg)
					self.hub.sendPlugin('MSGSENT', ev[1])
				#('SUB', (jid, txt))
				elif ev[0] == 'SUB':
					log.debug('subscription request for %s' % ev[1][0])
					self.con.send(common.jabber.Presence(ev[1][0], 'subscribe'))
				#('REQ', jid)
				elif ev[0] == 'AUTH':
					self.con.send(common.jabber.Presence(ev[1], 'subscribed'))
				#('DENY', jid)
				elif ev[0] == 'DENY':
					self.con.send(common.jabber.Presence(ev[1], 'unsubscribed'))
				#('UNSUB', jid)
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
						self.con.send(common.jabber.Presence(ev[1], 'unsubscribe'))
					if delroster:
						self.con.removeRosterItem(ev[1])
				#('UPDUSER', (jid, name, groups))
				elif ev[0] == 'UPDUSER':
					self.con.updateRosterItem(jid=ev[1][0], name=ev[1][1], \
						groups=ev[1][2])
				elif ev[0] == 'REQ_AGENTS':
					agents = self.con.requestAgents()
					self.hub.sendPlugin('AGENTS', agents)
				elif ev[0] == 'REQ_AGENT_INFO':
					self.con.requestRegInfo(ev[1])
					agent_info = self.con.getRegInfo()
					self.hub.sendPlugin('AGENT_INFO', (ev[1], agent_info))
				elif ev[0] == 'REG_AGENT':
					self.con.sendRegInfo(ev[1])
				#('NEW_ACC', (hostname, login, password, name, ressource))
				elif ev[0] == 'NEW_ACC':
					c = common.jabber.Client(host = \
						ev[1][0], debug = False, log = sys.stderr)
					try:
						c.connect()
					except IOError, e:
						log.debug("Couldn't connect to %s %s" % (hostname, e))
						return 0
					else:
						log.debug("Connected to server")
						c.requestRegInfo()
						req = c.getRegInfo()
						c.setRegInfo( 'username', ev[1][1])
						c.setRegInfo( 'password', ev[1][2])
						#FIXME: if users already exist, no error message :(
						if not c.sendRegInfo():
							print "error " + c.lastErr
						else:
							self.hub.sendPlugin('ACC_OK', ev[1])
				else:
					log.debug("Unknown Command %s" % ev[0])
			elif self.connected == 1:
				self.con.process(1)
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
			gc.hub.register(mod, 'SUBSCRIBE')
			gc.hub.register(mod, 'AGENTS')
			gc.hub.register(mod, 'AGENT_INFO')
			gc.hub.register(mod, 'QUIT')
			gc.hub.register(mod, 'ACC_OK')
			gc.hub.register(mod, 'CONFIG')
			modObj.load()
# END loadPLugins

def start():
	"""Start the Core"""
	gc = GajimCore()
	loadPlugins(gc)
################ pr des tests ###########
	gc.hub.sendPlugin('NOTIFY', ('aste@lagaule.org', 'online', 'online', 'oleron'))
#	gc.hub.sendPlugin('MSG', ('ate@lagaule.org', 'msg'))
#########################################
	try:
		gc.mainLoop()
	except KeyboardInterrupt:
		print "Keyboard Interrupt : Bye!"
		if gc.connected:
			gc.con.disconnect()
		gc.hub.sendPlugin('QUIT', ())
		return 0
# END start
