# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Generic
from typing import TypeVar

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk


class BaseCompletionListItem:

    def get_text(self) -> str:
        raise NotImplementedError


L = TypeVar("L", bound=BaseCompletionListItem)


class BaseCompletionViewItem(Generic[L]):

    css_class = ""

    def __init__(self) -> None:
        self._bindings: list[GObject.Binding] = []

    def bind(self, obj: L) -> None:
        raise NotImplementedError

    def unbind(self) -> None:
        raise NotImplementedError

    def do_unroot(self) -> None:
        raise NotImplementedError


class BaseCompletionProvider:

    trigger_char = ""
    name = ""

    def get_model(self) -> tuple[Gio.ListModel, type[BaseCompletionViewItem[Any]]]:
        raise NotImplementedError

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        raise NotImplementedError

    def populate(self, candidate: str, contact: Any) -> bool:
        raise NotImplementedError
