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

import sys
import logging

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import StyleAttr
from gajim.common.i18n import _
from gajim.common.helpers import allow_showing_notification
from gajim.common.helpers import exec_command
from gajim.common.helpers import play_sound
from gajim.common.helpers import play_sound_file
from gajim.common.nec import EventHelper

from .util import add_css_to_widget
from .util import get_builder
from .util import get_monitor_scale_factor
from .util import get_total_screen_geometry

log = logging.getLogger('gajim.gui.notification')

NOTIFICATION_ICONS = {
    'incoming-message': 'gajim-chat_msg_recv',
    'group-chat-invitation': 'gajim-gc_invitation',
    'jingle-incoming': 'call-start-symbolic',
    'subscription_request': 'gajim-subscription_request',
    'unsubscribed': 'gajim-unsubscribed',
    'file-request-received': 'document-send',
    'file-send-error': 'dialog-error',
}


class Notification(EventHelper):
    """
    Handle notifications
    """
    def __init__(self):
        EventHelper.__init__(self)
        self._dbus_available = False
        self._daemon_capabilities = ['actions']
        self._win32_active_popup = None

        self._detect_dbus_caps()

        self.register_events([
            ('notification', ged.GUI2, self._on_notification),
            ('simple-notification', ged.GUI2, self._on_notification),
            ('our-show', ged.GUI2, self._on_our_show),
            ('connection-lost', ged.GUI2, self._on_connection_lost)
        ])

    def _detect_dbus_caps(self):
        if sys.platform in ('win32', 'darwin'):
            return

        if app.is_flatpak():
            self._dbus_available = True
            return

        def on_proxy_ready(_source, res, _data=None):
            try:
                proxy = Gio.DBusProxy.new_finish(res)
                self._daemon_capabilities = proxy.GetCapabilities()
            except GLib.Error as error:
                log.warning('Notifications D-Bus not available: %s', error)
            else:
                self._dbus_available = True
                log.info('Notifications D-Bus connected')

        log.info('Connecting to Notifications D-Bus')
        Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION,
                                  Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
                                  None,
                                  'org.freedesktop.Notifications',
                                  '/org/freedesktop/Notifications',
                                  'org.freedesktop.Notifications',
                                  None,
                                  on_proxy_ready)

    def _on_notification(self, event):
        if hasattr(event, 'command'):
            # Used by Triggers plugin
            try:
                exec_command(event.command, use_shell=True)
            except Exception:
                pass

        if hasattr(event, 'sound_file'):
            # Allow override here, used by Triggers plugin
            play_sound_file(event.sound_file)
        elif hasattr(event, 'sound'):
            play_sound(event.sound, event.account)

        if not allow_showing_notification(event.account):
            return

        if hasattr(event, 'notif_detail'):
            notif_detail = event.notif_detail
        else:
            notif_detail = event.notif_type

        if hasattr(event, 'icon_name'):
            icon_name = event.icon_name
        else:
            icon_name = NOTIFICATION_ICONS.get(
                event.notif_detail, 'mail-message-new')

        self._issue_notification(
            event.notif_type,
            event.account,
            str(event.jid),
            notif_detail=notif_detail,
            title=event.title,
            text=event.text,
            icon_name=icon_name)

    def _on_simple_notification(self, event):
        if not allow_showing_notification(event.account):
            return

        self._issue_notification(
            event.notif_type,
            event.account,
            None,
            title=event.title,
            text=event.text)

    def _on_our_show(self, event):
        if app.account_is_connected(event.account):
            self._withdraw('connection-failed', event.account)

    def _on_connection_lost(self, event):
        if not allow_showing_notification(event.conn.name):
            return

        self._issue_notification(
            'connection-lost',
            event.conn.name,
            None,
            title=event.title,
            text=event.msg,
            icon_name='gajim-connection_lost')

    def _issue_notification(self,
                            notif_type,
                            account,
                            jid,
                            notif_detail='',
                            title='',
                            text='',
                            icon_name=None,
                            timeout=-1):
        """
        Notify a user of an event using GNotification and GApplication under
        Linux, Use PopupNotificationWindow under Windows
        """

        if icon_name is None:
            icon_name = 'mail-message-new'

        if timeout < 0:
            timeout = app.settings.get('notification_timeout')

        if sys.platform == 'win32':
            self._withdraw()
            self._win32_active_popup = PopupNotification(
                notif_type,
                account,
                jid,
                notif_detail,
                title,
                text,
                icon_name,
                timeout)
            self._win32_active_popup.connect('destroy', self._on_popup_destroy)
            return

        if not self._dbus_available:
            return

        icon = Gio.ThemedIcon.new(icon_name)

        notification = Gio.Notification()
        if title is not None:
            notification.set_title(title)
        if text is not None:
            notification.set_body(text)
        notif_id = None
        if notif_type in (
                'incoming-message',
                'file-transfer',
                'group-chat-invitation',
                'subscription-request',
                'unsubscribed',
                'incoming-call',
                'connection-failed'):
            if 'actions' in self._daemon_capabilities:
                # Create Variant Dict
                dict_ = {'account': GLib.Variant('s', account),
                         'jid': GLib.Variant('s', jid),
                         'notif_detail': GLib.Variant('s', notif_detail)}
                variant_dict = GLib.Variant('a{sv}', dict_)

                # Add 'Open' action button to notification
                action = f'app.{account}-open-event'
                notification.add_button_with_target(
                    _('Open'), action, variant_dict)
                notification.set_default_action_and_target(
                    action, variant_dict)

                if notif_type == 'incoming-message':
                    # Add 'Mark as Read' action button to notification
                    action = f'app.{account}-mark-as-read'
                    notification.add_button_with_target(
                        _('Mark as Read'), action, variant_dict)

            # Only one notification per JID
            if notif_type == 'connection-failed':
                notif_id = self._make_id('connection-failed', account)
            elif notif_type == 'incoming-message':
                if app.desktop_env == 'gnome':
                    icon = self._get_avatar_for_notification(account, jid)
                notif_id = self._make_id('new-message', account, jid)

        notification.set_icon(icon)
        notification.set_priority(Gio.NotificationPriority.NORMAL)

        app.app.send_notification(notif_id, notification)

    @staticmethod
    def _get_avatar_for_notification(account, jid):
        scale = get_monitor_scale_factor()
        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        return app.interface.get_avatar(contact, 32, scale, pixbuf=True)

    def _on_popup_destroy(self, *args):
        self._win32_active_popup = None

    def _withdraw(self, *args):
        if sys.platform == 'win32':
            if self._win32_active_popup is not None:
                self._win32_active_popup.destroy()
        elif self._dbus_available:
            app.app.withdraw_notification(self._make_id(*args))

    @staticmethod
    def _make_id(*args):
        return ','.join(map(str, args))


class PopupNotification(Gtk.Window):
    def __init__(self,
                 notif_type,
                 account,
                 jid,
                 notif_detail,
                 title,
                 text,
                 icon_name,
                 timeout):
        Gtk.Window.__init__(self)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_focus_on_map(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_decorated(False)

        self._timeout_id = None
        self._account = account
        self._jid = jid
        self._notif_type = notif_type

        self._ui = get_builder('popup_notification_window.ui')
        self.add(self._ui.eventbox)

        if notif_detail == 'incoming-message':
            bg_color = app.css_config.get_value('.gajim-notify-message',
                                                StyleAttr.COLOR)
        elif notif_detail in ('file-error',
                              'file-send-error',
                              'file-request-error'):
            bg_color = app.css_config.get_value('.gajim-notify-error',
                                                StyleAttr.COLOR)
        elif notif_detail in ('file-completed', 'file-stopped'):
            bg_color = app.css_config.get_value('.gajim-notify-success',
                                                StyleAttr.COLOR)
        elif notif_detail == 'group-chat-invitation':
            bg_color = app.css_config.get_value('.gajim-notify-invite',
                                                StyleAttr.COLOR)
        else:
            bg_color = app.css_config.get_value('.gajim-notify-other',
                                                StyleAttr.COLOR)

        bar_class = '''
            .popup-bar {
                background-color: %s
            }''' % bg_color
        add_css_to_widget(self._ui.color_bar, bar_class)
        self._ui.color_bar.get_style_context().add_class('popup-bar')

        if title is None:
            title = ''
        self._ui.event_type_label.set_markup(title)

        if text is None:
            client = app.get_client(account)
            contact = client.get_module('Contacts').get_contact(jid)
            text = contact.name
        escaped_text = GLib.markup_escape_text(text)
        self._ui.event_description_label.set_markup(escaped_text)

        self._ui.image.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)

        self.move(*self._get_window_pos())

        self._ui.connect_signals(self)
        self.connect('button-press-event', self._on_button_press)
        self.connect('destroy', self._on_destroy)
        self.show_all()
        if timeout > 0:
            self._timeout_id = GLib.timeout_add_seconds(timeout, self.destroy)

    @staticmethod
    def _get_window_pos():
        pos_x = app.settings.get('notification_position_x')
        screen_w, screen_h = get_total_screen_geometry()
        if pos_x < 0:
            pos_x = screen_w - 312 + pos_x + 1
        pos_y = app.settings.get('notification_position_y')
        if pos_y < 0:
            pos_y = screen_h - 95 - 80 + pos_y + 1
        return pos_x, pos_y

    def _on_close_button_clicked(self, _widget):
        self.destroy()

    def _on_button_press(self, _widget, event):
        if event.button == 1:
            app.interface.handle_event(
                self._account, self._jid, self._notif_type)
        self.destroy()

    def _on_destroy(self, *args):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
