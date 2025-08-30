# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

import datetime as dt
from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.const import PresenceShow
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ContactSettings

from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.contact_popover import ContactPopover
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT = "account"


class TestContactPopover(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=800,
        )
        contact = self._get_contact()

        scale = self.window.get_scale_factor()
        image = Gtk.Image.new_from_paintable(
            contact.get_avatar(AvatarSize.ACCOUNT_PAGE, scale)
        )
        image.set_pixel_size(AvatarSize.ACCOUNT_PAGE)

        button = Gtk.MenuButton(halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
        button.set_child(image)
        button.add_css_class("flat")
        self.set_child(button)

        popover = ContactPopover(contact)

        button.set_popover(popover)

        popover._on_vcard_received(
            JID.from_string("test@test.com"), self._get_vcard()
        )  # pyright: ignore

    def _get_contact(self) -> BareContact:
        contact = MagicMock(spec="BareContact")
        contact.connect = MagicMock()
        contact.disconnect_all_from_obj = MagicMock()

        contact.account = ACCOUNT
        contact.is_groupchat = False
        contact.is_self = False
        avatar = convert_surface_to_texture(
            generate_default_avatar(
                "T", (0.2, 0.1, 0.7), AvatarSize.ACCOUNT_PAGE, self.get_scale_factor()
            )
        )
        contact.get_avatar = MagicMock(return_value=avatar)
        contact.settings = ContactSettings(ACCOUNT, JID.from_string(ACCOUNT))

        contact.name = "Contact Name"
        contact.jid = JID.from_string("contact@example.org")

        contact.show = PresenceShow.ONLINE
        contact.status = "Status Message Text with a really long status message of many word with many characters"  # noqa: E501

        contact.idle_datetime = dt.datetime.now() - dt.timedelta(minutes=15)

        contact.subscription = "from"

        return contact

    def _get_vcard(self) -> VCard:
        vcard = VCard()
        vcard.add_property("org", values=["Gajim"])
        vcard.add_property("role", value="Admin")
        vcard.add_property("tel", value="+1454545544", value_type="text")
        vcard.add_property("email", value="mail@mail.com")
        vcard.add_property("tz", value="Europe/London", value_type="text")
        return vcard


def get_color(selector: str, *args: Any) -> str:
    if selector == ".gajim-status-online":
        return "rgb(102, 191, 16)"
    if selector == ".gajim-status-away":
        return "rgb(255, 133, 51)"
    return "rgb(100, 100, 100)"


app.get_client = MagicMock()
app.window = MagicMock()

util.init_settings()

app.settings.add_account(ACCOUNT)
app.settings.set_account_setting(ACCOUNT, "address", "user@example.org")

app.css_config = MagicMock()
app.css_config.get_value = MagicMock(side_effect=get_color)

app.plugin_manager = MagicMock()

window = TestContactPopover()
window.show()

util.run_app()
