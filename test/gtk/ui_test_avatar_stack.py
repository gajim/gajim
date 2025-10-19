# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime as dt
from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.protocol import JID

import gajim.common.storage.archive.models as mod
from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.storage.archive.storage import MessageArchiveStorage

from gajim.gtk.avatar import AvatarStorage
from gajim.gtk.conversation.avatar_stack import AvatarStack
from gajim.gtk.css_config import CSSConfig
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT = "testacc1"
REMOTE_JID = JID.from_string("user@domain.org")


class TestAvatarStack(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=800,
            default_height=800,
        )

        app.app = MagicMock()
        app.app.avatar_storage = AvatarStorage()

        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
        self.set_child(box)

        avatar_stack = AvatarStack()
        box.append(avatar_stack)

        markers = app.storage.archive.get_display_markers(
            "testacc1", JID.from_string("user@domain.org")
        )
        avatar_stack.set_data(list(markers))


def insert_test_markers() -> None:

    occupants: dict[int, mod.Occupant] = {}
    for i in range(10):
        occupants[i] = mod.Occupant(
            account_=ACCOUNT,
            remote_jid_=REMOTE_JID,
            id=f"occupantid{i}",
            nickname=f"nickname{i}",
            updated_at=dt.datetime.fromtimestamp(0, dt.UTC),
        )

    uuid = get_uuid()

    for i in range(10):
        marker = mod.DisplayedMarker(
            account_=ACCOUNT,
            remote_jid_=REMOTE_JID,
            occupant_=occupants[i],
            id=uuid,
            timestamp=dt.datetime.fromtimestamp(1000 * i, dt.UTC),
        )

        app.storage.archive.insert_object(marker)


util.init_settings()

app.settings.add_account(ACCOUNT)
app.settings.set_account_setting("testacc1", "address", "user@domain.org")
app.storage.archive = MessageArchiveStorage(in_memory=True)
app.storage.archive.init()
insert_test_markers()

app.css_config = CSSConfig()

window = TestAvatarStack()
window.show()

util.run_app()
