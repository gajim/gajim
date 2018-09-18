# Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
# Copyright (C) 2006 Philipp Hörist <philipp@hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
import select
import socket
import re
from gajim.common.zeroconf.zeroconf import Constant


log = logging.getLogger('gajim.c.z.zeroconf_bonjour')

try:
    import pybonjour
except ImportError:
    pass

resolve_timeout = 1


class Zeroconf:
    def __init__(self, new_serviceCB, remove_serviceCB, name_conflictCB,
                 disconnected_CB, error_CB, name, host, port):
        self.stype = '_presence._tcp'
        self.port = port  # listening port that gets announced
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

        self.contacts = {}  # all current local contacts with data
        self.connected = False
        self.announced = False
        self.invalid_self_contact = {}
        self.resolved_contacts = {}
        self.resolved = []
        self.queried = []

    def browse_callback(self, sdRef, flags, interfaceIndex, errorCode,
                        serviceName, regtype, replyDomain):
        log.debug('Found service %s in domain %s on %i(type: %s).',
                  serviceName, replyDomain, interfaceIndex, regtype)
        if not self.connected:
            return
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.debug('Error in browse_callback: %s', str(errorCode))
            return
        if not flags & pybonjour.kDNSServiceFlagsAdd:
            self.remove_service_callback(serviceName)
            return

        try:
            # asynchronous resolving
            resolve_sdRef = None
            resolve_sdRef = pybonjour.DNSServiceResolve(
                0, interfaceIndex, serviceName,
                regtype, replyDomain, self.service_resolved_callback)

            while not self.resolved:
                ready = select.select([resolve_sdRef], [], [], resolve_timeout)
                if resolve_sdRef not in ready[0]:
                    log.info('Resolve timed out')
                    break
                pybonjour.DNSServiceProcessResult(resolve_sdRef)
            else:
                self.resolved.pop()

        except pybonjour.BonjourError as error:
            log.info('Error when resolving DNS: %s', error)

        finally:
            if resolve_sdRef:
                resolve_sdRef.close()

    def remove_service_callback(self, name):
        log.info('Service %s disappeared.', name)
        if not self.connected:
            return
        if name != self.name:
            for key in list(self.contacts.keys()):
                if self.contacts[key][Constant.NAME] == name:
                    del self.contacts[key]
                    self.remove_serviceCB(key)
                    return

    def txt_array_to_dict(self, txt):
        if isinstance(txt, pybonjour.TXTRecord):
            items = txt._items
        else:
            items = pybonjour.TXTRecord.parse(txt)._items
        return dict((v[0], v[1]) for v in items.values())

    @staticmethod
    def _parse_name(fullname):
        log.debug('Parse name: %s', fullname)
        # TODO: do proper decoding...
        escaping = {r'\.': '.',
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

        bare_name = name
        if '@' not in name:
            name = name + '@' + name
        log.debug('End parse: %s %s %s %s',
                  name, bare_name, protocol, domain)

        return name, bare_name, protocol, domain

    def query_txt_callback(self, sdRef, flags, interfaceIndex, errorCode,
                           hosttarget, rrtype, rrclass, rdata, ttl):

        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.error('Error in query_record_callback: %s', str(errorCode))
            return

        name = self._parse_name(hosttarget)[0]

        if name != self.name:
            # update TXT data only, as intended according to
            # resolve_all comment
            old_contact = self.contacts[name]
            self.contacts[name] = old_contact[0:Constant.TXT] + (rdata,) + old_contact[Constant.TXT+1:]
            log.debug(self.contacts[name])

        self.queried.append(True)

    def query_record_callback(self, sdRef, flags, interfaceIndex, errorCode,
                              hosttarget, rrtype, rrclass, rdata, ttl):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.error('Error in query_record_callback: %s', str(errorCode))
            return

        fullname, port, txtRecord = self.resolved_contacts[hosttarget]

        txt = pybonjour.TXTRecord.parse(txtRecord)
        ip = socket.inet_ntoa(rdata)

        name, bare_name, protocol, domain = self._parse_name(fullname)

        log.info('Service data for service %s on %i:',
                 fullname, interfaceIndex)
        log.info('Host %s, ip %s, port %i, TXT data: %s',
                 hosttarget, ip, port, txt._items)

        if not self.connected:
            return

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

    def service_resolved_callback(self, sdRef, flags, interfaceIndex,
                                  errorCode, fullname, hosttarget, port,
                                  txtRecord):

        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.error('Error in service_resolved_callback: %s', str(errorCode))
            return

        self.resolved_contacts[hosttarget] = (fullname, port, txtRecord)

        try:
            query_sdRef = None
            query_sdRef = \
                pybonjour.DNSServiceQueryRecord(
                    interfaceIndex=interfaceIndex,
                    fullname=hosttarget,
                    rrtype=pybonjour.kDNSServiceType_A,
                    callBack=self.query_record_callback)

            while not self.queried:
                ready = select.select([query_sdRef], [], [], resolve_timeout)
                if query_sdRef not in ready[0]:
                    log.warning('Query record timed out')
                    break
                pybonjour.DNSServiceProcessResult(query_sdRef)
            else:
                self.queried.pop()

        except pybonjour.BonjourError as error:
            if error.errorCode == pybonjour.kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                self.error_CB(_('Error while adding service. %s') % error)

        finally:
            if query_sdRef:
                query_sdRef.close()

        self.resolved.append(True)

    def service_added_callback(self, sdRef, flags, errorCode,
                               name, regtype, domain):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            log.info('Service successfully added')

        elif errorCode == pybonjour.kDNSServiceErr_NameConflict:
            log.error('Error while adding service. %s', errorCode)
            parts = self.username.split(' ')

            # check if last part is a number and if, increment it
            try:
                stripped = str(int(parts[-1]))
            except Exception:
                stripped = 1
            alternative_name = self.username + str(stripped + 1)
            self.name_conflictCB(alternative_name)
        else:
            self.error_CB(_('Error while adding service. %s') % str(errorCode))

    # make zeroconf-valid names
    def replace_show(self, show):
        if show in ['chat', 'online', '']:
            return 'avail'
        if show == 'xa':
            return 'away'
        return show

    def create_service(self):
        txt = {}

        # remove empty keys
        for key, val in self.txt.items():
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
        self.txt = txt
        try:
            self.service_sdRef = pybonjour.DNSServiceRegister(
                name=self.name,
                regtype=self.stype,
                port=self.port,
                txtRecord=pybonjour.TXTRecord(self.txt, strict=True),
                callBack=self.service_added_callback)

            log.info('Publishing service %s of type %s', self.name, self.stype)

            ready = select.select([self.service_sdRef], [], [])
            if self.service_sdRef in ready[0]:
                pybonjour.DNSServiceProcessResult(self.service_sdRef)

        except pybonjour.BonjourError as error:
            if error.errorCode == pybonjour.kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                self.error_CB(_('Error while adding service. %s') % error)
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
        except pybonjour.BonjourError as error:
            log.error('Error when removing announce: %s', error)
            return False

    def connect(self):
        self.name = self.username + '@' + self.host  # service name

        self.connected = True

        # start browsing
        if self.browse_domain():
            return True

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
                regtype=self.stype,
                domain=domain,
                callBack=self.browse_callback)
            log.info('Starting to browse .local')
            return True
        except pybonjour.BonjourError as error:
            if error.errorCode == pybonjour.kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                log.error('Error while browsing for services. %s', error)
            return False

    def browse_loop(self):
        try:
            ready = select.select([self.browse_sdRef], [], [], 0)
            if self.browse_sdRef in ready[0]:
                pybonjour.DNSServiceProcessResult(self.browse_sdRef)
        except pybonjour.BonjourError as error:
            if error.errorCode == pybonjour.kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
                return False
            log.error('Error while browsing for services. %s', error)
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
                query_sdRef = None
                query_sdRef = \
                    pybonjour.DNSServiceQueryRecord(
                        interfaceIndex=pybonjour.kDNSServiceInterfaceIndexAny,
                        fullname=val[Constant.RESOLVED_INFO][0][Constant.BARE_NAME],
                        rrtype=pybonjour.kDNSServiceType_TXT,
                        callBack=self.query_txt_callback)

                while not self.queried:
                    ready = select.select(
                        [query_sdRef], [], [], resolve_timeout)
                    if query_sdRef not in ready[0]:
                        log.info('Query record timed out')
                        break
                    pybonjour.DNSServiceProcessResult(query_sdRef)
                else:
                    self.queried.pop()

            except pybonjour.BonjourError as error:
                if error.errorCode == pybonjour.kDNSServiceErr_ServiceNotRunning:
                    log.info('Service not running')
                    return False
                log.error('Error in query for TXT records. %s', error)
            finally:
                if query_sdRef:
                    query_sdRef.close()

        return True

    def get_contacts(self):
        return self.contacts

    def get_contact(self, jid):
        if jid not in self.contacts:
            return None
        return self.contacts[jid]

    def update_txt(self, show=None):
        if show:
            self.txt['status'] = self.replace_show(show)

        txt = pybonjour.TXTRecord(self.txt, strict=True)
        try:
            pybonjour.DNSServiceUpdateRecord(self.service_sdRef, None, 0, txt)
        except pybonjour.BonjourError as e:
            log.error('Error when updating TXT Record: %s', e)
            return False
        return True
