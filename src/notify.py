# -*- coding:utf-8 -*-
## src/notify.py
##
## Copyright (C) 2005 Sebastian Estienne
## Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2010 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
##                    Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
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
import time
from dialogs import PopupNotificationWindow
import gobject
import gtkgui_helpers
import gtk

from common import gajim
from common import helpers
from common import ged

from common import dbus_support
if dbus_support.supported:
    import dbus
    import dbus.glib


USER_HAS_PYNOTIFY = True # user has pynotify module
try:
    import pynotify
    pynotify.init('Gajim Notification')
except ImportError:
    USER_HAS_PYNOTIFY = False

def get_show_in_roster(event, account, contact, session=None):
    """
    Return True if this event must be shown in roster, else False
    """
    if event == 'gc_message_received':
        return True
    num = get_advanced_notification(event, account, contact)
    if num is not None:
        if gajim.config.get_per('notifications', str(num), 'roster') == 'yes':
            return True
        if gajim.config.get_per('notifications', str(num), 'roster') == 'no':
            return False
    if event == 'message_received':
        if session and session.control:
            return False
    return True

def get_show_in_systray(event, account, contact, type_=None):
    """
    Return True if this event must be shown in systray, else False
    """
    num = get_advanced_notification(event, account, contact)
    if num is not None:
        if gajim.config.get_per('notifications', str(num), 'systray') == 'yes':
            return True
        if gajim.config.get_per('notifications', str(num), 'systray') == 'no':
            return False
    if type_ == 'printed_gc_msg' and not gajim.config.get(
    'notify_on_all_muc_messages'):
        # it's not an highlighted message, don't show in systray
        return False
    return gajim.config.get('trayicon_notification_on_events')

def get_advanced_notification(event, account, contact):
    """
    Returns the number of the first (top most) advanced notification else None
    """
    num = 0
    notif = gajim.config.get_per('notifications', str(num))
    while notif:
        recipient_ok = False
        status_ok = False
        tab_opened_ok = False
        # test event
        if gajim.config.get_per('notifications', str(num), 'event') == event:
            # test recipient
            recipient_type = gajim.config.get_per('notifications', str(num),
                'recipient_type')
            recipients = gajim.config.get_per('notifications', str(num),
                'recipients').split()
            if recipient_type == 'all':
                recipient_ok = True
            elif recipient_type == 'contact' and contact.jid in recipients:
                recipient_ok = True
            elif recipient_type == 'group':
                for group in contact.groups:
                    if group in contact.groups:
                        recipient_ok = True
                        break
        if recipient_ok:
            # test status
            our_status = gajim.SHOW_LIST[gajim.connections[account].connected]
            status = gajim.config.get_per('notifications', str(num), 'status')
            if status == 'all' or our_status in status.split():
                status_ok = True
        if status_ok:
            # test window_opened
            tab_opened = gajim.config.get_per('notifications', str(num),
                'tab_opened')
            if tab_opened == 'both':
                tab_opened_ok = True
            else:
                chat_control = helpers.get_chat_control(account, contact)
                if (chat_control and tab_opened == 'yes') or (not chat_control \
                and tab_opened == 'no'):
                    tab_opened_ok = True
        if tab_opened_ok:
            return num

        num += 1
        notif = gajim.config.get_per('notifications', str(num))

def notify(event, jid, account, parameters, advanced_notif_num=None):
    """
    Check what type of notifications we want, depending on basic and the
    advanced configuration of notifications and do these notifications;
    advanced_notif_num holds the number of the first (top most) advanced
    notification
    """
    # First, find what notifications we want
    do_popup = False
    do_sound = False
    do_cmd = False
    if event == 'status_change':
        new_show = parameters[0]
        status_message = parameters[1]
        # Default: No popup for status change
    elif event == 'contact_connected':
        status_message = parameters
        j = gajim.get_jid_without_resource(jid)
        server = gajim.get_server_from_jid(j)
        account_server = account + '/' + server
        block_transport = False
        if account_server in gajim.block_signed_in_notifications and \
        gajim.block_signed_in_notifications[account_server]:
            block_transport = True
        if helpers.allow_showing_notification(account, 'notify_on_signin') and \
        not gajim.block_signed_in_notifications[account] and \
        not block_transport:
            do_popup = True
        if gajim.config.get_per('soundevents', 'contact_connected',
        'enabled') and not gajim.block_signed_in_notifications[account] and \
        not block_transport and helpers.allow_sound_notification(account,
        event, advanced_notif_num):
            do_sound = True
    elif event == 'contact_disconnected':
        status_message = parameters
        if helpers.allow_showing_notification(account, 'notify_on_signout'):
            do_popup = True
        if gajim.config.get_per('soundevents', 'contact_disconnected',
        'enabled') and helpers.allow_sound_notification(account,
        event, advanced_notif_num):
            do_sound = True
    elif event == 'new_message':
        message_type = parameters[0]
        is_first_message = parameters[1]
        nickname = parameters[2]
        if gajim.config.get('notification_preview_message'):
            message = parameters[3]
            if message.startswith('/me ') or message.startswith('/me\n'):
                message = '* ' + nickname + message[3:]
        else:
            # We don't want message preview, do_preview = False
            message = ''
        focused = parameters[4]
        if helpers.allow_showing_notification(account, 'notify_on_new_message',
        advanced_notif_num, is_first_message):
            do_popup = True
        if is_first_message and helpers.allow_sound_notification(account,
        'first_message_received', advanced_notif_num):
            do_sound = True
        elif not is_first_message and focused and \
        helpers.allow_sound_notification(account,
        'next_message_received_focused', advanced_notif_num):
            do_sound = True
        elif not is_first_message and not focused and \
        helpers.allow_sound_notification(account,
        'next_message_received_unfocused', advanced_notif_num):
            do_sound = True
    else:
        print '*Event not implemeted yet*'

    if advanced_notif_num is not None and gajim.config.get_per('notifications',
    str(advanced_notif_num), 'run_command'):
        do_cmd = True

    # Do the wanted notifications
    if do_popup:
        if event in ('contact_connected', 'contact_disconnected',
        'status_change'): # Common code for popup for these three events
            if event == 'contact_disconnected':
                show_image = 'offline.png'
                suffix = '_notif_size_bw'
            else: # Status Change or Connected
                # FIXME: for status change,
                # we don't always 'online.png', but we
                # first need 48x48 for all status
                show_image = 'online.png'
                suffix = '_notif_size_colored'
            transport_name = gajim.get_transport_name_from_jid(jid)
            img_path = None
            if transport_name:
                img_path = os.path.join(helpers.get_transport_path(
                    transport_name), '48x48', show_image)
            if not img_path or not os.path.isfile(img_path):
                iconset = gajim.config.get('iconset')
                img_path = os.path.join(helpers.get_iconset_path(iconset),
                    '48x48', show_image)
            path = gtkgui_helpers.get_path_to_generic_or_avatar(img_path,
                jid=jid, suffix=suffix)
            if event == 'status_change':
                title = _('%(nick)s Changed Status') % \
                    {'nick': gajim.get_name_from_jid(account, jid)}
                text = _('%(nick)s is now %(status)s') % \
                    {'nick': gajim.get_name_from_jid(account, jid),\
                    'status': helpers.get_uf_show(gajim.SHOW_LIST[new_show])}
                if status_message:
                    text = text + " : " + status_message
                popup(_('Contact Changed Status'), jid, account,
                    path_to_image=path, title=title, text=text)
            elif event == 'contact_connected':
                title = _('%(nickname)s Signed In') % \
                    {'nickname': gajim.get_name_from_jid(account, jid)}
                text = ''
                if status_message:
                    text = status_message
                popup(_('Contact Signed In'), jid, account,
                    path_to_image=path, title=title, text=text)
            elif event == 'contact_disconnected':
                title = _('%(nickname)s Signed Out') % \
                    {'nickname': gajim.get_name_from_jid(account, jid)}
                text = ''
                if status_message:
                    text = status_message
                popup(_('Contact Signed Out'), jid, account,
                    path_to_image=path, title=title, text=text)
        elif event == 'new_message':
            if message_type == 'normal': # single message
                event_type = _('New Single Message')
                img_name = 'gajim-single_msg_recv'
                title = _('New Single Message from %(nickname)s') % \
                    {'nickname': nickname}
                text = message
            elif message_type == 'pm': # private message
                event_type = _('New Private Message')
                room_name = gajim.get_nick_from_jid(jid)
                img_name = 'gajim-priv_msg_recv'
                title = _('New Private Message from group chat %s') % room_name
                if message:
                    text = _('%(nickname)s: %(message)s') % \
                        {'nickname': nickname, 'message': message}
                else:
                    text = _('Messaged by %(nickname)s') % \
                        {'nickname': nickname}

            else: # chat message
                event_type = _('New Message')
                img_name = 'gajim-chat_msg_recv'
                title = _('New Message from %(nickname)s') % \
                    {'nickname': nickname}
                text = message
            img_path = gtkgui_helpers.get_icon_path(img_name, 48)
            popup(event_type, jid, account, message_type,
                path_to_image=img_path, title=title, text=text)

    if do_sound:
        snd_file = None
        snd_event = None # If not snd_file, play the event
        if event == 'new_message':
            if advanced_notif_num is not None and gajim.config.get_per(
            'notifications', str(advanced_notif_num), 'sound') == 'yes':
                snd_file = gajim.config.get_per('notifications',
                    str(advanced_notif_num), 'sound_file')
            elif advanced_notif_num is not None and gajim.config.get_per(
            'notifications', str(advanced_notif_num), 'sound') == 'no':
                pass # do not set snd_event
            elif is_first_message:
                snd_event = 'first_message_received'
            elif focused:
                snd_event = 'next_message_received_focused'
            else:
                snd_event = 'next_message_received_unfocused'
        elif event in ('contact_connected', 'contact_disconnected'):
            snd_event = event
        if snd_file:
            helpers.play_sound_file(snd_file)
        if snd_event:
            helpers.play_sound(snd_event)

    if do_cmd:
        command = gajim.config.get_per('notifications', str(advanced_notif_num),
            'command')
        try:
            helpers.exec_command(command)
        except Exception:
            pass

def popup(event_type, jid, account, msg_type='', path_to_image=None, title=None,
text=None):
    """
    Notify a user of an event. It first tries to a valid implementation of
    the Desktop Notification Specification. If that fails, then we fall back to
    the older style PopupNotificationWindow method
    """
    # default image
    if not path_to_image:
        path_to_image = gtkgui_helpers.get_icon_path('gajim-chat_msg_recv', 48)

    # Try to show our popup via D-Bus and notification daemon
    if gajim.config.get('use_notif_daemon') and dbus_support.supported:
        try:
            DesktopNotification(event_type, jid, account, msg_type,
                path_to_image, title, gobject.markup_escape_text(text))
            return  # sucessfully did D-Bus Notification procedure!
        except dbus.DBusException, e:
            # Connection to D-Bus failed
            gajim.log.debug(str(e))
        except TypeError, e:
            # This means that we sent the message incorrectly
            gajim.log.debug(str(e))

    # Ok, that failed. Let's try pynotify, which also uses notification daemon
    if gajim.config.get('use_notif_daemon') and USER_HAS_PYNOTIFY:
        if not text and event_type == 'new_message':
            # empty text for new_message means do_preview = False
            # -> default value for text
            _text = gobject.markup_escape_text(
                gajim.get_name_from_jid(account, jid))
        else:
            _text = gobject.markup_escape_text(text)

        if not title:
            _title = ''
        else:
            _title = title

        notification = pynotify.Notification(_title, _text)
        timeout = gajim.config.get('notification_timeout') * 1000 # make it ms
        notification.set_timeout(timeout)

        notification.set_category(event_type)
        notification.set_data('event_type', event_type)
        notification.set_data('jid', jid)
        notification.set_data('account', account)
        notification.set_data('msg_type', msg_type)
        notification.set_property('icon-name', path_to_image)
        if 'actions' in pynotify.get_server_caps():
            notification.add_action('default', 'Default Action',
                    on_pynotify_notification_clicked)

        try:
            notification.show()
            return
        except gobject.GError, e:
            # Connection to notification-daemon failed, see #2893
            gajim.log.debug(str(e))

    # Either nothing succeeded or the user wants old-style notifications
    instance = PopupNotificationWindow(event_type, jid, account, msg_type,
        path_to_image, title, text)
    gajim.interface.roster.popup_notification_windows.append(instance)

def on_pynotify_notification_clicked(notification, action):
    jid = notification.get_data('jid')
    account = notification.get_data('account')
    msg_type = notification.get_data('msg_type')

    notification.close()
    gajim.interface.handle_event(account, jid, msg_type)

class Notification:
    """
    Handle notifications
    """
    def __init__(self):
        gajim.ged.register_event_handler('notification', ged.GUI2,
            self._nec_notification)

    def _nec_notification(self, obj):
        if obj.do_popup:
            popup(obj.popup_event_type, obj.jid, obj.conn.name,
                obj.popup_msg_type, path_to_image=obj.popup_image,
                title=obj.popup_title, text=obj.popup_text)

        if obj.do_sound:
            if obj.sound_file:
                helpers.play_sound_file(obj.sound_file)
            elif obj.sound_event:
                helpers.play_sound(obj.sound_event)

        if obj.do_command:
            try:
                helpers.exec_command(obj.command)
            except Exception:
                pass

class NotificationResponseManager:
    """
    Collect references to pending DesktopNotifications and manages there
    signalling. This is necessary due to a bug in DBus where you can't remove a
    signal from an interface once it's connected
    """

    def __init__(self):
        self.pending = {}
        self.received = []
        self.interface = None

    def attach_to_interface(self):
        if self.interface is not None:
            return
        self.interface = dbus_support.get_notifications_interface()
        self.interface.connect_to_signal('ActionInvoked',
            self.on_action_invoked)
        self.interface.connect_to_signal('NotificationClosed', self.on_closed)

    def on_action_invoked(self, id_, reason):
        self.received.append((id_, time.time(), reason))
        if id_ in self.pending:
            notification = self.pending[id_]
            notification.on_action_invoked(id_, reason)
            del self.pending[id_]
        if len(self.received) > 20:
            curt = time.time()
            for rec in self.received:
                diff = curt - rec[1]
                if diff > 10:
                    self.received.remove(rec)

    def on_closed(self, id_, reason=None):
        if id_ in self.pending:
            del self.pending[id_]

    def add_pending(self, id_, object_):
        # Check to make sure that we handle an event immediately if we're adding
        # an id that's already been triggered
        for rec in self.received:
            if rec[0] == id_:
                object_.on_action_invoked(id_, rec[2])
                self.received.remove(rec)
                return
        if id_ not in self.pending:
            # Add it
            self.pending[id_] = object_
        else:
            # We've triggered an event that has a duplicate ID!
            gajim.log.debug('Duplicate ID of notification. Can\'t handle this.')

notification_response_manager = NotificationResponseManager()

class DesktopNotification:
    """
    A DesktopNotification that interfaces with D-Bus via the Desktop
    Notification Specification
    """

    def __init__(self, event_type, jid, account, msg_type='',
    path_to_image=None, title=None, text=None):
        self.path_to_image = path_to_image
        self.event_type = event_type
        self.title = title
        self.text = text
        # 0.3.1 is the only version of notification daemon that has no way
        # to determine which version it is. If no method exists, it means
        # they're using that one.
        self.default_version = [0, 3, 1]
        self.account = account
        self.jid = jid
        self.msg_type = msg_type

        # default value of text
        if not text and event_type == 'new_message':
            # empty text for new_message means do_preview = False
            self.text = gajim.get_name_from_jid(account, jid)

        if not title:
            self.title = event_type # default value

        if event_type == _('Contact Signed In'):
            ntype = 'presence.online'
        elif event_type == _('Contact Signed Out'):
            ntype = 'presence.offline'
        elif event_type in (_('New Message'), _('New Single Message'),
        _('New Private Message')):
            ntype = 'im.received'
        elif event_type == _('File Transfer Request'):
            ntype = 'transfer'
        elif event_type == _('File Transfer Error'):
            ntype = 'transfer.error'
        elif event_type in (_('File Transfer Completed'),
        _('File Transfer Stopped')):
            ntype = 'transfer.complete'
        elif event_type == _('New E-mail'):
            ntype = 'email.arrived'
        elif event_type == _('Groupchat Invitation'):
            ntype = 'im.invitation'
        elif event_type == _('Contact Changed Status'):
            ntype = 'presence.status'
        elif event_type == _('Connection Failed'):
            ntype = 'connection.failed'
        elif event_type == _('Subscription request'):
            ntype = 'subscription.request'
        elif event_type == _('Unsubscribed'):
            ntype = 'unsubscribed'
        else:
            # default failsafe values
            self.path_to_image = gtkgui_helpers.get_icon_path(
                'gajim-chat_msg_recv', 48)
            ntype = 'im' # Notification Type

        self.notif = dbus_support.get_notifications_interface(self)
        if self.notif is None:
            raise dbus.DBusException('unable to get notifications interface')
        self.ntype = ntype

        if self.kde_notifications:
            self.attempt_notify()
        else:
            self.capabilities = self.notif.GetCapabilities()
            if self.capabilities is None:
                self.capabilities = ['actions']
            self.get_version()

    def attempt_notify(self):
        timeout = gajim.config.get('notification_timeout') # in seconds
        ntype = self.ntype
        if self.kde_notifications:
            notification_text = ('<html><img src="%(image)s" align=left />' \
                '%(title)s<br/>%(text)s</html>') % {'title': self.title,
                'text': self.text, 'image': self.path_to_image}
            gajim_icon = gtkgui_helpers.get_icon_path('gajim', 48)
            try:
                self.notif.Notify(
                    dbus.String(_('Gajim')),        # app_name (string)
                    dbus.UInt32(0),                 # replaces_id (uint)
                    ntype,                          # event_id (string)
                    dbus.String(gajim_icon),        # app_icon (string)
                    dbus.String(''),                # summary (string)
                    dbus.String(notification_text), # body (string)
                    # actions (stringlist)
                    (dbus.String('default'), dbus.String(self.event_type),
                    dbus.String('ignore'), dbus.String(_('Ignore'))),
                    [],                                                                             # hints (not used in KDE yet)
                    dbus.UInt32(timeout*1000),      # timeout (int), in ms
                    reply_handler=self.attach_by_id,
                    error_handler=self.notify_another_way)
                return
            except Exception:
                pass
        version = self.version
        if version[:2] == [0, 2]:
            actions = {}
            if 'actions' in self.capabilities:
                actions = {'default': 0}
            try:
                self.notif.Notify(
                    dbus.String(_('Gajim')),
                    dbus.String(self.path_to_image),
                    dbus.UInt32(0),
                    ntype,
                    dbus.Byte(0),
                    dbus.String(self.title),
                    dbus.String(self.text),
                    [dbus.String(self.path_to_image)],
                    actions,
                    [''],
                    True,
                    dbus.UInt32(timeout),
                    reply_handler=self.attach_by_id,
                    error_handler=self.notify_another_way)
            except AttributeError:
                # we're actually dealing with the newer version
                version = [0, 3, 1]
        if version > [0, 3]:
            if gajim.interface.systray_enabled and \
            gajim.config.get('attach_notifications_to_systray'):
                status_icon = gajim.interface.systray.status_icon
                x, y, width, height = status_icon.get_geometry()[1]
                pos_x = x + (width / 2)
                pos_y = y + (height / 2)
                hints = {'x': pos_x, 'y': pos_y}
            else:
                hints = {}
            if version >= [0, 3, 2]:
                hints['urgency'] = dbus.Byte(0) # Low Urgency
                hints['category'] = dbus.String(ntype)
                # it seems notification-daemon doesn't like empty text
                if self.text:
                    text = self.text
                else:
                    text = ' '
                if os.environ.get('KDE_FULL_SESSION') == 'true':
                    self.path_to_image = os.path.abspath(self.path_to_image)
                    text = '<table style=\'padding: 3px\'><tr><td>' \
                        '<img src=\"%s\"></td><td width=20> </td>' \
                        '<td>%s</td></tr></table>' % (self.path_to_image,
                        text)
                    self.path_to_image = os.path.abspath(
                        gtkgui_helpers.get_icon_path('gajim', 48))
                actions = ()
                if 'actions' in self.capabilities:
                    actions = (dbus.String('default'), dbus.String(
                        self.event_type))
                try:
                    self.notif.Notify(
                        dbus.String(_('Gajim')),
                        # this notification does not replace other
                        dbus.UInt32(0),
                        dbus.String(self.path_to_image),
                        dbus.String(self.title),
                        dbus.String(text),
                        actions,
                        hints,
                        dbus.UInt32(timeout*1000),
                        reply_handler=self.attach_by_id,
                        error_handler=self.notify_another_way)
                except Exception, e:
                    self.notify_another_way(e)
            else:
                try:
                    self.notif.Notify(
                        dbus.String(_('Gajim')),
                        dbus.String(self.path_to_image),
                        dbus.UInt32(0),
                        dbus.String(self.title),
                        dbus.String(self.text),
                        dbus.String(''),
                        hints,
                        dbus.UInt32(timeout*1000),
                        reply_handler=self.attach_by_id,
                        error_handler=self.notify_another_way)
                except Exception, e:
                    self.notify_another_way(e)

    def attach_by_id(self, id_):
        self.id = id_
        notification_response_manager.attach_to_interface()
        notification_response_manager.add_pending(self.id, self)

    def notify_another_way(self, e):
        gajim.log.debug('Error when trying to use notification daemon: %s' % \
            str(e))
        instance = PopupNotificationWindow(self.event_type, self.jid,
            self.account, self.msg_type, self.path_to_image, self.title,
            self.text)
        gajim.interface.roster.popup_notification_windows.append(instance)

    def on_action_invoked(self, id_, reason):
        if self.notif is None:
            return
        self.notif.CloseNotification(dbus.UInt32(id_))
        self.notif = None

        if reason == 'ignore':
            return

        gajim.interface.handle_event(self.account, self.jid, self.msg_type)

    def version_reply_handler(self, name, vendor, version, spec_version=None):
        if spec_version:
            version = spec_version
        elif vendor == 'Xfce' and version.startswith('0.1.0'):
            version = '0.9'
        version_list = version.split('.')
        self.version = []
        try:
            while len(version_list):
                self.version.append(int(version_list.pop(0)))
        except ValueError:
            self.version_error_handler_3_x_try(None)
        self.attempt_notify()

    def get_version(self):
        self.notif.GetServerInfo(
            reply_handler=self.version_reply_handler,
            error_handler=self.version_error_handler_2_x_try)

    def version_error_handler_2_x_try(self, e):
        self.notif.GetServerInformation(
            reply_handler=self.version_reply_handler,
            error_handler=self.version_error_handler_3_x_try)

    def version_error_handler_3_x_try(self, e):
        self.version = self.default_version
        self.attempt_notify()
