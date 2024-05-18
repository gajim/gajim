# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import NamedTuple
from typing import TYPE_CHECKING

import datetime as dt
import logging
from collections import defaultdict

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection

if TYPE_CHECKING:
    from gajim.gtk.conversation.rows.message import MessageRow

MAX_VISIBLE_REACTIONS = 5
MAX_TOTAL_REACTIONS = 25
MAX_USERS = 25

log = logging.getLogger('gajim.gtk.conversation.reactions_bar')


class ReactionData(NamedTuple):
    username: str
    timestamp: dt.datetime
    from_us: bool


class ReactionsBar(Gtk.Box):
    def __init__(self, message_row: MessageRow, contact: types.ChatContactT) -> None:
        Gtk.Box.__init__(self, spacing=3, no_show_all=True)
        self._message_row = message_row
        self._contact = contact

        self._reactions: list[mod.Reaction] = []

    def _aggregate_reactions(
        self, reactions: list[mod.Reaction]
    ) -> dict[str, list[ReactionData]]:
        aggregated_reactions: dict[str, list[ReactionData]] = defaultdict(list)
        for reaction in reactions:
            if not reaction.emojis:
                continue

            if reaction.direction == ChatDirection.OUTGOING:
                username = _('Me')
            else:
                if isinstance(self._contact, BareContact):
                    username = self._contact.name
                else:
                    if reaction.occupant is None or reaction.occupant.nickname is None:
                        log.debug('Ignoring MUC reaction without occupant')
                        continue
                    username = reaction.occupant.nickname

            for emoji in reaction.emojis.split(';'):
                aggregated_reactions[emoji].append(
                    ReactionData(
                        username=username,
                        timestamp=reaction.timestamp,
                        from_us=reaction.direction == ChatDirection.OUTGOING,
                    )
                )

        return aggregated_reactions

    def get_our_reactions(self) -> set[str]:
        our_reactions: set[str] = set()
        for reaction in self._reactions:
            if reaction.direction == ChatDirection.OUTGOING:
                our_reactions = set(reaction.emojis.split(';'))
                break

        return our_reactions

    def _on_reaction_clicked(self, reaction_button: ReactionButton) -> None:
        self._message_row.send_reaction(reaction_button.emoji)

    def _on_emoji_added(self, _widget: AddReactionButton, emoji: str) -> None:
        self._message_row.send_reaction(emoji)

    def update_from_reactions(self, reactions: list[mod.Reaction]) -> None:
        for widget in self.get_children():
            widget.destroy()

        self._reactions = reactions

        aggregated_reactions = self._aggregate_reactions(reactions)
        if not aggregated_reactions:
            self.set_no_show_all(True)
            self.hide()
            return

        more_reactions_button = None
        for index, (emoji, data) in enumerate(aggregated_reactions.items()):
            reaction_button = ReactionButton(emoji, data)
            reaction_button.connect('clicked', self._on_reaction_clicked)
            if index + 1 <= MAX_VISIBLE_REACTIONS:
                self.add(reaction_button)
            elif index + 1 > MAX_VISIBLE_REACTIONS and index + 1 <= MAX_TOTAL_REACTIONS:
                if more_reactions_button is None:
                    more_reactions_button = MoreReactionsButton()
                    self.add(more_reactions_button)
                more_reactions_button.add_reaction(reaction_button)
            else:
                log.debug('Too many reactions: %s', len(aggregated_reactions))
                break

        add_reaction_button = AddReactionButton()
        add_reaction_button.get_style_context().add_class('reaction')
        add_reaction_button.get_style_context().add_class('flat')
        add_reaction_button.connect('emoji-added', self._on_emoji_added)
        self.add(add_reaction_button)

        self.set_no_show_all(False)
        self.show_all()


class ReactionButton(Gtk.Button):
    def __init__(self, emoji: str, reaction_data: list[ReactionData]) -> None:
        Gtk.Button.__init__(self)
        self.emoji = emoji

        format_string = app.settings.get('date_time_format')
        tooltip_markup = f'<span size="200%">{emoji}</span>\n'

        self.from_us = False
        for reaction in reaction_data[:MAX_USERS]:
            if reaction.from_us:
                self.from_us = True
            tooltip_markup += (
                f'{reaction.username} ({reaction.timestamp.strftime(format_string)})\n'
            )
        if len(reaction_data) > MAX_USERS:
            tooltip_markup += _('And more...')

        self.set_tooltip_markup(tooltip_markup.strip())

        self.get_style_context().add_class('flat')
        self.get_style_context().add_class('reaction')
        if self.from_us:
            self.get_style_context().add_class('reaction-from-us')

        emoji_label = Gtk.Label(label=emoji)
        count_label = Gtk.Label(label=str(len(reaction_data)))
        count_label.get_style_context().add_class('monospace')

        self._box = Gtk.Box(spacing=3)
        self._box.add(emoji_label)
        self._box.add(count_label)
        self.add(self._box)

        self.show_all()


class MoreReactionsButton(Gtk.MenuButton):
    def __init__(self) -> None:
        Gtk.MenuButton.__init__(self, tooltip_text=_('Show all reactions'))
        self.get_style_context().add_class('flat')
        self.get_style_context().add_class('reaction')

        self._flow_box = Gtk.FlowBox(
            row_spacing=3,
            column_spacing=3,
            selection_mode=Gtk.SelectionMode.NONE,
            min_children_per_line=3,
            max_children_per_line=3,
        )
        self._flow_box.get_style_context().add_class('padding-6')

        popover = Gtk.Popover()
        popover.add(self._flow_box)
        self.set_popover(popover)

        self.show_all()

    def add_reaction(self, reaction_button: ReactionButton) -> None:
        self._flow_box.add(reaction_button)
        self._flow_box.show_all()


class AddReactionButton(Gtk.Button):

    __gsignals__ = {
        'emoji-added': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self) -> None:
        Gtk.Button.__init__(self, tooltip_text=_('Add reaction'))
        icon = Gtk.Image.new_from_icon_name(
            'lucide-smile-plus-symbolic', Gtk.IconSize.BUTTON
        )
        self._dummy_entry = Gtk.Entry(
            width_chars=0,
            editable=True,
            no_show_all=True,
        )
        self._dummy_entry.get_style_context().add_class('flat')
        self._dummy_entry.get_style_context().add_class('dummy-emoji-entry')
        self._dummy_entry.connect('changed', self._on_changed)

        box = Gtk.Box()
        box.add(icon)
        box.add(self._dummy_entry)
        self.add(box)
        self.set_tooltip_text(_('Add Reaction…'))

        # Use connect_after to allow other widgets to connect beforehand
        self.connect_after('clicked', self._on_clicked)

        self.show_all()

    def _on_clicked(self, _button: Gtk.Button) -> None:
        self._dummy_entry.set_text('')
        self._dummy_entry.show()
        self._dummy_entry.emit('insert-emoji')

    def _on_changed(self, entry: Gtk.Entry) -> None:
        entry.hide()
        if not entry.get_text():
            return

        emoji = entry.get_text()
        entry.set_text('')
        self.emit('emoji-added', emoji)
