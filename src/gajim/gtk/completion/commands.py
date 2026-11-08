# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Final

import logging

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.commands import Command
from gajim.common.commands import CommandContext
from gajim.common.i18n import _
from gajim.common.types import ChatContactT

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem

log = logging.getLogger("gajim.gtk.completion.commands")


MAX_COMPLETION_ENTRIES = 10


class CommandsCompletionListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "CommandsCompletionListItem"

    name: str = GObject.Property(type=str)  # type: ignore
    context: set[CommandContext] = GObject.Property(type=object)  # type: ignore
    usage: str = GObject.Property(type=str)  # type: ignore

    def __init__(self, command: Command) -> None:
        super().__init__(
            name=command.name,
            context=command.context,
            usage=f"/{command.name} {command.usage}",
        )

    def get_text(self) -> str:
        return f"/{self.name} "


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
    id: Final = "command"
    name = _("Commands")

    def __init__(self) -> None:
        BaseCompletionProvider.__init__(self)
        self._commands_loaded = False
        self._current_context: CommandContext | None = None

        self._list_store = Gio.ListStore(item_type=CommandsCompletionListItem)

        expression = Gtk.PropertyExpression.new(
            CommandsCompletionListItem, None, "name"
        )

        multi_filter = Gtk.EveryFilter()

        self._cmd_context_filter = Gtk.CustomFilter()
        self._cmd_context_filter.set_filter_func(self._context_filter_func)  # type: ignore

        self._cmd_name_filter = Gtk.StringFilter(
            expression=expression, match_mode="prefix"
        )

        multi_filter.append(self._cmd_context_filter)
        multi_filter.append(self._cmd_name_filter)

        filter_model = Gtk.FilterListModel(model=self._list_store, filter=multi_filter)
        self._model = Gtk.SliceListModel(
            model=filter_model, size=MAX_COMPLETION_ENTRIES
        )

    def _load_commands(self) -> None:
        commands = [CommandsCompletionListItem(c) for c in app.commands.get_commands()]
        self._list_store.splice(0, 0, commands)
        self._commands_loaded = True

    def _context_filter_func(self, item: CommandsCompletionListItem) -> bool:
        return self._current_context in item.context

    def get_model(
        self,
    ) -> tuple[
        Gio.ListModel[CommandsCompletionListItem], type[CommandsCompletionViewItem]
    ]:
        return self._model, CommandsCompletionViewItem

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        if not candidate.startswith(self.trigger_char) or candidate.startswith(
            self.trigger_char, 1, 2
        ):
            # Check for '/' at the beginning, but ignore '//'
            return False

        return start_iter.get_offset() == 0

    def populate(self, candidate: str, contact: ChatContactT) -> bool:
        if not self._commands_loaded:
            self._load_commands()

        new_context = CommandContext(contact.type_string)
        if self._current_context != new_context:
            self._current_context = new_context
            self._cmd_context_filter.changed(Gtk.FilterChange.DIFFERENT)

        candidate = candidate.lstrip(self.trigger_char)
        self._cmd_name_filter.set_search(candidate)
        return self._model.get_n_items() > 0
