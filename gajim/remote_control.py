# Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
#                         Dimitur Kirov <dkirov AT gmail.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os
import logging

from gi.repository import GLib
from gi.repository import Gio

from gajim.common import app
from gajim.common import ged
from gajim.common import helpers
from gajim.common.structs import OutgoingMessage

from gajim.gtk.add_contact import AddNewContactWindow


log = logging.getLogger('gajim.remote_control')


def get_dbus_struct(obj):
    """
    Recursively go through all the items and replace them with their casted dbus
    equivalents
    """
    if obj is None:
        return None
    if isinstance(obj, str):
        return GLib.Variant('s', obj)
    if isinstance(obj, int):
        return GLib.Variant('i', obj)
    if isinstance(obj, float):
        return GLib.Variant('d', obj)
    if isinstance(obj, bool):
        return GLib.Variant('b', obj)
    if isinstance(obj, (list, tuple)):
        lst = [get_dbus_struct(i) for i in obj if i is not None]
        result = GLib.Variant('av', lst)
        return result
    if isinstance(obj, dict):
        result = GLib.VariantDict()
        for key, value in obj.items():
            result.insert_value(key, get_dbus_struct(value))
        return result.end()
    # unknown type
    return GLib.Variant('s', str(obj))


class Server:
    def __init__(self, con, path):
        method_outargs = {}
        method_inargs = {}
        for interface in Gio.DBusNodeInfo.new_for_xml(self.__doc__).interfaces:

            for method in interface.methods:
                method_outargs[method.name] = '(' + ''.join(
                    [arg.signature for arg in method.out_args]) + ')'
                method_inargs[method.name] = tuple(
                    arg.signature for arg in method.in_args)

            con.register_object(
                object_path=path,
                interface_info=interface,
                method_call_closure=self.on_method_call)

        self.method_inargs = method_inargs
        self.method_outargs = method_outargs

    def on_method_call(self, connection, sender, object_path, interface_name,
                       method_name, parameters, invocation):

        args = list(parameters.unpack())
        for i, sig in enumerate(self.method_inargs[method_name]):
            if sig == 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])

        result = getattr(self, method_name)(*args)

        # out_args is at least (signature1). We therefore always wrap the result
        # as a tuple. Refer to https://bugzilla.gnome.org/show_bug.cgi?id=765603
        result = (result, )

        out_args = self.method_outargs[method_name]
        if out_args != '()':
            variant = GLib.Variant(out_args, result)
            invocation.return_value(variant)
        else:
            invocation.return_value(None)


class GajimRemote(Server):
    '''
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
            <method name='add_contact'>
                <arg name='jid' type='s' />
                <arg name='account' type='s' />
                <arg direction='out' type='b' />
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
            <method name='join_room'>
                <arg name='room_jid' type='s' />
                <arg name='password' type='s' />
                <arg name='account' type='s' />
            </method>
            <method name='list_accounts'>
                <arg direction='out' type='as' />
            </method>
            <method name='list_contacts'>
                <arg name='account' type='s' />
                <arg direction='out' type='aa{sv}' />
            </method>
            <method name='open_chat'>
                <arg name='jid' type='s' />
                <arg name='account' type='s' />
                <arg name='message' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='remove_contact'>
                <arg name='jid' type='s' />
                <arg name='account' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='send_chat_message'>
                <arg name='jid' type='s' />
                <arg name='message' type='s' />
                <arg name='account' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='send_file'>
                <arg name='file_path' type='s' />
                <arg name='jid' type='s' />
                <arg name='account' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='send_groupchat_message'>
                <arg name='room_jid' type='s' />
                <arg name='message' type='s' />
                <arg name='account' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='send_single_message'>
                <arg name='jid' type='s' />
                <arg name='subject' type='s' />
                <arg name='message' type='s' />
                <arg name='account' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='send_xml'>
                <arg name='xml' type='s' />
                <arg name='account' type='s' />
            </method>
            <method name='set_priority'>
                <arg name='prio' type='s' />
                <arg name='account' type='s' />
            </method>
            <method name='show_next_pending_event' />
            <method name='show_roster' />
            <method name='start_chat'>
                <arg name='jid' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='toggle_ipython' />
            <method name='toggle_roster_appearance' />
            <signal name='AccountPresence'>
                <arg type='av' />
            </signal>
            <signal name='ChatState'>
                <arg type='av' />
            </signal>
            <signal name='ContactAbsence'>
                <arg type='av' />
            </signal>
            <signal name='ContactPresence'>
                <arg type='av' />
            </signal>
            <signal name='ContactStatus'>
                <arg type='av' />
            </signal>
            <signal name='EntityTime'>
                <arg type='av' />
            </signal>
            <signal name='GCMessage'>
                <arg type='av' />
            </signal>
            <signal name='GCPresence'>
                <arg type='av' />
            </signal>
            <signal name='MessageSent'>
                <arg type='av' />
            </signal>
            <signal name='NewAccount'>
                <arg type='av' />
            </signal>
            <signal name='NewMessage'>
                <arg type='av' />
            </signal>
            <signal name='Roster'>
                <arg type='av' />
            </signal>
            <signal name='RosterInfo'>
                <arg type='av' />
            </signal>
            <signal name='Subscribe'>
                <arg type='av' />
            </signal>
            <signal name='Subscribed'>
                <arg type='av' />
            </signal>
            <signal name='Unsubscribed'>
                <arg type='av' />
            </signal>
            <signal name='VcardInfo'>
                <arg type='av' />
            </signal>
        </interface>
    </node>
    '''

    def __init__(self):
        self.con = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(self.con, 'org.gajim.Gajim',
                                       Gio.BusNameOwnerFlags.NONE, None, None)
        super().__init__(self.con, '/org/gajim/dbus/RemoteObject')
        self.first_show = True

        app.ged.register_event_handler('time-result-received', ged.POSTGUI,
            self.on_time)
        app.ged.register_event_handler('roster-info', ged.POSTGUI,
            self.on_roster_info)
        app.ged.register_event_handler('presence-received', ged.POSTGUI,
            self.on_presence_received)
        app.ged.register_event_handler('subscribe-presence-received',
            ged.POSTGUI, self.on_subscribe_presence_received)
        app.ged.register_event_handler('subscribed-presence-received',
            ged.POSTGUI, self.on_subscribed_presence_received)
        app.ged.register_event_handler('unsubscribed-presence-received',
            ged.POSTGUI, self.on_unsubscribed_presence_received)
        app.ged.register_event_handler('gc-message-received',
            ged.POSTGUI, self.on_gc_message_received)
        app.ged.register_event_handler('decrypted-message-received',
            ged.POSTGUI, self._nec_decrypted_message_received)
        app.ged.register_event_handler('our-show', ged.POSTGUI,
            self.on_our_status)
        app.ged.register_event_handler('account-created', ged.POSTGUI,
            self.on_account_created)
        app.ged.register_event_handler('vcard-received', ged.POSTGUI,
            self.on_vcard_received)
        app.ged.register_event_handler('chatstate-received', ged.POSTGUI,
            self.on_chatstate_received)
        app.ged.register_event_handler('message-sent', ged.POSTGUI,
            self.on_message_sent)

    def on_chatstate_received(self, obj):
        if obj.contact.is_gc_contact:
            jid = obj.contact.get_full_jid()
            chatstate = obj.contact.chatstate
        else:
            jid = obj.contact.jid
            chatstate = app.contacts.get_combined_chatstate(
                obj.account, obj.contact.jid)
        self.raise_signal('ChatState', (obj.account, [jid, chatstate]))

    def on_message_sent(self, obj):
        try:
            chatstate = obj.chatstate
        except AttributeError:
            chatstate = ''
        self.raise_signal('MessageSent', (obj.account, [
            obj.jid, obj.message, chatstate]))

    def on_time(self, obj):
        self.raise_signal('EntityTime', (obj.conn.name, [obj.jid.bare,
                                                         obj.jid.resource,
                                                         obj.time_info]))

    def on_roster_info(self, obj):
        self.raise_signal('RosterInfo', (obj.conn.name, [obj.jid, obj.nickname,
            obj.sub, obj.ask, obj.groups]))

    def on_presence_received(self, obj):
        if obj.old_show < 2 and obj.new_show > 1:
            event = 'ContactPresence'
        elif obj.old_show > 1 and obj.new_show < 2:
            event = 'ContactAbsence'
        elif obj.new_show > 1:
            event = 'ContactStatus'
        else:
            return
        self.raise_signal(event, (obj.conn.name, [obj.jid, obj.show,
                obj.status, obj.resource, obj.prio, obj.timestamp]))

    def on_subscribe_presence_received(self, obj):
        self.raise_signal('Subscribe', (obj.conn.name, [obj.jid, obj.status,
            obj.user_nick]))

    def on_subscribed_presence_received(self, event):
        self.raise_signal('Subscribed', (event.account,
                                         [event.jid.bare,
                                          event.jid.resource]))

    def on_unsubscribed_presence_received(self, obj):
        self.raise_signal('Unsubscribed', (obj.conn.name, obj.jid))

    def on_gc_message_received(self, obj):
        if not hasattr(obj, 'needs_highlight'):
            # event has not been handled at GUI level
            return
        self.raise_signal('GCMessage', (obj.conn.name, [obj.fjid, obj.msgtxt,
            obj.properties.timestamp, obj.delayed,
            obj.displaymarking, obj.needs_highlight]))

    def _nec_decrypted_message_received(self, obj):
        event_type = obj.properties.type.value
        if obj.properties.is_muc_pm:
            event_type = 'pm'
        self.raise_signal('NewMessage', (
            obj.conn.name, [obj.fjid, obj.msgtxt, obj.properties.timestamp,
            event_type, obj.properties.subject,
            obj.msg_log_id, obj.properties.nickname]))

    def on_our_status(self, event):
        self.raise_signal('AccountPresence', (event.show, event.account))

    def on_account_created(self, obj):
        self.raise_signal('NewAccount', (obj.conn.name, obj.account_info))

    def on_vcard_received(self, obj):
        self.raise_signal('VcardInfo', (obj.account, obj.vcard_dict))

    def raise_signal(self, event_name, data):
        log.info('Send event %s', event_name)
        self.con.emit_signal(None,
                             '/org/gajim/dbus/RemoteObject',
                             'org.gajim.dbus.RemoteInterface',
                             event_name,
                             GLib.Variant.new_tuple(get_dbus_struct(data)))

    def get_status(self, account):
        """
        Return status (show to be exact) which is the global one unless
        account is given
        """
        if not account:
            # If user did not ask for account, returns the global status
            return helpers.get_global_show()
        # return show for the given account
        return app.connections[account].status

    def get_status_message(self, account):
        """
        Return status which is the global one unless account is given
        """
        if not account:
            # If user did not ask for account, returns the global status
            return str(helpers.get_global_status_message())
        # return show for the given account
        return app.connections[account].status_message

    def _get_account_and_contact(self, account, jid):
        """
        Get the account (if not given) and contact instance from jid
        """
        connected_account = None
        contact = None
        accounts = app.contacts.get_accounts()
        # if there is only one account in roster, take it as default
        # if user did not ask for account
        if not account and len(accounts) == 1:
            account = accounts[0]
        if account:
            if app.account_is_available(account):  # account is connected
                connected_account = account
                contact = app.contacts.get_contact_with_highest_priority(
                    account, jid)
        else:
            for account_ in accounts:
                contact = app.contacts.get_contact_with_highest_priority(
                    account, jid)
                if contact and app.account_is_available(account_):
                    # account is connected
                    connected_account = account_
                    break
        if not contact:
            contact = jid

        return connected_account, contact

    def _get_account_for_groupchat(self, account, room_jid):
        """
        Get the account which is connected to groupchat (if not given)
        or check if the given account is connected to the groupchat
        """
        connected_account = None
        accounts = app.contacts.get_accounts()
        # if there is only one account in roster, take it as default
        # if user did not ask for account
        if not account and len(accounts) == 1:
            account = accounts[0]
        if account:
            if app.account_is_available(account) and \
                    room_jid in app.gc_connected[account] and \
                    app.gc_connected[account][room_jid]:
                # account and groupchat are connected
                connected_account = account
        else:
            for account_ in accounts:
                if app.account_is_available(account_) and \
                        room_jid in app.gc_connected[account_] and \
                        app.gc_connected[account_][room_jid]:
                    # account and groupchat are connected
                    connected_account = account_
                    break
        return connected_account

    def send_file(self, file_path, jid, account):
        """
        Send file, located at 'file_path' to 'jid', using account (optional)
        'account'
        """
        jid = self._get_real_jid(jid, account)
        connected_account, contact = self._get_account_and_contact(
            account, jid)

        if connected_account:
            if file_path.startswith('file://'):
                file_path = file_path[7:]
            if os.path.isfile(file_path):  # is it file?
                app.interface.instances['file_transfers'].send_file(
                    connected_account, contact, file_path)
                return True
        return False

    def _send_message(self,
                      jid,
                      message,
                      account,
                      type_='chat',
                      subject=None):
        """
        Can be called from send_chat_message (default when send_message) or
        send_single_message
        """
        if not jid or not message:
            return False

        connected_account, contact = self._get_account_and_contact(account, jid)
        if not connected_account or contact is None:
            return False

        connection = app.connections[connected_account]
        ctrl = app.interface.msg_win_mgr.search_control(
            jid, connected_account)
        if ctrl:
            ctrl.send_message(message)
        else:
            message_ = OutgoingMessage(account=connected_account,
                                       contact=contact,
                                       message=message,
                                       type_=type_,
                                       subject=subject,
                                       control=ctrl)
            connection.send_message(message_)
        return True

    def send_chat_message(self, jid, message, account):
        """
        Send chat 'message' to 'jid', using account (optional) 'account'.
        """
        jid = self._get_real_jid(jid, account)
        return self._send_message(jid, message, account)

    def send_single_message(self, jid, subject, message, account):
        """
        Send single 'message' to 'jid', using account (optional) 'account'.
        """
        jid = self._get_real_jid(jid, account)
        return self._send_message(jid, message, account, 'normal', subject)

    def send_groupchat_message(self, room_jid, message, account):
        """
        Send 'message' to groupchat 'room_jid',
        using account (optional) 'account'
        """
        if not room_jid or not message:
            return False
        connected_account = self._get_account_for_groupchat(account, room_jid)
        if not connected_account:
            return False

        contact = app.contacts.get_groupchat_contact(connected_account,
                                                     room_jid)
        if contact is None:
            return False

        message_ = OutgoingMessage(account=connected_account,
                                   contact=contact,
                                   message=message,
                                   type_='groupchat')
        con = app.connections[connected_account]
        con.send_message(message_)
        return True


    def open_chat(self, jid, account, message):
        """
        Shows the tabbed window for new message to 'jid', using account (optional)
        'account'
        """
        if not jid:
            raise ValueError('jid is missing')
        jid = self._get_real_jid(jid, account)
        try:
            jid = helpers.parse_jid(jid)
        except Exception:
            # Jid is not conform, ignore it
            return False

        minimized_control = None
        if account:
            accounts = [account]
        else:
            accounts = app.connections.keys()
            if len(accounts) == 1:
                account = accounts[0]
        connected_account = None
        first_connected_acct = None
        for acct in accounts:
            if app.account_is_available(acct):  # account is  online
                contact = app.contacts.get_first_contact_from_jid(acct, jid)
                if app.interface.msg_win_mgr.has_window(jid, acct):
                    connected_account = acct
                    break
                # jid is in roster
                if contact:
                    minimized_control = \
                        jid in app.interface.minimized_controls[acct]
                    connected_account = acct
                    break
                # we send the message to jid not in roster, because account is
                # specified, or there is only one account
                if account:
                    connected_account = acct
                elif first_connected_acct is None:
                    first_connected_acct = acct

        # if jid is not a contact, open-chat with first connected account
        if connected_account is None and first_connected_acct:
            connected_account = first_connected_acct

        if minimized_control:
            app.interface.roster.on_groupchat_maximized(
                None, jid, connected_account)

        if connected_account:
            app.interface.new_chat_from_jid(connected_account, jid, message)
            # preserve the 'steal focus preservation'
            win = app.interface.msg_win_mgr.get_window(
                jid, connected_account).window
            if win.get_property('visible'):
                win.window.present()
            return True
        return False

    def change_status(self, status, message, account):
        """
        change_status(status, message, account). Account is optional - if not
        specified status is changed for all accounts
        """
        if status not in ('offline', 'online', 'chat', 'away', 'xa', 'dnd'):
            status = ''
        if account:
            if not status:
                if account not in app.connections:
                    return False
                status = app.connections[account].status
            GLib.idle_add(app.interface.roster.send_status, account, status,
                          message)
        else:
            # account not specified, so change the status of all accounts
            for acc in app.contacts.get_accounts():
                if not app.settings.get_account_setting(
                        acc, 'sync_with_global_status'):
                    continue
                if status:
                    status_ = status
                else:
                    if acc not in app.connections:
                        continue
                    status_ = app.connections[acc].status
                GLib.idle_add(app.interface.roster.send_status, acc, status_,
                              message)
        return False

    def set_priority(self, prio, account):
        """
        set_priority(prio, account). Account is optional - if not specified
        priority is changed for all accounts. That are synced with global status
        """
        if account:
            app.settings.set_account_setting(account, 'priority', prio)
            show = app.connections[account].status
            status = app.connections[account].status_message
            GLib.idle_add(app.connections[account].change_status, show, status)
        else:
            # account not specified, so change prio of all accounts
            for acc in app.contacts.get_accounts():
                if not app.account_is_available(acc):
                    continue
                if not app.settings.get_account_setting(
                        acc, 'sync_with_global_status'):
                    continue
                app.settings.set_account_setting(acc, 'priority', prio)
                show = app.connections[acc].status
                status = app.connections[acc].status_message
                GLib.idle_add(app.connections[acc].change_status, show, status)

    def show_next_pending_event(self):
        """
        Show the window(s) with next pending event in tabbed/group chats
        """
        if app.events.get_nb_events():
            account, jid, event = app.events.get_first_systray_event()
            if not event:
                return
            app.interface.handle_event(account, jid, event.type_)

    def list_accounts(self):
        """
        List register accounts
        """
        result = app.contacts.get_accounts()
        result_array = []
        if result:
            for account in result:
                result_array.append(account)
        return result_array

    def account_info(self, account):
        """
        Show info on account: resource, jid, nick, prio, message
        """
        result = {}
        if account in app.connections:
            # account is valid
            con = app.connections[account]
            result['status'] = con.status
            result['name'] = con.name
            result['jid'] = app.get_jid_from_account(con.name)
            result['message'] = con.status_message
            result['priority'] = str(con.priority)
            result['resource'] = app.settings.get_account_setting(con.name,
                                                                  'resource')
        return result

    def list_contacts(self, account):
        """
        List all contacts in the roster. If the first argument is specified,
        then return the contacts for the specified account
        """
        result = []
        accounts = app.contacts.get_accounts()
        if not accounts:
            return result
        if account:
            accounts_to_search = [account]
        else:
            accounts_to_search = accounts
        for acct in accounts_to_search:
            if acct in accounts:
                for jid in app.contacts.get_jid_list(acct):
                    item = self._contacts_as_dbus_structure(
                            app.contacts.get_contacts(acct, jid))
                    if item:
                        result.append(item)
        return result

    def add_contact(self, jid, account):
        if account:
            if app.account_is_available(account):
                # if given account is active, use it
                AddNewContactWindow(account=account, contact_jid=jid)
            else:
                # wrong account
                return False
        else:
            # if account is not given, show account combobox
            AddNewContactWindow(account=None, contact_jid=jid)
        return True

    def remove_contact(self, jid, account):
        jid = self._get_real_jid(jid, account)
        accounts = app.contacts.get_accounts()

        # if there is only one account in roster, take it as default
        if account:
            accounts = [account]
        contact_exists = False
        for account_ in accounts:
            contacts = app.contacts.get_contacts(account_, jid)
            if contacts:
                app.connections[account_].get_module('Presence').unsubscribe(jid)
                for contact in contacts:
                    app.interface.roster.remove_contact(contact, account_)
                app.contacts.remove_jid(account_, jid)
                contact_exists = True
        return contact_exists

    def _is_first(self):
        if self.first_show:
            self.first_show = False
            return True
        return False

    def _get_real_jid(self, jid, account=None):
        """
        Get the real jid from the given one: removes xmpp: or get jid from nick if
        account is specified, search only in this account
        """
        if account:
            accounts = [account]
        else:
            accounts = app.connections.keys()
        if jid.startswith('xmpp:'):
            return jid[5:]  # len('xmpp:') = 5
        nick_in_roster = None  # Is jid a nick ?
        for account_ in accounts:
            # Does jid exists in roster of one account ?
            if app.contacts.get_contacts(account_, jid):
                return jid
            if not nick_in_roster:
                # look in all contact if one has jid as nick
                for jid_ in app.contacts.get_jid_list(account_):
                    c = app.contacts.get_contacts(account_, jid_)
                    if c[0].name == jid:
                        nick_in_roster = jid_
                        break
        if nick_in_roster:
            # We have not found jid in roster, but we found is as a nick
            return nick_in_roster
        # We have not found it as jid nor as nick, probably a not in roster jid
        return jid

    def _contacts_as_dbus_structure(self, contacts):
        """
        Get info from list of Contact objects and create dbus dict
        """
        if not contacts:
            return None
        prim_contact = None  # primary contact
        for contact in contacts:
            if prim_contact is None or contact.priority > prim_contact.priority:
                prim_contact = contact
        contact_dict = {}
        name = prim_contact.name if prim_contact.name is not None else ''
        contact_dict['name'] = GLib.Variant('s', name)
        contact_dict['show'] = GLib.Variant('s', prim_contact.show)
        contact_dict['jid'] = GLib.Variant('s', prim_contact.jid)

        resources = GLib.VariantBuilder(GLib.VariantType('a(sis)'))
        for contact in contacts:
            resource_props = (contact.resource, int(contact.priority),
                              contact.status)
            resources.add_value(GLib.Variant('(sis)', resource_props))
        contact_dict['resources'] = resources.end()

        groups = GLib.VariantBuilder(GLib.VariantType('as'))
        for group in prim_contact.groups:
            groups.add_value(GLib.Variant('s', group))
        contact_dict['groups'] = groups.end()
        return contact_dict

    def get_unread_msgs_number(self):
        unread = app.events.get_nb_events()
        for event in app.events.get_all_events(['printed_gc_msg']):
            contact = app.contacts.get_groupchat_contact(event.account,
                                                         event.jid)
            if contact is None or not contact.can_notify():
                unread -= 1
                continue

        return str(unread)

    def start_chat(self, jid=''):
        app.app.activate_action('start-chat', GLib.Variant('s', jid))
        return True

    def send_xml(self, xml, account):
        if account:
            app.connections[account].send_stanza(str(xml))
        else:
            for acc in app.contacts.get_accounts():
                app.connections[acc].send_stanza(str(xml))

    def join_room(self, room_jid, password, account):
        if not account:
            # get the first connected account
            accounts = app.connections.keys()
            for acct in accounts:
                if app.account_is_available(acct):
                    if not app.connections[acct].is_zeroconf:
                        account = acct
                        break
            if not account:
                return

        if app.connections[account].is_zeroconf:
            # zeroconf not support groupchats
            return

        app.interface.show_or_join_groupchat(account,
                                             room_jid,
                                             password=password)

    def Introspect(self):
        return self.__doc__
