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
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from common import gajim
import logging
import select
import socket
import re
from common.zeroconf.zeroconf import C_BARE_NAME, C_DOMAIN, C_TXT, C_RESOLVED_INFO

log = logging.getLogger('gajim.c.z.zeroconf_bonjour')

try:
    import pybonjour
except ImportError, e:
    pass

kDNSServiceErr_ServiceNotRunning = -65563
C_RI_FULLNAME = 3

resolve_timeout = 1

class Zeroconf:
    def __init__(self, new_serviceCB, remove_serviceCB, name_conflictCB,
            disconnected_CB, error_CB, name, host, port):
        self.stype = '_presence._tcp'
        self.port = port # listening port that gets announced
        self.username = name
        self.host = host
        self.txt = {}  # service data

        # XXX these CBs should be set to None when we destroy the object
        # (go offline), because they create a circular reference
        self.new_serviceCB = new_serviceCB
        self.remove_serviceCB = remove_serviceCB
        self.name_conflictCB = name_conflictCB
        self.disconnected_CB = disconnected_CB
        self.error_CB = error_CB

        self.contacts = {} # all current local contacts with data
        self.connected = False
        self.announced = False
        self.invalid_self_contact = {}
        self.resolved_contacts = {}
        self.resolved = []
        self.queried = []

    def browse_callback(self, sdRef, flags, interfaceIndex, errorCode, serviceName, regtype, replyDomain):
        log.debug('Found service %s in domain %s on %i(type: %s).' % (serviceName, replyDomain, interfaceIndex, regtype))
        if not self.connected:
            return
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.debug('Error in browse_callback: %s', str(errorCode))
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
                    log.info('Resolve timed out')
                    break
                pybonjour.DNSServiceProcessResult(resolve_sdRef)
            else:
                self.resolved.pop()
        finally:
            resolve_sdRef.close()

    def remove_service_callback(self, name):
        log.info('Service %s disappeared.' % name)
        if not self.connected:
            return
        if name != self.name:
            for key in self.contacts.keys():
                if self.contacts[key][C_BARE_NAME] == name:
                    del self.contacts[key]
                    self.remove_serviceCB(key)
                    return

    # takes a TXTRecord instance
    def txt_array_to_dict(self, txt):
        items = pybonjour.TXTRecord.parse(txt)._items
        return dict((v[0], v[1]) for v in items.values())

    def query_txt_callback(self, sdRef, flags, interfaceIndex, errorCode, hosttarget,
                          rrtype, rrclass, rdata, ttl):

        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.error('Error in query_record_callback: %s', str(errorCode))
            return

        result = re.split('(?<!\\\\)\.', hosttarget)
        name = result[0]

        if name != self.name:
            # update TXT data only, as intended according to resolve_all comment
            old_contact = self.contacts[name]
            self.contacts[name] = old_contact[0:C_TXT] + (rdata,) + old_contact[C_TXT+1:]
            log.debug(self.contacts[name])

        self.queried.append(True)

    def query_record_callback(self, sdRef, flags, interfaceIndex, errorCode, hosttarget,
                          rrtype, rrclass, rdata, ttl):

        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.error('Error in query_record_callback: %s', str(errorCode))
            return

        fullname, port, txtRecord = self.resolved_contacts[hosttarget]

        # TODO: do proper decoding...
        escaping = {
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
        ip = socket.inet_ntoa(rdata)

        log.info('Service data for service %s on %i:'
            % (fullname, interfaceIndex))
        log.info('Host %s, ip %s, port %i, TXT data: %s'
            % (hosttarget, ip, port, txt._items))

        if not self.connected:
            return

        bare_name = name
        if '@' not in name:
            name = name + '@' + name

        # we don't want to see ourselves in the list
        if name != self.name:
            resolved_info = [(interfaceIndex, protocol, hosttarget, fullname, ip, port)]
            self.contacts[name] = (name, domain, resolved_info, bare_name, txtRecord)

            self.new_serviceCB(name)
        else:
            # remember data
            # In case this is not our own record but of another
            # gajim instance on the same machine,
            # it will be used when we get a new name.
            self.invalid_self_contact[name] = \
                (name, domain,
                 (interfaceIndex, protocol, hosttarget, fullname, ip, port),
                 bare_name, txtRecord)

        self.queried.append(True)

    def service_resolved_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname,
                    hosttarget, port, txtRecord):

        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.error('Error in service_resolved_callback: %s', str(errorCode))
            return

        self.resolved_contacts[hosttarget] = (fullname, port, txtRecord)

        try:
            query_sdRef = \
                pybonjour.DNSServiceQueryRecord(interfaceIndex = interfaceIndex,
                                                fullname = hosttarget,
                                                rrtype = pybonjour.kDNSServiceType_A,
                                                callBack = self.query_record_callback)

            while not self.queried:
                ready = select.select([query_sdRef], [], [], resolve_timeout)
                if query_sdRef not in ready[0]:
                    print 'Query record timed out'
                    break
                pybonjour.DNSServiceProcessResult(query_sdRef)
            else:
                self.queried.pop()

        except pybonjour.BonjourError, e:
            if e[0][0] == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                self.error_CB(_('Error while adding service. %s') % str(e[0][0]))

        finally:
            query_sdRef.close()

        self.resolved.append(True)

    def service_added_callback(self, sdRef, flags, errorCode, name, regtype, domain):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            log.info('Service successfully added')

        elif errorCode == pybonjour.kDNSServiceErr_NameConflict:
            log.error('Error while adding service. %s' % str(err))
            parts = self.username.split(' ')

            #check if last part is a number and if, increment it
            try:
                stripped = str(int(parts[-1]))
            except Exception:
                stripped = 1
            alternative_name = self.username + str(stripped+1)
            self.name_conflictCB(alternative_name)
        else:
            self.error_CB(_('Error while adding service. %s') % str(err))

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
        for key, val in self.txt.iteritems():
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

        try:
            self.service_sdRef = pybonjour.DNSServiceRegister(
                name=self.name,
                regtype=self.stype,
                port=self.port,
                txtRecord=pybonjour.TXTRecord(txt),
                callBack=self.service_added_callback)

            log.info('Publishing service %s of type %s' % (self.name, self.stype))

            ready = select.select([self.service_sdRef], [], [])
            if self.service_sdRef in ready[0]:
                pybonjour.DNSServiceProcessResult(self.service_sdRef)

        except pybonjour.BonjourError, e:
            if e[0][0] == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                self.error_CB(_('Error while adding service. %s') % str(e[0][0]))
            self.disconnect()

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
            log.debug(e)
            return False

    def connect(self):
        self.name = self.username + '@' + self.host # service name

        self.connected = True

        # start browsing
        if self.browse_domain():
            return True
        else:
            self.disconnect()
            return False

    def disconnect(self):
        if self.connected:
            self.connected = False
            if hasattr(self, 'browse_sdRef'):
                self.browse_sdRef.close()
                self.remove_announce()

    def browse_domain(self, domain=None):
        try:
            self.browse_sdRef = pybonjour.DNSServiceBrowse(
                regtype=self.stype, domain=domain, callBack=self.browse_callback)
            log.info('Starting to browse .local')
            return True
        except pybonjour.BonjourError, e:
            if e[0][0] == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                log.error('Error while browsing for services. %s', str(e[0][0]))
            return False

    def browse_loop(self):
        try:
            ready = select.select([self.browse_sdRef], [], [], 0)
            if self.browse_sdRef in ready[0]:
                pybonjour.DNSServiceProcessResult(self.browse_sdRef)
        except pybonjour.BonjourError, e:
            if e[0][0] == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
                return False
            else:
                log.error('Error while browsing for services. %s',
                          str(e[0][0]))
        return True

    # resolve_all() is called every X seconds and querys for new clients
    # and monitors TXT records for changed status
    def resolve_all(self):
        if not self.connected:
            return False
        # for now put here as this is synchronous
        if not self.browse_loop():
            return False

        # Monitor TXT Records with DNSServiceQueryRecord because
        # its more efficient (see pybonjour documentation)
        for val in self.contacts.values():
            try:
                query_sdRef = \
                    pybonjour.DNSServiceQueryRecord(
                        interfaceIndex=pybonjour.kDNSServiceInterfaceIndexAny,
                        fullname=val[C_RESOLVED_INFO][0][C_RI_FULLNAME],
                        rrtype=pybonjour.kDNSServiceType_TXT,
                        callBack=self.query_txt_callback)

                while not self.queried:
                    ready = select.select([query_sdRef], [], [], resolve_timeout)
                    if query_sdRef not in ready[0]:
                        log.info('Query record timed out')
                        break
                    pybonjour.DNSServiceProcessResult(query_sdRef)
                else:
                    self.queried.pop()

            except pybonjour.BonjourError, e:
                if e[0][0] == kDNSServiceErr_ServiceNotRunning:
                    log.info('Service not running')
                    return False
                else:
                    log.error('Error in query for TXT records. %s',
                              str(e[0][0]))
            finally:
                    query_sdRef.close()

        return True

    def get_contacts(self):
        return self.contacts

    def get_contact(self, jid):
        if not jid in self.contacts:
            return None
        return self.contacts[jid]

    def update_txt(self, show=None):
        if show:
            self.txt['status'] = self.replace_show(show)

        try:
            pybonjour.DNSServiceUpdateRecord(self.service_sdRef, None, 0, self.txt)
        except pybonjour.BonjourError:
            return False
        return True
