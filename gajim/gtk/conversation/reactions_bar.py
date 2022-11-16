# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import NamedTuple

import time
from datetime import datetime

from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

MAX_VISIBLE_REACTIONS = 3


class ReactionData(NamedTuple):
    emoji: str
    users: list[tuple[types.ChatContactT, float]]


class ReactionsBar(Gtk.Box):
    def __init__(self,
                 contact: types.ChatContactT,
                 message_id: str,
                 new_reaction: bool
                 ) -> None:

        Gtk.Box.__init__(self, spacing=3)

        self._contact = contact
        self._message_id = message_id

        if new_reaction:
            self.add(AddReaction(
                self._contact, self._message_id, new_reaction=True))
            self.show_all()
            return

        # TODO: remove
        self._add_dummy_data()

    def set_reactions(self, reactions: list[ReactionData]) -> None:
        for reaction in reactions:
            reaction_widget = Reaction(
                self._contact, self._message_id, reaction)
            self.add(reaction_widget)
            if reactions.index(reaction) + 1 >= MAX_VISIBLE_REACTIONS:
                break

        if len(reactions) > MAX_VISIBLE_REACTIONS:
            more_reactions_button = MoreReactionsButton(
                self._contact, self._message_id, reactions)
            self.add(more_reactions_button)

        self.add(AddReaction(self._contact, self._message_id))
        self.show_all()

    def _add_dummy_data(self) -> None:
        # TODO: remove
        reactions_list: list[ReactionData] = []
        client = app.get_client(self._contact.account)
        contact1 = client.get_module('Contacts').get_contact(
            'heinrich@test')
        contact2 = client.get_module('Contacts').get_contact(
            'igor@test')
        contact3 = client.get_module('Contacts').get_contact(
            'romeo@test')

        timestamp = time.time()
        data1 = ReactionData(
            emoji='🤘️',
            users=[(contact1, timestamp), (contact2, timestamp)])
        data2 = ReactionData(
            emoji='🚀️',
            users=[(contact3, timestamp)])
        data3 = ReactionData(
            emoji='🙉️',
            users=[(contact2, timestamp)])
        reactions_list.append(data1)
        reactions_list.append(data2)
        reactions_list.append(data3)
        self.set_reactions(reactions_list)


class Reaction(Gtk.Button):
    def __init__(self,
                 contact: types.ChatContactT,
                 message_id: str,
                 reaction: ReactionData
                 ) -> None:

        Gtk.Button.__init__(self)
        self.get_style_context().add_class('flat')
        self.get_style_context().add_class('reaction')

        self._contact = contact
        self._message_id = message_id
        self._reaction = reaction

        if isinstance(contact, GroupchatContact):
            self_contact = contact.get_self()
        else:
            client = app.get_client(contact.account)
            self_contact = client.get_module('Contacts').get_contact(
                client.get_own_jid().bare)

        if self_contact in reaction.users[0]:
            self.get_style_context().add_class('reaction-from-us')

        emoji_label = Gtk.Label(label=reaction.emoji)
        count_label = Gtk.Label(label=str(len(reaction.users)))
        count_label.get_style_context().add_class('small')
        count_label.get_style_context().add_class('monospace')

        self._box = Gtk.Box(spacing=3)
        self._box.add(emoji_label)
        self._box.add(count_label)
        self.add(self._box)

        format_string = app.settings.get('date_time_format')
        tooltip_text = ''
        for user, timestamp in reaction.users:
            date_time = datetime.utcfromtimestamp(timestamp)
            timestamp_formatted = date_time.strftime(format_string)
            tooltip_text += f'{user.name} ({timestamp_formatted})\n'
        self.set_tooltip_text(tooltip_text.strip())

        self.connect('clicked',
                     self._on_clicked,
                     self_contact in reaction.users)

        self.show_all()

    def _on_clicked(self, _button: Gtk.Button, from_us: bool) -> None:
        if from_us:
            # TODO: Remove reaction of type self._reaction
            return

        # TODO: Add reaction of type self._reaction


class MoreReactionsButton(Gtk.MenuButton):
    def __init__(self,
                 contact: types.ChatContactT,
                 message_id: str,
                 reactions: list[ReactionData]
                 ) -> None:

        Gtk.MenuButton.__init__(self)
        self.get_style_context().add_class('flat')
        self.get_style_context().add_class('reaction')

        box = Gtk.FlowBox()
        box.set_row_spacing(3)
        box.set_column_spacing(3)
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        box.set_min_children_per_line(3)
        box.set_max_children_per_line(3)
        box.get_style_context().add_class('padding-6')

        for reaction in reactions[MAX_VISIBLE_REACTIONS:]:
            reaction_widget = Reaction(contact, message_id, reaction)
            box.add(reaction_widget)

        box.show_all()

        popover = Gtk.Popover()
        popover.add(box)
        self.set_popover(popover)


class AddReaction(Gtk.Button):
    def __init__(self,
                 contact: types.ChatContactT,
                 message_id: str,
                 new_reaction: bool = False
                 ) -> None:

        Gtk.Button.__init__(self)
        self.get_style_context().add_class('reaction')
        self.get_style_context().add_class('flat')

        self._contact = contact
        self._message_id = message_id

        icon = Gtk.Image.new_from_icon_name(
            'list-add-symbolic', Gtk.IconSize.BUTTON)
        self._dummy_entry = Gtk.Entry()
        self._dummy_entry.set_width_chars(0)
        self._dummy_entry.set_editable(True)
        self._dummy_entry.set_no_show_all(True)
        self._dummy_entry.get_style_context().add_class('flat')
        self._dummy_entry.get_style_context().add_class('reaction-dummy-entry')
        self._dummy_entry.connect('changed', self._on_changed)

        box = Gtk.Box()
        box.add(icon)
        box.add(self._dummy_entry)
        self.add(box)
        self.set_tooltip_text(_('Add Reaction…'))

        self.connect('clicked', self._on_clicked)

        if new_reaction:
            self._dummy_entry.show()
            self._dummy_entry.emit('insert-emoji')

    def _on_clicked(self, _button: Gtk.Button) -> None:
        self._dummy_entry.show()
        self._dummy_entry.emit('insert-emoji')

    def _on_changed(self, entry: Gtk.Entry) -> None:
        if not entry.get_text():
            return

        self._dummy_entry.hide()
        emoji = self._dummy_entry.get_text()
        entry.set_text('')

        print(f'Reaction to {self._contact.jid} ({self._message_id}): {emoji}')
        # TODO: Add reaction of type 'emoji'
