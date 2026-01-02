# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any

import random
from unittest.mock import MagicMock

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import InviteType
from nbxmpp.modules.discovery import parse_disco_info
from nbxmpp.protocol import Iq
from nbxmpp.structs import BookmarkData

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import CSSPriority
from gajim.common.events import MucInvitation
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.avatar import convert_surface_to_texture
from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.groupchat_invitation import GroupChatInvitation
from gajim.gtk.window import GajimAppWindow

from . import util

MUC_JID = JID.from_string("group@conference.example.org")
INVITER_JID = JID.from_string("contact@example.org")

accounts: list[list[str]] = []
for i in range(2):
    accounts.append(
        [f"testacc{i}", f"Account {i}"],
    )

stanza = Iq(
    node=f"""
<iq xmlns="jabber:client" xml:lang="de-DE" to="me@example.org" from="{MUC_JID}" type="result" id="67284933-e526-41f3-8309-9d9475cf9c74">
    <query
        xmlns="http://jabber.org/protocol/disco#info">
        <identity name="ipsum dolor sit amet, consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt" type="text" category="conference" />
        <feature var="vcard-temp" />
        <feature var="http://jabber.org/protocol/muc" />
        <feature var="http://jabber.org/protocol/disco#info" />
        <feature var="http://jabber.org/protocol/disco#items" />
        <feature var="muc_temporary" />
        <feature var="muc_moderated" />
        <feature var="muc_open" />
        <feature var="muc_hidden" />
        <feature var="muc_nonanonymous" />
        <feature var="muc_passwordprotected" />
        <feature var="urn:xmpp:mam:2" />
        <feature var="muc_public" />
        <feature var="muc_persistent" />
        <feature var="muc_membersonly" />
        <feature var="muc_semianonymous" />
        <feature var="muc_unmoderated" />
        <feature var="muc_unsecured" />
        <x type="result"
            xmlns="jabber:x:data">
            <field var="FORM_TYPE" type="hidden">
                <value>http://jabber.org/protocol/muc#roominfo</value>
            </field>
            <field var="muc#roominfo_occupants" type="text-single" label="Number of occupants">
                <value>1</value>
            </field>
            <field var="muc#roomconfig_roomname" type="text-single" label="Natural-Language Room Name">
                <value>ipsum dolor sit amet, consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt</value>
            </field>
            <field var="muc#roominfo_description" type="text-single" label="Raum Beschreibung">
                <value>Lorem ipsum dolor sit amet, consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore magna</value>
            </field>
            <field var="muc#roominfo_contactjid" type="jid-multi" label="Contact Addresses (normally, room owner or owners)">
                <value>userA@user.us</value>
                <value>userB@user.us</value>
            </field>
            <field var="muc#roominfo_changesubject" type="boolean" label="Occupants May Change the Subject">
                <value>1</value>
            </field>
            <field var="muc#roomconfig_allowinvites" type="boolean" label="Occupants are allowed to invite others">
                <value>1</value>
            </field>
            <field var="muc#roomconfig_allowpm" type="list-single" label="Roles that May Send Private Messages">
                <value>anyone</value>
                <option label="Anyone">
                    <value>anyone</value>
                </option>
                <option label="Anyone with Voice">
                    <value>participants</value>
                </option>
                <option label="Moderators Only">
                    <value>moderators</value>
                </option>
                <option label="Nobody">
                    <value>none</value>
                </option>
            </field>
            <field var="muc#roominfo_lang" type="text-single" label="Natural Language for Room Discussions">
                <value>de</value>
            </field>
            <field type="text-single" var="muc#roominfo_logs">
                <value>https://logs.xmpp.org/xsf/</value>
            </field>
        </x>
    </query>
</iq>"""  # type: ignore  # noqa: E501
)


subject = (
    "Lorem ipsum dolor sit amet, consetetur sadipscing elitr sed "
    "diam nonumy eirmod tempor invidunt ut labore et dolore magna"
)

disco_info = parse_disco_info(stanza)


class TestGroupchatInvitation(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=700,
            default_height=700,
            add_window_padding=True,
            header_bar=True,
        )

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._main_box.set_valign(Gtk.Align.FILL)

        event = MucInvitation(
            account=accounts[0][0],
            info=disco_info,
            muc=MUC_JID,
            from_=INVITER_JID,
            reason="Reason",
            password=None,
            type=InviteType.MEDIATED,
            continued=False,
            thread=None,
        )
        invitation_box = GroupChatInvitation(accounts[0][0], event)
        invitation_box.set_vexpand(True)

        self._main_box.append(invitation_box)

        self.set_child(self._main_box)

    def _cleanup(self) -> None:
        pass


class TestContactsModule:
    def __init__(self) -> None:
        pass

    @staticmethod
    def get_contact(
        jid: str | JID, groupchat: bool = False
    ) -> BareContact | GroupchatContact:
        if jid == MUC_JID:
            contact = MagicMock(spec_set=GroupchatContact)
            contact.jid = MUC_JID
            contact.name = "Group Chat Name"
            contact.is_groupchat = True
            avatar = convert_surface_to_texture(
                generate_default_avatar("G", (0.2, 0.7, 0.4), AvatarSize.GROUP_INFO, 1)
            )
        else:
            contact = MagicMock(spec_set=BareContact)
            contact.jid = INVITER_JID
            contact.name = "Inviter Name"
            contact.is_groupchat = False
            avatar = convert_surface_to_texture(
                generate_default_avatar("I", (0.2, 0.1, 0.7), AvatarSize.SMALL, 1)
            )

        contact.get_avatar = MagicMock(return_value=avatar)
        contact.account = accounts[0]

        return contact


class TestBookmarksModule:
    def __init__(self) -> None:
        pass

    def get_bookmark(self, jid: str | JID) -> BookmarkData:
        return BookmarkData(jid=MUC_JID, name="Group Chat Name", nick="Nickname")

    @staticmethod
    def get_name_from_bookmark(jid: JID | str) -> str:
        return "Group Chat Name"


class TestClient:
    def __init__(self, account: str) -> None:
        self._account = account

        self._contacts_module = TestContactsModule()
        self._bookmarks_module = TestBookmarksModule()

    def get_module(self, module: str) -> Any:
        if module == "Contacts":
            return self._contacts_module
        if module == "Bookmarks":
            return self._bookmarks_module
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


app.css_config = MagicMock()
app.css_config.get_value = MagicMock(return_value="rgb(100, 100, 255)")
app.css_config.get_dynamic_class = MagicMock(side_effect=_get_dynamic_class)

app.get_enabled_accounts_with_labels = MagicMock(return_value=[1, 2])

test_client = TestClient(accounts[0][0])
app.get_client = MagicMock(return_value=test_client)

util.init_settings()

for account in accounts:
    app.settings.add_account(account[0])
    app.settings.set_account_setting(
        account[0],
        "account_color",
        f"rgb({random.randrange(255)}, {random.randrange(255)}, {random.randrange(255)})",  # noqa: E501
    )
    app.settings.set_account_setting(account[0], "account_label", account[1])


window = TestGroupchatInvitation()
window.show()

util.run_app()
