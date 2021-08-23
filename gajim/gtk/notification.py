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

from gajim import gtkgui_helpers
from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common.const import StyleAttr
from gajim.common.i18n import _
from gajim.common.nec import EventHelper

from .util import get_builder
from .util import get_icon_name
from .util import get_monitor_scale_factor
from .util import get_total_screen_geometry

log = logging.getLogger('gajim.gui.notification')


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
            ('notification', ged.GUI2, self._nec_notification),
            ('simple-notification', ged.GUI2, self._on_notification),
            ('our-show', ged.GUI2, self._nec_our_status),
        ])

        app.events.event_removed_subscribe(self._on_event_removed)

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

    def _nec_notification(self, event):
        if event.popup_enabled and app.settings.get('show_notifications'):
            icon_name = self._get_icon_name(event)
            self.popup(
                event.popup_event_type,
                str(event.jid),
                event.account,
                event.popup_msg_type,
                icon_name=icon_name,
                title=event.popup_title,
                text=event.popup_text)

        if event.command:
            # Used by Triggers plugin
            try:
                helpers.exec_command(event.command, use_shell=True)
            except Exception:
                pass

        if event.sound_file:
            # Allow override here, used by Triggers plugin
            helpers.play_sound_file(event.sound_file)
        elif event.sound_event:
            helpers.play_sound(event.sound_event, event.account)

    def _on_notification(self, event):
        self.popup(event.type_,
                   None,
                   event.account,
                   title=event.title,
                   text=event.text)

    def _on_event_removed(self, event_list):
        for event in event_list:
            if event.type_ == 'gc-invitation':
                self._withdraw('gc-invitation', event.account, event.muc)
            if event.type_ in ('normal', 'printed_chat', 'chat',
                               'printed_pm', 'pm', 'printed_marked_gc_msg',
                               'printed_gc_msg', 'jingle-incoming'):
                self._withdraw('new-message', event.account, event.jid)

    def _nec_our_status(self, event):
        if app.account_is_connected(event.account):
            self._withdraw('connection-failed', event.account)

    @staticmethod
    def _get_icon_name(event):
        if event.notif_type == 'msg':
            return 'gajim-chat_msg_recv'

        if event.notif_type == 'pres':
            if event.transport_name is not None:
                return '%s-%s' % (event.transport_name, event.show)
            return get_icon_name(event.show)
        return None

    def popup(self, event_type, jid, account, type_='', icon_name=None,
              title=None, text=None, timeout=-1, room_jid=None):
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
                event_type, jid, account, type_,
                icon_name, title, text, timeout)
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
        if event_type in (
                _('New Message'), _('New Private Message'),
                _('New Group Chat Message'),
                _('Contact Changed Status'), _('File Transfer Request'),
                _('File Transfer Error'), _('File Transfer Completed'),
                _('File Transfer Stopped'), _('Group Chat Invitation'),
                _('Connection Failed'), _('Subscription request'),
                _('Contact Unsubscribed'), _('Incoming Call')):
            if 'actions' in self._daemon_capabilities:
                # Create Variant Dict
                dict_ = {'account': GLib.Variant('s', account),
                         'jid': GLib.Variant('s', jid),
                         'type_': GLib.Variant('s', type_)}
                variant_dict = GLib.Variant('a{sv}', dict_)
                action = 'app.{}-open-event'.format(account)
                # Notification button
                notification.add_button_with_target(
                    _('Open'), action, variant_dict)
                notification.set_default_action_and_target(
                    action, variant_dict)
                if event_type in (
                        _('New Message'),
                        _('New Private Message'),
                        _('New Group Chat Message')):
                    action = 'app.{}-remove-event'.format(account)
                    notification.add_button_with_target(
                        _('Mark as Read'), action, variant_dict)

            # Only one notification per JID
            if event_type == _('Contact Changed Status'):
                notif_id = self._make_id('contact-status-changed', account, jid)
            elif event_type == _('Group Chat Invitation'):
                notif_id = self._make_id('gc-invitation', account, room_jid)
            elif event_type == _('Connection Failed'):
                notif_id = self._make_id('connection-failed', account)
            elif event_type in (_('New Message'),
                                _('New Private Message'),
                                _('New Group Chat Message')):
                if app.desktop_env == 'gnome':
                    icon = self._get_avatar_for_notification(account, jid)
                notif_id = self._make_id('new-message', account, jid)

        notification.set_icon(icon)
        notification.set_priority(Gio.NotificationPriority.NORMAL)

        app.app.send_notification(notif_id, notification)

    @staticmethod
    def _get_avatar_for_notification(account, jid):
        scale = get_monitor_scale_factor()
        contact = app.contacts.get_contact(account, jid)
        if contact is None:
            return None
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
    def __init__(self, event_type, jid, account, msg_type='',
                 icon_name=None, title=None, text=None, timeout=-1):
        Gtk.Window.__init__(self)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_focus_on_map(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_decorated(False)

        self._timeout_id = None
        self.account = account
        self.jid = jid
        self.msg_type = msg_type

        self._ui = get_builder('popup_notification_window.ui')
        self.add(self._ui.eventbox)

        if event_type in (_('New Message'),
                          _('New Private Message'),
                          _('New E-mail')):
            bg_color = app.css_config.get_value('.gajim-notify-message',
                                                StyleAttr.COLOR)
        elif event_type == _('File Transfer Request'):
            bg_color = app.css_config.get_value('.gajim-notify-ft-request',
                                                StyleAttr.COLOR)
        elif event_type == _('File Transfer Error'):
            bg_color = app.css_config.get_value('.gajim-notify-ft-error',
                                                StyleAttr.COLOR)
        elif event_type in (_('File Transfer Completed'),
                            _('File Transfer Stopped')):
            bg_color = app.css_config.get_value('.gajim-notify-ft-complete',
                                                StyleAttr.COLOR)
        elif event_type == _('Group Chat Invitation'):
            bg_color = app.css_config.get_value('.gajim-notify-invite',
                                                StyleAttr.COLOR)
        elif event_type == _('Contact Changed Status'):
            bg_color = app.css_config.get_value('.gajim-notify-status',
                                                StyleAttr.COLOR)
        else:  # Unknown event (shouldn't happen, but deal with it)
            bg_color = app.css_config.get_value('.gajim-notify-other',
                                                StyleAttr.COLOR)

        bar_class = '''
            .popup-bar {
                background-color: %s
            }''' % bg_color
        gtkgui_helpers.add_css_to_widget(self._ui.color_bar, bar_class)
        self._ui.color_bar.get_style_context().add_class('popup-bar')

        if not title:
            title = ''
        self._ui.event_type_label.set_markup(title)

        if not text:
            text = app.get_name_from_jid(account, jid)  # default value of text
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
            app.interface.handle_event(self.account, self.jid, self.msg_type)
        self.destroy()

    def _on_destroy(self, *args):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
