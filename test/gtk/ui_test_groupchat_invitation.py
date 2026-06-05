# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import InviteType
from nbxmpp.modules.discovery import parse_disco_info
from nbxmpp.protocol import Iq

from gajim.common import app
from gajim.common.events import MucInvitation
from test.gtk.application import GajimTestApplication

from gajim.gtk.groupchat_invitation import GroupChatInvitation
from gajim.gtk.window import GajimAppWindow

MUC_JID = JID.from_string("group@conference.example.org")

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

ACCOUNT = "testacc0"


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

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        main_box.set_valign(Gtk.Align.FILL)

        event = MucInvitation(
            account=ACCOUNT,
            info=disco_info,
            muc=MUC_JID,
            from_=JID.from_string("contact@example.org"),
            reason="Reason",
            password=None,
            type=InviteType.MEDIATED,
            continued=False,
            thread=None,
        )
        invitation_box = GroupChatInvitation(ACCOUNT, event)
        invitation_box.set_vexpand(True)

        main_box.append(invitation_box)

        self.set_child(main_box)

    def _cleanup(self) -> None:
        pass


def init(app: GajimTestApplication) -> None:
    app.add_account("testacc0")
    app.add_account("testacc1")
    window = TestGroupchatInvitation()
    window.present()


if __name__ == "__main__":
    # Protect the entry point of the application because we use
    # the multiprocessing module with "spawn"
    app = GajimTestApplication()
    app.connect("activate", init)
    app.run(None)
