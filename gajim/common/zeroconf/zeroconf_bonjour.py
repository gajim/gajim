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
import re

from gajim.common.i18n import _
from gajim.common.zeroconf.zeroconf import Constant


log = logging.getLogger('gajim.c.z.zeroconf_bonjour')

try:
    from pybonjour import kDNSServiceErr_NoError
    from pybonjour import kDNSServiceErr_ServiceNotRunning
    from pybonjour import kDNSServiceErr_NameConflict
    from pybonjour import kDNSServiceInterfaceIndexAny
    from pybonjour import kDNSServiceType_TXT
    from pybonjour import kDNSServiceFlagsAdd
    from pybonjour import kDNSServiceFlagsNoAutoRename
    from pybonjour import BonjourError
    from pybonjour import TXTRecord
    from pybonjour import DNSServiceUpdateRecord
    from pybonjour import DNSServiceResolve
    from pybonjour import DNSServiceProcessResult
    from pybonjour import DNSServiceGetAddrInfo
    from pybonjour import DNSServiceQueryRecord
    from pybonjour import DNSServiceBrowse
    from pybonjour import DNSServiceRegister
except ImportError:
    pass

resolve_timeout = 1


class Zeroconf:
    def __init__(self, new_service_cb, remove_service_cb, name_conflict_cb,
                 _disconnected_cb, error_cb, name, host, port):
        self.stype = '_presence._tcp'
        self.port = port  # listening port that gets announced
        self.username = name
        self.host = host
        self.txt = {}  # service data
        self.name = None

        self.connected = False
        self.announced = False

        # XXX these CBs should be set to None when we destroy the object
        # (go offline), because they create a circular reference
        self._new_service_cb = new_service_cb
        self._remove_service_cb = remove_service_cb
        self._name_conflict_cb = name_conflict_cb
        self._error_cb = error_cb

        self._service_sdref = None
        self._browse_sdref = None

        self._contacts = {}  # all current local contacts with data
        self._invalid_self_contact = {}
        self._resolved_hosts = {}
        self._resolved = []
        self._queried = []

    def _browse_callback(self, _sdref, flags, interface, error_code,
                         service_name, regtype, reply_domain):
        log.debug('Found service %s in domain %s on %i(type: %s).',
                  service_name, reply_domain, interface, regtype)
        if not self.connected:
            return
        if error_code != kDNSServiceErr_NoError:
            log.debug('Error in browse_callback: %s', str(error_code))
            return
        if not flags & kDNSServiceFlagsAdd:
            self._remove_service_callback(service_name)
            return

        try:
            # asynchronous resolving
            resolve_sdref = None
            resolve_sdref = DNSServiceResolve(
                0, interface, service_name,
                regtype, reply_domain, self._service_resolved_callback)

            while not self._resolved:
                ready = select.select([resolve_sdref], [], [], resolve_timeout)
                if resolve_sdref not in ready[0]:
                    log.info('Resolve timed out')
                    break
                DNSServiceProcessResult(resolve_sdref)
            else:
                self._resolved.pop()

        except BonjourError as error:
            log.info('Error when resolving DNS: %s', error)

        finally:
            if resolve_sdref:
                resolve_sdref.close()

    def _remove_service_callback(self, name):
        log.info('Service %s disappeared.', name)
        if not self.connected:
            return
        if name != self.name:
            for key in list(self._contacts.keys()):
                if self._contacts[key][Constant.NAME] == name:
                    del self._contacts[key]
                    self._remove_service_cb(key)
                    return

    @staticmethod
    def txt_array_to_dict(txt):
        if not isinstance(txt, TXTRecord):
            txt = TXTRecord.parse(txt)
        return dict((v[0], v[1]) for v in txt)

    @staticmethod
    def _parse_name(fullname):
        log.debug('Parse name: %s', fullname)
        # TODO: do proper decoding...
        escaping = {r'\.': '.',
                    r'\032': ' ',
                    r'\064': '@',
                    }

        # Split on '.' but do not split on '\.'
        result = re.split(r'(?<!\\\\)\.', fullname)
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

    def _query_txt_callback(self, _sdref, _flags, _interface, error_code,
                            hosttarget, _rrtype, _rrclass, rdata, _ttl):

        if error_code != kDNSServiceErr_NoError:
            log.error('Error in query_record_callback: %s', str(error_code))
            return

        name = self._parse_name(hosttarget)[0]

        if name != self.name:
            # update TXT data only, as intended according to
            # resolve_all comment
            old_contact = self._contacts[name]
            self._contacts[name] = old_contact[0:Constant.TXT] + (rdata,) + old_contact[Constant.TXT+1:]
            log.debug(self._contacts[name])

        self._queried.append(True)

    def _getaddrinfo_callback(self, _sdref, _flags, interface, error_code,
                              hosttarget, address, _ttl):
        if error_code != kDNSServiceErr_NoError:
            log.error('Error in getaddrinfo_callback: %s', str(error_code))
            return

        fullname, port, txt_record = self._resolved_hosts[hosttarget]

        txt = TXTRecord.parse(txt_record)
        ip = address[1]

        name, bare_name, protocol, domain = self._parse_name(fullname)

        log.info('Service data for service %s on %i:',
                 fullname, interface)
        log.info('Host %s, ip %s, port %i, TXT data: %s',
                 hosttarget, ip, port, txt)

        if not self.connected:
            return

        # we don't want to see ourselves in the list
        if name != self.name:
            resolved_info = [(interface, protocol, hosttarget,
                              fullname, ip, port)]
            self._contacts[name] = (name, domain, resolved_info,
                                    bare_name, txt_record)

            self._new_service_cb(name)
        else:
            # remember data
            # In case this is not our own record but of another
            # gajim instance on the same machine,
            # it will be used when we get a new name.
            self._invalid_self_contact[name] = \
                (name, domain,
                 (interface, protocol, hosttarget, fullname, ip, port),
                 bare_name, txt_record)

        self._queried.append(True)

    def _service_resolved_callback(self, _sdref, _flags, interface,
                                   error_code, fullname, hosttarget, port,
                                   txt_record):
        if error_code != kDNSServiceErr_NoError:
            log.error('Error in service_resolved_callback: %s', str(error_code))
            return

        self._resolved_hosts[hosttarget] = (fullname, port, txt_record)

        try:
            getaddrinfo_sdref = \
                DNSServiceGetAddrInfo(
                    interfaceIndex=interface,
                    hostname=hosttarget,
                    callBack=self._getaddrinfo_callback)

            while not self._queried:
                ready = select.select(
                    [getaddrinfo_sdref], [], [], resolve_timeout)
                if getaddrinfo_sdref not in ready[0]:
                    log.warning('GetAddrInfo timed out')
                    break
                DNSServiceProcessResult(getaddrinfo_sdref)
            else:
                self._queried.pop()

        except BonjourError as error:
            if error.error_code == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                self._error_cb(_('Error while adding service. %s') % error)

        finally:
            if getaddrinfo_sdref:
                getaddrinfo_sdref.close()

        self._resolved.append(True)

    def service_added_callback(self, _sdref, _flags, error_code,
                               _name, _regtype, _domain):
        if error_code == kDNSServiceErr_NoError:
            log.info('Service successfully added')

        elif error_code == kDNSServiceErr_NameConflict:
            log.error('Error while adding service. %s', error_code)
            self._name_conflict_cb(self._get_alternativ_name(self.username))
        else:
            error = _('Error while adding service. %s') % str(error_code)
            self._error_cb(error)

    @staticmethod
    def _get_alternativ_name(name):
        if name[-2] == '-':
            try:
                number = int(name[-1])
            except Exception:
                return '%s-1' % name
            return '%s-%s' % (name[:-2], number + 1)
        return '%s-1' % name

    @staticmethod
    def _replace_show(show):
        if show in ['chat', 'online', '']:
            return 'avail'
        if show == 'xa':
            return 'away'
        return show

    def _create_service(self):
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
            txt['status'] = self._replace_show(self.txt['status'])
        else:
            txt['status'] = 'avail'
        self.txt = txt
        try:
            self._service_sdref = DNSServiceRegister(
                flags=kDNSServiceFlagsNoAutoRename,
                name=self.name,
                regtype=self.stype,
                port=self.port,
                txtRecord=TXTRecord(self.txt, strict=True),
                callBack=self.service_added_callback)

            log.info('Publishing service %s of type %s', self.name, self.stype)

            ready = select.select([self._service_sdref], [], [])
            if self._service_sdref in ready[0]:
                DNSServiceProcessResult(self._service_sdref)

        except BonjourError as error:
            if error.errorCode == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                self._error_cb(_('Error while adding service. %s') % error)
            self.disconnect()

    def announce(self):
        if not self.connected:
            return False

        self._create_service()
        self.announced = True
        return True

    def remove_announce(self):
        if not self.announced:
            return False

        if self._service_sdref is None:
            return False

        try:
            self._service_sdref.close()
            self.announced = False
            return True
        except BonjourError as error:
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
            if self._browse_sdref is not None:
                self._browse_sdref.close()
                self._browse_sdref = None
                self.remove_announce()

    def browse_domain(self, domain=None):
        try:
            self._browse_sdref = DNSServiceBrowse(
                regtype=self.stype,
                domain=domain,
                callBack=self._browse_callback)
            log.info('Starting to browse .local')
            return True
        except BonjourError as error:
            if error.errorCode == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
            else:
                log.error('Error while browsing for services. %s', error)
            return False

    def browse_loop(self):
        try:
            ready = select.select([self._browse_sdref], [], [], 0)
            if self._browse_sdref in ready[0]:
                DNSServiceProcessResult(self._browse_sdref)
        except BonjourError as error:
            if error.errorCode == kDNSServiceErr_ServiceNotRunning:
                log.info('Service not running')
                return False
            log.error('Error while browsing for services. %s', error)
        return True

    # resolve_all() is called every X seconds and queries for new clients
    # and monitors TXT records for changed status
    def resolve_all(self):
        if not self.connected:
            return False
        # for now put here as this is synchronous
        if not self.browse_loop():
            return False

        # Monitor TXT Records with DNSServiceQueryRecord because
        # its more efficient (see pybonjour documentation)
        for val in self._contacts.values():
            bare_name = val[Constant.RESOLVED_INFO][0][Constant.BARE_NAME]

            try:
                query_sdref = None
                query_sdref = \
                    DNSServiceQueryRecord(
                        interfaceIndex=kDNSServiceInterfaceIndexAny,
                        fullname=bare_name,
                        rrtype=kDNSServiceType_TXT,
                        callBack=self._query_txt_callback)

                while not self._queried:
                    ready = select.select(
                        [query_sdref], [], [], resolve_timeout)
                    if query_sdref not in ready[0]:
                        log.info('Query record timed out')
                        break
                    DNSServiceProcessResult(query_sdref)
                else:
                    self._queried.pop()

            except BonjourError as error:
                if error.errorCode == kDNSServiceErr_ServiceNotRunning:
                    log.info('Service not running')
                    return False
                log.error('Error in query for TXT records. %s', error)
            finally:
                if query_sdref:
                    query_sdref.close()

        return True

    def get_contacts(self):
        return self._contacts

    def get_contact(self, jid):
        if jid not in self._contacts:
            return None
        return self._contacts[jid]

    def update_txt(self, show=None):
        if show:
            self.txt['status'] = self._replace_show(show)

        txt = TXTRecord(self.txt, strict=True)
        try:
            DNSServiceUpdateRecord(self._service_sdref, None, 0, txt)
        except BonjourError as error:
            log.error('Error when updating TXT Record: %s', error)
            return False
        return True
