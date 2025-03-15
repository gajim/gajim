# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

import datetime as dt
import random
import string
from collections.abc import Iterator
from unittest.mock import MagicMock

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import RosterItem

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import CSSPriority
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.avatar import convert_surface_to_texture
from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.start_chat import StartChatDialog

from . import util

ACCOUNTS_COUNT = 2
CONTACTS_PER_ACCOUNT_COUNT = 10
CONTACTS_COUNT = int(CONTACTS_PER_ACCOUNT_COUNT / 2)
GROUPCHATS_COUNT = int(CONTACTS_PER_ACCOUNT_COUNT / 2)
CONTACT_GROUPS = {"Group A", "Group B", "Group C with long name"}
STATUS_MESSAGES = [
    "Status Message very very very very very long\nwith newline",
    "Status message",
    "",
]


class TestRosterModule:
    def __init__(self, account: str) -> None:
        self._account = account
        self._roster: dict[JID, RosterItem] = {}
        for i in range(CONTACTS_COUNT):
            jid = JID.from_string(f"test{i}@{self._account}.org")
            self._roster[jid] = RosterItem(
                jid=jid,
                name=f"name{i}",
                ask=None,
                subscription=None,
                approved=None,
                groups=set(),
            )

    def get_groups(self) -> set[str]:
        return CONTACT_GROUPS

    def iter(self) -> Iterator[tuple[JID, RosterItem]]:
        yield from self._roster.items()


class TestBookmarksModule:
    def __init__(self, account: str) -> None:
        self._account = account
        self._bookmarks: dict[JID, BookmarkData] = {}

        for i in range(GROUPCHATS_COUNT):
            jid = JID.from_string(f"groupchat{i}@conference.{self._account}.org")
            self._bookmarks[jid] = BookmarkData(
                jid=jid,
                name=f"name{i}",
            )

    @property
    def bookmarks(self) -> list[BookmarkData]:
        return list(self._bookmarks.values())


class TestContactsModule:
    def __init__(self, account: str) -> None:
        self._account = account

        self._avatars: list[Gdk.Texture] = []
        alphabet = list(string.ascii_uppercase)
        for _i in range(5):
            color = (
                random.randrange(100) / 100,
                random.randrange(100) / 100,
                random.randrange(100) / 100,
            )
            avatar = generate_default_avatar(
                random.choice(alphabet), color, AvatarSize.CALL_BIG, 1
            )
            self._avatars.append(convert_surface_to_texture(avatar))

        self._contact_index = 0
        self._groupchat_contact_index = 0

    def get_contact(self, jid: str | JID, groupchat: bool = False) -> BareContact:
        if groupchat:
            spec_set = GroupchatContact
            contact_name = f"Group Chat {self._groupchat_contact_index}"
            self._groupchat_contact_index += 1
        else:
            contact_name = f"Contact {self._contact_index}"
            spec_set = BareContact
            self._contact_index += 1

        contact = MagicMock(spec_set=spec_set)
        contact.jid = jid
        contact.name = contact_name
        contact.get_avatar = MagicMock(return_value=random.choice(self._avatars))

        contact.account = self._account
        contact.is_groupchat = groupchat

        if not groupchat:
            contact.status = random.choice(STATUS_MESSAGES)
            contact.idle_datetime = dt.datetime.now()
            contact.groups = set(random.sample(sorted(CONTACT_GROUPS), 1))

        return contact


class TestClient:
    def __init__(self, account: str) -> None:
        self._account = account

        self._contacts_module = TestContactsModule(self._account)
        self._bookmarks_module = TestBookmarksModule(self._account)
        self._roster_module = TestRosterModule(self._account)

    def get_own_jid(self) -> JID:
        return JID.from_string(self._account)

    def get_module(self, module: str) -> Any:
        if module == "Contacts":
            return self._contacts_module
        if module == "Bookmarks":
            return self._bookmarks_module
        if module == "Roster":
            return self._roster_module
        return MagicMock()


def _get_dynamic_class(account: str) -> str:
    color = app.settings.get_account_setting(account, "account_color")
    css_class = f"gajim_class_{account}"
    css = f".{css_class} {{ background-color: {color}; }}\n"
    dynamic_provider = Gtk.CssProvider()
    dynamic_provider.load_from_bytes(GLib.Bytes.new(css.encode("utf-8")))
    display = Gdk.Display.get_default()
    assert display is not None
    Gtk.StyleContext.add_provider_for_display(
        display, dynamic_provider, CSSPriority.APPLICATION
    )
    return css_class


accounts: list[list[str]] = []
for i in range(ACCOUNTS_COUNT):
    accounts.append(
        [f"account{i}", f"Account {i}"],
    )

util.init_settings()

for account in accounts:
    app.settings.add_account(account[0])
    app.settings.set_account_setting(
        account[0],
        "account_color",
        f"rgb({random.randrange(255)}, {random.randrange(255)}, {random.randrange(255)})",  # noqa: E501
    )
    app.settings.set_account_setting(account[0], "account_label", account[1])


app.css_config = MagicMock()
app.css_config.get_dynamic_class = MagicMock(side_effect=_get_dynamic_class)

app.get_client = MagicMock(side_effect=TestClient)

app.get_enabled_accounts_with_labels = MagicMock(return_value=accounts)


window = StartChatDialog()
window.show()

util.run_app()
