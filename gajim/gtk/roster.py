import locale
import logging
from typing import Optional
from enum import IntEnum
from collections import defaultdict

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr
from gajim.common.const import PresenceShowExt
from gajim.common.helpers import jid_is_blocked
from gajim.common.helpers import event_filter
from gajim.common.i18n import _

from gajim.gui_menu_builder import get_roster_menu

from .util import EventHelper
from .util import get_builder

log = logging.getLogger('gajim.gui.roster')


HANDLED_EVENTS = [
    'presence-received',
]


DEFAULT_GROUP = _('Contacts')


class Column(IntEnum):
    AVATAR = 0
    TEXT = 1
    IS_CONTACT = 2
    JID_OR_GROUP = 3
    VISIBLE = 4


class Roster(Gtk.ScrolledWindow, EventHelper):
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
        self._contact_refs = defaultdict(list)
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
            ('roster-push', ged.GUI2, self._on_roster_push),
        ])

        self._modelfilter = self._store.filter_new()
        self._modelfilter.set_visible_func(self._visible_func)
        self._filter_enabled = False
        self._filter_string = ''

        self._add_actions()
        self._initial_draw()

    def _add_actions(self):
        actions = [
            ('contact-info', self._on_contact_info),
            ('execute-command', self._on_execute_command),
            ('block-contact', self._on_block_contact),
            ('remove-contact', self._on_remove_contact),
        ]
        for action in actions:
            action_name, func = action
            act = Gio.SimpleAction.new(
                f'{action_name}-{self._account}', GLib.VariantType.new('s'))
            act.connect('activate', func)
            app.window.add_action(act)

        action = Gio.SimpleAction.new_stateful(
            f'show-offline-{self._account}',
            None,
            GLib.Variant.new_boolean(app.settings.get('showoffline')))
        action.connect('change-state', self._on_show_offline)
        app.window.add_action(action)

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
            'show-offline',
        ]
        for action in actions:
            app.window.remove_action(f'{action}-{self._account}')

    def _get_contact(self, jid):
        return self._client.get_module('Contacts').get_contact(jid)

    def _on_account_state(self, _event):
        self.update_actions()

    def _on_theme_update(self, _event):
        self.redraw()

    def _on_show_offline(self, action, param):
        action.set_state(param)
        app.settings.set('showoffline', param.get_boolean())
        self._draw_contacts()

    def _on_contact_info(self, _action, param):
        app.window.contact_info(self._account, param.get_string())

    def _on_execute_command(self, _action, param):
        app.window.execute_command(self._account, param.get_string())

    def _on_block_contact(self, _action, param):
        app.window.block_contact(self._account, param.get_string())

    def _on_remove_contact(self, _action, param):
        app.window.remove_contact(self._account, param.get_string())

    def _on_roster_row_activated(self, _treeview, path, _column):
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # This is a group row
            return

        jid = self._store[iter_][Column.JID_OR_GROUP]
        app.window.add_chat(self._account, jid, 'contact', select=True)
        app.window.show_chats()

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
            app.window.add_chat(self._account, jid, 'contact', select=True)
            app.window.show_chats()

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

    def set_search_string(self, text):
        self._filter_string = text
        self._filter_enabled = bool(text)
        self._draw_contacts()

    def _get_contact_visible(self, contact):
        if self._filter_enabled:
            return self._filter_string in contact.name.lower()

        if app.settings.get('showoffline'):
            return True

        if contact.show is PresenceShowExt.OFFLINE:
            return False

        return True

    def _visible_func(self, model, iter_, _data):
        visible = model[iter_][Column.VISIBLE]
        is_contact = model[iter_][Column.IS_CONTACT]
        name = model[iter_][Column.TEXT]

        if not is_contact:
            # Always show groups
            return True

        if self._filter_enabled:
            return self._filter_string in name.lower()

        return visible

    def set_model(self):
        self._roster.set_model(self._modelfilter)

    def redraw(self):
        self._roster.set_model(None)
        self._roster.set_model(self._modelfilter)
        self._roster.expand_all()

    def _reset(self):
        self._roster.set_model(None)
        self.enable_sort(False)
        self._initial_draw()

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
            self._add_or_update_contact(contact)

        self.enable_sort(True)
        self.set_model()
        self._roster.expand_all()

    def _on_presence_update(self, contact, _signal_name):
        self._draw_contact(contact)

    def _on_avatar_update(self, contact, _signal_name):
        self._draw_contact(contact)

    @event_filter(['account'])
    def _on_roster_received(self, _event):
        self._reset()

    @event_filter(['account'])
    def _on_roster_push(self, event):
        contact = self._get_contact(event.item.jid)
        self._add_or_update_contact(contact)

    def _get_current_groups(self, jid):
        groups = set()
        for ref in self._contact_refs[jid]:
            iter_ = self._get_iter_from_ref(ref)
            group_iter = self._store.iter_parent(iter_)
            groups.add(self._store[group_iter][Column.JID_OR_GROUP])
        return groups

    def _add_group(self, group_name):
        group_iter = self._get_group_iter(group_name)
        if group_iter is not None:
            return group_iter

        group_iter = self._store.append(
            None, (None, group_name, False, group_name, True))
        group_path = self._store.get_path(group_iter)
        group_ref = Gtk.TreeRowReference(self._store, group_path)
        self._group_refs[group_name] = group_ref
        return group_iter

    def _add_contact_to_group(self, contact, group):
        group_iter = self._add_group(group)
        iter_ = self._store.append(
            group_iter,
            (None, contact.name, True, str(contact.jid), True))

        ref = Gtk.TreeRowReference(self._store, self._store.get_path(iter_))
        self._contact_refs[contact.jid].append(ref)

    def _add_contact_to_groups(self, contact, groups):
        for group in groups:
            self._add_contact_to_group(contact, group)

    def _remove_contact_from_groups(self, contact, groups):
        if not groups:
            return

        refs = self._contact_refs[contact.jid]
        for ref in refs:
            iter_ = self._get_iter_from_ref(ref)
            group_iter = self._store.iter_parent(iter_)
            group = self._store[group_iter][Column.JID_OR_GROUP]
            if group in groups:
                iter_ = self._store.get_iter(ref.get_path())
                self._store.remove(iter_)
                self._contact_refs[contact.jid].remove(ref)

        self._check_for_empty_groups()

    def _remove_contact(self, contact):
        refs = self._contact_refs.pop(contact.jid)
        for ref in refs:
            iter_ = self._get_iter_from_ref(ref)
            self._store.remove(iter_)

        self._check_for_empty_groups()

    def _check_for_empty_groups(self):
        for ref in list(self._group_refs.values()):
            group_iter = self._get_iter_from_ref(ref)
            if self._store.iter_has_child(group_iter):
                continue
            group = self._store[group_iter][Column.JID_OR_GROUP]
            self._store.remove(group_iter)
            del self._group_refs[group]

    def _add_or_update_contact(self, contact):
        new_groups = set(contact.groups or [DEFAULT_GROUP])
        groups = self._get_current_groups(contact.jid)

        add_to_groups = new_groups - groups
        remove_from_groups = groups - new_groups

        self._add_contact_to_groups(contact, add_to_groups)
        self._remove_contact_from_groups(contact, remove_from_groups)

        self._draw_groups()
        self._draw_contact(contact)

    def _draw_groups(self):
        for group in self._group_refs:
            self._draw_group(group)

    def _draw_group(self, group_name):
        group_iter = self._get_group_iter(group_name)
        if not group_iter:
            return

        if self._roster.get_model() is not None:
            group_path = self._store.get_path(group_iter)
            self._roster.expand_row(group_path, False)

        total_users = self._get_total_user_count()
        group_users = self._store.iter_n_children(group_iter)
        group_name += f' ({group_users}/{total_users})'

        self._store[group_iter][Column.TEXT] = group_name
        self._store[group_iter][Column.VISIBLE] = True

    def _draw_contacts(self):
        for jid in self._contact_refs:
            self._draw_contact(self._get_contact(jid))
        self._roster.expand_all()

    def _draw_contact(self, contact):
        for ref in self._contact_refs[contact.jid]:
            self._draw_contact_row(ref, contact)
        self._roster.expand_all()

    def _draw_contact_row(self, ref, contact):
        iter_ = self._get_iter_from_ref(ref)

        name = GLib.markup_escape_text(contact.name)
        if jid_is_blocked(self._account, contact.jid):
            name = f'<span strikethrough="true">{name}</span>'
        self._store[iter_][Column.TEXT] = name
        visible = self._get_contact_visible(contact)
        self._store[iter_][Column.VISIBLE] = visible

        surface = contact.get_avatar(
            AvatarSize.ROSTER, self.get_scale_factor())
        self._store[iter_][Column.AVATAR] = surface

    def _get_total_user_count(self):
        count = 0
        for group_row in self._store:
            count += self._store.iter_n_children(group_row.iter)
        return count

    def _get_iter_from_ref(self, ref):
        return self._store.get_iter(ref.get_path())

    def _get_group_iter(self, group_name: str) -> Optional[Gtk.TreeIter]:
        try:
            ref = self._group_refs[group_name]
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

            contact1 = self._get_contact(model[iter1][Column.JID_OR_GROUP])
            contact2 = self._get_contact(model[iter2][Column.JID_OR_GROUP])

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

    def _on_presence_received(self, _event):
        pass

    def process_event(self, event):
        if event.name not in HANDLED_EVENTS:
            return

        if event.name == 'presence-received':
            self._on_presence_received(event)
        else:
            log.warning('Unhandled Event: %s', event.name)

    def _on_destroy(self, _roster):
        self._remove_actions()
        self._contact_refs = {}
        self._group_refs = {}
        self._roster.set_model(None)
        self._roster = None
        self._store.clear()
        self._store.reset_default_sort_func()
        self._store = None
        # self._tooltip.destroy()
        # self._tooltip = None
        app.check_finalize(self)
