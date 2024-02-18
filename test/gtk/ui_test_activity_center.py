# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any

from unittest.mock import MagicMock

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import InviteType
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import DiscoInfo

from gajim.common import app
from gajim.common import events
from gajim.common.const import AvatarSize
from gajim.common.helpers import Observable
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ContactSettings
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupChatSettings

from gajim.gtk.activity_list import ActivityList
from gajim.gtk.activity_list import ActivityListRow
from gajim.gtk.activity_page import ActivityPage
from gajim.gtk.activity_side_bar import ActivitySideBar
from gajim.gtk.avatar import AvatarStorage
from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT = "testacc1"
FROM_JID = JID.from_string("contact@test.tld")
MUC_JID = JID.from_string("test@conference.example.org")


class TestActivityCenter(GajimAppWindow):
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
        app.app.avatar_storage.get_activity_sidebar_icon.side_effect = (
            self._get_activity_sidebar_icon
        )
        app.app.avatar_storage.get_gajim_circle_icon.side_effect = (
            self._get_gajim_circle_icon
        )

        activity_list = ActivityList()
        activity_list.connect("row-activated", self._on_activity_row_activated)
        activity_list.connect("row-removed", self._on_activity_row_removed)
        activity_list_scrolled = Gtk.ScrolledWindow(
            child=activity_list, width_request=300
        )

        self._activity_page = ActivityPage()

        paned = Gtk.Paned(
            shrink_start_child=False,
            resize_start_child=False,
            position=250,
            start_child=activity_list_scrolled,
            end_child=self._activity_page,
        )

        self._activity_sidebar = ActivitySideBar(activity_list)
        self._activity_sidebar.set_valign(Gtk.Align.START)

        main_box = Gtk.Box()
        main_box.append(self._activity_sidebar)
        main_box.append(paned)

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
        button_box.add_css_class("floating-overlay-box")
        button_box.append(update_button)
        button_box.append(subscription_button)
        button_box.append(invitation_button)

        overlay = Gtk.Overlay(hexpand=True)
        overlay.set_child(main_box)
        overlay.add_overlay(button_box)
        self.set_child(overlay)

    def _cleanup(self) -> None:
        pass

    def _get_activity_sidebar_icon(
        self,
        size: int,
        scale: int,
    ) -> Gdk.Texture | None:
        return AvatarStorage.get_activity_sidebar_icon(size, scale)

    def _get_gajim_circle_icon(self, size: int, scale: int) -> Gdk.Texture | None:
        return AvatarStorage.get_gajim_circle_icon(size, scale)

    def show_activity_page(self) -> None:
        self._activity_sidebar.select()
        self._activity_page.show_page("default")

    def _on_activity_row_activated(
        self, _listbox: ActivityList, row: ActivityListRow
    ) -> None:
        self._activity_page.process_row_activated(row)

    def _on_activity_row_removed(self, _listbox: ActivityList) -> None:
        self._activity_page.show_page("default")

    def _on_update_button_clicked(self, _button: Gtk.Button) -> None:
        app.plugin_repository.trigger_plugin_update()  # type: ignore
        app.plugin_repository.trigger_plugin_update_successful()  # type: ignore
        app.ged.raise_event(events.AllowGajimUpdateCheck())
        app.ged.raise_event(
            events.GajimUpdateAvailable("2.0.0", "https://gajim.org/download")
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

    def _on_invitation_button_clicked(self, _button: Gtk.Button) -> None:
        muc_info = DiscoInfo(None, [], [], [], None)
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

app.settings = MagicMock()
app.window = MagicMock()

app.get_client = MagicMock(return_value=TestClient)

app.css_config = MagicMock()
app.css_config.get_dynamic_class = MagicMock(
    return_value=".test-class {{ background-color: purple }}\n"
)

window = TestActivityCenter()
window.show()

app.window.show_activity_page = window.show_activity_page

util.run_app()
