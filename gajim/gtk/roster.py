import locale
import logging
from typing import Optional
from enum import IntEnum
from collections import defaultdict

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from nbxmpp import Namespace

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr
from gajim.common.const import PresenceShowExt
from gajim.common.helpers import event_filter
from gajim.common.i18n import _

from gajim.gui_menu_builder import get_roster_menu

from .dialogs import ConfirmationDialog
from .dialogs import DialogButton
from .tooltips import RosterTooltip
from .service_registration import ServiceRegistration
from .util import EventHelper
from .util import get_builder

log = logging.getLogger('gajim.gui.roster')


HANDLED_EVENTS = []

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

        self._roster_tooltip = RosterTooltip()

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
        self._roster.set_has_tooltip(True)
        self._roster.connect('query-tooltip', self._on_query_tooltip)

        # Drag and Drop
        entries = [Gtk.TargetEntry.new(
            'ROSTER_ITEM',
            Gtk.TargetFlags.SAME_APP,
            0)]
        self._roster.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK,
            entries,
            Gdk.DragAction.MOVE)
        self._roster.enable_model_drag_dest(entries, Gdk.DragAction.DEFAULT)
        self._roster.connect('drag-drop', self._on_drag_drop)
        self._roster.connect('drag-data-received', self._on_drag_data_received)

        self._ui.contact_column.set_cell_data_func(self._ui.text_renderer,
                                                   self._text_cell_data_func)
        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self.register_events([
            ('account-connected', ged.CORE, self._on_account_state),
            ('account-disconnected', ged.CORE, self._on_account_state),
            ('roster-received', ged.CORE, self._on_roster_received),
            ('theme-update', ged.GUI2, self._on_theme_update),
            ('roster-push', ged.GUI2, self._on_roster_push),
        ])

        roster_size = self._client.get_module('Roster').get_size()
        self._high_performance = roster_size > 1000

        self._modelfilter = self._store.filter_new()
        if self._high_performance:
            self._modelfilter.set_visible_func(self._visible_func)
        else:
            self._modelfilter.set_visible_column(Column.VISIBLE)
        self._filter_enabled = False
        self._filter_string = ''

        self._add_actions()
        self._initial_draw()

    def _add_actions(self):
        actions = [
            ('contact-info', self._on_contact_info),
            ('modify-gateway', self._on_modify_gateway),
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
            f'modify-gateway-{self._account}').set_enabled(online)
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
            'modify-gateway',
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

    @staticmethod
    def _on_drag_drop(treeview, drag_context, _x_coord, _y_coord,
                      timestamp):
        treeview.stop_emission_by_name('drag-drop')
        target_list = treeview.drag_dest_get_target_list()
        target = treeview.drag_dest_find_target(drag_context, target_list)
        treeview.drag_get_data(drag_context, target, timestamp)
        return True

    def _on_drag_data_received(self, treeview, _drag_context, x_coord,
                               y_coord, _selection_data, _info, _timestamp):
        treeview.stop_emission_by_name('drag-data-received')
        if treeview.get_selection().count_selected_rows() == 0:
            # No selections, nothing dragged from treeview
            return

        drop_info = treeview.get_dest_row_at_pos(x_coord, y_coord)
        if not drop_info:
            return

        model = treeview.get_model()
        path_dest, _position = drop_info

        # Source: the row being dragged
        path_source = treeview.get_selection().get_selected_rows()[1][0]
        iter_source = model.get_iter(path_source)
        iter_source_parent = model.iter_parent(iter_source)
        if iter_source_parent is None:
            # Dragged a group
            return

        source_group = model[iter_source_parent][Column.JID_OR_GROUP]

        jid = model[iter_source][Column.JID_OR_GROUP]
        # name = model[iter_source][Column.TEXT]

        # Destination: the row receiving the drop
        iter_dest = model.get_iter(path_dest)
        iter_dest_parent = model.iter_parent(iter_dest)
        if iter_dest_parent is None:
            # Dropped on a group
            dest_group = model[iter_dest][Column.JID_OR_GROUP]
        else:
            dest_group = model[iter_dest_parent][Column.JID_OR_GROUP]

        if source_group == dest_group:
            return

        if DEFAULT_GROUP == dest_group:
            self._client.get_module('Roster').set_groups(jid, None)
            return

        self._client.get_module('Roster').change_group(jid,
                                                       source_group,
                                                       dest_group)

    def _on_query_tooltip(self, treeview, x_coord, y_coord, _keyboard_mode,
                          tooltip):
        try:
            path = treeview.get_path_at_pos(x_coord, y_coord)
            row = path[0]
        except TypeError:
            self._roster_tooltip.clear_tooltip()
            return False

        if not row:
            self._roster_tooltip.clear_tooltip()
            return False

        iter_ = None
        try:
            model = treeview.get_model()
            iter_ = model.get_iter(row)
        except Exception:
            self._roster_tooltip.clear_tooltip()
            return False

        if not model[iter_][Column.IS_CONTACT]:
            # It’s a group
            self._roster_tooltip.clear_tooltip()
            return False

        contact = self._get_contact(model[iter_][Column.JID_OR_GROUP])
        value, widget = self._roster_tooltip.get_tooltip(row, contact)
        tooltip.set_custom(widget)
        return value

    def _on_show_offline(self, action, param):
        action.set_state(param)
        app.settings.set('showoffline', param.get_boolean())
        self._refilter()

    def _on_contact_info(self, _action, param):
        app.window.contact_info(self._account, param.get_string())

    def _on_modify_gateway(self, _action, param):
        ServiceRegistration(self._account, param.get_string())

    def _on_execute_command(self, _action, param):
        app.window.execute_command(self._account, param.get_string())

    def _on_block_contact(self, _action, param):
        app.window.block_contact(self._account, param.get_string())

    def _on_remove_contact(self, _action, param):
        jid = param.get_string()
        selected_contact = self._client.get_module('Contacts').get_contact(jid)
        if selected_contact.is_gateway:
            # Check for transport users in roster and warn about removing the
            # transport if there are any
            has_transport_contacts = False
            for contact in self._client.get_module('Roster').iter_contacts():
                if contact.jid.domain == selected_contact.jid.domain:
                    has_transport_contacts = True
                    break
            if has_transport_contacts:
                def _on_remove():
                    self._client.get_module('Gateway').unsubscribe(
                        selected_contact.jid)

                ConfirmationDialog(
                    _('Remove Transport'),
                    _('Transport \'%s\' will be '
                      'removed') % selected_contact.name,
                    _('You will no longer be able to send and receive '
                      'messages from and to contacts using this transport.'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       callback=_on_remove)],
                    transient_for=app.window).show()
            else:
                _on_remove()
            return

        app.window.remove_contact(self._account, jid)

    def _on_roster_row_activated(self, _treeview, path, _column):
        path = self._modelfilter.convert_path_to_child_path(path)
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # This is a group row
            return

        jid = self._store[iter_][Column.JID_OR_GROUP]
        app.window.add_chat(self._account, jid, 'contact', select=True)

    def _on_roster_button_press_event(self, treeview, event):
        if event.button not in (2, 3):
            return

        pos = treeview.get_path_at_pos(int(event.x), int(event.y))
        if pos is None:
            return

        path, _, _, _ = pos
        path = self._modelfilter.convert_path_to_child_path(path)
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # Group row
            return

        jid = self._store[iter_][Column.JID_OR_GROUP]

        if event.button == 3:  # right click
            self._show_contact_menu(jid, treeview, event)

        if event.button == 2:  # middle click
            app.window.add_chat(self._account, jid, 'contact', select=True)

    @staticmethod
    def _on_focus_out(treeview, _param):
        treeview.get_selection().unselect_all()

    def _show_contact_menu(self, jid, treeview, event):
        contact = self._client.get_module('Contacts').get_contact(jid)
        gateway_register = contact.is_gateway and contact.supports(
            Namespace.REGISTER)
        menu = get_roster_menu(
            self._account, jid, gateway=gateway_register)

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
        self._filter_string = text.lower()
        self._filter_enabled = bool(text)
        self._refilter()

    def _visible_func(self, model, iter_, *_data):
        if not self._filter_enabled:
            return True

        if not model[iter_][Column.IS_CONTACT]:
            return True

        return self._filter_string in model[iter_][Column.TEXT].lower()

    def _get_contact_visible(self, contact):
        if self._filter_enabled:
            return self._filter_string in contact.name.lower()

        if app.settings.get('showoffline'):
            return True

        if contact.show is PresenceShowExt.OFFLINE:
            return False

        return True

    def _set_model(self):
        self._roster.set_model(self._modelfilter)

    def _unset_model(self):
        self._roster.set_model(None)

    def redraw(self):
        self._unset_model()
        self._set_model()
        self._roster.expand_all()

    def _reset_roster(self):
        self._unset_model()
        self._enable_sort(False)
        self._clear()
        self._initial_draw()

    def _enable_sort(self, enable):
        column = Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID
        if enable:
            column = Column.TEXT

        self._store.set_sort_column_id(column, Gtk.SortType.ASCENDING)

    def _initial_draw(self):
        for contact in self._client.get_module('Roster').iter_contacts():
            self._connect_contact_signals(contact)
            self._add_or_update_contact(contact)

        self._enable_sort(True)
        self._set_model()
        self._roster.expand_all()

    def _connect_contact_signals(self, contact):
        contact.connect('presence-update', self._on_contact_update)
        contact.connect('caps-update', self._on_contact_update)
        contact.connect('avatar-update', self._on_contact_update)
        contact.connect('blocking-update', self._on_contact_update)

    def _on_contact_update(self, contact, _signal_name):
        self._draw_contact(contact)

    @event_filter(['account'])
    def _on_roster_received(self, _event):
        self._reset_roster()

    @event_filter(['account'])
    def _on_roster_push(self, event):
        contact = self._get_contact(event.item.jid)

        if event.item.subscription == 'remove':
            contact.disconnect(self)
            self._remove_contact(contact)
        else:
            if contact.jid not in self._contact_refs:
                self._connect_contact_signals(contact)
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

    def _refilter(self):
        if self._high_performance:
            self._modelfilter.refilter()
            self._roster.expand_all()
            return

        for group in self._store:
            group_is_visible = False
            for child in group.iterchildren():
                contact = self._get_contact(child[Column.JID_OR_GROUP])
                is_visible = self._get_contact_visible(contact)
                child[Column.VISIBLE] = is_visible
                if is_visible:
                    group_is_visible = True

            group[Column.VISIBLE] = group_is_visible
        self._roster.expand_all()

    def _draw_contact(self, contact):
        for ref in self._contact_refs[contact.jid]:
            self._draw_contact_row(ref, contact)
        self._roster.expand_all()

    def _draw_contact_row(self, ref, contact):
        iter_ = self._get_iter_from_ref(ref)

        name = GLib.markup_escape_text(contact.name)
        if contact.is_blocked:
            name = f'<span strikethrough="true">{name}</span>'
        self._store[iter_][Column.TEXT] = name

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

    def _clear(self):
        self._contact_refs.clear()
        self._group_refs.clear()
        self._store.clear()

    def process_event(self, event):
        if event.name not in HANDLED_EVENTS:
            return

    def _on_destroy(self, _roster):
        self._remove_actions()
        self._contact_refs.clear()
        self._group_refs.clear()
        self._unset_model()
        self._roster = None
        self._enable_sort(False)
        self._store.clear()
        self._store = None
        # self._tooltip.destroy()
        # self._tooltip = None
        app.check_finalize(self)
