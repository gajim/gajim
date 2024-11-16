# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import NamedTuple
from typing import TYPE_CHECKING

import datetime as dt
import logging
from collections import defaultdict

from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection

from gajim.gtk.emoji_chooser import EmojiChooser
from gajim.gtk.util import iterate_children
from gajim.gtk.util import SignalManager

if TYPE_CHECKING:
    from gajim.gtk.conversation.rows.message import MessageRow

MAX_VISIBLE_REACTIONS = 5
MAX_TOTAL_REACTIONS = 25
MAX_USERS = 25

log = logging.getLogger("gajim.gtk.conversation.reactions_bar")


class ReactionData(NamedTuple):
    username: str
    timestamp: dt.datetime
    from_us: bool


class ReactionsBar(Gtk.Box, SignalManager):
    def __init__(self, message_row: MessageRow, contact: types.ChatContactT) -> None:
        Gtk.Box.__init__(self, spacing=3, visible=False, halign=Gtk.Align.START)
        SignalManager.__init__(self)

        self._message_row = message_row
        self._contact = contact
        if isinstance(self._contact, GroupchatContact):
            self._contact.connect("state-changed", self._on_muc_state_changed)

        self._client = app.get_client(self._contact.account)
        self._client.connect_signal("state-changed", self._on_client_state_changed)
        self.set_sensitive(self._get_reactions_enabled())

        self._reactions: list[mod.Reaction] = []

        self._add_reaction_button = Gtk.MenuButton(
            icon_name="lucide-smile-plus-symbolic",
            tooltip_text=_("Add Reaction…"),
        )

        self._add_reaction_button.set_create_popup_func(self._on_emoji_create_popover)
        self._add_reaction_button.add_css_class("flat")
        self._add_reaction_button.add_css_class("reaction-add-show-all")

        self.append(self._add_reaction_button)

    def do_unroot(self) -> None:
        self._reactions.clear()
        self._contact.disconnect_all_from_obj(self)
        self._client.disconnect_all_from_obj(self)
        self._add_reaction_button.set_create_popup_func(None)
        del self._add_reaction_button
        del self._message_row
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _on_client_state_changed(self, *args: Any) -> None:
        self.set_sensitive(self._get_reactions_enabled())

    def _on_muc_state_changed(self, *args: Any) -> None:
        self.set_sensitive(self._get_reactions_enabled())

    def _get_reactions_enabled(self) -> bool:
        if not app.account_is_connected(self._contact.account):
            return False

        if isinstance(self._contact, GroupchatContact):
            if not self._contact.is_joined:
                return False

            self_contact = self._contact.get_self()
            assert self_contact is not None
            if self_contact.role.is_visitor:
                return False

        return True

    def _aggregate_reactions(
        self, reactions: list[mod.Reaction]
    ) -> dict[str, list[ReactionData]]:
        aggregated_reactions: dict[str, list[ReactionData]] = defaultdict(list)
        for reaction in reactions:
            if not reaction.emojis:
                continue

            if reaction.direction == ChatDirection.OUTGOING:
                username = _("Me")
            else:
                if isinstance(self._contact, BareContact):
                    username = self._contact.name
                else:
                    if reaction.occupant is None or reaction.occupant.nickname is None:
                        log.debug("Ignoring MUC reaction without occupant")
                        continue
                    username = reaction.occupant.nickname

            for emoji in reaction.emojis.split(";"):
                aggregated_reactions[emoji].append(
                    ReactionData(
                        username=username,
                        timestamp=reaction.timestamp,
                        from_us=reaction.direction == ChatDirection.OUTGOING,
                    )
                )

        # Multisort dict, first for emojis, afterwards for count
        emoji_sorted = sorted(aggregated_reactions.items())
        count_sorted = sorted(emoji_sorted, reverse=True, key=lambda tup: len(tup[1]))
        return dict(count_sorted)

    def get_our_reactions(self) -> set[str]:
        our_reactions: set[str] = set()
        for reaction in self._reactions:
            if reaction.direction == ChatDirection.OUTGOING:
                our_reactions = {emoji for emoji in reaction.emojis.split(";") if emoji}
                break

        return our_reactions

    def _on_reaction_clicked(self, reaction_button: ReactionButton) -> None:
        self._message_row.send_reaction(reaction_button.emoji)

    def _on_emoji_added(self, _widget: EmojiChooser, emoji: str) -> None:
        # Remove emoji variant selectors
        emoji = emoji.strip("\uFE0E\uFE0F")
        self._message_row.send_reaction(emoji, toggle=False)

    def update_from_reactions(self, reactions: list[mod.Reaction]) -> None:
        for widget in list(iterate_children(self)):
            if isinstance(widget, MoreReactionsButton):
                widget.hide_popover()
                self.remove(widget)
                continue

            if isinstance(widget, Gtk.MenuButton):
                continue

            self.remove(widget)

        self._reactions = reactions

        aggregated_reactions = self._aggregate_reactions(reactions)
        if not aggregated_reactions:
            self.set_visible(False)
            return

        more_reactions_button = None
        for index, (emoji, data) in enumerate(aggregated_reactions.items()):
            reaction_button = ReactionButton(emoji, data)
            self._connect(reaction_button, "clicked", self._on_reaction_clicked)
            if index + 1 <= MAX_VISIBLE_REACTIONS:
                self.prepend(reaction_button)
            elif index + 1 > MAX_VISIBLE_REACTIONS and index + 1 <= MAX_TOTAL_REACTIONS:
                if more_reactions_button is None:
                    more_reactions_button = MoreReactionsButton()
                    self.append(more_reactions_button)
                more_reactions_button.add_reaction(reaction_button)
            else:
                log.debug("Too many reactions: %s", len(aggregated_reactions))
                break

        self.show()

    def _on_emoji_create_popover(self, button: Gtk.MenuButton) -> None:
        emoji_chooser = app.window.get_emoji_chooser()
        button.set_popover(emoji_chooser)
        emoji_chooser.set_emoji_picked_func(self._on_emoji_added)


class ReactionButton(Gtk.Button):
    def __init__(self, emoji: str, reaction_data: list[ReactionData]) -> None:
        Gtk.Button.__init__(self)
        self.emoji = emoji

        # Add emoji presentation selector, otherwise depending on the font
        # emojis might be displayed in its text variant
        emoji_presentation_form = f"{emoji}\uFE0F"

        format_string = app.settings.get("date_time_format")
        tooltip_markup = f'<span size="200%">{emoji_presentation_form}</span>\n'

        self.from_us = False
        for reaction in reaction_data[:MAX_USERS]:
            if reaction.from_us:
                self.from_us = True

            dt_str = reaction.timestamp.astimezone().strftime(format_string)
            tooltip_markup += f"{reaction.username} ({dt_str})\n"
        if len(reaction_data) > MAX_USERS:
            tooltip_markup += _("And more...")

        self.set_tooltip_markup(tooltip_markup.strip())

        self.add_css_class("flat")
        self.add_css_class("reaction")
        if self.from_us:
            self.add_css_class("reaction-from-us")

        emoji_label = Gtk.Label(label=emoji_presentation_form)
        count_label = Gtk.Label(label=str(len(reaction_data)))
        count_label.add_css_class("monospace")

        self._box = Gtk.Box(spacing=3)
        self._box.append(emoji_label)
        self._box.append(count_label)
        self.set_child(self._box)


class MoreReactionsButton(Gtk.MenuButton):
    def __init__(self) -> None:
        Gtk.MenuButton.__init__(self, tooltip_text=_("Show all reactions"))
        self.add_css_class("flat")
        self.add_css_class("reaction-add-show-all")

        self._flow_box = Gtk.FlowBox(
            row_spacing=3,
            column_spacing=3,
            selection_mode=Gtk.SelectionMode.NONE,
            min_children_per_line=3,
            max_children_per_line=3,
        )
        self._flow_box.add_css_class("p-6")

        popover = Gtk.Popover()
        popover.set_child(self._flow_box)
        self.set_popover(popover)

    def hide_popover(self) -> None:
        popover = self.get_popover()
        if popover is not None:
            popover.popdown()

    def add_reaction(self, reaction_button: ReactionButton) -> None:
        self._flow_box.append(reaction_button)
