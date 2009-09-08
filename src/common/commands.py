# -*- coding:utf-8 -*-
## src/common/commands.py
##
## Copyright (C) 2006-2007 Yann Leboulanger <asterix AT lagaule.org>
##                         Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
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

import xmpp
import helpers
import dataforms
import gajim

class AdHocCommand:
	commandnode = 'command'
	commandname = 'The Command'
	commandfeatures = (xmpp.NS_DATA,)

	@staticmethod
	def isVisibleFor(samejid):
		''' This returns True if that command should be visible and invokable
		for others.
		samejid - True when command is invoked by an entity with the same bare
		jid.'''
		return True

	def __init__(self, conn, jid, sessionid):
		self.connection = conn
		self.jid = jid
		self.sessionid = sessionid

	def buildResponse(self, request, status = 'executing', defaultaction = None,
	actions = None):
		assert status in ('executing', 'completed', 'canceled')

		response = request.buildReply('result')
		cmd = response.addChild('command', namespace=xmpp.NS_COMMANDS, attrs={
			'sessionid': self.sessionid,
			'node': self.commandnode,
			'status': status})
		if defaultaction is not None or actions is not None:
			if defaultaction is not None:
				assert defaultaction in ('cancel', 'execute', 'prev', 'next',
					'complete')
				attrs = {'action': defaultaction}
			else:
				attrs = {}

			cmd.addChild('actions', attrs, actions)
		return response, cmd

	def badRequest(self, stanza):
		self.connection.connection.send(xmpp.Error(stanza, xmpp.NS_STANZAS + \
			' bad-request'))

	def cancel(self, request):
		response = self.buildResponse(request, status = 'canceled')[0]
		self.connection.connection.send(response)
		return False	# finish the session

class ChangeStatusCommand(AdHocCommand):
	commandnode = 'change-status'
	commandname = _('Change status information')

	@staticmethod
	def isVisibleFor(samejid):
		''' Change status is visible only if the entity has the same bare jid. '''
		return samejid

	def execute(self, request):
		# first query...
		response, cmd = self.buildResponse(request, defaultaction = 'execute',
			actions = ['execute'])

		cmd.addChild(node = dataforms.SimpleDataForm(
			title = _('Change status'),
			instructions = _('Set the presence type and description'),
			fields = [
				dataforms.Field('list-single',
					var = 'presence-type',
					label = 'Type of presence:',
					options = [
						(u'chat', _('Free for chat')),
						(u'online', _('Online')),
						(u'away', _('Away')),
						(u'xa', _('Extended away')),
						(u'dnd', _('Do not disturb')),
						(u'offline', _('Offline - disconnect'))],
					value = 'online',
					required = True),
				dataforms.Field('text-multi',
					var = 'presence-desc',
					label = _('Presence description:'))]))

		self.connection.connection.send(response)

		# for next invocation
		self.execute = self.changestatus

		return True	# keep the session

	def changestatus(self, request):
		# check if the data is correct
		try:
			form = dataforms.SimpleDataForm(extend = request.getTag('command').\
				getTag('x'))
		except Exception:
			self.badRequest(request)
			return False

		try:
			presencetype = form['presence-type'].value
			if not presencetype in \
			('chat', 'online', 'away', 'xa', 'dnd', 'offline'):
				self.badRequest(request)
				return False
		except Exception:	# KeyError if there's no presence-type field in form or
			# AttributeError if that field is of wrong type
			self.badRequest(request)
			return False

		try:
			presencedesc = form['presence-desc'].value
		except Exception:	# same exceptions as in last comment
			presencedesc = u''

		response, cmd = self.buildResponse(request, status = 'completed')
		cmd.addChild('note', {}, _('The status has been changed.'))

		# if going offline, we need to push response so it won't go into
		# queue and disappear
		self.connection.connection.send(response, now = presencetype == 'offline')

		# send new status
		gajim.interface.roster.send_status(self.connection.name, presencetype,
			presencedesc)

		return False	# finish the session

def find_current_groupchats(account):
	import message_control
	rooms = []
	for gc_control in gajim.interface.msg_win_mgr.get_controls(
	message_control.TYPE_GC) + gajim.interface.minimized_controls[account].\
	values():
		acct = gc_control.account
		# check if account is the good one
		if acct != account:
			continue
		room_jid = gc_control.room_jid
		nick = gc_control.nick
		if room_jid in gajim.gc_connected[acct] and \
		gajim.gc_connected[acct][room_jid]:
			rooms.append((room_jid, nick,))
	return rooms


class LeaveGroupchatsCommand(AdHocCommand):
	commandnode = 'leave-groupchats'
	commandname = _('Leave Groupchats')

	@staticmethod
	def isVisibleFor(samejid):
		''' Change status is visible only if the entity has the same bare jid. '''
		return samejid

	def execute(self, request):
		# first query...
		response, cmd = self.buildResponse(request, defaultaction = 'execute',
			actions=['execute'])
		options = []
		account = self.connection.name
		for gc in find_current_groupchats(account):
			options.append((u'%s' %(gc[0]), _('%(nickname)s on %(room_jid)s') % \
				{'nickname': gc[1], 'room_jid': gc[0]}))
		if not len(options):
			response, cmd = self.buildResponse(request, status = 'completed')
			cmd.addChild('note', {}, _('You have not joined a groupchat.'))

			self.connection.connection.send(response)
			return False

		cmd.addChild(node=dataforms.SimpleDataForm(
			title = _('Leave Groupchats'),
			instructions = _('Choose the groupchats you want to leave'),
			fields=[
				dataforms.Field('list-multi',
					var = 'groupchats',
					label = _('Groupchats'),
					options = options,
					required = True)]))

		self.connection.connection.send(response)

		# for next invocation
		self.execute = self.leavegroupchats

		return True	# keep the session

	def leavegroupchats(self, request):
		# check if the data is correct
		try:
			form = dataforms.SimpleDataForm(extend = request.getTag('command').\
				getTag('x'))
		except Exception:
			self.badRequest(request)
			return False

		try:
			gc = form['groupchats'].values
		except Exception:	# KeyError if there's no groupchats in form
			self.badRequest(request)
			return False
		account = self.connection.name
		try:
			for room_jid in gc:
				gc_control = gajim.interface.msg_win_mgr.get_gc_control(room_jid,
					account)
				if not gc_control:
					gc_control = gajim.interface.minimized_controls[account]\
						[room_jid]
					gc_control.shutdown()
					gajim.interface.roster.remove_groupchat(room_jid, account)
					continue
				gc_control.parent_win.remove_tab(gc_control, None, force = True)
		except Exception:	# KeyError if there's no such room opened
			self.badRequest(request)
			return False
		response, cmd = self.buildResponse(request, status = 'completed')
		note = _('You left the following groupchats:')
		for room_jid in gc:
			note += '\n\t' + room_jid
		cmd.addChild('note', {}, note)

		self.connection.connection.send(response)
		return False


class ForwardMessagesCommand(AdHocCommand):
	# http://www.xmpp.org/extensions/xep-0146.html#forward
	commandnode = 'forward-messages'
	commandname = _('Forward unread messages')

	@staticmethod
	def isVisibleFor(samejid):
		''' Change status is visible only if the entity has the same bare jid. '''
		return samejid

	def execute(self, request):
		account = self.connection.name
		# Forward messages
		events = gajim.events.get_events(account, types=['chat', 'normal'])
		j, resource = gajim.get_room_and_nick_from_fjid(self.jid)
		for jid in events:
			for event in events[jid]:
				self.connection.send_message(j, event.parameters[0], '',
					type_=event.type_, subject=event.parameters[1],
					resource=resource, forward_from=jid, delayed=event.time_)

		# Inform other client of completion
		response, cmd = self.buildResponse(request, status = 'completed')
		cmd.addChild('note', {}, _('All unread messages have been forwarded.'))

		self.connection.connection.send(response)

		return False	# finish the session

class ConnectionCommands:
	''' This class depends on that it is a part of Connection() class. '''
	def __init__(self):
		# a list of all commands exposed: node -> command class
		self.__commands = {}
		for cmdobj in (ChangeStatusCommand, ForwardMessagesCommand,
		LeaveGroupchatsCommand):
			self.__commands[cmdobj.commandnode] = cmdobj

		# a list of sessions; keys are tuples (jid, sessionid, node)
		self.__sessions = {}

	def getOurBareJID(self):
		return gajim.get_jid_from_account(self.name)

	def isSameJID(self, jid):
		''' Tests if the bare jid given is the same as our bare jid. '''
		return xmpp.JID(jid).getStripped() == self.getOurBareJID()

	def commandListQuery(self, con, iq_obj):
		iq = iq_obj.buildReply('result')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		q = iq.getTag('query')
		# buildReply don't copy the node attribute. Re-add it
		q.setAttr('node', xmpp.NS_COMMANDS)

		for node, cmd in self.__commands.iteritems():
			if cmd.isVisibleFor(self.isSameJID(jid)):
				q.addChild('item', {
					# TODO: find the jid
					'jid': self.getOurBareJID() + u'/' + self.server_resource,
					'node': node,
					'name': cmd.commandname})

		self.connection.send(iq)

	def commandInfoQuery(self, con, iq_obj):
		''' Send disco#info result for query for command (JEP-0050, example 6.).
		Return True if the result was sent, False if not. '''
		jid = helpers.get_full_jid_from_iq(iq_obj)
		node = iq_obj.getTagAttr('query', 'node')

		if node not in self.__commands: return False

		cmd = self.__commands[node]
		if cmd.isVisibleFor(self.isSameJID(jid)):
			iq = iq_obj.buildReply('result')
			q = iq.getTag('query')
			q.addChild('identity', attrs = {'type': 'command-node',
				'category': 'automation',
				'name': cmd.commandname})
			q.addChild('feature', attrs = {'var': xmpp.NS_COMMANDS})
			for feature in cmd.commandfeatures:
				q.addChild('feature', attrs = {'var': feature})

			self.connection.send(iq)
			return True

		return False

	def commandItemsQuery(self, con, iq_obj):
		''' Send disco#items result for query for command.
		Return True if the result was sent, False if not. '''
		jid = helpers.get_full_jid_from_iq(iq_obj)
		node = iq_obj.getTagAttr('query', 'node')

		if node not in self.__commands: return False

		cmd = self.__commands[node]
		if cmd.isVisibleFor(self.isSameJID(jid)):
			iq = iq_obj.buildReply('result')
			self.connection.send(iq)
			return True

		return False

	def _CommandExecuteCB(self, con, iq_obj):
		jid = helpers.get_full_jid_from_iq(iq_obj)

		cmd = iq_obj.getTag('command')
		if cmd is None: return

		node = cmd.getAttr('node')
		if node is None: return

		sessionid = cmd.getAttr('sessionid')
		if sessionid is None:
			# we start a new command session... only if we are visible for the jid
			# and command exist
			if node not in self.__commands.keys():
				self.connection.send(
					xmpp.Error(iq_obj, xmpp.NS_STANZAS + ' item-not-found'))
				raise xmpp.NodeProcessed

			newcmd = self.__commands[node]
			if not newcmd.isVisibleFor(self.isSameJID(jid)):
				return

			# generate new sessionid
			sessionid = self.connection.getAnID()

			# create new instance and run it
			obj = newcmd(conn = self, jid = jid, sessionid = sessionid)
			rc = obj.execute(iq_obj)
			if rc:
				self.__sessions[(jid, sessionid, node)] = obj
			raise xmpp.NodeProcessed
		else:
			# the command is already running, check for it
			magictuple = (jid, sessionid, node)
			if magictuple not in self.__sessions:
				# we don't have this session... ha!
				return

			action = cmd.getAttr('action')
			obj = self.__sessions[magictuple]

			try:
				if action == 'cancel':
					rc = obj.cancel(iq_obj)
				elif action == 'prev':
					rc = obj.prev(iq_obj)
				elif action == 'next':
					rc = obj.next(iq_obj)
				elif action == 'execute' or action is None:
					rc = obj.execute(iq_obj)
				elif action == 'complete':
					rc = obj.complete(iq_obj)
				else:
					# action is wrong. stop the session, send error
					raise AttributeError
			except AttributeError:
				# the command probably doesn't handle invoked action...
				# stop the session, return error
				del self.__sessions[magictuple]
				return

			# delete the session if rc is False
			if not rc:
				del self.__sessions[magictuple]

			raise xmpp.NodeProcessed

# vim: se ts=3:
