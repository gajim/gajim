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

from __future__ import annotations

from typing import Any
from typing import Optional
from typing import Union

import sys
import logging

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import ged
from gajim.common import events
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.const import StyleAttr
from gajim.common.i18n import _
from gajim.common.helpers import allow_showing_notification
from gajim.common.helpers import play_sound
from gajim.common.ged import EventHelper

from .builder import get_builder
from .util import add_css_to_widget
from .util import get_monitor_scale_factor
from .util import get_total_screen_geometry
from .structs import OpenEventActionParams

log = logging.getLogger('gajim.gui.notification')


NOTIFICATION_ICONS: dict[str, str] = {
    'incoming-message': 'gajim-chat_msg_recv',
    'group-chat-invitation': 'gajim-gc_invitation',
    'incoming-call': 'call-start-symbolic',
    'subscription_request': 'gajim-subscription_request',
    'unsubscribed': 'gajim-unsubscribed',
    'file-request-received': 'document-send',
    'file-send-error': 'dialog-error',
}


_notification_backend = None


class NotificationBackend(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)

        self.register_events([
            ('notification', ged.GUI2, self._on_notification),
            ('account-enabled', ged.GUI2, self._on_account_enabled)
        ])

        for client in app.get_clients():
            client.connect_signal('state-changed',
                                  self._on_client_state_changed)

    def _on_notification(self, event: events.Notification) -> None:
        if event.sound is not None:
            play_sound(event.sound, event.account)

        if not allow_showing_notification(event.account):
            return

        self._send(event)

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        client = app.get_client(event.account)
        client.connect_signal('state-changed', self._on_client_state_changed)

    def _on_client_state_changed(self,
                                 client: Client,
                                 _signal_name: str,
                                 state: SimpleClientState) -> None:

        if not state.is_connected:
            return
        self._withdraw(['connection-failed', client.account])
        self._withdraw(['server-shutdown', client.account])

    def _send(self, event: events.Notification) -> None:
        raise NotImplementedError

    def _withdraw(self, details: list[Any]) -> None:
        raise NotImplementedError


class DummyBackend(NotificationBackend):

    def _send(self, event: events.Notification) -> None:
        pass

    def _withdraw(self, details: list[Any]) -> None:
        pass


class Windows(NotificationBackend):
    def __init__(self):
        NotificationBackend.__init__(self)
        self._active_notification = None

    def _send(self, event: events.Notification) -> None:
        timeout = app.settings.get('notification_timeout')
        self._withdraw()
        self._active_notification = PopupNotification(event, timeout)

        def _on_popup_destroy(_widget: Gtk.Window) -> None:
            self._active_notification = None

        self._active_notification.connect('destroy', _on_popup_destroy)

    def _withdraw(self, *args: Any) -> None:
        if self._active_notification is not None:
            self._active_notification.destroy()


class PopupNotification(Gtk.Window):

    _background_class = {
        'incoming-message': '.gajim-notify-message',
        'file-error': '.gajim-notify-error',
        'file-send-error': '.gajim-notify-error',
        'file-request-error': '.gajim-notify-error',
        'file-completed': '.gajim-notify-success',
        'file-stopped': '.gajim-notify-success',
        'group-chat-invitation': '.gajim-notify-invite',
    }

    def __init__(self, event: events.Notification, timeout: int) -> None:
        Gtk.Window.__init__(self)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_focus_on_map(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_decorated(False)
        self.set_keep_above(True)

        self._timeout_id: Optional[int] = None
        self._event = event

        self._ui = get_builder('popup_notification_window.ui')
        self.add(self._ui.eventbox)

        self._add_background_color(event)
        icon_name = self._get_icon_name(event)
        self._ui.image.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        self._ui.event_type_label.set_text(event.title)
        self._ui.event_description_label.set_text(event.text)

        if timeout > 0:
            self._timeout_id = GLib.timeout_add_seconds(timeout, self.destroy)

        self.move(*self._get_window_pos())

        self._ui.connect_signals(self)
        self.connect('button-press-event', self._on_button_press)
        self.connect('destroy', self._on_destroy)
        self.show_all()

    def _get_icon_name(self, event: events.Notification) -> str:
        if event.icon_name is not None:
            return event.icon_name
        icon_name = event.sub_type or event.type
        return NOTIFICATION_ICONS.get(icon_name, 'mail-unread')

    def _add_background_color(self, event: events.Notification) -> None:
        event_type = event.sub_type or event.type
        css_class = self._background_class.get(event_type,
                                               '.gajim-notify-other')
        bg_color = app.css_config.get_value(css_class, StyleAttr.COLOR)
        bar_class = '''
            .popup-bar {
                background-color: %s
            }''' % bg_color
        add_css_to_widget(self._ui.color_bar, bar_class)
        self._ui.color_bar.get_style_context().add_class('popup-bar')

    @staticmethod
    def _get_window_pos() -> tuple[int, int]:
        pos_x = app.settings.get('notification_position_x')
        screen_w, screen_h = get_total_screen_geometry()
        if pos_x < 0:
            pos_x = screen_w - 312 + pos_x + 1
        pos_y = app.settings.get('notification_position_y')
        if pos_y < 0:
            pos_y = screen_h - 95 - 80 + pos_y + 1
        return pos_x, pos_y

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.destroy()

    def _on_button_press(self,
                         _widget: Gtk.Widget,
                         event: Gdk.EventButton
                         ) -> None:
        if event.button == 1:

            jid = ''
            if self._event.jid is not None:
                jid = str(self._event.jid)

            params = OpenEventActionParams(type=self._event.type,
                                           sub_type=self._event.sub_type or '',
                                           account=self._event.account,
                                           jid=jid)
            # present_with_time needs to be called at this instant in order to
            # work on Windows
            app.window.present_with_time(event.time)
            app.app.activate_action(f'app.{self._event.account}-open-event',
                                    params.to_variant())

        self.destroy()

    def _on_destroy(self, _widget: Gtk.Window) -> None:
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)


class Linux(NotificationBackend):

    _action_types = [
        'connection-failed',
        'server-shutdown',
        'file-transfer',
        'group-chat-invitation',
        'incoming-call',
        'incoming-message',
        'subscription-request',
        'unsubscribed',
    ]

    def __init__(self):
        NotificationBackend.__init__(self)
        self._dbus_available: bool = False
        self._caps: list[str] = []
        self._detect_dbus_caps()
        log.info('Detected notification capabilities: %s', self._caps)

    def _detect_dbus_caps(self) -> None:
        if app.is_flatpak() or app.desktop_env == 'gnome':
            # Gnome Desktop does not use org.freedesktop.Notifications.
            # It has its own API at org.gtk.Notifications, which is not an
            # implementation of the freedesktop spec. There is no documentation
            # on what it currently supports, we can assume at least what the
            # GLib.Notification API offers (icons, actions).
            self._caps = ['actions']
            self._dbus_available = True
            return

        def on_proxy_ready(_source: Gio.DBusProxy,
                           res: Gio.AsyncResult) -> None:
            try:
                proxy = Gio.DBusProxy.new_finish(res)
                self._caps = proxy.GetCapabilities()  # type: ignore
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

    def _send(self, event: events.Notification) -> None:
        if not self._dbus_available:
            return

        notification = Gio.Notification()
        if event.title is not None:
            notification.set_title(event.title)

        text = event.text
        if 'body-markup' in self._caps:
            text = GLib.markup_escape_text(event.text)

        notification.set_body(text)
        notification.set_priority(Gio.NotificationPriority.NORMAL)

        icon = self._make_icon(event)
        notification.set_icon(icon)

        self._add_actions(event, notification)
        notification_id = self._make_notification_id(event)

        log.info('Sending notification: %s', notification_id)
        app.app.send_notification(notification_id, notification)

    def _add_actions(self,
                     event: events.Notification,
                     notification: Gio.Notification) -> None:

        if event.type not in self._action_types:
            return

        if 'actions' not in self._caps:
            return

        jid = ''
        if event.jid is not None:
            jid = str(event.jid)

        params = OpenEventActionParams(type=event.type,
                                       sub_type=event.sub_type or '',
                                       account=event.account,
                                       jid=jid)

        action = f'app.{event.account}-open-event'
        notification.add_button_with_target(
            _('Open'), action, params.to_variant())
        notification.set_default_action_and_target(
            action, params.to_variant())

        if event.type == 'incoming-message':
            action = f'app.{event.account}-mark-as-read'
            notification.add_button_with_target(
                _('Mark as Read'), action, params.to_variant())

    def _make_notification_id(self,
                              event: events.Notification) -> Optional[str]:
        if event.type in ('connection-failed', 'server-shutdown'):
            return self._make_id([event.type, event.account])

        if event.type == 'incoming-message':
            return self._make_id(['new-message', event.account, str(event.jid)])

        return None

    @staticmethod
    def _get_avatar_for_notification(account: str,
                                     jid: Union[JID, str]) -> GdkPixbuf.Pixbuf:
        scale = get_monitor_scale_factor()
        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        return contact.get_avatar(AvatarSize.NOTIFICATION,
                                  scale,
                                  pixbuf=True)

    def _make_icon(self, event: events.Notification) -> Gio.Icon:
        if (event.type == 'incoming-message' and app.desktop_env == 'gnome'):
            assert event.jid is not None
            return self._get_avatar_for_notification(event.account, event.jid)

        if event.icon_name is not None:
            return Gio.ThemedIcon.new(event.icon_name)

        icon_name = event.sub_type or event.type
        icon_name = NOTIFICATION_ICONS.get(icon_name, 'mail-unread')
        return Gio.ThemedIcon.new(icon_name)

    def _withdraw(self, details: list[Any]) -> None:
        if not self._dbus_available:
            return
        notification_id = self._make_id(details)

        log.info('Withdraw notification: %s', notification_id)
        app.app.withdraw_notification(notification_id)

    @staticmethod
    def _make_id(details: list[Any]) -> str:
        return ','.join(map(str, details))


def get_notification_backend() -> NotificationBackend:
    if sys.platform == 'win32':
        return Windows()

    if sys.platform == 'darwin':
        return DummyBackend()
    return Linux()


def init() -> None:
    global _notification_backend  # pylint: disable=global-statement
    _notification_backend = get_notification_backend()
