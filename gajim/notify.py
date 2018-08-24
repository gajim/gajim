#
# Copyright (C) 2005 Sebastian Estienne
# Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
#                    Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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
import sys

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

from gajim import gtkgui_helpers
from gajim.common import app
from gajim.common import helpers
from gajim.common import ged

log = logging.getLogger('gajim.notify')


def get_show_in_roster(event, account, jid, session=None):
    """
    Return True if this event must be shown in roster, else False
    """
    if event == 'gc_message_received':
        return True
    if event == 'message_received':
        if app.config.get('autopopup_chat_opened'):
            return True
        if session and session.control:
            return False
    return True


def get_show_in_systray(event, account, jid, type_=None):
    """
    Return True if this event must be shown in systray, else False
    """

    notify = app.config.get('notify_on_all_muc_messages')
    notify_for_jid = app.config.get_per(
        'rooms', jid, 'notify_on_all_messages')

    if type_ == 'printed_gc_msg' and not notify and not notify_for_jid:
        # it's not an highlighted message, don't show in systray
        return False
    return app.config.get('trayicon_notification_on_events')


class Notification:
    """
    Handle notifications
    """
    def __init__(self):
        self.daemon_capabilities = ['actions']

        # Detect if actions are supported by the notification daemon
        if sys.platform == 'linux':
            def on_proxy_ready(source, res, data=None):
                try:
                    proxy = Gio.DBusProxy.new_finish(res)
                    self.daemon_capabilities = proxy.GetCapabilities()
                except GLib.Error as e:
                    if e.domain == 'g-dbus-error-quark':
                        log.info('Notifications D-Bus connection failed: %s',
                                 e.message)
                    else:
                        raise
                else:
                    log.debug('Notifications D-Bus connected')

            log.debug('Connecting to Notifications D-Bus')
            Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION,
                                      Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
                                      None,
                                      'org.freedesktop.Notifications',
                                      '/org/freedesktop/Notifications',
                                      'org.freedesktop.Notifications',
                                      None, on_proxy_ready)

        app.ged.register_event_handler(
            'notification', ged.GUI2, self._nec_notification)
        app.ged.register_event_handler(
            'our-show', ged.GUI2, self._nec_our_status)
        app.events.event_removed_subscribe(self._on_event_removed)

    def _nec_notification(self, obj):
        if obj.do_popup:
            icon_name = self._get_icon_name(obj)
            self.popup(obj.popup_event_type, obj.jid, obj.conn.name,
                       obj.popup_msg_type, icon_name=icon_name,
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

    def _on_event_removed(self, event_list):
        for event in event_list:
            if event.type_ == 'gc-invitation':
                self.withdraw('gc-invitation', event.account, event.room_jid)
            if event.type_ in ('normal', 'printed_chat', 'chat',
            'printed_pm', 'pm'):
                self.withdraw('new-message', event.account, event.jid)

    def _nec_our_status(self, obj):
        if app.account_is_connected(obj.conn.name):
            self.withdraw('connection-failed', obj.conn.name)

    def _get_icon_name(self, obj):
        if obj.notif_type == 'msg':
            if obj.base_event.mtype == 'pm':
                return 'gajim-priv_msg_recv'
            if obj.base_event.mtype == 'normal':
                return 'gajim-single_msg_recv'

        elif obj.notif_type == 'pres':
            if obj.transport_name is not None:
                return '%s-%s' % (obj.transport_name, obj.show)
            else:
                return gtkgui_helpers.get_iconset_name_for(obj.show)

    def popup(self, event_type, jid, account, type_='', icon_name=None,
              title=None, text=None, timeout=-1, room_jid=None):
        """
        Notify a user of an event using GNotification and GApplication under
        Linux, Use PopupNotificationWindow under Windows
        """

        if icon_name is None:
            icon_name = 'gajim-chat_msg_recv'

        if timeout < 0:
            timeout = app.config.get('notification_timeout')

        if sys.platform == 'win32':
            instance = PopupNotificationWindow(event_type, jid, account, type_,
                                               icon_name, title, text, timeout)
            app.interface.roster.popup_notification_windows.append(instance)
            return

        scale = gtkgui_helpers.get_monitor_scale_factor()
        icon_pixbuf = gtkgui_helpers.gtk_icon_theme.load_icon_for_scale(
            icon_name, 48, scale, 0)

        notification = Gio.Notification()
        if title is not None:
            notification.set_title(title)
        if text is not None:
            notification.set_body(text)
        notification.set_icon(icon_pixbuf)
        notif_id = None
        if event_type in (_('Contact Signed In'), _('Contact Signed Out'),
        _('New Message'), _('New Single Message'), _('New Private Message'),
        _('Contact Changed Status'), _('File Transfer Request'),
        _('File Transfer Error'), _('File Transfer Completed'),
        _('File Transfer Stopped'), _('Groupchat Invitation'),
        _('Connection Failed'), _('Subscription request'), _('Unsubscribed')):
            if 'actions' in self.daemon_capabilities:
                # Create Variant Dict
                dict_ = {'account': GLib.Variant('s', account),
                         'jid': GLib.Variant('s', jid),
                         'type_': GLib.Variant('s', type_)}
                variant_dict = GLib.Variant('a{sv}', dict_)
                action = 'app.{}-open-event'.format(account)
                #Button in notification
                notification.add_button_with_target(_('Open'), action,
                                                    variant_dict)
                notification.set_default_action_and_target(action,
                                                           variant_dict)

            # Only one notification per JID
            if event_type in (_('Contact Signed In'), _('Contact Signed Out'),
            _('Contact Changed Status')):
                notif_id = self._id('contact-status-changed', account, jid)
            elif event_type == _('Groupchat Invitation'):
                notif_id = self._id('gc-invitation', account, room_jid)
            elif event_type == _('Connection Failed'):
                notif_id = self._id('connection-failed', account)
            elif event_type in (_('New Message'), _('New Single Message'),
            _('New Private Message')):
                notif_id = self._id('new-message', account, jid)

        notification.set_priority(Gio.NotificationPriority.NORMAL)
        app.app.send_notification(notif_id, notification)

    def withdraw(self, *args):
        if sys.platform != 'win32':
            app.app.withdraw_notification(self._id(*args))

    def _id(self, *args):
        return ','.join(args)

class PopupNotificationWindow:
    def __init__(self, event_type, jid, account, msg_type='',
                 icon_name=None, title=None, text=None, timeout=-1):
        self.account = account
        self.jid = jid
        self.msg_type = msg_type
        self.index = len(app.interface.roster.popup_notification_windows)
        xml = gtkgui_helpers.get_gtk_builder('popup_notification_window.ui')
        self.window = xml.get_object('popup_notification_window')
        self.window.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)
        self.window.set_name('NotificationPopup')
        close_button = xml.get_object('close_button')
        event_type_label = xml.get_object('event_type_label')
        event_description_label = xml.get_object('event_description_label')
        eventbox = xml.get_object('eventbox')
        image = xml.get_object('notification_image')

        if not text:
            text = app.get_name_from_jid(account, jid)  # default value of text
        if not title:
            title = ''

        event_type_label.set_markup(
            '<span foreground="black" weight="bold">%s</span>' %
            GLib.markup_escape_text(title))

        css = '#NotificationPopup {background-color: black }'
        gtkgui_helpers.add_css_to_widget(self.window, css)

        if event_type == _('Contact Signed In'):
            bg_color = app.config.get('notif_signin_color')
        elif event_type == _('Contact Signed Out'):
            bg_color = app.config.get('notif_signout_color')
        elif event_type in (_('New Message'), _('New Single Message'),
            _('New Private Message'), _('New E-mail')):
            bg_color = app.config.get('notif_message_color')
        elif event_type == _('File Transfer Request'):
            bg_color = app.config.get('notif_ftrequest_color')
        elif event_type == _('File Transfer Error'):
            bg_color = app.config.get('notif_fterror_color')
        elif event_type in (_('File Transfer Completed'),
        _('File Transfer Stopped')):
            bg_color = app.config.get('notif_ftcomplete_color')
        elif event_type == _('Groupchat Invitation'):
            bg_color = app.config.get('notif_invite_color')
        elif event_type == _('Contact Changed Status'):
            bg_color = app.config.get('notif_status_color')
        else: # Unknown event! Shouldn't happen but deal with it
            bg_color = app.config.get('notif_other_color')

        background_class = '''
            .popup-style {
                border-image: none;
                background-image: none;
                background-color: %s }''' % bg_color

        gtkgui_helpers.add_css_to_widget(eventbox, background_class)
        eventbox.get_style_context().add_class('popup-style')

        gtkgui_helpers.add_css_to_widget(close_button, background_class)
        eventbox.get_style_context().add_class('popup-style')

        event_description_label.set_markup('<span foreground="black">%s</span>' %
            GLib.markup_escape_text(text))

        # set the image
        image.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)

        # position the window to bottom-right of screen
        window_width, self.window_height = self.window.get_size()
        app.interface.roster.popups_notification_height += self.window_height
        pos_x = app.config.get('notification_position_x')
        screen_w, screen_h = gtkgui_helpers.get_total_screen_geometry()
        if pos_x < 0:
            pos_x = screen_w - window_width + pos_x + 1
        pos_y = app.config.get('notification_position_y')
        if pos_y < 0:
            pos_y = screen_h - \
                app.interface.roster.popups_notification_height + pos_y + 1
        self.window.move(pos_x, pos_y)

        xml.connect_signals(self)
        self.window.show_all()
        if timeout > 0:
            GLib.timeout_add_seconds(timeout, self.on_timeout)

    def on_close_button_clicked(self, widget):
        self.adjust_height_and_move_popup_notification_windows()

    def on_timeout(self):
        self.adjust_height_and_move_popup_notification_windows()

    def adjust_height_and_move_popup_notification_windows(self):
        #remove
        app.interface.roster.popups_notification_height -= self.window_height
        self.window.destroy()

        if len(app.interface.roster.popup_notification_windows) > self.index:
            # we want to remove the destroyed window from the list
            app.interface.roster.popup_notification_windows.pop(self.index)

        # move the rest of popup windows
        app.interface.roster.popups_notification_height = 0
        current_index = 0
        for window_instance in app.interface.roster.popup_notification_windows:
            window_instance.index = current_index
            current_index += 1
            window_width, window_height = window_instance.window.get_size()
            app.interface.roster.popups_notification_height += window_height
            screen_w, screen_h = gtkgui_helpers.get_total_screen_geometry()
            window_instance.window.move(screen_w - window_width,
                screen_h - \
                app.interface.roster.popups_notification_height)

    def on_popup_notification_window_button_press_event(self, widget, event):
        if event.button != 1:
            self.window.destroy()
            return
        app.interface.handle_event(self.account, self.jid, self.msg_type)
        self.adjust_height_and_move_popup_notification_windows()
