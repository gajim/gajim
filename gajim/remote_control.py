# -*- coding:utf-8 -*-
## src/remote_control.py
##
## Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
##                         Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os
import base64
import mimetypes
from time import time

from gi.repository import GLib
from gi.repository import Gio

from gajim.common import app
from gajim.common import helpers
from gajim.gtk import AddNewContactWindow
from gajim.common import ged
from gajim.common.connection_handlers_events import MessageOutgoingEvent
from gajim.common.connection_handlers_events import GcMessageOutgoingEvent


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
        result = GLib.Variant('av', [get_dbus_struct(i) for i in obj])
        return result
    if isinstance(obj, dict):
        result = GLib.VariantDict()
        for key, value in obj.items():
            result.insert_value(key, get_dbus_struct(value))
        return result.end()
    # unknown type
    return None


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
            if sig is 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])

        result = getattr(self, method_name)(*args)

        # out_args is atleast (signature1). We therefore always wrap the result
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
            <method name='change_avatar'>
                <arg name='picture' type='s' />
                <arg name='account' type='s' />
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
                <arg name='nick' type='s' />
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
            <method name='prefs_del'>
                <arg name='key' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='prefs_list'>
                <arg direction='out' type='a{ss}' />
            </method>
            <method name='prefs_put'>
                <arg name='key' type='s' />
                <arg direction='out' type='b' />
            </method>
            <method name='prefs_store'>
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
                <arg name='keyID' type='s' />
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
                <arg name='keyID' type='s' />
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
                <arg name='account' type='s' />
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
            <signal name='OsInfo'>
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

        app.ged.register_event_handler('version-result-received', ged.POSTGUI,
            self.on_os_info)
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
        self.raise_signal('ChatState', (obj.conn.name, [
            obj.jid, obj.fjid, obj.stanza, obj.resource, obj.chatstate]))

    def on_message_sent(self, obj):
        try:
            chatstate = obj.chatstate
        except AttributeError:
            chatstate = ""
        self.raise_signal('MessageSent', (obj.conn.name, [
            obj.jid, obj.message, obj.keyID, chatstate]))

    def on_os_info(self, obj):
        self.raise_signal('OsInfo', (obj.conn.name, [obj.jid.getStripped(),
                                                     obj.jid.getResource(),
                                                     obj.client_info,
                                                     obj.os_info]))

    def on_time(self, obj):
        self.raise_signal('EntityTime', (obj.conn.name, [obj.jid.getStripped(),
                                                         obj.jid.getResource(),
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
                obj.status, obj.resource, obj.prio, obj.keyID, obj.timestamp,
                obj.contact_nickname]))

    def on_subscribe_presence_received(self, obj):
        self.raise_signal('Subscribe', (obj.conn.name, [obj.jid, obj.status,
            obj.user_nick]))

    def on_subscribed_presence_received(self, obj):
        self.raise_signal('Subscribed', (obj.conn.name, [obj.jid,
            obj.resource]))

    def on_unsubscribed_presence_received(self, obj):
        self.raise_signal('Unsubscribed', (obj.conn.name, obj.jid))

    def on_gc_message_received(self, obj):
        if not hasattr(obj, 'needs_highlight'):
            # event has not been handled at GUI level
            return
        self.raise_signal('GCMessage', (obj.conn.name, [obj.fjid, obj.msgtxt,
            obj.timestamp, obj.has_timestamp, obj.xhtml_msgtxt, obj.status_code,
            obj.displaymarking, obj.captcha_form, obj.needs_highlight]))

    def on_our_status(self, obj):
        self.raise_signal('AccountPresence', (obj.show, obj.conn.name))

    def on_account_created(self, obj):
        self.raise_signal('NewAccount', (obj.conn.name, obj.account_info))

    def on_vcard_received(self, obj):
        self.raise_signal('VcardInfo', (obj.conn.name, obj.vcard_dict))

    def raise_signal(self, event_name, data):
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
        index = app.connections[account].connected
        return app.SHOW_LIST[index]

    def get_status_message(self, account):
        """
        Return status which is the global one unless account is given
        """
        if not account:
            # If user did not ask for account, returns the global status
            return str(helpers.get_global_status())
        # return show for the given account
        status = app.connections[account].status
        return status

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
            if app.connections[account].connected > 1:  # account is connected
                connected_account = account
                contact = app.contacts.get_contact_with_highest_priority(
                    account, jid)
        else:
            for account in accounts:
                contact = app.contacts.get_contact_with_highest_priority(
                    account, jid)
                if contact and app.connections[account].connected > 1:
                    # account is connected
                    connected_account = account
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
            if app.connections[account].connected > 1 and \
                    room_jid in app.gc_connected[account] and \
                    app.gc_connected[account][room_jid]:
                # account and groupchat are connected
                connected_account = account
        else:
            for account in accounts:
                if app.connections[account].connected > 1 and \
                        room_jid in app.gc_connected[account] and \
                        app.gc_connected[account][room_jid]:
                    # account and groupchat are connected
                    connected_account = account
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
                      keyID,
                      account,
                      type_='chat',
                      subject=None):
        """
        Can be called from send_chat_message (default when send_message) or
        send_single_message
        """
        if not jid or not message:
            return False
        if not keyID:
            keyID = ''

        connected_account, contact = self._get_account_and_contact(
            account, jid)
        if connected_account:
            connection = app.connections[connected_account]
            sessions = connection.get_sessions(jid)
            if sessions:
                session = sessions[0]
            else:
                session = connection.make_new_session(jid)
            ctrl = app.interface.msg_win_mgr.search_control(
                jid, connected_account)
            if ctrl:
                ctrl.send_message(message)
            else:
                app.nec.push_outgoing_event(
                    MessageOutgoingEvent(
                        None,
                        account=connected_account,
                        jid=jid,
                        message=message,
                        keyID=keyID,
                        type_=type_,
                        control=ctrl))

            return True
        return False

    def send_chat_message(self, jid, message, keyID, account):
        """
        Send chat 'message' to 'jid', using account (optional) 'account'. If keyID
        is specified, encrypt the message with the pgp key
        """
        jid = self._get_real_jid(jid, account)
        return self._send_message(jid, message, keyID, account)

    def send_single_message(self, jid, subject, message, keyID, account):
        """
        Send single 'message' to 'jid', using account (optional) 'account'. If
        keyID is specified, encrypt the message with the pgp key
        """
        jid = self._get_real_jid(jid, account)
        return self._send_message(jid, message, keyID, account, 'normal',
                                  subject)

    def send_groupchat_message(self, room_jid, message, account):
        """
        Send 'message' to groupchat 'room_jid', using account (optional) 'account'
        """
        if not room_jid or not message:
            return False
        connected_account = self._get_account_for_groupchat(account, room_jid)
        if connected_account:
            connection = app.connections[connected_account]
            app.nec.push_outgoing_event(
                GcMessageOutgoingEvent(
                    None,
                    account=connected_account,
                    jid=room_jid,
                    message=message))
            return True
        return False

    def open_chat(self, jid, account, message):
        """
        Shows the tabbed window for new message to 'jid', using account (optional)
        'account'
        """
        if not jid:
            raise dbus_support.MissingArgument()
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
            if app.connections[acct].connected > 1:  # account is  online
                contact = app.contacts.get_first_contact_from_jid(acct, jid)
                if app.interface.msg_win_mgr.has_window(jid, acct):
                    connected_account = acct
                    break
                # jid is in roster
                elif contact:
                    minimized_control = \
                        jid in app.interface.minimized_controls[acct]
                    connected_account = acct
                    break
                # we send the message to jid not in roster, because account is
                # specified, or there is only one account
                elif account:
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
        if status not in ('offline', 'online', 'chat', 'away', 'xa', 'dnd',
                          'invisible'):
            status = ''
        if account:
            if not status:
                if account not in app.connections:
                    return False
                status = app.SHOW_LIST[app.connections[account].connected]
            GLib.idle_add(app.interface.roster.send_status, account, status,
                          message)
        else:
            # account not specified, so change the status of all accounts
            for acc in app.contacts.get_accounts():
                if not app.config.get_per('accounts', acc,
                                          'sync_with_global_status'):
                    continue
                if status:
                    status_ = status
                else:
                    if acc not in app.connections:
                        continue
                    status_ = app.SHOW_LIST[app.connections[acc].connected]
                GLib.idle_add(app.interface.roster.send_status, acc, status_,
                              message)
        return False

    def set_priority(self, prio, account):
        """
        set_priority(prio, account). Account is optional - if not specified
        priority is changed for all accounts. That are synced with global status
        """
        if account:
            app.config.set_per('accounts', account, 'priority', prio)
            show = app.SHOW_LIST[app.connections[account].connected]
            status = app.connections[account].status
            GLib.idle_add(app.connections[account].change_status, show, status)
        else:
            # account not specified, so change prio of all accounts
            for acc in app.contacts.get_accounts():
                if not app.account_is_connected(acc):
                    continue
                if not app.config.get_per('accounts', acc,
                                          'sync_with_global_status'):
                    continue
                app.config.set_per('accounts', acc, 'priority', prio)
                show = app.SHOW_LIST[app.connections[acc].connected]
                status = app.connections[acc].status
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
            index = con.connected
            result['status'] = app.SHOW_LIST[index]
            result['name'] = con.name
            result['jid'] = app.get_jid_from_account(con.name)
            result['message'] = con.status
            result['priority'] = str(con.priority)
            result['resource'] = app.config.get_per('accounts', con.name,
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

    def prefs_list(self):
        prefs_dict = {}

        def get_prefs(data, name, path, value):
            if value is None:
                return
            key = ''
            if path is not None:
                for node in path:
                    key += node + '#'
            key += name
            prefs_dict[key] = str(value)

        app.config.foreach(get_prefs)
        return prefs_dict

    def prefs_store(self):
        try:
            app.interface.save_config()
        except Exception:
            return False
        return True

    def prefs_del(self, key):
        if not key:
            return False
        key_path = key.split('#', 2)
        if len(key_path) != 3:
            return False
        if key_path[2] == '*':
            app.config.del_per(key_path[0], key_path[1])
        else:
            app.config.del_per(key_path[0], key_path[1], key_path[2])
        return True

    def prefs_put(self, key):
        if not key:
            return False
        key_path = key.split('#', 2)
        if len(key_path) < 3:
            subname, value = key.split('=', 1)
            app.config.set(subname, value)
            return True
        subname, value = key_path[2].split('=', 1)
        app.config.set_per(key_path[0], key_path[1], subname, value)
        return True

    def add_contact(self, jid, account):
        if account:
            if account in app.connections and \
                    app.connections[account].connected > 1:
                # if given account is active, use it
                AddNewContactWindow(account=account, jid=jid)
            else:
                # wrong account
                return False
        else:
            # if account is not given, show account combobox
            AddNewContactWindow(account=None, jid=jid)
        return True

    def remove_contact(self, jid, account):
        jid = self._get_real_jid(jid, account)
        accounts = app.contacts.get_accounts()

        # if there is only one account in roster, take it as default
        if account:
            accounts = [account]
        contact_exists = False
        for account in accounts:
            contacts = app.contacts.get_contacts(account, jid)
            if contacts:
                app.connections[account].get_module('Presence').unsubscribe(jid)
                for contact in contacts:
                    app.interface.roster.remove_contact(contact, account)
                app.contacts.remove_jid(account, jid)
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
        for account in accounts:
            # Does jid exists in roster of one account ?
            if app.contacts.get_contacts(account, jid):
                return jid
            if not nick_in_roster:
                # look in all contact if one has jid as nick
                for jid_ in app.contacts.get_jid_list(account):
                    c = app.contacts.get_contacts(account, jid_)
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
        contact_dict['name'] = GLib.Variant('s', prim_contact.name)
        contact_dict['show'] = GLib.Variant('s', prim_contact.show)
        contact_dict['jid'] = GLib.Variant('s', prim_contact.jid)
        if prim_contact.keyID:
            keyID = None
            if len(prim_contact.keyID) == 8:
                keyID = prim_contact.keyID
            elif len(prim_contact.keyID) == 16:
                keyID = prim_contact.keyID[8:]
            if keyID:
                contact_dict['openpgp'] = GLib.Variant('s', keyID)
        resources = GLib.VariantBuilder(GLib.VariantType('a(sis)'))
        for contact in contacts:
            resource_props = (contact.resource, int(contact.priority),
                              contact.status)
            resources.add_value(GLib.Variant("(sis)", resource_props))
        contact_dict['resources'] = resources.end()
        #contact_dict['groups'] = []  # TODO
        #for group in prim_contact.groups:
        #    contact_dict['groups'].append((group, ))
        return contact_dict

    def get_unread_msgs_number(self):
        return str(app.events.get_nb_events())

    def start_chat(self, account):
        if not account:
            # error is shown in gajim-remote check_arguments(..)
            return False
        app.app.activate_action('start-chat')
        return True

    def send_xml(self, xml, account):
        if account:
            app.connections[account].send_stanza(str(xml))
        else:
            for acc in app.contacts.get_accounts():
                app.connections[acc].send_stanza(str(xml))

    def change_avatar(self, picture, account):
        filesize = os.path.getsize(picture)
        invalid_file = False
        if os.path.isfile(picture):
            stat = os.stat(picture)
            if stat[6] == 0:
                invalid_file = True
        else:
            invalid_file = True
        if not invalid_file and filesize < 16384:
            sha = app.interface.save_avatar(picture, publish=True)
            if sha is None:
                return
            app.config.set_per('accounts', self.name, 'avatar_sha', sha)
            data = app.interface.get_avatar(sha, publish=True)
            avatar = base64.b64encode(data).decode('utf-8')
            avatar_mime_type = mimetypes.guess_type(picture)[0]
            vcard = {}
            vcard['PHOTO'] = {'BINVAL': avatar}
            if avatar_mime_type:
                vcard['PHOTO']['TYPE'] = avatar_mime_type
            if account:
                app.connections[account].get_module('VCardTemp').send_vcard(
                    vcard, sha)
            else:
                for acc in app.connections:
                    app.connections[acc].get_module('VCardTemp').send_vcard(
                        vcard, sha)

    def join_room(self, room_jid, nick, password, account):
        if not account:
            # get the first connected account
            accounts = app.connections.keys()
            for acct in accounts:
                if app.account_is_connected(acct):
                    if not app.connections[acct].is_zeroconf:
                        account = acct
                        break
            if not account:
                return

        if app.connections[account].is_zeroconf:
            # zeroconf not support groupchats
            return

        if not nick:
            app.interface.join_gc_minimal(account, room_jid)
        else:
            app.interface.join_gc_room(account, room_jid, nick, password)

    def Introspect(self):
        return self.__doc__
