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
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

import hashlib
import logging
import platform
import sys
from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import configpaths
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.helpers import allow_showing_notification
from gajim.common.helpers import play_sound
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import ResourceContact

from gajim.gtk.avatar import convert_surface_to_texture
from gajim.gtk.avatar import merge_avatars
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.structs import OpenEventActionParams
from gajim.gtk.util import load_icon_surface

MIN_WINDOWS_TOASTS_WIN_VERSION = 10240

if (
    sys.platform == "win32"
    and int(platform.version().split(".")[2]) >= MIN_WINDOWS_TOASTS_WIN_VERSION
) or TYPE_CHECKING:
    # Importing windows_toasts on an unsupported OS will throw an Exception
    from windows_toasts import InteractableWindowsToaster
    from windows_toasts import Toast
    from windows_toasts import ToastActivatedEventArgs
    from windows_toasts import ToastButton
    from windows_toasts import ToastDisplayImage
    from windows_toasts import ToastImage
    from windows_toasts import ToastImagePosition

log = logging.getLogger("gajim.gtk.notification")

NOTIFICATION_ICONS: dict[str, str] = {
    "incoming-message": "gajim-chat-msg-recv",
    "group-chat-invitation": "gajim-group-chat-invitation",
    "incoming-call": "call-start-symbolic",
    "subscription_request": "gajim-subscription-request",
    "unsubscribed": "gajim-unsubscribed",
    "file-request-received": "document-send",
    "file-send-error": "dialog-error",
}


_notification_backend = None


class NotificationBackend(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)

        self.register_events(
            [
                ("notification", ged.GUI2, self._on_notification),
                ("account-enabled", ged.GUI2, self._on_account_enabled),
                ("chat-read", ged.GUI2, self._on_chat_read),
            ]
        )

        for client in app.get_clients():
            client.connect_signal("state-changed", self._on_client_state_changed)

    def _on_notification(self, event: events.Notification) -> None:
        if event.account and event.jid:
            client = app.get_client(event.account)
            contact = client.get_module("Contacts").get_contact(event.jid)

            if contact.is_muted:
                log.debug("Notifications muted for %s", contact)
                return

        if event.sound is not None:
            play_sound(event.sound, event.account)

        if not allow_showing_notification(event.account):
            return

        self._send(event)

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        client = app.get_client(event.account)
        client.connect_signal("state-changed", self._on_client_state_changed)

    def _on_chat_read(self, event: events.ChatRead) -> None:
        self._withdraw(["new-message", event.account, event.jid])

    def _on_client_state_changed(
        self, client: Client, _signal_name: str, state: SimpleClientState
    ) -> None:

        if not state.is_connected:
            return
        self._withdraw(["connection-failed", client.account])
        self._withdraw(["server-shutdown", client.account])

    def _send(self, event: events.Notification) -> None:
        raise NotImplementedError

    def _withdraw(self, details: list[Any]) -> None:
        raise NotImplementedError


class DummyBackend(NotificationBackend):

    def _send(self, event: events.Notification) -> None:
        pass

    def _withdraw(self, details: list[Any]) -> None:
        pass


class WindowsToastNotification(NotificationBackend):
    def __init__(self):
        NotificationBackend.__init__(self)

        if app.is_ms_store():
            from winrt.windows.applicationmodel import AppInfo

            assert AppInfo.current is not None
            aumid = AppInfo.current.app_user_model_id
        else:
            # Non MS Store version has to register an AUMID manually
            aumid = "Gajim.ToastNotification"
            self._register_notifier_aumid(aumid)

        self._toaster = InteractableWindowsToaster(
            applicationText="Gajim", notifierAUMID=aumid
        )

    def _register_notifier_aumid(self, aumid: str) -> None:
        """Register an AUMID for Gajim's toast notifications.
        This allows notifications issued by Gajim to have the right icon and title.
        Code taken from: https://github.com/DatGuy1/Windows-Toasts/blob/main/scripts/register_hkey_aumid.py
        """
        key_path = f"SOFTWARE\\Classes\\AppUserModelId\\{aumid}"

        image_path = (
            Path(sys.executable).parent.parent
            / "share"
            / "icons"
            / "hicolor"
            / "96x96"
            / "apps"
            / "gajim.png"
        )

        import winreg

        winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as master_key:
            winreg.SetValueEx(master_key, "DisplayName", 0, winreg.REG_SZ, "Gajim")
            winreg.SetValueEx(
                master_key, "IconUri", 0, winreg.REG_SZ, str(image_path.resolve())
            )

    def _send(self, event: events.Notification) -> None:
        toast = Toast()
        toast.text_fields = [event.title, event.text]

        toast_image = self._get_toast_image(event)
        toast_display_image = ToastDisplayImage(
            image=toast_image,
            position=ToastImagePosition.AppLogo,
        )
        toast.AddImage(toast_display_image)

        for button in self._get_toast_buttons(event):
            toast.AddAction(button)

        toast.on_activated = self._on_activated

        self._toaster.show_toast(toast)

    def _withdraw(self, details: list[Any]) -> None:
        self._toaster.clear_toasts()

    def _on_activated(self, event: ToastActivatedEventArgs) -> None:
        # Calls need to be executed with GLib.idle_add to avoid threading issues,
        # because Toasts run in a different thread.
        if event.arguments is None:
            GLib.idle_add(app.window.present)
            return

        if event.arguments.startswith("open-event-"):
            serialized_data = event.arguments.split("open-event-")[1]
            params = OpenEventActionParams.from_serialized_string(
                serialized_data, GLib.VariantType("a{sv}")
            )
            if params is not None:
                GLib.idle_add(
                    app.app.activate_action,
                    f"{params.account}-open-event",
                    params.to_variant(),
                )
                return

        elif event.arguments.startswith("mark-as-read-"):
            serialized_data = event.arguments.split("mark-as-read-")[1]
            params = AccountJidParam.from_serialized_string(
                serialized_data, GLib.VariantType("a{sv}")
            )
            if params is not None:
                GLib.idle_add(
                    app.app.activate_action,
                    f"{params.account}-mark-as-read",
                    params.to_variant(),
                )
                return

        GLib.idle_add(app.window.present)

    def _get_toast_image(self, event: events.Notification) -> ToastImage:
        if event.type == "incoming-message":
            assert event.jid is not None
            texture = _get_texture_for_notification(
                event.account, event.jid, event.resource
            )
            return ToastImage(_get_path_for_texture(texture))

        if event.icon_name is not None:
            surface = load_icon_surface(event.icon_name, 32)
            assert surface is not None
            texture = convert_surface_to_texture(surface)
            return ToastImage(_get_path_for_texture(texture))

        icon_name = event.sub_type or event.type
        icon_name = NOTIFICATION_ICONS.get(icon_name, "mail-unread")
        surface = load_icon_surface(icon_name, 32)
        assert surface is not None
        texture = convert_surface_to_texture(surface)
        return ToastImage(_get_path_for_texture(texture))

    def _get_toast_buttons(self, event: events.Notification) -> list[ToastButton]:
        toast_buttons: list[ToastButton] = []

        jid = "" if event.jid is None else str(event.jid)

        params = OpenEventActionParams(
            type=event.type,
            sub_type=event.sub_type or "",
            account=event.account,
            jid=jid,
        )

        button = ToastButton(
            content=_("Open"), arguments=f"open-event-{params.serialize()}"
        )
        toast_buttons.append(button)

        if event.type == "incoming-message":
            assert isinstance(event.jid, JID)
            params = AccountJidParam(account=event.account, jid=event.jid)

            button = ToastButton(
                content=_("Mark as Read"),
                arguments=f"mark-as-read-{params.serialize()}",
            )
            toast_buttons.append(button)

        return toast_buttons


class Linux(NotificationBackend):

    _action_types = [
        "connection-failed",
        "server-shutdown",
        "group-chat-invitation",
        "incoming-call",
        "incoming-message",
        "subscription-request",
        "unsubscribed",
    ]

    def __init__(self):
        NotificationBackend.__init__(self)
        self._notifications_supported: bool = False
        self._caps: list[str] = []
        self._detect_dbus_caps()
        log.info("Detected notification capabilities: %s", self._caps)

    def _detect_dbus_caps(self) -> None:
        if app.is_flatpak() or app.desktop_env == "gnome":
            # Gnome Desktop does not use org.freedesktop.Notifications.
            # It has its own API at org.gtk.Notifications, which is not an
            # implementation of the freedesktop spec. There is no documentation
            # on what it currently supports, we can assume at least what the
            # GLib.Notification API offers (icons, actions).
            #
            # If the app is run as flatpak the portal API is used
            # https://flatpak.github.io/xdg-desktop-portal/docs
            self._caps = ["actions"]
            self._notifications_supported = True
            return

        def on_proxy_ready(_source: Gio.DBusProxy, res: Gio.AsyncResult) -> None:
            try:
                proxy = Gio.DBusProxy.new_finish(res)
                self._caps = proxy.GetCapabilities()  # pyright: ignore
            except GLib.Error as error:
                log.warning("Notifications D-Bus not available: %s", error)
            else:
                self._notifications_supported = True
                log.info("Notifications D-Bus connected")

        log.info("Connecting to Notifications D-Bus")
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
            None,
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            None,
            on_proxy_ready,
        )

    def _send(self, event: events.Notification) -> None:
        if not self._notifications_supported:
            return

        notification = Gio.Notification()
        notification.set_title(event.title)

        text = event.text
        if "body-markup" in self._caps:
            text = GLib.markup_escape_text(event.text)

        notification.set_body(text)
        notification.set_priority(Gio.NotificationPriority.NORMAL)

        icon = self._make_icon(event)
        notification.set_icon(icon)

        self._add_actions(event, notification)
        notification_id = self._make_notification_id(event)

        log.info("Sending notification: %s", notification_id)
        app.app.send_notification(notification_id, notification)

    def _add_actions(
        self, event: events.Notification, notification: Gio.Notification
    ) -> None:

        if event.type not in self._action_types:
            return

        if "actions" not in self._caps:
            return

        jid = ""
        if event.jid is not None:
            jid = str(event.jid)

        params = OpenEventActionParams(
            type=event.type,
            sub_type=event.sub_type or "",
            account=event.account,
            jid=jid,
        )

        action = f"app.{event.account}-open-event"
        notification.add_button_with_target(_("Open"), action, params.to_variant())
        notification.set_default_action_and_target(action, params.to_variant())

        if event.type == "incoming-message":
            action = f"app.{event.account}-mark-as-read"
            params = AccountJidParam(account=event.account, jid=JID.from_string(jid))
            notification.add_button_with_target(
                _("Mark as Read"), action, params.to_variant()
            )

    def _make_notification_id(self, event: events.Notification) -> str | None:
        if event.type in ("connection-failed", "server-shutdown"):
            return self._make_id([event.type, event.account])

        if event.type == "incoming-message":
            return self._make_id(["new-message", event.account, str(event.jid)])

        return None

    def _make_icon(self, event: events.Notification) -> Gio.Icon:
        if event.type == "incoming-message":
            assert event.jid is not None

            if app.is_flatpak():
                return _get_bytes_icon(event.account, event.jid, event.resource)

            return _get_file_icon(event.account, event.jid, event.resource)

        if event.icon_name is not None:
            return Gio.ThemedIcon.new(event.icon_name)

        icon_name = event.sub_type or event.type
        icon_name = NOTIFICATION_ICONS.get(icon_name, "mail-unread")
        return Gio.ThemedIcon.new(icon_name)

    def _withdraw(self, details: list[Any]) -> None:
        if not self._notifications_supported:
            return
        notification_id = self._make_id(details)

        log.info("Withdraw notification: %s", notification_id)
        app.app.withdraw_notification(notification_id)

    @staticmethod
    def _make_id(details: list[Any]) -> str:
        return ",".join(map(str, details))


def _get_participant_texture(
    gc_contact: GroupchatContact, resource: str
) -> Gdk.Texture:
    size = AvatarSize.NOTIFICATION
    muc_avatar = gc_contact.get_avatar(size, 1)
    participant_avatar = gc_contact.get_resource(resource).get_avatar(
        size, 1, add_show=False
    )

    return merge_avatars(muc_avatar, participant_avatar)


def _get_texture_for_notification(
    account: str, jid: JID | str, resource: str | None
) -> Gdk.Texture:
    size = AvatarSize.NOTIFICATION
    client = app.get_client(account)
    contact = client.get_module("Contacts").get_contact(jid)
    if isinstance(contact, GroupchatContact):
        if resource:
            return _get_participant_texture(contact, resource)
        else:
            return contact.get_avatar(size, 1)

    assert not isinstance(contact, ResourceContact)
    return contact.get_avatar(size, 1, add_show=False)


def _get_bytes_icon(
    account: str, jid: JID | str, resource: str | None
) -> Gio.BytesIcon:
    texture = _get_texture_for_notification(account, jid, resource)
    png_bytes = texture.save_to_png_bytes()
    return Gio.BytesIcon(bytes=png_bytes)


def _get_file_icon(account: str, jid: JID | str, resource: str | None) -> Gio.FileIcon:
    texture = _get_texture_for_notification(account, jid, resource)
    path = _get_path_for_texture(texture)
    return Gio.FileIcon(file=Gio.File.new_for_path(str(path)))


def _get_path_for_texture(texture: Gdk.Texture) -> Path:
    png_bytes = texture.save_to_png_bytes()
    png_bytes_data = png_bytes.get_data()
    assert png_bytes_data is not None
    path = configpaths.get("AVATAR_ICONS") / hashlib.sha1(png_bytes_data).hexdigest()
    if not path.exists():
        texture.save_to_png(str(path))
    return path


def get_notification_backend() -> NotificationBackend:
    if sys.platform == "win32":
        if int(platform.version().split(".")[2]) >= MIN_WINDOWS_TOASTS_WIN_VERSION:
            return WindowsToastNotification()
        return DummyBackend()

    if sys.platform == "darwin":
        return DummyBackend()
    return Linux()


def init() -> None:
    global _notification_backend  # pylint: disable=global-statement
    _notification_backend = get_notification_backend()
