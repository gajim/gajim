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
from typing import cast

import locale
from enum import IntEnum

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject
from nbxmpp.const import Affiliation
from nbxmpp.structs import MessageProperties

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.helpers import get_uf_role
from gajim.common.helpers import get_uf_affiliation
from gajim.common.helpers import jid_is_blocked
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr
from gajim.common.events import ApplicationEvent
from gajim.common.modules.contacts import GroupchatContact

from .menus import get_groupchat_roster_menu
from .tooltips import GCTooltip
from .builder import get_builder
from .types import GroupchatControlType
from .util import EventHelper


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
    EVENT = 2
    IS_CONTACT = 3
    NICK_OR_GROUP = 4


class GroupchatRoster(Gtk.ScrolledWindow, EventHelper):

    __gsignals__ = {
        'row-activated': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None, # return value
            (str, )) # arguments
    }

    def __init__(self,
                 account: str,
                 room_jid: str,
                 control: GroupchatControlType
                 ) -> None:
        Gtk.ScrolledWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.get_style_context().add_class('groupchat-roster')
        self._account = account
        self.room_jid = room_jid
        self._control = control
        self._control_id = control.control_id
        self._tooltip = GCTooltip()
        self._group_chat_contact = cast(GroupchatContact, control.contact)
        self._group_chat_contact.connect(
            'user-avatar-update', self._on_user_avatar_update)
        self._group_chat_contact.connect('user-joined', self._on_user_joined)
        self._group_chat_contact.connect('user-left', self._on_user_left)
        self._group_chat_contact.connect(
            'user-affiliation-changed', self._update_contact)
        self._group_chat_contact.connect(
            'user-role-changed', self._update_contact)
        self._group_chat_contact.connect(
            'user-status-show-changed', self._on_user_status_show_changed)
        self._group_chat_contact.connect(
            'user-nickname-changed', self._on_user_nickname_changed)

        self._ui = get_builder('groupchat_roster.ui')
        self._ui.roster_treeview.set_model(None)
        self.add(self._ui.roster_treeview)

        self._contact_refs: dict[str, Gtk.TreeRowReference] = {}
        self._group_refs: dict[str, Gtk.TreeRowReference] = {}

        self._store = self._ui.participant_store
        self._store.set_sort_func(Column.TEXT, self._tree_compare_iters)

        self._roster = self._ui.roster_treeview
        self._roster.set_search_equal_func(self._search_func)
        self._roster.set_has_tooltip(True)
        self._roster.connect('query-tooltip', self._query_tooltip)

        self._ui.contact_column.set_fixed_width(
            app.settings.get('groupchat_roster_width'))
        self._ui.contact_column.set_cell_data_func(self._ui.text_renderer,
                                                   self._text_cell_data_func)

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self.register_events([
            ('theme-update', ged.GUI2, self._on_theme_update),
        ])

    @staticmethod
    def _on_focus_out(treeview: Gtk.TreeView, _param: Gdk.EventFocus) -> None:
        treeview.get_selection().unselect_all()

    def _set_model(self) -> None:
        self._roster.set_model(self._store)

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

        contact = self._group_chat_contact.get_resource(nickname)

        value, widget = self._tooltip.get_tooltip(contact)
        tooltip.set_custom(widget)
        return value

    @staticmethod
    def _search_func(model: Gtk.TreeModel,
                     _column: int,
                     search_text: str,
                     iter_: Gtk.TreeIter
                     ) -> bool:
        return search_text.lower() not in model[iter_][1].lower()

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
                None, [None, group_text, None, False, group_name])
            role_path = self._store.get_path(group_iter)
            group_ref = Gtk.TreeRowReference(self._store, role_path)
            self._group_refs[group_name] = group_ref

        # Avatar
        surface = contact.get_avatar(AvatarSize.ROSTER,
                                     self.get_scale_factor())

        iter_ = self._store.append(group_iter,
                                   [surface, nick, None, True, nick])
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
                                  contact: types.GroupchatContact,
                                  _signal_name: str,
                                  user_contact: types.GroupchatParticipant,
                                  properties: MessageProperties
                                  ) -> None:
        self._remove_contact(user_contact)

        user_contact = contact.get_resource(properties.muc_user.nick)
        self._add_contact(user_contact)

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
        nick = self._store[iter_][Column.NICK_OR_GROUP]
        if self._control.contact.nickname == nick:
            return
        self.emit('row-activated', nick)

    def _on_roster_button_press_event(self,
                                      treeview: Gtk.TreeView,
                                      event: Gdk.EventButton
                                      ) -> None:
        if event.button not in (2, 3):
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

        nick = self._store[iter_][Column.NICK_OR_GROUP]
        if self._group_chat_contact.nickname == nick:
            return

        if event.button == 3:  # right click
            self._show_contact_menu(nick)

        if event.button == 2:  # middle click
            self.emit('row-activated', nick)

    def _show_contact_menu(self, nick: str) -> None:
        self_contact = self._group_chat_contact.get_self()
        contact = self._group_chat_contact.get_resource(nick)
        menu = get_groupchat_roster_menu(self._account,
                                         self._control_id,
                                         self_contact,
                                         contact)

        def destroy(menu: Gtk.Menu, _pspec: GObject.ParamSpec) -> None:
            visible = menu.get_property('visible')
            if not visible:
                GLib.idle_add(menu.destroy)

        menu.attach_to_widget(self, None)
        menu.connect('notify::visible', destroy)
        menu.popup_at_pointer()

    def _tree_compare_iters(self,
                            model: Gtk.TreeModel,
                            iter1: Gtk.TreeIter,
                            iter2: Gtk.TreeIter,
                            _user_data: Optional[object]
                            ) -> int:
        """
        Compare two iterators to sort them
        """
        is_contact = model.iter_parent(iter1)
        if is_contact:
            # Sort contacts with pending events to top
            if model[iter1][Column.EVENT] != model[iter2][Column.EVENT]:
                return -1 if model[iter1][Column.EVENT] else 1

            nick1 = model[iter1][Column.NICK_OR_GROUP]
            nick2 = model[iter2][Column.NICK_OR_GROUP]

            if not app.settings.get('sort_by_show_in_muc'):
                return locale.strcoll(nick1.lower(), nick2.lower())

            contact1 = self._group_chat_contact.get_resource(nick1)
            contact2 = self._group_chat_contact.get_resource(nick2)

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

    def invalidate_sort(self) -> None:
        self.enable_sort(False)
        self.enable_sort(True)

    def initial_draw(self) -> None:
        self.enable_sort(True)
        self._set_model()
        self._roster.expand_all()

    def _redraw(self) -> None:
        self._roster.set_model(None)
        self._roster.set_model(self._store)
        self._roster.expand_all()

    def _draw_contact(self, nick: str) -> None:
        iter_ = self._get_contact_iter(nick)
        if not iter_:
            return

        contact = self._group_chat_contact.get_resource(nick)

        self._draw_avatar(contact)

        self._store[iter_][Column.EVENT] = False

        name = GLib.markup_escape_text(contact.name)

        # Strike name if blocked
        fjid = f'{self.room_jid}/{nick}'
        if jid_is_blocked(self._account, fjid):
            name = f'<span strikethrough="true">{name}</span>'

        # add status msg, if not empty, under contact name
        status = contact.status
        if status is not None:
            status = status.strip()

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
                               user_contact: types.GroupchatParticipant):
        self._draw_avatar(user_contact)

    def _get_total_user_count(self) -> int:
        count = 0
        for group_row in self._store:
            count += self._store.iter_n_children(group_row.iter)
        return count

    def _on_theme_update(self, _event: ApplicationEvent) -> None:
        self._redraw()

    def clear(self) -> None:
        self._contact_refs = {}
        self._group_refs = {}
        self._store.clear()

    def _on_destroy(self, _roster: Any) -> None:
        self._group_chat_contact.disconnect(self)
        self._contact_refs = {}
        self._group_refs = {}
        self._roster.set_model(None)
        self._store.clear()
        # Store keeps a ref on the object if we dont unset the sort func
        self._store.set_sort_func(Column.TEXT, print)
        self._tooltip.destroy()
        del self._roster
        del self._store
        del self._control
        del self._tooltip
        app.check_finalize(self)
