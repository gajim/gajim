##      common/zeroconf/zeroconf.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
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

import os
import sys
import socket
from common import gajim
from common import xmpp

try:
	import avahi, gobject, dbus
except ImportError:
	gajim.log.debug('Error: python-avahi and python-dbus need to be installed. No zeroconf support.')

try:
	import dbus.glib
except ImportError, e:
	pass


C_NAME, C_DOMAIN, C_INTERFACE, C_PROTOCOL, C_HOST, \
C_ADDRESS, C_PORT, C_BARE_NAME, C_TXT = range(9)

class Zeroconf:
	def __init__(self, new_serviceCB, remove_serviceCB, name_conflictCB, 
		disconnected_CB, error_CB, name, host, port):
		self.server = None
		self.domain = None   # specific domain to browse
		self.stype = '_presence._tcp'	
		self.port = port  # listening port that gets announced	
		self.username = name
		self.host = host
		self.txt = {}		# service data
		
		#XXX these CBs should be set to None when we destroy the object 
		# (go offline), because they create a circular reference 
		self.new_serviceCB = new_serviceCB
		self.remove_serviceCB = remove_serviceCB
		self.name_conflictCB = name_conflictCB
		self.disconnected_CB = disconnected_CB
		self.error_CB = error_CB
		
		self.service_browser = None
		self.domain_browser = None
		self.server = None
		self.contacts = {}    # all current local contacts with data
		self.entrygroup = None
		self.connected = False
		self.announced = False
		self.invalid_self_contact = {}


	## handlers for dbus callbacks
	def entrygroup_commit_error_CB(self, err):
		# left for eventual later use
		pass
	
	def error_callback1(self, err):
		gajim.log.debug('RR' + str(err))
	
	def error_callback(self, err):
		gajim.log.debug(str(err))
		# timeouts are non-critical
		if str(err) != 'Timeout reached':
			self.disconnect()
			self.disconnected_CB()

	def new_service_callback(self, interface, protocol, name, stype, domain, flags):
		gajim.log.debug('Found service %s in domain %s on %i.%i.' % (name, domain, interface, protocol))
		# if not self.connected:
		# 	return
		
		# synchronous resolving
		self.server.ResolveService( int(interface), int(protocol), name, stype, \
					domain, avahi.PROTO_UNSPEC, dbus.UInt32(0), \
					reply_handler=self.service_resolved_callback, error_handler=self.error_callback1)

	def remove_service_callback(self, interface, protocol, name, stype, domain, flags):
		gajim.log.debug('Service %s in domain %s on %i.%i disappeared.' % (name, domain, interface, protocol))
		# if not self.connected:
		# 	return
		if name != self.name:
			for key in self.contacts.keys():
				if self.contacts[key][C_BARE_NAME] == name:
					del self.contacts[key]
					self.remove_serviceCB(key)
					return

	def new_service_type(self, interface, protocol, stype, domain, flags):
		# Are we already browsing this domain for this type? 
		if self.service_browser:
			return

		object_path = self.server.ServiceBrowserNew(interface, protocol, \
				stype, domain, dbus.UInt32(0))
		
		self.service_browser = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, \
			object_path) , avahi.DBUS_INTERFACE_SERVICE_BROWSER)
		self.service_browser.connect_to_signal('ItemNew', self.new_service_callback)
		self.service_browser.connect_to_signal('ItemRemove', self.remove_service_callback)
		self.service_browser.connect_to_signal('Failure', self.error_callback)

	def new_domain_callback(self,interface, protocol, domain, flags):
		if domain != "local":
			self.browse_domain(interface, protocol, domain)

	def txt_array_to_dict(self,txt_array):
		items = {}

		for byte_array in txt_array:
			# 'str' is used for string type in python
			value = avahi.byte_array_to_string(byte_array)
			poseq = value.find('=')
			items[value[:poseq]] = value[poseq+1:]
		return items
	
	def service_resolved_callback(self, interface, protocol, name, stype, domain, host, aprotocol, address, port, txt, flags):	
		gajim.log.debug('Service data for service %s in domain %s on %i.%i:' % (name, domain, interface, protocol))
		gajim.log.debug('Host %s (%s), port %i, TXT data: %s' % (host, address, port, avahi.txt_array_to_string_array(txt)))
		if not self.connected:
			return
		bare_name = name
		if name.find('@') == -1:
			name = name + '@' + name
		
		# we don't want to see ourselves in the list
		if name != self.name:
			self.contacts[name] = (name, domain, interface, protocol, host, address, port, 
					bare_name, txt)
			self.new_serviceCB(name)
		else:
			# remember data
			# In case this is not our own record but of another
			# gajim instance on the same machine,
			# it will be used when we get a new name.
			self.invalid_self_contact[name] = (name, domain, interface, protocol, host, address, port, bare_name, txt)


	# different handler when resolving all contacts
	def service_resolved_all_callback(self, interface, protocol, name, stype, domain, host, aprotocol, address, port, txt, flags):
		if not self.connected:
			return
		bare_name = name
		if name.find('@') == -1:
			name = name + '@' + name
		self.contacts[name] = (name, domain, interface, protocol, host, address, port, bare_name, txt)

	def service_added_callback(self):
		gajim.log.debug('Service successfully added')

	def service_committed_callback(self):
		gajim.log.debug('Service successfully committed')

	def service_updated_callback(self):
		gajim.log.debug('Service successfully updated')

	def service_add_fail_callback(self, err):
		gajim.log.debug('Error while adding service. %s' % str(err))
		if str(err) == 'Local name collision':
			alternative_name = self.server.GetAlternativeServiceName(self.username)
			self.name_conflictCB(alternative_name)
		else:
			self.error_CB(_('Error while adding service. %s') % str(err))
		self.disconnect()

	def server_state_changed_callback(self, state, error):
		print 'server.state %s' % state
		if state == avahi.SERVER_RUNNING:
			self.create_service()
		elif state == avahi.SERVER_COLLISION:
			self.entrygroup.Reset()
		elif state == avahi.CLIENT_FAILURE:           # TODO: add error handling (avahi daemon dies...?)
			print 'CLIENT FAILURE'

	def entrygroup_state_changed_callback(self, state, error):
		# the name is already present, so recreate
		if state == avahi.ENTRY_GROUP_COLLISION:
			self.service_add_fail_callback('Local name collision, recreating.')
		elif state == avahi.ENTRY_GROUP_FAILURE:
			print 'zeroconf.py: ENTRY_GROUP_FAILURE reached(that should not happen)'

	# make zeroconf-valid names
	def replace_show(self, show):
		if show in ['chat', 'online', '']:
			return 'avail'
		elif show == 'xa':
			return 'away'
		return show

	def create_service(self):
		try:
			if not self.entrygroup:
				# create an EntryGroup for publishing
				self.entrygroup = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, self.server.EntryGroupNew()), avahi.DBUS_INTERFACE_ENTRY_GROUP)
				self.entrygroup.connect_to_signal('StateChanged', self.entrygroup_state_changed_callback)
			
			txt = {}
			
			#remove empty keys
			for key,val in self.txt.iteritems():
				if val:
					txt[key] = val
			
			txt['port.p2pj'] = self.port
			txt['version'] = 1
			txt['txtvers'] = 1

			# replace gajim's show messages with compatible ones
			if self.txt.has_key('status'):
				txt['status'] = self.replace_show(self.txt['status'])
			else:
				txt['status'] = 'avail'

			self.txt = txt
			gajim.log.debug('Publishing service %s of type %s' % (self.name, self.stype))
			self.entrygroup.AddService(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0), self.name, self.stype, '', '', self.port, avahi.dict_to_txt_array(self.txt), reply_handler=self.service_added_callback, error_handler=self.service_add_fail_callback)
			self.entrygroup.Commit(reply_handler=self.service_committed_callback, 
				error_handler=self.entrygroup_commit_error_CB)

			return True
		
		except dbus.dbus_bindings.DBusException, e:
			gajim.log.debug(str(e))
			return False
			
	def announce(self):
		if not self.connected:
			return False

		state = self.server.GetState()
		if state == avahi.SERVER_RUNNING:
			self.create_service()
			self.announced = True
			return True

	def remove_announce(self):
		if self.announced == False:
			return False
		try:
			if self.entrygroup.GetState() != avahi.ENTRY_GROUP_FAILURE:
				self.entrygroup.Reset()
				self.entrygroup.Free()
				self.entrygroup = None
				self.announced = False
				return True
			else:
				return False
		except dbus.dbus_bindings.DBusException, e:
			gajim.log.debug("Can't remove service. That should not happen")

	def browse_domain(self, interface, protocol, domain):
		self.new_service_type(interface, protocol, self.stype, domain, '')

	def avahi_dbus_connect_cb(self, a, connect, disconnect):
		if connect != "":
			gajim.log.debug('Lost connection to avahi-daemon')
			try:
				self.connected = False
				self.disconnect()
				self.disconnected_CB()
			except Exception, e:
				print e
		else:
			gajim.log.debug('We are connected to avahi-daemon')
			
			
			
	# connect to dbus
	def connect_dbus(self):
		if self.server:
			return True
		try:
			self.bus = dbus.SystemBus()
			self.bus.add_signal_receiver(self.avahi_dbus_connect_cb, 
				"NameOwnerChanged", "org.freedesktop.DBus", 
				arg0="org.freedesktop.Avahi")
			self.server = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, \
			avahi.DBUS_PATH_SERVER), avahi.DBUS_INTERFACE_SERVER)
			self.server.connect_to_signal('StateChanged', 
				self.server_state_changed_callback)
		except Exception, e:
			# Avahi service is not present
			self.server = None
			gajim.log.debug(str(e))
			return False
		else:
			return True

	def connect(self):
		self.name = self.username + '@' + self.host # service name
		if not self.connect_dbus():
			return False
		
		self.connected = True
		# start browsing
		if self.domain is None:
			# Explicitly browse .local
			self.browse_domain(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, "local")

			# Browse for other browsable domains
			self.domain_browser = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, \
					self.server.DomainBrowserNew(avahi.IF_UNSPEC, \
					avahi.PROTO_UNSPEC, '', avahi.DOMAIN_BROWSER_BROWSE,\
					dbus.UInt32(0))), avahi.DBUS_INTERFACE_DOMAIN_BROWSER)
			self.domain_browser.connect_to_signal('ItemNew', self.new_domain_callback)
			self.domain_browser.connect_to_signal('Failure', self.error_callback)
		else:
			self.browse_domain(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, domain)
		
		return True

	def disconnect(self):
		if self.connected:
			self.connected = False
			if self.service_browser:
				self.service_browser.Free()
			if self.domain_browser:
				self.domain_browser.Free()
			self.remove_announce()
		self.service_browser = None
		self.domain_browser = None
		self.server = None

	# refresh txt data of all contacts manually (no callback available)
	def resolve_all(self):
		for val in self.contacts.values():
			self.server.ResolveService(int(val[C_INTERFACE]), int(val[C_PROTOCOL]), val[C_BARE_NAME], \
				self.stype, val[C_DOMAIN], avahi.PROTO_UNSPEC, dbus.UInt32(0),\
				reply_handler=self.service_resolved_all_callback, error_handler=self.error_callback)

	def get_contacts(self):
		return self.contacts

	def get_contact(self, jid):
		return self.contacts[jid]
		
	def update_txt(self, show = None):
		if show:
			self.txt['status'] = self.replace_show(show)

		txt = avahi.dict_to_txt_array(self.txt)
		if self.connected and self.entrygroup:
			self.entrygroup.UpdateServiceTxt(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0), self.name, self.stype,'', txt, reply_handler=self.service_updated_callback, error_handler=self.error_callback)
			return True
		else:
			return False


# END Zeroconf

'''
# how to use
		
	zeroconf = Zeroconf()
	zeroconf.connect()				
	zeroconf.txt['1st'] = 'foo'
	zeroconf.txt['last'] = 'bar'
	zeroconf.txt['email'] = foo@bar.org
	zeroconf.announce()

	# updating after announcing
	txt = {}
	txt['status'] = 'avail'
	txt['msg'] = 'Here I am'
	zeroconf.update_txt(txt)
'''
