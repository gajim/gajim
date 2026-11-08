# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Final

import locale
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import XmppUriQuery
from gajim.common.helpers import idle_add_once
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem

log = logging.getLogger("gajim.gtk.completion.contact")


MAX_COMPLETION_ENTRIES = 10


class ContactListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "ContactCompletionListItem"

    name = GObject.Property(type=str)
    name_cmp = GObject.Property(type=str)

    def __init__(self, contact: BareContact | GroupchatContact) -> None:
        self._contact = contact
        self._avatar = None
        self._scale = app.window.get_scale_factor()

        name = contact.name

        super().__init__(
            name=name,
            name_cmp=name.casefold(),
        )

    @GObject.Property(type=Gdk.Texture, flags=GObject.ParamFlags.READABLE)
    def avatar(self) -> Gdk.Texture:
        # Load avatar lazy
        if self._avatar is None:
            if isinstance(self._contact, GroupchatContact):
                self._avatar = self._contact.get_avatar(AvatarSize.SMALL, self._scale)
            else:
                self._avatar = self._contact.get_avatar(
                    AvatarSize.SMALL, self._scale, add_show=False
                )
        return self._avatar

    def get_text(self) -> str:
        if self._contact.is_groupchat:
            return self._contact.jid.to_iri(XmppUriQuery.JOIN.value)
        return self._contact.jid.to_iri()


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
        BaseCompletionProvider.__init__(self)
        self._list_store = Gio.ListStore(item_type=ContactListItem)
        self._account: str | None = None

        expression = Gtk.PropertyExpression.new(ContactListItem, None, "name")

        self._string_filter = Gtk.StringFilter(expression=expression)
        self._filter_model = Gtk.FilterListModel(
            model=self._list_store, filter=self._string_filter
        )

        sorter = Gtk.CustomSorter()
        sorter.set_sort_func(self._sort_func, self._string_filter)  # type: ignore
        sort_model = Gtk.SortListModel(model=self._filter_model, sorter=sorter)

        self._model = Gtk.SliceListModel(model=sort_model, size=MAX_COMPLETION_ENTRIES)
        self._model.connect("items-changed", self._on_items_changed)

    def get_model(
        self,
    ) -> tuple[Gio.ListModel[ContactListItem], type[ContactViewItem]]:
        return self._model, ContactViewItem

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        return candidate.startswith(self.trigger_char)

    def populate(self, candidate: str, contact: ChatContactT) -> bool:
        search = candidate.removeprefix(self.trigger_char)
        if not search:
            return False

        if self._account != contact.account:
            self._account = contact.account
            self._filter_model.set_model(None)

            known_contacts = self._get_known_contacts(contact.account)
            self._list_store.splice(0, self._list_store.get_n_items(), known_contacts)

        self._string_filter.set_search(search.casefold())
        self._filter_model.set_model(self._list_store)
        return self._model.get_n_items() > 0

    @staticmethod
    def _sort_func(
        a: ContactListItem,
        b: ContactListItem,
        string_filter: Gtk.StringFilter,
    ) -> int:
        search = string_filter.get_search()

        a_has_prefix = a.name_cmp.startswith(search)
        b_has_prefix = b.name_cmp.startswith(search)

        if a_has_prefix is b_has_prefix:
            return locale.strcoll(a.name, b.name)

        return -1 if a_has_prefix else 1

    @staticmethod
    def _get_known_contacts(account: str) -> list[ContactListItem]:
        client = app.get_client(account)

        items: list[ContactListItem] = []

        for bookmark in client.get_module("Bookmarks").bookmarks:
            contact = client.get_module("Contacts").get_contact(
                bookmark.jid, groupchat=True
            )
            assert isinstance(contact, GroupchatContact)
            items.append(ContactListItem(contact))

        for jid, _data in client.get_module("Roster").iter():
            contact = client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            items.append(ContactListItem(contact))

        return items

    def _on_items_changed(self, *args: Any) -> None:
        idle_add_once(self.emit, "suggestions-changed")
