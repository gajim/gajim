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
    def __init__(self, new_service_cb, remove_service_cb, name_conflict_cb,
                 disconnected_cb, error_cb, name, host, port):
        self.domain = None   # specific domain to browse
        self.stype = '_presence._tcp'
        self.port = port  # listening port that gets announced
        self.username = name
        self.host = host
        self.txt = {}
        self.name = None

        self.connected = False
        self.announced = False

        #XXX these CBs should be set to None when we destroy the object
        # (go offline), because they create a circular reference
        self._new_service_cb = new_service_cb
        self._remove_service_cb = remove_service_cb
        self._name_conflict_cb = name_conflict_cb
        self._disconnected_cb = disconnected_cb
        self._error_cb = error_cb

        self._server = None
        self._avahi_client = None
        self._service_browser = None
        self._domain_browser = None
        self._entrygroup = None

        self._sb_connections = []
        self._connections = {}

        self._contacts = {}
        self._invalid_self_contact = {}

    @staticmethod
    def _call(proxy, method_name):
        try:
            output = proxy.call_sync(
                method_name, None, Gio.DBusCallFlags.NONE, -1, None)
            if output:
                return output[0]
        except GLib.Error as error:
            log.debug(error)
        return None

    def _error_callback(self, error):
        log.debug(error)
        # timeouts are non-critical
        if str(error) != 'Timeout reached':
            self.disconnect()
            self._disconnected_cb()

    def _new_service_callback(self, _browser, interface, protocol, name, stype,
                              domain, _flags):
        log.debug('Found service %s in domain %s on %i.%i.',
                  name, domain, interface, protocol)
        if not self.connected:
            return

        # synchronous resolving
        try:
            output = self._server.call_sync(
                'ResolveService',
                GLib.Variant('(iisssiu)', (interface, protocol, name, stype,
                                           domain, Protocol.UNSPEC, 0)),
                Gio.DBusCallFlags.NONE, -1, None)
            self.service_resolved_callback(*output)
        except GLib.Error as error:
            log.debug('Error while resolving: %s', error)

    def _remove_service_callback(self, _browser, interface, protocol, name,
                                 _stype, domain, _flags):
        log.debug('Service %s in domain %s on %i.%i disappeared.',
                  name, domain, interface, protocol)
        if not self.connected:
            return
        if name == self.name:
            return

        for key in list(self._contacts.keys()):
            val = self._contacts[key]
            if val[Constant.BARE_NAME] == name:
                # try to reduce instead of delete first
                resolved_info = val[Constant.RESOLVED_INFO]
                if len(resolved_info) > 1:
                    for i, _info in enumerate(resolved_info):
                        if resolved_info[i][ConstantRI.INTERFACE] == interface and resolved_info[i][ConstantRI.PROTOCOL] == protocol:
                            del self._contacts[key][Constant.RESOLVED_INFO][i]
                    # if still something left, don't remove
                    if len(self._contacts[key][Constant.RESOLVED_INFO]) > 1:
                        return
                del self._contacts[key]
                self._remove_service_cb(key)
                return

    def _new_service_type(self, interface, protocol, stype, domain, _flags):
        # Are we already browsing this domain for this type?
        if self._service_browser:
            return

        self._service_browser = Avahi.ServiceBrowser.new_full(
            interface, protocol, stype, domain, 0)

        self._avahi_client = Avahi.Client(flags=0,)
        self._avahi_client.start()
        con = self._service_browser.connect('new_service',
                                            self._new_service_callback)
        self._sb_connections.append(con)
        con = self._service_browser.connect('removed_service',
                                            self._remove_service_callback)
        self._sb_connections.append(con)
        con = self._service_browser.connect('failure', self._error_callback)
        self._sb_connections.append(con)

        self._service_browser.attach(self._avahi_client)

    def _new_domain_callback(self, interface, protocol, domain, _flags):
        if domain != 'local':
            self._browse_domain(interface, protocol, domain)

    @staticmethod
    def txt_array_to_dict(txt_array):
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

    @staticmethod
    def dict_to_txt_array(txt_dict):
        array = []

        for key, value in txt_dict.items():
            item = '%s=%s' % (key, value)
            item = item.encode('utf-8')
            array.append(item)

        return array

    def service_resolved_callback(self, interface, protocol, name, _stype,
                                  domain, host, aprotocol, address, port, txt,
                                  _flags):
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
            resolved_info = [(interface, protocol, host,
                              aprotocol, address, int(port))]
            if name in self._contacts:
                # Decide whether to try to merge with existing resolved info:
                old_name, old_domain, old_resolved_info, old_bare_name, _old_txt = self._contacts[name]
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
            self._contacts[name] = (name, domain, resolved_info, bare_name, txt)
            self._new_service_cb(name)
        else:
            # remember data
            # In case this is not our own record but of another
            # gajim instance on the same machine,
            # it will be used when we get a new name.
            self._invalid_self_contact[name] = (
                name,
                domain,
                (interface, protocol, host, aprotocol, address, int(port)),
                bare_name,
                txt)

    def _service_resolved_all_callback(self, _interface, _protocol, name,
                                       _stype, _domain, _host, _aprotocol,
                                       _address, _port, txt, _flags):
        if not self.connected:
            return

        if name.find('@') == -1:
            name = name + '@' + name
        # update TXT data only, as intended according to resolve_all comment
        old_contact = self._contacts[name]
        self._contacts[name] = old_contact[0:Constant.TXT] + (txt,) + old_contact[Constant.TXT+1:]

    def _service_add_fail_callback(self, err):
        log.debug('Error while adding service. %s', str(err))
        if 'Local name collision' in str(err):
            alternative_name = self._server.call_sync(
                'GetAlternativeServiceName',
                GLib.Variant('(s)', (self.username,)),
                Gio.DBusCallFlags.NONE, -1, None)
            self._name_conflict_cb(alternative_name[0])
            return
        self._error_cb(_('Error while adding service. %s') % str(err))
        self.disconnect()

    def _server_state_changed_callback(self, _connection, _sender_name,
                                       _object_path, _interface_name,
                                       _signal_name, parameters):
        state, _ = parameters
        log.debug('server state changed to %s', state)
        if state == ServerState.RUNNING:
            self._create_service()
        elif state in (ServerState.COLLISION,
                       ServerState.REGISTERING):
            self.disconnect()
            if self._entrygroup:
                self._call(self._entrygroup, 'Reset')

    def _entrygroup_state_changed_callback(self, _connection, _sender_name,
                                           _object_path, _interface_name,
                                           _signal_name, parameters):
        state, _ = parameters
        # the name is already present, so recreate
        if state == EntryGroup.COLLISION:
            log.debug('zeroconf.py: local name collision')
            self._service_add_fail_callback('Local name collision')
        elif state == EntryGroup.FAILURE:
            self.disconnect()
            self._call(self._entrygroup, 'Reset')
            log.debug('zeroconf.py: ENTRY_GROUP_FAILURE reached (that '
                      'should not happen)')

    @staticmethod
    def _replace_show(show):
        if show in ['chat', 'online', '']:
            return 'avail'
        if show == 'xa':
            return 'away'
        return show

    def avahi_txt(self):
        return self.dict_to_txt_array(self.txt)

    def _create_service(self):
        try:
            if not self._entrygroup:
                # create an EntryGroup for publishing
                object_path = self._server.call_sync(
                    'EntryGroupNew', None, Gio.DBusCallFlags.NONE, -1, None)

                self._entrygroup = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                    DBUS_NAME, *object_path, DBUS_INTERFACE_ENTRY_GROUP, None)

                connection = self._entrygroup.get_connection()
                subscription = connection.signal_subscribe(
                    DBUS_NAME, DBUS_INTERFACE_ENTRY_GROUP, 'StateChanged',
                    *object_path, None, Gio.DBusSignalFlags.NONE,
                    self._entrygroup_state_changed_callback)

                self._connections[connection] = [subscription]

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
            log.debug('Publishing service %s of type %s',
                      self.name, self.stype)

            try:
                self._entrygroup.call_sync(
                    'AddService',
                    GLib.Variant('(iiussssqaay)', (Interface.UNSPEC,
                                                   Protocol.UNSPEC, 0,
                                                   self.name, self.stype, '',
                                                   '', self.port,
                                                   self.avahi_txt())),
                    Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error as error:
                self._service_add_fail_callback(error)
                return False

            try:
                self._entrygroup.call_sync('Commit', None,
                                           Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error:
                pass

            return True
        except GLib.Error as error:
            log.debug(error)
            return False

    def announce(self):
        if not self.connected:
            return False

        state = self._server.call_sync(
            'GetState', None, Gio.DBusCallFlags.NONE, -1, None)

        if state[0] == ServerState.RUNNING:
            if self._create_service():
                self.announced = True
                return True
            return False
        return None

    def remove_announce(self):
        if self.announced is False:
            return False

        if self._call(self._entrygroup, 'GetState') != EntryGroup.FAILURE:
            self._call(self._entrygroup, 'Reset')
            self._call(self._entrygroup, 'Free')
            self._entrygroup = None
            self.announced = False

            return True
        return False

    def _browse_domain(self, interface, protocol, domain):
        self._new_service_type(interface, protocol, self.stype, domain, '')

    def _avahi_dbus_connect_cb(self, connection, sender_name, object_path,
                               interface_name, signal_name, parameters):
        name, old_owner, new_owner = parameters
        if name == DBUS_NAME:
            if new_owner and not old_owner:
                log.debug('We are connected to avahi-daemon')
            else:
                log.debug('Lost connection to avahi-daemon')
                self.disconnect()
                if self._disconnected_cb:
                    self._disconnected_cb()

    def _connect_dbus(self):
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', None)

            connection = proxy.get_connection()
            subscription = connection.signal_subscribe(
                'org.freedesktop.DBus', 'org.freedesktop.DBus',
                'NameOwnerChanged', '/org/freedesktop/DBus', None,
                Gio.DBusSignalFlags.NONE, self._avahi_dbus_connect_cb)
            self._connections[connection] = [subscription]
        except GLib.Error as error:
            log.debug(error)
            return False
        else:
            return True

    def _connect_avahi(self):
        if not self._connect_dbus():
            return False

        if self._server:
            return True
        try:
            self._server = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                DBUS_NAME, '/', DBUS_INTERFACE_SERVER, None)

            connection = self._server.get_connection()
            subscription = connection.signal_subscribe(
                DBUS_NAME, DBUS_INTERFACE_SERVER, 'StateChanged', '/', None,
                Gio.DBusSignalFlags.NONE, self._server_state_changed_callback)
            self._connections[connection] = [subscription]
        except Exception as error:
            # Avahi service is not present
            self._server = None
            log.debug(error)
            return False
        else:
            return True

    def connect(self):
        self.name = self.username + '@' + self.host # service name
        if not self._connect_avahi():
            return False

        self.connected = True
        # start browsing
        if self.domain is None:
            # Explicitly browse .local
            self._browse_domain(
                Interface.UNSPEC, Protocol.UNSPEC, 'local')

            # Browse for other browsable domains
            object_path = self._server.call_sync(
                'DomainBrowserNew',
                GLib.Variant('(iisiu)', (Interface.UNSPEC, Protocol.UNSPEC, '',
                                         DomainBrowser.BROWSE, 0)),
                Gio.DBusCallFlags.NONE, -1, None)

            self._domain_browser = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None, DBUS_NAME,
                *object_path, DBUS_INTERFACE_DOMAIN_BROWSER, None)

            connection = self._domain_browser.get_connection()
            subscription = connection.signal_subscribe(
                DBUS_NAME, DBUS_INTERFACE_DOMAIN_BROWSER, 'ItemNew',
                *object_path, None, Gio.DBusSignalFlags.NONE,
                self._new_domain_callback)
            self._connections[connection] = [subscription]

            subscription = connection.signal_subscribe(
                DBUS_NAME, DBUS_INTERFACE_DOMAIN_BROWSER, 'Failure',
                *object_path, None, Gio.DBusSignalFlags.NONE,
                self._error_callback)
            self._connections[connection].append(subscription)
        else:
            self._browse_domain(
                Interface.UNSPEC, Protocol.UNSPEC, self.domain)

        return True

    def disconnect(self):
        if self.connected:
            self.connected = False
            for connection, subscriptions in self._connections.items():
                for subscription in subscriptions:
                    connection.signal_unsubscribe(subscription)
            for con in self._sb_connections:
                self._service_browser.disconnect(con)
            if self._domain_browser:
                self._call(self._domain_browser, 'Free')
            self.remove_announce()
        self._server = None
        self._service_browser = None
        self._domain_browser = None

    # refresh txt data of all contacts manually (no callback available)
    def resolve_all(self):
        if not self.connected:
            return False
        for val in self._contacts.values():
            # get txt data from last recorded resolved info
            # TODO: Better try to get it from last IPv6 mDNS, then last IPv4?
            ri = val[Constant.RESOLVED_INFO][0]
            output = self._server.call_sync(
                'ResolveService',
                GLib.Variant('(iisssiu)', (ri[ConstantRI.INTERFACE],
                                           ri[ConstantRI.PROTOCOL],
                                           val[Constant.BARE_NAME],
                                           self.stype, val[Constant.DOMAIN],
                                           Protocol.UNSPEC,
                                           0)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
                )
            self._service_resolved_all_callback(*output)

        return True

    def get_contacts(self):
        return self._contacts

    def get_contact(self, jid):
        if not jid in self._contacts:
            return None
        return self._contacts[jid]

    def update_txt(self, show=None):
        if show:
            self.txt['status'] = self._replace_show(show)

        txt = self.avahi_txt()
        if self.connected and self._entrygroup:
            try:
                self._entrygroup.call_sync(
                    'UpdateServiceTxt',
                    GLib.Variant('(iiusssaay)', (Interface.UNSPEC,
                                                 Protocol.UNSPEC, 0, self.name,
                                                 self.stype, '', txt)),
                    Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error as error:
                self._error_callback(error)
                return False

            return True
        return False
