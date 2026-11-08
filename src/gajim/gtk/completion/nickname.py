# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Final

import itertools
import locale
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.events import MessageReceived
from gajim.common.helpers import idle_add_once
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatOfflineParticipant
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem

log = logging.getLogger("gajim.gtk.completion.nickname")


MAX_COMPLETION_ENTRIES = 10


class NicknameCompletionListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "NicknameCompletionListItem"

    nickname = GObject.Property(type=str)
    nickname_cmp = GObject.Property(type=str)

    def __init__(
        self, contact: GroupchatParticipant | GroupchatOfflineParticipant, scale: int
    ) -> None:
        self._contact = contact
        self._avatar = None
        self._scale = scale

        super().__init__(
            nickname=contact.name,
            nickname_cmp=contact.name.casefold(),
        )

    @GObject.Property(type=Gdk.Texture, flags=GObject.ParamFlags.READABLE)
    def avatar(self) -> Gdk.Texture:
        # Load avatar lazy
        if self._avatar is None:
            self._avatar = self._contact.get_avatar(
                AvatarSize.SMALL, self._scale, add_show=False
            )
        return self._avatar

    def get_text(self) -> str:
        return self.nickname


class NicknameCompletionViewItem(
    BaseCompletionViewItem[NicknameCompletionListItem], Gtk.Box
):
    __gtype_name__ = "NicknameCompletionViewItem"
    css_class = "nickname-completion"

    def __init__(self) -> None:
        super().__init__()
        Gtk.Box.__init__(self, spacing=6)
        self.set_size_request(200, -1)

        self._label = Gtk.Label()
        self._image = Gtk.Image(pixel_size=AvatarSize.SMALL)
        self.append(self._image)
        self.append(self._label)

    def bind(self, obj: NicknameCompletionListItem) -> None:
        bind_spec = [
            ("nickname", self._label, "label"),
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


class NicknameCompletionProvider(BaseCompletionProvider):
    trigger_char: Final = "@"
    id: Final = "nickname"
    name = _("Participants")

    __gtype_name__ = "NicknameCompletionProvider"

    def __init__(self) -> None:
        BaseCompletionProvider.__init__(self)
        self._list_store = Gio.ListStore(item_type=NicknameCompletionListItem)
        self._contact: GroupchatContact | None = None

        app.ged.register_event_handler(
            "message-received", ged.GUI2, self._on_message_received
        )

        expression = Gtk.PropertyExpression.new(
            NicknameCompletionListItem, None, "nickname"
        )

        self._string_filter = Gtk.StringFilter(expression=expression, ignore_case=True)
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
    ) -> tuple[
        Gio.ListModel[NicknameCompletionListItem], type[NicknameCompletionViewItem]
    ]:
        return self._model, NicknameCompletionViewItem

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        return candidate.startswith(self.trigger_char)

    def populate(self, candidate: str, contact: Any) -> bool:
        if not isinstance(contact, GroupchatContact):
            return False

        search = candidate.lstrip(self.trigger_char)
        if not search:
            return False

        if self._contact is not contact:
            # New contact, regenerate suggestions
            # Remove model before doing operations on the ListStore so
            # no changes need to propagate
            self._filter_model.set_model(None)
            # Use splice, this is more performant than remove/insert
            self._list_store.splice(
                0, self._list_store.get_n_items(), self._generate_suggestions(contact)
            )

            self._contact = contact

        self._string_filter.set_search(search.casefold())
        self._filter_model.set_model(self._list_store)
        return self._model.get_n_items() > 0

    @staticmethod
    def _sort_func(
        a: NicknameCompletionListItem,
        b: NicknameCompletionListItem,
        string_filter: Gtk.StringFilter,
    ) -> int:
        search = string_filter.get_search()

        a_has_prefix = a.nickname_cmp.startswith(search)
        b_has_prefix = b.nickname_cmp.startswith(search)

        if a_has_prefix is b_has_prefix:
            return locale.strcoll(a.nickname, b.nickname)

        return -1 if a_has_prefix else 1

    @staticmethod
    def _generate_suggestions(
        contact: GroupchatContact,
    ) -> list[NicknameCompletionListItem]:
        # Get recent nicknames from DB. This enables us to suggest
        # nicknames even if the user is not joined
        recent_participants = map(
            contact.get_resource,
            app.storage.archive.get_recent_muc_nicks(contact.account, contact.jid),
        )
        current_participants = contact.get_participants()
        offline_members = contact.get_offline_members()

        suggestions = itertools.chain(
            recent_participants, current_participants, offline_members
        )
        scale = app.window.get_scale_factor()
        # Use set() for deduplication
        return [NicknameCompletionListItem(c, scale) for c in set(suggestions)]

    def _on_items_changed(self, *args: Any) -> None:
        idle_add_once(self.emit, "suggestions-changed")

    def _on_message_received(self, event: MessageReceived) -> None:
        if self._contact is None:
            return

        if event.jid != self._contact.jid:
            return

        # This will trigger generating new suggestions
        self._contact = None
