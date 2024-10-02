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

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection

from gajim.gtk.util import iterate_children

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
        Gtk.Box.__init__(self, spacing=3, visible=False, halign=Gtk.Align.START)
        self._message_row = message_row
        self._contact = contact
        if isinstance(self._contact, GroupchatContact):
            self._contact.connect('state-changed', self._on_muc_state_changed)

        self._client = app.get_client(self._contact.account)
        self._client.connect_signal('state-changed', self._on_client_state_changed)
        self.set_sensitive(self._get_reactions_enabled())

        self._reactions: list[mod.Reaction] = []

        add_reaction_button = AddReactionButton()
        add_reaction_button.get_style_context().add_class('reaction')
        add_reaction_button.get_style_context().add_class('flat')
        add_reaction_button.connect('emoji-added', self._on_emoji_added)
        self.append(add_reaction_button)

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
                our_reactions = {
                    emoji for emoji in reaction.emojis.split(';') if emoji
                }
                break

        return our_reactions

    def _on_reaction_clicked(self, reaction_button: ReactionButton) -> None:
        self._message_row.send_reaction(reaction_button.emoji)

    def _on_emoji_added(self, _widget: AddReactionButton, emoji: str) -> None:
        self._message_row.send_reaction(emoji, toggle=False)

    def update_from_reactions(self, reactions: list[mod.Reaction]) -> None:
        for widget in iterate_children(self):
            if isinstance(widget, AddReactionButton):
                continue

            if isinstance(widget, MoreReactionsButton):
                widget.hide_popover()
                continue

            self.remove(widget)

        self._reactions = reactions

        aggregated_reactions = self._aggregate_reactions(reactions)
        if not aggregated_reactions:
            self.set_visible(False)
            self.hide()
            return

        more_reactions_button = None
        for index, (emoji, data) in enumerate(aggregated_reactions.items()):
            reaction_button = ReactionButton(emoji, data)
            reaction_button.connect('clicked', self._on_reaction_clicked)
            if index + 1 <= MAX_VISIBLE_REACTIONS:
                self.prepend(reaction_button)
            elif index + 1 > MAX_VISIBLE_REACTIONS and index + 1 <= MAX_TOTAL_REACTIONS:
                if more_reactions_button is None:
                    more_reactions_button = MoreReactionsButton()
                    self.append(more_reactions_button)
                    self.reorder_child_after(more_reactions_button, reaction_button)
                more_reactions_button.add_reaction(reaction_button)
            else:
                log.debug('Too many reactions: %s', len(aggregated_reactions))
                break

        self.show()


class ReactionButton(Gtk.Button):
    def __init__(self, emoji: str, reaction_data: list[ReactionData]) -> None:
        Gtk.Button.__init__(self)
        self.emoji = emoji

        # Add emoji presentation selector, otherwise depending on the font
        # emojis might be displayed in its text variant
        emoji_presentation_form = f'{emoji}\uFE0F'

        format_string = app.settings.get('date_time_format')
        tooltip_markup = f'<span size="200%">{emoji_presentation_form}</span>\n'

        self.from_us = False
        for reaction in reaction_data[:MAX_USERS]:
            if reaction.from_us:
                self.from_us = True

            dt_str = reaction.timestamp.astimezone().strftime(format_string)
            tooltip_markup += (f'{reaction.username} ({dt_str})\n')
        if len(reaction_data) > MAX_USERS:
            tooltip_markup += _('And more...')

        self.set_tooltip_markup(tooltip_markup.strip())

        self.get_style_context().add_class('flat')
        self.get_style_context().add_class('reaction')
        if self.from_us:
            self.get_style_context().add_class('reaction-from-us')

        emoji_label = Gtk.Label(label=emoji_presentation_form)
        count_label = Gtk.Label(label=str(len(reaction_data)))
        count_label.get_style_context().add_class('monospace')

        self._box = Gtk.Box(spacing=3)
        self._box.append(emoji_label)
        self._box.append(count_label)
        self.set_child(self._box)


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
        popover.set_child(self._flow_box)
        self.set_popover(popover)

    def hide_popover(self) -> None:
        popover = self.get_popover()
        if popover is not None:
            popover.popdown()

    def add_reaction(self, reaction_button: ReactionButton) -> None:
        self._flow_box.append(reaction_button)


class AddReactionButton(Gtk.Button):

    __gsignals__ = {
        'emoji-added': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self) -> None:
        Gtk.Button.__init__(self, tooltip_text=_('Add reaction'))
        icon = Gtk.Image.new_from_icon_name('lucide-smile-plus-symbolic')
        self._dummy_entry = Gtk.Text(
            width_chars=0,
            editable=True,
            visible=False,
            propagate_text_width=True,
            css_classes=['flat', 'dummy-emoji-entry']
        )
        self._dummy_entry.connect('insert-text', self._on_insert_text)

        box = Gtk.Box()
        box.append(icon)
        box.append(self._dummy_entry)
        self.set_child(box)
        self.set_tooltip_text(_('Add Reaction…'))

        # Use connect_after to allow other widgets to connect beforehand
        self.connect_after('clicked', self._on_clicked)

    def _on_clicked(self, _button: Gtk.Button) -> None:
        self._dummy_entry.show()
        self._dummy_entry.emit('insert-emoji')

    def _on_insert_text(
        self, entry: Gtk.Entry, text: str, _length: int, _position: int
    ) -> int:
        entry.stop_emission_by_name('insert-text')
        entry.hide()

        # Remove emoji variant selectors
        text = text.strip('\uFE0E\uFE0F')
        if text:
            self.emit('emoji-added', text)
        return 0
