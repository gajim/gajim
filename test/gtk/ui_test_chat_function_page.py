# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.chat_function_page import ChatFunctionPage
from gajim.gtk.chat_function_page import FunctionMode
from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.dropdown import KeyValueItem
from gajim.gtk.widgets import GajimAppWindow

from . import util

FUNCTION_DATA = {
    FunctionMode.KICK: "Nasty User",
    FunctionMode.BAN: "Nasty User",
    FunctionMode.CAPTCHA_ERROR: "Captcha error message",
    FunctionMode.JOIN_FAILED: "registration-required",
    FunctionMode.CREATION_FAILED: "Creation failed message",
    FunctionMode.CONFIG_FAILED: "Config failed message",
}

ACCOUNT = "testacc1"
FROM_JID = "test@example.org"


class TestChatFunctionPage(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=700,
            default_height=700,
        )

        self._main_box = Gtk.Box(
            hexpand=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            orientation=Gtk.Orientation.VERTICAL,
        )

        self._chat_function_page = ChatFunctionPage()
        self._chat_function_page.connect("finish", self._on_finish)
        self._chat_function_page.connect("message", self._on_message)

        self._main_box.append(self._chat_function_page)

        drop_down = GajimDropDown([item.name for item in FunctionMode])
        drop_down.connect("notify::selected", self._on_function_mode_selected)
        drop_down.set_selected(1)
        self._main_box.append(drop_down)

        self.set_child(self._main_box)

    def _on_function_mode_selected(self, drop_down: GajimDropDown, *args: Any) -> None:
        selected_mode = drop_down.get_selected_item()
        assert isinstance(selected_mode, KeyValueItem)
        mode = selected_mode.key
        data = FUNCTION_DATA.get(FunctionMode[selected_mode.key])
        files = ["test.txt"]

        contact_type = "bare"
        if FunctionMode[mode] == FunctionMode.CHANGE_NICKNAME:
            contact_type = "groupchat"

        contact = self._get_contact(contact_type)

        self._chat_function_page.set_mode(contact, FunctionMode[mode], data, files)

    def _get_contact(self, contact_type: str) -> BareContact | GroupchatContact:
        if contact_type == "bare":
            contact = MagicMock(spec_set=BareContact)
        else:
            contact = MagicMock(spec_set=GroupchatContact)
            contact.nickname = "Nickname"

        contact.account = ACCOUNT
        contact.jid = JID.from_string(FROM_JID)
        contact.name = "Example Contact"
        return contact

    def _on_finish(self, widget: ChatFunctionPage, finished: bool) -> None:
        print("Close control", finished)

    def _on_message(self, widget: ChatFunctionPage, message: str) -> None:
        print("Message", message)


util.init_settings()

app.get_client = MagicMock()
app.account_is_connected = MagicMock(return_value=True)

app.window = MagicMock()
app.window.get_preferred_ft_method = MagicMock(return_value="httpupload")

window = TestChatFunctionPage()
window.show()

util.run_app()
