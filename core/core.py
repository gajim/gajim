#!/usr/bin/env python
##	core/core.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
## 	- David Ferlier <david@yazzy.org>
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

import Queue
import socket
import sys
import time
import logging

import plugins
import common.hub
import common.jabber
import common.optparser

log = logging.getLogger('core.core')
log.setLevel(logging.DEBUG)
CONFPATH = "~/.gajimrc"

class GajimCore:
	def __init__(self):
		self.connected = 0
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
#		print '%s\n' % self.cfgParser.Server_hostname;
		self.hub = common.hub.GajimHub()
		self.cfgParser.parseCfgFile()
	# END __init__

	def messageCB(self, con, msg):
		self.hub.sendPlugin('MSG', (msg.getFrom().getBasic(), \
			msg.getBody()))
	# END messageCB

	def presenceCB(self, con, prs):
		who = str(prs.getFrom())
		type = prs.getType()
		if type == None: type = 'available'
		log.debug("PresenceCB : %s" % type)
		if type == 'available':
			if prs.getShow():
				show = prs.getShow()
			else:
				show = 'online'
			self.hub.sendPlugin('NOTIFY', \
			(prs.getFrom().getBasic(), show, prs.getStatus()))
		elif type == 'unavailable':
			self.hub.sendPlugin('NOTIFY', \
				(prs.getFrom().getBasic(), 'offline', prs.getStatus()))
		elif type == 'subscribe':
			log.debug("subscribe request from %s" % who)
			if self.cfgParser.Core_alwaysauth == 1:
				self.con.send(common.jabber.Presence(who, 'subscribed'))
			else:
				self.hub.sendPlugin('SUBSCRIBE', who)
		elif type == 'subscribed':
			#plein de trucs a faire
			jid = prs.getFrom()
			self.hub.sendPlugin('SUBSCRIBED', {'jid':jid.getBasic(), \
				'nom':jid.getNode()})
			self.con.updateRosterItem(jid=jid.getBasic(), name=jid.getNode())
			log.debug("we are now subscribed to %s" % who)
		elif type == 'unsubscribe':
			log.debug("unsubscribe request from %s" % who)
		elif type == 'unsubscribed':
			log.debug("we are now unsubscribed to %s" % who)
			
	# END presenceCB

	def disconnectedCB(self, con):
		log.debug("disconnectedCB")
	# END disconenctedCB

	def connect(self):
		self.con = common.jabber.Client(host = \
			self.cfgParser.Server_hostname, \
			debug = False, log = sys.stderr)
		try:
			self.con.connect()
		except IOError, e:
			log.debug("Couldn't connect to %s" % e)
			sys.exit(0)
		else:
			log.debug("Connected to server")

			self.con.setMessageHandler(self.messageCB)
			self.con.setPresenceHandler(self.presenceCB)
			self.con.setDisconnectHandler(self.disconnectedCB)
			if self.con.auth(self.cfgParser.Profile_name,
					self.cfgParser.Profile_password, 
					self.cfgParser.Profile_ressource):

				self.con.requestRoster()
				roster = self.con.getRoster().getRaw()
				if not roster :
					roster = {}
				self.hub.sendPlugin('ROSTER', roster)
				self.con.sendInitPresence()
				self.connected = 1
			else:
				sys.exit(1)
	# END connect

	def mainLoop(self):
		while 1:
			if not self.hub.queueIn.empty():
				ev = self.hub.queueIn.get()
				if ev[0] == 'QUIT':
					if self.connected == 1:
						self.con.disconnect()
					return
				#('STATUS', status)
				elif ev[0] == 'STATUS':
					if (ev[1] != 'offline') and (self.connected == 0):
						self.connect()
					elif (ev[1] == 'offline') and (self.connected == 1):
						self.con.disconnect()
						self.connected = 0
					if ev[1] != 'offline':
						p = common.jabber.Presence()
						p.setShow(ev[1])
						self.con.send(p)
				#('MSG', (jid, msg))
				elif ev[0] == 'MSG':
					msg = common.jabber.Message(ev[1][0], ev[1][1])
					msg.setType('chat')
					self.con.send(msg)
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
					delauth = self.cfgParser.Core_delauth
					if not delauth: delauth = 1
					delroster = self.cfgParser.Core_delroster
					if not delroster: delroster = 1
					if delauth:
						self.con.send(common.jabber.Presence(ev[1], 'unsubscribe'))
					if delroster:
						self.con.removeRosterItem(ev[1])
				#('UPDUSER', (jid, name, groups))
				elif ev[0] == 'UPDUSER':
					self.con.updateRosterItem(jid=ev[1][0], name=ev[1][1], groups=ev[1][2])
				else:
					log.debug("Unknown Command")
			elif self.connected == 1:
				self.con.process(1)
			time.sleep(0.1)
	# END main
# END GajimCore

def start():
	gc = GajimCore()
	guiPl = gc.hub.newPlugin ('gtkgui')
	gc.hub.register('gtkgui', 'ROSTER')
	gc.hub.register('gtkgui', 'NOTIFY')
	gc.hub.register('gtkgui', 'MSG')
	gc.hub.register('gtkgui', 'SUBSCRIBED')
	gc.hub.register('gtkgui', 'SUBSCRIBE')
	guiPl.load ()
	gc.mainLoop()
