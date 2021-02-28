import logging
from typing import Optional
from enum import IntEnum

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GObject

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .util import get_builder

log = logging.getLogger('gajim.gui.roster')


HANDLED_EVENTS = [
    'presence-received',
]


class Column(IntEnum):
    AVATAR = 0
    TEXT = 1
    EVENT = 2
    IS_CONTACT = 3
    NICK_OR_GROUP = 4


class Roster(Gtk.ScrolledWindow):

    __gsignals__ = {
        'row-activated': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,  # return value
            (str, ))  # arguments
    }

    def __init__(self, account):
        Gtk.ScrolledWindow.__init__(self)
        self.set_size_request(300, -1)

        self._account = account

        self._handler_ids = {}

        self._ui = get_builder('roster.ui')
        self._ui.roster_treeview.set_model(None)
        self.add(self._ui.roster_treeview)

        # Holds the Gtk.TreeRowReference for each contact
        self._contact_refs = {}
        # Holds the Gtk.TreeRowReference for each group
        self._group_refs = {}

        self._store = self._ui.contact_store

        self._roster = self._ui.roster_treeview

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self._initial_draw()

    def _on_roster_row_activated(self, _treeview, path, _column):
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # This is a group row
            return

        nick = self._store[iter_][Column.NICK_OR_GROUP]
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

        if event.button == 3:  # right click
            self._show_contact_menu(nick)

        if event.button == 2:  # middle click
            self.emit('row-activated', nick)

    @staticmethod
    def _on_focus_out(treeview, _param):
        treeview.get_selection().unselect_all()

    def _show_contact_menu(self, nick):
        pass

    def _on_destroy(self, _roster):
        for id_ in list(self._handler_ids.keys()):
            if self._handler_ids[id_].handler_is_connected(id_):
                self._handler_ids[id_].disconnect(id_)
            del self._handler_ids[id_]

        self._contact_refs = {}
        self._group_refs = {}
        self._roster.set_model(None)
        self._roster = None
        self._store.clear()
        self._store = None
        # self._tooltip.destroy()
        # self._tooltip = None

    def set_model(self):
        self._roster.set_model(self._store)

    def _initial_draw(self):
        client = app.get_client(self._account)
        for contact in client.get_module('Roster').iter_contacts():
            contact.connect('presence-update', self._on_presence_update)
            contact.connect('avatar-update', self._on_avatar_update)
            self._add_contact(contact)

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
                        None, (None, group_name, None, False, group_name))
                group_path = self._store.get_path(group_iter)
                group_ref = Gtk.TreeRowReference(self._store, group_path)
                self._group_refs[group_name] = group_ref
        else:
            group_iter = self._get_group_iter(main_group)
            if not group_iter:
                group_iter = self._store.append(
                    None, (None, main_group, None, False, main_group))
            group_path = self._store.get_path(group_iter)
            group_ref = Gtk.TreeRowReference(self._store, group_path)
            self._group_refs[main_group] = group_ref

        # Avatar
        surface = contact.get_avatar(AvatarSize.CHAT, self.get_scale_factor())

        iter_ = self._store.append(
            group_iter, (surface, contact.name, None, True, contact.name))
        self._contact_refs[contact.jid] = Gtk.TreeRowReference(
            self._store, self._store.get_path(iter_))

        self.draw_groups()
        self.draw_contact(contact.jid)

        if (group_path is not None and
                self._roster.get_model() is not None):
            self._roster.expand_row(group_path, False)

    def draw_groups(self):
        for group in self._group_refs:
            self.draw_group(group)

    def draw_group(self, group):
        group_iter = self._get_group_iter(group)
        if not group_iter:
            return

        self._store[group_iter][Column.TEXT] = group

    def draw_contacts(self):
        for jid in self._contact_refs:
            self.draw_contact(jid)

    def draw_contact(self, jid):
        iter_ = self._get_contact_iter(jid)
        if not iter_:
            return

        client = app.get_client(self._account)
        contact = client.get_module('Contacts').get_contact(jid)

        self.draw_avatar(contact)
        self._store[iter_][Column.TEXT] = GLib.markup_escape_text(contact.name)

    def draw_avatar(self, contact):
        iter_ = self._get_contact_iter(contact.jid)
        if iter_ is None:
            return

        surface = contact.get_avatar(
            AvatarSize.ROSTER, self.get_scale_factor())
        self._store[iter_][Column.AVATAR] = surface

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
