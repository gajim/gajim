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
		log.debug("PresenceCB")
		who = str(prs.getFrom())
		type = prs.getType()
		if type == None: type = 'available'
		if type == 'available':
			if prs.getShow():
				show = prs.getShow()
			else:
				show = 'online'
			self.hub.sendPlugin('NOTIFY', \
			(prs.getFrom().getBasic(), show, prs.getStatus()))
		if type == 'unavailable':
			self.hub.sendPlugin('NOTIFY', \
				(prs.getFrom().getBasic(), 'offline', prs.getStatus()))
			
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
				roster = self.con.getRoster()
				tab_roster = {}
				for jid in roster.getJIDs():
					if roster.getShow(jid):
						show = roster.getShow(jid)
					else:
						show = roster.getOnline(jid)
					tab_roster[jid.getBasic()] = \
						{"Online":roster.getOnline(jid), "Status":roster.getStatus(jid), "Show":show}
				self.hub.sendPlugin('ROSTER', tab_roster)
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
				elif ev[0] == 'STATUS':
					if (ev[1] != 'offline') and (self.connected == 0):
						self.connect()
					elif (ev[1] == 'offline') and (self.connected == 1):
						self.con.disconnect()
						self.connected = 0
					else:
						print ev
						p = common.jabber.Presence()
						p.setShow(ev[1])
						self.con.send(p)
				elif ev[0] == 'MSG':
					msg = common.jabber.Message(ev[1][0], ev[1][1])
					msg.setType('chat')
					self.con.send(msg)
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
	guiPl.load ()
	gc.mainLoop()
