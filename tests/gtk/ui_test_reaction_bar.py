# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.protocol import JID

import gajim.common.storage.archive.models as mod
from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ContactSettings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.util.datetime import utc_now
from tests.gtk import util

from gajim.gtk.avatar import AvatarStorage
from gajim.gtk.conversation.reactions_bar import ReactionsBar
from gajim.gtk.conversation.rows.message import MessageRow
from gajim.gtk.css_config import CSSConfig
from gajim.gtk.window import GajimAppWindow


class TestReactionBar(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=300,
            default_height=300,
            add_window_padding=True,
            header_bar=True,
        )

        app.app = MagicMock()
        app.app.avatar_storage = AvatarStorage()

        self._account = "testacc1"
        self._account_jid = JID.from_string("user@domain.org")
        self._remote_jid = JID.from_string("remote@jid.org")

        app.settings.add_account(self._account)
        app.settings.set_account_setting(self._account, "address", "user@domain.org")

        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)

        message = self._prepare_database()

        contact = self._get_contact()
        row = MessageRow(contact, message)
        bar = ReactionsBar(row, contact)
        box.append(bar)

        bar.update_from_reactions(message.reactions)
        bar.set_sensitive(True)
        self.set_child(box)

    def _prepare_database(self) -> mod.Message:
        uuid = get_uuid()

        emojis = [
            "😇️;😁️;😄;❤️;🫒;✌️;😍",
            "😇️;😁️;😄;❤️;🫒;✌️",
            "😇️;😁️;😄;❤️;🫒",
            "😇️;😁️;😄;❤️",
            "😇️;😁️;😄",
            "😇️;😁️",
            "😇️",
        ]

        for index, emoji in enumerate(emojis):
            for num in range(20):
                occupant = mod.Occupant(
                    account_=self._account,
                    remote_jid_=self._remote_jid,
                    id=f"occupantid{num}-{index}",
                    nickname=f"nickname{num}-{index}",
                    updated_at=utc_now(),
                )
                reaction = mod.Reaction(
                    account_=self._account,
                    remote_jid_=self._remote_jid,
                    occupant_=occupant,
                    id=uuid,
                    direction=ChatDirection.INCOMING,
                    emojis=emoji,
                    timestamp=utc_now(),
                )

                self._archive.upsert_row2(reaction, return_full=False)

        message_data = mod.Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            resource="res",
            text="Some Message",
            id=uuid,
            stanza_id=uuid,
            occupant_=None,
        )

        pk = self._archive.insert_object(message_data)
        assert pk is not None

        message = self._archive.get_message_with_pk(pk)
        assert message is not None
        return message

    def _cleanup(self) -> None:
        pass

    def _get_contact(self) -> BareContact:
        contact = MagicMock(spec="BareContact")
        contact.connect = MagicMock()
        contact.account = self._account
        contact.jid = JID.from_string(self._remote_jid)
        contact.name = "Test Contact"
        contact.is_groupchat = False
        contact.get_avatar = MagicMock(return_value=None)
        contact.settings = ContactSettings(
            self._account, JID.from_string(self._account)
        )
        contact.disconnect_all_from_obj = MagicMock()
        return contact


util.init_settings()

app.css_config = CSSConfig()
app.get_client = MagicMock()

window = TestReactionBar()
window.show()

util.run_app()
