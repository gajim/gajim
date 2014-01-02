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

from gi.repository import GLib
from gi.repository import Gtk
import os
import base64
import mimetypes

from common import gajim
from common import helpers
from time import time
from dialogs import AddNewContactWindow, NewChatDialog, JoinGroupchatWindow
from common import ged
from common.connection_handlers_events import MessageOutgoingEvent
from common.connection_handlers_events import GcMessageOutgoingEvent


from common import dbus_support
if dbus_support.supported:
    import dbus
    if dbus_support:
        import dbus.service

INTERFACE = 'org.gajim.dbus.RemoteInterface'
OBJ_PATH = '/org/gajim/dbus/RemoteObject'
SERVICE = 'org.gajim.dbus'

# type mapping

# in most cases it is a utf-8 string
DBUS_STRING = dbus.String

# general type (for use in dicts, where all values should have the same type)
DBUS_BOOLEAN = dbus.Boolean
DBUS_DOUBLE = dbus.Double
DBUS_INT32 = dbus.Int32
# dictionary with string key and binary value
DBUS_DICT_SV = lambda : dbus.Dictionary({}, signature="sv")
# dictionary with string key and value
DBUS_DICT_SS = lambda : dbus.Dictionary({}, signature="ss")
# empty type (there is no equivalent of None on D-Bus, but historically gajim
# used 0 instead)
DBUS_NONE = lambda : dbus.Int32(0)

def get_dbus_struct(obj):
    """
    Recursively go through all the items and replace them with their casted dbus
    equivalents
    """
    if obj is None:
        return DBUS_NONE()
    if isinstance(obj, str):
        return DBUS_STRING(obj)
    if isinstance(obj, int):
        return DBUS_INT32(obj)
    if isinstance(obj, float):
        return DBUS_DOUBLE(obj)
    if isinstance(obj, bool):
        return DBUS_BOOLEAN(obj)
    if isinstance(obj, (list, tuple)):
        result = dbus.Array([get_dbus_struct(i) for i in obj],
                signature='v')
        if result == []:
            return DBUS_NONE()
        return result
    if isinstance(obj, dict):
        result = DBUS_DICT_SV()
        for key, value in obj.items():
            result[DBUS_STRING(key)] = get_dbus_struct(value)
        if result == {}:
            return DBUS_NONE()
        return result
    # unknown type
    return DBUS_NONE()

class Remote:
    def __init__(self):
        self.signal_object = None
        session_bus = dbus_support.session_bus.SessionBus()

        bus_name = dbus.service.BusName(SERVICE, bus=session_bus)
        self.signal_object = SignalObject(bus_name)

        gajim.ged.register_event_handler('last-result-received', ged.POSTGUI,
            self.on_last_status_time)
        gajim.ged.register_event_handler('version-result-received', ged.POSTGUI,
            self.on_os_info)
        gajim.ged.register_event_handler('time-result-received', ged.POSTGUI,
            self.on_time)
        gajim.ged.register_event_handler('gmail-nofify', ged.POSTGUI,
            self.on_gmail_notify)
        gajim.ged.register_event_handler('roster-info', ged.POSTGUI,
            self.on_roster_info)
        gajim.ged.register_event_handler('presence-received', ged.POSTGUI,
            self.on_presence_received)
        gajim.ged.register_event_handler('subscribe-presence-received',
            ged.POSTGUI, self.on_subscribe_presence_received)
        gajim.ged.register_event_handler('subscribed-presence-received',
            ged.POSTGUI, self.on_subscribed_presence_received)
        gajim.ged.register_event_handler('unsubscribed-presence-received',
            ged.POSTGUI, self.on_unsubscribed_presence_received)
        gajim.ged.register_event_handler('gc-message-received',
            ged.POSTGUI, self.on_gc_message_received)
        gajim.ged.register_event_handler('our-show', ged.POSTGUI,
            self.on_our_status)
        gajim.ged.register_event_handler('account-created', ged.POSTGUI,
            self.on_account_created)
        gajim.ged.register_event_handler('vcard-received', ged.POSTGUI,
            self.on_vcard_received)
        gajim.ged.register_event_handler('chatstate-received', ged.POSTGUI,
            self.on_chatstate_received)
        gajim.ged.register_event_handler('message-sent', ged.POSTGUI,
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

    def on_last_status_time(self, obj):
        self.raise_signal('LastStatusTime', (obj.conn.name, [
            obj.jid, obj.resource, obj.seconds, obj.status]))

    def on_os_info(self, obj):
        self.raise_signal('OsInfo', (obj.conn.name, [obj.jid, obj.resource,
            obj.client_info, obj.os_info]))

    def on_time(self, obj):
        self.raise_signal('EntityTime', (obj.conn.name, [obj.jid, obj.resource,
            obj.time_info]))

    def on_gmail_notify(self, obj):
        self.raise_signal('NewGmail', (obj.conn.name, [obj.jid, obj.newmsgs,
            obj.gmail_messages_list]))

    def on_roster_info(self, obj):
        self.raise_signal('RosterInfo', (obj.conn.name, [obj.jid, obj.nickname,
            obj.sub, obj.ask, obj.groups]))

    def on_presence_received(self, obj):
        event = None
        if obj.old_show < 2 and obj.new_show > 1:
            event = 'ContactPresence'
        elif obj.old_show > 1 and obj.new_show < 2:
            event = 'ContactAbsence'
        elif obj.new_show > 1:
            event = 'ContactStatus'
        if event:
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

    def raise_signal(self, signal, arg):
        if self.signal_object:
            try:
                getattr(self.signal_object, signal)(get_dbus_struct(arg))
            except UnicodeDecodeError:
                pass # ignore error when we fail to announce on dbus


class SignalObject(dbus.service.Object):
    """
    Local object definition for /org/gajim/dbus/RemoteObject

    This docstring is not be visible, because the clients can access only the
    remote object.
    """

    def __init__(self, bus_name):
        self.first_show = True
        self.vcard_account = None

        # register our dbus API
        dbus.service.Object.__init__(self, bus_name, OBJ_PATH)

    @dbus.service.signal(INTERFACE, signature='av')
    def Roster(self, account_and_data):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def AccountPresence(self, status_and_account):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def ContactPresence(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def ContactAbsence(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def ContactStatus(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def NewMessage(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def Subscribe(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def Subscribed(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def Unsubscribed(self, account_and_jid):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def NewAccount(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def VcardInfo(self, account_and_vcard):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def LastStatusTime(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def OsInfo(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def EntityTime(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def GCPresence(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def GCMessage(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def RosterInfo(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def NewGmail(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def ChatState(self, account_and_array):
        pass

    @dbus.service.signal(INTERFACE, signature='av')
    def MessageSent(self, account_and_array):
        pass

    def raise_signal(self, signal, arg):
        """
        Raise a signal, with a single argument of unspecified type Instead of
        obj.raise_signal("Foo", bar), use obj.Foo(bar)
        """
        getattr(self, signal)(arg)

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='s')
    def get_status(self, account):
        """
        Return status (show to be exact) which is the global one unless account is
        given
        """
        if not account:
            # If user did not ask for account, returns the global status
            return DBUS_STRING(helpers.get_global_show())
        # return show for the given account
        index = gajim.connections[account].connected
        return DBUS_STRING(gajim.SHOW_LIST[index])

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='s')
    def get_status_message(self, account):
        """
        Return status which is the global one unless account is given
        """
        if not account:
            # If user did not ask for account, returns the global status
            return DBUS_STRING(str(helpers.get_global_status()))
        # return show for the given account
        status = gajim.connections[account].status
        return DBUS_STRING(status)

    def _get_account_and_contact(self, account, jid):
        """
        Get the account (if not given) and contact instance from jid
        """
        connected_account = None
        contact = None
        accounts = gajim.contacts.get_accounts()
        # if there is only one account in roster, take it as default
        # if user did not ask for account
        if not account and len(accounts) == 1:
            account = accounts[0]
        if account:
            if gajim.connections[account].connected > 1: # account is connected
                connected_account = account
                contact = gajim.contacts.get_contact_with_highest_priority(account,
                        jid)
        else:
            for account in accounts:
                contact = gajim.contacts.get_contact_with_highest_priority(account,
                        jid)
                if contact and gajim.connections[account].connected > 1:
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
        accounts = gajim.contacts.get_accounts()
        # if there is only one account in roster, take it as default
        # if user did not ask for account
        if not account and len(accounts) == 1:
            account = accounts[0]
        if account:
            if gajim.connections[account].connected > 1 and \
            room_jid in gajim.gc_connected[account] and \
            gajim.gc_connected[account][room_jid]:
                # account and groupchat are connected
                connected_account = account
        else:
            for account in accounts:
                if gajim.connections[account].connected > 1 and \
                room_jid in gajim.gc_connected[account] and \
                gajim.gc_connected[account][room_jid]:
                    # account and groupchat are connected
                    connected_account = account
                    break
        return connected_account

    @dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
    def send_file(self, file_path, jid, account):
        """
        Send file, located at 'file_path' to 'jid', using account (optional)
        'account'
        """
        jid = self._get_real_jid(jid, account)
        connected_account, contact = self._get_account_and_contact(account, jid)

        if connected_account:
            if file_path.startswith('file://'):
                file_path=file_path[7:]
            if os.path.isfile(file_path): # is it file?
                gajim.interface.instances['file_transfers'].send_file(
                        connected_account, contact, file_path)
                return DBUS_BOOLEAN(True)
        return DBUS_BOOLEAN(False)

    def _send_message(self, jid, message, keyID, account, type_ = 'chat',
    subject = None):
        """
        Can be called from send_chat_message (default when send_message) or
        send_single_message
        """
        if not jid or not message:
            return DBUS_BOOLEAN(False)
        if not keyID:
            keyID = ''

        connected_account, contact = self._get_account_and_contact(account, jid)
        if connected_account:
            connection = gajim.connections[connected_account]
            sessions = connection.get_sessions(jid)
            if sessions:
                session = sessions[0]
            else:
                session = connection.make_new_session(jid)
            ctrl = gajim.interface.msg_win_mgr.search_control(jid,
                connected_account)
            if ctrl:
                ctrl.send_message(message)
            else:
                gajim.nec.push_outgoing_event(MessageOutgoingEvent(None, account=connected_account, jid=jid, message=message, keyID=keyID, type_=type_, control=ctrl))

            return DBUS_BOOLEAN(True)
        return DBUS_BOOLEAN(False)

    @dbus.service.method(INTERFACE, in_signature='ssss', out_signature='b')
    def send_chat_message(self, jid, message, keyID, account):
        """
        Send chat 'message' to 'jid', using account (optional) 'account'. If keyID
        is specified, encrypt the message with the pgp key
        """
        jid = self._get_real_jid(jid, account)
        return self._send_message(jid, message, keyID, account)

    @dbus.service.method(INTERFACE, in_signature='sssss', out_signature='b')
    def send_single_message(self, jid, subject, message, keyID, account):
        """
        Send single 'message' to 'jid', using account (optional) 'account'. If
        keyID is specified, encrypt the message with the pgp key
        """
        jid = self._get_real_jid(jid, account)
        return self._send_message(jid, message, keyID, account, 'normal', subject)

    @dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
    def send_groupchat_message(self, room_jid, message, account):
        """
        Send 'message' to groupchat 'room_jid', using account (optional) 'account'
        """
        if not room_jid or not message:
            return DBUS_BOOLEAN(False)
        connected_account = self._get_account_for_groupchat(account, room_jid)
        if connected_account:
            connection = gajim.connections[connected_account]
            gajim.nec.push_outgoing_event(GcMessageOutgoingEvent(None,
                account=connected_account, jid=room_jid, message=message))
            return DBUS_BOOLEAN(True)
        return DBUS_BOOLEAN(False)

    @dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
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
            return DBUS_BOOLEAN(False)

        minimized_control = None
        if account:
            accounts = [account]
        else:
            accounts = gajim.connections.keys()
            if len(accounts) == 1:
                account = accounts[0]
        connected_account = None
        first_connected_acct = None
        for acct in accounts:
            if gajim.connections[acct].connected > 1: # account is  online
                contact = gajim.contacts.get_first_contact_from_jid(acct, jid)
                if gajim.interface.msg_win_mgr.has_window(jid, acct):
                    connected_account = acct
                    break
                # jid is in roster
                elif contact:
                    minimized_control = \
                        jid in gajim.interface.minimized_controls[acct]
                    connected_account = acct
                    break
                # we send the message to jid not in roster, because account is
                # specified, or there is only one account
                elif account:
                    connected_account = acct
                elif first_connected_acct is None:
                    first_connected_acct = acct

        # if jid is not a conntact, open-chat with first connected account
        if connected_account is None and first_connected_acct:
            connected_account = first_connected_acct

        if minimized_control:
            gajim.interface.roster.on_groupchat_maximized(None, jid,
                connected_account)

        if connected_account:
            gajim.interface.new_chat_from_jid(connected_account, jid, message)
            # preserve the 'steal focus preservation'
            win = gajim.interface.msg_win_mgr.get_window(jid,
                    connected_account).window
            if win.get_property('visible'):
                win.window.focus(Gtk.get_current_event_time())
            return DBUS_BOOLEAN(True)
        return DBUS_BOOLEAN(False)

    @dbus.service.method(INTERFACE, in_signature='sss', out_signature='b')
    def change_status(self, status, message, account):
        """
        change_status(status, message, account). Account is optional - if not
        specified status is changed for all accounts
        """
        if status not in ('offline', 'online', 'chat',
        'away', 'xa', 'dnd', 'invisible'):
            status = ''
        if account:
            if not status:
                if account not in gajim.connections:
                    return DBUS_BOOLEAN(False)
                status = gajim.SHOW_LIST[gajim.connections[account].connected]
            GLib.idle_add(gajim.interface.roster.send_status, account, status,
                message)
        else:
            # account not specified, so change the status of all accounts
            for acc in gajim.contacts.get_accounts():
                if not gajim.config.get_per('accounts', acc,
                'sync_with_global_status'):
                    continue
                if status:
                    status_ = status
                else:
                    if acc not in gajim.connections:
                        continue
                    status_ = gajim.SHOW_LIST[gajim.connections[acc].connected]
                GLib.idle_add(gajim.interface.roster.send_status, acc, status_,
                    message)
        return DBUS_BOOLEAN(False)

    @dbus.service.method(INTERFACE, in_signature='ss', out_signature='')
    def set_priority(self, prio, account):
        """
        set_priority(prio, account). Account is optional - if not specified
        priority is changed for all accounts. That are synced with global status
        """
        if account:
            gajim.config.set_per('accounts', account, 'priority', prio)
            show = gajim.SHOW_LIST[gajim.connections[account].connected]
            status = gajim.connections[account].status
            GLib.idle_add(gajim.connections[account].change_status, show,
                status)
        else:
            # account not specified, so change prio of all accounts
            for acc in gajim.contacts.get_accounts():
                if not gajim.account_is_connected(acc):
                    continue
                if not gajim.config.get_per('accounts', acc,
                'sync_with_global_status'):
                    continue
                gajim.config.set_per('accounts', acc, 'priority', prio)
                show = gajim.SHOW_LIST[gajim.connections[acc].connected]
                status = gajim.connections[acc].status
                GLib.idle_add(gajim.connections[acc].change_status, show,
                    status)

    @dbus.service.method(INTERFACE, in_signature='', out_signature='')
    def show_next_pending_event(self):
        """
        Show the window(s) with next pending event in tabbed/group chats
        """
        if gajim.events.get_nb_events():
            account, jid, event = gajim.events.get_first_systray_event()
            if not event:
                return
            gajim.interface.handle_event(account, jid, event.type_)

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='a{sv}')
    def contact_info(self, jid):
        """
        Get vcard info for a contact. Return cached value of the vcard
        """
        if not isinstance(jid, str):
            jid = str(jid)
        if not jid:
            raise dbus_support.MissingArgument()
        jid = self._get_real_jid(jid)

        cached_vcard = list(gajim.connections.values())[0].get_cached_vcard(jid)
        if cached_vcard:
            return get_dbus_struct(cached_vcard)

        # return empty dict
        return DBUS_DICT_SV()

    @dbus.service.method(INTERFACE, in_signature='', out_signature='as')
    def list_accounts(self):
        """
        List register accounts
        """
        result = gajim.contacts.get_accounts()
        result_array = dbus.Array([], signature='s')
        if result and len(result) > 0:
            for account in result:
                result_array.append(DBUS_STRING(account))
        return result_array

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='a{ss}')
    def account_info(self, account):
        """
        Show info on account: resource, jid, nick, prio, message
        """
        result = DBUS_DICT_SS()
        if account in gajim.connections:
            # account is valid
            con = gajim.connections[account]
            index = con.connected
            result['status'] = DBUS_STRING(gajim.SHOW_LIST[index])
            result['name'] = DBUS_STRING(con.name)
            result['jid'] = DBUS_STRING(gajim.get_jid_from_account(con.name))
            result['message'] = DBUS_STRING(con.status)
            result['priority'] = DBUS_STRING(str(con.priority))
            result['resource'] = DBUS_STRING(gajim.config.get_per('accounts',
                con.name, 'resource'))
        return result

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='aa{sv}')
    def list_contacts(self, account):
        """
        List all contacts in the roster. If the first argument is specified, then
        return the contacts for the specified account
        """
        result = dbus.Array([], signature='aa{sv}')
        accounts = gajim.contacts.get_accounts()
        if len(accounts) == 0:
            return result
        if account:
            accounts_to_search = [account]
        else:
            accounts_to_search = accounts
        for acct in accounts_to_search:
            if acct in accounts:
                for jid in gajim.contacts.get_jid_list(acct):
                    item = self._contacts_as_dbus_structure(
                            gajim.contacts.get_contacts(acct, jid))
                    if item:
                        result.append(item)
        return result

    @dbus.service.method(INTERFACE, in_signature='', out_signature='')
    def toggle_roster_appearance(self):
        """
        Show/hide the roster window
        """
        win = gajim.interface.roster.window
        if win.get_property('visible'):
            GLib.idle_add(win.hide)
        else:
            win.present()
            # preserve the 'steal focus preservation'
            if self._is_first():
                win.window.focus(Gtk.get_current_event_time())
            else:
                win.window.focus(long(time()))

    @dbus.service.method(INTERFACE, in_signature='', out_signature='')
    def show_roster(self):
        """
        Show the roster window
        """
        win = gajim.interface.roster.window
        win.present()
        # preserve the 'steal focus preservation'
        if self._is_first():
            win.window.focus(Gtk.get_current_event_time())
        else:
            win.window.focus(long(time()))

    @dbus.service.method(INTERFACE, in_signature='', out_signature='')
    def toggle_ipython(self):
        """
        Show/hide the ipython window
        """
        win = gajim.ipython_window
        if win:
            if win.window.is_visible():
                GLib.idle_add(win.hide)
            else:
                win.show_all()
                win.present()
        else:
            gajim.interface.create_ipython_window()

    @dbus.service.method(INTERFACE, in_signature='', out_signature='a{ss}')
    def prefs_list(self):
        prefs_dict = DBUS_DICT_SS()
        def get_prefs(data, name, path, value):
            if value is None:
                return
            key = ''
            if path is not None:
                for node in path:
                    key += node + '#'
            key += name
            prefs_dict[DBUS_STRING(key)] = DBUS_STRING(value)
        gajim.config.foreach(get_prefs)
        return prefs_dict

    @dbus.service.method(INTERFACE, in_signature='', out_signature='b')
    def prefs_store(self):
        try:
            gajim.interface.save_config()
        except Exception:
            return DBUS_BOOLEAN(False)
        return DBUS_BOOLEAN(True)

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='b')
    def prefs_del(self, key):
        if not key:
            return DBUS_BOOLEAN(False)
        key_path = key.split('#', 2)
        if len(key_path) != 3:
            return DBUS_BOOLEAN(False)
        if key_path[2] == '*':
            gajim.config.del_per(key_path[0], key_path[1])
        else:
            gajim.config.del_per(key_path[0], key_path[1], key_path[2])
        return DBUS_BOOLEAN(True)

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='b')
    def prefs_put(self, key):
        if not key:
            return DBUS_BOOLEAN(False)
        key_path = key.split('#', 2)
        if len(key_path) < 3:
            subname, value = key.split('=', 1)
            gajim.config.set(subname, value)
            return DBUS_BOOLEAN(True)
        subname, value = key_path[2].split('=', 1)
        gajim.config.set_per(key_path[0], key_path[1], subname, value)
        return DBUS_BOOLEAN(True)

    @dbus.service.method(INTERFACE, in_signature='ss', out_signature='b')
    def add_contact(self, jid, account):
        if account:
            if account in gajim.connections and \
                    gajim.connections[account].connected > 1:
                # if given account is active, use it
                AddNewContactWindow(account = account, jid = jid)
            else:
                # wrong account
                return DBUS_BOOLEAN(False)
        else:
            # if account is not given, show account combobox
            AddNewContactWindow(account = None, jid = jid)
        return DBUS_BOOLEAN(True)

    @dbus.service.method(INTERFACE, in_signature='ss', out_signature='b')
    def remove_contact(self, jid, account):
        jid = self._get_real_jid(jid, account)
        accounts = gajim.contacts.get_accounts()

        # if there is only one account in roster, take it as default
        if account:
            accounts = [account]
        contact_exists = False
        for account in accounts:
            contacts = gajim.contacts.get_contacts(account, jid)
            if contacts:
                gajim.connections[account].unsubscribe(jid)
                for contact in contacts:
                    gajim.interface.roster.remove_contact(contact, account)
                gajim.contacts.remove_jid(account, jid)
                contact_exists = True
        return DBUS_BOOLEAN(contact_exists)

    def _is_first(self):
        if self.first_show:
            self.first_show = False
            return True
        return False

    def _get_real_jid(self, jid, account = None):
        """
        Get the real jid from the given one: removes xmpp: or get jid from nick if
        account is specified, search only in this account
        """
        if account:
            accounts = [account]
        else:
            accounts = gajim.connections.keys()
        if jid.startswith('xmpp:'):
            return jid[5:] # len('xmpp:') = 5
        nick_in_roster = None # Is jid a nick ?
        for account in accounts:
            # Does jid exists in roster of one account ?
            if gajim.contacts.get_contacts(account, jid):
                return jid
            if not nick_in_roster:
                # look in all contact if one has jid as nick
                for jid_ in gajim.contacts.get_jid_list(account):
                    c = gajim.contacts.get_contacts(account, jid_)
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
        prim_contact = None # primary contact
        for contact in contacts:
            if prim_contact is None or contact.priority > prim_contact.priority:
                prim_contact = contact
        contact_dict = DBUS_DICT_SV()
        contact_dict['name'] = DBUS_STRING(prim_contact.name)
        contact_dict['show'] = DBUS_STRING(prim_contact.show)
        contact_dict['jid'] = DBUS_STRING(prim_contact.jid)
        if prim_contact.keyID:
            keyID = None
            if len(prim_contact.keyID) == 8:
                keyID = prim_contact.keyID
            elif len(prim_contact.keyID) == 16:
                keyID = prim_contact.keyID[8:]
            if keyID:
                contact_dict['openpgp'] = keyID
        contact_dict['resources'] = dbus.Array([], signature='(sis)')
        for contact in contacts:
            resource_props = dbus.Struct((DBUS_STRING(contact.resource),
                    dbus.Int32(contact.priority), DBUS_STRING(contact.status)))
            contact_dict['resources'].append(resource_props)
        contact_dict['groups'] = dbus.Array([], signature='(s)')
        for group in prim_contact.groups:
            contact_dict['groups'].append((DBUS_STRING(group),))
        return contact_dict

    @dbus.service.method(INTERFACE, in_signature='', out_signature='s')
    def get_unread_msgs_number(self):
        return DBUS_STRING(str(gajim.events.get_nb_events()))

    @dbus.service.method(INTERFACE, in_signature='s', out_signature='b')
    def start_chat(self, account):
        if not account:
            # error is shown in gajim-remote check_arguments(..)
            return DBUS_BOOLEAN(False)
        NewChatDialog(account)
        return DBUS_BOOLEAN(True)

    @dbus.service.method(INTERFACE, in_signature='ss', out_signature='')
    def send_xml(self, xml, account):
        if account:
            gajim.connections[account].send_stanza(str(xml))
        else:
            for acc in gajim.contacts.get_accounts():
                gajim.connections[acc].send_stanza(str(xml))

    @dbus.service.method(INTERFACE, in_signature='ss', out_signature='')
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
            with open(picture, 'rb') as fb:
                data = fd.read()
            avatar = base64.b64encode(data).decode('utf-8')
            avatar_mime_type = mimetypes.guess_type(picture)[0]
            vcard={}
            vcard['PHOTO'] = {'BINVAL': avatar}
            if avatar_mime_type:
                vcard['PHOTO']['TYPE'] = avatar_mime_type
            if account:
                gajim.connections[account].send_vcard(vcard)
            else:
                for acc in gajim.connections:
                    gajim.connections[acc].send_vcard(vcard)

    @dbus.service.method(INTERFACE, in_signature='ssss', out_signature='')
    def join_room(self, room_jid, nick, password, account):
        if not account:
            # get the first connected account
            accounts = gajim.connections.keys()
            for acct in accounts:
                if gajim.account_is_connected(acct):
                    if not gajim.connections[acct].is_zeroconf:
                        account = acct
                        break
            if not account:
                return

        if gajim.connections[account].is_zeroconf:
            # zeroconf not support groupchats
            return

        if not nick:
            nick = ''
            gajim.interface.instances[account]['join_gc'] = \
                            JoinGroupchatWindow(account, room_jid, nick)
        else:
            gajim.interface.join_gc_room(account, room_jid, nick, password)
