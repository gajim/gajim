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

from typing import Any
from typing import Optional

import locale
import logging
from enum import IntEnum

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.const import Affiliation

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr
from gajim.common.events import ApplicationEvent
from gajim.common.events import MUCNicknameChanged
from gajim.common.helpers import get_uf_affiliation
from gajim.common.helpers import get_uf_role
from gajim.common.helpers import jid_is_blocked
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_groupchat_participant_menu
from gajim.gtk.tooltips import GCTooltip
from gajim.gtk.util import EventHelper
from gajim.gtk.util import GajimPopover

log = logging.getLogger('gajim.gtk.groupchat_roster')


AffiliationRoleSortOrder = {
    'owner': 0,
    'admin': 1,
    'moderator': 2,
    'participant': 3,
    'visitor': 4
}


class Column(IntEnum):
    AVATAR = 0
    TEXT = 1
    IS_CONTACT = 2
    NICK_OR_GROUP = 3


CONTACT_SIGNALS = {
    'user-affiliation-changed',
    'user-avatar-update',
    'user-joined',
    'user-left',
    'user-nickname-changed',
    'user-role-changed',
    'user-status-show-changed',
}


class GroupchatRoster(Gtk.Revealer, EventHelper):
    def __init__(self) -> None:
        Gtk.Revealer.__init__(self)
        EventHelper.__init__(self)

        self._contact = None

        self._tooltip = GCTooltip()

        self._ui = get_builder('groupchat_roster.ui')
        self.add(self._ui.box)

        self._contact_refs: dict[str, Gtk.TreeRowReference] = {}
        self._group_refs: dict[str, Gtk.TreeRowReference] = {}

        self._store = self._ui.participant_store
        self._store.set_sort_func(Column.TEXT, self._tree_compare_iters)

        self._roster = self._ui.roster_treeview

        self._filter_string = ''
        self._modelfilter = self._store.filter_new()
        self._modelfilter.set_visible_func(self._visible_func)
        self._roster.set_has_tooltip(True)

        self._ui.contact_column.set_fixed_width(
            app.settings.get('groupchat_roster_width'))
        self._ui.contact_column.set_cell_data_func(self._ui.text_renderer,
                                                   self._text_cell_data_func)

        self._ui.connect_signals(self)

        app.settings.connect_signal(
            'hide_groupchat_occupants_list', self._hide_roster)

        self.register_events([
            ('theme-update', ged.GUI2, self._on_theme_update),
        ])

        self.set_reveal_child(
            not app.settings.get('hide_groupchat_occupants_list'))

        self.connect('notify::reveal-child', self._on_reveal)

    def _hide_roster(self, hide_roster: bool, *args: Any) -> None:
        transition = Gtk.RevealerTransitionType.SLIDE_RIGHT
        if not hide_roster:
            self.show_all()
            transition = Gtk.RevealerTransitionType.SLIDE_LEFT

        self.set_transition_type(transition)
        self.set_reveal_child(not hide_roster)
        self.set_visible(not hide_roster)

    def _on_reveal(self, revealer: Gtk.Revealer, param: Any) -> None:
        if revealer.get_reveal_child():
            self._load_roster()
        else:
            self._unload_roster()

    def clear(self) -> None:
        if self._contact is None:
            return

        log.info('Clear')
        self._unload_roster()
        self._contact.disconnect_signal(self, 'state-changed')
        self._contact = None

    def switch_contact(self, contact: types.ChatContactT) -> None:
        if self._contact is not None:
            self.clear()

        is_groupchat = isinstance(contact, GroupchatContact)
        hide_roster = app.settings.get('hide_groupchat_occupants_list')
        self.set_visible(is_groupchat and not hide_roster)
        if not is_groupchat:
            return

        log.info('Switch to %s (%s)', contact.jid, contact.account)

        contact.connect('state-changed', self._on_muc_state_changed)

        self._contact = contact

        if self._contact.is_joined:
            self._load_roster()

    @staticmethod
    def _on_focus_out(treeview: Gtk.TreeView, _param: Gdk.EventFocus) -> None:
        treeview.get_selection().unselect_all()

    def _query_tooltip(self,
                       widget: Gtk.Widget,
                       x_pos: int,
                       y_pos: int,
                       _keyboard_mode: bool,
                       tooltip: Gtk.Tooltip
                       ) -> bool:

        row = self._roster.get_path_at_pos(x_pos, y_pos)
        if row is None:
            self._tooltip.clear_tooltip()
            return False

        path, _, _, _ = row
        if path is None:
            self._tooltip.clear_tooltip()
            return False

        iter_ = None
        try:
            iter_ = self._store.get_iter(path)
        except Exception:
            self._tooltip.clear_tooltip()
            return False

        if not self._store[iter_][Column.IS_CONTACT]:
            self._tooltip.clear_tooltip()
            return False

        nickname = self._store[iter_][Column.NICK_OR_GROUP]

        assert self._contact is not None
        contact = self._contact.get_resource(nickname)

        value, widget = self._tooltip.get_tooltip(contact)
        tooltip.set_custom(widget)
        return value

    def _on_search_changed(self, widget: Gtk.SearchEntry) -> None:
        self._filter_string = widget.get_text().lower()
        self._modelfilter.refilter()
        self._roster.expand_all()

    def _visible_func(self,
                      model: Gtk.TreeModelFilter,
                      iter_: Gtk.TreeIter,
                      *_data: Any
                      ) -> bool:

        if not self._filter_string:
            return True

        if not model[iter_][Column.IS_CONTACT]:
            return True

        return self._filter_string in model[iter_][Column.TEXT].lower()

    def _get_group_iter(self, group_name: str) -> Optional[Gtk.TreeIter]:
        try:
            ref = self._group_refs[group_name]
        except KeyError:
            return None

        path = ref.get_path()
        if path is None:
            return None
        return self._store.get_iter(path)

    def _get_contact_iter(self, nick: str) -> Optional[Gtk.TreeIter]:
        try:
            ref = self._contact_refs[nick]
        except KeyError:
            return None

        path = ref.get_path()
        if path is None:
            return None
        return self._store.get_iter(path)

    def _on_user_joined(self,
                        _contact: types.GroupchatContact,
                        _signal_name: str,
                        user_contact: types.GroupchatParticipant,
                        *args: Any
                        ) -> None:
        self._add_contact(user_contact)

    def _add_contact(self, contact: types.GroupchatParticipant) -> None:
        group_name, group_text = self._get_group_from_contact(contact)
        nick = contact.name

        # Create Group
        group_iter = self._get_group_iter(group_name)
        role_path = None
        if not group_iter:
            group_iter = self._store.append(
                None, [None, group_text, False, group_name])
            role_path = self._store.get_path(group_iter)
            group_ref = Gtk.TreeRowReference(self._store, role_path)
            self._group_refs[group_name] = group_ref

        # Avatar
        surface = contact.get_avatar(AvatarSize.ROSTER,
                                     self.get_scale_factor())

        iter_ = self._store.append(group_iter,
                                   [surface, nick, True, nick])
        self._contact_refs[nick] = Gtk.TreeRowReference(
            self._store, self._store.get_path(iter_))

        self._draw_groups()
        self._draw_contact(nick)

        if (role_path is not None and
                self._roster.get_model() is not None):
            self._roster.expand_row(role_path, False)

    def _on_user_left(self,
                      _contact: types.GroupchatContact,
                      _signal_name: str,
                      user_contact: types.GroupchatParticipant,
                      *args: Any
                      ) -> None:

        self._remove_contact(user_contact)
        self._draw_groups()

    def _update_contact(self,
                        _contact: types.GroupchatContact,
                        _signal_name: str,
                        user_contact: types.GroupchatParticipant,
                        *args: Any
                        ) -> None:

        self._remove_contact(user_contact)
        self._add_contact(user_contact)

    def _on_user_nickname_changed(self,
                                  _contact: types.GroupchatContact,
                                  _signal_name: str,
                                  _event: MUCNicknameChanged,
                                  old_contact: types.GroupchatParticipant,
                                  new_contact: types.GroupchatParticipant
                                  ) -> None:

        self._remove_contact(old_contact)
        self._add_contact(new_contact)

    def _on_user_status_show_changed(self,
                                     _contact: types.GroupchatContact,
                                     _signal_name: str,
                                     user_contact: types.GroupchatParticipant,
                                     *args: Any
                                     ) -> None:

        self._draw_contact(user_contact.name)

    def _remove_contact(self, contact: types.GroupchatParticipant) -> None:
        nick = contact.name
        iter_ = self._get_contact_iter(nick)
        if not iter_:
            return

        group_iter = self._store.iter_parent(iter_)
        if group_iter is None:
            raise ValueError('Trying to remove non-child')

        self._store.remove(iter_)
        del self._contact_refs[nick]
        if not self._store.iter_has_child(group_iter):
            group = self._store[group_iter][Column.NICK_OR_GROUP]
            del self._group_refs[group]
            self._store.remove(group_iter)

    @staticmethod
    def _get_group_from_contact(contact: types.GroupchatParticipant
                                ) -> tuple[str, str]:
        if contact.affiliation in (Affiliation.OWNER, Affiliation.ADMIN):
            return contact.affiliation.value, get_uf_affiliation(
                contact.affiliation, plural=True)
        return contact.role.value, get_uf_role(contact.role, plural=True)

    @staticmethod
    def _text_cell_data_func(_column: Gtk.TreeViewColumn,
                             renderer: Gtk.CellRenderer,
                             model: Gtk.TreeModel,
                             iter_: Gtk.TreeIter,
                             _user_data: Optional[object]
                             ) -> None:

        has_parent = bool(model.iter_parent(iter_))
        style = 'contact' if has_parent else 'group'

        bgcolor = app.css_config.get_value(f'.gajim-{style}-row',
                                           StyleAttr.BACKGROUND)
        renderer.set_property('cell-background', bgcolor)

        color = app.css_config.get_value(f'.gajim-{style}-row',
                                         StyleAttr.COLOR)
        renderer.set_property('foreground', color)

        desc = app.css_config.get_font(f'.gajim-{style}-row')
        renderer.set_property('font-desc', desc)

        if not has_parent:
            renderer.set_property('weight', 600)
            renderer.set_property('ypad', 6)

    def _on_roster_row_activated(self,
                                 _treeview: Gtk.TreeView,
                                 path: Gtk.TreePath,
                                 _column: Gtk.TreeViewColumn
                                 ) -> None:

        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # This is a group row
            return

        assert self._contact is not None

        nick = self._store[iter_][Column.NICK_OR_GROUP]
        if self._contact.nickname == nick:
            return

        disco = self._contact.get_disco()
        assert disco is not None

        muc_prefer_direct_msg = app.settings.get('muc_prefer_direct_msg')
        if disco.muc_is_nonanonymous and muc_prefer_direct_msg:
            participant = self._contact.get_resource(nick)
            assert participant.real_jid is not None
            app.window.add_chat(self._contact.account,
                                participant.real_jid,
                                'contact',
                                select=True)
        else:
            contact = self._contact.get_resource(nick)
            app.window.add_private_chat(self._contact.account,
                                        contact.jid,
                                        select=True)

    def _on_roster_button_press_event(self,
                                      treeview: Gtk.TreeView,
                                      event: Gdk.EventButton
                                      ) -> None:

        if event.button == Gdk.BUTTON_PRIMARY:
            return

        pos = treeview.get_path_at_pos(int(event.x), int(event.y))
        if pos is None:
            return

        path, _, _, _ = pos
        if path is None:
            return

        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # Group row
            return

        assert self._contact is not None

        nick = self._store[iter_][Column.NICK_OR_GROUP]
        if self._contact.nickname == nick:
            return

        if event.button == Gdk.BUTTON_SECONDARY:
            self._show_contact_menu(nick, event)

        # if event.button == Gdk.BUTTON_MIDDLE:
            # self.roster.emit('row-activated', nick)

    def _show_contact_menu(self, nick: str, event: Gdk.EventButton) -> None:
        assert self._contact is not None
        self_contact = self._contact.get_self()
        assert self_contact is not None
        contact = self._contact.get_resource(nick)
        menu = get_groupchat_participant_menu(self._contact.account,
                                              self_contact,
                                              contact)

        popover = GajimPopover(menu, relative_to=self, event=event)
        popover.popup()

    def _on_muc_state_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:

        if contact.is_joined:
            self._load_roster()

        elif contact.is_not_joined:
            self._unload_roster()

    def _tree_compare_iters(self,
                            model: Gtk.TreeModel,
                            iter1: Gtk.TreeIter,
                            iter2: Gtk.TreeIter,
                            _user_data: Optional[object]
                            ) -> int:
        '''
        Compare two iterators to sort them
        '''
        is_contact = model.iter_parent(iter1)
        if is_contact:

            nick1 = model[iter1][Column.NICK_OR_GROUP]
            nick2 = model[iter2][Column.NICK_OR_GROUP]

            if not app.settings.get('sort_by_show_in_muc'):
                return locale.strcoll(nick1.lower(), nick2.lower())

            assert self._contact is not None
            contact1 = self._contact.get_resource(nick1)
            contact2 = self._contact.get_resource(nick2)

            if contact1.show != contact2.show:
                return -1 if contact1.show > contact2.show else 1

            return locale.strcoll(nick1.lower(), nick2.lower())

        # Group
        group1 = model[iter1][Column.NICK_OR_GROUP]
        group2 = model[iter2][Column.NICK_OR_GROUP]
        group1_index = AffiliationRoleSortOrder[group1]
        group2_index = AffiliationRoleSortOrder[group2]
        return -1 if group1_index < group2_index else 1

    def enable_sort(self, enable: bool) -> None:
        column = Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID
        if enable:
            column = Column.TEXT

        self._store.set_sort_column_id(column, Gtk.SortType.ASCENDING)

    def _load_roster(self) -> None:
        if not self.get_reveal_child():
            return

        log.info('Load Roster')
        assert self._contact is not None
        self._contact.multi_connect({
            'user-affiliation-changed': self._update_contact,
            'user-avatar-update': self._on_user_avatar_update,
            'user-joined': self._on_user_joined,
            'user-left': self._on_user_left,
            'user-nickname-changed': self._on_user_nickname_changed,
            'user-role-changed': self._update_contact,
            'user-status-show-changed': self._on_user_status_show_changed,
        })

        for participant in self._contact.get_participants():
            self._add_contact(participant)

        self.enable_sort(True)
        self._roster.set_model(self._modelfilter)

        self._ui.search_entry.set_text('')
        self._roster.expand_all()

    def _unload_roster(self) -> None:
        if self._roster.get_model() is None:
            return

        log.info('Unload Roster')
        assert self._contact is not None
        self._contact.multi_disconnect(self, CONTACT_SIGNALS)

        self._roster.set_model(None)
        self._store.clear()
        self.enable_sort(False)

        self._contact_refs = {}
        self._group_refs = {}

    def invalidate_sort(self) -> None:
        self.enable_sort(False)
        self.enable_sort(True)

    def _redraw(self) -> None:
        self._roster.set_model(None)
        self._roster.set_model(self._store)
        self._roster.expand_all()

    def _draw_contact(self, nick: str) -> None:
        iter_ = self._get_contact_iter(nick)
        if not iter_:
            return

        assert self._contact is not None
        contact = self._contact.get_resource(nick)

        self._draw_avatar(contact)

        name = GLib.markup_escape_text(contact.name)

        # Strike name if blocked
        fjid = f'{self._contact.jid}/{nick}'
        if jid_is_blocked(self._contact.account, fjid):
            name = f'<span strikethrough="true">{name}</span>'

        # add status msg, if not empty, under contact name
        status = contact.status.strip()
        if status and app.settings.get('show_status_msgs_in_roster'):
            # Display only first line
            status = status.split('\n', 1)[0]
            # escape markup entities and make them small italic and fg color
            name += (f'\n<span size="small" style="italic" alpha="70%">'
                     f'{GLib.markup_escape_text(status)}</span>')

        self._store[iter_][Column.TEXT] = name

    def draw_contacts(self) -> None:
        for nick in self._contact_refs:
            self._draw_contact(nick)

    def _draw_groups(self) -> None:
        for group in self._group_refs:
            self._draw_group(group)

    def _draw_group(self, group: str) -> None:
        group_iter = self._get_group_iter(group)
        if not group_iter:
            return

        if group in ('owner', 'admin'):
            group_text = get_uf_affiliation(group, plural=True)
        else:
            group_text = get_uf_role(group, plural=True)

        total_users = self._get_total_user_count()
        group_users = self._store.iter_n_children(group_iter)

        group_text += f' ({group_users}/{total_users})'

        self._store[group_iter][Column.TEXT] = group_text

    def _draw_avatar(self, contact: types.GroupchatParticipant) -> None:
        iter_ = self._get_contact_iter(contact.name)
        if iter_ is None:
            return

        surface = contact.get_avatar(AvatarSize.ROSTER,
                                     self.get_scale_factor())

        self._store[iter_][Column.AVATAR] = surface

    def _on_user_avatar_update(self,
                               _contact: types.GroupchatContact,
                               _signal_name: str,
                               user_contact: types.GroupchatParticipant
                               ) -> None:

        self._draw_avatar(user_contact)

    def _get_total_user_count(self) -> int:
        count = 0
        for group_row in self._store:
            count += self._store.iter_n_children(group_row.iter)
        return count

    def _on_theme_update(self, _event: ApplicationEvent) -> None:
        self._redraw()
