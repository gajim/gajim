##	common/zeroconf/connection_zeroconf.py
##
## Contributors for this file:
##	- Yann Leboulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
## - Stefan Bethge <stefan@lanpartei.de>
##
## Copyright (C) 2003-2004 Yann Leboulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2006 Yann Leboulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##                    Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##


import os
import random
random.seed()

import signal
if os.name != 'nt':
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import getpass
import gobject

from common.connection import CommonConnection
from common import gajim
from common import GnuPG
from common.zeroconf import client_zeroconf
from common.zeroconf import zeroconf
from connection_handlers_zeroconf import *

class ConnectionZeroconf(CommonConnection, ConnectionHandlersZeroconf):
	def __init__(self, name):
		ConnectionHandlersZeroconf.__init__(self)
		# system username
		self.username = None
		self.server_resource = '' # zeroconf has no resource, fake an empty one
		self.is_zeroconf = True
		self.call_resolve_timeout = False
		# we don't need a password, but must be non-empty
		self.password = 'zeroconf'
		self.autoconnect = False

		CommonConnection.__init__(self, name)

	def get_config_values_or_default(self):
		"""
		Get name, host, port from config, or create zeroconf account with default
		values
		"""
		if not gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'name'):
			gajim.log.debug('Creating zeroconf account')
			gajim.config.add_per('accounts', gajim.ZEROCONF_ACC_NAME)
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'autoconnect', True)
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'no_log_for',
				'')
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'password',
				'zeroconf')
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'sync_with_global_status', True)

			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'custom_port', 5298)
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'is_zeroconf', True)
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'use_ft_proxies', False)
		#XXX make sure host is US-ASCII
		self.host = unicode(socket.gethostname())
		gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'hostname',
			self.host)
		self.port = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'custom_port')
		self.autoconnect = gajim.config.get_per('accounts',
			gajim.ZEROCONF_ACC_NAME, 'autoconnect')
		self.sync_with_global_status = gajim.config.get_per('accounts',
			gajim.ZEROCONF_ACC_NAME, 'sync_with_global_status')
		self.first = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'zeroconf_first_name')
		self.last = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'zeroconf_last_name')
		self.jabber_id = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'zeroconf_jabber_id')
		self.email = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'zeroconf_email')

		if not self.username:
			self.username = unicode(getpass.getuser())
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'name',
				self.username)
		else:
			self.username = gajim.config.get_per('accounts',
				gajim.ZEROCONF_ACC_NAME, 'name')
	# END __init__

	def check_jid(self, jid):
		return jid

	def _reconnect(self):
		# Do not try to reco while we are already trying
		self.time_to_reconnect = None
		gajim.log.debug('reconnect')

		self.disconnect()
		self.change_status(self.old_show, self.status)

	def disable_account(self):
		self.disconnect()

	def _on_resolve_timeout(self):
		if self.connected:
			self.connection.resolve_all()
			diffs = self.roster.getDiffs()
			for key in diffs:
				self.roster.setItem(key)
				self.dispatch('ROSTER_INFO', (key, self.roster.getName(key),
							'both', 'no', self.roster.getGroups(key)))
				self.dispatch('NOTIFY', (key, self.roster.getStatus(key),
							self.roster.getMessage(key), 'local', 0, None, 0, None))
				#XXX open chat windows don't get refreshed (full name), add that
		return self.call_resolve_timeout

	# callbacks called from zeroconf
	def _on_new_service(self, jid):
		self.roster.setItem(jid)
		self.dispatch('ROSTER_INFO', (jid, self.roster.getName(jid), 'both', 'no',
			self.roster.getGroups(jid)))
		self.dispatch('NOTIFY', (jid, self.roster.getStatus(jid),
			self.roster.getMessage(jid), 'local', 0, None, 0, None))

	def _on_remove_service(self, jid):
		self.roster.delItem(jid)
		# 'NOTIFY' (account, (jid, status, status message, resource, priority,
		# keyID, timestamp, contact_nickname))
		self.dispatch('NOTIFY', (jid, 'offline', '', 'local', 0, None, 0, None))

	def _disconnectedReconnCB(self):
		"""
		Called when we are disconnected. Comes from network manager for example
		we don't try to reconnect, network manager will tell us when we can
		"""
		if gajim.account_is_connected(self.name):
			# we cannot change our status to offline or connecting
			# after we auth to server
			self.old_show = STATUS_LIST[self.connected]
		self.connected = 0
		self.dispatch('STATUS', 'offline')
		# random number to show we wait network manager to send us a reconenct
		self.time_to_reconnect = 5
		self.on_purpose = False

	def _on_name_conflictCB(self, alt_name):
		self.disconnect()
		self.dispatch('STATUS', 'offline')
		self.dispatch('ZC_NAME_CONFLICT', alt_name)

	def _on_error(self, message):
		self.dispatch('ERROR', (_('Avahi error'),
			_('%s\nLink-local messaging might not work properly.') % message))

	def connect(self, show='online', msg=''):
		self.get_config_values_or_default()
		if not self.connection:
			self.connection = client_zeroconf.ClientZeroconf(self)
			if not zeroconf.test_zeroconf():
				self.dispatch('STATUS', 'offline')
				self.status = 'offline'
				self.dispatch('CONNECTION_LOST',
					(_('Could not connect to "%s"') % self.name,
					_('Please check if Avahi or Bonjour is installed.')))
				self.disconnect()
				return
			result = self.connection.connect(show, msg)
			if not result:
				self.dispatch('STATUS', 'offline')
				self.status = 'offline'
				if result is False:
					self.dispatch('CONNECTION_LOST',
						(_('Could not start local service'),
						_('Unable to bind to port %d.' % self.port)))
				else: # result is None
					self.dispatch('CONNECTION_LOST',
					(_('Could not start local service'),
					_('Please check if avahi-daemon is running.')))
				self.disconnect()
				return
		else:
			self.connection.announce()
		self.roster = self.connection.getRoster()
		self.dispatch('ROSTER', self.roster)

		# display contacts already detected and resolved
		for jid in self.roster.keys():
			self.dispatch('ROSTER_INFO', (jid, self.roster.getName(jid), 'both',
				'no', self.roster.getGroups(jid)))
			self.dispatch('NOTIFY', (jid, self.roster.getStatus(jid),
				self.roster.getMessage(jid), 'local', 0, None, 0, None))

		self.connected = STATUS_LIST.index(show)

		# refresh all contacts data every five seconds
		self.call_resolve_timeout = True
		gobject.timeout_add_seconds(5, self._on_resolve_timeout)
		return True

	def disconnect(self, on_purpose=False):
		self.connected = 0
		self.time_to_reconnect = None
		if self.connection:
			self.connection.disconnect()
			self.connection = None
			# stop calling the timeout
			self.call_resolve_timeout = False

	def reannounce(self):
		if self.connected:
			txt = {}
			txt['1st'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'zeroconf_first_name')
			txt['last'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'zeroconf_last_name')
			txt['jid'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'zeroconf_jabber_id')
			txt['email'] = gajim.config.get_per('accounts',
				gajim.ZEROCONF_ACC_NAME, 'zeroconf_email')
			self.connection.reannounce(txt)

	def update_details(self):
		if self.connection:
			port = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'custom_port')
			if port != self.port:
				self.port = port
				last_msg = self.connection.last_msg
				self.disconnect()
				if not self.connect(self.status, last_msg):
					return
				if self.status != 'invisible':
					self.connection.announce()
			else:
				self.reannounce()

	def connect_and_init(self, show, msg, sign_msg):
		# to check for errors from zeroconf
		check = True
		if not self.connect(show, msg):
			return
		if show != 'invisible':
			check = self.connection.announce()
		else:
			self.connected = STATUS_LIST.index(show)
		self.dispatch('SIGNED_IN', ())

		# stay offline when zeroconf does something wrong
		if check:
			self.dispatch('STATUS', show)
		else:
			# show notification that avahi or system bus is down
			self.dispatch('STATUS', 'offline')
			self.status = 'offline'
			self.dispatch('CONNECTION_LOST',
				(_('Could not change status of account "%s"') % self.name,
				_('Please check if avahi-daemon is running.')))

	def _change_to_invisible(self, msg):
		if self.connection.remove_announce():
			self.dispatch('STATUS', 'invisible')
		else:
			# show notification that avahi or system bus is down
			self.dispatch('STATUS', 'offline')
			self.status = 'offline'
			self.dispatch('CONNECTION_LOST',
				(_('Could not change status of account "%s"') % self.name,
				_('Please check if avahi-daemon is running.')))

	def _change_from_invisible(self):
		self.connection.announce()

	def _update_status(self, show, msg):
		if self.connection.set_show_msg(show, msg):
			self.dispatch('STATUS', show)
		else:
			# show notification that avahi or system bus is down
			self.dispatch('STATUS', 'offline')
			self.status = 'offline'
			self.dispatch('CONNECTION_LOST',
				(_('Could not change status of account "%s"') % self.name,
				_('Please check if avahi-daemon is running.')))

	def send_message(self, jid, msg, keyID, type_='chat', subject='',
	chatstate=None, msg_id=None, composing_xep=None, resource=None,
	user_nick=None, xhtml=None, session=None, forward_from=None, form_node=None,
	original_message=None, delayed=None, callback=None, callback_args=[]):

		def on_send_ok(msg_id):
			self.dispatch('MSGSENT', (jid, msg, keyID))
			if callback:
				callback(msg_id, *callback_args)

			self.log_message(jid, msg, forward_from, session, original_message,
				subject, type_)

		def on_send_not_ok(reason):
			reason += ' ' + _('Your message could not be sent.')
			self.dispatch('MSGERROR', [jid, -1, reason, None, None, session])

		def cb(jid, msg, keyID, forward_from, session, original_message, subject,
		type_, msg_iq):
			ret = self.connection.send(msg_iq, msg is not None, on_ok=on_send_ok,
				on_not_ok=on_send_not_ok)

			if ret == -1:
				# Contact Offline
				self.dispatch('MSGERROR', [jid, -1, _('Contact is offline. Your '
					'message could not be sent.'), None, None, session])

		self._prepare_message(jid, msg, keyID, type_=type_, subject=subject,
			chatstate=chatstate, msg_id=msg_id, composing_xep=composing_xep,
			resource=resource, user_nick=user_nick, xhtml=xhtml, session=session,
			forward_from=forward_from, form_node=form_node,
			original_message=original_message, delayed=delayed, callback=cb)

	def send_stanza(self, stanza):
		# send a stanza untouched
		if not self.connection:
			return
		if not isinstance(stanza, common.xmpp.Node):
			stanza = common.xmpp.Protocol(node=stanza)
		self.connection.send(stanza)

	def _event_dispatcher(self, realm, event, data):
		CommonConnection._event_dispatcher(self, realm, event, data)
		if realm == '':
			if event == common.xmpp.transports_nb.DATA_ERROR:
				thread_id = data[1]
				frm = unicode(data[0])
				session = self.get_or_create_session(frm, thread_id)
				self.dispatch('MSGERROR', [frm, -1,
	            _('Connection to host could not be established: Timeout while '
					'sending data.'), None, None, session])

# END ConnectionZeroconf

# vim: se ts=3:
