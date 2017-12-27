# -*- coding: utf-8 -*-
## src/roster_window.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
##                    Tomasz Melcer <liori AT exroot.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
import os
import time
import locale
import hashlib

from enum import IntEnum, unique

from gajim.common import sleepy
from gajim import history_window
from gajim import dialogs
from gajim import vcard
from gajim import config
from gajim import disco
from gajim import gtkgui_helpers
from gajim import gui_menu_builder
from gajim import cell_renderer_image
from gajim import tooltips
from gajim import message_control
from gajim import adhoc_commands
from gajim.common.const import AvatarSize

from gajim.common import app
from gajim.common import helpers
from gajim.common.exceptions import GajimGeneralException
from gajim.common import i18n
if app.HAVE_GEOCLUE:
    from gajim.common import location_listener
from gajim.common import ged
from gajim.common import dbus_support
from gajim.message_window import MessageWindowMgr
from nbxmpp.protocol import NS_FILE, NS_ROSTERX, NS_CONFERENCE


@unique
class Column(IntEnum):
    IMG = 0  # image to show state (online, new message etc)
    NAME = 1  # cellrenderer text that holds contact nickame
    TYPE = 2  # account, group or contact?
    JID = 3  # the jid of the row
    ACCOUNT = 4  # cellrenderer text that holds account name
    MOOD_PIXBUF = 5
    ACTIVITY_PIXBUF = 6
    TUNE_PIXBUF = 7
    LOCATION_PIXBUF = 8
    AVATAR_IMG = 9  # avatar_sha
    PADLOCK_PIXBUF = 10  # use for account row only
    VISIBLE = 11

empty_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1, 1)
empty_pixbuf.fill(0xffffff00)


class RosterWindow:
    """
    Class for main window of the GTK+ interface
    """

    def _get_account_iter(self, name, model=None):
        """
        Return the Gtk.TreeIter of the given account or None if not found

        Keyword arguments:
        name -- the account name
        model -- the data model (default TreeFilterModel)
        """
        if model is None:
            model = self.modelfilter
            if model is None:
                return

        if self.regroup:
            name = 'MERGED'
        if name not in self._iters:
            return None
        it = self._iters[name]['account']

        if model == self.model or it is None:
            return it
        try:
            (ok, it) = self.modelfilter.convert_child_iter_to_iter(it)
            if ok:
                return it
            return None
        except RuntimeError:
            return None


    def _get_group_iter(self, name, account, model=None):
        """
        Return the Gtk.TreeIter of the given group or None if not found

        Keyword arguments:
        name -- the group name
        account -- the account name
        model -- the data model (default TreeFilterModel)
        """
        if model is None:
            model = self.modelfilter
            if model is None:
                return

        if self.regroup:
            account = 'MERGED'

        if account not in self._iters:
            return None
        if name not in self._iters[account]['groups']:
            return None

        it = self._iters[account]['groups'][name]
        if model == self.model or it is None:
            return it
        try:
            (ok, it) = self.modelfilter.convert_child_iter_to_iter(it)
            if ok:
                return it
            return None
        except RuntimeError:
            return None


    def _get_self_contact_iter(self, account, model=None):
        """
        Return the Gtk.TreeIter of SelfContact or None if not found

        Keyword arguments:
        account -- the account of SelfContact
        model -- the data model (default TreeFilterModel)
        """
        jid = app.get_jid_from_account(account)
        its = self._get_contact_iter(jid, account, model=model)
        if its:
            return its[0]
        return None


    def _get_contact_iter(self, jid, account, contact=None, model=None):
        """
        Return a list of Gtk.TreeIter of the given contact

        Keyword arguments:
        jid -- the jid without resource
        account -- the account
        contact -- the contact (default None)
        model -- the data model (default TreeFilterModel)
        """
        if model is None:
            model = self.modelfilter
            # when closing Gajim model can be none (async pbs?)
            if model is None:
                return []

        if not contact:
            contact = app.contacts.get_first_contact_from_jid(account, jid)
            if not contact:
                # We don't know this contact
                return []

        if account not in self._iters:
            return []

        if jid not in self._iters[account]['contacts']:
            return []

        its = self._iters[account]['contacts'][jid]

        if not its:
            return []

        if model == self.model:
            return its

        its2 = []
        for it in its:
            try:
                (ok, it) = self.modelfilter.convert_child_iter_to_iter(it)
                if ok:
                    its2.append(it)
            except RuntimeError:
                pass
        return its2

    @staticmethod
    def _iter_is_separator(model, titer):
        """
        Return True if the given iter is a separator

        Keyword arguments:
        model -- the data model
        iter -- the Gtk.TreeIter to test
        """
        if model[titer][0] == 'SEPARATOR':
            return True
        return False

    @staticmethod
    def _status_cell_data_func(cell_layout, cell, tree_model, iter_):
        if isinstance(cell, Gtk.CellRendererPixbuf):
            icon_name = tree_model[iter_][1]
            if icon_name is None:
                return
            if tree_model[iter_][2] == 'status':
                cell.set_property('icon_name', icon_name)
            else:
                iconset_name = gtkgui_helpers.get_iconset_name_for(icon_name)
                cell.set_property('icon_name', iconset_name)
        else:
            show = tree_model[iter_][0]
            id_ = tree_model[iter_][2]
            if id_ not in ('status', 'desync'):
                show = helpers.get_uf_show(show)
            cell.set_property('text', show)



#############################################################################
### Methods for adding and removing roster window items
#############################################################################

    def add_account(self, account):
        """
        Add account to roster and draw it. Do nothing if it is already in
        """
        if self._get_account_iter(account):
            # Will happen on reconnect or for merged accounts
            return

        if self.regroup:
            # Merged accounts view
            show = helpers.get_global_show()
            image = gtkgui_helpers.get_image_from_icon_name(
                show, self.scale_factor)
            it = self.model.append(None, [
                image,
                _('Merged accounts'), 'account', '', 'all', None, None, None,
                None, None, None, True] + [None] * self.nb_ext_renderers)
            self._iters['MERGED']['account'] = it
        else:
            show = app.SHOW_LIST[app.connections[account].connected]
            our_jid = app.get_jid_from_account(account)

            tls_pixbuf = None
            if app.account_is_securely_connected(account):
                tls_pixbuf = 'changes-prevent'

            image = gtkgui_helpers.get_image_from_icon_name(
                show, self.scale_factor)
            it = self.model.append(None, [
                image,
                GLib.markup_escape_text(account), 'account', our_jid,
                account, None, None, None, None, None, tls_pixbuf, True] +
                [None] * self.nb_ext_renderers)
            self._iters[account]['account'] = it

        self.draw_account(account)


    def add_account_contacts(self, account, improve_speed=True,
    draw_contacts=True):
        """
        Add all contacts and groups of the given account to roster, draw them
        and account
        """
        if improve_speed:
            self._before_fill()
        jids = app.contacts.get_jid_list(account)

        for jid in jids:
            self.add_contact(jid, account)

        if draw_contacts:
            # Do not freeze the GUI when drawing the contacts
            if jids:
                # Overhead is big, only invoke when needed
                self._idle_draw_jids_of_account(jids, account)

            # Draw all known groups
            for group in app.groups[account]:
                self.draw_group(group, account)
            self.draw_account(account)

        if improve_speed:
            self._after_fill()

    def _add_group_iter(self, account, group):
        """
        Add a group iter in roster and return the newly created iter
        """
        if self.regroup:
            account_group = 'MERGED'
        else:
            account_group = account
        delimiter = app.connections[account].nested_group_delimiter
        group_splited = group.split(delimiter)
        parent_group = delimiter.join(group_splited[:-1])
        if len(group_splited) > 1 and parent_group in self._iters[account_group]['groups']:
            iter_parent = self._iters[account_group]['groups'][parent_group]
        elif parent_group:
            iter_parent = self._add_group_iter(account, parent_group)
            if parent_group not in app.groups[account]:
                if account + parent_group in self.collapsed_rows:
                    is_expanded = False
                else:
                    is_expanded = True
                app.groups[account][parent_group] = {'expand': is_expanded}
        else:
            iter_parent = self._get_account_iter(account, self.model)

        image = gtkgui_helpers.get_image_from_icon_name(
            'closed', self.scale_factor)
        iter_group = self.model.append(iter_parent,
            [image,
            GLib.markup_escape_text(group), 'group', group, account, None,
            None, None, None, None, None, False] + [None] * self.nb_ext_renderers)
        self.draw_group(group, account)
        self._iters[account_group]['groups'][group] = iter_group
        return iter_group

    def _add_entity(self, contact, account, groups=None,
    big_brother_contact=None, big_brother_account=None):
        """
        Add the given contact to roster data model

        Contact is added regardless if he is already in roster or not. Return
        list of newly added iters.

        Keyword arguments:
        contact -- the contact to add
        account -- the contacts account
        groups -- list of groups to add the contact to.
                  (default groups in contact.get_shown_groups()).
                Parameter ignored when big_brother_contact is specified.
        big_brother_contact -- if specified contact is added as child
                  big_brother_contact. (default None)
        """
        added_iters = []
        visible = self.contact_is_visible(contact, account)
        if big_brother_contact:
            # Add contact under big brother

            parent_iters = self._get_contact_iter(
                    big_brother_contact.jid, big_brother_account,
                    big_brother_contact, self.model)
            assert len(parent_iters) > 0, 'Big brother is not yet in roster!'

            # Do not confuse get_contact_iter: Sync groups of family members
            contact.groups = big_brother_contact.groups[:]

            for child_iter in parent_iters:
                it = self.model.append(child_iter, [None,
                    contact.get_shown_name(), 'contact', contact.jid, account,
                    None, None, None, None, None, None, visible] + \
                    [None] * self.nb_ext_renderers)
                added_iters.append(it)
                if contact.jid in self._iters[account]['contacts']:
                    self._iters[account]['contacts'][contact.jid].append(it)
                else:
                    self._iters[account]['contacts'][contact.jid] = [it]
        else:
            # We are a normal contact. Add us to our groups.
            if not groups:
                groups = contact.get_shown_groups()
            for group in groups:
                child_iterG = self._get_group_iter(group, account,
                    model=self.model)
                if not child_iterG:
                    # Group is not yet in roster, add it!
                    child_iterG = self._add_group_iter(account, group)

                if contact.is_transport():
                    typestr = 'agent'
                elif contact.is_groupchat():
                    typestr = 'groupchat'
                else:
                    typestr = 'contact'

                # we add some values here. see draw_contact
                # for more
                i_ = self.model.append(child_iterG, [None,
                    contact.get_shown_name(), typestr, contact.jid, account,
                    None, None, None, None, None, None, visible] + \
                    [None] * self.nb_ext_renderers)
                added_iters.append(i_)
                if contact.jid in self._iters[account]['contacts']:
                    self._iters[account]['contacts'][contact.jid].append(i_)
                else:
                    self._iters[account]['contacts'][contact.jid] = [i_]

                # Restore the group expand state
                if account + group in self.collapsed_rows:
                    is_expanded = False
                else:
                    is_expanded = True
                if group not in app.groups[account]:
                    app.groups[account][group] = {'expand': is_expanded}

        assert len(added_iters), '%s has not been added to roster!' % \
        contact.jid
        return added_iters

    def _remove_entity(self, contact, account, groups=None):
        """
        Remove the given contact from roster data model

        Empty groups after contact removal are removed too.
        Return False if contact still has children and deletion was
        not performed.
        Return True on success.

        Keyword arguments:
        contact -- the contact to add
        account -- the contacts account
        groups -- list of groups to remove the contact from.
        """
        iters = self._get_contact_iter(contact.jid, account, contact,
            self.model)
        assert iters, '%s shall be removed but is not in roster' % contact.jid

        parent_iter = self.model.iter_parent(iters[0])
        parent_type = self.model[parent_iter][Column.TYPE]

        if groups:
            # Only remove from specified groups
            all_iters = iters[:]
            group_iters = [self._get_group_iter(group, account)
                    for group in groups]
            iters = [titer for titer in all_iters
                    if self.model.iter_parent(titer) in group_iters]

        iter_children = self.model.iter_children(iters[0])

        if iter_children:
            # We have children. We cannot be removed!
            return False
        # Remove us and empty groups from the model
        for i in iters:
            assert self.model[i][Column.JID] == contact.jid and \
                    self.model[i][Column.ACCOUNT] == account, \
                    "Invalidated iters of %s" % contact.jid

            parent_i = self.model.iter_parent(i)
            parent_type = self.model[parent_i][Column.TYPE]

            to_be_removed = i
            while parent_type == 'group' and \
            self.model.iter_n_children(parent_i) == 1:
                if self.regroup:
                    account_group = 'MERGED'
                else:
                    account_group = account
                group = self.model[parent_i][Column.JID]
                if group in app.groups[account]:
                    del app.groups[account][group]
                to_be_removed = parent_i
                del self._iters[account_group]['groups'][group]
                parent_i = self.model.iter_parent(parent_i)
                parent_type = self.model[parent_i][Column.TYPE]
            self.model.remove(to_be_removed)

        del self._iters[account]['contacts'][contact.jid]
        return True

    def _add_metacontact_family(self, family, account):
        """
        Add the give Metacontact family to roster data model

        Add Big Brother to his groups and all others under him.
        Return list of all added (contact, account) tuples with
        Big Brother as first element.

        Keyword arguments:
        family -- the family, see Contacts.get_metacontacts_family()
        """

        nearby_family, big_brother_jid, big_brother_account = \
                self._get_nearby_family_and_big_brother(family, account)
        if not big_brother_jid:
            return []
        big_brother_contact = app.contacts.get_first_contact_from_jid(
                big_brother_account, big_brother_jid)

        assert len(self._get_contact_iter(big_brother_jid,
                big_brother_account, big_brother_contact, self.model)) == 0, \
                'Big brother %s already in roster\n Family: %s' \
                % (big_brother_jid, family)
        self._add_entity(big_brother_contact, big_brother_account)

        brothers = []
        # Filter family members
        for data in nearby_family:
            _account = data['account']
            _jid = data['jid']
            _contact = app.contacts.get_first_contact_from_jid(
                    _account, _jid)

            if not _contact or _contact == big_brother_contact:
                # Corresponding account is not connected
                # or brother already added
                continue

            assert len(self._get_contact_iter(_jid, _account,
                    _contact, self.model)) == 0, \
                    "%s already in roster.\n Family: %s" % (_jid, nearby_family)
            self._add_entity(_contact, _account,
                    big_brother_contact = big_brother_contact,
                    big_brother_account = big_brother_account)
            brothers.append((_contact, _account))

        brothers.insert(0, (big_brother_contact, big_brother_account))
        return brothers

    def _remove_metacontact_family(self, family, account):
        """
        Remove the given Metacontact family from roster data model

        See Contacts.get_metacontacts_family() and
        RosterWindow._remove_entity()
        """
        nearby_family = self._get_nearby_family_and_big_brother(
                family, account)[0]

        # Family might has changed (actual big brother not on top).
        # Remove childs first then big brother
        family_in_roster = False
        for data in nearby_family:
            _account = data['account']
            _jid = data['jid']
            _contact = app.contacts.get_first_contact_from_jid(_account, _jid)

            iters = self._get_contact_iter(_jid, _account, _contact, self.model)
            if not iters or not _contact:
                # Family might not be up to date.
                # Only try to remove what is actually in the roster
                continue
            assert iters, '%s shall be removed but is not in roster \
                    \n Family: %s' % (_jid, family)

            family_in_roster = True

            parent_iter = self.model.iter_parent(iters[0])
            parent_type = self.model[parent_iter][Column.TYPE]

            if parent_type != 'contact':
                # The contact on top
                old_big_account = _account
                old_big_contact = _contact
                old_big_jid = _jid
                continue

            ok = self._remove_entity(_contact, _account)
            assert ok, '%s was not removed' % _jid
            assert len(self._get_contact_iter(_jid, _account, _contact,
                self.model)) == 0, '%s is removed but still in roster' % _jid

        if not family_in_roster:
            return False

        assert old_big_jid, 'No Big Brother in nearby family %s (Family: %s)' %\
            (nearby_family, family)
        iters = self._get_contact_iter(old_big_jid, old_big_account,
            old_big_contact, self.model)
        assert len(iters) > 0, 'Old Big Brother %s is not in roster anymore' % \
            old_big_jid
        assert not self.model.iter_children(iters[0]), \
            'Old Big Brother %s still has children' % old_big_jid

        ok = self._remove_entity(old_big_contact, old_big_account)
        assert ok, "Old Big Brother %s not removed" % old_big_jid
        assert len(self._get_contact_iter(old_big_jid, old_big_account,
            old_big_contact, self.model)) == 0, \
            'Old Big Brother %s is removed but still in roster' % old_big_jid

        return True

    def _recalibrate_metacontact_family(self, family, account):
        """
        Regroup metacontact family if necessary
        """

        brothers = []
        nearby_family, big_brother_jid, big_brother_account = \
            self._get_nearby_family_and_big_brother(family, account)
        big_brother_contact = app.contacts.get_contact(big_brother_account,
            big_brother_jid)
        child_iters = self._get_contact_iter(big_brother_jid,
            big_brother_account, model=self.model)
        if child_iters:
            parent_iter = self.model.iter_parent(child_iters[0])
            parent_type = self.model[parent_iter][Column.TYPE]

            # Check if the current BigBrother has even been before.
            if parent_type == 'contact':
                for data in nearby_family:
                    # recalibrate after remove to keep highlight
                    if data['jid'] in app.to_be_removed[data['account']]:
                        return

                self._remove_metacontact_family(family, account)
                brothers = self._add_metacontact_family(family, account)

                for c, acc in brothers:
                    self.draw_completely(c.jid, acc)

        # Check is small brothers are under the big brother
        for child in nearby_family:
            _jid = child['jid']
            _account = child['account']
            if _account == big_brother_account and _jid == big_brother_jid:
                continue
            child_iters = self._get_contact_iter(_jid, _account,
                model=self.model)
            if not child_iters:
                continue
            parent_iter = self.model.iter_parent(child_iters[0])
            parent_type = self.model[parent_iter][Column.TYPE]
            if parent_type != 'contact':
                _contact = app.contacts.get_contact(_account, _jid)
                self._remove_entity(_contact, _account)
                self._add_entity(_contact, _account, groups=None,
                        big_brother_contact=big_brother_contact,
                        big_brother_account=big_brother_account)

    def _get_nearby_family_and_big_brother(self, family, account):
        return app.contacts.get_nearby_family_and_big_brother(family, account)

    def _add_self_contact(self, account):
        """
        Add account's SelfContact to roster and draw it and the account

        Return the SelfContact contact instance
        """
        jid = app.get_jid_from_account(account)
        contact = app.contacts.get_first_contact_from_jid(account, jid)

        assert len(self._get_contact_iter(jid, account, contact,
        self.model)) == 0, 'Self contact %s already in roster' % jid

        child_iterA = self._get_account_iter(account, self.model)
        self._iters[account]['contacts'][jid] = [self.model.append(child_iterA,
            [None, app.nicks[account], 'self_contact', jid, account, None,
            None, None, None, None, None, True] + [None] * self.nb_ext_renderers)]

        self.draw_completely(jid, account)
        self.draw_account(account)

        return contact

    def redraw_metacontacts(self, account):
        for family in app.contacts.iter_metacontacts_families(account):
            self._recalibrate_metacontact_family(family, account)

    def add_contact(self, jid, account):
        """
        Add contact to roster and draw him

        Add contact to all its group and redraw the groups, the contact and the
        account. If it's a Metacontact, add and draw the whole family.
        Do nothing if the contact is already in roster.

        Return the added contact instance. If it is a Metacontact return
        Big Brother.

        Keyword arguments:
        jid -- the contact's jid or SelfJid to add SelfContact
        account -- the corresponding account.
        """
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        if len(self._get_contact_iter(jid, account, contact, self.model)):
            # If contact already in roster, do nothing
            return

        if jid == app.get_jid_from_account(account):
            show_self_contact = app.config.get('show_self_contact')
            if show_self_contact == 'never':
                return
            if (contact.resource != app.connections[account].server_resource \
            and show_self_contact == 'when_other_resource') or \
            show_self_contact == 'always':
                return self._add_self_contact(account)
            return

        is_observer = contact.is_observer()
        if is_observer:
            # if he has a tag, remove it
            app.contacts.remove_metacontact(account, jid)

        # Add contact to roster
        family = app.contacts.get_metacontacts_family(account, jid)
        contacts = []
        if family:
            # We have a family. So we are a metacontact.
            # Add all family members that we shall be grouped with
            if self.regroup:
                # remove existing family members to regroup them
                self._remove_metacontact_family(family, account)
            contacts = self._add_metacontact_family(family, account)
        else:
            # We are a normal contact
            contacts = [(contact, account), ]
            self._add_entity(contact, account)

        # Draw the contact and its groups contact
        if not self.starting:
            for c, acc in contacts:
                self.draw_completely(c.jid, acc)
            for group in contact.get_shown_groups():
                self.draw_group(group, account)
                self._adjust_group_expand_collapse_state(group, account)
            self.draw_account(account)

        return contacts[0][0] # it's contact/big brother with highest priority

    def remove_contact(self, jid, account, force=False, backend=False):
        """
        Remove contact from roster

        Remove contact from all its group. Remove empty groups or redraw
        otherwise.
        Draw the account.
        If it's a Metacontact, remove the whole family.
        Do nothing if the contact is not in roster.

        Keyword arguments:
        jid -- the contact's jid or SelfJid to remove SelfContact
        account -- the corresponding account.
        force -- remove contact even it has pending evens (Default False)
        backend -- also remove contact instance (Default False)
        """
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        if not contact:
            return

        if not force and self.contact_has_pending_roster_events(contact,
        account):
            return False

        iters = self._get_contact_iter(jid, account, contact, self.model)
        if iters:
            # no more pending events
            # Remove contact from roster directly
            family = app.contacts.get_metacontacts_family(account, jid)
            if family:
                # We have a family. So we are a metacontact.
                self._remove_metacontact_family(family, account)
            else:
                self._remove_entity(contact, account)

        old_grps = []
        if backend:
            if not app.interface.msg_win_mgr.get_control(jid, account) or \
            force:
                # If a window is still opened: don't remove contact instance
                # Remove contact before redrawing, otherwise the old
                # numbers will still be show
                app.contacts.remove_jid(account, jid, remove_meta=True)
                if iters:
                    rest_of_family = [data for data in family
                        if account != data['account'] or jid != data['jid']]
                    if rest_of_family:
                        # reshow the rest of the family
                        brothers = self._add_metacontact_family(rest_of_family,
                            account)
                        for c, acc in brothers:
                            self.draw_completely(c.jid, acc)
            else:
                for c in app.contacts.get_contacts(account, jid):
                    c.sub = 'none'
                    c.show = 'not in roster'
                    c.status = ''
                    old_grps = c.get_shown_groups()
                    c.groups = [_('Not in Roster')]
                    self._add_entity(c, account)
                    self.draw_contact(jid, account)

        if iters:
            # Draw all groups of the contact
            for group in contact.get_shown_groups() + old_grps:
                self.draw_group(group, account)
            self.draw_account(account)

        return True

    def rename_self_contact(self, old_jid, new_jid, account):
        """
        Rename the self_contact jid

        Keyword arguments:
        old_jid -- our old jid
        new_jid -- our new jid
        account -- the corresponding account.
        """
        app.contacts.change_contact_jid(old_jid, new_jid, account)
        self_iter = self._get_self_contact_iter(account, model=self.model)
        if not self_iter:
            return
        self.model[self_iter][Column.JID] = new_jid
        self.draw_contact(new_jid, account)

    def add_groupchat(self, jid, account, status=''):
        """
        Add groupchat to roster and draw it. Return the added contact instance
        """
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        # Do not show gc if we are disconnected and minimize it
        if app.account_is_connected(account):
            show = 'online'
        else:
            show = 'offline'
            status = ''

        if contact is None:
            gc_control = app.interface.msg_win_mgr.get_gc_control(jid,
                account)
            if gc_control:
                # there is a window that we can minimize
                app.interface.minimized_controls[account][jid] = gc_control
                name = gc_control.name
            elif jid in app.interface.minimized_controls[account]:
                name = app.interface.minimized_controls[account][jid].name
            else:
                name = jid.split('@')[0]
            # New groupchat
            contact = app.contacts.create_contact(jid=jid, account=account,
                name=name, groups=[_('Groupchats')], show=show, status=status,
                sub='none')
            app.contacts.add_contact(account, contact)
            self.add_contact(jid, account)
        else:
            if jid not in app.interface.minimized_controls[account]:
                # there is a window that we can minimize
                gc_control = app.interface.msg_win_mgr.get_gc_control(jid,
                        account)
                app.interface.minimized_controls[account][jid] = gc_control
            contact.show = show
            contact.status = status
            self.adjust_and_draw_contact_context(jid, account)

        return contact


    def remove_groupchat(self, jid, account):
        """
        Remove groupchat from roster and redraw account and group
        """
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        if contact.is_groupchat():
            if jid in app.interface.minimized_controls[account]:
                del app.interface.minimized_controls[account][jid]
            self.remove_contact(jid, account, force=True, backend=True)
            return True
        else:
            return False


    # FIXME: This function is yet unused! Port to new API
    def add_transport(self, jid, account):
        """
        Add transport to roster and draw it. Return the added contact instance
        """
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        if contact is None:
            contact = app.contacts.create_contact(jid=jid, account=account,
                name=jid, groups=[_('Transports')], show='offline',
                status='offline', sub='from')
            app.contacts.add_contact(account, contact)
        self.add_contact(jid, account)
        return contact

    def remove_transport(self, jid, account):
        """
        Remove transport from roster and redraw account and group
        """
        self.remove_contact(jid, account, force=True, backend=True)
        return True

    def rename_group(self, old_name, new_name, account):
        """
        Rename a roster group
        """
        if old_name == new_name:
            return

        # Groups may not change name from or to a special groups
        for g in helpers.special_groups:
            if g in (new_name, old_name):
                return

        # update all contacts in the given group
        if self.regroup:
            accounts = app.connections.keys()
        else:
            accounts = [account, ]

        for acc in accounts:
            changed_contacts = []
            for jid in app.contacts.get_jid_list(acc):
                contact = app.contacts.get_first_contact_from_jid(acc, jid)
                if old_name not in contact.groups:
                    continue

                self.remove_contact(jid, acc, force=True)

                contact.groups.remove(old_name)
                if new_name not in contact.groups:
                    contact.groups.append(new_name)

                changed_contacts.append({'jid': jid, 'name': contact.name,
                    'groups':contact.groups})

            app.connections[acc].update_contacts(changed_contacts)

            for c in changed_contacts:
                self.add_contact(c['jid'], acc)

            self._adjust_group_expand_collapse_state(new_name, acc)

            self.draw_group(old_name, acc)
            self.draw_group(new_name, acc)


    def add_contact_to_groups(self, jid, account, groups, update=True):
        """
        Add contact to given groups and redraw them

        Contact on server is updated too. When the contact has a family,
        the action will be performed for all members.

        Keyword Arguments:
        jid -- the jid
        account -- the corresponding account
        groups -- list of Groups to add the contact to.
        update -- update contact on the server
        """
        self.remove_contact(jid, account, force=True)
        for contact in app.contacts.get_contacts(account, jid):
            for group in groups:
                if group not in contact.groups:
                    # we might be dropped from meta to group
                    contact.groups.append(group)
            if update:
                app.connections[account].update_contact(jid, contact.name,
                        contact.groups)

        self.add_contact(jid, account)

        for group in groups:
            self._adjust_group_expand_collapse_state(group, account)

    def remove_contact_from_groups(self, jid, account, groups, update=True):
        """
        Remove contact from given groups and redraw them

        Contact on server is updated too. When the contact has a family,
        the action will be performed for all members.

        Keyword Arguments:
        jid -- the jid
        account -- the corresponding account
        groups -- list of Groups to remove the contact from
        update -- update contact on the server
        """
        self.remove_contact(jid, account, force=True)
        for contact in app.contacts.get_contacts(account, jid):
            for group in groups:
                if group in contact.groups:
                    # Needed when we remove from "General" or "Observers"
                    contact.groups.remove(group)
            if update:
                app.connections[account].update_contact(jid, contact.name,
                        contact.groups)
        self.add_contact(jid, account)

        # Also redraw old groups
        for group in groups:
            self.draw_group(group, account)

    # FIXME: maybe move to app.py
    def remove_newly_added(self, jid, account):
        if account not in app.newly_added:
            # Account has been deleted during the timeout that called us
            return
        if jid in app.newly_added[account]:
            app.newly_added[account].remove(jid)
            self.draw_contact(jid, account)

    # FIXME: maybe move to app.py
    def remove_to_be_removed(self, jid, account):
        if account not in app.interface.instances:
            # Account has been deleted during the timeout that called us
            return
        if jid in app.newly_added[account]:
            return
        if jid in app.to_be_removed[account]:
            app.to_be_removed[account].remove(jid)
            family = app.contacts.get_metacontacts_family(account, jid)
            if family:
                # Peform delayed recalibration
                self._recalibrate_metacontact_family(family, account)
            self.draw_contact(jid, account)
            # Hide Group if all childs are hidden
            contact = app.contacts.get_contact(account, jid)
            if not contact:
                return
            for group in contact.get_shown_groups():
                self.draw_group(group, account)

    # FIXME: integrate into add_contact()
    def add_to_not_in_the_roster(self, account, jid, nick='', resource=''):
        keyID = ''
        attached_keys = app.config.get_per('accounts', account,
                'attached_gpg_keys').split()
        if jid in attached_keys:
            keyID = attached_keys[attached_keys.index(jid) + 1]
        contact = app.contacts.create_not_in_roster_contact(jid=jid,
                account=account, resource=resource, name=nick, keyID=keyID)
        app.contacts.add_contact(account, contact)
        self.add_contact(contact.jid, account)
        return contact


################################################################################
### Methods for adding and removing roster window items
################################################################################

    def _really_draw_account(self, account):
        child_iter = self._get_account_iter(account, self.model)
        if not child_iter:
            assert False, 'Account iter of %s could not be found.' % account
            return

        num_of_accounts = app.get_number_of_connected_accounts()
        num_of_secured = app.get_number_of_securely_connected_accounts()

        tls_pixbuf = None
        if app.account_is_securely_connected(account) and not self.regroup or\
        self.regroup and num_of_secured and num_of_secured == num_of_accounts:
            tls_pixbuf = 'changes-prevent'
            self.model[child_iter][Column.PADLOCK_PIXBUF] = tls_pixbuf

        if self.regroup:
            account_name = _('Merged accounts')
            accounts = []
        else:
            acclabel = app.config.get_per('accounts', account, 'account_label')
            account_name = acclabel or account
            accounts = [account]

        if account in self.collapsed_rows and \
        self.model.iter_has_child(child_iter):
            account_name = '[%s]' % account_name

        if (app.account_is_connected(account) or (self.regroup and \
        app.get_number_of_connected_accounts())) and app.config.get(
        'show_contacts_number'):
            nbr_on, nbr_total = app.contacts.get_nb_online_total_contacts(
                    accounts = accounts)
            account_name += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))

        self.model[child_iter][Column.NAME] = GLib.markup_escape_text(account_name)

        pep_dict = app.connections[account].pep
        if app.config.get('show_mood_in_roster') and 'mood' in pep_dict:
            self.model[child_iter][Column.MOOD_PIXBUF] = \
                gtkgui_helpers.get_pep_as_pixbuf(pep_dict['mood'])
        else:
            self.model[child_iter][Column.MOOD_PIXBUF] = empty_pixbuf

        if app.config.get('show_activity_in_roster') and 'activity' in \
        pep_dict:
            self.model[child_iter][Column.ACTIVITY_PIXBUF] = \
                gtkgui_helpers.get_pep_as_pixbuf(pep_dict['activity'])
        else:
            self.model[child_iter][Column.ACTIVITY_PIXBUF] = empty_pixbuf

        if app.config.get('show_tunes_in_roster') and 'tune' in pep_dict:
            self.model[child_iter][Column.TUNE_PIXBUF] = \
                gtkgui_helpers.get_pep_as_pixbuf(pep_dict['tune'])
        else:
            self.model[child_iter][Column.TUNE_PIXBUF] = empty_pixbuf

        if app.config.get('show_location_in_roster') and 'location' in \
        pep_dict:
            self.model[child_iter][Column.LOCATION_PIXBUF] = \
                gtkgui_helpers.get_pep_as_pixbuf(pep_dict['location'])
        else:
            self.model[child_iter][Column.LOCATION_PIXBUF] = empty_pixbuf

    def _really_draw_accounts(self):
        for acct in self.accounts_to_draw:
            self._really_draw_account(acct)
        self.accounts_to_draw = []
        return False

    def draw_account(self, account):
        if account in self.accounts_to_draw:
            return
        self.accounts_to_draw.append(account)
        if len(self.accounts_to_draw) == 1:
            GLib.timeout_add(200, self._really_draw_accounts)

    def _really_draw_group(self, group, account):
        child_iter = self._get_group_iter(group, account, model=self.model)
        if not child_iter:
            # Eg. We redraw groups after we removed a entitiy
            # and its empty groups
            return
        if self.regroup:
            accounts = []
        else:
            accounts = [account]
        text = GLib.markup_escape_text(group)
        if helpers.group_is_blocked(account, group):
            text = '<span strikethrough="true">%s</span>' % text
        if app.config.get('show_contacts_number'):
            nbr_on, nbr_total = app.contacts.get_nb_online_total_contacts(
                    accounts = accounts, groups = [group])
            text += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))

        self.model[child_iter][Column.NAME] = text

        # Hide group if no more contacts
        iterG = self._get_group_iter(group, account, model=self.modelfilter)
        to_hide = []
        while(iterG):
            parent = self.modelfilter.iter_parent(iterG)
            if (not self.modelfilter.iter_has_child(iterG)) or (len(to_hide) > \
            0 and self.modelfilter.iter_n_children(iterG) == 1):
                to_hide.append(iterG)
                if not parent or self.modelfilter[parent][Column.TYPE] != \
                'group':
                    iterG = None
                else:
                    iterG = parent
            else:
                iterG = None
        for iter_ in to_hide:
            self.modelfilter[iter_][Column.VISIBLE] = False

    def _really_draw_groups(self):
        for ag in self.groups_to_draw.values():
            acct = ag['account']
            grp = ag['group']
            self._really_draw_group(grp, acct)
        self.groups_to_draw = {}
        return False

    def draw_group(self, group, account):
        ag = account + group
        if ag in self.groups_to_draw:
            return
        self.groups_to_draw[ag] = {'group': group, 'account': account}
        if len(self.groups_to_draw) == 1:
            GLib.timeout_add(200, self._really_draw_groups)

    def draw_parent_contact(self, jid, account):
        child_iters = self._get_contact_iter(jid, account, model=self.model)
        if not child_iters:
            return False
        parent_iter = self.model.iter_parent(child_iters[0])
        if self.model[parent_iter][Column.TYPE] != 'contact':
            # parent is not a contact
            return
        parent_jid = self.model[parent_iter][Column.JID]
        parent_account = self.model[parent_iter][Column.ACCOUNT]
        self.draw_contact(parent_jid, parent_account)
        return False

    def draw_contact(self, jid, account, selected=False, focus=False,
    contact_instances=None, contact=None):
        """
        Draw the correct state image, name BUT not avatar
        """
        # focus is about if the roster window has toplevel-focus or not
        # FIXME: We really need a custom cell_renderer

        if not contact_instances:
            contact_instances = app.contacts.get_contacts(account, jid)
        if not contact:
            contact = app.contacts.get_highest_prio_contact_from_contacts(
                contact_instances)
        if not contact:
            return False

        child_iters = self._get_contact_iter(jid, account, contact, self.model)
        if not child_iters:
            return False

        name = GLib.markup_escape_text(contact.get_shown_name())

        # gets number of unread gc marked messages
        if jid in app.interface.minimized_controls[account] and \
        app.interface.minimized_controls[account][jid]:
            nb_unread = len(app.events.get_events(account, jid,
                    ['printed_marked_gc_msg']))
            nb_unread += app.interface.minimized_controls \
                    [account][jid].get_nb_unread_pm()

            if nb_unread == 1:
                name = '%s *' % name
            elif nb_unread > 1:
                name = '%s [%s]' % (name, str(nb_unread))

        # Strike name if blocked
        strike = False
        if helpers.jid_is_blocked(account, jid):
            strike = True
        else:
            for group in contact.get_shown_groups():
                if helpers.group_is_blocked(account, group):
                    strike = True
                    break
        if strike:
            name = '<span strikethrough="true">%s</span>' % name

        # Show resource counter
        nb_connected_contact = 0
        for c in contact_instances:
            if c.show not in ('error', 'offline'):
                nb_connected_contact += 1
        if nb_connected_contact > 1:
            # switch back to default writing direction
            name += i18n.paragraph_direction_mark(name)
            name += ' (%d)' % nb_connected_contact

        # add status msg, if not empty, under contact name in
        # the treeview
        if contact.status and app.config.get('show_status_msgs_in_roster'):
            status = contact.status.strip()
            if status != '':
                status = helpers.reduce_chars_newlines(status,
                    max_lines = 1)
                # escape markup entities and make them small
                # italic and fg color color is calcuted to be
                # always readable
                color = gtkgui_helpers.get_fade_color(self.tree, selected,
                    focus)
                colorstring = '#%04x%04x%04x' % (int(color.red * 65535),
                    int(color.green * 65535), int(color.blue * 65535))
                name += '\n<span size="small" style="italic" ' \
                    'foreground="%s">%s</span>' % (colorstring,
                    GLib.markup_escape_text(status))

        icon_name = helpers.get_icon_name_to_show(contact, account)
        # look if another resource has awaiting events
        for c in contact_instances:
            c_icon_name = helpers.get_icon_name_to_show(c, account)
            if c_icon_name in ('event', 'muc-active', 'muc-inactive'):
                icon_name = c_icon_name
                break

        # Check for events of collapsed (hidden) brothers
        family = app.contacts.get_metacontacts_family(account, jid)
        is_big_brother = False
        have_visible_children = False
        if family:
            bb_jid, bb_account = \
                self._get_nearby_family_and_big_brother(family, account)[1:]
            is_big_brother = (jid, account) == (bb_jid, bb_account)
            iters = self._get_contact_iter(jid, account)
            have_visible_children = iters and \
                self.modelfilter.iter_has_child(iters[0])

        if have_visible_children:
            # We are the big brother and have a visible family
            for child_iter in child_iters:
                child_path = self.model.get_path(child_iter)
                path = self.modelfilter.convert_child_path_to_path(child_path)

                if not path:
                    continue

                if not self.tree.row_expanded(path) and icon_name != 'event':
                    iterC = self.model.iter_children(child_iter)
                    while iterC:
                        # a child has awaiting messages?
                        jidC = self.model[iterC][Column.JID]
                        accountC = self.model[iterC][Column.ACCOUNT]
                        if len(app.events.get_events(accountC, jidC)):
                            icon_name = 'event'
                            break
                        iterC = self.model.iter_next(iterC)

                expanded = self.tree.row_expanded(path)
                image = gtkgui_helpers.draw_metacontact(
                    icon_name, expanded, self.scale_factor)

                # Expand/collapse icon might differ per iter
                # (group)
                self.model[child_iter][Column.IMG] = image
                self.model[child_iter][Column.NAME] = name
                #TODO: compute visible
                visible = True
                self.model[child_iter][Column.VISIBLE] = visible
        else:
            # A normal contact or little brother
            image = gtkgui_helpers.get_image_from_icon_name(
                icon_name, self.scale_factor)

            visible = self.contact_is_visible(contact, account)

            for child_iter in child_iters:
                self.model[child_iter][Column.IMG] = image
                self.model[child_iter][Column.NAME] = name
                self.model[child_iter][Column.VISIBLE] = visible
                if visible:
                    parent_iter = self.model.iter_parent(child_iter)
                    self.model[parent_iter][Column.VISIBLE] = True

            # We are a little brother
            if family and not is_big_brother and not self.starting:
                self.draw_parent_contact(jid, account)

        if visible:
            delimiter = app.connections[account].nested_group_delimiter
            for group in contact.get_shown_groups():
                group_splited = group.split(delimiter)
                i = 1
                while i < len(group_splited) + 1:
                    g = delimiter.join(group_splited[:i])
                    iterG = self._get_group_iter(g, account, model=self.model)
                    if iterG:
                        # it's not self contact
                        self.model[iterG][Column.VISIBLE] = True
                    i += 1

        app.plugin_manager.gui_extension_point('roster_draw_contact', self,
            jid, account, contact)

        return False

    def _is_pep_shown_in_roster(self, pep_type):
        if pep_type == 'mood':
            return app.config.get('show_mood_in_roster')
        elif pep_type == 'activity':
            return app.config.get('show_activity_in_roster')
        elif pep_type == 'tune':
            return  app.config.get('show_tunes_in_roster')
        elif pep_type == 'location':
            return  app.config.get('show_location_in_roster')
        else:
            return False

    def draw_all_pep_types(self, jid, account, contact=None):
        for pep_type in self._pep_type_to_model_column:
            self.draw_pep(jid, account, pep_type, contact=contact)

    def draw_pep(self, jid, account, pep_type, contact=None):
        if pep_type not in self._pep_type_to_model_column:
            return
        if not self._is_pep_shown_in_roster(pep_type):
            return

        model_column = self._pep_type_to_model_column[pep_type]
        iters = self._get_contact_iter(jid, account, model=self.model)
        if not iters:
            return
        if not contact:
            contact = app.contacts.get_contact(account, jid)
        if pep_type in contact.pep:
            pixbuf = gtkgui_helpers.get_pep_as_pixbuf(contact.pep[pep_type])
        else:
            pixbuf = empty_pixbuf
        for child_iter in iters:
            self.model[child_iter][model_column] = pixbuf

    def draw_avatar(self, jid, account):
        iters = self._get_contact_iter(jid, account, model=self.model)
        if not iters or not app.config.get('show_avatars_in_roster'):
            return
        jid = self.model[iters[0]][Column.JID]

        scale = self.window.get_scale_factor()
        surface = app.contacts.get_avatar(
            account, jid, AvatarSize.ROSTER, scale)
        image = Gtk.Image.new_from_surface(surface)
        for child_iter in iters:
            self.model[child_iter][Column.AVATAR_IMG] = image
        return False

    def draw_completely(self, jid, account):
        contact_instances = app.contacts.get_contacts(account, jid)
        contact = app.contacts.get_highest_prio_contact_from_contacts(
            contact_instances)
        self.draw_contact(jid, account, contact_instances=contact_instances,
            contact=contact)
        self.draw_all_pep_types(jid, account, contact=contact)
        self.draw_avatar(jid, account)

    def adjust_and_draw_contact_context(self, jid, account):
        """
        Draw contact, account and groups of given jid Show contact if it has
        pending events
        """
        contact = app.contacts.get_first_contact_from_jid(account, jid)
        if not contact:
            # idle draw or just removed SelfContact
            return

        family = app.contacts.get_metacontacts_family(account, jid)
        if family:
            # There might be a new big brother
            self._recalibrate_metacontact_family(family, account)
        self.draw_contact(jid, account)
        self.draw_account(account)

        for group in contact.get_shown_groups():
            self.draw_group(group, account)
            self._adjust_group_expand_collapse_state(group, account)

    def _idle_draw_jids_of_account(self, jids, account):
        """
        Draw given contacts and their avatars in a lazy fashion

        Keyword arguments:
        jids -- a list of jids to draw
        account -- the corresponding account
        """
        def _draw_all_contacts(jids, account):
            for jid in jids:
                family = app.contacts.get_metacontacts_family(account, jid)
                if family:
                    # For metacontacts over several accounts:
                    # When we connect a new account existing brothers
                    # must be redrawn (got removed and readded)
                    for data in family:
                        self.draw_completely(data['jid'], data['account'])
                else:
                    self.draw_completely(jid, account)
                yield True
            self.refilter_shown_roster_items()
            yield False

        task = _draw_all_contacts(jids, account)
        GLib.idle_add(next, task)

    def _before_fill(self):
        self.tree.freeze_child_notify()
        self.tree.set_model(None)
        # disable sorting
        self.model.set_sort_column_id(-2, Gtk.SortType.ASCENDING)
        self.starting = True
        self.starting_filtering = True

    def _after_fill(self):
        self.starting = False
        accounts_list = app.contacts.get_accounts()
        for account in app.connections:
            if account not in accounts_list:
                continue

            jids = app.contacts.get_jid_list(account)
            for jid in jids:
                self.draw_completely(jid, account)

            # Draw all known groups
            for group in app.groups[account]:
                self.draw_group(group, account)
            self.draw_account(account)

        self.model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.tree.set_model(self.modelfilter)
        self.tree.thaw_child_notify()
        self.starting_filtering = False
        self.refilter_shown_roster_items()

    def setup_and_draw_roster(self):
        """
        Create new empty model and draw roster
        """
        self.modelfilter = None
        self.model = Gtk.TreeStore(*self.columns)

        self.model.set_sort_func(1, self._compareIters)
        self.model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.modelfilter = self.model.filter_new()
        self.modelfilter.set_visible_func(self._visible_func)
        self.modelfilter.connect('row-has-child-toggled',
                self.on_modelfilter_row_has_child_toggled)
        self.tree.set_model(self.modelfilter)

        self._iters = {}
        # for merged mode
        self._iters['MERGED'] = {'account': None, 'groups': {}}
        for acct in app.contacts.get_accounts():
            self._iters[acct] = {'account': None, 'groups': {}, 'contacts': {}}

        for acct in app.contacts.get_accounts():
            self.add_account(acct)
            self.add_account_contacts(acct, improve_speed=True,
                draw_contacts=False)

        # Recalculate column width for ellipsizing
        self.tree.columns_autosize()


    def select_contact(self, jid, account):
        """
        Select contact in roster. If contact is hidden but has events, show him
        """
        # Refiltering SHOULD NOT be needed:
        # When a contact gets a new event he will be redrawn and his
        # icon changes, so _visible_func WILL be called on him anyway
        iters = self._get_contact_iter(jid, account)
        if not iters:
            # Not visible in roster
            return
        path = self.modelfilter.get_path(iters[0])
        if self.dragging or not app.config.get(
        'scroll_roster_to_last_message'):
            # do not change selection while DND'ing
            return
        # Expand his parent, so this path is visible, don't expand it.
        path.up()
        self.tree.expand_to_path(path)
        self.tree.scroll_to_cell(path)
        self.tree.set_cursor(path)

    def _readjust_expand_collapse_state(self):
        def func(model, path, iter_, param):
            type_ = model[iter_][Column.TYPE]
            acct = model[iter_][Column.ACCOUNT]
            jid = model[iter_][Column.JID]
            key = None
            if type_ == 'account':
                key = acct
            elif type_ == 'group':
                key = acct + jid
            elif type_ == 'contact':
                parent_iter = model.iter_parent(iter_)
                ptype = model[parent_iter][Column.TYPE]
                if ptype == 'group':
                    grp = model[parent_iter][Column.JID]
                    key = acct + grp + jid
            if key:
                if key in self.collapsed_rows:
                    self.tree.collapse_row(path)
                else:
                    self.tree.expand_row(path, False)
        self.modelfilter.foreach(func, None)

    def _adjust_account_expand_collapse_state(self, account):
        """
        Expand/collapse account row based on self.collapsed_rows
        """
        if not self.tree.get_model():
            return
        iterA = self._get_account_iter(account)
        if not iterA:
            # thank you modelfilter
            return
        path = self.modelfilter.get_path(iterA)
        if account in self.collapsed_rows:
            self.tree.collapse_row(path)
        else:
            self.tree.expand_row(path, False)
        return False


    def _adjust_group_expand_collapse_state(self, group, account):
        """
        Expand/collapse group row based on self.collapsed_rows
        """
        if not self.tree.get_model():
            return
        if account not in app.connections:
            return
        delimiter = app.connections[account].nested_group_delimiter
        group_splited = group.split(delimiter)
        i = 1
        while i < len(group_splited) + 1:
            g = delimiter.join(group_splited[:i])
            iterG = self._get_group_iter(g, account)
            if not iterG:
                # Group not visible
                return
            path = self.modelfilter.get_path(iterG)
            if account + g in self.collapsed_rows:
                self.tree.collapse_row(path)
            else:
                self.tree.expand_row(path, False)
            i += 1

##############################################################################
### Roster and Modelfilter handling
##############################################################################

    def refilter_shown_roster_items(self):
        if self.filtering:
            return
        self.filtering = True
        for account in app.connections:
            for jid in app.contacts.get_jid_list(account):
                self.adjust_and_draw_contact_context(jid, account)
        self.filtering = False

    def contact_has_pending_roster_events(self, contact, account):
        """
        Return True if the contact or one if it resources has pending events
        """
        # jid has pending events
        if app.events.get_nb_roster_events(account, contact.jid) > 0:
            return True
        # check events of all resources
        for contact_ in app.contacts.get_contacts(account, contact.jid):
            if contact_.resource and app.events.get_nb_roster_events(account,
            contact_.get_full_jid()) > 0:
                return True
        return False

    def contact_is_visible(self, contact, account):
        if self.rfilter_enabled:
            return self.rfilter_string in contact.get_shown_name().lower()
        if self.contact_has_pending_roster_events(contact, account):
            return True
        if app.config.get('showoffline'):
            return True

        if contact.show in ('offline', 'error'):
            if contact.jid in app.to_be_removed[account]:
                return True
            return False
        if app.config.get('show_only_chat_and_online') and contact.show in (
        'away', 'xa', 'busy'):
            return False
        if _('Transports') in contact.get_shown_groups():
            return app.config.get('show_transports_group')
        return True

    def _visible_func(self, model, titer, dummy):
        """
        Determine whether iter should be visible in the treeview
        """
        if self.starting_filtering:
            return False

        visible = model[titer][Column.VISIBLE]

        type_ = model[titer][Column.TYPE]
        if not type_:
            return False
        if type_ == 'account':
            # Always show account
            return True

        account = model[titer][Column.ACCOUNT]
        if not account:
            return False

        jid = model[titer][Column.JID]
        if not jid:
            return False

        if not self.rfilter_enabled:
            return visible

        if type_ == 'group':
            group = jid
            if group == _('Transports'):
                if self.regroup:
                    accounts = app.contacts.get_accounts()
                else:
                    accounts = [account]
                for _acc in accounts:
                    for contact in app.contacts.iter_contacts(_acc):
                        if group in contact.get_shown_groups():
                            if self.rfilter_string in \
                            contact.get_shown_name().lower():
                                return True
                        elif self.contact_has_pending_roster_events(contact,
                        _acc):
                            return True
                    # No transport has been found
                    return False

        if type_ == 'contact':
            if model.iter_has_child(titer):
                iter_c = model.iter_children(titer)
                while iter_c:
                    if self.rfilter_string in model[iter_c][Column.NAME].lower():
                        return True
                    iter_c = model.iter_next(iter_c)
            return self.rfilter_string in model[titer][Column.NAME].lower()

        if type_ == 'agent':
            return self.rfilter_string in model[titer][Column.NAME].lower()

        if type_ == 'groupchat':
            return self.rfilter_string in model[titer][Column.NAME].lower()

        return visible

    def _compareIters(self, model, iter1, iter2, data=None):
        """
        Compare two iters to sort them
        """
        name1 = model[iter1][Column.NAME]
        name2 = model[iter2][Column.NAME]
        if not name1 or not name2:
            return 0
        type1 = model[iter1][Column.TYPE]
        type2 = model[iter2][Column.TYPE]
        if type1 == 'self_contact':
            return -1
        if type2 == 'self_contact':
            return 1
        if type1 == 'group':
            name1 = model[iter1][Column.JID]
            name2 = model[iter2][Column.JID]
            if name1 == _('Transports'):
                return 1
            if name2 == _('Transports'):
                return -1
            if name1 == _('Not in Roster'):
                return 1
            if name2 == _('Not in Roster'):
                return -1
            if name1 == _('Groupchats'):
                return 1
            if name2 == _('Groupchats'):
                return -1
        account1 = model[iter1][Column.ACCOUNT]
        account2 = model[iter2][Column.ACCOUNT]
        if not account1 or not account2:
            return 0
        if type1 == 'account':
            return locale.strcoll(account1, account2)
        jid1 = model[iter1][Column.JID]
        jid2 = model[iter2][Column.JID]
        if type1 == 'contact':
            lcontact1 = app.contacts.get_contacts(account1, jid1)
            contact1 = app.contacts.get_first_contact_from_jid(account1, jid1)
            if not contact1:
                return 0
            name1 = contact1.get_shown_name()
        if type2 == 'contact':
            lcontact2 = app.contacts.get_contacts(account2, jid2)
            contact2 = app.contacts.get_first_contact_from_jid(account2, jid2)
            if not contact2:
                return 0
            name2 = contact2.get_shown_name()
        # We first compare by show if sort_by_show_in_roster is True or if it's
        # a child contact
        if type1 == 'contact' and type2 == 'contact' and \
        app.config.get('sort_by_show_in_roster'):
            cshow = {'chat':0, 'online': 1, 'away': 2, 'xa': 3, 'dnd': 4,
                'invisible': 5, 'offline': 6, 'not in roster': 7, 'error': 8}
            s = self.get_show(lcontact1)
            show1 = cshow.get(s, 9)
            s = self.get_show(lcontact2)
            show2 = cshow.get(s, 9)
            removing1 = False
            removing2 = False
            if show1 == 6 and jid1 in app.to_be_removed[account1]:
                removing1 = True
            if show2 == 6 and jid2 in app.to_be_removed[account2]:
                removing2 = True
            if removing1 and not removing2:
                return 1
            if removing2 and not removing1:
                return -1
            sub1 = contact1.sub
            sub2 = contact2.sub
            # none and from goes after
            if sub1 not in ['none', 'from'] and sub2 in ['none', 'from']:
                return -1
            if sub1 in ['none', 'from'] and sub2 not in ['none', 'from']:
                return 1
            if show1 < show2:
                return -1
            elif show1 > show2:
                return 1
        # We compare names
        cmp_result = locale.strcoll(name1.lower(), name2.lower())
        if cmp_result < 0:
            return -1
        if cmp_result > 0:
            return 1
        if type1 == 'contact' and type2 == 'contact':
            # We compare account names
            cmp_result = locale.strcoll(account1.lower(), account2.lower())
            if cmp_result < 0:
                return -1
            if cmp_result > 0:
                return 1
            # We compare jids
            cmp_result = locale.strcoll(jid1.lower(), jid2.lower())
            if cmp_result < 0:
                return -1
            if cmp_result > 0:
                return 1
        return 0

################################################################################
### FIXME: Methods that don't belong to roster window...
###             ... atleast not in there current form
################################################################################

    def fire_up_unread_messages_events(self, account):
        """
        Read from db the unread messages, and fire them up, and if we find very
        old unread messages, delete them from unread table
        """
        results = app.logger.get_unread_msgs()
        for result, shown in results:
            jid = result.jid
            additional_data = result.additional_data
            if app.contacts.get_first_contact_from_jid(account, jid) and not \
            shown:
                # We have this jid in our contacts list
                # XXX unread messages should probably have their session saved
                # with them
                session = app.connections[account].make_new_session(jid)

                tim = float(result.time)
                session.roster_message(jid, result.message, tim, msg_type='chat',
                    msg_log_id=result.log_line_id, additional_data=additional_data)
                app.logger.set_shown_unread_msgs(result.log_line_id)

            elif (time.time() - result.time) > 2592000:
                # ok, here we see that we have a message in unread messages
                # table that is older than a month. It is probably from someone
                # not in our roster for accounts we usually launch, so we will
                # delete this id from unread message tables.
                app.logger.set_read_messages([result.log_line_id])

    def fill_contacts_and_groups_dicts(self, array, account):
        """
        Fill app.contacts and app.groups
        """
        # FIXME: This function needs to be splitted
        # Most of the logic SHOULD NOT be done at GUI level
        if account not in app.contacts.get_accounts():
            app.contacts.add_account(account)
        if not account in self._iters:
            self._iters[account] = {'account': None, 'groups': {},
                'contacts': {}}
        if account not in app.groups:
            app.groups[account] = {}
        if app.config.get('show_self_contact') == 'always':
            self_jid = app.get_jid_from_account(account)
            if app.connections[account].server_resource:
                self_jid += '/' + app.connections[account].server_resource
            array[self_jid] = {'name': app.nicks[account],
                'groups': ['self_contact'], 'subscription': 'both',
                'ask': 'none'}

        # .keys() is needed
        for jid in list(array.keys()):
            # Remove the contact in roster. It might has changed
            self.remove_contact(jid, account, force=True)
            # Remove old Contact instances
            app.contacts.remove_jid(account, jid, remove_meta=False)
            jids = jid.split('/')
            # get jid
            ji = jids[0]
            # get resource
            resource = ''
            if len(jids) > 1:
                resource = '/'.join(jids[1:])
            # get name
            name = array[jid]['name'] or ''
            show = 'offline' # show is offline by default
            status = '' # no status message by default

            keyID = ''
            attached_keys = app.config.get_per('accounts', account,
                'attached_gpg_keys').split()
            if jid in attached_keys:
                keyID = attached_keys[attached_keys.index(jid) + 1]

            if app.jid_is_transport(jid):
                array[jid]['groups'] = [_('Transports')]
            #TRANSP - potential
            contact1 = app.contacts.create_contact(jid=ji, account=account,
                name=name, groups=array[jid]['groups'], show=show,
                status=status, sub=array[jid]['subscription'],
                ask=array[jid]['ask'], resource=resource, keyID=keyID)
            app.contacts.add_contact(account, contact1)

            # If we already have chat windows opened, update them with new
            # contact instance
            chat_control = app.interface.msg_win_mgr.get_control(ji, account)
            if chat_control:
                chat_control.contact = contact1

    def connected_rooms(self, account):
        if account in list(app.gc_connected[account].values()):
            return True
        return False

    def on_event_removed(self, event_list):
        """
        Remove contacts on last events removed

        Only performed if removal was requested before but the contact still had
        pending events
        """

        msg_log_ids = []
        for ev in event_list:
            if ev.type_ != 'printed_chat':
                continue
            if ev.msg_log_id:
                # There is a msg_log_id
                msg_log_ids.append(ev.msg_log_id)

        if msg_log_ids:
            app.logger.set_read_messages(msg_log_ids)

        contact_list = ((event.jid.split('/')[0], event.account) for event in \
                event_list)

        for jid, account in contact_list:
            self.draw_contact(jid, account)
            # Remove contacts in roster if removal was requested
            key = (jid, account)
            if key in list(self.contacts_to_be_removed.keys()):
                backend = self.contacts_to_be_removed[key]['backend']
                del self.contacts_to_be_removed[key]
                # Remove contact will delay removal if there are more events
                # pending
                self.remove_contact(jid, account, backend=backend)
        self.show_title()

    def open_event(self, account, jid, event):
        """
        If an event was handled, return True, else return False
        """
        ft = app.interface.instances['file_transfers']
        event = app.events.get_first_event(account, jid, event.type_)
        if event.type_ == 'normal':
            dialogs.SingleMessageWindow(account, jid,
                action='receive', from_whom=jid, subject=event.subject,
                message=event.message, resource=event.resource,
                session=event.session, form_node=event.form_node)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ == 'file-request':
            contact = app.contacts.get_contact_with_highest_priority(account,
                    jid)
            ft.show_file_request(account, contact, event.file_props)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ in ('file-request-error', 'file-send-error'):
            ft.show_send_error(event.file_props)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ in ('file-error', 'file-stopped'):
            msg_err = ''
            if event.file_props.error == -1:
                msg_err = _('Remote contact stopped transfer')
            elif event.file_props.error == -6:
                msg_err = _('Error opening file')
            ft.show_stopped(jid, event.file_props, error_msg=msg_err)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ == 'file-hash-error':
            ft.show_hash_error(jid, event.file_props, account)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ == 'file-completed':
            ft.show_completed(jid, event.file_props)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ == 'gc-invitation':
            dialogs.InvitationReceivedDialog(account, event.room_jid,
                event.jid_from, event.password, event.reason,
                is_continued=event.is_continued)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ == 'subscription_request':
            dialogs.SubscriptionRequestWindow(jid, event.text, account,
                event.nick)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ == 'unsubscribed':
            app.interface.show_unsubscribed_dialog(account, event.contact)
            app.events.remove_events(account, jid, event)
            return True
        elif event.type_ == 'jingle-incoming':
            dialogs.VoIPCallReceivedDialog(account, event.peerjid, event.sid,
                event.content_types)
            app.events.remove_events(account, jid, event)
            return True
        return False

################################################################################
### This and that... random.
################################################################################

    def show_roster_vbox(self, active):
        vb = self.xml.get_object('roster_vbox2')
        if active:
            vb.set_no_show_all(False)
            vb.show()
        else:
            vb.hide()
            vb.set_no_show_all(True)

    def authorize(self, widget, jid, account):
        """
        Authorize a contact (by re-sending auth menuitem)
        """
        app.connections[account].send_authorization(jid)
        dialogs.InformationDialog(_('Authorization sent'),
            _('"%s" will now see your status.') %jid)

    def req_sub(self, widget, jid, txt, account, groups=None, nickname=None,
                    auto_auth=False):
        """
        Request subscription to a contact
        """
        groups_list = groups or []
        app.connections[account].request_subscription(jid, txt, nickname,
            groups_list, auto_auth, app.nicks[account])
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        if not contact:
            keyID = ''
            attached_keys = app.config.get_per('accounts', account,
                'attached_gpg_keys').split()
            if jid in attached_keys:
                keyID = attached_keys[attached_keys.index(jid) + 1]
            contact = app.contacts.create_contact(jid=jid, account=account,
                name=nickname, groups=groups_list, show='requested', status='',
                ask='none', sub='subscribe', keyID=keyID)
            app.contacts.add_contact(account, contact)
        else:
            if not _('Not in Roster') in contact.get_shown_groups():
                dialogs.InformationDialog(_('Subscription request has been '
                    'sent'), _('If "%s" accepts this request you will know his '
                    'or her status.') % jid)
                return
            self.remove_contact(contact.jid, account, force=True)
            contact.groups = groups_list
            if nickname:
                contact.name = nickname
        self.add_contact(jid, account)

    def revoke_auth(self, widget, jid, account):
        """
        Revoke a contact's authorization
        """
        app.connections[account].refuse_authorization(jid)
        dialogs.InformationDialog(_('Authorization removed'),
            _('Now "%s" will always see you as offline.') %jid)

    def set_state(self, account, state):
        child_iterA = self._get_account_iter(account, self.model)
        if child_iterA:
            image = gtkgui_helpers.get_image_from_icon_name(
                state, self.scale_factor)
            self.model[child_iterA][Column.IMG] = image
        if app.interface.systray_enabled:
            app.interface.systray.change_status(state)

    def set_connecting_state(self, account):
        self.set_state(account, 'connecting')

    def send_status(self, account, status, txt, auto=False, to=None):
        if status != 'offline':
            if to is None:
                app.config.set_per('accounts', account, 'last_status', status)
                app.config.set_per('accounts', account, 'last_status_msg',
                        helpers.to_one_line(txt))
            if app.connections[account].connected < 2:
                self.set_connecting_state(account)

                keyid = app.config.get_per('accounts', account, 'keyid')
                if keyid and not app.connections[account].gpg:
                    dialogs.WarningDialog(_('OpenPGP is not usable'),
                        _('Gajim needs python-gnupg >= 0.3.8\n'
                          'Beware there is an incompatible python package called gnupg.\n'
                          'You will be connected to %s without OpenPGP.') % account)

        self.send_status_continue(account, status, txt, auto, to)

    def send_pep(self, account, pep_dict):
        connection = app.connections[account]

        if 'activity' in pep_dict:
            activity = pep_dict['activity']
            subactivity = pep_dict.get('subactivity', None)
            activity_text = pep_dict.get('activity_text', None)
            connection.send_activity(activity, subactivity, activity_text)
        else:
            connection.retract_activity()

        if 'mood' in pep_dict:
            mood = pep_dict['mood']
            mood_text = pep_dict.get('mood_text', None)
            connection.send_mood(mood, mood_text)
        else:
            connection.retract_mood()

    def delete_pep(self, jid, account):
        if jid == app.get_jid_from_account(account):
            app.connections[account].pep = {}
            self.draw_account(account)

        for contact in app.contacts.get_contacts(account, jid):
            contact.pep = {}

        self.draw_all_pep_types(jid, account)
        ctrl = app.interface.msg_win_mgr.get_control(jid, account)
        if ctrl:
            ctrl.update_all_pep_types()

    def send_status_continue(self, account, status, txt, auto, to):
        if app.account_is_connected(account) and not to:
            if status == 'online' and app.interface.sleeper.getState() != \
            sleepy.STATE_UNKNOWN:
                app.sleeper_state[account] = 'online'
            elif app.sleeper_state[account] not in ('autoaway', 'autoxa') or \
            status == 'offline':
                app.sleeper_state[account] = 'off'

        if to:
            app.connections[account].send_custom_status(status, txt, to)
        else:
            if status in ('invisible', 'offline'):
                self.delete_pep(app.get_jid_from_account(account), account)
            was_invisible = app.connections[account].connected == \
                    app.SHOW_LIST.index('invisible')
            app.connections[account].change_status(status, txt, auto)

            if account in app.interface.status_sent_to_users:
                app.interface.status_sent_to_users[account] = {}
            if account in app.interface.status_sent_to_groups:
                app.interface.status_sent_to_groups[account] = {}
            for gc_control in app.interface.msg_win_mgr.get_controls(
            message_control.TYPE_GC) + \
            list(app.interface.minimized_controls[account].values()):
                if gc_control.account == account:
                    if app.gc_connected[account][gc_control.room_jid]:
                        app.connections[account].send_gc_status(
                            gc_control.nick, gc_control.room_jid, status, txt,
                            auto=auto)
            if was_invisible and status != 'offline':
                # We come back from invisible, join bookmarks
                app.interface.auto_join_bookmarks(account)


    def chg_contact_status(self, contact, show, status, account):
        """
        When a contact changes his or her status
        """
        contact_instances = app.contacts.get_contacts(account, contact.jid)
        contact.show = show
        contact.status = status
        # name is to show in conversation window
        name = contact.get_shown_name()
        fjid = contact.get_full_jid()

        # The contact has several resources
        if len(contact_instances) > 1:
            if contact.resource != '':
                name += '/' + contact.resource

            # Remove resource when going offline
            if show in ('offline', 'error') and \
            not self.contact_has_pending_roster_events(contact, account):
                ctrl = app.interface.msg_win_mgr.get_control(fjid, account)
                if ctrl:
                    ctrl.update_ui()
                    ctrl.parent_win.redraw_tab(ctrl)
                    # keep the contact around, since it's
                    # already attached to the control
                else:
                    app.contacts.remove_contact(account, contact)

        elif contact.jid == app.get_jid_from_account(account) and \
        show in ('offline', 'error'):
            if app.config.get('show_self_contact') != 'never':
                # SelfContact went offline. Remove him when last pending
                # message was read
                self.remove_contact(contact.jid, account, backend=True)

        uf_show = helpers.get_uf_show(show)

        # print status in chat window and update status/GPG image
        ctrl = app.interface.msg_win_mgr.get_control(contact.jid, account)
        if ctrl and ctrl.type_id != message_control.TYPE_GC:
            ctrl.contact = app.contacts.get_contact_with_highest_priority(
                account, contact.jid)
            ctrl.update_status_display(name, uf_show, status)

        if contact.resource:
            ctrl = app.interface.msg_win_mgr.get_control(fjid, account)
            if ctrl:
                ctrl.update_status_display(name, uf_show, status)

        # Delete pep if needed
        keep_pep = any(c.show not in ('error', 'offline') for c in
            contact_instances)
        if not keep_pep and contact.jid != app.get_jid_from_account(account) \
        and not contact.is_groupchat():
            self.delete_pep(contact.jid, account)

        # Redraw everything and select the sender
        self.adjust_and_draw_contact_context(contact.jid, account)


    def on_status_changed(self, account, show):
        """
        The core tells us that our status has changed
        """
        if account not in app.contacts.get_accounts():
            return
        child_iterA = self._get_account_iter(account, self.model)
        if app.config.get('show_self_contact') == 'always':
            self_resource = app.connections[account].server_resource
            self_contact = app.contacts.get_contact(account,
                    app.get_jid_from_account(account), resource=self_resource)
            if self_contact:
                status = app.connections[account].status
                self.chg_contact_status(self_contact, show, status, account)
        self.set_account_status_icon(account)
        if show == 'offline':
            if self.quit_on_next_offline > -1:
                # we want to quit, we are waiting for all accounts to be offline
                self.quit_on_next_offline -= 1
                if self.quit_on_next_offline < 1:
                    # all accounts offline, quit
                    self.quit_gtkgui_interface()
            else:
                # No need to redraw contacts if we're quitting
                if child_iterA:
                    self.model[child_iterA][Column.AVATAR_IMG] = None
                if account in app.con_types:
                    app.con_types[account] = None
                for jid in list(app.contacts.get_jid_list(account)):
                    lcontact = app.contacts.get_contacts(account, jid)
                    ctrl = app.interface.msg_win_mgr.get_gc_control(jid,
                        account)
                    for contact in [c for c in lcontact if (
                    (c.show != 'offline' or c.is_transport()) and not ctrl)]:
                        self.chg_contact_status(contact, 'offline', '', account)
        self.update_status_combobox()

    def get_status_message(self, show, on_response, show_pep=True,
                    always_ask=False):
        """
        Get the status message by:

        1/ looking in default status message
        2/ asking to user if needed depending on ask_on(ff)line_status and
                always_ask
        show_pep can be False to hide pep things from status message or True
        """
        empty_pep = {'activity': '', 'subactivity': '', 'activity_text': '',
            'mood': '', 'mood_text': ''}
        if show in app.config.get_per('defaultstatusmsg'):
            if app.config.get_per('defaultstatusmsg', show, 'enabled'):
                msg = app.config.get_per('defaultstatusmsg', show, 'message')
                msg = helpers.from_one_line(msg)
                on_response(msg, empty_pep)
                return
        if not always_ask and ((show == 'online' and not app.config.get(
        'ask_online_status')) or (show in ('offline', 'invisible') and not \
        app.config.get('ask_offline_status'))):
            on_response('', empty_pep)
            return

        dlg = dialogs.ChangeStatusMessageDialog(on_response, show, show_pep)
        dlg.dialog.present() # show it on current workspace

    def change_status(self, widget, account, status):
        def change(account, status):
            def on_response(message, pep_dict):
                if message is None:
                    # user pressed Cancel to change status message dialog
                    return
                self.send_status(account, status, message)
                self.send_pep(account, pep_dict)
            self.get_status_message(status, on_response)

        if status == 'invisible' and self.connected_rooms(account):
            dialogs.ConfirmationDialog(
                _('You are participating in one or more group chats'),
                _('Changing your status to invisible will result in '
                'disconnection from those group chats. Are you sure you want '
                'to go invisible?'), on_response_ok = (change, account, status))
        else:
            change(account, status)

    def update_status_combobox(self):
        # table to change index in connection.connected to index in combobox
        table = {'offline':9, 'connecting':9, 'online':0, 'chat':1, 'away':2,
            'xa':3, 'dnd':4, 'invisible':5}

        liststore = self.status_combobox.get_model()
        # we check if there are more options in the combobox that it should
        # if yes, we remove the first ones
        while len(liststore) > len(table)+2:
            titer = liststore.get_iter_first()
            liststore.remove(titer)

        show = helpers.get_global_show()
        # temporarily block signal in order not to send status that we show
        # in the combobox
        self.combobox_callback_active = False
        if helpers.statuses_unified():
            self.status_combobox.set_active(table[show])
        else:
            uf_show = helpers.get_uf_show(show)
            liststore.prepend(['SEPARATOR', None, '', True])
            status_combobox_text = uf_show + ' (' + _("desync'ed") + ')'
            liststore.prepend(
                [status_combobox_text, show, 'desync', False])
            self.status_combobox.set_active(0)
        self.combobox_callback_active = True
        if app.interface.systray_enabled:
            app.interface.systray.change_status(show)

    def get_show(self, lcontact):
        prio = lcontact[0].priority
        show = lcontact[0].show
        for u in lcontact:
            if u.priority > prio:
                prio = u.priority
                show = u.show
        return show

    def on_message_window_delete(self, win_mgr, msg_win):
        if app.config.get('one_message_window') == 'always_with_roster':
            self.show_roster_vbox(True)
            gtkgui_helpers.resize_window(self.window,
                    app.config.get('roster_width'),
                    app.config.get('roster_height'))

    def close_all_from_dict(self, dic):
        """
        Close all the windows in the given dictionary
        """
        for w in list(dic.values()):
            if isinstance(w, dict):
                self.close_all_from_dict(w)
            else:
                try:
                    w.window.destroy()
                except (AttributeError, RuntimeError):
                    w.destroy()

    def close_all(self, account, force=False):
        """
        Close all the windows from an account. If force is True, do not ask
        confirmation before closing chat/gc windows
        """
        if account in app.interface.instances:
            self.close_all_from_dict(app.interface.instances[account])
        for ctrl in app.interface.msg_win_mgr.get_controls(acct=account):
            ctrl.parent_win.remove_tab(ctrl, ctrl.parent_win.CLOSE_CLOSE_BUTTON,
                force=force)

    def on_roster_window_delete_event(self, widget, event):
        """
        Main window X button was clicked
        """
        if not app.config.get('quit_on_roster_x_button') and (
        (app.interface.systray_enabled and app.config.get('trayicon') != \
        'on_event') or app.config.get('allow_hide_roster')):
            if app.config.get('save-roster-position'):
                x, y = self.window.get_position()
                app.config.set('roster_x-position', x)
                app.config.set('roster_y-position', y)
            if app.config.get('hide_on_roster_x_button'):
                self.window.hide()
            else:
                self.window.iconify()
        elif app.config.get('quit_on_roster_x_button'):
            self.on_quit_request()
        else:
            def on_ok(checked):
                if checked:
                    app.config.set('quit_on_roster_x_button', True)
                self.on_quit_request()
            dialogs.ConfirmationDialogCheck(_('Really quit Gajim?'),
                    _('Are you sure you want to quit Gajim?'),
                    _('Always close Gajim'), on_response_ok=on_ok)
        return True # do NOT destroy the window

    def prepare_quit(self):
        if self.save_done:
            return
        msgwin_width_adjust = 0

        # in case show_roster_on_start is False and roster is never shown
        # window.window is None
        if self.window.get_window() is not None:
            if app.config.get('save-roster-position'):
                x, y = self.window.get_window().get_root_origin()
                app.config.set('roster_x-position', x)
                app.config.set('roster_y-position', y)
            width, height = self.window.get_size()
            app.config.set('roster_width', width)
            app.config.set('roster_height', height)
            if not self.xml.get_object('roster_vbox2').get_property('visible'):
                # The roster vbox is hidden, so the message window is larger
                # then we want to save (i.e. the window will grow every startup)
                # so adjust.
                msgwin_width_adjust = -1 * width
        app.config.set('last_roster_visible',
                self.window.get_property('visible'))
        app.interface.msg_win_mgr.save_opened_controls()
        app.interface.msg_win_mgr.shutdown(msgwin_width_adjust)

        app.config.set('collapsed_rows', '\t'.join(self.collapsed_rows))
        app.interface.save_config()
        for account in app.connections:
            app.connections[account].quit(True)
            self.close_all(account)
        if app.interface.systray_enabled:
            app.interface.hide_systray()
        self.save_done = True

    def quit_gtkgui_interface(self):
        """
        When we quit the gtk interface - exit gtk
        """
        self.prepare_quit()
        self.application.quit()

    def on_quit_request(self, widget=None):
        """
        User wants to quit. Check if he should be warned about messages pending.
        Terminate all sessions and send offline to all connected account. We do
        NOT really quit gajim here
        """
        accounts = list(app.connections.keys())
        get_msg = False
        for acct in accounts:
            if app.connections[acct].connected:
                get_msg = True
                break

        def on_continue3(message, pep_dict):
            self.quit_on_next_offline = 0
            accounts_to_disconnect = []
            for acct in accounts:
                if app.connections[acct].connected > 1:
                    self.quit_on_next_offline += 1
                    accounts_to_disconnect.append(acct)

            if not self.quit_on_next_offline:
                # all accounts offline, quit
                self.quit_gtkgui_interface()
                return

            for acct in accounts_to_disconnect:
                self.send_status(acct, 'offline', message)
                self.send_pep(acct, pep_dict)

        def on_continue2(message, pep_dict):
            # check if there is an active file transfer
            from gajim.common.protocol.bytestream import (is_transfer_active)
            files_props = app.interface.instances['file_transfers'].\
                files_props
            transfer_active = False
            for x in files_props:
                for y in files_props[x]:
                    if is_transfer_active(files_props[x][y]):
                        transfer_active = True
                        break

            if transfer_active:
                dialogs.ConfirmationDialog(_('You have running file transfers'),
                        _('If you quit now, the file(s) being transferred will '
                        'be stopped. Do you still want to quit?'),
                        on_response_ok=(on_continue3, message, pep_dict))
                return
            on_continue3(message, pep_dict)

        def on_continue(message, pep_dict):
            if message is None:
                # user pressed Cancel to change status message dialog
                return
            # check if we have unread messages
            unread = app.events.get_nb_events()
            if not app.config.get('notify_on_all_muc_messages'):
                unread_not_to_notify = app.events.get_nb_events(
                        ['printed_gc_msg'])
                unread -= unread_not_to_notify

            # check if we have recent messages
            recent = False
            for win in app.interface.msg_win_mgr.windows():
                for ctrl in win.controls():
                    fjid = ctrl.get_full_jid()
                    if fjid in app.last_message_time[ctrl.account]:
                        if time.time() - app.last_message_time[ctrl.account][
                        fjid] < 2:
                            recent = True
                            break
                if recent:
                    break

            if unread or recent:
                dialogs.ConfirmationDialog(_('You have unread messages'),
                    _('Messages will only be available for reading them later '
                    'if you have history enabled and contact is in your '
                    'roster.'), on_response_ok=(on_continue2,
                    message, pep_dict))
                return
            on_continue2(message, pep_dict)

        if get_msg:
            self.get_status_message('offline', on_continue, show_pep=False)
        else:
            on_continue('', None)

    def _nec_presence_received(self, obj):
        account = obj.conn.name
        jid = obj.jid

        if obj.need_add_in_roster:
            self.add_contact(jid, account)

        jid_list = app.contacts.get_jid_list(account)
        if jid in jid_list or jid == app.get_jid_from_account(account):
            if not app.jid_is_transport(jid) and len(obj.contact_list) == 1:
                if obj.old_show == 0 and obj.new_show > 1:
                    GLib.timeout_add_seconds(5, self.remove_newly_added, jid,
                        account)
                elif obj.old_show > 1 and obj.new_show == 0 and \
                obj.conn.connected > 1:
                    GLib.timeout_add_seconds(5, self.remove_to_be_removed,
                        jid, account)

        if obj.need_redraw:
            self.draw_contact(jid, account)

        if app.jid_is_transport(jid) and jid in jid_list:
            # It must be an agent
            # Update existing iter and group counting
            self.draw_contact(jid, account)
            self.draw_group(_('Transports'), account)

        if obj.contact:
            self.chg_contact_status(obj.contact, obj.show, obj.status, account)

        if obj.popup:
            ctrl = app.interface.msg_win_mgr.search_control(jid, account)
            if ctrl:
                GLib.idle_add(ctrl.parent_win.set_active_tab, ctrl)
            else:
                ctrl = app.interface.new_chat(obj.contact, account)
                if len(app.events.get_events(account, obj.jid)):
                    ctrl.read_queue()

    def _nec_gc_presence_received(self, obj):
        account = obj.conn.name
        if obj.room_jid in app.interface.minimized_controls[account]:
            gc_ctrl = app.interface.minimized_controls[account][obj.room_jid]
        else:
            return

        if obj.nick == gc_ctrl.nick:
            contact = app.contacts.get_contact_with_highest_priority(account,
                obj.room_jid)
            if contact:
                contact.show = obj.show
                self.draw_contact(obj.room_jid, account)
                self.draw_group(_('Groupchats'), account)

    def _nec_roster_received(self, obj):
        if obj.received_from_server:
            self.fill_contacts_and_groups_dicts(obj.roster, obj.conn.name)
            self.add_account_contacts(obj.conn.name, improve_speed=False)
            self.fire_up_unread_messages_events(obj.conn.name)
        else:
            # add self contact
            if app.config.get('show_self_contact') == 'always':
                account = obj.conn.name
                self_jid = app.get_jid_from_account(account)
                if self_jid not in app.contacts.get_jid_list(account):
                    resource = ''
                    if app.connections[account].server_resource:
                        resource = app.connections[account].server_resource
                    sha = app.config.get_per('accounts', account, 'avatar_sha')
                    contact = app.contacts.create_contact(jid=self_jid,
                        account=account, name=app.nicks[account],
                        groups=['self_contact'], show='offline', sub='both',
                        ask='none', resource=resource, avatar_sha=sha)
                    app.contacts.add_contact(account, contact)
                    self.add_contact(self_jid, account)
            if app.config.get('remember_opened_chat_controls'):
                account = obj.conn.name
                controls = app.config.get_per('accounts', account,
                    'opened_chat_controls')
                if controls:
                    for jid in controls.split(','):
                        contact = \
                            app.contacts.get_contact_with_highest_priority(
                            account, jid)
                        if not contact:
                            contact = self.add_to_not_in_the_roster(account,
                                jid)
                        app.interface.on_open_chat_window(None, contact,
                            account)
                app.config.set_per('accounts', account,
                    'opened_chat_controls', '')
            GLib.idle_add(self.refilter_shown_roster_items)

    def _nec_anonymous_auth(self, obj):
        """
        This event is raised when our JID changed (most probably because we use
        anonymous account. We update contact and roster entry in this case
        """
        self.rename_self_contact(obj.old_jid, obj.new_jid, obj.conn.name)

    def _nec_our_show(self, obj):
        model = self.status_combobox.get_model()
        iter_ = model.get_iter_from_string('7')
        if obj.show == 'offline':
            # sensitivity for this menuitem
            if app.get_number_of_connected_accounts() == 0:
                model[iter_][3] = False
            self.application.set_account_actions_state(obj.conn.name)
        else:
            # sensitivity for this menuitem
            model[iter_][3] = True
        self.on_status_changed(obj.conn.name, obj.show)

    def _nec_connection_type(self, obj):
        self.draw_account(obj.conn.name)

    def _nec_agent_removed(self, obj):
        for jid in obj.jid_list:
            self.remove_contact(jid, obj.conn.name, backend=True)

    def _nec_pep_received(self, obj):
        if obj.jid == app.get_jid_from_account(obj.conn.name):
            self.draw_account(obj.conn.name)

        if obj.pep_type == 'nickname':
            self.draw_contact(obj.jid, obj.conn.name)
        else:
            self.draw_pep(obj.jid, obj.conn.name, obj.pep_type)

    def _nec_update_avatar(self, obj):
        app.log('avatar').debug('Draw roster avatar: %s', obj.jid)
        self.draw_avatar(obj.jid, obj.account)

    def _nec_gc_subject_received(self, obj):
        contact = app.contacts.get_contact_with_highest_priority(
            obj.conn.name, obj.room_jid)
        if contact:
            contact.status = obj.subject
            self.draw_contact(obj.room_jid, obj.conn.name)

    def _nec_metacontacts_received(self, obj):
        self.redraw_metacontacts(obj.conn.name)

    def _nec_signed_in(self, obj):
        self.application.set_account_actions_state(obj.conn.name, True)
        self.draw_account(obj.conn.name)

    def _nec_decrypted_message_received(self, obj):
        if not obj.msgtxt: # empty message text
            return True
        if obj.mtype not in ('normal', 'chat'):
            return
        if obj.mtype == 'normal' and obj.popup:
            # it's single message to be autopopuped
            dialogs.SingleMessageWindow(obj.conn.name, obj.jid,
                action='receive', from_whom=obj.jid, subject=obj.subject,
                message=obj.msgtxt, resource=obj.resource, session=obj.session,
                form_node=obj.form_node)
            return
        if obj.session.control and obj.mtype == 'chat':
            typ = ''
            xep0184_id = None
            if obj.mtype == 'error':
                typ = 'error'
            if obj.forwarded and obj.sent:
                typ = 'out'
                if obj.jid != app.get_jid_from_account(obj.conn.name):
                    xep0184_id = obj.id_

            obj.session.control.print_conversation(obj.msgtxt, typ,
                tim=obj.timestamp, encrypted=obj.encrypted, subject=obj.subject,
                xhtml=obj.xhtml, displaymarking=obj.displaymarking,
                msg_log_id=obj.msg_log_id, msg_stanza_id=obj.id_, correct_id=obj.correct_id,
                xep0184_id=xep0184_id, additional_data=obj.additional_data)
            if obj.msg_log_id:
                pw = obj.session.control.parent_win
                end = obj.session.control.was_at_the_end
                if not pw or (pw.get_active_control() and obj.session.control \
                == pw.get_active_control() and pw.is_active() and end):
                    app.logger.set_read_messages([obj.msg_log_id])
        elif obj.popup and obj.mtype == 'chat':
            contact = app.contacts.get_contact(obj.conn.name, obj.jid)
            obj.session.control = app.interface.new_chat(contact,
                obj.conn.name, session=obj.session)
            if len(app.events.get_events(obj.conn.name, obj.fjid)):
                obj.session.control.read_queue()

        if obj.show_in_roster:
            self.draw_contact(obj.jid, obj.conn.name)
            self.show_title() # we show the * or [n]
            # Select the big brother contact in roster, it's visible because it
            # has events.
            family = app.contacts.get_metacontacts_family(obj.conn.name,
                obj.jid)
            if family:
                nearby_family, bb_jid, bb_account = \
                    app.contacts.get_nearby_family_and_big_brother(family,
                    obj.conn.name)
            else:
                bb_jid, bb_account = obj.jid, obj.conn.name
            self.select_contact(bb_jid, bb_account)

################################################################################
### Menu and GUI callbacks
### FIXME: order callbacks in itself...
################################################################################

    def on_bookmark_menuitem_activate(self, widget, account, bookmark):
        app.interface.join_gc_room(account, bookmark['jid'], bookmark['nick'],
                bookmark['password'])

    def on_info(self, widget, contact, account):
        """
        Call vcard_information_window class to display contact's information
        """
        if app.connections[account].is_zeroconf:
            self.on_info_zeroconf(widget, contact, account)
            return

        info = app.interface.instances[account]['infos']
        if contact.jid in info:
            info[contact.jid].window.present()
        else:
            info[contact.jid] = vcard.VcardWindow(contact, account)

    def on_info_zeroconf(self, widget, contact, account):
        info = app.interface.instances[account]['infos']
        if contact.jid in info:
            info[contact.jid].window.present()
        else:
            contact = app.contacts.get_first_contact_from_jid(account,
                                            contact.jid)
            if contact.show in ('offline', 'error'):
                # don't show info on offline contacts
                return
            info[contact.jid] = vcard.ZeroconfVcardWindow(contact, account)

    def on_agent_logging(self, widget, jid, state, account):
        """
        When an agent is requested to log in or off
        """
        app.connections[account].send_agent_status(jid, state)

    def on_edit_agent(self, widget, contact, account):
        """
        When we want to modify the agent registration
        """
        app.connections[account].request_register_agent_info(contact.jid)

    def on_remove_agent(self, widget, list_):
        """
        When an agent is requested to be removed. list_ is a list of (contact,
        account) tuple
        """
        for (contact, account) in list_:
            if app.config.get_per('accounts', account, 'hostname') == \
            contact.jid:
                # We remove the server contact
                # remove it from treeview
                app.connections[account].unsubscribe(contact.jid)
                self.remove_contact(contact.jid, account, backend=True)
                return

        def remove(list_):
            for (contact, account) in list_:
                full_jid = contact.get_full_jid()
                app.connections[account].unsubscribe_agent(full_jid)
                # remove transport from treeview
                self.remove_contact(contact.jid, account, backend=True)

        # Check if there are unread events from some contacts
        has_unread_events = False
        for (contact, account) in list_:
            for jid in app.events.get_events(account):
                if jid.endswith(contact.jid):
                    has_unread_events = True
                    break
        if has_unread_events:
            dialogs.ErrorDialog(_('You have unread messages'),
                    _('You must read them before removing this transport.'))
            return
        if len(list_) == 1:
            pritext = _('Transport "%s" will be removed') % list_[0][0].jid
            sectext = _('You will no longer be able to send and receive '
                'messages from contacts using this transport.')
        else:
            pritext = _('Transports will be removed')
            jids = ''
            for (contact, account) in list_:
                jids += '\n  ' + contact.get_shown_name() + ','
            jids = jids[:-1] + '.'
            sectext = _('You will no longer be able to send and receive '
                'messages to contacts from these transports: %s') % jids
        dialogs.ConfirmationDialog(pritext, sectext,
            on_response_ok = (remove, list_), transient_for=self.window)

    def _nec_blocking(self, obj):
        if obj.unblock_all or obj.blocklist:
            jids = app.contacts.get_jid_list(obj.conn.name)
            self._idle_draw_jids_of_account(jids, obj.conn.name)
        else:
            for jid in obj.blocked_jids + obj.unblocked_jids:
                self.draw_contact(jid, obj.conn.name)

    def on_block(self, widget, list_, group=None):
        """
        When clicked on the 'block' button in context menu. list_ is a list of
        (contact, account)
        """
        def on_continue(msg, pep_dict):
            if msg is None:
                # user pressed Cancel to change status message dialog
                return
            accounts = set(i[1] for i in list_ if (app.connections[i[1]].\
                privacy_rules_supported or (group is None and app.\
                connections[i[1]].blocking_supported)))
            if group is None:
                for acct in accounts:
                    l_ = [i[0] for i in list_ if i[1] == acct]
                    app.connections[acct].block_contacts(l_, msg)
                    for contact in l_:
                        self.draw_contact(contact.jid, acct)
            else:
                for acct in accounts:
                    l_ = [i[0] for i in list_ if i[1] == acct]
                    app.connections[acct].block_group(group, l_, msg)
                    self.draw_group(group, acct)
                    for contact in l_:
                        self.draw_contact(contact.jid, acct)

        def _block_it(is_checked=None):
            if is_checked is not None: # dialog has been shown
                if is_checked: # user does not want to be asked again
                    app.config.set('confirm_block', 'no')
                else:
                    app.config.set('confirm_block', 'yes')
            self.get_status_message('offline', on_continue, show_pep=False)

        confirm_block = app.config.get('confirm_block')
        if confirm_block == 'no':
            _block_it()
            return
        pritext = _('You are about to block a contact. Are you sure you want'
            ' to continue?')
        sectext = _('This contact will see you offline and you will not '
            'receive messages it sends you.')
        dialogs.ConfirmationDialogCheck(pritext, sectext,
            _('_Do not ask me again'), on_response_ok=_block_it)

    def on_unblock(self, widget, list_, group=None):
        """
        When clicked on the 'unblock' button in context menu.
        """
        accounts = set(i[1] for i in list_ if (app.connections[i[1]].\
            privacy_rules_supported or (group is None and app.\
            connections[i[1]].blocking_supported)))
        if group is None:
            for acct in accounts:
                l_ = [i[0] for i in list_ if i[1] == acct]
                app.connections[acct].unblock_contacts(l_)
                for contact in l_:
                    self.draw_contact(contact.jid, acct)
        else:
            for acct in accounts:
                l_ = [i[0] for i in list_ if i[1] == acct]
                app.connections[acct].unblock_group(group, l_)
                self.draw_group(group, acct)
                for contact in l_:
                    self.draw_contact(contact.jid, acct)
        for acct in accounts:
            if 'privacy_list_block' in app.interface.instances[acct]:
                del app.interface.instances[acct]['privacy_list_block']

    def on_rename(self, widget, row_type, jid, account):
        # this function is called either by F2 or by Rename menuitem
        if 'rename' in app.interface.instances:
            app.interface.instances['rename'].dialog.present()
            return

        # account is offline, don't allow to rename
        if app.connections[account].connected < 2:
            return
        if row_type in ('contact', 'agent'):
            # it's jid
            title = _('Rename Contact')
            message = _('Enter a new nickname for contact %s') % jid
            old_text = app.contacts.get_contact_with_highest_priority(account,
                    jid).name
        elif row_type == 'group':
            if jid in helpers.special_groups + (_('General'),):
                return
            old_text = jid
            title = _('Rename Group')
            message = _('Enter a new name for group %s') % \
                GLib.markup_escape_text(jid)

        def on_renamed(new_text, account, row_type, jid, old_text):
            if 'rename' in app.interface.instances:
                del app.interface.instances['rename']
            if row_type in ('contact', 'agent'):
                if old_text == new_text:
                    return
                contacts = app.contacts.get_contacts(account, jid)
                for contact in contacts:
                    contact.name = new_text
                app.connections[account].update_contact(jid, new_text, \
                    contacts[0].groups)
                self.draw_contact(jid, account)
                # Update opened chats
                for ctrl in app.interface.msg_win_mgr.get_controls(jid,
                account):
                    ctrl.update_ui()
                    win = app.interface.msg_win_mgr.get_window(jid, account)
                    win.redraw_tab(ctrl)
                    win.show_title()
            elif row_type == 'group':
                # in Column.JID column, we hold the group name (which is not escaped)
                self.rename_group(old_text, new_text, account)

        def on_canceled():
            if 'rename' in app.interface.instances:
                del app.interface.instances['rename']

        app.interface.instances['rename'] = dialogs.InputDialog(title,
            message, old_text, False, (on_renamed, account, row_type, jid,
            old_text), on_canceled, transient_for=self.window)

    def on_remove_group_item_activated(self, widget, group, account):
        def on_ok(checked):
            for contact in app.contacts.get_contacts_from_group(account,
            group):
                if not checked:
                    self.remove_contact_from_groups(contact.jid, account,
                        [group])
                else:
                    app.connections[account].unsubscribe(contact.jid)
                    self.remove_contact(contact.jid, account, backend=True)

        dialogs.ConfirmationDialogCheck(_('Remove Group'),
            _('Do you want to remove group %s from the roster?') % group,
            _('Also remove all contacts in this group from your roster'),
            on_response_ok=on_ok)

    def on_assign_pgp_key(self, widget, contact, account):
        attached_keys = app.config.get_per('accounts', account,
                'attached_gpg_keys').split()
        keys = {}
        keyID = _('None')
        for i in range(len(attached_keys) // 2):
            keys[attached_keys[2*i]] = attached_keys[2*i+1]
            if attached_keys[2*i] == contact.jid:
                keyID = attached_keys[2*i+1]
        public_keys = app.connections[account].ask_gpg_keys()
        public_keys[_('None')] = _('None')

        def on_key_selected(keyID):
            if keyID is None:
                return
            if keyID[0] == _('None'):
                if contact.jid in keys:
                    del keys[contact.jid]
                keyID = ''
            else:
                keyID = keyID[0]
                keys[contact.jid] = keyID

            ctrl = app.interface.msg_win_mgr.get_control(contact.jid, account)
            if ctrl:
                ctrl.update_ui()

            keys_str = ''
            for jid in keys:
                keys_str += jid + ' ' + keys[jid] + ' '
            app.config.set_per('accounts', account, 'attached_gpg_keys',
                    keys_str)
            for u in app.contacts.get_contacts(account, contact.jid):
                u.keyID = helpers.prepare_and_validate_gpg_keyID(account,
                    contact.jid, keyID)

        dialogs.ChooseGPGKeyDialog(_('Assign OpenPGP Key'),
            _('Select a key to apply to the contact'), public_keys,
            on_key_selected, selected=keyID, transient_for=self.window)

    def on_edit_groups(self, widget, list_):
        dialogs.EditGroupsDialog(list_)

    def on_history(self, widget, contact, account):
        """
        When history menuitem is activated: call log window
        """
        if 'logs' in app.interface.instances:
            app.interface.instances['logs'].window.present()
            app.interface.instances['logs'].open_history(contact.jid, account)
        else:
            app.interface.instances['logs'] = history_window.\
                HistoryWindow(contact.jid, account)

    def on_disconnect(self, widget, jid, account):
        """
        When disconnect menuitem is activated: disconect from room
        """
        if jid in app.interface.minimized_controls[account]:
            ctrl = app.interface.minimized_controls[account][jid]
            ctrl.shutdown()
            ctrl.got_disconnected()
        self.remove_groupchat(jid, account)

    def on_reconnect(self, widget, jid, account):
        """
        When reconnect menuitem is activated: join the room
        """
        if jid in app.interface.minimized_controls[account]:
            ctrl = app.interface.minimized_controls[account][jid]
            app.interface.join_gc_room(account, jid, ctrl.nick,
                app.gc_passwords.get(jid, ''))

    def on_send_single_message_menuitem_activate(self, widget, account,
    contact=None):
        if contact is None:
            dialogs.SingleMessageWindow(account, action='send')
        elif isinstance(contact, list):
            dialogs.SingleMessageWindow(account, contact, 'send')
        else:
            jid = contact.jid
            if contact.jid == app.get_jid_from_account(account):
                jid += '/' + contact.resource
            dialogs.SingleMessageWindow(account, jid, 'send')

    def on_send_file_menuitem_activate(self, widget, contact, account,
    resource=None):
        app.interface.instances['file_transfers'].show_file_send_request(
            account, contact)

    def on_add_special_notification_menuitem_activate(self, widget, jid):
        dialogs.AddSpecialNotificationDialog(jid)

    def on_invite_to_new_room(self, widget, list_, resource=None):
        """
        Resource parameter MUST NOT be used if more than one contact in list
        """
        account_list = []
        jid_list = []
        for (contact, account) in list_:
            if contact.jid not in jid_list:
                if resource: # we MUST have one contact only in list_
                    fjid = contact.jid + '/' + resource
                    jid_list.append(fjid)
                else:
                    jid_list.append(contact.jid)
            if account not in account_list:
                account_list.append(account)
        # transform None in 'jabber'
        type_ = app.get_transport_name_from_jid(jid_list[0]) or 'jabber'
        for account in account_list:
            if app.connections[account].muc_jid[type_]:
                # create the room on this muc server
                if 'join_gc' in app.interface.instances[account]:
                    app.interface.instances[account]['join_gc'].destroy()
                else:
                    app.interface.instances[account]['join_gc'] = \
                        dialogs.JoinGroupchatWindow(
                            account, None, automatic={'invities': jid_list})
                break

    def on_invite_to_room(self, widget, list_, room_jid, room_account,
    resource=None):
        """
        Resource parameter MUST NOT be used if more than one contact in list
        """
        for e in list_:
            contact = e[0]
            contact_jid = contact.jid
            if resource: # we MUST have one contact only in list_
                contact_jid += '/' + resource
            app.connections[room_account].send_invite(room_jid, contact_jid)
            gc_control = app.interface.msg_win_mgr.get_gc_control(room_jid,
                room_account)
            if gc_control:
                gc_control.print_conversation(
                    _('%(jid)s has been invited in this room') % {
                    'jid': contact_jid}, graphics=False)

    def on_all_groupchat_maximized(self, widget, group_list):
        for (contact, account) in group_list:
            self.on_groupchat_maximized(widget, contact.jid, account)

    def on_groupchat_maximized(self, widget, jid, account):
        """
        When a groupchat is maximized
        """
        if not jid in app.interface.minimized_controls[account]:
            # Already opened?
            gc_control = app.interface.msg_win_mgr.get_gc_control(jid,
                account)
            if gc_control:
                mw = app.interface.msg_win_mgr.get_window(jid, account)
                mw.set_active_tab(gc_control)
            return
        ctrl = app.interface.minimized_controls[account][jid]
        mw = app.interface.msg_win_mgr.get_window(jid, account)
        if not mw:
            mw = app.interface.msg_win_mgr.create_window(ctrl.contact,
                ctrl.account, ctrl.type_id)
            id_ = mw.window.connect('motion-notify-event',
                ctrl._on_window_motion_notify)
            ctrl.handlers[id_] = mw.window
        ctrl.parent_win = mw
        ctrl.on_groupchat_maximize()
        mw.new_tab(ctrl)
        mw.set_active_tab(ctrl)
        self.remove_groupchat(jid, account)

    def on_edit_account(self, widget, account):
        if 'accounts' in app.interface.instances:
            app.interface.instances['accounts'].present()
        else:
            app.interface.instances['accounts'] = config.AccountsWindow()
        app.interface.instances['accounts'].select_account(account)

    def on_change_status_message_activate(self, widget, account):
        show = app.SHOW_LIST[app.connections[account].connected]
        def on_response(message, pep_dict):
            if message is None: # None is if user pressed Cancel
                return
            self.send_status(account, show, message)
            self.send_pep(account, pep_dict)
        dialogs.ChangeStatusMessageDialog(on_response, show)

    def on_add_to_roster(self, widget, contact, account):
        dialogs.AddNewContactWindow(account, contact.jid, contact.name)

    def on_roster_treeview_key_press_event(self, widget, event):
        """
        When a key is pressed in the treeviews
        """
        if event.keyval == Gdk.KEY_Escape:
            if self.rfilter_enabled:
                self.disable_rfilter()
            else:
                self.tree.get_selection().unselect_all()
        elif event.keyval == Gdk.KEY_F2:
            treeselection = self.tree.get_selection()
            model, list_of_paths = treeselection.get_selected_rows()
            if len(list_of_paths) != 1:
                return
            path = list_of_paths[0]
            type_ = model[path][Column.TYPE]
            if type_ in ('contact', 'group', 'agent'):
                jid = model[path][Column.JID]
                account = model[path][Column.ACCOUNT]
                self.on_rename(widget, type_, jid, account)

        elif event.keyval == Gdk.KEY_Delete:
            treeselection = self.tree.get_selection()
            model, list_of_paths = treeselection.get_selected_rows()
            if not len(list_of_paths):
                return
            type_ = model[list_of_paths[0]][Column.TYPE]
            account = model[list_of_paths[0]][Column.ACCOUNT]
            if type_ in ('account', 'group', 'self_contact') or \
            account == app.ZEROCONF_ACC_NAME:
                return
            list_ = []
            for path in list_of_paths:
                if model[path][Column.TYPE] != type_:
                    return
                jid = model[path][Column.JID]
                account = model[path][Column.ACCOUNT]
                if not app.account_is_connected(account):
                    continue
                contact = app.contacts.get_contact_with_highest_priority(
                    account, jid)
                list_.append((contact, account))
            if not list_:
                return
            if type_ == 'contact':
                self.on_req_usub(widget, list_)
            elif type_ == 'agent':
                self.on_remove_agent(widget, list_)

        elif not (event.get_state() & (Gdk.ModifierType.CONTROL_MASK | \
        Gdk.ModifierType.MOD1_MASK)):
            num = Gdk.keyval_to_unicode(event.keyval)
            if num and num > 31:
                # if we got unicode symbol without ctrl / alt
                self.enable_rfilter(chr(num))

        elif event.get_state() & Gdk.ModifierType.CONTROL_MASK and \
        event.get_state() & Gdk.ModifierType.SHIFT_MASK and \
        event.keyval == Gdk.KEY_U:
            self.enable_rfilter('')
            self.rfilter_entry.event(event)

        elif event.keyval == Gdk.KEY_Left:
            treeselection = self.tree.get_selection()
            model, list_of_paths = treeselection.get_selected_rows()
            if len(list_of_paths) != 1:
                return
            path = list_of_paths[0]
            iter_ = model.get_iter(path)
            if model.iter_has_child(iter_) and self.tree.row_expanded(path):
                self.tree.collapse_row(path)
                return True
            elif path.get_depth() > 1:
                self.tree.set_cursor(path[:-1])
                return True
        elif event.keyval == Gdk.KEY_Right:
            treeselection = self.tree.get_selection()
            model, list_of_paths = treeselection.get_selected_rows()
            if len(list_of_paths) != 1:
                return
            path = list_of_paths[0]
            iter_ = model.get_iter(path)
            if model.iter_has_child(iter_):
                self.tree.expand_row(path, False)
                return True

    def on_roster_treeview_button_release_event(self, widget, event):
        try:
            path = self.tree.get_path_at_pos(int(event.x), int(event.y))[0]
        except TypeError:
            return False

        if event.button == 1: # Left click
            if app.single_click and not event.get_state() & Gdk.ModifierType.SHIFT_MASK and \
            not event.get_state() & Gdk.ModifierType.CONTROL_MASK:
                # Check if button has been pressed on the same row
                if self.clicked_path == path:
                    self.on_row_activated(widget, path)
                self.clicked_path = None

    def accel_group_func(self, accel_group, acceleratable, keyval, modifier):
        # CTRL mask
        if modifier & Gdk.ModifierType.CONTROL_MASK:
            if keyval == Gdk.KEY_s: # CTRL + s
                model = self.status_combobox.get_model()
                accounts = list(app.connections.keys())
                status = model[self.previous_status_combobox_active][2]
                def on_response(message, pep_dict):
                    if message is not None: # None if user pressed Cancel
                        for account in accounts:
                            if not app.config.get_per('accounts', account,
                            'sync_with_global_status'):
                                continue
                            current_show = app.SHOW_LIST[
                                app.connections[account].connected]
                            self.send_status(account, current_show, message)
                            self.send_pep(account, pep_dict)
                dialogs.ChangeStatusMessageDialog(on_response, status)
                return True
            elif keyval == Gdk.KEY_k: # CTRL + k
                self.enable_rfilter('')

    def on_roster_treeview_button_press_event(self, widget, event):
        try:
            pos = self.tree.get_path_at_pos(int(event.x), int(event.y))
            path, x = pos[0], pos[2]
        except TypeError:
            self.tree.get_selection().unselect_all()
            return False

        if event.button == 3: # Right click
            try:
                model, list_of_paths = self.tree.get_selection().\
                    get_selected_rows()
            except TypeError:
                list_of_paths = []
            if path not in list_of_paths:
                self.tree.get_selection().unselect_all()
                self.tree.get_selection().select_path(path)
            return self.show_treeview_menu(event)

        elif event.button == 2: # Middle click
            try:
                model, list_of_paths = self.tree.get_selection().\
                    get_selected_rows()
            except TypeError:
                list_of_paths = []
            if list_of_paths != [path]:
                self.tree.get_selection().unselect_all()
                self.tree.get_selection().select_path(path)
            type_ = model[path][Column.TYPE]
            if type_ in ('agent', 'contact', 'self_contact', 'groupchat'):
                self.on_row_activated(widget, path)
            elif type_ == 'account':
                account = model[path][Column.ACCOUNT]
                if account != 'all':
                    show = app.connections[account].connected
                    if show > 1: # We are connected
                        self.on_change_status_message_activate(widget, account)
                    return True
                show = helpers.get_global_show()
                if show == 'offline':
                    return True
                def on_response(message, pep_dict):
                    if message is None:
                        return True
                    for acct in app.connections:
                        if not app.config.get_per('accounts', acct,
                        'sync_with_global_status'):
                            continue
                        current_show = app.SHOW_LIST[app.connections[acct].\
                            connected]
                        self.send_status(acct, current_show, message)
                        self.send_pep(acct, pep_dict)
                dialogs.ChangeStatusMessageDialog(on_response, show)
            return True

        elif event.button == 1: # Left click
            model = self.modelfilter
            type_ = model[path][Column.TYPE]
            # x_min is the x start position of status icon column
            if app.config.get('avatar_position_in_roster') == 'left':
                x_min = AvatarSize.ROSTER
            else:
                x_min = 0
            if app.single_click and not event.get_state() & Gdk.ModifierType.SHIFT_MASK and \
            not event.get_state() & Gdk.ModifierType.CONTROL_MASK:
                # Don't handle double click if we press icon of a metacontact
                titer = model.get_iter(path)
                if x > x_min and x < x_min + 27 and type_ == 'contact' and \
                model.iter_has_child(titer):
                    if (self.tree.row_expanded(path)):
                        self.tree.collapse_row(path)
                    else:
                        self.tree.expand_row(path, False)
                    return
                # We just save on which row we press button, and open chat
                # window on button release to be able to do DND without opening
                # chat window
                self.clicked_path = path
                return
            else:
                if type_ == 'group' and x < 27:
                    # first cell in 1st column (the arrow SINGLE clicked)
                    if (self.tree.row_expanded(path)):
                        self.tree.collapse_row(path)
                    else:
                        self.expand_group_row(path)

                elif type_ == 'contact' and x > x_min and x < x_min + 27:
                    if (self.tree.row_expanded(path)):
                        self.tree.collapse_row(path)
                    else:
                        self.tree.expand_row(path, False)

    def expand_group_row(self, path):
        self.tree.expand_row(path, False)
        iter = self.modelfilter.get_iter(path)
        child_iter = self.modelfilter.iter_children(iter)
        while child_iter:
            type_ = self.modelfilter[child_iter][Column.TYPE]
            account = self.modelfilter[child_iter][Column.ACCOUNT]
            group = self.modelfilter[child_iter][Column.JID]
            if type_ == 'group' and account + group not in self.collapsed_rows:
                self.expand_group_row(self.modelfilter.get_path(child_iter))
            child_iter = self.modelfilter.iter_next(child_iter)

    def on_req_usub(self, widget, list_):
        """
        Remove a contact. list_ is a list of (contact, account) tuples
        """
        def on_ok(is_checked, list_):
            remove_auth = True
            if len(list_) == 1:
                contact = list_[0][0]
                if contact.sub != 'to' and is_checked:
                    remove_auth = False
            for (contact, account) in list_:
                if _('Not in Roster') not in contact.get_shown_groups():
                    app.connections[account].unsubscribe(contact.jid,
                        remove_auth)
                self.remove_contact(contact.jid, account, backend=True)
                if not remove_auth and contact.sub == 'both':
                    contact.name = ''
                    contact.groups = []
                    contact.sub = 'from'
                    # we can't see him, but have to set it manually in contact
                    contact.show = 'offline'
                    app.contacts.add_contact(account, contact)
                    self.add_contact(contact.jid, account)
        def on_ok2(list_):
            on_ok(False, list_)

        if len(list_) == 1:
            contact = list_[0][0]
            pritext = _('Contact "%s" will be removed from your roster') % \
                contact.get_shown_name()
            sectext = _('You are about to remove "%(name)s" (%(jid)s) from '
                'your roster.\n') % {'name': contact.get_shown_name(),
                'jid': contact.jid}
            if contact.sub == 'to':
                dialogs.ConfirmationDialog(pritext, sectext + \
                    _('By removing this contact you also remove authorization '
                    'resulting in them always seeing you as offline.'),
                    on_response_ok=(on_ok2, list_))
            elif _('Not in Roster') in contact.get_shown_groups():
                # Contact is not in roster
                dialogs.ConfirmationDialog(pritext, sectext + \
                    _('Do you want to continue?'), on_response_ok=(on_ok2,
                    list_))
            else:
                dialogs.ConfirmationDialogCheck(pritext, sectext + \
                    _('By removing this contact you also by default remove '
                    'authorization resulting in them always seeing you as'
                    ' offline.'),
                    _('I want this contact to know my status after removal'),
                    on_response_ok=(on_ok, list_))
        else:
            # several contact to remove at the same time
            pritext = _('Contacts will be removed from your roster')
            jids = ''
            for (contact, account) in list_:
                jids += '\n  ' + contact.get_shown_name() + ' (%s)' % \
                contact.jid + ','
            sectext = _('By removing these contacts:%s\nyou also remove '
                'authorization resulting in them always seeing you as '
                'offline.') % jids
            dialogs.ConfirmationDialog(pritext, sectext,
                on_response_ok=(on_ok2, list_))

    def on_send_custom_status(self, widget, contact_list, show, group=None):
        """
        Send custom status
        """
        # contact_list has only one element except if group != None
        def on_response(message, pep_dict):
            if message is None: # None if user pressed Cancel
                return
            account_list = []
            for (contact, account) in contact_list:
                if account not in account_list:
                    account_list.append(account)
            # 1. update status_sent_to_[groups|users] list
            if group:
                for account in account_list:
                    if account not in app.interface.status_sent_to_groups:
                        app.interface.status_sent_to_groups[account] = {}
                    app.interface.status_sent_to_groups[account][group] = show
            else:
                for (contact, account) in contact_list:
                    if account not in app.interface.status_sent_to_users:
                        app.interface.status_sent_to_users[account] = {}
                    app.interface.status_sent_to_users[account][contact.jid] \
                        = show

            # 2. update privacy lists if main status is invisible
            for account in account_list:
                if app.SHOW_LIST[app.connections[account].connected] == \
                'invisible':
                    app.connections[account].set_invisible_rule()

            # 3. send directed presence
            for (contact, account) in contact_list:
                our_jid = app.get_jid_from_account(account)
                jid = contact.jid
                if jid == our_jid:
                    jid += '/' + contact.resource
                self.send_status(account, show, message, to=jid)

        def send_it(is_checked=None):
            if is_checked is not None: # dialog has been shown
                if is_checked: # user does not want to be asked again
                    app.config.set('confirm_custom_status', 'no')
                else:
                    app.config.set('confirm_custom_status', 'yes')
            self.get_status_message(show, on_response, show_pep=False,
                always_ask=True)

        confirm_custom_status = app.config.get('confirm_custom_status')
        if confirm_custom_status == 'no':
            send_it()
            return
        pritext = _('You are about to send a custom status. Are you sure you '
            'want to continue?')
        sectext = _('This contact will temporarily see you as %(status)s, '
            'but only until you change your status. Then they will see '
            'your global status.') % {'status': show}
        dialogs.ConfirmationDialogCheck(pritext, sectext,
            _('_Do not ask me again'), on_response_ok=send_it)

    def on_status_combobox_changed(self, widget):
        """
        When we change our status via the combobox
        """
        model = self.status_combobox.get_model()
        active = self.status_combobox.get_active()
        if active == -1: # no active item
            return
        if not self.combobox_callback_active:
            self.previous_status_combobox_active = active
            return
        accounts = list(app.connections.keys())
        if len(accounts) == 0:
            dialogs.ErrorDialog(_('No account available'),
                _('You must create an account before you can chat with other '
                'contacts.'))
            self.update_status_combobox()
            return
        status = model[active][2]
        # status "desync'ed" or not
        statuses_unified = helpers.statuses_unified()
        if (active == 7 and statuses_unified) or (active == 9 and \
        not statuses_unified):
            # 'Change status message' selected:
            # do not change show, just show change status dialog
            status = model[self.previous_status_combobox_active][2]
            def on_response(message, pep_dict):
                if message is not None: # None if user pressed Cancel
                    for account in accounts:
                        if not app.config.get_per('accounts', account,
                        'sync_with_global_status'):
                            continue
                        current_show = app.SHOW_LIST[
                            app.connections[account].connected]
                        self.send_status(account, current_show, message)
                        self.send_pep(account, pep_dict)
                self.combobox_callback_active = False
                self.status_combobox.set_active(
                    self.previous_status_combobox_active)
                self.combobox_callback_active = True
            dialogs.ChangeStatusMessageDialog(on_response, status)
            return
        # we are about to change show, so save this new show so in case
        # after user chooses "Change status message" menuitem
        # we can return to this show
        self.previous_status_combobox_active = active
        connected_accounts = app.get_number_of_connected_accounts()

        def on_continue(message, pep_dict):
            if message is None:
                # user pressed Cancel to change status message dialog
                self.update_status_combobox()
                return
            global_sync_accounts = []
            for acct in accounts:
                if app.config.get_per('accounts', acct,
                'sync_with_global_status'):
                    global_sync_accounts.append(acct)
            global_sync_connected_accounts = \
                app.get_number_of_connected_accounts(global_sync_accounts)
            for account in accounts:
                if not app.config.get_per('accounts', account,
                'sync_with_global_status'):
                    continue
                # we are connected (so we wanna change show and status)
                # or no account is connected and we want to connect with new
                # show and status

                if not global_sync_connected_accounts > 0 or \
                app.connections[account].connected > 0:
                    self.send_status(account, status, message)
                    self.send_pep(account, pep_dict)
            self.update_status_combobox()

        if status == 'invisible':
            bug_user = False
            for account in accounts:
                if connected_accounts < 1 or app.account_is_connected(
                account):
                    if not app.config.get_per('accounts', account,
                    'sync_with_global_status'):
                        continue
                    # We're going to change our status to invisible
                    if self.connected_rooms(account):
                        bug_user = True
                        break
            if bug_user:
                def on_ok():
                    self.get_status_message(status, on_continue, show_pep=False)

                def on_cancel():
                    self.update_status_combobox()

                dialogs.ConfirmationDialog(
                    _('You are participating in one or more group chats'),
                    _('Changing your status to invisible will result in '
                    'disconnection from those group chats. Are you sure you '
                    'want to go invisible?'), on_response_ok=on_ok,
                    on_response_cancel=on_cancel)
                return

        self.get_status_message(status, on_continue)

    def on_publish_tune_toggled(self, widget, account):
        active = widget.get_active()
        app.config.set_per('accounts', account, 'publish_tune', active)
        if active:
            app.interface.enable_music_listener()
        else:
            app.connections[account].retract_tune()
            # disable music listener only if no other account uses it
            for acc in app.connections:
                if app.config.get_per('accounts', acc, 'publish_tune'):
                    break
            else:
                app.interface.disable_music_listener()

        helpers.update_optional_features(account)

    def on_publish_location_toggled(self, widget, account):
        active = widget.get_active()
        app.config.set_per('accounts', account, 'publish_location', active)
        if active:
            location_listener.enable()
        else:
            app.connections[account].retract_location()

        helpers.update_optional_features(account)

    def on_pep_services_menuitem_activate(self, widget, account):
        if 'pep_services' in app.interface.instances[account]:
            app.interface.instances[account]['pep_services'].window.present()
        else:
            app.interface.instances[account]['pep_services'] = \
                config.ManagePEPServicesWindow(account)

    def on_add_new_contact(self, widget, account):
        dialogs.AddNewContactWindow(account)

    def on_join_gc_activate(self, widget, account):
        """
        When the join gc menuitem is clicked, show the join gc window
        """
        invisible_show = app.SHOW_LIST.index('invisible')
        if app.connections[account].connected == invisible_show:
            dialogs.ErrorDialog(_('You cannot join a group chat while you are '
                'invisible'))
            return
        if 'join_gc' in app.interface.instances[account]:
            app.interface.instances[account]['join_gc'].present()
        else:
            app.interface.instances[account]['join_gc'] = \
                    dialogs.JoinGroupchatWindow(account, None)

    def on_show_transports_action(self, action, param):
        app.config.set('show_transports_group', param.get_boolean())
        action.set_state(param)
        self.refilter_shown_roster_items()

    def on_manage_bookmarks_menuitem_activate(self, widget):
        config.ManageBookmarksWindow()

    def on_execute_command(self, widget, contact, account, resource=None):
        """
        Execute command. Full JID needed; if it is other contact, resource is
        necessary. Widget is unnecessary, only to be able to make this a
        callback
        """
        jid = contact.jid
        if resource is not None:
            jid = jid + '/' + resource
        adhoc_commands.CommandWindow(account, jid)

    def on_roster_window_focus_in_event(self, widget, event):
        # roster received focus, so if we had urgency REMOVE IT
        # NOTE: we do not have to read the message to remove urgency
        # so this functions does that
        gtkgui_helpers.set_unset_urgency_hint(widget, False)

        # if a contact row is selected, update colors (eg. for status msg)
        # because gtk engines may differ in bg when window is selected
        # or not
        if len(self._last_selected_contact):
            for (jid, account) in self._last_selected_contact:
                self.draw_contact(jid, account, selected=True, focus=True)

    def on_roster_window_focus_out_event(self, widget, event):
        # if a contact row is selected, update colors (eg. for status msg)
        # because gtk engines may differ in bg when window is selected
        # or not
        if len(self._last_selected_contact):
            for (jid, account) in self._last_selected_contact:
                self.draw_contact(jid, account, selected=True, focus=False)

    def on_roster_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            if self.rfilter_enabled:
                self.disable_rfilter()
                return True
            if app.interface.msg_win_mgr.mode == \
            MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER and \
            app.interface.msg_win_mgr.one_window_opened():
                # let message window close the tab
                return
            list_of_paths = self.tree.get_selection().get_selected_rows()[1]
            if not len(list_of_paths) and not app.config.get(
            'quit_on_roster_x_button') and ((app.interface.systray_enabled and\
            app.config.get('trayicon') == 'always') or app.config.get(
            'allow_hide_roster')):
                if app.config.get('hide_on_roster_x_button'):
                    self.window.hide()
                else:
                    self.window.iconify()
        elif event.get_state() & Gdk.ModifierType.CONTROL_MASK and event.keyval == \
        Gdk.KEY_i:
            treeselection = self.tree.get_selection()
            model, list_of_paths = treeselection.get_selected_rows()
            for path in list_of_paths:
                type_ = model[path][Column.TYPE]
                if type_ in ('contact', 'agent'):
                    jid = model[path][Column.JID]
                    account = model[path][Column.ACCOUNT]
                    contact = app.contacts.get_first_contact_from_jid(account,
                        jid)
                    self.on_info(widget, contact, account)
        elif event.get_state() & Gdk.ModifierType.CONTROL_MASK and event.keyval == \
        Gdk.KEY_h:
            treeselection = self.tree.get_selection()
            model, list_of_paths = treeselection.get_selected_rows()
            if len(list_of_paths) != 1:
                return
            path = list_of_paths[0]
            type_ = model[path][Column.TYPE]
            if type_ in ('contact', 'agent'):
                jid = model[path][Column.JID]
                account = model[path][Column.ACCOUNT]
                contact = app.contacts.get_first_contact_from_jid(account,
                    jid)
                self.on_history(widget, contact, account)

    def on_roster_window_popup_menu(self, widget):
        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        self.show_treeview_menu(event)

    def on_row_activated(self, widget, path):
        """
        When an iter is activated (double-click or single click if gnome is set
        this way)
        """
        model = self.modelfilter
        account = model[path][Column.ACCOUNT]
        type_ = model[path][Column.TYPE]
        if type_ in ('group', 'account'):
            if self.tree.row_expanded(path):
                self.tree.collapse_row(path)
            else:
                self.tree.expand_row(path, False)
            return
        if self.rfilter_enabled:
            GObject.idle_add(self.disable_rfilter)
        jid = model[path][Column.JID]
        resource = None
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        titer = model.get_iter(path)
        if contact.is_groupchat():
            first_ev = app.events.get_first_event(account, jid)
            if first_ev and self.open_event(account, jid, first_ev):
                # We are invited to a GC
                # open event cares about connecting to it
                self.remove_groupchat(jid, account)
            else:
                self.on_groupchat_maximized(None, jid, account)
            return

        # else
        first_ev = app.events.get_first_event(account, jid)
        if not first_ev:
            # look in other resources
            for c in app.contacts.get_contacts(account, jid):
                fjid = c.get_full_jid()
                first_ev = app.events.get_first_event(account, fjid)
                if first_ev:
                    resource = c.resource
                    break
        if not first_ev and model.iter_has_child(titer):
            child_iter = model.iter_children(titer)
            while not first_ev and child_iter:
                child_jid = model[child_iter][Column.JID]
                first_ev = app.events.get_first_event(account, child_jid)
                if first_ev:
                    jid = child_jid
                else:
                    child_iter = model.iter_next(child_iter)
        session = None
        if first_ev:
            if first_ev.type_ in ('chat', 'normal'):
                session = first_ev.session
            fjid = jid
            if resource:
                fjid += '/' + resource
            if self.open_event(account, fjid, first_ev):
                return
            # else
            contact = app.contacts.get_contact(account, jid, resource)
        if not contact or isinstance(contact, list):
            contact = app.contacts.get_contact_with_highest_priority(account,
                    jid)
        if jid == app.get_jid_from_account(account):
            resource = None

        app.interface.on_open_chat_window(None, contact, account, \
            resource=resource, session=session)

    def on_roster_treeview_row_activated(self, widget, path, col=0):
        """
        When an iter is double clicked: open the first event window
        """
        if not app.single_click:
            self.on_row_activated(widget, path)

    def on_roster_treeview_row_expanded(self, widget, titer, path):
        """
        When a row is expanded change the icon of the arrow
        """
        self._toggeling_row = True
        model = widget.get_model()
        child_model = model.get_model()
        child_iter =  model.convert_iter_to_child_iter(titer)

        if self.regroup: # merged accounts
            accounts = list(app.connections.keys())
        else:
            accounts = [model[titer][Column.ACCOUNT]]

        type_ = model[titer][Column.TYPE]
        if type_ == 'group':
            group = model[titer][Column.JID]
            image = gtkgui_helpers.get_image_from_icon_name(
                'opened', self.scale_factor)
            child_model[child_iter][Column.IMG] = image
            if self.rfilter_enabled:
                return
            for account in accounts:
                if group in app.groups[account]: # This account has this group
                    app.groups[account][group]['expand'] = True
                    if account + group in self.collapsed_rows:
                        self.collapsed_rows.remove(account + group)
                for contact in app.contacts.iter_contacts(account):
                    jid = contact.jid
                    if group in contact.groups and \
                    app.contacts.is_big_brother(account, jid, accounts) and \
                    account + group + jid not in self.collapsed_rows:
                        titers = self._get_contact_iter(jid, account)
                        for titer in titers:
                            path = model.get_path(titer)
                            self.tree.expand_row(path, False)
        elif type_ == 'account':
            account = list(accounts)[0] # There is only one cause we don't use merge
            if account in self.collapsed_rows:
                self.collapsed_rows.remove(account)
            self.draw_account(account)
            # When we expand, groups are collapsed. Restore expand state
            for group in app.groups[account]:
                if app.groups[account][group]['expand']:
                    titer = self._get_group_iter(group, account)
                    if titer:
                        path = model.get_path(titer)
                        self.tree.expand_row(path, False)
        elif type_ == 'contact':
            # Metacontact got toggled, update icon
            jid = model[titer][Column.JID]
            account = model[titer][Column.ACCOUNT]
            contact = app.contacts.get_contact(account, jid)
            for group in contact.groups:
                if account + group + jid in self.collapsed_rows:
                    self.collapsed_rows.remove(account + group + jid)
            family = app.contacts.get_metacontacts_family(account, jid)
            nearby_family = \
                self._get_nearby_family_and_big_brother(family, account)[0]
            # Redraw all brothers to show pending events
            for data in nearby_family:
                self.draw_contact(data['jid'], data['account'])

        self._toggeling_row = False

    def on_roster_treeview_row_collapsed(self, widget, titer, path):
        """
        When a row is collapsed change the icon of the arrow
        """
        self._toggeling_row = True
        model = widget.get_model()
        child_model = model.get_model()
        child_iter =  model.convert_iter_to_child_iter(titer)

        if self.regroup: # merged accounts
            accounts = list(app.connections.keys())
        else:
            accounts = [model[titer][Column.ACCOUNT]]

        type_ = model[titer][Column.TYPE]
        if type_ == 'group':
            image = gtkgui_helpers.get_image_from_icon_name(
                'closed', self.scale_factor)
            child_model[child_iter][Column.IMG] = image
            if self.rfilter_enabled:
                return
            group = model[titer][Column.JID]
            for account in accounts:
                if group in app.groups[account]: # This account has this group
                    app.groups[account][group]['expand'] = False
                    if account + group not in self.collapsed_rows:
                        self.collapsed_rows.append(account + group)
        elif type_ == 'account':
            account = accounts[0] # There is only one cause we don't use merge
            if account not in self.collapsed_rows:
                self.collapsed_rows.append(account)
            self.draw_account(account)
        elif type_ == 'contact':
            # Metacontact got toggled, update icon
            jid = model[titer][Column.JID]
            account = model[titer][Column.ACCOUNT]
            contact = app.contacts.get_contact(account, jid)
            groups = contact.groups
            if not groups:
                groups = [_('General')]
            for group in groups:
                if account + group + jid not in self.collapsed_rows:
                    self.collapsed_rows.append(account + group + jid)
            family = app.contacts.get_metacontacts_family(account, jid)
            nearby_family  = \
                    self._get_nearby_family_and_big_brother(family, account)[0]
            # Redraw all brothers to show pending events
            for data in nearby_family:
                self.draw_contact(data['jid'], data['account'])

        self._toggeling_row = False

    def on_modelfilter_row_has_child_toggled(self, model, path, titer):
        """
        Called when a row has gotten the first or lost its last child row

        Expand Parent if necessary.
        """
        if self._toggeling_row:
            # Signal is emitted when we write to our model
            return

        type_ = model[titer][Column.TYPE]
        account = model[titer][Column.ACCOUNT]
        if not account:
            return

        if type_ == 'contact':
            child_iter = model.convert_iter_to_child_iter(titer)
            if self.model.iter_has_child(child_iter):
                # we are a bigbrother metacontact
                # redraw us to show/hide expand icon
                if self.filtering:
                    # Prevent endless loops
                    jid = model[titer][Column.JID]
                    GLib.idle_add(self.draw_contact, jid, account)
        elif type_ == 'group':
            group = model[titer][Column.JID]
            GLib.idle_add(self._adjust_group_expand_collapse_state, group, account)
        elif type_ == 'account':
            GLib.idle_add(self._adjust_account_expand_collapse_state, account)

# Selection can change when the model is filtered
# Only write to the model when filtering is finished!
#
# FIXME: When we are filtering our custom colors are somehow lost
#
#       def on_treeview_selection_changed(self, selection):
#               '''Called when selection in TreeView has changed.
#
#               Redraw unselected rows to make status message readable
#               on all possible backgrounds.
#               '''
#               model, list_of_paths = selection.get_selected_rows()
#               if len(self._last_selected_contact):
#                       # update unselected rows
#                       for (jid, account) in self._last_selected_contact:
#                               GLib.idle_add(self.draw_contact, jid,
#                                       account)
#               self._last_selected_contact = []
#               if len(list_of_paths) == 0:
#                       return
#               for path in list_of_paths:
#                       row = model[path]
#                       if row[Column.TYPE] != 'contact':
#                               self._last_selected_contact = []
#                               return
#                       jid = row[Column.JID]
#                       account = row[Column.ACCOUNT]
#                       self._last_selected_contact.append((jid, account))
#                       GLib.idle_add(self.draw_contact, jid, account, True)
    

    def on_service_disco_menuitem_activate(self, widget, account):
        server_jid = app.config.get_per('accounts', account, 'hostname')
        if server_jid in app.interface.instances[account]['disco']:
            app.interface.instances[account]['disco'][server_jid].\
                window.present()
        else:
            try:
                # Object will add itself to the window dict
                disco.ServiceDiscoveryWindow(account, address_entry=True)
            except GajimGeneralException:
                pass

    def on_show_offline_contacts_action(self, action, param):
        """
        When show offline option is changed: redraw the treeview
        """
        action.set_state(param)
        app.config.set('showoffline', param.get_boolean())
        self.refilter_shown_roster_items()
        self.window.lookup_action('show-active').set_enabled(
            not param.get_boolean())

    def on_show_active_contacts_action(self, action, param):
        """
        When show only active contact option is changed: redraw the treeview
        """
        action.set_state(param)
        app.config.set('show_only_chat_and_online', param.get_boolean())
        self.refilter_shown_roster_items()
        self.window.lookup_action('show-offline').set_enabled(
            not param.get_boolean())

    def on_show_roster_action(self, action, param):
        # when num controls is 0 this menuitem is hidden, but still need to
        # disable keybinding
        action.set_state(param)
        if self.hpaned.get_child2() is not None:
            self.show_roster_vbox(param.get_boolean())

    def on_rfilter_entry_changed(self, widget):
        """ When we update the content of the filter """
        self.rfilter_string = widget.get_text().lower()
        if self.rfilter_string == '':
            self.disable_rfilter()
        self.refilter_shown_roster_items()
        # select first row
        self.tree.get_selection().unselect_all()
        def _func(model, path, iter_, param):
            if model[iter_][Column.TYPE] == 'contact' and self.rfilter_string in \
            model[iter_][Column.NAME].lower():
                col = self.tree.get_column(0)
                self.tree.set_cursor_on_cell(path, col, None, False)
                return True
        self.modelfilter.foreach(_func, None)

    def on_rfilter_entry_icon_press(self, widget, icon, event):
        """
        Disable the roster filtering by clicking the icon in the textEntry
        """
        self.disable_rfilter()

    def on_rfilter_entry_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.disable_rfilter()
        elif event.keyval == Gdk.KEY_Return:
            self.tree.grab_focus()
            self.tree.event(event)
            self.disable_rfilter()
        elif event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down):
            self.tree.grab_focus()
            self.tree.event(event)
        elif event.keyval == Gdk.KEY_BackSpace:
            if widget.get_text() == '':
                self.disable_rfilter()

    def enable_rfilter(self, search_string):
        self.rfilter_entry.set_visible(True)
        self.rfilter_entry.set_editable(True)
        self.rfilter_entry.grab_focus()
        if self.rfilter_enabled:
            self.rfilter_entry.set_text(self.rfilter_entry.get_text() + \
                search_string)
        else:
            self.rfilter_enabled = True
            self.rfilter_entry.set_text(search_string)
            self.tree.expand_all()
        self.rfilter_entry.set_position(-1)

        # If roster is hidden, let's temporarily show it. This can happen if user
        # enables rfilter via keyboard shortcut.
        self.show_roster_vbox(True)

    def disable_rfilter(self):
        self.rfilter_enabled = False
        self.rfilter_entry.set_text('')
        self.rfilter_entry.set_visible(False)
        self.rfilter_entry.set_editable(False)
        self.refilter_shown_roster_items()
        self.tree.grab_focus()
        self._readjust_expand_collapse_state()

        # If roster was hidden before enable_rfilter was called, hide it back.
        state = self.window.lookup_action('show-roster').get_state().get_boolean()
        if state is False and self.hpaned.get_child2() is not None:
            self.show_roster_vbox(False)

    def on_roster_hpaned_notify(self, pane, gparamspec):
        """
        Keep changing the width of the roster
        (when a Gtk.Paned widget handle is dragged)
        """
        if gparamspec and gparamspec.name == 'position':
            roster_width = pane.get_child1().get_allocation().width
            app.config.set('roster_width', roster_width)
            app.config.set('roster_hpaned_position', pane.get_position())

################################################################################
### Drag and Drop handling
################################################################################

    def drag_data_get_data(self, treeview, context, selection, target_id,
    etime):
        model, list_of_paths = self.tree.get_selection().get_selected_rows()
        if len(list_of_paths) != 1:
            return
        path = list_of_paths[0]
        data = ''
        if path.get_depth() >= 2:
            data = model[path][Column.JID]
        selection.set_text(data, -1)

    def drag_begin(self, treeview, context):
        self.dragging = True

    def drag_end(self, treeview, context):
        self.dragging = False

    def on_drop_rosterx(self, widget, account_source, c_source, account_dest,
    c_dest, was_big_brother, context, etime):
        type_ = 'message'
        if c_dest.show not in ('offline', 'error') and c_dest.supports(
        NS_ROSTERX):
            type_ = 'iq'
        app.connections[account_dest].send_contacts([c_source],
             c_dest.get_full_jid(), type_=type_)

    def on_drop_in_contact(self, widget, account_source, c_source, account_dest,
    c_dest, was_big_brother, context, etime):

        if not app.connections[account_source].private_storage_supported or \
        not app.connections[account_dest].private_storage_supported:
            dialogs.WarningDialog(_('Metacontacts storage not supported by '
                'your server'),
                _('Your server does not support storing metacontacts '
                'information. So this information will not be saved on next '
                'reconnection.'))

        def merge_contacts(is_checked=None):
            contacts = 0
            if is_checked is not None: # dialog has been shown
                if is_checked: # user does not want to be asked again
                    app.config.set('confirm_metacontacts', 'no')
                else:
                    app.config.set('confirm_metacontacts', 'yes')

            # We might have dropped on a metacontact.
            # Remove it and readd later with updated family info
            dest_family = app.contacts.get_metacontacts_family(account_dest,
                c_dest.jid)
            if dest_family:
                self._remove_metacontact_family(dest_family, account_dest)
                source_family = app.contacts.get_metacontacts_family(
                    account_source, c_source.jid)
                if dest_family == source_family:
                    n = contacts = len(dest_family)
                    for tag in source_family:
                        if tag['jid'] == c_source.jid:
                            tag['order'] = contacts
                            continue
                        if 'order' in tag:
                            n -= 1
                            tag['order'] = n
            else:
                self._remove_entity(c_dest, account_dest)

            old_family = app.contacts.get_metacontacts_family(account_source,
                    c_source.jid)
            old_groups = c_source.groups

            # Remove old source contact(s)
            if was_big_brother:
                # We have got little brothers. Readd them all
                self._remove_metacontact_family(old_family, account_source)
            else:
                # We are only a litle brother. Simply remove us from our big
                # brother
                if self._get_contact_iter(c_source.jid, account_source):
                    # When we have been in the group before.
                    # Do not try to remove us again
                    self._remove_entity(c_source, account_source)

                own_data = {}
                own_data['jid'] = c_source.jid
                own_data['account'] = account_source
                # Don't touch the rest of the family
                old_family = [own_data]

            # Apply new tag and update contact
            for data in old_family:
                if account_source != data['account'] and not self.regroup:
                    continue

                _account = data['account']
                _jid = data['jid']
                _contact = app.contacts.get_first_contact_from_jid(_account,
                    _jid)
                if not _contact:
                    # One of the metacontacts may be not connected.
                    continue

                _contact.groups = c_dest.groups[:]
                app.contacts.add_metacontact(account_dest, c_dest.jid,
                    _account, _contact.jid, contacts)
                app.connections[account_source].update_contact(_contact.jid,
                    _contact.name, _contact.groups)

            # Re-add all and update GUI
            new_family = app.contacts.get_metacontacts_family(account_source,
                c_source.jid)
            brothers = self._add_metacontact_family(new_family, account_source)

            for c, acc in brothers:
                self.draw_completely(c.jid, acc)

            old_groups.extend(c_dest.groups)
            for g in old_groups:
                self.draw_group(g, account_source)

            self.draw_account(account_source)
            context.finish(True, True, etime)

        dest_family = app.contacts.get_metacontacts_family(account_dest,
            c_dest.jid)
        source_family = app.contacts.get_metacontacts_family(account_source,
            c_source.jid)
        confirm_metacontacts = app.config.get('confirm_metacontacts')
        if confirm_metacontacts == 'no' or dest_family == source_family:
            merge_contacts()
            return
        pritext = _('You are about to create a metacontact. Are you sure you '
            'want to continue?')
        sectext = _('Metacontacts are a way to regroup several contacts in one '
            'line. Generally it is used when the same person has several '
            'XMPP accounts or transport accounts.')
        dlg = dialogs.ConfirmationDialogCheck(pritext, sectext,
            _('_Do not ask me again'), on_response_ok=merge_contacts)
        if not confirm_metacontacts: # First time we see this window
            dlg.checkbutton.set_active(True)

    def on_drop_in_group(self, widget, account, c_source, grp_dest,
    is_big_brother, context, etime, grp_source = None):
        if is_big_brother:
            # add whole metacontact to new group
            self.add_contact_to_groups(c_source.jid, account, [grp_dest, ])
            # remove afterwards so the contact is not moved to General in the
            # meantime
            if grp_dest != grp_source:
                self.remove_contact_from_groups(c_source.jid, account,
                    [grp_source])
        else:
            # Normal contact or little brother
            family = app.contacts.get_metacontacts_family(account,
                c_source.jid)
            if family:
                # Little brother
                # Remove whole family. Remove us from the family.
                # Then re-add other family members.
                self._remove_metacontact_family(family, account)
                app.contacts.remove_metacontact(account, c_source.jid)
                for data in family:
                    if account != data['account'] and not self.regroup:
                        continue
                    if data['jid'] == c_source.jid and\
                    data['account'] == account:
                        continue
                    self.add_contact(data['jid'], data['account'])
                    break

                self.add_contact_to_groups(c_source.jid, account, [grp_dest, ])

            else:
                # Normal contact
                self.add_contact_to_groups(c_source.jid, account, [grp_dest, ])
                # remove afterwards so the contact is not moved to General in
                # the meantime
                if grp_dest != grp_source:
                    self.remove_contact_from_groups(c_source.jid, account,
                        [grp_source])

        if context.get_actions() in (Gdk.DragAction.MOVE, Gdk.DragAction.COPY):
            context.finish(True, True, etime)

    def drag_drop(self, treeview, context, x, y, timestamp):
        target_list = treeview.drag_dest_get_target_list()
        target = treeview.drag_dest_find_target(context, target_list)
        treeview.drag_get_data(context, target, 0)
        context.finish(False, True, 0)
        return True

    def move_group(self, old_name, new_name, account):
        for group in list(app.groups[account].keys()):
            if group.startswith(old_name):
                self.rename_group(group, group.replace(old_name, new_name),
                    account)

    def drag_data_received_data(self, treeview, context, x, y, selection, info,
    etime):
        treeview.stop_emission_by_name('drag_data_received')
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if not drop_info:
            return
        data = selection.get_data().decode()
        if not data:
            return # prevents tb when several entrys are dragged
        model = treeview.get_model()

        path_dest, position = drop_info

        if position == Gtk.TreeViewDropPosition.BEFORE and len(path_dest) == 2 \
        and path_dest[1] == 0: # dropped before the first group
            return
        if position == Gtk.TreeViewDropPosition.BEFORE and len(path_dest) == 2:
            # dropped before a group: we drop it in the previous group every
            # time
            path_dest = (path_dest[0], path_dest[1]-1)
        # destination: the row something got dropped on
        iter_dest = model.get_iter(path_dest)
        type_dest = model[iter_dest][Column.TYPE]
        jid_dest = model[iter_dest][Column.JID]
        account_dest = model[iter_dest][Column.ACCOUNT]

        # drop on account row in merged mode, we cannot know the desired account
        if account_dest == 'all':
            return
        # nothing can be done, if destination account is offline
        if app.connections[account_dest].connected < 2:
            return

        # A file got dropped on the roster
        if info == self.TARGET_TYPE_URI_LIST:
            if len(path_dest) < 3:
                return
            if type_dest != 'contact':
                return
            c_dest = app.contacts.get_contact_with_highest_priority(
                account_dest, jid_dest)
            if not c_dest.supports(NS_FILE):
                return
            uri = data.strip()
            uri_splitted = uri.split() # we may have more than one file dropped
            try:
                # This is always the last element in windows
                uri_splitted.remove('\0')
            except ValueError:
                pass
            nb_uri = len(uri_splitted)
            # Check the URIs
            bad_uris = []
            for a_uri in uri_splitted:
                path = helpers.get_file_path_from_dnd_dropped_uri(a_uri)
                if not os.path.isfile(path):
                    bad_uris.append(a_uri)
            if len(bad_uris):
                dialogs.ErrorDialog(_('Invalid file URI:'), '\n'.join(bad_uris))
                return
            def _on_send_files(account, jid, uris):
                c = app.contacts.get_contact_with_highest_priority(account,
                    jid)
                for uri in uris:
                    path = helpers.get_file_path_from_dnd_dropped_uri(uri)
                    if os.path.isfile(path): # is it file?
                        app.interface.instances['file_transfers'].send_file(
                            account, c, path)
            # Popup dialog to confirm sending
            prim_text = 'Send file?'
            sec_text = i18n.ngettext('Do you want to send this file to %s:',
                'Do you want to send these files to %s:', nb_uri) %\
                c_dest.get_shown_name()
            for uri in uri_splitted:
                path = helpers.get_file_path_from_dnd_dropped_uri(uri)
                sec_text += '\n' + os.path.basename(path)
            dialog = dialogs.NonModalConfirmationDialog(prim_text, sec_text,
                on_response_ok=(_on_send_files, account_dest, jid_dest,
                uri_splitted))
            dialog.popup()
            return

        # a roster entry was dragged and dropped somewhere in the roster

        # source: the row that was dragged
        path_source = treeview.get_selection().get_selected_rows()[1][0]
        iter_source = model.get_iter(path_source)
        type_source = model[iter_source][Column.TYPE]
        account_source = model[iter_source][Column.ACCOUNT]

        if app.config.get_per('accounts', account_source, 'is_zeroconf'):
            return

        if type_dest == 'self_contact':
            # drop on self contact row
            return

        if type_dest == 'groupchat':
            # drop on a minimized groupchat
            # TODO: Invite to groupchat if type_dest = contact
            return

        if type_source == 'group':
            if account_source != account_dest:
                # drop on another account
                return
            grp_source = model[iter_source][Column.JID]
            delimiter = app.connections[account_source].nested_group_delimiter
            grp_source_list = grp_source.split(delimiter)
            new_grp = None
            if type_dest == 'account':
                new_grp = grp_source_list[-1]
            elif type_dest == 'group':
                grp_dest = model[iter_dest][Column.JID]
                grp_dest_list = grp_dest.split(delimiter)
                # Do not allow to drop on a subgroup of source group
                if grp_source_list[0] != grp_dest_list[0]:
                    new_grp = model[iter_dest][Column.JID] + delimiter + \
                        grp_source_list[-1]
            if new_grp:
                self.move_group(grp_source, new_grp, account_source)

        # Only normal contacts and group can be dragged
        if type_source != 'contact':
            return

        # A contact was dropped
        if app.config.get_per('accounts', account_dest, 'is_zeroconf'):
            # drop on zeroconf account, adding not possible
            return

        if type_dest == 'account' and account_source == account_dest:
            # drop on the account it was dragged from
            return

        # Get valid source group, jid and contact
        it = iter_source
        while model[it][Column.TYPE] == 'contact':
            it = model.iter_parent(it)
        grp_source = model[it][Column.JID]
        if grp_source in helpers.special_groups and \
                grp_source not in ('Not in Roster', 'Observers'):
            # a transport or a minimized groupchat was dragged
            # we can add it to other accounts but not move it to another group,
            # see below
            return
        jid_source = data
        c_source = app.contacts.get_contact_with_highest_priority(
            account_source, jid_source)

        # Get destination group
        grp_dest = None
        if type_dest == 'group':
            grp_dest = model[iter_dest][Column.JID]
        elif type_dest in ('contact', 'agent'):
            it = iter_dest
            while model[it][Column.TYPE] != 'group':
                it = model.iter_parent(it)
            grp_dest = model[it][Column.JID]
        if grp_dest in helpers.special_groups:
            return

        if jid_source == jid_dest:
            if grp_source == grp_dest and account_source == account_dest:
                # Drop on self
                return

        # contact drop somewhere in or on a foreign account
        if (type_dest == 'account' or not self.regroup) and \
        account_source != account_dest:
            # add to account in specified group
            dialogs.AddNewContactWindow(account=account_dest, jid=jid_source,
                user_nick=c_source.name, group=grp_dest)
            return

        # we may not add contacts from special_groups
        if grp_source in helpers.special_groups :
            return

        # Is the contact we drag a meta contact?
        accounts = (self.regroup and app.contacts.get_accounts()) or \
                account_source
        is_big_brother = app.contacts.is_big_brother(account_source,
            jid_source, accounts)

        drop_in_middle_of_meta = False
        if type_dest == 'contact':
            if position == Gtk.TreeViewDropPosition.BEFORE and len(path_dest) == 4:
                drop_in_middle_of_meta = True
            if position == Gtk.TreeViewDropPosition.AFTER and (len(path_dest) == 4 or\
            self.modelfilter.iter_has_child(iter_dest)):
                drop_in_middle_of_meta = True
        # Contact drop on group row or between two contacts that are
        # not metacontacts
        if (type_dest == 'group' or position in (Gtk.TreeViewDropPosition.BEFORE,
        Gtk.TreeViewDropPosition.AFTER)) and not drop_in_middle_of_meta:
            self.on_drop_in_group(None, account_source, c_source, grp_dest,
                is_big_brother, context, etime, grp_source)
            return

        # Contact drop on another contact, make meta contacts
        if position == Gtk.TreeViewDropPosition.INTO_OR_AFTER or \
        position == Gtk.TreeViewDropPosition.INTO_OR_BEFORE or drop_in_middle_of_meta:
            c_dest = app.contacts.get_contact_with_highest_priority(
                account_dest, jid_dest)
            if not c_dest:
                # c_dest is None if jid_dest doesn't belong to account
                return
            menu = Gtk.Menu()
            item = Gtk.MenuItem.new_with_label(_('Send %(from)s to %(to)s') % {
                'from': c_source.get_shown_name(), 'to': c_dest.get_shown_name()})
            item.set_use_underline(False)
            item.connect('activate', self.on_drop_rosterx, account_source,
            c_source, account_dest, c_dest, is_big_brother, context, etime)
            menu.append(item)

            dest_family = app.contacts.get_metacontacts_family(account_dest,
                c_dest.jid)
            source_family = app.contacts.get_metacontacts_family(
                account_source, c_source.jid)
            if dest_family == source_family  and dest_family:
                item = Gtk.MenuItem.new_with_label(
                    _('Make %s first contact') % (
                    c_source.get_shown_name()))
                item.set_use_underline(False)
            else:
                item = Gtk.MenuItem.new_with_label(
                    _('Make %(contact1)s and %(contact2)s metacontacts') % {
                    'contact1': c_source.get_shown_name(), 'contact2': c_dest.get_shown_name()})
                item.set_use_underline(False)

            item.connect('activate', self.on_drop_in_contact, account_source,
            c_source, account_dest, c_dest, is_big_brother, context, etime)

            menu.append(item)

            menu.attach_to_widget(self.tree, None)
            menu.connect('selection-done', gtkgui_helpers.destroy_widget)
            menu.show_all()
            menu.popup(None, None, None, None, 1, etime)

################################################################################
### Everything about images and icons....
### Cleanup assigned to Jim++ :-)
################################################################################

    def update_jabber_state_images(self):
        # Update the roster
        self.setup_and_draw_roster()
        # Update the status combobox
        self.status_combobox.queue_draw()
        # Update the systray
        if app.interface.systray_enabled:
            app.interface.systray.set_img()

        for win in app.interface.msg_win_mgr.windows():
            for ctrl in win.controls():
                ctrl.update_ui()
                win.redraw_tab(ctrl)

        self.update_status_combobox()

    def set_account_status_icon(self, account):
        status = app.connections[account].connected
        child_iterA = self._get_account_iter(account, self.model)
        if not child_iterA:
            return
        if not self.regroup:
            show = app.SHOW_LIST[status]
        else: # accounts merged
            show = helpers.get_global_show()
        image = gtkgui_helpers.get_image_from_icon_name(
            show, self.scale_factor)
        self.model[child_iterA][Column.IMG] = image

################################################################################
### Style and theme related methods
################################################################################

    def show_title(self):
        change_title_allowed = app.config.get('change_roster_title')
        if not change_title_allowed:
            return

        nb_unread = 0
        for account in app.connections:
            # Count events in roster title only if we don't auto open them
            if not helpers.allow_popup_window(account):
                nb_unread += app.events.get_nb_events(['chat', 'normal',
                    'file-request', 'file-error', 'file-completed',
                    'file-request-error', 'file-send-error', 'file-stopped',
                    'printed_chat'], account)


        if app.config.get('one_message_window') == 'always_with_roster':
            # always_with_roster mode defers to the MessageWindow
            if not app.interface.msg_win_mgr.one_window_opened():
                # No MessageWindow to defer to
                self.window.set_title('Gajim')
            gtkgui_helpers.set_unset_urgency_hint(self.window, nb_unread)
            return

        start = ''
        if nb_unread > 1:
            start = '[' + str(nb_unread) + ']  '
        elif nb_unread == 1:
            start = '*  '

        self.window.set_title(start + 'Gajim')

        gtkgui_helpers.set_unset_urgency_hint(self.window, nb_unread)

    def _change_style(self, model, path, titer, option):
        if option is None or model[titer][Column.TYPE] == option:
            # We changed style for this type of row
            model[titer][Column.NAME] = model[titer][Column.NAME]

    def change_roster_style(self, option):
        self.model.foreach(self._change_style, option)
        for win in app.interface.msg_win_mgr.windows():
            win.repaint_themed_widgets()

    def repaint_themed_widgets(self):
        """
        Notify windows that contain themed widgets to repaint them
        """
        for win in app.interface.msg_win_mgr.windows():
            win.repaint_themed_widgets()
        for account in app.connections:
            for ctrl in list(app.interface.minimized_controls[account].values()):
                ctrl.repaint_themed_widgets()

    def _iconCellDataFunc(self, column, renderer, model, titer, data=None):
        """
        When a row is added, set properties for icon renderer
        """
        try:
            type_ = model[titer][Column.TYPE]
        except TypeError:
            return

        if type_ == 'account':
            self._set_account_row_background_color(renderer)
            renderer.set_property('xalign', 0)
        elif type_ == 'group':
            self._set_group_row_background_color(renderer)
            parent_iter = model.iter_parent(titer)
            if model[parent_iter][Column.TYPE] == 'group':
                renderer.set_property('xalign', 0.4)
            else:
                renderer.set_property('xalign', 0.6)
        elif type_:
            # prevent type_ = None, see http://trac.gajim.org/ticket/2534
            if not model[titer][Column.JID] or not model[titer][Column.ACCOUNT]:
                # This can append when at the moment we add the row
                return
            jid = model[titer][Column.JID]
            account = model[titer][Column.ACCOUNT]
            self._set_contact_row_background_color(renderer, jid, account)
            parent_iter = model.iter_parent(titer)
            if model[parent_iter][Column.TYPE] == 'contact':
                renderer.set_property('xalign', 1)
            else:
                renderer.set_property('xalign', 0.6)
        renderer.set_property('width', 26)

        image = model[titer][Column.IMG]
        surface = image.get_property('surface')
        renderer.set_property('surface', surface)

    def _nameCellDataFunc(self, column, renderer, model, titer, data=None):
        """
        When a row is added, set properties for name renderer
        """
        try:
            type_ = model[titer][Column.TYPE]
        except TypeError:
            return
        theme = app.config.get('roster_theme')
        if type_ == 'account':
            color = app.config.get_per('themes', theme, 'accounttextcolor')
            renderer.set_property('foreground', color or None)
            renderer.set_property('font',
                gtkgui_helpers.get_theme_font_for_option(theme, 'accountfont'))
            renderer.set_property('xpad', 0)
            renderer.set_property('width', 3)
            self._set_account_row_background_color(renderer)
        elif type_ == 'group':
            color = app.config.get_per('themes', theme, 'grouptextcolor')
            renderer.set_property('foreground', color or None)
            renderer.set_property('font',
                gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))
            parent_iter = model.iter_parent(titer)
            if model[parent_iter][Column.TYPE] == 'group':
                renderer.set_property('xpad', 8)
            else:
                renderer.set_property('xpad', 4)
            self._set_group_row_background_color(renderer)
        elif type_:
            # prevent type_ = None, see http://trac.gajim.org/ticket/2534
            if not model[titer][Column.JID] or not model[titer][Column.ACCOUNT]:
                # This can append when at the moment we add the row
                return
            jid = model[titer][Column.JID]
            account = model[titer][Column.ACCOUNT]
            color = None
            if type_ == 'groupchat':
                ctrl = app.interface.minimized_controls[account].get(jid,
                    None)
                if ctrl and ctrl.attention_flag:
                    color = app.config.get_per('themes', theme,
                        'state_muc_directed_msg_color')
                renderer.set_property('foreground', 'red')
            if not color:
                color = app.config.get_per('themes', theme,
                    'contacttextcolor')
            if color:
                renderer.set_property('foreground', color)
            else:
                renderer.set_property('foreground', None)
            self._set_contact_row_background_color(renderer, jid, account)
            renderer.set_property('font',
                gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
            parent_iter = model.iter_parent(titer)
            if model[parent_iter][Column.TYPE] == 'contact':
                renderer.set_property('xpad', 16)
            else:
                renderer.set_property('xpad', 12)

    def _fill_pep_pixbuf_renderer(self, column, renderer, model, titer,
    data=None):
        """
        When a row is added, draw the respective pep icon
        """
        try:
            type_ = model[titer][Column.TYPE]
        except TypeError:
            return

        # allocate space for the icon only if needed
        if not model[titer][data] or model[titer][data] == empty_pixbuf:
            renderer.set_property('visible', False)
        else:
            renderer.set_property('visible', True)

            if type_ == 'account':
                self._set_account_row_background_color(renderer)
                renderer.set_property('xalign', 1)
            elif type_:
                if not model[titer][Column.JID] or not model[titer][Column.ACCOUNT]:
                    # This can append at the moment we add the row
                    return
                jid = model[titer][Column.JID]
                account = model[titer][Column.ACCOUNT]
                self._set_contact_row_background_color(renderer, jid, account)

    def _fill_avatar_pixbuf_renderer(self, column, renderer, model, titer,
    data=None):
        """
        When a row is added, set properties for avatar renderer
        """
        try:
            type_ = model[titer][Column.TYPE]
        except TypeError:
            return

        if type_ in ('group', 'account'):
            renderer.set_property('visible', False)
            return

        image = model[titer][Column.AVATAR_IMG]
        surface = image.get_property('surface')
        renderer.set_property('surface', surface)
        # allocate space for the icon only if needed
        if model[titer][Column.AVATAR_IMG] or \
        app.config.get('avatar_position_in_roster') == 'left':
            renderer.set_property('visible', True)
            if type_:
                # prevent type_ = None, see http://trac.gajim.org/ticket/2534
                if not model[titer][Column.JID] or not model[titer][Column.ACCOUNT]:
                    # This can append at the moment we add the row
                    return
                jid = model[titer][Column.JID]
                account = model[titer][Column.ACCOUNT]
                self._set_contact_row_background_color(renderer, jid, account)
        else:
            renderer.set_property('visible', False)
        if model[titer][Column.AVATAR_IMG] is None and \
        app.config.get('avatar_position_in_roster') != 'left':
            renderer.set_property('visible', False)

        if app.config.get('avatar_position_in_roster') == 'left':
            renderer.set_property('width', AvatarSize.ROSTER)
            renderer.set_property('xalign', 0.5)
        else:
            renderer.set_property('xalign', 1) # align pixbuf to the right

    def _fill_padlock_pixbuf_renderer(self, column, renderer, model, titer,
    data=None):
        """
        When a row is added, set properties for padlock renderer
        """
        try:
            type_ = model[titer][Column.TYPE]
        except TypeError:
            return

        # allocate space for the icon only if needed
        if type_ == 'account' and model[titer][Column.PADLOCK_PIXBUF]:
            renderer.set_property('visible', True)
            self._set_account_row_background_color(renderer)
            renderer.set_property('xalign', 1) # align pixbuf to the right
        else:
            renderer.set_property('visible', False)

    def _set_account_row_background_color(self, renderer):
        theme = app.config.get('roster_theme')
        color = app.config.get_per('themes', theme, 'accountbgcolor')
        renderer.set_property('cell-background', color or None)

    def _set_contact_row_background_color(self, renderer, jid, account):
        theme = app.config.get('roster_theme')
        if jid in app.newly_added[account]:
            renderer.set_property('cell-background', app.config.get(
                    'just_connected_bg_color'))
        elif jid in app.to_be_removed[account]:
            renderer.set_property('cell-background', app.config.get(
                'just_disconnected_bg_color'))
        else:
            color = app.config.get_per('themes', theme, 'contactbgcolor')
            renderer.set_property('cell-background', color or None)

    def _set_group_row_background_color(self, renderer):
        theme = app.config.get('roster_theme')
        color = app.config.get_per('themes', theme, 'groupbgcolor')
        renderer.set_property('cell-background', color or None)

################################################################################
### Everything about building menus
### FIXME: We really need to make it simpler! 1465 lines are a few to much....
################################################################################

    def build_account_menu(self, account):
        # we have to create our own set of icons for the menu
        # using self.jabber_status_images is poopoo
        iconset = app.config.get('iconset')
        path = os.path.join(helpers.get_iconset_path(iconset), '16x16')

        if not app.config.get_per('accounts', account, 'is_zeroconf'):
            xml = gtkgui_helpers.get_gtk_builder('account_context_menu.ui')
            account_context_menu = xml.get_object('account_context_menu')

            status_menuitem = xml.get_object('status_menuitem')
            join_group_chat_menuitem = xml.get_object(
                'join_group_chat_menuitem')
            add_contact_menuitem = xml.get_object('add_contact_menuitem')
            service_discovery_menuitem = xml.get_object(
                'service_discovery_menuitem')
            execute_command_menuitem = xml.get_object(
                'execute_command_menuitem')
            edit_account_menuitem = xml.get_object('edit_account_menuitem')
            sub_menu = Gtk.Menu()
            status_menuitem.set_submenu(sub_menu)

            for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
                uf_show = helpers.get_uf_show(show, use_mnemonic=True)
                item = Gtk.MenuItem.new_with_mnemonic(uf_show)
                sub_menu.append(item)
                con = app.connections[account]
                if show == 'invisible' and con.connected > 1 and \
                not con.privacy_rules_supported:
                    item.set_sensitive(False)
                else:
                    item.connect('activate', self.change_status, account, show)

            item = Gtk.SeparatorMenuItem.new()
            sub_menu.append(item)

            item = Gtk.MenuItem.new_with_mnemonic(_('_Change Status Message'))
            sub_menu.append(item)
            item.connect('activate', self.on_change_status_message_activate,
                account)
            if app.connections[account].connected < 2:
                item.set_sensitive(False)

            item = Gtk.SeparatorMenuItem.new()
            sub_menu.append(item)

            uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
            item = Gtk.MenuItem.new_with_mnemonic(uf_show)
            sub_menu.append(item)
            item.connect('activate', self.change_status, account, 'offline')

            pep_menuitem = xml.get_object('pep_menuitem')
            if app.connections[account].pep_supported:
                pep_submenu = Gtk.Menu()
                pep_menuitem.set_submenu(pep_submenu)

                item = Gtk.CheckMenuItem(_('Publish Tune'))
                pep_submenu.append(item)
                if not dbus_support.supported:
                    item.set_sensitive(False)
                else:
                    activ = app.config.get_per('accounts', account,
                                               'publish_tune')
                    item.set_active(activ)
                    item.connect('toggled', self.on_publish_tune_toggled,
                                 account)

                item = Gtk.CheckMenuItem(_('Publish Location'))
                pep_submenu.append(item)
                if not app.HAVE_GEOCLUE:
                    item.set_sensitive(False)
                else:
                    activ = app.config.get_per('accounts', account,
                                               'publish_location')
                    item.set_active(activ)
                    item.connect('toggled', self.on_publish_location_toggled,
                                 account)

                pep_config = Gtk.MenuItem.new_with_label(
                    _('Configure Services…'))
                item = Gtk.SeparatorMenuItem.new()
                pep_submenu.append(item)
                pep_config.set_sensitive(True)
                pep_submenu.append(pep_config)
                pep_config.connect('activate',
                    self.on_pep_services_menuitem_activate, account)

            else:
                pep_menuitem.set_sensitive(False)

            edit_account_menuitem.connect('activate', self.on_edit_account,
                account)
            if app.connections[account].roster_supported:
                add_contact_menuitem.connect('activate',
                    self.on_add_new_contact, account)
            else:
                add_contact_menuitem.set_sensitive(False)
            service_discovery_menuitem.connect('activate',
                self.on_service_disco_menuitem_activate, account)
            hostname = app.config.get_per('accounts', account, 'hostname')
            contact = app.contacts.create_contact(jid=hostname,
                account=account) # Fake contact
            execute_command_menuitem.connect('activate',
                self.on_execute_command, contact, account)

            gc_sub_menu = Gtk.Menu() # gc is always a submenu
            join_group_chat_menuitem.set_submenu(gc_sub_menu)
            self.add_bookmarks_list(gc_sub_menu, account)

            # make some items insensitive if account is offline
            if app.connections[account].connected < 2:
                for widget in (add_contact_menuitem, service_discovery_menuitem,
                join_group_chat_menuitem, execute_command_menuitem,
                pep_menuitem):
                    widget.set_sensitive(False)
        else:
            xml = gtkgui_helpers.get_gtk_builder('zeroconf_context_menu.ui')
            account_context_menu = xml.get_object('zeroconf_context_menu')

            status_menuitem = xml.get_object('status_menuitem')
            zeroconf_properties_menuitem = xml.get_object(
                    'zeroconf_properties_menuitem')
            sub_menu = Gtk.Menu()
            status_menuitem.set_submenu(sub_menu)

            for show in ('online', 'away', 'dnd', 'invisible'):
                uf_show = helpers.get_uf_show(show, use_mnemonic=True)
                item = Gtk.MenuItem.new_with_mnemonic(uf_show)
                sub_menu.append(item)
                item.connect('activate', self.change_status, account, show)

            item = Gtk.SeparatorMenuItem.new()
            sub_menu.append(item)

            item = Gtk.MenuItem.new_with_mnemonic(_('_Change Status Message'))
            sub_menu.append(item)
            item.connect('activate', self.on_change_status_message_activate,
                account)
            if app.connections[account].connected < 2:
                item.set_sensitive(False)

            uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
            item = Gtk.MenuItem.new_with_mnemonic(uf_show)
            sub_menu.append(item)
            item.connect('activate', self.change_status, account, 'offline')

            zeroconf_properties_menuitem.connect('activate',
                self.on_edit_account, account)

        return account_context_menu

    def make_account_menu(self, event, titer):
        """
        Make account's popup menu
        """
        model = self.modelfilter
        account = model[titer][Column.ACCOUNT]

        if account != 'all': # not in merged mode
            menu = self.build_account_menu(account)
        else:
            menu = Gtk.Menu()
            iconset = app.config.get('iconset')
            path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
            accounts = [] # Put accounts in a list to sort them
            for account in app.connections:
                accounts.append(account)
            accounts.sort()
            for account in accounts:
                label = app.config.get_per('accounts', account,
                                           'account_label')
                item = Gtk.MenuItem.new_with_label(label or account)
                account_menu = self.build_account_menu(account)
                item.set_submenu(account_menu)
                menu.append(item)

        event_button = gtkgui_helpers.get_possible_button_event(event)

        menu.attach_to_widget(self.tree, None)
        menu.connect('selection-done', gtkgui_helpers.destroy_widget)
        menu.show_all()
        menu.popup(None, None, None, None, event_button, event.time)

    def make_group_menu(self, event, titer):
        """
        Make group's popup menu
        """
        model = self.modelfilter
        path = model.get_path(titer)
        group = model[titer][Column.JID]
        account = model[titer][Column.ACCOUNT]

        list_ = [] # list of (contact, account) tuples
        list_online = [] # list of (contact, account) tuples

        show_bookmarked = True
        group = model[titer][Column.JID]
        for jid in app.contacts.get_jid_list(account):
            contact = app.contacts.get_contact_with_highest_priority(account,
                jid)
            if group in contact.get_shown_groups():
                if contact.show not in ('offline', 'error'):
                    list_online.append((contact, account))
                    # Check that all contacts support direct NUC invite
                    if not contact.supports(NS_CONFERENCE):
                        show_bookmarked = False
                list_.append((contact, account))
        menu = Gtk.Menu()

        # Make special context menu if group is Groupchats
        if group == _('Groupchats'):
            maximize_menuitem = Gtk.MenuItem.new_with_mnemonic(_(
                '_Maximize All'))
            maximize_menuitem.connect('activate',
                self.on_all_groupchat_maximized, list_)
            menu.append(maximize_menuitem)
        else:
            # Send Group Message
            send_group_message_item = Gtk.MenuItem.new_with_mnemonic(
                _('Send Group M_essage'))

            send_group_message_submenu = Gtk.Menu()
            send_group_message_item.set_submenu(send_group_message_submenu)
            menu.append(send_group_message_item)

            group_message_to_all_item = Gtk.MenuItem.new_with_label(_(
                'To all users'))
            send_group_message_submenu.append(group_message_to_all_item)

            group_message_to_all_online_item = Gtk.MenuItem.new_with_label(
                _('To all online users'))
            send_group_message_submenu.append(group_message_to_all_online_item)

            group_message_to_all_online_item.connect('activate',
                self.on_send_single_message_menuitem_activate, account,
                list_online)
            group_message_to_all_item.connect('activate',
                self.on_send_single_message_menuitem_activate, account, list_)

            # Invite to
            if group != _('Transports'):
                invite_menuitem = Gtk.MenuItem.new_with_mnemonic(
                    _('In_vite to'))

                gui_menu_builder.build_invite_submenu(invite_menuitem,
                    list_online, show_bookmarked=show_bookmarked)
                menu.append(invite_menuitem)

            # Send Custom Status
            send_custom_status_menuitem = Gtk.MenuItem.new_with_mnemonic(
                _('Send Cus_tom Status'))
            if helpers.group_is_blocked(account, group):
                send_custom_status_menuitem.set_sensitive(False)
            status_menuitems = Gtk.Menu()
            send_custom_status_menuitem.set_submenu(status_menuitems)
            iconset = app.config.get('iconset')
            path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
            for s in ('online', 'chat', 'away', 'xa', 'dnd', 'offline'):
                status_menuitem = Gtk.MenuItem.new_with_label(
                    helpers.get_uf_show(s))
                status_menuitem.connect('activate', self.on_send_custom_status,
                    list_, s, group)
                status_menuitems.append(status_menuitem)
            menu.append(send_custom_status_menuitem)

            # there is no singlemessage and custom status for zeroconf
            if app.config.get_per('accounts', account, 'is_zeroconf'):
                send_custom_status_menuitem.set_sensitive(False)
                send_group_message_item.set_sensitive(False)

            if app.connections[account].connected < 2:
                send_group_message_item.set_sensitive(False)
                invite_menuitem.set_sensitive(False)
                send_custom_status_menuitem.set_sensitive(False)

        if not group in helpers.special_groups:
            item = Gtk.SeparatorMenuItem.new() # separator
            menu.append(item)

            # Rename
            rename_item = Gtk.MenuItem.new_with_mnemonic(_('_Rename…'))
            menu.append(rename_item)
            rename_item.connect('activate', self.on_rename, 'group', group,
                account)

            # Block group
            is_blocked = False
            if self.regroup:
                for g_account in app.connections:
                    if helpers.group_is_blocked(g_account, group):
                        is_blocked = True
            else:
                if helpers.group_is_blocked(account, group):
                    is_blocked = True

            if is_blocked and app.connections[account].\
            privacy_rules_supported:
                unblock_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Unblock'))
                unblock_menuitem.connect('activate', self.on_unblock, list_,
                    group)
                menu.append(unblock_menuitem)
            else:
                block_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Block'))
                block_menuitem.connect('activate', self.on_block, list_, group)
                menu.append(block_menuitem)
                if not app.connections[account].privacy_rules_supported:
                    block_menuitem.set_sensitive(False)

            # Remove group
            remove_item = Gtk.MenuItem.new_with_mnemonic(_('Remo_ve'))
            menu.append(remove_item)
            remove_item.connect('activate', self.on_remove_group_item_activated,
                group, account)

            # unsensitive if account is not connected
            if app.connections[account].connected < 2:
                rename_item.set_sensitive(False)

            # General group cannot be changed
            if group == _('General'):
                rename_item.set_sensitive(False)
                remove_item.set_sensitive(False)

        event_button = gtkgui_helpers.get_possible_button_event(event)

        menu.attach_to_widget(self.tree, None)
        menu.connect('selection-done', gtkgui_helpers.destroy_widget)
        menu.show_all()
        menu.popup(None, None, None, None, event_button, event.time)

    def make_contact_menu(self, event, titer):
        """
        Make contact's popup menu
        """
        model = self.modelfilter
        jid = model[titer][Column.JID]
        account = model[titer][Column.ACCOUNT]
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        menu = gui_menu_builder.get_contact_menu(contact, account)
        event_button = gtkgui_helpers.get_possible_button_event(event)
        menu.attach_to_widget(self.tree, None)
        menu.popup(None, None, None, None, event_button, event.time)

    def make_multiple_contact_menu(self, event, iters):
        """
        Make group's popup menu
        """
        model = self.modelfilter
        list_ = [] # list of (jid, account) tuples
        one_account_offline = False
        is_blocked = True
        privacy_rules_supported = True
        for titer in iters:
            jid = model[titer][Column.JID]
            account = model[titer][Column.ACCOUNT]
            if app.connections[account].connected < 2:
                one_account_offline = True
            if not app.connections[account].privacy_rules_supported:
                privacy_rules_supported = False
            contact = app.contacts.get_contact_with_highest_priority(account,
                jid)
            if not helpers.jid_is_blocked(account, jid):
                is_blocked = False
            list_.append((contact, account))

        menu = Gtk.Menu()
        account = None
        for (contact, current_account) in list_:
            # check that we use the same account for every sender
            if account is not None and account != current_account:
                account = None
                break
            account = current_account
        show_bookmarked = True
        for (contact, current_account) in list_:
            # Check that all contacts support direct NUC invite
            if not contact.supports(NS_CONFERENCE):
                show_bookmarked = False
                break
        if account is not None:
            send_group_message_item = Gtk.MenuItem.new_with_mnemonic(
                _('Send Group M_essage'))
            menu.append(send_group_message_item)
            send_group_message_item.connect('activate',
                self.on_send_single_message_menuitem_activate, account, list_)

        # Invite to Groupchat
        invite_item = Gtk.MenuItem.new_with_mnemonic(_('In_vite to'))

        gui_menu_builder.build_invite_submenu(invite_item, list_,
            show_bookmarked=show_bookmarked)
        menu.append(invite_item)

        item = Gtk.SeparatorMenuItem.new() # separator
        menu.append(item)

        # Manage Transport submenu
        item = Gtk.MenuItem.new_with_mnemonic(_('_Manage Contacts'))
        manage_contacts_submenu = Gtk.Menu()
        item.set_submenu(manage_contacts_submenu)
        menu.append(item)

        # Edit Groups
        edit_groups_item = Gtk.MenuItem.new_with_mnemonic(_('Edit _Groups…'))
        manage_contacts_submenu.append(edit_groups_item)
        edit_groups_item.connect('activate', self.on_edit_groups, list_)

        item = Gtk.SeparatorMenuItem.new() # separator
        manage_contacts_submenu.append(item)

        # Block
        if is_blocked and privacy_rules_supported:
            unblock_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Unblock'))
            unblock_menuitem.connect('activate', self.on_unblock, list_)
            manage_contacts_submenu.append(unblock_menuitem)
        else:
            block_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Block'))
            block_menuitem.connect('activate', self.on_block, list_)
            manage_contacts_submenu.append(block_menuitem)

            if not privacy_rules_supported:
                block_menuitem.set_sensitive(False)

        # Remove
        remove_item = Gtk.MenuItem.new_with_mnemonic(_('_Remove'))
        manage_contacts_submenu.append(remove_item)
        remove_item.connect('activate', self.on_req_usub, list_)
        # unsensitive remove if one account is not connected
        if one_account_offline:
            remove_item.set_sensitive(False)

        event_button = gtkgui_helpers.get_possible_button_event(event)

        menu.attach_to_widget(self.tree, None)
        menu.connect('selection-done', gtkgui_helpers.destroy_widget)
        menu.show_all()
        menu.popup(None, None, None, None, event_button, event.time)

    def make_transport_menu(self, event, titer):
        """
        Make transport's popup menu
        """
        model = self.modelfilter
        jid = model[titer][Column.JID]
        path = model.get_path(titer)
        account = model[titer][Column.ACCOUNT]
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        menu = gui_menu_builder.get_transport_menu(contact, account)
        event_button = gtkgui_helpers.get_possible_button_event(event)
        menu.attach_to_widget(self.tree, None)
        menu.popup(None, None, None, None, event_button, event.time)

    def make_groupchat_menu(self, event, titer):
        model = self.modelfilter

        jid = model[titer][Column.JID]
        account = model[titer][Column.ACCOUNT]
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        menu = Gtk.Menu()

        if jid in app.interface.minimized_controls[account]:
            maximize_menuitem = Gtk.MenuItem.new_with_mnemonic(_(
                '_Maximize'))
            maximize_menuitem.connect('activate', self.on_groupchat_maximized, \
                jid, account)
            menu.append(maximize_menuitem)

        if not app.gc_connected[account].get(jid, False):
            connect_menuitem = Gtk.MenuItem.new_with_mnemonic(_(
                '_Reconnect'))
            connect_menuitem.connect('activate', self.on_reconnect, jid,
                account)
            menu.append(connect_menuitem)
        disconnect_menuitem = Gtk.MenuItem.new_with_mnemonic(_(
            '_Disconnect'))
        disconnect_menuitem.connect('activate', self.on_disconnect, jid,
            account)
        menu.append(disconnect_menuitem)

        item = Gtk.SeparatorMenuItem.new() # separator
        menu.append(item)

        adhoc_menuitem = Gtk.MenuItem.new_with_mnemonic(_('Execute command'))
        adhoc_menuitem.connect('activate', self.on_execute_command, contact,
            account)
        menu.append(adhoc_menuitem)

        item = Gtk.SeparatorMenuItem.new() # separator
        menu.append(item)

        history_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_History'))
        history_menuitem.connect('activate', self.on_history, contact, account)
        menu.append(history_menuitem)

        event_button = gtkgui_helpers.get_possible_button_event(event)

        menu.attach_to_widget(self.tree, None)
        menu.connect('selection-done', gtkgui_helpers.destroy_widget)
        menu.show_all()
        menu.popup(None, None, None, None, event_button, event.time)

    def get_and_connect_advanced_menuitem_menu(self, account):
        """
        Add FOR ACCOUNT options
        """
        xml = gtkgui_helpers.get_gtk_builder('advanced_menuitem_menu.ui')
        advanced_menuitem_menu = xml.get_object('advanced_menuitem_menu')

        xml_console_menuitem = xml.get_object('xml_console_menuitem')
        archiving_preferences_menuitem = xml.get_object(
            'archiving_preferences_menuitem')
        privacy_lists_menuitem = xml.get_object('privacy_lists_menuitem')
        administrator_menuitem = xml.get_object('administrator_menuitem')
        send_server_message_menuitem = xml.get_object(
            'send_server_message_menuitem')
        set_motd_menuitem = xml.get_object('set_motd_menuitem')
        update_motd_menuitem = xml.get_object('update_motd_menuitem')
        delete_motd_menuitem = xml.get_object('delete_motd_menuitem')

        xml_console_menuitem.connect('activate',
            self.on_xml_console_menuitem_activate, account)

        if app.connections[account]:
            if app.connections[account].privacy_rules_supported:
                privacy_lists_menuitem.connect('activate',
                    self.on_privacy_lists_menuitem_activate, account)
            else:
                privacy_lists_menuitem.set_sensitive(False)
            if app.connections[account].archiving_313_supported:
                archiving_preferences_menuitem.connect(
                    'activate',
                    self.on_archiving_preferences_menuitem_activate, account)
            else:
                archiving_preferences_menuitem.set_sensitive(False)

        if app.connections[account].is_zeroconf:
            administrator_menuitem.set_sensitive(False)
            send_server_message_menuitem.set_sensitive(False)
            set_motd_menuitem.set_sensitive(False)
            update_motd_menuitem.set_sensitive(False)
            delete_motd_menuitem.set_sensitive(False)
        else:
            send_server_message_menuitem.connect('activate',
                self.on_send_server_message_menuitem_activate, account)

            set_motd_menuitem.connect('activate',
                self.on_set_motd_menuitem_activate, account)

            update_motd_menuitem.connect('activate',
                self.on_update_motd_menuitem_activate, account)

            delete_motd_menuitem.connect('activate',
                self.on_delete_motd_menuitem_activate, account)

        advanced_menuitem_menu.show_all()

        return advanced_menuitem_menu

    def add_history_manager_menuitem(self, menu):
        """
        Add a seperator and History Manager menuitem BELOW for account menuitems
        """
        item = Gtk.SeparatorMenuItem.new() # separator
        menu.append(item)

        # History manager
        item = Gtk.MenuItem.new_with_mnemonic(_('History Manager'))
        menu.append(item)
        item.connect('activate', self.on_history_manager_menuitem_activate)

    def add_bookmarks_list(self, gc_sub_menu, account):
        """
        Show join new group chat item and bookmarks list for an account
        """
        item = Gtk.MenuItem.new_with_mnemonic(_('_Join New Group Chat'))
        item.connect('activate', self.on_join_gc_activate, account)

        gc_sub_menu.append(item)

        # User has at least one bookmark.
        if app.connections[account].bookmarks:
            item = Gtk.SeparatorMenuItem.new()
            gc_sub_menu.append(item)

        for bookmark in app.connections[account].bookmarks:
            name = bookmark['name']
            if not name:
                # No name was given for this bookmark.
                # Use the first part of JID instead...
                name = bookmark['jid'].split("@")[0]

            # Shorten long names
            name = (name[:42] + '..') if len(name) > 42 else name

            # Do not use underline.
            item = Gtk.MenuItem.new_with_label(name)
            item.set_use_underline(False)
            item.connect('activate', self.on_bookmark_menuitem_activate,
                    account, bookmark)
            gc_sub_menu.append(item)

    def show_appropriate_context_menu(self, event, iters):
        # iters must be all of the same type
        model = self.modelfilter
        type_ = model[iters[0]][Column.TYPE]
        for titer in iters[1:]:
            if model[titer][Column.TYPE] != type_:
                return
        if type_ == 'group' and len(iters) == 1:
            self.make_group_menu(event, iters[0])
        if type_ == 'groupchat' and len(iters) == 1:
            self.make_groupchat_menu(event, iters[0])
        elif type_ == 'agent' and len(iters) == 1:
            self.make_transport_menu(event, iters[0])
        elif type_ in ('contact', 'self_contact') and len(iters) == 1:
            self.make_contact_menu(event, iters[0])
        elif type_ == 'contact':
            self.make_multiple_contact_menu(event, iters)
        elif type_ == 'account' and len(iters) == 1:
            self.make_account_menu(event, iters[0])

    def show_treeview_menu(self, event):
        try:
            model, list_of_paths = self.tree.get_selection().get_selected_rows()
        except TypeError:
            self.tree.get_selection().unselect_all()
            return
        if not len(list_of_paths):
            # no row is selected
            return
        if len(list_of_paths) > 1:
            iters = []
            for path in list_of_paths:
                iters.append(model.get_iter(path))
        else:
            path = list_of_paths[0]
            iters = [model.get_iter(path)]
        self.show_appropriate_context_menu(event, iters)

        return True

    def on_ctrl_j(self, accel_group, acceleratable, keyval, modifier):
        """
        Bring up the conference join dialog, when CTRL+J accelerator is being
        activated
        """
        # find a connected account:
        for account in app.connections:
            if app.account_is_connected(account):
                break
        self.on_join_gc_activate(None, account)
        return True

    def fill_column(self, col):
        for rend in self.renderers_list:
            col.pack_start(rend[1], rend[2])
            if rend[0] not in ('avatar', 'icon'):
                col.add_attribute(rend[1], rend[3], rend[4])
            col.set_cell_data_func(rend[1], rend[5], rend[6])
        # set renderers propertys
        for renderer in self.renderers_propertys.keys():
            renderer.set_property(self.renderers_propertys[renderer][0],
                self.renderers_propertys[renderer][1])

    def query_tooltip(self, widget, x_pos, y_pos, keyboard_mode, tooltip):
        try:
            row = widget.get_path_at_pos(x_pos, y_pos)[0]
        except TypeError:
            return False
        if not row:
            return False

        iter_ = None
        try:
            model = widget.get_model()
            iter_ = model.get_iter(row)
        except Exception:
            return False

        typ = model[iter_][Column.TYPE]
        account = model[iter_][Column.ACCOUNT]
        jid = model[iter_][Column.JID]
        connected_contacts = []

        if typ in ('contact', 'self_contact'):
            contacts = app.contacts.get_contacts(account, jid)
            
            for c in contacts:
                if c.show not in ('offline', 'error'):
                    connected_contacts.append(c)
            if not connected_contacts:
                # no connected contacts, show the offline one
                connected_contacts = contacts
        elif typ == 'groupchat':
            connected_contacts = app.contacts.get_contacts(account, jid)
        elif typ != 'account':
            return False

        if self.current_tooltip != row:
            # If the row changes we hide the current tooltip
            self.current_tooltip = row
            return False

        tooltip = widget.get_tooltip_window()

        if tooltip.row == row:
            # We already populated the window with the row data
            return True
        tooltip.row = row
        tooltip.populate(connected_contacts, account, typ)
        return True

    def add_actions(self):
        action = Gio.SimpleAction.new_stateful(
            "show-roster", None,
            GLib.Variant.new_boolean(
                not self.xml.get_object('roster_vbox2').get_no_show_all()))
        action.connect("change-state",
                       self.on_show_roster_action)
        self.window.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "show-offline", None,
            GLib.Variant.new_boolean(app.config.get('showoffline')))
        action.connect("change-state",
                       self.on_show_offline_contacts_action)
        self.window.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "show-active", None,
            GLib.Variant.new_boolean(
                app.config.get('show_only_chat_and_online')))
        action.connect("change-state",
                       self.on_show_active_contacts_action)
        self.window.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "show-transports", None,
            GLib.Variant.new_boolean(app.config.get('show_transports_group')))
        action.connect("change-state", self.on_show_transports_action)
        self.window.add_action(action)

################################################################################
###
################################################################################

    def __init__(self, application: Gtk.Application):
        self.application = application
        self.filtering = False
        self.starting = False
        self.starting_filtering = False
        # Number of renderers plugins added
        self.nb_ext_renderers = 0
        # When we quit, rememver if we already saved config once
        self.save_done = False

        # [icon, name, type, jid, account, editable, mood_pixbuf,
        # activity_pixbuf, tune_pixbuf, location_pixbuf, avatar_img,
        # padlock_pixbuf, visible]
        self.columns = [Gtk.Image, str, str, str, str,
            GdkPixbuf.Pixbuf, GdkPixbuf.Pixbuf, GdkPixbuf.Pixbuf, GdkPixbuf.Pixbuf,
            Gtk.Image, str, bool]

        self.xml = gtkgui_helpers.get_gtk_builder('roster_window.ui')
        self.window = self.xml.get_object('roster_window')
        application.add_window(self.window)
        self.add_actions()
        self.hpaned = self.xml.get_object('roster_hpaned')

        app.interface.msg_win_mgr = MessageWindowMgr(self.window, self.hpaned)
        app.interface.msg_win_mgr.connect('window-delete',
            self.on_message_window_delete)

        # Set headermenu but hide it.
        # MessageWindow will show it if we are in single-window mode
        headerbar = self.xml.get_object('headerbar')
        self.window.set_titlebar(headerbar)
        self.header_menu = self.xml.get_object('header_menu')
        self.header_menu.hide()

        self.advanced_menus = [] # We keep them to destroy them
        if app.config.get('roster_window_skip_taskbar'):
            self.window.set_property('skip-taskbar-hint', True)
        self.tree = self.xml.get_object('roster_treeview')
        sel = self.tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.MULTIPLE)
        # sel.connect('changed',
        #       self.on_treeview_selection_changed)

        self._iters = {}
        # for merged mode
        self._iters['MERGED'] = {'account': None, 'groups': {}}
        # holds a list of (jid, account) tuples
        self._last_selected_contact = []
        self.transports_state_images = {'16': {}, '32': {}, 'opened': {},
            'closed': {}}

        self.last_save_dir = None
        self.editing_path = None # path of row with cell in edit mode
        self.add_new_contact_handler_id = False
        self.service_disco_handler_id = False
        self.new_chat_menuitem_handler_id = False
        self.single_message_menuitem_handler_id = False
        self.profile_avatar_menuitem_handler_id = False
        #FIXME: When list_accel_closures will be wrapped in pygtk
        # no need of this variable
        self.have_new_chat_accel = False # Is the "Ctrl+N" shown ?
        self.regroup = app.config.get('mergeaccounts')
        self.clicked_path = None # Used remember on wich row we clicked
        if len(app.connections) < 2:
            # Do not merge accounts if only one exists
            self.regroup = False
        gtkgui_helpers.resize_window(self.window,
            app.config.get('roster_width'),
            app.config.get('roster_height'))
        if app.config.get('save-roster-position'):
            gtkgui_helpers.move_window(self.window,
                app.config.get('roster_x-position'),
                app.config.get('roster_y-position'))

        self.popups_notification_height = 0
        self.popup_notification_windows = []

        # Remove contact from roster when last event opened
        # { (contact, account): { backend: boolean }
        self.contacts_to_be_removed = {}
        app.events.event_removed_subscribe(self.on_event_removed)

        # when this value become 0 we quit main application. If it's more than 0
        # it means we are waiting for this number of accounts to disconnect
        # before quitting
        self.quit_on_next_offline = -1

        # groups to draw next time we draw groups.
        self.groups_to_draw = {}
        # accounts to draw next time we draw accounts.
        self.accounts_to_draw = []

        # StatusComboBox
        self.status_combobox = self.xml.get_object('status_combobox')
        pixbuf_renderer, text_renderer = self.status_combobox.get_cells()
        self.status_combobox.set_cell_data_func(
            pixbuf_renderer, self._status_cell_data_func)
        self.status_combobox.set_cell_data_func(
            text_renderer, self._status_cell_data_func)
        self.status_combobox.set_row_separator_func(self._iter_is_separator)

        self.status_combobox.set_active(9)
        # holds index to previously selected item so if
        # "change status message..." is selected we can fallback to previously
        # selected item and not stay with that item selected
        self.previous_status_combobox_active = 9

        # Enable/Disable checkboxes at start
        if app.config.get('showoffline'):
            self.window.lookup_action('show-active').set_enabled(False)

        if app.config.get('show_only_chat_and_online'):
            self.window.lookup_action('show-offline').set_enabled(False)

        if self.hpaned.get_child2() is None:
            self.window.lookup_action('show-roster').set_enabled(False)

        # columns
        col = Gtk.TreeViewColumn()
        # list of renderers with attributes / properties in the form:
        # (name, renderer_object, expand?, attribute_name, attribute_value,
        # cell_data_func, func_arg)
        self.renderers_list = []
        self.renderers_propertys ={}
        self._pep_type_to_model_column = {'mood': Column.MOOD_PIXBUF,
            'activity': Column.ACTIVITY_PIXBUF, 'tune': Column.TUNE_PIXBUF,
            'location': Column.LOCATION_PIXBUF}

        renderer_text = Gtk.CellRendererText()
        self.renderers_propertys[renderer_text] = ('ellipsize',
            Pango.EllipsizeMode.END)

        def add_avatar_renderer():
            self.renderers_list.append(('avatar', Gtk.CellRendererPixbuf(),
                False, None, Column.AVATAR_IMG,
                self._fill_avatar_pixbuf_renderer, None))

        if app.config.get('avatar_position_in_roster') == 'left':
            add_avatar_renderer()

        self.renderers_list += (
                ('icon', Gtk.CellRendererPixbuf(), False,
                None, Column.IMG, self._iconCellDataFunc, None),

                ('name', renderer_text, True,
                'markup', Column.NAME, self._nameCellDataFunc, None),

                ('mood', Gtk.CellRendererPixbuf(), False,
                'pixbuf', Column.MOOD_PIXBUF,
                self._fill_pep_pixbuf_renderer, Column.MOOD_PIXBUF),

                ('activity', Gtk.CellRendererPixbuf(), False,
                'pixbuf', Column.ACTIVITY_PIXBUF,
                self._fill_pep_pixbuf_renderer, Column.ACTIVITY_PIXBUF),

                ('tune', Gtk.CellRendererPixbuf(), False,
                'pixbuf', Column.TUNE_PIXBUF,
                self._fill_pep_pixbuf_renderer, Column.TUNE_PIXBUF),

                ('location', Gtk.CellRendererPixbuf(), False,
                'pixbuf', Column.LOCATION_PIXBUF,
                self._fill_pep_pixbuf_renderer, Column.LOCATION_PIXBUF))

        if app.config.get('avatar_position_in_roster') == 'right':
            add_avatar_renderer()

        self.renderers_list.append(('padlock', Gtk.CellRendererPixbuf(), False,
                'icon_name', Column.PADLOCK_PIXBUF,
                self._fill_padlock_pixbuf_renderer, None))

        # fill and append column
        self.fill_column(col)
        self.tree.append_column(col)

        # do not show gtk arrows workaround
        col = Gtk.TreeViewColumn()
        render_pixbuf = Gtk.CellRendererPixbuf()
        col.pack_start(render_pixbuf, False)
        self.tree.append_column(col)
        col.set_visible(False)
        self.tree.set_expander_column(col)

        # signals
        self.TARGET_TYPE_URI_LIST = 80
        self.tree.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK,
            [], Gdk.DragAction.DEFAULT | Gdk.DragAction.MOVE | \
            Gdk.DragAction.COPY)
        self.tree.drag_source_add_text_targets()
        self.tree.enable_model_drag_dest([], Gdk.DragAction.DEFAULT)
        dst_targets = Gtk.TargetList.new([])
        dst_targets.add_text_targets(0)
        dst_targets.add_uri_targets(self.TARGET_TYPE_URI_LIST)
        self.tree.drag_dest_set_target_list(dst_targets)
        self.tree.connect('drag_begin', self.drag_begin)
        self.tree.connect('drag_end', self.drag_end)
        self.tree.connect('drag_drop', self.drag_drop)
        self.tree.connect('drag_data_get', self.drag_data_get_data)
        self.tree.connect('drag_data_received', self.drag_data_received_data)
        self.dragging = False
        self.xml.connect_signals(self)
        self.combobox_callback_active = True

        self.collapsed_rows = app.config.get('collapsed_rows').split('\t')
        self.tree.set_has_tooltip(True)
        self.tree.set_tooltip_window(tooltips.RosterTooltip(self.window))
        self.current_tooltip = None
        self.tree.connect('query-tooltip', self.query_tooltip)
        # Workaroung: For strange reasons signal is behaving like row-changed
        self._toggeling_row = False

        if app.config.get('show_roster_on_startup') == 'always':
            self.window.show_all()
        elif app.config.get('show_roster_on_startup') == 'never':
            if app.config.get('trayicon') != 'always':
                # Without trayicon, user should see the roster!
                self.window.show_all()
                app.config.set('last_roster_visible', True)
        else:
            if app.config.get('last_roster_visible') or \
            app.config.get('trayicon') != 'always':
                self.window.show_all()

        self.scale_factor = self.window.get_scale_factor()
        self.setup_and_draw_roster()

        if not app.config.get_per('accounts') or \
        app.config.get_per('accounts') == ['Local'] and not \
        app.config.get_per('accounts', 'Local', 'active'):
        # if we have no account configured or only Local account but not enabled
            def _open_wizard():
                app.interface.instances['account_creation_wizard'] = \
                    config.AccountCreationWizardWindow()
            # Open wizard only after roster is created, so we can make it
            # transient for the roster window
            GLib.idle_add(_open_wizard)
        if not app.ZEROCONF_ACC_NAME in app.config.get_per('accounts'):
            # Create zeroconf in config file
            from gajim.common.zeroconf import connection_zeroconf
            connection_zeroconf.ConnectionZeroconf(app.ZEROCONF_ACC_NAME)

        # Setting CTRL+J to be the shortcut for bringing up the dialog to join a
        # conference.
        accel_group = Gtk.accel_groups_from_object(self.window)[0]
        accel_group.connect(Gdk.KEY_j, Gdk.ModifierType.CONTROL_MASK,
                Gtk.AccelFlags.MASK, self.on_ctrl_j)

        # Setting CTRL+S to be the shortcut to change status message
        accel_group = Gtk.AccelGroup()
        keyval, mod = Gtk.accelerator_parse('<Control>s')
        accel_group.connect(keyval, mod, Gtk.AccelFlags.VISIBLE,
            self.accel_group_func)

        # Setting CTRL+k to focus rfilter_entry
        keyval, mod = Gtk.accelerator_parse('<Control>k')
        accel_group.connect(keyval, mod, Gtk.AccelFlags.VISIBLE,
            self.accel_group_func)
        self.window.add_accel_group(accel_group)

        # Setting the search stuff
        self.rfilter_entry = self.xml.get_object('rfilter_entry')
        self.rfilter_string = ''
        self.rfilter_enabled = False
        self.rfilter_entry.connect('key-press-event',
            self.on_rfilter_entry_key_press_event)

        app.ged.register_event_handler('presence-received', ged.GUI1,
            self._nec_presence_received)
        # presence has to be fully handled so that contact is added to occupant
        # list before roster can be correctly updated
        app.ged.register_event_handler('gc-presence-received', ged.GUI2,
            self._nec_gc_presence_received)
        app.ged.register_event_handler('roster-received', ged.GUI1,
            self._nec_roster_received)
        app.ged.register_event_handler('anonymous-auth', ged.GUI1,
            self._nec_anonymous_auth)
        app.ged.register_event_handler('our-show', ged.GUI1,
            self._nec_our_show)
        app.ged.register_event_handler('connection-type', ged.GUI1,
            self._nec_connection_type)
        app.ged.register_event_handler('agent-removed', ged.GUI1,
            self._nec_agent_removed)
        app.ged.register_event_handler('pep-received', ged.GUI1,
            self._nec_pep_received)
        app.ged.register_event_handler('update-roster-avatar', ged.GUI1,
            self._nec_update_avatar)
        app.ged.register_event_handler('gc-subject-received', ged.GUI1,
            self._nec_gc_subject_received)
        app.ged.register_event_handler('metacontacts-received', ged.GUI2,
            self._nec_metacontacts_received)
        app.ged.register_event_handler('signed-in', ged.GUI1,
            self._nec_signed_in)
        app.ged.register_event_handler('decrypted-message-received', ged.GUI2,
            self._nec_decrypted_message_received)
        app.ged.register_event_handler('blocking', ged.GUI1,
            self._nec_blocking)
