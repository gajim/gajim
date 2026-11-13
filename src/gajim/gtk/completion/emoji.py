# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Final

import locale
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.emoji import EmojiData
from gajim.common.helpers import idle_add_once
from gajim.common.i18n import _

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

MAX_COMPLETION_ENTRIES = 12

log = logging.getLogger("gajim.gtk.completion.emoji")


class EmojiCompletionListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "EmojiCompletionListItem"

    emoji = GObject.Property(type=str)
    name = GObject.Property(type=str)
    search = GObject.Property(type=str)
    has_skin_variation = GObject.Property(type=bool, default=False)
    var1 = GObject.Property(type=str, default="")
    var2 = GObject.Property(type=str, default="")
    var3 = GObject.Property(type=str, default="")
    var4 = GObject.Property(type=str, default="")
    var5 = GObject.Property(type=str, default="")

    def get_text(self) -> str:
        return self.emoji


@Gtk.Template(string=get_ui_string("emoji_completion_view_item.ui"))
class EmojiCompletionViewItem(
    BaseCompletionViewItem[EmojiCompletionListItem], Gtk.Stack, SignalManager
):
    __gtype_name__ = "EmojiCompletionViewItem"
    css_class = "emoji-completion"

    _emoji_label: Gtk.Label = Gtk.Template.Child()
    _short_name_label: Gtk.Label = Gtk.Template.Child()
    _var1_button: Gtk.Button = Gtk.Template.Child()
    _var2_button: Gtk.Button = Gtk.Template.Child()
    _var3_button: Gtk.Button = Gtk.Template.Child()
    _var4_button: Gtk.Button = Gtk.Template.Child()
    _var5_button: Gtk.Button = Gtk.Template.Child()

    has_skin_variation = GObject.Property(type=bool, default=False)

    def __init__(self) -> None:
        super().__init__()
        Gtk.Stack.__init__(self)
        SignalManager.__init__(self)

        controller = Gtk.GestureClick(
            button=Gdk.BUTTON_SECONDARY, propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(controller, "pressed", self._on_button_press)
        self.add_controller(controller)

        self._connect(self._var1_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var2_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var3_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var4_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var5_button, "clicked", self._on_var_button_clicked)

    def _on_button_press(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        if not self.props.has_skin_variation:  # type: ignore
            return

        gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)
        self.set_visible_child_name("variations")

    def _on_var_button_clicked(self, button: Gtk.Button) -> None:
        emoji = button.get_label()
        view = cast(Gtk.Widget, self.get_parent().get_parent())  # type: ignore
        view.emit("extended-activate", emoji)

    def bind(self, obj: EmojiCompletionListItem) -> None:
        bind_spec = [
            ("has_skin_variation", self, "has_skin_variation"),
            ("emoji", self._emoji_label, "label"),
            ("name", self._short_name_label, "label"),
            ("var1", self._var1_button, "label"),
            ("var2", self._var2_button, "label"),
            ("var3", self._var3_button, "label"),
            ("var4", self._var4_button, "label"),
            ("var5", self._var5_button, "label"),
        ]

        for source_prop, widget, target_prop in bind_spec:
            bind = obj.bind_property(
                source_prop, widget, target_prop, GObject.BindingFlags.SYNC_CREATE
            )
            self._bindings.append(bind)

    def unbind(self) -> None:
        self.set_visible_child_name("emoji")
        for bind in self._bindings:
            bind.unbind()
        self._bindings.clear()

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Stack.do_unroot(self)
        app.check_finalize(self)


class EmojiCompletionProvider(BaseCompletionProvider):
    trigger_char: Final = ":"
    id: Final = "emoji"
    name = _("Emojis")

    def __init__(self) -> None:
        BaseCompletionProvider.__init__(self)
        self._load_complete = False
        self._list_store = Gio.ListStore(item_type=EmojiCompletionListItem)

        expression = Gtk.PropertyExpression.new(EmojiCompletionListItem, None, "search")
        self._string_filter = Gtk.StringFilter(expression=expression)
        self._filter_model = Gtk.FilterListModel(filter=self._string_filter)

        sorter = Gtk.CustomSorter()
        sorter.set_sort_func(self._sort_func, self._string_filter)  # type: ignore
        sort_model = Gtk.SortListModel(model=self._filter_model, sorter=sorter)

        self._model = Gtk.SliceListModel(model=sort_model, size=MAX_COMPLETION_ENTRIES)
        self._model.connect("items-changed", self._on_items_changed)

    def get_model(
        self,
    ) -> tuple[Gio.ListModel[EmojiCompletionListItem], type[EmojiCompletionViewItem]]:
        return self._model, EmojiCompletionViewItem

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        return candidate.startswith(self.trigger_char)

    @staticmethod
    def _sort_func(
        a: EmojiCompletionListItem,
        b: EmojiCompletionListItem,
        string_filter: Gtk.StringFilter,
    ) -> int:
        search = string_filter.get_search()

        a_has_prefix = a.search.startswith(search)
        b_has_prefix = b.search.startswith(search)

        if a_has_prefix is b_has_prefix:
            return locale.strcoll(a.search, b.search)

        return -1 if a_has_prefix else 1

    @staticmethod
    def _load_model_data() -> list[EmojiCompletionListItem]:
        items: list[EmojiCompletionListItem] = []

        for sequence, emoji in EmojiData:
            if isinstance(emoji, str):
                continue

            u_mod_sequences: dict[str, str] = {}
            if variations := emoji.skin_tone_variations:
                for index, var_sequence in enumerate(variations, start=1):
                    u_mod_sequences[f"var{index}"] = var_sequence

            item = EmojiCompletionListItem(
                emoji=sequence,
                name=f":{emoji.trans_short_name}:",
                search=f"{emoji.trans_short_name}|{emoji.short_name}|{'|'.join(emoji.trans_keywords)}",
                has_skin_variation=bool(emoji.skin_tone_variations),
                **u_mod_sequences,
            )
            items.append(item)

        return items

    def populate(self, candidate: str, contact: Any) -> bool:
        candidate = candidate.lstrip(self.trigger_char)
        if len(candidate) < 2:
            # Don't activate until a sufficient # of chars have been typed,
            # which is chosen to be > 1 to not interfere with ASCII smilies
            # consisting of a colon and 1 single other char.
            return False

        if not app.settings.get("enable_emoji_shortcodes"):
            return False

        self._string_filter.set_search(candidate.casefold())

        if not self._load_complete:
            self._list_store.splice(0, 0, self._load_model_data())
            self._filter_model.set_model(self._list_store)
            self._load_complete = True

        return self._model.get_n_items() > 0

    def _on_items_changed(self, *args: Any) -> None:
        idle_add_once(self.emit, "suggestions-changed")
