# Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

import logging

from gi.repository import Avahi
from gi.repository import Gio
from gi.repository import GLib

from gajim.common.i18n import _
from gajim.common.zeroconf.zeroconf import Constant, ConstantRI
from gajim.common.zeroconf.zeroconf_avahi_const import DBUS_NAME
from gajim.common.zeroconf.zeroconf_avahi_const import DBUS_INTERFACE_SERVER
from gajim.common.zeroconf.zeroconf_avahi_const import DBUS_INTERFACE_ENTRY_GROUP
from gajim.common.zeroconf.zeroconf_avahi_const import DBUS_INTERFACE_DOMAIN_BROWSER
from gajim.common.zeroconf.zeroconf_avahi_const import ServerState
from gajim.common.zeroconf.zeroconf_avahi_const import EntryGroup
from gajim.common.zeroconf.zeroconf_avahi_const import DomainBrowser
from gajim.common.zeroconf.zeroconf_avahi_const import Protocol
from gajim.common.zeroconf.zeroconf_avahi_const import Interface

log = logging.getLogger('gajim.c.z.zeroconf_avahi')


class Zeroconf:
    def __init__(self, new_serviceCB, remove_serviceCB, name_conflictCB,
            disconnected_CB, error_CB, name, host, port):
        self.domain = None   # specific domain to browse
        self.stype = '_presence._tcp'
        self.port = port  # listening port that gets announced
        self.username = name
        self.host = host
        self.txt = {}           # service data

        #XXX these CBs should be set to None when we destroy the object
        # (go offline), because they create a circular reference
        self.new_serviceCB = new_serviceCB
        self.remove_serviceCB = remove_serviceCB
        self.name_conflictCB = name_conflictCB
        self.disconnected_CB = disconnected_CB
        self.error_CB = error_CB

        self.service_browser = None
        self.sb_connections = []
        self.connections = {}
        self.domain_browser = None
        self.server = None
        self.contacts = {}    # all current local contacts with data
        self.entrygroup = None
        self.connected = False
        self.announced = False
        self.invalid_self_contact = {}


    ## handlers for dbus callbacks
    def entrygroup_commit_error_CB(self, err):
        # left blank for possible later usage
        pass

    def _call(self, proxy, method_name):
        try:
            output = proxy.call_sync(
                method_name, None, Gio.DBusCallFlags.NONE, -1, None)
            if output:
                return output[0]
        except GLib.Error as e:
            log.debug(str(e))

    def error_callback1(self, err):
        log.debug('Error while resolving: %s', str(err))

    def error_callback(self, err):
        log.debug(str(err))
        # timeouts are non-critical
        if str(err) != 'Timeout reached':
            self.disconnect()
            self.disconnected_CB()

    def new_service_callback(self, browser, interface, protocol, name, stype,
                             domain, flags):
        log.debug('Found service %s in domain %s on %i.%i.',
                  name, domain, interface, protocol)
        if not self.connected:
            return

        # synchronous resolving
        try:
            output = self.server.call_sync(
                'ResolveService',
                GLib.Variant('(iisssiu)', (interface, protocol, name, stype,
                                           domain, Protocol.UNSPEC, 0)),
                Gio.DBusCallFlags.NONE, -1, None)
            self.service_resolved_callback(*output)
        except GLib.Error as e:
            self.error_callback1(e)

    def remove_service_callback(self, browser, interface, protocol, name,
                                stype, domain, flags):
        log.debug('Service %s in domain %s on %i.%i disappeared.',
                  name, domain, interface, protocol)
        if not self.connected:
            return
        if name == self.name:
            return

        for key in list(self.contacts.keys()):
            val = self.contacts[key]
            if val[Constant.BARE_NAME] == name:
                # try to reduce instead of delete first
                resolved_info = val[Constant.RESOLVED_INFO]
                if len(resolved_info) > 1:
                    for i, _info in enumerate(resolved_info):
                        if resolved_info[i][ConstantRI.INTERFACE] == interface and resolved_info[i][ConstantRI.PROTOCOL] == protocol:
                            del self.contacts[key][Constant.RESOLVED_INFO][i]
                    # if still something left, don't remove
                    if len(self.contacts[key][Constant.RESOLVED_INFO]) > 1:
                        return
                del self.contacts[key]
                self.remove_serviceCB(key)
                return

    def new_service_type(self, interface, protocol, stype, domain, flags):
        # Are we already browsing this domain for this type?
        if self.service_browser:
            return

        self.service_browser = Avahi.ServiceBrowser.new_full(
            interface, protocol, stype, domain, 0)

        self.avahi_client = Avahi.Client(flags=0,)
        self.avahi_client.start()
        con = self.service_browser.connect('new_service', self.new_service_callback)
        self.sb_connections.append(con)
        con = self.service_browser.connect('removed_service', self.remove_service_callback)
        self.sb_connections.append(con)
        con = self.service_browser.connect('failure', self.error_callback)
        self.sb_connections.append(con)

        self.service_browser.attach(self.avahi_client)

    def new_domain_callback(self, interface, protocol, domain, flags):
        if domain != 'local':
            self.browse_domain(interface, protocol, domain)

    def txt_array_to_dict(self, txt_array):
        txt_dict = {}
        for array in txt_array:
            item = bytes(array)
            item = item.decode('utf-8')
            item = item.split('=', 1)

            if item[0] and (item[0] not in txt_dict):
                if len(item) == 1:
                    txt_dict[item[0]] = None
                else:
                    txt_dict[item[0]] = item[1]

        return txt_dict

    def dict_to_txt_array(self, txt_dict):
        array = []

        for k, v in txt_dict.items():
            item = '%s=%s' % (k, v)
            item = item.encode('utf-8')
            array.append(item)

        return array

    def service_resolved_callback(self, interface, protocol, name, stype, domain,
    host, aprotocol, address, port, txt, flags):
        log.debug('Service data for service %s in domain %s on %i.%i:',
                  name, domain, interface, protocol)
        log.debug('Host %s (%s), port %i, TXT data: %s',
                  host, address, port, self.txt_array_to_dict(txt))
        if not self.connected:
            return
        bare_name = name
        if name.find('@') == -1:
            name = name + '@' + name

        # we don't want to see ourselves in the list
        if name != self.name:
            resolved_info = [(interface, protocol, host, aprotocol, address, int(port))]
            if name in self.contacts:
                # Decide whether to try to merge with existing resolved info:
                old_name, old_domain, old_resolved_info, old_bare_name, _old_txt = self.contacts[name]
                if name == old_name and domain == old_domain and bare_name == old_bare_name:
                    # Seems similar enough, try to merge resolved info:
                    for i, _info in enumerate(old_resolved_info):
                        # for now, keep a single record for each (interface, protocol) pair
                        #
                        # Note that, theoretically, we could both get IPv4 and
                        # IPv6 aprotocol responses via the same protocol,
                        # so this probably needs to be revised again.
                        if old_resolved_info[i][0:2] == (interface, protocol):
                            log.debug('Deleting resolved info for interface %s',
                                      old_resolved_info[i])
                            del old_resolved_info[i]
                            break
                    resolved_info = resolved_info + old_resolved_info
                    log.debug('Collected resolved info is now: %s',
                              resolved_info)
            self.contacts[name] = (name, domain, resolved_info, bare_name, txt)
            self.new_serviceCB(name)
        else:
            # remember data
            # In case this is not our own record but of another
            # gajim instance on the same machine,
            # it will be used when we get a new name.
            self.invalid_self_contact[name] = (name, domain,
                    (interface, protocol, host, aprotocol, address, int(port)),
                    bare_name, txt)

    # different handler when resolving all contacts
    def service_resolved_all_callback(self, interface, protocol, name, stype,
                                      domain, host, aprotocol, address, port,
                                      txt, flags):
        if not self.connected:
            return

        if name.find('@') == -1:
            name = name + '@' + name
        # update TXT data only, as intended according to resolve_all comment
        old_contact = self.contacts[name]
        self.contacts[name] = old_contact[0:Constant.TXT] + (txt,) + old_contact[Constant.TXT+1:]

    def service_updated_callback(self):
        log.debug('Service successfully updated')

    def service_add_fail_callback(self, err):
        log.debug('Error while adding service. %s', str(err))
        if 'Local name collision' in str(err):
            alternative_name = self.server.call_sync(
                'GetAlternativeServiceName',
                GLib.Variant('(s)', (self.username,)),
                Gio.DBusCallFlags.NONE, -1, None)
            self.name_conflictCB(alternative_name[0])
            return
        self.error_CB(_('Error while adding service. %s') % str(err))
        self.disconnect()

    def server_state_changed_callback(self, connection, sender_name,
                                      object_path, interface_name,
                                      signal_name, parameters):
        state, _ = parameters
        log.debug('server state changed to %s', state)
        if state == ServerState.RUNNING:
            self.create_service()
        elif state in (ServerState.COLLISION,
                       ServerState.REGISTERING):
            self.disconnect()
            if self.entrygroup:
                self._call(self.entrygroup, 'Reset')

    def entrygroup_state_changed_callback(self, connection, sender_name,
                                          object_path, interface_name,
                                          signal_name, parameters):
        state, _ = parameters
        # the name is already present, so recreate
        if state == EntryGroup.COLLISION:
            log.debug('zeroconf.py: local name collision')
            self.service_add_fail_callback('Local name collision')
        elif state == EntryGroup.FAILURE:
            self.disconnect()
            self._call(self.entrygroup, 'Reset')
            log.debug('zeroconf.py: ENTRY_GROUP_FAILURE reached(that'
                    ' should not happen)')

    # make zeroconf-valid names
    def replace_show(self, show):
        if show in ['chat', 'online', '']:
            return 'avail'
        if show == 'xa':
            return 'away'
        return show

    def avahi_txt(self):
        return self.dict_to_txt_array(self.txt)

    def create_service(self):
        try:
            if not self.entrygroup:
                # create an EntryGroup for publishing
                object_path = self.server.call_sync(
                    'EntryGroupNew', None, Gio.DBusCallFlags.NONE, -1, None)

                self.entrygroup = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                    DBUS_NAME, *object_path, DBUS_INTERFACE_ENTRY_GROUP, None)

                connection = self.entrygroup.get_connection()
                subscription = connection.signal_subscribe(
                    DBUS_NAME, DBUS_INTERFACE_ENTRY_GROUP, 'StateChanged',
                    *object_path, None, Gio.DBusSignalFlags.NONE,
                    self.entrygroup_state_changed_callback)

                self.connections[connection] = [subscription]

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
            log.debug('Publishing service %s of type %s',
                      self.name, self.stype)

            try:
                self.entrygroup.call_sync(
                    'AddService',
                    GLib.Variant('(iiussssqaay)', (Interface.UNSPEC,
                                                   Protocol.UNSPEC, 0,
                                                   self.name, self.stype, '',
                                                   '', self.port,
                                                   self.avahi_txt())),
                    Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error as e:
                self.service_add_fail_callback(e)
                return False

            try:
                self.entrygroup.call_sync('Commit', None,
                                          Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error as e:
                self.entrygroup_commit_error_CB(e)

            return True
        except GLib.Error as e:
            log.debug(str(e))
            return False

    def announce(self):
        if not self.connected:
            return False

        state = self.server.call_sync(
            'GetState', None, Gio.DBusCallFlags.NONE, -1, None)

        if state[0] == ServerState.RUNNING:
            if self.create_service():
                self.announced = True
                return True
            return False

    def remove_announce(self):
        if self.announced is False:
            return False

        if self._call(self.entrygroup, 'GetState') != EntryGroup.FAILURE:
            self._call(self.entrygroup, 'Reset')
            self._call(self.entrygroup, 'Free')
            self.entrygroup = None
            self.announced = False

            return True
        return False

    def browse_domain(self, interface, protocol, domain):
        self.new_service_type(interface, protocol, self.stype, domain, '')

    def avahi_dbus_connect_cb(self, connection, sender_name, object_path,
                              interface_name, signal_name, parameters):
        name, oldOwner, newOwner = parameters
        if name == DBUS_NAME:
            if newOwner and not oldOwner:
                log.debug('We are connected to avahi-daemon')
            else:
                log.debug('Lost connection to avahi-daemon')
                self.disconnect()
                if self.disconnected_CB:
                    self.disconnected_CB()

    # connect to dbus
    def connect_dbus(self):
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', None)

            connection = proxy.get_connection()
            subscription = connection.signal_subscribe(
                'org.freedesktop.DBus', 'org.freedesktop.DBus',
                'NameOwnerChanged', '/org/freedesktop/DBus', None,
                Gio.DBusSignalFlags.NONE, self.avahi_dbus_connect_cb)
            self.connections[connection] = [subscription]
        except GLib.Error as e:
            log.debug(str(e))
            return False
        else:
            return True

    # connect to avahi
    def connect_avahi(self):
        if not self.connect_dbus():
            return False

        if self.server:
            return True
        try:
            self.server = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                DBUS_NAME, '/', DBUS_INTERFACE_SERVER, None)

            connection = self.server.get_connection()
            subscription = connection.signal_subscribe(
                DBUS_NAME, DBUS_INTERFACE_SERVER, 'StateChanged', '/', None,
                Gio.DBusSignalFlags.NONE, self.server_state_changed_callback)
            self.connections[connection] = [subscription]
        except Exception as e:
            # Avahi service is not present
            self.server = None
            log.debug(str(e))
            return False
        else:
            return True

    def connect(self):
        self.name = self.username + '@' + self.host # service name
        if not self.connect_avahi():
            return False

        self.connected = True
        # start browsing
        if self.domain is None:
            # Explicitly browse .local
            self.browse_domain(
                Interface.UNSPEC, Protocol.UNSPEC, 'local')

            # Browse for other browsable domains
            object_path = self.server.call_sync(
                'DomainBrowserNew',
                GLib.Variant('(iisiu)', (Interface.UNSPEC, Protocol.UNSPEC, '',
                                         DomainBrowser.BROWSE, 0)),
                Gio.DBusCallFlags.NONE, -1, None)

            self.domain_browser = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None, DBUS_NAME,
                *object_path, DBUS_INTERFACE_DOMAIN_BROWSER, None)

            connection = self.domain_browser.get_connection()
            subscription = connection.signal_subscribe(
                DBUS_NAME, DBUS_INTERFACE_DOMAIN_BROWSER, 'ItemNew',
                *object_path, None, Gio.DBusSignalFlags.NONE,
                self.new_domain_callback)
            self.connections[connection] = [subscription]

            subscription = connection.signal_subscribe(
                DBUS_NAME, DBUS_INTERFACE_DOMAIN_BROWSER, 'Failure',
                *object_path, None, Gio.DBusSignalFlags.NONE,
                self.error_callback)
            self.connections[connection].append(subscription)
        else:
            self.browse_domain(
                Interface.UNSPEC, Protocol.UNSPEC, self.domain)

        return True

    def disconnect(self):
        if self.connected:
            self.connected = False
            for connection, subscriptions in self.connections.items():
                for subscription in subscriptions:
                    connection.signal_unsubscribe(subscription)
            for con in self.sb_connections:
                self.service_browser.disconnect(con)
            if self.domain_browser:
                self._call(self.domain_browser, 'Free')
            self.remove_announce()
        self.server = None
        self.service_browser = None
        self.domain_browser = None

    # refresh txt data of all contacts manually (no callback available)
    def resolve_all(self):
        if not self.connected:
            return False
        for val in self.contacts.values():
            # get txt data from last recorded resolved info
            # TODO: Better try to get it from last IPv6 mDNS, then last IPv4?
            ri = val[Constant.RESOLVED_INFO][0]
            output = self.server.call_sync(
                'ResolveService',
                GLib.Variant('(iisssiu)', (ri[ConstantRI.INTERFACE], ri[ConstantRI.PROTOCOL],
                                           val[Constant.BARE_NAME], self.stype, val[Constant.DOMAIN],
                                           Protocol.UNSPEC, 0)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
                )
            self.service_resolved_all_callback(*output)

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

        txt = self.avahi_txt()
        if self.connected and self.entrygroup:
            try:
                self.entrygroup.call_sync(
                    'UpdateServiceTxt',
                    GLib.Variant('(iiusssaay)', (Interface.UNSPEC,
                                                 Protocol.UNSPEC, 0, self.name,
                                                 self.stype, '', txt)),
                    Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error as e:
                self.error_callback(e)
                return False

            return True
        return False
