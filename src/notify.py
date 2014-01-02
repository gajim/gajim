# -*- coding:utf-8 -*-
## src/notify.py
##
## Copyright (C) 2005 Sebastian Estienne
## Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
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
from gi.repository import GObject
from gi.repository import GLib
import gtkgui_helpers
from gi.repository import Gtk

from common import gajim
from common import helpers
from common import ged

from common import dbus_support
if dbus_support.supported:
    import dbus


USER_HAS_PYNOTIFY = True # user has pynotify module
try:
    from gi.repository import Notify
    Notify.init('Gajim Notification')
except ImportError:
    USER_HAS_PYNOTIFY = False

def get_show_in_roster(event, account, contact, session=None):
    """
    Return True if this event must be shown in roster, else False
    """
    if event == 'gc_message_received':
        return True
    if event == 'message_received':
        if session and session.control:
            return False
    return True

def get_show_in_systray(event, account, contact, type_=None):
    """
    Return True if this event must be shown in systray, else False
    """
    if type_ == 'printed_gc_msg' and not gajim.config.get(
    'notify_on_all_muc_messages'):
        # it's not an highlighted message, don't show in systray
        return False
    return gajim.config.get('trayicon_notification_on_events')

def popup(event_type, jid, account, msg_type='', path_to_image=None, title=None,
text=None, timeout=-1):
    """
    Notify a user of an event. It first tries to a valid implementation of
    the Desktop Notification Specification. If that fails, then we fall back to
    the older style PopupNotificationWindow method
    """
    # default image
    if not path_to_image:
        path_to_image = gtkgui_helpers.get_icon_path('gajim-chat_msg_recv', 48)

    if timeout < 0:
        timeout = gajim.config.get('notification_timeout')

    # Try to show our popup via D-Bus and notification daemon
    if gajim.config.get('use_notif_daemon') and dbus_support.supported:
        try:
            DesktopNotification(event_type, jid, account, msg_type,
                path_to_image, title, GLib.markup_escape_text(text), timeout)
            return  # sucessfully did D-Bus Notification procedure!
        except dbus.DBusException as e:
            # Connection to D-Bus failed
            gajim.log.debug(str(e))
        except TypeError as e:
            # This means that we sent the message incorrectly
            gajim.log.debug(str(e))

    # Ok, that failed. Let's try pynotify, which also uses notification daemon
    if gajim.config.get('use_notif_daemon') and USER_HAS_PYNOTIFY:
        if not text and event_type == 'new_message':
            # empty text for new_message means do_preview = False
            # -> default value for text
            _text = GLib.markup_escape_text(gajim.get_name_from_jid(account,
                jid))
        else:
            _text = GLib.markup_escape_text(text)

        if not title:
            _title = ''
        else:
            _title = title

        notification = Notify.Notification(_title, _text)
        notification.set_timeout(timeout*1000)

        notification.set_category(event_type)
        notification.set_data('event_type', event_type)
        notification.set_data('jid', jid)
        notification.set_data('account', account)
        notification.set_data('msg_type', msg_type)
        notification.set_property('icon-name', path_to_image)
        if 'actions' in Notify.get_server_caps():
            notification.add_action('default', 'Default Action',
                    on_pynotify_notification_clicked)

        try:
            notification.show()
            return
        except GObject.GError as e:
            # Connection to notification-daemon failed, see #2893
            gajim.log.debug(str(e))

    # Either nothing succeeded or the user wants old-style notifications
    instance = PopupNotificationWindow(event_type, jid, account, msg_type,
        path_to_image, title, text, timeout)
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
            if obj.popup_image:
                icon_path = gtkgui_helpers.get_icon_path(obj.popup_image, 48)
                if icon_path:
                    image_path = icon_path
            elif obj.popup_image_path:
                image_path = obj.popup_image_path
            else:
                image_path = ''
            popup(obj.popup_event_type, obj.jid, obj.conn.name,
                obj.popup_msg_type, path_to_image=image_path,
                title=obj.popup_title, text=obj.popup_text,
                timeout=obj.popup_timeout)

        if obj.do_sound:
            if obj.sound_file:
                helpers.play_sound_file(obj.sound_file)
            elif obj.sound_event:
                helpers.play_sound(obj.sound_event)

        if obj.do_command:
            try:
                helpers.exec_command(obj.command, use_shell=True)
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
        if id_ in self.pending:
            notification = self.pending[id_]
            notification.on_action_invoked(id_, reason)
            del self.pending[id_]
            return
        # got an action on popup that isn't handled yet? Maybe user clicked too
        # fast. Remember it.
        self.received.append((id_, time.time(), reason))
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
    path_to_image=None, title=None, text=None, timeout=-1):
        self.path_to_image = os.path.abspath(path_to_image)
        self.event_type = event_type
        self.title = title
        self.text = text
        self.timeout = timeout
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
                    [], # hints (not used in KDE yet)
                    dbus.UInt32(self.timeout*1000), # timeout (int), in ms
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
                    dbus.UInt32(self.timeout),
                    reply_handler=self.attach_by_id,
                    error_handler=self.notify_another_way)
            except AttributeError:
                # we're actually dealing with the newer version
                version = [0, 3, 1]
        if version > [0, 3]:
            if gajim.interface.systray_enabled and \
            gajim.config.get('attach_notifications_to_systray'):
                status_icon = gajim.interface.systray.status_icon
                rect = status_icon.get_geometry()[2]
                x, y, width, height = rect.x, rect.y, rect.width, rect.height
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
                    if len(self.text) > 200:
                        text = '%s\n...' % self.text[:200]
                else:
                    text = ' '
                if os.environ.get('KDE_FULL_SESSION') == 'true':
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
                        dbus.UInt32(self.timeout*1000),
                        reply_handler=self.attach_by_id,
                        error_handler=self.notify_another_way)
                except Exception as e:
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
                        dbus.UInt32(self.timeout*1000),
                        reply_handler=self.attach_by_id,
                        error_handler=self.notify_another_way)
                except Exception as e:
                    self.notify_another_way(e)

    def attach_by_id(self, id_):
        notification_response_manager.attach_to_interface()
        notification_response_manager.add_pending(id_, self)

    def notify_another_way(self, e):
        gajim.log.debug('Error when trying to use notification daemon: %s' % \
            str(e))
        instance = PopupNotificationWindow(self.event_type, self.jid,
            self.account, self.msg_type, self.path_to_image, self.title,
            self.text, self.timeout)
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
