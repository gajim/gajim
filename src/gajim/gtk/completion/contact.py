# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Final

import logging
from collections.abc import Iterator

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import XmppUriQuery
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem

log = logging.getLogger("gajim.gtk.completion.contact")


MAX_COMPLETION_ENTRIES = 10


class ContactListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "ContactCompletionListItem"

    jid: JID = GObject.Property(type=object)  # type: ignore
    name = GObject.Property(type=str)
    is_groupchat = GObject.Property(type=bool, default=False)
    avatar = GObject.Property(type=Gdk.Texture)

    def __init__(self, contact: BareContact | GroupchatContact) -> None:
        scale = app.window.get_scale_factor()
        super().__init__(
            jid=contact.jid,
            name=contact.name,
            is_groupchat=contact.is_groupchat,
            avatar=contact.get_avatar(AvatarSize.SMALL, scale),
        )

    def get_text(self) -> str:
        if self.is_groupchat:
            return self.jid.to_iri(XmppUriQuery.JOIN.value)
        return self.jid.to_iri()


class ContactViewItem(BaseCompletionViewItem[ContactListItem], Gtk.Box):
    __gtype_name__ = "ContactCompletionViewItem"
    css_class = "contact-completion"

    def __init__(self) -> None:
        super().__init__()
        Gtk.Box.__init__(self, spacing=6)
        self.set_size_request(200, -1)

        self._label = Gtk.Label()
        self._image = Gtk.Image(pixel_size=AvatarSize.SMALL)
        self.append(self._image)
        self.append(self._label)

    def bind(self, obj: ContactListItem) -> None:
        bind_spec = [
            ("name", self._label, "label"),
            ("avatar", self._image, "paintable"),
        ]

        for source_prop, widget, target_prop in bind_spec:
            bind = obj.bind_property(
                source_prop, widget, target_prop, GObject.BindingFlags.SYNC_CREATE
            )
            self._bindings.append(bind)

    def unbind(self) -> None:
        for bind in self._bindings:
            bind.unbind()
        self._bindings.clear()

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)


class ContactProvider(BaseCompletionProvider):
    trigger_char: Final = "xmpp:"
    id: Final = "contact"
    name = _("Contacts")

    def __init__(self) -> None:
        self._list_store = Gio.ListStore(item_type=ContactListItem)
        self._account: str | None = None

        expression = Gtk.PropertyExpression.new(ContactListItem, None, "name")

        self._string_filter = Gtk.StringFilter(expression=expression)

        sorter = Gtk.StringSorter.new(expression=expression)
        sort_model = Gtk.SortListModel(model=self._list_store, sorter=sorter)

        filter_model = Gtk.FilterListModel(model=sort_model, filter=self._string_filter)
        self._model = Gtk.SliceListModel(
            model=filter_model, size=MAX_COMPLETION_ENTRIES
        )

    def get_model(
        self,
    ) -> tuple[Gio.ListModel[ContactListItem], type[ContactViewItem]]:
        return self._model, ContactViewItem

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        return candidate.startswith(self.trigger_char)

    def populate(self, candidate: str, contact: Any) -> bool:
        if self._account != contact.account:
            self._list_store.remove_all()
            for known_contact in self._get_known_contacts(contact.account):
                self._list_store.append(ContactListItem(known_contact))
            self._account = contact.account

        candidate = candidate.removeprefix(self.trigger_char)
        self._string_filter.set_search(candidate)
        return self._model.get_n_items() > 0

    def _get_known_contacts(
        self, account: str
    ) -> Iterator[GroupchatContact | BareContact]:
        client = app.get_client(account)

        for bookmark in client.get_module("Bookmarks").bookmarks:
            contact = client.get_module("Contacts").get_contact(
                bookmark.jid, groupchat=True
            )
            yield cast(GroupchatContact, contact)

        for jid, _data in client.get_module("Roster").iter():
            contact = client.get_module("Contacts").get_contact(jid)
            yield cast(BareContact, contact)
