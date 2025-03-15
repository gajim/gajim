# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator
from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.storage.cache import CacheStorage

from gajim.gtk.resource_selector import ResourceSelector
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT = "testacc1"
FROM_JID = "test@example.org"


class TestResourceSelector(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            width_request=500,
            height_request=700,
        )
        self.set_child(box)

        contact = self._get_contact()

        self._resources = self._generate_resources()

        self._resource_selector = ResourceSelector(contact)
        self._resource_selector.set_hexpand(True)
        self._resource_selector.connect("selection-changed", self._on_selection_changed)
        box.append(self._resource_selector)

    def _on_selection_changed(
        self, _resource_selector: ResourceSelector, state: bool
    ) -> None:
        print("Selection available:", state)

    def _get_contact(self) -> BareContact:
        contact = MagicMock(spec_set=BareContact)
        contact.account = ACCOUNT
        contact.jid = JID.from_string(FROM_JID)
        contact.name = "Test Contact"
        contact.is_groupchat = False
        contact.iter_resources = MagicMock(side_effect=self._iter_resources)
        return contact

    def _generate_resources(self) -> list[ResourceContact]:
        resources: list[ResourceContact] = []
        for index in range(5):
            resource_contact = MagicMock(spec_set=ResourceContact)
            resource_contact.jid = JID.from_string(f"{FROM_JID}/Resource.{index}")
            resources.append(resource_contact)

        return resources

    def _iter_resources(self) -> Iterator[ResourceContact]:
        yield from self._resources


util.init_settings()

app.storage.cache = CacheStorage(in_memory=True)
app.storage.cache.init()

window = TestResourceSelector()
window.show()

util.run_app()
