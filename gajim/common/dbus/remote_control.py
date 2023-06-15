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

from typing import Any
from typing import cast

import logging

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common import helpers
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.structs import OutgoingMessage

log = logging.getLogger('gajim.c.dbus.remote_control')

INTERFACE_DESC = '''
<!DOCTYPE node PUBLIC '-//freedesktop//DTD D-BUS Object Introspection 1.0//EN'
'http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd'>
<node>
    <interface name='org.freedesktop.DBus.Introspectable'>
        <method name='Introspect'>
            <arg name='data' direction='out' type='s'/>
        </method>
    </interface>
    <interface name='org.gajim.dbus.RemoteInterface'>
        <method name='account_info'>
            <arg name='account' type='s' />
            <arg direction='out' type='a{ss}' />
        </method>
        <method name='change_status'>
            <arg name='status' type='s' />
            <arg name='message' type='s' />
            <arg name='account' type='s' />
            <arg direction='out' type='b' />
        </method>
        <method name='get_status'>
            <arg name='account' type='s' />
            <arg direction='out' type='s' />
        </method>
        <method name='get_status_message'>
            <arg name='account' type='s' />
            <arg direction='out' type='s' />
        </method>
        <method name='get_unread_msgs_number'>
            <arg direction='out' type='s' />
        </method>
        <method name='list_accounts'>
            <arg direction='out' type='as' />
        </method>
        <method name='list_contacts'>
            <arg name='account' type='s' />
            <arg direction='out' type='aa{sv}' />
        </method>
        <method name='send_chat_message'>
            <arg name='jid' type='s' />
            <arg name='message' type='s' />
            <arg name='account' type='s' />
            <arg direction='out' type='b' />
        </method>
        <method name='send_groupchat_message'>
            <arg name='room_jid' type='s' />
            <arg name='message' type='s' />
            <arg name='account' type='s' />
            <arg direction='out' type='b' />
        </method>
        <signal name='AccountPresence'>
            <arg type='av' />
        </signal>
        <signal name='ContactPresence'>
            <arg type='av' />
        </signal>
        <signal name='GCMessage'>
            <arg type='av' />
        </signal>
        <signal name='MessageSent'>
            <arg type='av' />
        </signal>
        <signal name='NewMessage'>
            <arg type='av' />
        </signal>
    </interface>
</node>
'''


def get_dbus_struct(obj: Any) -> GLib.Variant:
    '''
    Recursively go through all the items and replace them with their casted dbus
    equivalents
    '''
    if isinstance(obj, str):
        return GLib.Variant('s', obj)
    if isinstance(obj, int):
        return GLib.Variant('i', obj)
    if isinstance(obj, float):
        return GLib.Variant('d', obj)
    if isinstance(obj, bool):
        return GLib.Variant('b', obj)
    if isinstance(obj, list | tuple):
        lst = [get_dbus_struct(i) for i in obj  # pyright: ignore
               if i is not None]
        result = GLib.Variant('av', lst)
        return result
    if isinstance(obj, dict):
        obj = cast(dict[str, Any], obj)
        result = GLib.VariantDict()
        for key, value in obj.items():
            result.insert_value(key, get_dbus_struct(value))
        return result.end()
    # unknown type
    return GLib.Variant('s', str(obj))


class Server:
    def __init__(self, con: Gio.DBusConnection, path: str) -> None:
        self._method_outargs: dict[str, str] = {}
        self._method_inargs: dict[str, tuple[str, ...]] = {}
        node_info = Gio.DBusNodeInfo.new_for_xml(INTERFACE_DESC)
        for interface in node_info.interfaces:
            for method in interface.methods:
                self._method_outargs[method.name] = '(' + ''.join(
                    [arg.signature for arg in method.out_args]) + ')'
                self._method_inargs[method.name] = tuple(
                    arg.signature for arg in method.in_args)

            con.register_object(
                object_path=path,
                interface_info=interface,
                method_call_closure=self._on_method_call)

    def _on_method_call(self,
                        _connection: Gio.DBusConnection,
                        _sender: str,
                        _object_path: str,
                        _interface_name: str,
                        method_name: str,
                        parameters: GLib.Variant,
                        invocation: Gio.DBusMethodInvocation) -> None:

        args = list(parameters.unpack())
        for i, sig in enumerate(self._method_inargs[method_name]):
            if sig == 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                assert fd_list is not None
                args[i] = fd_list.get(args[i])

        result = getattr(self, method_name)(*args)

        # out_args is at least (signature1). We therefore always wrap the result
        # as a tuple. Refer to https://bugzilla.gnome.org/show_bug.cgi?id=765603
        result = (result, )

        out_args = self._method_outargs[method_name]
        if out_args != '()':
            variant = GLib.Variant(out_args, result)
            invocation.return_value(variant)
        else:
            invocation.return_value(None)


class GajimRemote(Server):
    def __init__(self) -> None:
        self._con = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(self._con, 'org.gajim.Gajim',
                                       Gio.BusNameOwnerFlags.NONE, None, None)
        super().__init__(self._con, '/org/gajim/dbus/RemoteObject')

        app.ged.register_event_handler('presence-received',
                                       ged.POSTGUI,
                                       self._on_presence_received)
        app.ged.register_event_handler('gc-message-received',
                                       ged.POSTGUI,
                                       self._on_gc_message_received)
        app.ged.register_event_handler('message-received',
                                       ged.POSTGUI,
                                       self._on_message_received)
        app.ged.register_event_handler('our-show',
                                       ged.POSTGUI,
                                       self._on_our_status)
        app.ged.register_event_handler('message-sent',
                                       ged.POSTGUI,
                                       self._on_message_sent)

    def _on_message_sent(self, event: events.MessageSent) -> None:
        self.raise_signal('MessageSent', (
            event.account, [event.jid,
                          event.message]))

    def _on_presence_received(self, event: events.PresenceReceived) -> None:
        self.raise_signal('ContactPresence', (event.account, [
            event.jid,
            event.resource,
            event.show,
            event.status]))

    def _on_gc_message_received(self, event: events.GcMessageReceived) -> None:
        self.raise_signal('GCMessage', (
            event.conn.name, [event.fjid,
                              event.msgtxt,
                              event.properties.timestamp,
                              event.delayed,
                              event.displaymarking]))

    def _on_message_received(self,
                             event: events.MessageReceived) -> None:

        event_type = event.properties.type.value
        if event.properties.is_muc_pm:
            event_type = 'pm'
        self.raise_signal('NewMessage', (
            event.conn.name, [event.fjid,
                              event.msgtxt,
                              event.properties.timestamp,
                              event_type,
                              event.properties.subject,
                              event.msg_log_id,
                              event.properties.nickname]))

    def _on_our_status(self, event: events.ShowChanged) -> None:
        self.raise_signal('AccountPresence', (event.show, event.account))

    def raise_signal(self, event_name: str, data: Any) -> None:
        log.info('Send event %s', event_name)
        self._con.emit_signal(None,
                              '/org/gajim/dbus/RemoteObject',
                              'org.gajim.dbus.RemoteInterface',
                              event_name,
                              GLib.Variant.new_tuple(get_dbus_struct(data)))

    @staticmethod
    def get_status(account: str) -> str:
        if not account:
            return helpers.get_global_show()
        return helpers.get_client_status(account)

    @staticmethod
    def get_status_message(account: str) -> str:
        if not account:
            return str(helpers.get_global_status_message())
        return app.get_client(account).status_message

    @staticmethod
    def _send_message(jid: str,
                      message: str,
                      account: str,
                      type_: str) -> bool:

        if not app.account_is_available(account):
            return False

        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(
            jid, groupchat=type_ == 'groupchat')

        if type_ == 'groupchat':
            assert isinstance(contact, GroupchatContact)
            if not contact.is_joined:
                return False

        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant)
        message_ = OutgoingMessage(account=account,
                                   contact=contact,
                                   message=message,
                                   type_=type_)

        app.get_client(account).send_message(message_)
        return True

    def send_chat_message(self, jid: str, message: str, account: str) -> bool:
        if not jid or not message or not account:
            return False

        return self._send_message(jid, message, account, 'chat')

    def send_groupchat_message(self,
                               jid: str,
                               message: str,
                               account: str) -> bool:

        if not jid or not message or not account:
            return False

        return self._send_message(jid, message, account, 'groupchat')

    @staticmethod
    def change_status(status: str, message: str, account: str) -> bool:
        '''
        change_status(status, message, account). Account is optional - if not
        specified status is changed for all accounts
        '''
        if status not in ('offline', 'online', 'chat', 'away', 'xa', 'dnd'):
            status = ''

        if account:
            if not status:
                if account not in app.settings.get_active_accounts():
                    return False
                status = app.get_client(account).status

            GLib.idle_add(app.get_client(account).change_status,
                          status,
                          message)
        else:
            # account not specified, so change the status of all accounts
            for acc in app.settings.get_active_accounts():
                if not app.settings.get_account_setting(
                        acc, 'sync_with_global_status'):
                    continue

                if not status:
                    status = app.get_client(acc).status

                GLib.idle_add(app.get_client(acc).change_status,
                              status,
                              message)
        return True

    @staticmethod
    def list_accounts() -> list[str]:
        '''
        List register accounts
        '''
        result = app.settings.get_active_accounts()
        result_array: list[str] = []
        if result:
            for account in result:
                result_array.append(account)
        return result_array

    @staticmethod
    def account_info(account: str) -> dict[str, str]:
        '''
        Show info on account: resource, jid, nick, prio, message
        '''
        result: dict[str, str] = {}
        if account in app.settings.get_active_accounts():
            # account is valid
            client = app.get_client(account)
            result['status'] = client.status
            result['name'] = client.name
            result['jid'] = app.get_jid_from_account(client.name)
            result['message'] = client.status_message
            result['priority'] = str(client.priority)
            result['resource'] = app.settings.get_account_setting(client.name,
                                                                  'resource')
        return result

    def list_contacts(self, account: str) -> list[dict[str, GLib.Variant]]:
        result: list[dict[str, GLib.Variant]] = []
        accounts = app.settings.get_active_accounts()
        if not accounts:
            return result
        if account:
            accounts_to_search = [account]
        else:
            accounts_to_search = accounts
        for acct in accounts_to_search:
            if acct in accounts:
                client = app.get_client(acct)
                for contact in client.get_module('Roster').iter_contacts():
                    item = self._contacts_as_dbus_structure(contact)
                    if item:
                        result.append(item)
        return result

    @staticmethod
    def _contacts_as_dbus_structure(contact: BareContact
                                    ) -> dict[str, GLib.Variant]:
        '''
        Get info from list of Contact objects and create dbus dict
        '''

        contact_dict: dict[str, GLib.Variant] = {}

        contact_dict['name'] = GLib.Variant('s', contact.name)
        contact_dict['show'] = GLib.Variant('s', contact.show.value)
        contact_dict['jid'] = GLib.Variant('s', str(contact.jid))

        resources = GLib.VariantBuilder(GLib.VariantType('a(ss)'))
        for res_contact in contact.iter_resources():
            resource_props = (res_contact.resource,
                              res_contact.status)
            resources.add_value(GLib.Variant('(ss)', resource_props))
        contact_dict['resources'] = resources.end()

        groups = GLib.VariantBuilder(GLib.VariantType('as'))
        for group in contact.groups:
            groups.add_value(GLib.Variant('s', group))
        contact_dict['groups'] = groups.end()
        return contact_dict

    @staticmethod
    def get_unread_msgs_number() -> str:
        return str(app.window.get_total_unread_count())

    @staticmethod
    def Introspect() -> str:  # pylint: disable=invalid-name
        return INTERFACE_DESC
