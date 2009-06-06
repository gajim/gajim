##      common/zeroconf/zeroconf_bonjour.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
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

from common import gajim
import select
import re
from common.zeroconf.zeroconf import C_BARE_NAME, C_DOMAIN

try:
	import pybonjour
except ImportError, e:
	pass


resolve_timeout  = 1

class Zeroconf:
	def __init__(self, new_serviceCB, remove_serviceCB, name_conflictCB,
		disconnected_CB, error_CB, name, host, port):
		self.domain = None   # specific domain to browse
		self.stype = '_presence._tcp'
		self.port = port  # listening port that gets announced
		self.username = name
		self.host = host
		self.txt = pybonjour.TXTRecord()		# service data

		# XXX these CBs should be set to None when we destroy the object
		# (go offline), because they create a circular reference
		self.new_serviceCB = new_serviceCB
		self.remove_serviceCB = remove_serviceCB
		self.name_conflictCB = name_conflictCB
		self.disconnected_CB = disconnected_CB
		self.error_CB = error_CB

		self.contacts = {}    # all current local contacts with data
		self.connected = False
		self.announced = False
		self.invalid_self_contact = {}
		self.resolved = []


	def browse_callback(self, sdRef, flags, interfaceIndex, errorCode, serviceName, regtype, replyDomain):
		gajim.log.debug('Found service %s in domain %s on %i(type: %s).' % (serviceName, replyDomain, interfaceIndex, regtype))
		if not self.connected:
		 	return
		if errorCode != pybonjour.kDNSServiceErr_NoError:
			return
		if not (flags & pybonjour.kDNSServiceFlagsAdd):
			self.remove_service_callback(serviceName)
			return

		# asynchronous resolving
		resolve_sdRef = pybonjour.DNSServiceResolve(0, interfaceIndex, serviceName, regtype, replyDomain, self.service_resolved_callback)

		try:
			while not self.resolved:
				ready = select.select([resolve_sdRef], [], [], resolve_timeout)
				if resolve_sdRef not in ready[0]:
					gajim.log.debug('Resolve timed out')
					break
				pybonjour.DNSServiceProcessResult(resolve_sdRef)
			else:
				self.resolved.pop()
		finally:
			resolve_sdRef.close()

	def remove_service_callback(self, name):
		gajim.log.debug('Service %s disappeared.' % name)
		if not self.connected:
		 	return
		if name != self.name:
			for key in self.contacts.keys():
				if self.contacts[key][C_BARE_NAME] == name:
					del self.contacts[key]
					self.remove_serviceCB(key)
					return

	def new_domain_callback(self,interface, protocol, domain, flags):
		if domain != "local":
			self.browse_domain(interface, protocol, domain)

	# takes a TXTRecord instance
	def txt_array_to_dict(self, txt):
		items = pybonjour.TXTRecord.parse(txt)._items
		return dict((v[0], v[1]) for v in items.values())

	def service_resolved_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname,
			hosttarget, port, txtRecord):

        # TODO: do proper decoding...
		escaping= {
		r'\.': '.',
		r'\032': ' ',
		r'\064': '@',
		}

		# Split on '.' but do not split on '\.'
		result = re.split('(?<!\\\\)\.', fullname)
		name = result[0]
		protocol, domain = result[2:4]

		# Replace the escaped values
		for src, trg in escaping.items():
			name = name.replace(src, trg)

		txt = pybonjour.TXTRecord.parse(txtRecord)

		gajim.log.debug('Service data for service %s on %i:' % (fullname, interfaceIndex))
		gajim.log.debug('Host %s, port %i, TXT data: %s' % (hosttarget, port, txt._items))

		if not self.connected:
			return

		bare_name = name
		if '@' not in name:
			name = name + '@' + name

		# we don't want to see ourselves in the list
		if name != self.name:
			self.contacts[name] = (name, domain, interfaceIndex, protocol, hosttarget, hosttarget, port, bare_name, txtRecord)

			self.new_serviceCB(name)
		else:
			# remember data
			# In case this is not our own record but of another
			# gajim instance on the same machine,
			# it will be used when we get a new name.
			self.invalid_self_contact[name] = (name, domain, interfaceIndex, protocol, hosttarget, hosttarget, port, bare_name, txtRecord)
		# count services
		self.resolved.append(True)

	# different handler when resolving all contacts
	def service_resolved_all_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname, hosttarget, port, txtRecord):
		if not self.connected:
			return

		escaping= {
		r'\.': '.',
		r'\032': ' ',
		r'\064': '@',
		}

		name, stype, protocol, domain, dummy = fullname.split('.')

		# Replace the escaped values
		for src, trg in escaping.items():
			name = name.replace(src, trg)

		bare_name = name
		if name.find('@') == -1:
			name = name + '@' + name

		# we don't want to see ourselves in the list
		if name != self.name:
			self.contacts[name] = (name, domain, interfaceIndex, protocol, hosttarget, hosttarget, port, bare_name, txtRecord)


	def service_added_callback(self, sdRef, flags, errorCode, name, regtype, domain):
		if errorCode == pybonjour.kDNSServiceErr_NoError:
			gajim.log.debug('Service successfully added')

	def service_add_fail_callback(self, err):
		if err[0][0] == pybonjour.kDNSServiceErr_NameConflict:
			gajim.log.debug('Error while adding service. %s' % str(err))
			parts = self.username.split(' ')

			#check if last part is a number and if, increment it
			try:
				stripped = str(int(parts[-1]))
			except Exception:
				stripped = 1
			alternative_name = self.username + str(stripped+1)
			self.name_conflictCB(alternative_name)
			return
		self.error_CB(_('Error while adding service. %s') % str(err))
		self.disconnect()

	# make zeroconf-valid names
	def replace_show(self, show):
		if show in ['chat', 'online', '']:
			return 'avail'
		elif show == 'xa':
			return 'away'
		return show

	def create_service(self):
		txt = {}

		#remove empty keys
		for key,val in self.txt:
			if val:
				txt[key] = val

		txt['port.p2pj'] = self.port
		txt['version'] = 1
		txt['txtvers'] = 1

      # replace gajim's show messages with compatible ones
		if 'status' in self.txt:
			txt['status'] = self.replace_show(self.txt['status'])
		else:
			txt['status'] = 'avail'

		self.txt = pybonjour.TXTRecord(txt, strict=True)

		try:
			sdRef = pybonjour.DNSServiceRegister(name = self.name,
		   	   	regtype = self.stype, port = self.port, txtRecord = self.txt,
				callBack = self.service_added_callback)
			self.service_sdRef = sdRef
		except pybonjour.BonjourError, e:
			self.service_add_fail_callback(e)
		else:
			gajim.log.debug('Publishing service %s of type %s' % (self.name, self.stype))

			ready = select.select([sdRef], [], [], resolve_timeout)
			if sdRef in ready[0]:
				pybonjour.DNSServiceProcessResult(sdRef)

	def announce(self):
		if not self.connected:
			return False

		self.create_service()
		self.announced = True
		return True

	def remove_announce(self):
		if not self.announced:
			return False
		try:
			self.service_sdRef.close()
			self.announced = False
			return True
		except pybonjour.BonjourError, e:
			gajim.log.debug(e)
			return False


	def connect(self):
		self.name = self.username + '@' + self.host # service name

		self.connected = True

		# start browsing
		if self.domain is None:
			# Explicitly browse .local
			self.browse_domain()

			# Browse for other browsable domains
			#self.domain_sdRef = pybonjour.DNSServiceEnumerateDomains(flags, interfaceIndex=0, callBack=self.new_domain_callback)

		else:
			self.browse_domain(self.domain)

		return True

	def disconnect(self):
		if self.connected:
			self.connected = False
			self.browse_sdRef.close()
			self.remove_announce()


	def browse_domain(self, domain=None):
		gajim.log.debug('starting to browse')
		try:
			self.browse_sdRef = pybonjour.DNSServiceBrowse(regtype=self.stype, domain=domain, callBack=self.browse_callback)
		except pybonjour.BonjourError, e:
			self.error_CB("Error while browsing: %s" % e)

	def browse_loop(self):
		ready = select.select([self.browse_sdRef], [], [], 2)
		if self.browse_sdRef in ready[0]:
			pybonjour.DNSServiceProcessResult(self.browse_sdRef)

	# refresh txt data of all contacts manually (no callback available)
	def resolve_all(self):
		if not self.connected:
			return

		# for now put here as this is synchronous
		self.browse_loop()

		for val in self.contacts.values():
			resolve_sdRef = pybonjour.DNSServiceResolve(0,
				pybonjour.kDNSServiceInterfaceIndexAny, val[C_BARE_NAME],
				self.stype + '.', val[C_DOMAIN] + '.',
				self.service_resolved_all_callback)

			try:
				ready = select.select([resolve_sdRef], [], [], resolve_timeout)
				if resolve_sdRef not in ready[0]:
					gajim.log.debug('Resolve timed out (in resolve_all)')
					break
				pybonjour.DNSServiceProcessResult(resolve_sdRef)
			finally:
				resolve_sdRef.close()

	def get_contacts(self):
		return self.contacts

	def get_contact(self, jid):
		if not jid in self.contacts:
			return None
		return self.contacts[jid]

	def update_txt(self, show = None):
		if show:
			self.txt['status'] = self.replace_show(show)

		try:
			pybonjour.DNSServiceUpdateRecord(self.service_sdRef, None, 0, self.txt)
		except pybonjour.BonjourError:
			return False
		return True


# vim: se ts=3:
