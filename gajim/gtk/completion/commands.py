# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Final

import logging

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem

log = logging.getLogger("gajim.gtk.completion.commands")


MAX_COMPLETION_ENTRIES = 10


class CommandsCompletionListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "CommandsCompletionListItem"

    command = GObject.Property(type=str)
    usage = GObject.Property(type=str)

    def get_text(self) -> str:
        return f"/{self.command} "


class CommandsCompletionViewItem(
    BaseCompletionViewItem[CommandsCompletionListItem], Gtk.Box
):
    __gtype_name__ = "CommandsCompletionViewItem"
    css_class = "command-completion"

    def __init__(self) -> None:
        super().__init__()
        Gtk.Box.__init__(self)

        self._label = Gtk.Label()

        self.append(self._label)

    def bind(self, obj: CommandsCompletionListItem) -> None:
        bind_spec = [
            ("usage", self._label, "label"),
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


class CommandsCompletionProvider(BaseCompletionProvider):

    trigger_char: Final = "/"
    name = _("Commands")

    def __init__(self) -> None:
        self._list_store = Gio.ListStore(item_type=CommandsCompletionListItem)

        for command, usage in app.commands.get_commands("chat"):  # TODO
            self._list_store.append(
                CommandsCompletionListItem(command=command, usage=f"/{command} {usage}")
            )

        expression = Gtk.PropertyExpression.new(
            CommandsCompletionListItem, None, "command"
        )

        self._string_filter = Gtk.StringFilter(expression=expression)

        filter_model = Gtk.FilterListModel(
            model=self._list_store, filter=self._string_filter
        )
        self._model = Gtk.SliceListModel(
            model=filter_model, size=MAX_COMPLETION_ENTRIES
        )

    def get_model(self) -> tuple[Gio.ListModel, type[CommandsCompletionViewItem]]:
        return self._model, CommandsCompletionViewItem

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        if not candidate.startswith(self.trigger_char) or candidate.startswith(
            self.trigger_char, 1, 2
        ):
            # Check for '/' at the beginning, but ignore '//'
            return False

        return start_iter.get_offset() == 0

    def populate(self, candidate: str, contact: Any) -> bool:
        candidate = candidate.lstrip(self.trigger_char)
        self._string_filter.set_search(candidate)
        return self._model.get_n_items() > 0
