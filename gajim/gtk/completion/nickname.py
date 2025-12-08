# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Final

import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.events import MessageReceived
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem

log = logging.getLogger("gajim.gtk.completion.nickname")


MAX_COMPLETION_ENTRIES = 10


class NicknameCompletionListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "NicknameCompletionListItem"

    nickname = GObject.Property(type=str)
    avatar = GObject.Property(type=Gdk.Texture)

    def get_text(self) -> str:
        return f"{self.nickname}{app.settings.get('gc_refer_to_nick_char')} "


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
    name = _("Participants")

    def __init__(self) -> None:
        self._list_store = Gio.ListStore(item_type=NicknameCompletionListItem)
        self._contact: GroupchatContact | None = None

        app.ged.register_event_handler(
            "message-received", ged.GUI2, self._on_message_received
        )

        expression = Gtk.PropertyExpression.new(
            NicknameCompletionListItem, None, "nickname"
        )

        self._string_filter = Gtk.StringFilter(expression=expression)

        filter_model = Gtk.FilterListModel(
            model=self._list_store, filter=self._string_filter
        )
        self._model = Gtk.SliceListModel(
            model=filter_model, size=MAX_COMPLETION_ENTRIES
        )

    def get_model(self) -> tuple[Gio.ListModel, type[NicknameCompletionViewItem]]:
        return self._model, NicknameCompletionViewItem

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        return candidate.startswith(self.trigger_char)

    def populate(self, candidate: str, contact: Any) -> bool:
        if not isinstance(contact, GroupchatContact):
            return False

        scale = app.window.get_scale_factor()
        if self._contact is not contact:
            # New contact, regenerate suggestions
            self._list_store.remove_all()
            for suggested_contact in self._generate_suggestions(contact):
                self._list_store.append(
                    NicknameCompletionListItem(
                        nickname=suggested_contact.name,
                        avatar=suggested_contact.get_avatar(
                            AvatarSize.SMALL, scale, add_show=False
                        ),
                    )
                )
            self._contact = contact

        candidate = candidate.lstrip(self.trigger_char)
        self._string_filter.set_search(candidate)
        return self._model.get_n_items() > 0

    def _generate_suggestions(
        self, contact: GroupchatContact
    ) -> list[GroupchatParticipant]:
        # Get recent nicknames from DB. This enables us to suggest
        # nicknames even if no message arrived since Gajim was started.
        recent_participants = list(
            map(
                contact.get_resource,
                app.storage.archive.get_recent_muc_nicks(contact.account, contact.jid),
            )
        )

        current_participants = list(contact.get_participants())
        current_participants.sort(key=lambda c: c.name.lower())

        suggestions = recent_participants + current_participants
        # deduplicate
        return list(dict.fromkeys(suggestions))

    def _on_message_received(self, event: MessageReceived) -> None:
        if self._contact is None:
            return

        if event.jid != self._contact.jid:
            return

        # This will trigger generating new suggestions
        self._contact = None
