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

from typing import Optional

import locale
from enum import IntEnum

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject
from nbxmpp.const import Role
from nbxmpp.const import Affiliation

from gajim.common import app
from gajim.common import ged
from gajim.common.helpers import get_uf_role
from gajim.common.helpers import get_uf_affiliation
from gajim.common.helpers import jid_is_blocked
from gajim.common.helpers import event_filter
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr

from gajim.gui_menu_builder import get_groupchat_roster_menu
from gajim.gtk.tooltips import GCTooltip
from gajim.gtk.util import get_builder
from gajim.gtk.util import EventHelper


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

    def __init__(self, account, room_jid, control):
        Gtk.ScrolledWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.get_style_context().add_class('groupchat-roster')
        self._account = account
        self.room_jid = room_jid
        self._control = control
        self._control_id = control.control_id
        self._show_roles = True
        self._handler_ids = {}
        self._tooltip = GCTooltip()

        self._ui = get_builder('groupchat_roster.ui')
        self._ui.roster_treeview.set_model(None)
        self.add(self._ui.roster_treeview)

        # Holds the Gtk.TreeRowReference for each contact
        self._contact_refs = {}
        # Holds the Gtk.TreeRowReference for each group
        self._group_refs = {}

        self._store = self._ui.participant_store
        self._store.set_sort_func(Column.TEXT, self._tree_compare_iters)

        self._roster = self._ui.roster_treeview
        self._roster.set_search_equal_func(self._search_func)

        self._ui.contact_column.set_fixed_width(
            app.config.get('groupchat_roster_width'))
        self._ui.contact_column.set_cell_data_func(self._ui.text_renderer,
                                                   self._text_cell_data_func)

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self.register_events([
            ('theme-update', ged.GUI2, self._on_theme_update),
            ('update-gc-avatar', ged.GUI1, self._on_avatar_update),
        ])

    @staticmethod
    def _on_focus_out(treeview, _param):
        treeview.get_selection().unselect_all()

    def set_model(self):
        self._roster.set_model(self._store)

    def set_show_roles(self, enabled):
        self._show_roles = enabled

    def enable_tooltips(self):
        if self._roster.get_tooltip_window():
            return

        self._roster.set_has_tooltip(True)
        id_ = self._roster.connect('query-tooltip', self._query_tooltip)
        self._handler_ids[id_] = self._roster

    def _query_tooltip(self, widget, x_pos, y_pos, _keyboard_mode, tooltip):
        try:
            row = self._roster.get_path_at_pos(x_pos, y_pos)[0]
        except TypeError:
            self._tooltip.clear_tooltip()
            return False
        if not row:
            self._tooltip.clear_tooltip()
            return False

        iter_ = None
        try:
            iter_ = self._store.get_iter(row)
        except Exception:
            self._tooltip.clear_tooltip()
            return False

        if not self._store[iter_][Column.IS_CONTACT]:
            self._tooltip.clear_tooltip()
            return False

        nickname = self._store[iter_][Column.NICK_OR_GROUP]
        contact = app.contacts.get_gc_contact(self._account,
                                              self.room_jid,
                                              nickname)
        if contact is None:
            self._tooltip.clear_tooltip()
            return False

        value, widget = self._tooltip.get_tooltip(contact)
        tooltip.set_custom(widget)
        return value

    @staticmethod
    def _search_func(model, _column, search_text, iter_):
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

    def add_contact(self, nick):
        contact = app.contacts.get_gc_contact(self._account,
                                              self.room_jid,
                                              nick)
        group_name, group_text = self._get_group_from_contact(contact)

        # Create Group
        group_iter = self._get_group_iter(group_name)
        role_path = None
        if not group_iter:
            group_iter = self._store.append(
                None, (None, group_text, None, False, group_name))
            role_path = self._store.get_path(group_iter)
            group_ref = Gtk.TreeRowReference(self._store, role_path)
            self._group_refs[group_name] = group_ref

        # Avatar
        surface = app.interface.get_avatar(contact,
                                           AvatarSize.ROSTER,
                                           self.get_scale_factor(),
                                           contact.show.value)

        iter_ = self._store.append(group_iter,
                                   (surface, nick, None, True, nick))
        self._contact_refs[nick] = Gtk.TreeRowReference(
            self._store, self._store.get_path(iter_))

        self.draw_groups()
        self.draw_contact(nick)

        if (role_path is not None and
                self._roster.get_model() is not None):
            self._roster.expand_row(role_path, False)

    def remove_contact(self, nick):
        """
        Remove a user
        """
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
    def _get_group_from_contact(contact):
        if contact.affiliation in (Affiliation.OWNER, Affiliation.ADMIN):
            return contact.affiliation.value, get_uf_affiliation(
                contact.affiliation, plural=True)
        return contact.role.value, get_uf_role(contact.role, plural=True)

    @staticmethod
    def _text_cell_data_func(_column, renderer, model, iter_, _user_data):
        has_parent = bool(model.iter_parent(iter_))
        style = 'contact' if has_parent else 'group'

        bgcolor = app.css_config.get_value('.gajim-%s-row' % style,
                                           StyleAttr.BACKGROUND)
        renderer.set_property('cell-background', bgcolor)

        color = app.css_config.get_value('.gajim-%s-row' % style,
                                         StyleAttr.COLOR)
        renderer.set_property('foreground', color)

        desc = app.css_config.get_font('.gajim-%s-row' % style)
        renderer.set_property('font-desc', desc)

        if not has_parent:
            renderer.set_property('weight', 600)
            renderer.set_property('ypad', 6)

    def _on_roster_row_activated(self, _treeview, path, _column):
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # This is a group row
            return
        nick = self._store[iter_][Column.NICK_OR_GROUP]
        if self._control.nick == nick:
            return
        self.emit('row-activated', nick)

    def _on_roster_button_press_event(self, treeview, event):
        if event.button not in (2, 3):
            return

        pos = treeview.get_path_at_pos(int(event.x), int(event.y))
        if pos is None:
            return

        path, _, _, _ = pos
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # Group row
            return

        nick = self._store[iter_][Column.NICK_OR_GROUP]
        if self._control.nick == nick:
            return

        if event.button == 3: # right click
            self._show_contact_menu(nick)

        if event.button == 2: # middle click
            self.emit('row-activated', nick)

    def _show_contact_menu(self, nick):
        self_contact = app.contacts.get_gc_contact(
            self._account, self.room_jid, self._control.nick)
        contact = app.contacts.get_gc_contact(
            self._account, self.room_jid, nick)
        menu = get_groupchat_roster_menu(self._account,
                                         self._control_id,
                                         self_contact,
                                         contact)

        def destroy(menu, _pspec):
            visible = menu.get_property('visible')
            if not visible:
                GLib.idle_add(menu.destroy)

        menu.attach_to_widget(self, None)
        menu.connect('notify::visible', destroy)
        menu.popup_at_pointer()

    def _tree_compare_iters(self, model, iter1, iter2, _user_data):
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

            if not app.config.get('sort_by_show_in_muc'):
                return locale.strcoll(nick1.lower(), nick2.lower())

            gc_contact1 = app.contacts.get_gc_contact(self._account,
                                                      self.room_jid,
                                                      nick1)
            gc_contact2 = app.contacts.get_gc_contact(self._account,
                                                      self.room_jid,
                                                      nick2)
            if gc_contact1.show != gc_contact2.show:
                return -1 if gc_contact1.show > gc_contact2.show else 1

            return locale.strcoll(nick1.lower(), nick2.lower())

        # Group
        group1 = model[iter1][Column.NICK_OR_GROUP]
        group2 = model[iter2][Column.NICK_OR_GROUP]
        group1_index = AffiliationRoleSortOrder[group1]
        group2_index = AffiliationRoleSortOrder[group2]
        return -1 if group1_index < group2_index else 1

    def enable_sort(self, enable):
        column = Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID
        if enable:
            column = Column.TEXT

        self._store.set_sort_column_id(column, Gtk.SortType.ASCENDING)

    def invalidate_sort(self):
        self.enable_sort(False)
        self.enable_sort(True)

    def initial_draw(self):
        self.enable_sort(True)
        self.set_model()
        self._roster.expand_all()

    def redraw(self):
        self._roster.set_model(None)
        self._roster.set_model(self._store)
        self._roster.expand_all()

    def draw_contact(self, nick):
        iter_ = self._get_contact_iter(nick)
        if not iter_:
            return

        gc_contact = app.contacts.get_gc_contact(
            self._account, self.room_jid, nick)

        self.draw_avatar(gc_contact)

        if app.events.get_events(self._account, self.room_jid + '/' + nick):
            self._store[iter_][Column.EVENT] = True
        else:
            self._store[iter_][Column.EVENT] = False

        name = GLib.markup_escape_text(gc_contact.name)

        # Strike name if blocked
        fjid = self.room_jid + '/' + nick
        if jid_is_blocked(self._account, fjid):
            name = '<span strikethrough="true">%s</span>' % name

        # add status msg, if not empty, under contact name
        status = gc_contact.status
        if status is not None:
            status = status.strip()

        if status and app.config.get('show_status_msgs_in_roster'):
            # Display only first line
            status = status.split('\n', 1)[0]
            # escape markup entities and make them small italic and fg color
            name += ('\n<span size="small" style="italic" alpha="70%">'
                     '{}</span>'.format(GLib.markup_escape_text(status)))

        self._store[iter_][Column.TEXT] = name

    def draw_contacts(self):
        for nick in self._contact_refs:
            self.draw_contact(nick)

    def draw_group(self, group):
        group_iter = self._get_group_iter(group)
        if not group_iter:
            return

        if group in ('owner', 'admin'):
            group_text = get_uf_affiliation(group, plural=True)
        else:
            group_text = get_uf_role(group, plural=True)

        total_users = self._get_total_user_count()
        group_users = self._store.iter_n_children(group_iter)

        group_text += ' (%s/%s)' % (group_users, total_users)

        self._store[group_iter][Column.TEXT] = group_text

    def draw_groups(self):
        for group in self._group_refs:
            self.draw_group(group)

    def draw_avatar(self, contact):
        iter_ = self._get_contact_iter(contact.name)
        if iter_ is None:
            return
        surface = app.interface.get_avatar(contact,
                                           AvatarSize.ROSTER,
                                           self.get_scale_factor(),
                                           contact.show.value)
        self._store[iter_][Column.AVATAR] = surface

    def _get_total_user_count(self):
        count = 0
        for group_row in self._store:
            count += self._store.iter_n_children(group_row.iter)
        return count

    def get_role(self, nick):
        gc_contact = app.contacts.get_gc_contact(
            self._account, self.room_jid, nick)
        if gc_contact:
            return gc_contact.role
        return Role.VISITOR

    def _on_theme_update(self, _event):
        self.redraw()

    @event_filter(['room_jid'])
    def _on_avatar_update(self, event):
        self.draw_avatar(event.contact)

    def clear(self):
        self._contact_refs = {}
        self._group_refs = {}
        self._store.clear()

    def _on_destroy(self, _roster):
        for id_ in list(self._handler_ids.keys()):
            if self._handler_ids[id_].handler_is_connected(id_):
                self._handler_ids[id_].disconnect(id_)
            del self._handler_ids[id_]

        self._contact_refs = {}
        self._group_refs = {}
        self._control = None
        self._roster.set_model(None)
        self._roster = None
        self._store.clear()
        self._store = None
        self._tooltip.destroy()
        self._tooltip = None
