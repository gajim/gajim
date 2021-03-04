import locale
import logging
from typing import Optional
from enum import IntEnum

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GObject

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr
from gajim.common.helpers import jid_is_blocked
from gajim.common.i18n import _

from gajim.gui_menu_builder import get_roster_menu

from .util import EventHelper
from .util import get_builder

log = logging.getLogger('gajim.gui.roster')


HANDLED_EVENTS = [
    'presence-received',
]


class Column(IntEnum):
    AVATAR = 0
    TEXT = 1
    IS_CONTACT = 2
    JID_OR_GROUP = 3


class Roster(Gtk.ScrolledWindow, EventHelper):

    __gsignals__ = {
        'row-activated': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,  # return value
            (str, ))  # arguments
    }

    def __init__(self, account):
        Gtk.ScrolledWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_size_request(200, -1)
        self.set_vexpand(True)
        self.get_style_context().add_class('roster')

        self._account = account
        self._client = app.get_client(account)

        self._ui = get_builder('roster.ui')
        self._ui.roster_treeview.set_model(None)
        self.add(self._ui.roster_treeview)

        # Holds the Gtk.TreeRowReference for each contact
        self._contact_refs = {}
        # Holds the Gtk.TreeRowReference for each group
        self._group_refs = {}

        self._store = self._ui.contact_store
        self._store.set_sort_func(Column.TEXT, self._tree_compare_iters)

        self._roster = self._ui.roster_treeview

        self._ui.contact_column.set_cell_data_func(self._ui.text_renderer,
                                                   self._text_cell_data_func)
        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self.register_events([
            ('account-connected', ged.CORE, self._on_account_state),
            ('account-disconnected', ged.CORE, self._on_account_state),
            ('theme-update', ged.GUI2, self._on_theme_update),
        ])

        self._add_actions()
        self._initial_draw()

    def _add_actions(self):
        actions = [
            ('contact-info', self._contact_info),
            ('execute-command', self._execute_command),
            ('block-contact', self._block_contact),
            ('remove-contact', self._remove_contact),
        ]
        for action in actions:
            action_name, func = action
            act = Gio.SimpleAction.new(
                f'{action_name}-{self._account}', GLib.VariantType.new('s'))
            act.connect('activate', func)
            app.window.add_action(act)

    def update_actions(self):
        online = app.account_is_connected(self._account)
        blocking_support = self._client.get_module('Blocking').supported

        app.window.lookup_action(
            f'contact-info-{self._account}').set_enabled(online)
        app.window.lookup_action(
            f'execute-command-{self._account}').set_enabled(online)
        app.window.lookup_action(
            f'block-contact-{self._account}').set_enabled(
                online and blocking_support)
        app.window.lookup_action(
            f'remove-contact-{self._account}').set_enabled(online)

    def _remove_actions(self):
        actions = [
            'contact-info',
            'execute-command',
            'block-contact',
            'remove-contact',
        ]
        for action in actions:
            app.window.remove_action(f'{action}-{self._account}')

    def _on_account_state(self, _event):
        self.update_actions()

    def _on_theme_update(self, _event):
        self.redraw()

    def _contact_info(self, _action, param):
        app.window.contact_info(self._account, param.get_string())

    def _execute_command(self, _action, param):
        app.window.execute_command(self._account, param.get_string())

    def _block_contact(self, _action, param):
        app.window.block_contact(self._account, param.get_string())

    def _remove_contact(self, _action, param):
        app.window.remove_contact(self._account, param.get_string())

    def _on_roster_row_activated(self, _treeview, path, _column):
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # This is a group row
            return

        jid = self._store[iter_][Column.JID_OR_GROUP]
        self.emit('row-activated', jid)

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

        jid = self._store[iter_][Column.JID_OR_GROUP]

        if event.button == 3:  # right click
            self._show_contact_menu(jid, treeview, event)

        if event.button == 2:  # middle click
            self.emit('row-activated', jid)

    @staticmethod
    def _on_focus_out(treeview, _param):
        treeview.get_selection().unselect_all()

    def _show_contact_menu(self, jid, treeview, event):
        menu = get_roster_menu(self._account, jid)

        rectangle = Gdk.Rectangle()
        rectangle.x = event.x
        rectangle.y = event.y
        rectangle.width = rectangle.height = 1

        popover = Gtk.Popover.new_from_model(self, menu)
        popover.set_relative_to(treeview)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.set_pointing_to(rectangle)
        popover.popup()

    def _on_destroy(self, _roster):
        self._remove_actions()
        self._contact_refs = {}
        self._group_refs = {}
        self._roster.set_model(None)
        self._roster = None
        # Store keeps a ref on the object if we don’t unset the sort func
        self._store.set_sort_func(Column.TEXT, print)
        self._store.clear()
        self._store = None
        # self._tooltip.destroy()
        # self._tooltip = None
        app.check_finalize(self)

    def set_model(self):
        self._roster.set_model(self._store)

    def redraw(self):
        self._roster.set_model(None)
        self._roster.set_model(self._store)
        self._roster.expand_all()

    def enable_sort(self, enable):
        column = Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID
        if enable:
            column = Column.TEXT

        self._store.set_sort_column_id(column, Gtk.SortType.ASCENDING)

    def invalidate_sort(self):
        self.enable_sort(False)
        self.enable_sort(True)

    def _initial_draw(self):
        for contact in self._client.get_module('Roster').iter_contacts():
            contact.connect('presence-update', self._on_presence_update)
            contact.connect('avatar-update', self._on_avatar_update)
            self._add_contact(contact)

        self.enable_sort(True)
        self.set_model()
        self._roster.expand_all()

    def _on_presence_update(self, contact, _signal_name):
        self.draw_avatar(contact)

    def _on_avatar_update(self, contact, _signal_name):
        self.draw_avatar(contact)

    def _add_contact(self, contact):
        main_group = _('Contacts')

        if contact.groups:
            for group_name in contact.groups:
                group_iter = self._get_group_iter(group_name)
                if not group_iter:
                    group_iter = self._store.append(
                        None, (None, group_name, False, group_name))
                group_path = self._store.get_path(group_iter)
                group_ref = Gtk.TreeRowReference(self._store, group_path)
                self._group_refs[group_name] = group_ref
        else:
            group_iter = self._get_group_iter(main_group)
            if not group_iter:
                group_iter = self._store.append(
                    None, (None, main_group, False, main_group))
            group_path = self._store.get_path(group_iter)
            group_ref = Gtk.TreeRowReference(self._store, group_path)
            self._group_refs[main_group] = group_ref

        # Avatar
        surface = contact.get_avatar(AvatarSize.CHAT, self.get_scale_factor())

        jid = str(contact.jid)
        # TODO: Multiple groups per contact ?
        iter_ = self._store.append(
            group_iter, (surface, contact.name, True, jid))
        self._contact_refs[jid] = Gtk.TreeRowReference(
            self._store, self._store.get_path(iter_))

        self.draw_groups()
        self.draw_contact(jid)

        if (group_path is not None and
                self._roster.get_model() is not None):
            self._roster.expand_row(group_path, False)

    def remove_contact(self, jid):
        # TODO: How to delete a roster item?
        #self._client.get_module('Roster').delete_item(jid)

        iter_ = self._get_contact_iter(jid)
        if not iter_:
            return

        group_iter = self._store.iter_parent(iter_)
        if group_iter is None:
            raise ValueError('Trying to remove non-chil')

        self._store.remove(iter_)
        del self._contact_refs[jid]
        if not self._store.iter_has_child(group_iter):
            group = self._store[group_iter][Column.JID_OR_GROUP]
            del self._group_refs[group]
            self._store.remove(group_iter)

        self.redraw()

    def draw_groups(self):
        for group in self._group_refs:
            self.draw_group(group)

    def draw_group(self, group_name):
        group_iter = self._get_group_iter(group_name)
        if not group_iter:
            return

        total_users = self._get_total_user_count()
        group_users = self._store.iter_n_children(group_iter)
        group_name += f' ({group_users}/{total_users})'

        self._store[group_iter][Column.TEXT] = group_name

    def draw_contacts(self):
        for jid in self._contact_refs:
            self.draw_contact(jid)

    def draw_contact(self, jid):
        iter_ = self._get_contact_iter(jid)
        if not iter_:
            return

        contact = self._client.get_module('Contacts').get_contact(jid)
        name = GLib.markup_escape_text(contact.name)
        if jid_is_blocked(self._account, jid):
            name = f'<span strikethrough="true">{name}</span>'

        self.draw_avatar(contact)
        self._store[iter_][Column.TEXT] = name

    def draw_avatar(self, contact):
        iter_ = self._get_contact_iter(str(contact.jid))
        if iter_ is None:
            return

        surface = contact.get_avatar(
            AvatarSize.ROSTER, self.get_scale_factor())
        self._store[iter_][Column.AVATAR] = surface

    def _get_total_user_count(self):
        count = 0
        for group_row in self._store:
            count += self._store.iter_n_children(group_row.iter)
        return count

    def _get_group_iter(self, group_name: str) -> Optional[Gtk.TreeIter]:
        try:
            ref = self._group_refs[group_name]
        except KeyError:
            return None

        path = ref.get_path()
        if path is None:
            return None
        return self._store.get_iter(path)

    def _get_contact_iter(self, jid: str) -> Optional[Gtk.TreeIter]:
        try:
            ref = self._contact_refs[jid]
        except KeyError:
            return None

        path = ref.get_path()
        if path is None:
            return None

        return self._store.get_iter(path)

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

    def _tree_compare_iters(self, model, iter1, iter2, _user_data):
        """
        Compare two iterators to sort them
        """

        is_contact = model.iter_parent(iter1)
        if is_contact:
            name1 = model[iter1][Column.TEXT]
            name2 = model[iter2][Column.TEXT]

            if not app.settings.get('sort_by_show_in_roster'):
                return locale.strcoll(name1.lower(), name2.lower())

            contact1 = self._client.get_module('Contacts').get_contact(
                model[iter1][Column.JID_OR_GROUP])
            contact2 = self._client.get_module('Contacts').get_contact(
                model[iter2][Column.JID_OR_GROUP])

            if contact1.show != contact2.show:
                return -1 if contact1.show > contact2.show else 1

            return locale.strcoll(name1.lower(), name2.lower())

        # Group
        group1 = model[iter1][Column.JID_OR_GROUP]
        group2 = model[iter2][Column.JID_OR_GROUP]
        return -1 if group1 < group2 else 1

    def clear(self):
        self._contact_refs = {}
        self._group_refs = {}
        self._store.clear()

    def _on_presence_received(self, event):
        pass

    def process_event(self, event):
        if event.name not in HANDLED_EVENTS:
            return

        if event.name == 'presence-received':
            self._on_presence_received(event)
        else:
            log.warning('Unhandled Event: %s', event.name)
