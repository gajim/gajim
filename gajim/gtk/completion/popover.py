# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource

from gajim.common.const import Direction

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem

log = logging.getLogger("gajim.gtk.chat_action_processor")


class CompletionPopover(Gtk.Popover):

    __gsignals__ = {
        "completion-picked": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str,),
        )
    }

    def __init__(self, message_input: GtkSource.View) -> None:
        Gtk.Popover.__init__(
            self,
            autohide=False,
            has_arrow=False,
            position=Gtk.PositionType.TOP,
        )
        self.add_css_class("completion-popover")
        self.set_offset(100, 0)

        self._message_input = message_input
        self._provider: BaseCompletionProvider | None = None
        self._widget_cls: type[BaseCompletionViewItem[Any]] | None = None

        controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        controller.connect("key-pressed", self._on_key_pressed)
        self._message_input.add_controller(controller)

        box = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL)

        self._view = CompletionListView(
            model=Gtk.SingleSelection(), single_click_activate=True, can_focus=False
        )
        self._view.connect("activate", self._on_item_activated)
        self._view.connect("extended-activate", self._on_extended_item_activated)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup)
        factory.connect("bind", self._on_factory_bind)
        factory.connect("unbind", self._on_factory_unbind)
        self._view.set_factory(factory)

        self._header_label = Gtk.Label(halign=Gtk.Align.START, xalign=0)
        self._header_label.add_css_class("dim-label")
        box.append(self._header_label)
        box.append(self._view)

        self.set_child(box)

    def set_provider(self, provider: BaseCompletionProvider) -> None:
        if self._provider is provider:
            return

        self._provider = provider
        model, widget_cls = self._provider.get_model()
        self._header_label.set_label(self._provider.name)
        self._widget_cls = widget_cls
        for name in self._view.get_css_classes():
            if name.endswith("-completion"):
                self._view.remove_css_class(name)
        self._view.add_css_class(widget_cls.css_class)
        selection_model = cast(Gtk.SingleSelection, self._view.get_model())
        assert selection_model is not None
        selection_model.set_model(model)

    def _on_factory_setup(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        assert self._widget_cls is not None
        list_item.set_child(self._widget_cls())  # pyright: ignore

    @staticmethod
    def _on_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = cast(BaseCompletionViewItem[Any], list_item.get_child())
        obj = list_item.get_item()
        view_item.bind(obj)

    @staticmethod
    def _on_factory_unbind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = cast(BaseCompletionViewItem[Any], list_item.get_child())
        view_item.unbind()

    def _on_item_activated(self, list_view: Gtk.ListView, position: int) -> None:
        self.popdown()
        model = cast(Gtk.SingleSelection, list_view.get_model())
        assert model is not None
        item = cast(BaseCompletionListItem, model.get_item(position))
        self.emit("completion-picked", item.get_text())

    def _on_extended_item_activated(
        self, list_view: Gtk.ListView, complete_string: str
    ) -> None:
        self.popdown()
        self.emit("completion-picked", complete_string)

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:

        if not self.get_visible():
            return Gdk.EVENT_PROPAGATE

        if keyval == Gdk.KEY_Up:
            self._select(Direction.PREV)
            return Gdk.EVENT_STOP

        if keyval == Gdk.KEY_Down:
            self._select(Direction.NEXT)
            return Gdk.EVENT_STOP

        if keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            self.popdown()
            return Gdk.EVENT_PROPAGATE

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter, Gdk.KEY_Tab):
            model = cast(Gtk.SingleSelection, self._view.get_model())
            assert model is not None
            position = model.get_selected()
            if position != Gtk.INVALID_LIST_POSITION:
                self._view.emit("activate", position)
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _select(self, direction: Direction) -> None:
        model = cast(Gtk.SingleSelection, self._view.get_model())
        assert model is not None
        selected_pos = model.get_selected()
        if selected_pos == Gtk.INVALID_LIST_POSITION:
            return

        if direction == Direction.NEXT:
            new_pos = selected_pos + 1
        else:
            new_pos = selected_pos - 1

        if not 0 <= new_pos < model.get_n_items():
            return

        model.set_selected(new_pos)


class CompletionListView(Gtk.ListView):
    __gsignals__ = {
        "extended-activate": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str,),
        )
    }
