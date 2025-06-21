# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any

from unittest.mock import MagicMock

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import Iq
from nbxmpp import JID
from nbxmpp.const import InviteType
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import DiscoInfo

from gajim.common import app
from gajim.common import events
from gajim.common.const import AvatarSize
from gajim.common.const import CSSPriority
from gajim.common.helpers import Observable
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ContactSettings
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupChatSettings

from gajim.gtk.activity_list import ActivityListView
from gajim.gtk.activity_page import ActivityPage
from gajim.gtk.activity_side_bar import ActivitySideBar
from gajim.gtk.avatar import AvatarStorage
from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.chat_page import ChatPage
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT = "testacc1"
FROM_JID = JID.from_string("contact@example.org")
FROM_JID_2 = JID.from_string("contact2@example.org")
MUC_JID = JID.from_string("test@conference.example.org")
MUC_JID_2 = JID.from_string("test2@conference.example.org")


class TestActivityFeed(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=1000,
            default_height=800,
            add_window_padding=False,
        )

        app.app = MagicMock()
        app.app.avatar_storage.get_gajim_circle_icon.side_effect = (
            self._get_gajim_circle_icon
        )

        chat_page = ChatPage()

        # activity_list.connect("activate", self._on_activity_row_activate)
        # activity_list.connect("unselected", self._on_activity_item_unselected)

        # Replace ChatPage's internal activity list with test object
        # to track unread count in sidebar
        # chat_page._activity_list = activity_list

        self._activity_page = ActivityPage()

        self._activity_sidebar = ActivitySideBar()
        self._activity_sidebar.set_chat_page(chat_page)
        self._activity_sidebar.set_valign(Gtk.Align.START)

        update_button = Gtk.Button.new_with_label("Updates")
        update_button.connect("clicked", self._on_update_button_clicked)

        subscription_button = Gtk.Button.new_with_label("Subscription")
        subscription_button.connect("clicked", self._on_subscription_button_clicked)

        invitation_button = Gtk.Button.new_with_label("Invitation")
        invitation_button.connect("clicked", self._on_invitation_button_clicked)

        button_box = Gtk.Box(
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.END,
            hexpand=True,
            margin_bottom=12,
        )
        button_box.add_css_class("toolbar")
        button_box.add_css_class("osd")
        button_box.append(update_button)
        button_box.append(subscription_button)
        button_box.append(invitation_button)

        overlay = Gtk.Overlay(hexpand=True)
        overlay.set_child(chat_page)
        overlay.add_overlay(button_box)
        self.set_child(overlay)

    def _cleanup(self) -> None:
        pass

    def _get_gajim_circle_icon(self, size: int, scale: int) -> Gdk.Texture | None:
        return AvatarStorage.get_gajim_circle_icon(size, scale)

    def show_activity_page(self) -> None:
        self._activity_sidebar.select()
        self._activity_page.show_default_page()

    def _on_activity_row_activate(
        self, listview: ActivityListView, position: int
    ) -> None:
        item = listview.get_listitem(position)
        self._activity_page.process_row_activated(item)

    def _on_activity_item_unselected(self, listview: ActivityListView) -> None:
        self._activity_page.show_default_page()

    def _on_activity_row_removed(self, _listview: ActivityListView) -> None:
        self._activity_page.show_default_page()

    def _on_update_button_clicked(self, _button: Gtk.Button) -> None:
        app.plugin_repository.trigger_plugin_update()  # type: ignore
        app.ged.raise_event(events.AllowGajimUpdateCheck())
        app.ged.raise_event(
            events.GajimUpdateAvailable("2.0.0", "https://gajim.org/download")
        )

        # Trigger plugin update successful event with delay, because it removes
        # available update message
        GLib.timeout_add_seconds(
            10, app.plugin_repository.trigger_plugin_update_successful  # type: ignore
        )

    def _on_subscription_button_clicked(self, _button: Gtk.Button) -> None:
        event = events.SubscribePresenceReceived(
            conn=app.get_client(ACCOUNT),
            account=ACCOUNT,
            jid=str(FROM_JID),
            fjid=f"{FROM_JID}/test",
            status="",
            user_nick="User Nick",
            is_transport=False,
        )
        app.ged.raise_event(event)

        event = events.UnsubscribedPresenceReceived(
            conn=app.get_client(ACCOUNT),
            account=ACCOUNT,
            jid=str(FROM_JID_2),
        )
        app.ged.raise_event(event)

    def _on_invitation_button_clicked(self, _button: Gtk.Button) -> None:
        muc_info = DiscoInfo(
            Iq(frm=JID.from_string("test@example.org")), [], [], [], None
        )
        event = events.MucInvitation(
            ACCOUNT,
            info=muc_info,
            muc=MUC_JID,
            from_=FROM_JID,
            reason=None,
            password=None,
            type=InviteType.DIRECT,
            continued=False,
            thread=None,
        )
        app.ged.raise_event(event)

        event = events.MucDecline(
            ACCOUNT,
            muc=MUC_JID_2,
            from_=FROM_JID_2,
            reason=None,
        )
        app.ged.raise_event(event)


class TestPluginRepository(Observable):
    def __init__(self):
        super().__init__()

    def trigger_plugin_update(self) -> None:
        self.notify("plugin-updates-available", [])

    def trigger_plugin_update_successful(self) -> None:
        self.notify("auto-update-finished")


class TestModule(MagicMock):
    def __init__(self) -> None:
        super().__init__()

    def get_contact(self, jid: JID, groupchat: bool = False) -> MagicMock:
        if jid == MUC_JID:
            return self._get_contact(jid, groupchat=True)

        return self._get_contact(jid, groupchat=groupchat)

    def _get_contact(self, jid: JID, groupchat: bool = False) -> MagicMock:
        if groupchat:
            contact = MagicMock(spec=GroupchatContact)
            contact.settings = GroupChatSettings(ACCOUNT, jid)
        else:
            contact = MagicMock(spec=BareContact)
            contact.settings = ContactSettings(ACCOUNT, jid)

        contact.is_groupchat = groupchat

        contact.connect = MagicMock()
        contact.account = ACCOUNT
        contact.jid = jid
        contact.name = "Test Contact"
        avatar = convert_surface_to_texture(
            generate_default_avatar("T", (0.2, 0.1, 0.7), AvatarSize.ACTIVITY_PAGE, 1)
        )
        contact.get_avatar = MagicMock(return_value=avatar)
        return contact

    def get_name_from_bookmark(self, jid: JID) -> str:
        return "Group Chat Name"

    def get_bookmark(self, room_jid: JID) -> BookmarkData:
        return BookmarkData(MUC_JID, "Group Chat Name", "Nick")

    def decline(self, *args: Any) -> None:
        pass


class TestClient(MagicMock):
    def __init__(self):
        super().__init__()

    def get_module(self) -> TestModule:
        return TestModule()


app.plugin_repository = TestPluginRepository()

util.init_settings()
app.settings.add_account("testacc1")
app.settings.set_account_setting("testacc1", "active", True)
app.settings.add_account("testacc2")
app.settings.set_account_setting("testacc2", "active", True)

app.window = MagicMock()
app.commands = MagicMock()
app.plugin_manager = MagicMock()

app.get_client = MagicMock(return_value=TestClient)

css = ".gajim_class_1 { background-color: purple; }"
provider = Gtk.CssProvider()
provider.load_from_bytes(GLib.Bytes.new(css.encode()))

display = Gdk.Display.get_default()
assert display is not None
Gtk.StyleContext.add_provider_for_display(display, provider, CSSPriority.APPLICATION)

app.css_config = MagicMock()
app.css_config.get_dynamic_class = MagicMock(return_value="gajim_class_1")

window = TestActivityFeed()
window.show()

app.window.show_activity_page = window.show_activity_page

util.run_app()
