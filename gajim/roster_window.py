# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    James Newton <redshodan AT gmail.com>
#                    Tomasz Melcer <liori AT exroot.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
#
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

import os
import sys
import time
import locale
import logging
from enum import IntEnum, unique

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
from nbxmpp.namespaces import Namespace

from gajim import dialogs
from gajim import vcard
from gajim import gtkgui_helpers
from gajim import gui_menu_builder

from gajim.common import app
from gajim.common import helpers
from gajim.common.exceptions import GajimGeneralException
from gajim.common import i18n
from gajim.common.helpers import save_roster_position
from gajim.common.helpers import ask_for_status_message
from gajim.common.i18n import _
from gajim.common.const import PEPEventType, AvatarSize, StyleAttr
from gajim.common.dbus import location

from gajim.common import ged
from gajim.message_window import MessageWindowMgr

from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.dialogs import NewConfirmationCheckDialog
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.dialogs import WarningDialog
from gajim.gtk.dialogs import InformationDialog
from gajim.gtk.dialogs import InvitationReceivedDialog
from gajim.gtk.single_message import SingleMessageWindow
from gajim.gtk.add_contact import AddNewContactWindow
from gajim.gtk.service_registration import ServiceRegistration
from gajim.gtk.discovery import ServiceDiscoveryWindow
from gajim.gtk.tooltips import RosterTooltip
from gajim.gtk.adhoc import AdHocCommand
from gajim.gtk.status_selector import StatusSelector
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import resize_window
from gajim.gtk.util import restore_roster_position
from gajim.gtk.util import get_metacontact_surface
from gajim.gtk.util import get_builder
from gajim.gtk.util import set_urgency_hint
from gajim.gtk.util import get_activity_icon_name
from gajim.gtk.util import get_account_activity_icon_name
from gajim.gtk.util import get_account_mood_icon_name
from gajim.gtk.util import get_account_tune_icon_name
from gajim.gtk.util import get_account_location_icon_name
from gajim.gtk.util import open_window


log = logging.getLogger('gajim.roster')

@unique
class Column(IntEnum):
    IMG = 0  # image to show state (online, new message etc)
    NAME = 1  # cellrenderer text that holds contact nickname
    TYPE = 2  # account, group or contact?
    JID = 3  # the jid of the row
    ACCOUNT = 4  # cellrenderer text that holds account name
    MOOD_PIXBUF = 5
    ACTIVITY_PIXBUF = 6
    TUNE_ICON = 7
    LOCATION_ICON = 8
    AVATAR_IMG = 9  # avatar_sha
    PADLOCK_PIXBUF = 10  # use for account row only
    VISIBLE = 11


class RosterWindow:
    """
    Class for main window of the GTK interface
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
            it = self.model.append(None, [get_icon_name(show),
                _('Merged accounts'), 'account', '', 'all', None, None, None,
                None, None, None, True] + [None] * self.nb_ext_renderers)
            self._iters['MERGED']['account'] = it
        else:
            show = helpers.get_connection_status(account)
            our_jid = app.get_jid_from_account(account)

            it = self.model.append(None, [get_icon_name(show),
                GLib.markup_escape_text(account), 'account', our_jid,
                account, None, None, None, None, None, None, True] +
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
        delimiter = app.connections[account].get_module('Delimiter').delimiter
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
        iter_group = self.model.append(iter_parent,
            [get_icon_name('closed'),
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

            # Do not confuse get_contact_iter: Sync groups of family members
            contact.groups = big_brother_contact.groups[:]

            image = self._get_avatar_image(account, contact.jid)

            for child_iter in parent_iters:
                it = self.model.append(child_iter, [None,
                    contact.get_shown_name(), 'contact', contact.jid, account,
                    None, None, None, None, image, None, visible] + \
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
                elif contact.is_groupchat:
                    typestr = 'groupchat'
                else:
                    typestr = 'contact'

                image = self._get_avatar_image(account, contact.jid)

                # we add some values here. see draw_contact
                # for more
                i_ = self.model.append(child_iterG, [None,
                    contact.get_shown_name(), typestr, contact.jid, account,
                    None, None, None, None, image, None, visible] + \
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

            self._add_entity(_contact, _account,
                    big_brother_contact=big_brother_contact,
                    big_brother_account=big_brother_account)
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
        # Remove children first then big brother
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

            family_in_roster = True

            parent_iter = self.model.iter_parent(iters[0])
            parent_type = self.model[parent_iter][Column.TYPE]

            if parent_type != 'contact':
                # The contact on top
                old_big_account = _account
                old_big_contact = _contact
                continue

            self._remove_entity(_contact, _account)

        if not family_in_roster:
            return False

        self._remove_entity(old_big_contact, old_big_account)

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
        if self._get_contact_iter(jid, account, contact, self.model):
            # If contact already in roster, do nothing
            return

        if jid == app.get_jid_from_account(account):
            return self._add_self_contact(account)

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

    def remove_contact(self, jid, account, force=False, backend=False, maximize=False):
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
                if not maximize:
                    # Don't remove contact when we maximize a room
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
                    c.groups = [_('Not in contact list')]
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

    def minimize_groupchat(self, account, jid, status=''):
        gc_control = app.interface.msg_win_mgr.get_gc_control(jid, account)
        app.interface.minimized_controls[account][jid] = gc_control
        self.add_groupchat(jid, account)

    def add_groupchat(self, jid, account):
        """
        Add groupchat to roster and draw it. Return the added contact instance
        """
        contact = app.contacts.get_groupchat_contact(account, jid)
        show = 'offline'
        if app.account_is_available(account):
            show = 'online'

        contact.show = show
        self.add_contact(jid, account)

        return contact

    def remove_groupchat(self, jid, account, maximize=False):
        """
        Remove groupchat from roster and redraw account and group
        """
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        if contact.is_groupchat:
            if jid in app.interface.minimized_controls[account]:
                del app.interface.minimized_controls[account][jid]
            self.remove_contact(jid, account, force=True, backend=True, maximize=maximize)
            return True
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

            app.connections[acc].get_module('Roster').update_contacts(
                changed_contacts)

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
                con = app.connections[account]
                con.get_module('Roster').update_contact(
                    jid, contact.name, contact.groups)

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
                con = app.connections[account]
                con.get_module('Roster').update_contact(
                    jid, contact.name, contact.groups)
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
                # Perform delayed recalibration
                self._recalibrate_metacontact_family(family, account)
            self.draw_contact(jid, account)
            # Hide Group if all children are hidden
            contact = app.contacts.get_contact(account, jid)
            if not contact:
                return
            for group in contact.get_shown_groups():
                self.draw_group(group, account)

    # FIXME: integrate into add_contact()
    def add_to_not_in_the_roster(self, account, jid, nick='', resource='',
                                 groupchat=False):
        contact = app.contacts.create_not_in_roster_contact(
            jid=jid, account=account, resource=resource, name=nick,
            groupchat=groupchat)
        app.contacts.add_contact(account, contact)
        self.add_contact(contact.jid, account)
        return contact


################################################################################
### Methods for adding and removing roster window items
################################################################################

    def _really_draw_account(self, account):
        child_iter = self._get_account_iter(account, self.model)
        if not child_iter:
            return

        if self.regroup:
            account_name = _('Merged accounts')
            accounts = []
        else:
            account_name = app.get_account_label(account)
            accounts = [account]

        if account in self.collapsed_rows and \
        self.model.iter_has_child(child_iter):
            account_name = '[%s]' % account_name

        if (app.account_is_available(account) or (self.regroup and \
        app.get_number_of_connected_accounts())) and app.settings.get(
        'show_contacts_number'):
            nbr_on, nbr_total = app.contacts.get_nb_online_total_contacts(
                    accounts=accounts)
            account_name += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))

        self.model[child_iter][Column.NAME] = GLib.markup_escape_text(account_name)

        mood_icon_name = get_account_mood_icon_name(account)
        self.model[child_iter][Column.MOOD_PIXBUF] = mood_icon_name

        activity_icon_name = get_account_activity_icon_name(account)
        self.model[child_iter][Column.ACTIVITY_PIXBUF] = activity_icon_name

        tune_icon_name = get_account_tune_icon_name(account)
        self.model[child_iter][Column.TUNE_ICON] = tune_icon_name

        location_icon_name = get_account_location_icon_name(account)
        self.model[child_iter][Column.LOCATION_ICON] = location_icon_name

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
            # Eg. We redraw groups after we removed a entity
            # and its empty groups
            return
        if self.regroup:
            accounts = []
        else:
            accounts = [account]
        text = GLib.markup_escape_text(group)
        if app.settings.get('show_contacts_number'):
            nbr_on, nbr_total = app.contacts.get_nb_online_total_contacts(
                    accounts=accounts, groups=[group])
            text += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))

        self.model[child_iter][Column.NAME] = text

        # Hide group if no more contacts
        iterG = self._get_group_iter(group, account, model=self.modelfilter)
        to_hide = []
        while iterG:
            parent = self.modelfilter.iter_parent(iterG)
            if (not self.modelfilter.iter_has_child(iterG)) or (to_hide \
            and self.modelfilter.iter_n_children(iterG) == 1):
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
        strike = helpers.jid_is_blocked(account, jid)
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
        if app.settings.get('show_status_msgs_in_roster'):
            status_span = '\n<span size="small" style="italic" ' \
                          'alpha="70%">{}</span>'
            if contact.is_groupchat:
                disco_info = app.logger.get_last_disco_info(contact.jid)
                if disco_info is not None:
                    description = disco_info.muc_description
                    if description:
                        name += status_span.format(
                            GLib.markup_escape_text(description))
            elif contact.status:
                status = contact.status.strip()
                if status != '':
                    status = helpers.reduce_chars_newlines(
                        status, max_lines=1)
                    name += status_span.format(
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
                        if app.events.get_events(accountC, jidC):
                            icon_name = 'event'
                            break
                        iterC = self.model.iter_next(iterC)

                if self.tree.row_expanded(path):
                    icon_name += ':opened'
                else:
                    icon_name += ':closed'

                theme_icon = get_icon_name(icon_name)
                self.model[child_iter][Column.IMG] = theme_icon
                self.model[child_iter][Column.NAME] = name
                #TODO: compute visible
                visible = True
                self.model[child_iter][Column.VISIBLE] = visible
        else:
            # A normal contact or little brother
            transport = app.get_transport_name_from_jid(jid)
            if transport == 'jabber':
                transport = None
            theme_icon = get_icon_name(icon_name, transport=transport)

            visible = self.contact_is_visible(contact, account)
            # All iters have the same icon (no expand/collapse)
            for child_iter in child_iters:
                self.model[child_iter][Column.IMG] = theme_icon
                self.model[child_iter][Column.NAME] = name
                self.model[child_iter][Column.VISIBLE] = visible
                if visible:
                    parent_iter = self.model.iter_parent(child_iter)
                    self.model[parent_iter][Column.VISIBLE] = True

            # We are a little brother
            if family and not is_big_brother and not self.starting:
                self.draw_parent_contact(jid, account)

        if visible:
            delimiter = app.connections[account].get_module('Delimiter').delimiter
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
        if pep_type == PEPEventType.MOOD:
            return app.settings.get('show_mood_in_roster')

        if pep_type == PEPEventType.ACTIVITY:
            return app.settings.get('show_activity_in_roster')

        if pep_type == PEPEventType.TUNE:
            return  app.settings.get('show_tunes_in_roster')

        if pep_type == PEPEventType.LOCATION:
            return  app.settings.get('show_location_in_roster')

        return False

    def draw_all_pep_types(self, jid, account, contact=None):
        self._draw_pep(account, jid, PEPEventType.MOOD)
        self._draw_pep(account, jid, PEPEventType.ACTIVITY)
        self._draw_pep(account, jid, PEPEventType.TUNE)
        self._draw_pep(account, jid, PEPEventType.LOCATION)

    def _draw_pep(self, account, jid, type_):
        if not self._is_pep_shown_in_roster(type_):
            return

        iters = self._get_contact_iter(jid, account, model=self.model)
        if not iters:
            return
        contact = app.contacts.get_contact(account, jid)

        icon = None
        data = contact.pep.get(type_)

        if type_ == PEPEventType.MOOD:
            column = Column.MOOD_PIXBUF
            if data is not None:
                icon = 'mood-%s' % data.mood
        elif type_ == PEPEventType.ACTIVITY:
            column = Column.ACTIVITY_PIXBUF
            if data is not None:
                icon = get_activity_icon_name(data.activity, data.subactivity)
        elif type_ == PEPEventType.TUNE:
            column = Column.TUNE_ICON
            if data is not None:
                icon = 'audio-x-generic'
        elif type_ == PEPEventType.LOCATION:
            column = Column.LOCATION_ICON
            if data is not None:
                icon = 'applications-internet'

        for child_iter in iters:
            self.model[child_iter][column] = icon

    def _get_avatar_image(self, account, jid):
        if not app.settings.get('show_avatars_in_roster'):
            return None
        scale = self.window.get_scale_factor()
        surface = app.contacts.get_avatar(
            account, jid, AvatarSize.ROSTER, scale)
        return Gtk.Image.new_from_surface(surface)

    def draw_avatar(self, jid, account):
        iters = self._get_contact_iter(jid, account, model=self.model)
        if not iters or not app.settings.get('show_avatars_in_roster'):
            return
        jid = self.model[iters[0]][Column.JID]
        image = self._get_avatar_image(account, jid)

        for child_iter in iters:
            self.model[child_iter][Column.AVATAR_IMG] = image
        return False

    def draw_completely(self, jid, account):
        contact_instances = app.contacts.get_contacts(account, jid)
        contact = app.contacts.get_highest_prio_contact_from_contacts(
            contact_instances)
        self.draw_contact(
            jid, account,
            contact_instances=contact_instances,
            contact=contact)

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
                    # must be redrawn (got removed and added again)
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

    def update_status_selector(self):
        self._status_selector.update()

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
        if self.dragging or not app.settings.get(
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
        delimiter = app.connections[account].get_module('Delimiter').delimiter
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
        if app.settings.get('showoffline'):
            return True

        if contact.show in ('offline', 'error'):
            if contact.jid in app.to_be_removed[account]:
                return True
            return False
        if app.settings.get('show_only_chat_and_online') and contact.show in (
        'away', 'xa', 'busy'):
            return False
        if _('Transports') in contact.get_shown_groups():
            return app.settings.get('show_transports_group')
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
            if name1 == _('Not in contact list'):
                return 1
            if name2 == _('Not in contact list'):
                return -1
            if name1 == _('Group chats'):
                return 1
            if name2 == _('Group chats'):
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
        app.settings.get('sort_by_show_in_roster'):
            cshow = {'chat':0, 'online': 1, 'away': 2, 'xa': 3, 'dnd': 4,
                     'offline': 6, 'not in roster': 7, 'error': 8}
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
            if show1 > show2:
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
###             ... at least not in there current form
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
        # FIXME: This function needs to be split
        # Most of the logic SHOULD NOT be done at GUI level
        if account not in app.contacts.get_accounts():
            app.contacts.add_account(account)
        if not account in self._iters:
            self._iters[account] = {'account': None, 'groups': {},
                'contacts': {}}
        if account not in app.groups:
            app.groups[account] = {}

        self_jid = str(app.connections[account].get_own_jid())
        if account != app.ZEROCONF_ACC_NAME:
            array[self_jid] = {'name': app.nicks[account],
                               'groups': ['self_contact'],
                               'subscription': 'both',
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

            if app.jid_is_transport(jid):
                array[jid]['groups'] = [_('Transports')]
            #TRANSP - potential
            contact1 = app.contacts.create_contact(jid=ji, account=account,
                name=name, groups=array[jid]['groups'], show=show,
                status=status, sub=array[jid]['subscription'],
                ask=array[jid]['ask'], resource=resource)
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
            SingleMessageWindow(account, jid,
                action='receive', from_whom=jid, subject=event.subject,
                message=event.message, resource=event.resource)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ == 'file-request':
            contact = app.contacts.get_contact_with_highest_priority(account,
                    jid)
            ft.show_file_request(account, contact, event.file_props)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ in ('file-request-error', 'file-send-error'):
            ft.show_send_error(event.file_props)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ in ('file-error', 'file-stopped'):
            msg_err = ''
            if event.file_props.error == -1:
                msg_err = _('Remote contact stopped transfer')
            elif event.file_props.error == -6:
                msg_err = _('Error opening file')
            ft.show_stopped(jid, event.file_props, error_msg=msg_err)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ == 'file-hash-error':
            ft.show_hash_error(jid, event.file_props, account)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ == 'file-completed':
            ft.show_completed(jid, event.file_props)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ == 'gc-invitation':
            InvitationReceivedDialog(account, event)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ == 'subscription_request':
            open_window('SubscriptionRequest',
                        account=account,
                        jid=jid,
                        text=event.text,
                        user_nick=event.nick)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ == 'unsubscribed':
            app.interface.show_unsubscribed_dialog(account, event.contact)
            app.events.remove_events(account, jid, event)
            return True

        if event.type_ == 'jingle-incoming':
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
        app.connections[account].get_module('Presence').subscribed(jid)
        InformationDialog(_('Authorization sent'),
            _('"%s" will now see your status.') %jid)

    def req_sub(self, widget, jid, txt, account, groups=None, nickname=None,
                    auto_auth=False):
        """
        Request subscription to a contact
        """
        groups_list = groups or []
        app.connections[account].get_module('Presence').subscribe(
            jid, txt, nickname, groups_list, auto_auth)
        contact = app.contacts.get_contact_with_highest_priority(account, jid)
        if not contact:
            contact = app.contacts.create_contact(jid=jid, account=account,
                name=nickname, groups=groups_list, show='requested', status='',
                ask='none', sub='subscribe')
            app.contacts.add_contact(account, contact)
        else:
            if not _('Not in contact list') in contact.get_shown_groups():
                InformationDialog(_('Subscription request has been '
                    'sent'), _('If "%s" accepts this request you will know '
                    'their status.') % jid)
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
        app.connections[account].get_module('Presence').unsubscribed(jid)
        InformationDialog(_('Authorization removed'),
            _('Now "%s" will always see you as offline.') %jid)

    def set_state(self, account, state):
        child_iterA = self._get_account_iter(account, self.model)
        if child_iterA:
            self.model[child_iterA][0] = get_icon_name(state)
        if app.interface.systray_enabled:
            app.interface.systray.change_status(state)

    def set_connecting_state(self, account):
        self.set_state(account, 'connecting')

    def send_status(self, account, status, txt):
        if status != 'offline':
            app.config.set_per('accounts', account, 'last_status', status)
            app.config.set_per('accounts', account, 'last_status_msg',
                    helpers.to_one_line(txt))
            if not app.account_is_available(account):
                self.set_connecting_state(account)

        if status == 'offline':
            self.delete_pep(app.get_jid_from_account(account), account)

        app.connections[account].change_status(status, txt)
        self._status_selector.update()

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

    def chg_contact_status(self, contact, show, status_message, account):
        """
        When a contact changes their status
        """
        contact_instances = app.contacts.get_contacts(account, contact.jid)
        contact.show = show
        contact.status = status_message
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
            self.remove_contact(contact.jid, account, backend=True)

        uf_show = helpers.get_uf_show(show)

        # print status in chat window and update status/GPG image
        ctrl = app.interface.msg_win_mgr.get_control(contact.jid, account)
        if ctrl and not ctrl.is_groupchat:
            ctrl.contact = app.contacts.get_contact_with_highest_priority(
                account, contact.jid)
            ctrl.update_status_display(name, uf_show, status_message)

        if contact.resource:
            ctrl = app.interface.msg_win_mgr.get_control(fjid, account)
            if ctrl:
                ctrl.update_status_display(name, uf_show, status_message)

        # Delete pep if needed
        keep_pep = any(c.show not in ('error', 'offline') for c in
            contact_instances)
        if not keep_pep and contact.jid != app.get_jid_from_account(account) \
        and not contact.is_groupchat:
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
        self_resource = app.connections[account].get_own_jid().getResource()
        self_contact = app.contacts.get_contact(account,
                app.get_jid_from_account(account), resource=self_resource)
        if self_contact:
            status_message = app.connections[account].status_message
            self.chg_contact_status(self_contact, show, status_message, account)
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
                for jid in list(app.contacts.get_jid_list(account)):
                    lcontact = app.contacts.get_contacts(account, jid)
                    ctrl = app.interface.msg_win_mgr.get_gc_control(jid,
                        account)
                    for contact in [c for c in lcontact if (
                    (c.show != 'offline' or c.is_transport()) and not ctrl)]:
                        self.chg_contact_status(contact, 'offline', '', account)
        if app.interface.systray_enabled:
            app.interface.systray.change_status(show)
        self._status_selector.update()

    def change_status(self, _widget, account, status):
        app.interface.change_account_status(account, status=status)

    def get_show(self, lcontact):
        prio = lcontact[0].priority
        show = lcontact[0].show
        for u in lcontact:
            if u.priority > prio:
                prio = u.priority
                show = u.show
        return show

    def on_message_window_delete(self, win_mgr, msg_win):
        if app.settings.get('one_message_window') == 'always_with_roster':
            self.show_roster_vbox(True)
            resize_window(self.window,
                          app.settings.get('roster_width'),
                          app.settings.get('roster_height'))

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
        if not app.settings.get('quit_on_roster_x_button') and (
        (app.interface.systray_enabled and app.settings.get('trayicon') != \
        'on_event') or app.settings.get('allow_hide_roster')):
            save_roster_position(self.window)
            if os.name == 'nt' or app.settings.get('hide_on_roster_x_button'):
                self.window.hide()
            else:
                self.window.iconify()
        elif app.settings.get('quit_on_roster_x_button'):
            self.on_quit_request()
        else:
            def _on_ok(is_checked):
                if is_checked:
                    app.config.set('quit_on_roster_x_button', True)
                self.on_quit_request()
            NewConfirmationCheckDialog(
                _('Quit Gajim'),
                _('You are about to quit Gajim'),
                _('Are you sure you want to quit Gajim?'),
                _('_Always quit when closing Gajim'),
                [DialogButton.make('Cancel'),
                 DialogButton.make('Remove',
                                   text=_('_Quit'),
                                   callback=_on_ok)]).show()
        return True #  Do NOT destroy the window

    def prepare_quit(self):
        if self.save_done:
            return
        msgwin_width_adjust = 0

        # in case show_roster_on_start is False and roster is never shown
        # window.window is None
        if self.window.get_window() is not None:
            save_roster_position(self.window)
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
            if app.account_is_available(acct):
                get_msg = True
                break

        def on_continue3(message):
            self.quit_on_next_offline = 0
            accounts_to_disconnect = []
            for acct in accounts:
                if app.account_is_available(acct):
                    self.quit_on_next_offline += 1
                    accounts_to_disconnect.append(acct)

            if not self.quit_on_next_offline:
                # all accounts offline, quit
                self.quit_gtkgui_interface()
                return

            for acct in accounts_to_disconnect:
                self.send_status(acct, 'offline', message)

        def on_continue2(message):
            if 'file_transfers' not in app.interface.instances:
                on_continue3(message)
                return
            # check if there is an active file transfer
            from gajim.common.modules.bytestream import is_transfer_active
            files_props = app.interface.instances['file_transfers'].\
                files_props
            transfer_active = False
            for x in files_props:
                for y in files_props[x]:
                    if is_transfer_active(files_props[x][y]):
                        transfer_active = True
                        break

            if transfer_active:
                NewConfirmationDialog(
                    _('Stop File Transfers'),
                    _('You still have running file transfers'),
                    _('If you quit now, the file(s) being transferred will '
                      'be lost.\n'
                      'Do you still want to quit?'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       text=_('_Quit'),
                                       callback=on_continue3,
                                       args=[message])]).show()
                return
            on_continue3(message)

        def on_continue(message):
            if message is None:
                # user pressed Cancel to change status message dialog
                return
            # check if we have unread messages
            unread = app.events.get_nb_events()

            for event in app.events.get_all_events(['printed_gc_msg']):
                contact = app.contacts.get_groupchat_contact(event.account,
                                                             event.jid)
                if contact is None or not contact.can_notify():
                    unread -= 1

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
                NewConfirmationDialog(
                    _('Unread Messages'),
                    _('You still have unread messages'),
                    _('Messages will only be available for reading them later '
                      'if storing chat history is enabled and if the contact '
                      'is in your contact list.'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       text=_('_Quit'),
                                       callback=on_continue2,
                                       args=[message])]).show()
                return
            on_continue2(message)

        if get_msg and ask_for_status_message('offline'):
            open_window('StatusChange',
                        status='offline',
                        callback=on_continue,
                        show_pep=False)
        else:
            on_continue('')

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
                obj.conn.state.is_available:
                    GLib.timeout_add_seconds(5, self.remove_to_be_removed,
                        jid, account)

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
                if app.events.get_events(account, obj.jid):
                    ctrl.read_queue()

    def _nec_roster_received(self, obj):
        if obj.received_from_server:
            self.fill_contacts_and_groups_dicts(obj.roster, obj.conn.name)
            self.add_account_contacts(obj.conn.name)
            self.fire_up_unread_messages_events(obj.conn.name)
        else:
            # add self contact
            account = obj.conn.name
            self_jid = app.get_jid_from_account(account)
            if self_jid not in app.contacts.get_jid_list(account):
                sha = app.config.get_per('accounts', account, 'avatar_sha')
                contact = app.contacts.create_contact(
                    jid=self_jid, account=account, name=app.nicks[account],
                    groups=['self_contact'], show='offline', sub='both',
                    ask='none', avatar_sha=sha)
                app.contacts.add_contact(account, contact)
                self.add_contact(self_jid, account)

            if app.settings.get('remember_opened_chat_controls'):
                account = obj.conn.name
                controls = app.config.get_per(
                    'accounts', account, 'opened_chat_controls')
                if controls:
                    for jid in controls.split(','):
                        contact = \
                            app.contacts.get_contact_with_highest_priority(
                                account, jid)
                        if not contact:
                            contact = self.add_to_not_in_the_roster(
                                account, jid)
                        app.interface.on_open_chat_window(
                            None, contact, account)
                app.config.set_per(
                    'accounts', account, 'opened_chat_controls', '')
            GLib.idle_add(self.refilter_shown_roster_items)

    def _nec_anonymous_auth(self, obj):
        """
        This event is raised when our JID changed (most probably because we use
        anonymous account. We update contact and roster entry in this case
        """
        self.rename_self_contact(obj.old_jid, obj.new_jid, obj.conn.name)

    def _nec_our_show(self, event):
        if event.show == 'offline':
            self.application.set_account_actions_state(event.account)
            self.application.update_app_actions_state()

        self.on_status_changed(event.account, event.show)

    def _nec_connection_type(self, obj):
        self.draw_account(obj.conn.name)

    def _nec_agent_removed(self, obj):
        for jid in obj.jid_list:
            self.remove_contact(jid, obj.conn.name, backend=True)

    def _on_mood_received(self, event):
        if event.is_self_message:
            self.draw_account(event.account)
        self._draw_pep(event.account, event.jid, PEPEventType.MOOD)

    def _on_activity_received(self, event):
        if event.is_self_message:
            self.draw_account(event.account)
        self._draw_pep(event.account, event.jid, PEPEventType.ACTIVITY)

    def _on_tune_received(self, event):
        if event.is_self_message:
            self.draw_account(event.account)
        self._draw_pep(event.account, event.jid, PEPEventType.TUNE)

    def _on_location_received(self, event):
        if event.is_self_message:
            self.draw_account(event.account)
        self._draw_pep(event.account, event.jid, PEPEventType.LOCATION)

    def _on_nickname_received(self, event):
        self.draw_contact(event.jid, event.account)

    def _nec_update_avatar(self, obj):
        app.log('avatar').debug('Draw roster avatar: %s', obj.jid)
        self.draw_avatar(obj.jid, obj.account)

    def _nec_muc_subject_received(self, event):
        self.draw_contact(event.room_jid, event.account)

    def _on_muc_disco_update(self, event):
        self.draw_contact(str(event.room_jid), event.account)

    def _on_bookmarks_received(self, event):
        con = app.connections[event.account]
        for bookmark in con.get_module('Bookmarks').bookmarks:
            self.draw_contact(str(bookmark.jid), event.account)

    def _nec_metacontacts_received(self, obj):
        self.redraw_metacontacts(obj.conn.name)

    def _nec_signed_in(self, obj):
        self.application.set_account_actions_state(obj.conn.name, True)
        self.application.update_app_actions_state()
        self.draw_account(obj.conn.name)

    def _nec_decrypted_message_received(self, obj):
        if not obj.msgtxt:
            return True
        if obj.properties.type.value not in ('normal', 'chat'):
            return

        if obj.popup and not obj.session.control:
            contact = app.contacts.get_contact(obj.conn.name, obj.jid)
            obj.session.control = app.interface.new_chat(contact,
                obj.conn.name, session=obj.session)
            if app.events.get_events(obj.conn.name, obj.fjid):
                obj.session.control.read_queue()

        if not obj.properties.is_muc_pm and obj.show_in_roster:
            self.draw_contact(obj.jid, obj.conn.name)
            self.show_title() # we show the * or [n]
            # Select the big brother contact in roster, it's visible because it
            # has events.
            family = app.contacts.get_metacontacts_family(obj.conn.name,
                obj.jid)
            if family:
                _nearby_family, bb_jid, bb_account = \
                    app.contacts.get_nearby_family_and_big_brother(family,
                    obj.conn.name)
            else:
                bb_jid, bb_account = obj.jid, obj.conn.name
            self.select_contact(bb_jid, bb_account)

################################################################################
### Menu and GUI callbacks
### FIXME: order callbacks in itself...
################################################################################

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

    def on_edit_agent(self, widget, contact, account):
        """
        When we want to modify the agent registration
        """
        ServiceRegistration(account, contact.jid)

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
                app.connections[account].get_module('Presence').unsubscribe(contact.jid)
                self.remove_contact(contact.jid, account, backend=True)
                return

        def remove():
            for (contact, account) in list_:
                full_jid = contact.get_full_jid()
                app.connections[account].get_module('Gateway').unsubscribe(full_jid)
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
            ErrorDialog(
                _('You have unread messages'),
                _('You must read them before removing this transport.'))
            return
        if len(list_) == 1:
            pritext = _('Transport \'%s\' will be removed') % list_[0][0].jid
            sectext = _('You will no longer be able to send and receive '
                        'messages from and to contacts using this transport.')
        else:
            pritext = _('Transports will be removed')
            jids = ''
            for (contact, account) in list_:
                jids += '\n  ' + contact.get_shown_name() + ','
            jids = jids[:-1] + '.'
            sectext = _('You will no longer be able to send and receive '
                        'messages from and to contacts using these '
                        'transports:\n%s') % jids
        NewConfirmationDialog(
            _('Remove Transport'),
            pritext,
            sectext,
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               callback=remove)],
            transient_for=self.window).show()

    def _nec_blocking(self, obj):
        for jid in obj.changed:
            self.draw_contact(jid, obj.conn.name)

    def on_block(self, widget, list_):
        """
        When clicked on the 'block' button in context menu. list_ is a list of
        (contact, account)
        """
        def _block_it(is_checked=None, report=None):
            if is_checked is not None:  # Dialog has been shown
                if is_checked:
                    app.config.set('confirm_block', 'no')
                else:
                    app.config.set('confirm_block', 'yes')

            accounts = []
            for _, account in list_:
                con = app.connections[account]
                if con.get_module('Blocking').supported:
                    accounts.append(account)

            for acct in accounts:
                l_ = [i[0] for i in list_ if i[1] == acct]
                con = app.connections[acct]
                jid_list = [contact.jid for contact in l_]
                con.get_module('Blocking').block(jid_list, report)
                for contact in l_:
                    ctrl = app.interface.msg_win_mgr.get_control(
                        contact.jid, acct)
                    if ctrl:
                        ctrl.parent_win.remove_tab(
                            ctrl, ctrl.parent_win.CLOSE_COMMAND, force=True)
                    if contact.show == 'not in roster':
                        self.remove_contact(contact.jid, acct, force=True,
                                            backend=True)
                        return
                    self.draw_contact(contact.jid, acct)

        # Check if confirmation is needed for blocking
        confirm_block = app.settings.get('confirm_block')
        if confirm_block == 'no':
            _block_it()
            return

        NewConfirmationCheckDialog(
            _('Block Contact'),
            _('Really block this contact?'),
            _('You will appear offline for this contact and you '
              'will not receive further messages.'),
            _('_Do not ask again'),
            [DialogButton.make('Cancel'),
             DialogButton.make('OK',
                               text=_('_Report Spam'),
                               callback=_block_it,
                               kwargs={'report': 'spam'}),
             DialogButton.make('Remove',
                               text=_('_Block'),
                               callback=_block_it)],
            modal=False).show()

    def on_unblock(self, widget, list_):
        """
        When clicked on the 'unblock' button in context menu.
        """
        accounts = []
        for _, account in list_:
            con = app.connections[account]
            if con.get_module('Blocking').supported:
                accounts.append(account)

        for acct in accounts:
            l_ = [i[0] for i in list_ if i[1] == acct]
            con = app.connections[acct]
            jid_list = [contact.jid for contact in l_]
            con.get_module('Blocking').unblock(jid_list)
            for contact in l_:
                self.draw_contact(contact.jid, acct)

    def on_rename(self, widget, row_type, jid, account):
        # This function is called either by F2 or by Rename menuitem
        if 'rename' in app.interface.instances:
            app.interface.instances['rename'].dialog.present()
            return

        # Account is offline, don't allow to rename
        if not app.account_is_available(account):
            return
        if row_type in ('contact', 'agent'):
            # It's jid
            title = _('Rename Contact')
            text = _('Rename contact %s?') % jid
            sec_text = _('Please enter a new nickname')
            old_text = app.contacts.get_contact_with_highest_priority(account,
                                                                      jid).name
        elif row_type == 'group':
            if jid in helpers.special_groups + (_('General'),):
                return
            old_text = jid
            title = _('Rename Group')
            text = _('Rename group %s?') % GLib.markup_escape_text(jid)
            sec_text = _('Please enter a new name')

        def _on_renamed(new_text, account, row_type, jid, old_text):
            if row_type in ('contact', 'agent'):
                if old_text == new_text:
                    return
                contacts = app.contacts.get_contacts(account, jid)
                for contact in contacts:
                    contact.name = new_text
                con = app.connections[account]
                con.get_module('Roster').update_contact(
                    jid, new_text, contacts[0].groups)
                self.draw_contact(jid, account)
                # Update opened chats
                for ctrl in app.interface.msg_win_mgr.get_controls(jid,
                account):
                    ctrl.update_ui()
                    win = app.interface.msg_win_mgr.get_window(jid, account)
                    win.redraw_tab(ctrl)
                    win.show_title()
            elif row_type == 'group':
                # In Column.JID column, we hold the group name (which is not escaped)
                self.rename_group(old_text, new_text, account)

        InputDialog(
            title,
            text,
            sec_text,
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Rename'),
                               callback=_on_renamed,
                               args=[account,
                                     row_type,
                                     jid,
                                     old_text])],
            input_str=old_text,
            transient_for=self.window).show()

    def on_remove_group_item_activated(self, widget, group, account):
        def _on_ok(is_checked):
            for contact in app.contacts.get_contacts_from_group(account,
            group):
                if not is_checked:
                    self.remove_contact_from_groups(contact.jid, account,
                        [group])
                else:
                    app.connections[account].get_module(
                        'Presence').unsubscribe(contact.jid)
                    self.remove_contact(contact.jid, account, backend=True)

        NewConfirmationCheckDialog(
            _('Remove Group'),
            _('Remove Group'),
            _('Do you want to remove %s from the contact list?') % group,
            _('_Also remove all contacts of this group from contact list'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               callback=_on_ok)]).show()

    def on_edit_groups(self, widget, list_):
        dialogs.EditGroupsDialog(list_)

    def on_disconnect(self, widget, jid, account):
        """
        When disconnect menuitem is activated: disconnect from room
        """
        if jid in app.interface.minimized_controls[account]:
            ctrl = app.interface.minimized_controls[account][jid]
            ctrl.leave()
        self.remove_groupchat(jid, account)

    def on_send_single_message_menuitem_activate(self, widget, account,
    contact=None):
        if contact is None:
            SingleMessageWindow(account, action='send')
        elif isinstance(contact, list):
            SingleMessageWindow(account, contact, 'send')
        else:
            jid = contact.jid
            if contact.jid == app.get_jid_from_account(account):
                jid += '/' + contact.resource
            SingleMessageWindow(account, jid, 'send')

    def on_send_file_menuitem_activate(self, widget, contact, account,
    resource=None):
        app.interface.instances['file_transfers'].show_file_send_request(
            account, contact)

    def on_invite_to_room(self,
                          _widget,
                          list_,
                          room_jid,
                          room_account,
                          resource=None):
        """
        Resource parameter MUST NOT be used if more than one contact in list
        """
        gc_control = app.get_groupchat_control(room_account, room_jid)
        if gc_control is None:
            return

        for contact, _ in list_:
            contact_jid = contact.jid
            if resource: # we MUST have one contact only in list_
                contact_jid += '/' + resource
            gc_control.invite(contact_jid)

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
            mw = app.interface.msg_win_mgr.create_window(
                ctrl.contact, ctrl.account, ctrl.type)
            id_ = mw.window.connect('motion-notify-event',
                ctrl._on_window_motion_notify)
            ctrl.handlers[id_] = mw.window
        ctrl.parent_win = mw
        ctrl.on_groupchat_maximize()
        mw.new_tab(ctrl)
        mw.set_active_tab(ctrl)
        self.remove_groupchat(jid, account, maximize=True)

    def on_groupchat_rename(self, _widget, jid, account):
        def _on_rename(new_name):
            con = app.connections[account]
            con.get_module('Bookmarks').modify(jid, name=new_name)

        contact = app.contacts.get_first_contact_from_jid(account, jid)
        name = contact.get_shown_name()

        InputDialog(
            _('Rename Group Chat'),
            _('Rename Group Chat'),
            _('Please enter a new name for this group chat'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Rename'),
                               callback=_on_rename)],
            input_str=name,
            transient_for=self.window).show()

    def on_change_status_message_activate(self, _widget, account):
        app.interface.change_account_status(account)

    def on_add_to_roster(self, widget, contact, account):
        AddNewContactWindow(account, contact.jid, contact.name)

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
            if not list_of_paths:
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
                if not app.account_is_available(account):
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

        elif not (event.get_state() &
                  (Gdk.ModifierType.CONTROL_MASK |
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
            if path.get_depth() > 1:
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

    def accel_group_func(self, accel_group, acceleratable, keyval, modifier):
        # CTRL mask
        if modifier & Gdk.ModifierType.CONTROL_MASK:
            if keyval == Gdk.KEY_s:  # CTRL + s
                app.interface.change_status()
                return True
            if keyval == Gdk.KEY_k:  # CTRL + k
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

        if event.button == 2: # Middle click
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
                    if app.account_is_available(account):
                        app.interface.change_account_status(account)
                    return True

                show = helpers.get_global_show()
                if show == 'offline':
                    return True
                app.interface.change_status()
            return True

        if event.button == 1: # Left click
            model = self.modelfilter
            type_ = model[path][Column.TYPE]
            # x_min is the x start position of status icon column
            if app.settings.get('avatar_position_in_roster') == 'left':
                x_min = AvatarSize.ROSTER
            else:
                x_min = 0

            if type_ == 'group' and x < 27:
                # first cell in 1st column (the arrow SINGLE clicked)
                if self.tree.row_expanded(path):
                    self.tree.collapse_row(path)
                else:
                    self.expand_group_row(path)

            elif type_ == 'contact' and x_min < x < x_min + 27:
                if self.tree.row_expanded(path):
                    self.tree.collapse_row(path)
                else:
                    self.tree.expand_row(path, False)

    def expand_group_row(self, path):
        self.tree.expand_row(path, False)
        iter_ = self.modelfilter.get_iter(path)
        child_iter = self.modelfilter.iter_children(iter_)
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
        def on_ok(is_checked):
            remove_auth = True
            if len(list_) == 1:
                contact = list_[0][0]
                if contact.sub != 'to' and is_checked:
                    remove_auth = False
            for (contact, account) in list_:
                if _('Not in contact list') not in contact.get_shown_groups():
                    app.connections[account].get_module('Presence').unsubscribe(contact.jid,
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
        def on_ok2():
            on_ok(False)

        if len(list_) == 1:
            contact = list_[0][0]
            title = _('Remove Contact')
            pritext = _('Remove contact from contact list')
            sectext = _('You are about to remove %(name)s (%(jid)s) from '
                        'your contact list.\n') % {
                            'name': contact.get_shown_name(),
                            'jid': contact.jid}
            if contact.sub == 'to':
                NewConfirmationDialog(
                    title,
                    pritext,
                    sectext + \
                    _('By removing this contact you also remove authorization. '
                      'This means the contact will see you as offline.'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       callback=on_ok2)]).show()
            elif _('Not in contact list') in contact.get_shown_groups():
                # Contact is not in roster
                NewConfirmationDialog(
                    title,
                    pritext,
                    sectext + \
                    _('Do you want to continue?'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       callback=on_ok2)]).show()
            else:
                NewConfirmationCheckDialog(
                    title,
                    pritext,
                    sectext + \
                    _('By removing this contact you also remove authorization. '
                      'This means the contact will see you as offline.'),
                    _('_I want this contact to know my status after removal'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       callback=on_ok)],
                    modal=False).show()
        else:
            # several contact to remove at the same time
            pritext = _('Remove contacts from contact list')
            jids = ''
            for contact, _account in list_:
                jids += '%(name)s (%(jid)s)\n' % {
                    'name': contact.get_shown_name(),
                    'jid': contact.jid}
            sectext = _('By removing the following contacts, you will also '
                        'remove authorization. This means they will see you '
                        'as offline:\n\n%s') % jids
            NewConfirmationDialog(
                _('Remove Contacts'),
                pritext,
                sectext,
                [DialogButton.make('Cancel'),
                 DialogButton.make('Remove',
                                   callback=on_ok2)]).show()

    def on_publish_tune_toggled(self, widget, account):
        active = widget.get_active()
        client = app.get_client(account)
        client.get_module('UserTune').set_enabled(active)

    def on_publish_location_toggled(self, widget, account):
        active = widget.get_active()
        client = app.get_client(account)
        app.config.set_per('accounts', account, 'publish_location', active)
        if active:
            location.enable()
        else:
            client = app.get_client(account)
            client.set_user_location(None)

        client.get_module('Caps').update_caps()

    def on_add_new_contact(self, widget, account):
        AddNewContactWindow(account)

    def on_create_gc_activate(self, widget, account):
        """
        When the create gc menuitem is clicked, show the create gc window
        """
        app.app.activate_action('create-groupchat',
                                GLib.Variant('s', account))

    def on_show_transports_action(self, action, param):
        app.config.set('show_transports_group', param.get_boolean())
        action.set_state(param)
        self.refilter_shown_roster_items()

    def on_execute_command(self, widget, contact, account, resource=None):
        """
        Execute command. Full JID needed; if it is other contact, resource is
        necessary. Widget is unnecessary, only to be able to make this a
        callback
        """
        jid = contact.jid
        if resource:
            jid = jid + '/' + resource
        AdHocCommand(account, jid)

    def on_view_server_info(self, _widget, account):
        app.app.activate_action('%s-server-info' % account,
                                GLib.Variant('s', account))

    def on_roster_window_focus_in_event(self, widget, event):
        # roster received focus, so if we had urgency REMOVE IT
        # NOTE: we do not have to read the message to remove urgency
        # so this functions does that
        set_urgency_hint(widget, False)

        # if a contact row is selected, update colors (eg. for status msg)
        # because gtk engines may differ in bg when window is selected
        # or not
        if self._last_selected_contact:
            for (jid, account) in self._last_selected_contact:
                self.draw_contact(jid, account, selected=True, focus=True)

    def on_roster_window_focus_out_event(self, widget, event):
        # if a contact row is selected, update colors (eg. for status msg)
        # because gtk engines may differ in bg when window is selected
        # or not
        if self._last_selected_contact:
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
            if not list_of_paths and not app.settings.get(
            'quit_on_roster_x_button') and ((app.interface.systray_enabled and\
            app.settings.get('trayicon') == 'always') or app.settings.get(
            'allow_hide_roster')):
                if os.name == 'nt' or app.settings.get('hide_on_roster_x_button'):
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
            if app.settings.get('one_message_window') == 'always_with_roster':
                # Let MessageWindow handle this
                return
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
                dict_ = {'jid': GLib.Variant('s', jid),
                         'account': GLib.Variant('s', account)}
                app.app.activate_action('browse-history',
                                        GLib.Variant('a{sv}', dict_))

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
        if contact.is_groupchat:
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
        self.on_row_activated(widget, path)

    def on_roster_treeview_row_expanded(self, widget, titer, path):
        """
        When a row is expanded change the icon of the arrow
        """
        self._toggeling_row = True
        model = widget.get_model()
        child_model = model.get_model()
        child_iter = model.convert_iter_to_child_iter(titer)

        if self.regroup: # merged accounts
            accounts = list(app.connections.keys())
        else:
            accounts = [model[titer][Column.ACCOUNT]]

        type_ = model[titer][Column.TYPE]
        if type_ == 'group':
            group = model[titer][Column.JID]
            child_model[child_iter][Column.IMG] = get_icon_name('opened')
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
                        for titer_ in titers:
                            path = model.get_path(titer_)
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
        child_iter = model.convert_iter_to_child_iter(titer)

        if self.regroup: # merged accounts
            accounts = list(app.connections.keys())
        else:
            accounts = [model[titer][Column.ACCOUNT]]

        type_ = model[titer][Column.TYPE]
        if type_ == 'group':
            child_model[child_iter][Column.IMG] = get_icon_name('closed')
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
            nearby_family = \
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
                ServiceDiscoveryWindow(account, address_entry=True)
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
        if (c_dest.show not in ('offline', 'error') and
                c_dest.supports(Namespace.ROSTERX)):
            type_ = 'iq'
        con = app.connections[account_dest]
        con.get_module('RosterItemExchange').send_contacts(
            [c_source], c_dest.get_full_jid(), type_=type_)

    def on_drop_in_contact(self, widget, account_source, c_source, account_dest,
    c_dest, was_big_brother, context, etime):
        con_source = app.connections[account_source]
        con_dest = app.connections[account_dest]
        if (not con_source.get_module('MetaContacts').available or
                not con_dest.get_module('MetaContacts').available):
            WarningDialog(_('Metacontacts storage not supported by '
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
            # Remove it and add it again later with updated family info
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
                # We have got little brothers. Add them all back
                self._remove_metacontact_family(old_family, account_source)
            else:
                # We are only a little brother. Simply remove us from our big
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
                con = app.connections[account_source]
                con.get_module('Roster').update_contact(
                    _contact.jid, _contact.name, _contact.groups)

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
        confirm_metacontacts = app.settings.get('confirm_metacontacts')
        if confirm_metacontacts == 'no' or dest_family == source_family:
            merge_contacts()
            return
        pritext = _('You are about to create a metacontact')
        sectext = _('Metacontacts are a way to regroup several contacts in '
                    'one single contact. Generally it is used when the same '
                    'person has several XMPP- or Transport-Accounts.')
        NewConfirmationCheckDialog(
            _('Create Metacontact'),
            pritext,
            sectext,
            _('_Do not ask me again'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Create'),
                               callback=merge_contacts)]).show()

    def on_drop_in_group(self, widget, account, c_source, grp_dest,
    is_big_brother, context, etime, grp_source=None):
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
        treeview.stop_emission_by_name('drag-drop')
        target_list = treeview.drag_dest_get_target_list()
        target = treeview.drag_dest_find_target(context, target_list)
        treeview.drag_get_data(context, target, timestamp)
        return True

    def move_group(self, old_name, new_name, account):
        for group in list(app.groups[account].keys()):
            if group.startswith(old_name):
                self.rename_group(group, group.replace(old_name, new_name),
                    account)

    def drag_data_received_data(self, treeview, context, x, y, selection, info,
    etime):
        treeview.stop_emission_by_name('drag-data-received')
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if not drop_info:
            return
        data = selection.get_data().decode()
        if not data:
            return # prevents tb when several entries are dragged
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
        if not app.account_is_available(account_dest):
            return

        # A file got dropped on the roster
        if info == self.TARGET_TYPE_URI_LIST:
            if len(path_dest) < 3:
                return
            if type_dest != 'contact':
                return
            c_dest = app.contacts.get_contact_with_highest_priority(
                account_dest, jid_dest)
            if not c_dest.supports(Namespace.JINGLE_FILE_TRANSFER_5):
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
            if bad_uris:
                ErrorDialog(_('Invalid file URI:'), '\n'.join(bad_uris))
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
            text = i18n.ngettext(
                'Send this file to %s:\n',
                'Send these files to %s:\n',
                nb_uri) % c_dest.get_shown_name()

            for uri in uri_splitted:
                path = helpers.get_file_path_from_dnd_dropped_uri(uri)
                text += '\n' + os.path.basename(path)
            NewConfirmationDialog(
                _('File Transfer'),
                _('File Transfer'),
                text,
                [DialogButton.make('Cancel'),
                 DialogButton.make('Accept',
                                   text=_('_Send'),
                                   callback=_on_send_files,
                                   args=(account_dest, jid_dest, uri_splitted))],
                transient_for=self.window).show()
            return

        # Check if something is selected
        if treeview.get_selection().count_selected_rows() == 0:
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
            # Drop on a minimized groupchat
            if type_source != 'contact':
                return
            contact_jid = data
            gc_control = app.get_groupchat_control(account_dest, jid_dest)
            if gc_control is not None:
                gc_control.invite(contact_jid)
            return

        if type_source == 'group':
            if account_source != account_dest:
                # drop on another account
                return
            grp_source = model[iter_source][Column.JID]
            delimiter = app.connections[account_source].get_module('Delimiter').delimiter
            grp_source_list = grp_source.split(delimiter)
            new_grp = None
            if type_dest == 'account':
                new_grp = grp_source_list[-1]
            elif type_dest == 'group':
                grp_dest = model[iter_dest][Column.JID]
                # Don't allow to drop on e.g. Groupchats group
                if grp_dest in helpers.special_groups:
                    return
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
        if grp_source in (_('Transports'), _('Group chats')):
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
            AddNewContactWindow(account=account_dest, contact_jid=jid_source,
                user_nick=c_source.name, group=grp_dest)
            return

        # we may not add contacts from special_groups
        if grp_source in helpers.special_groups:
            if grp_source == _('Not in contact list'):
                AddNewContactWindow(
                    account=account_dest,
                    contact_jid=jid_source,
                    user_nick=c_source.name,
                    group=grp_dest)
                return
            return

        # Is the contact we drag a meta contact?
        accounts = account_source
        if self.regroup:
            accounts = app.contacts.get_accounts() or account_source
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
            #from and to are the names of contacts
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
            menu.popup_at_pointer(None)

################################################################################
### Everything about images and icons....
### Cleanup assigned to Jim++ :-)
################################################################################

    def update_icons(self):
        # Update the roster
        self.setup_and_draw_roster()

        # Update the systray
        if app.interface.systray_enabled:
            app.interface.systray.set_img()
            app.interface.systray.change_status(helpers.get_global_show())

        for win in app.interface.msg_win_mgr.windows():
            for ctrl in win.controls():
                ctrl.update_ui()
                win.redraw_tab(ctrl)

        self._status_selector.update()


    def set_account_status_icon(self, account):
        child_iterA = self._get_account_iter(account, self.model)
        if not child_iterA:
            return
        if not self.regroup:
            status = helpers.get_connection_status(account)
        else: # accounts merged
            status = helpers.get_global_show()
        self.model[child_iterA][Column.IMG] = get_icon_name(status)

################################################################################
### Style and theme related methods
################################################################################

    def show_title(self):
        change_title_allowed = app.settings.get('change_roster_title')
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


        if app.settings.get('one_message_window') == 'always_with_roster':
            # always_with_roster mode defers to the MessageWindow
            if not app.interface.msg_win_mgr.one_window_opened():
                # No MessageWindow to defer to
                self.window.set_title('Gajim')
            set_urgency_hint(self.window, nb_unread > 0)
            return

        start = ''
        if nb_unread > 1:
            start = '[' + str(nb_unread) + ']  '
        elif nb_unread == 1:
            start = '*  '

        self.window.set_title(start + 'Gajim')
        set_urgency_hint(self.window, nb_unread > 0)

    def _nec_chatstate_received(self, event):
        if event.contact.is_gc_contact or event.contact.is_pm_contact:
            return
        self.draw_contact(event.contact.jid, event.account)

    def _style_changed(self, *args):
        self.change_roster_style(None)

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
        icon_name = model[titer][Column.IMG]
        if ':' in icon_name:
            icon_name, expanded = icon_name.split(':')
            surface = get_metacontact_surface(
                icon_name, expanded == 'opened', self.scale_factor)
            renderer.set_property('icon_name', None)
            renderer.set_property('surface', surface)
        else:
            renderer.set_property('surface', None)
            renderer.set_property('icon_name', icon_name)

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

    def _nameCellDataFunc(self, column, renderer, model, titer, data=None):
        """
        When a row is added, set properties for name renderer
        """
        try:
            type_ = model[titer][Column.TYPE]
        except TypeError:
            return

        if type_ == 'account':
            color = app.css_config.get_value('.gajim-account-row', StyleAttr.COLOR)
            renderer.set_property('foreground', color)
            desc = app.css_config.get_font('.gajim-account-row')
            renderer.set_property('font-desc', desc)
            renderer.set_property('xpad', 0)
            renderer.set_property('width', 3)
            self._set_account_row_background_color(renderer)
        elif type_ == 'group':
            color = app.css_config.get_value('.gajim-group-row', StyleAttr.COLOR)
            renderer.set_property('foreground', color)
            desc = app.css_config.get_font('.gajim-group-row')
            renderer.set_property('font-desc', desc)
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
                ctrl = app.interface.minimized_controls[account].get(jid, None)
                if ctrl and ctrl.attention_flag:
                    color = app.css_config.get_value(
                        '.state_muc_directed_msg_color', StyleAttr.COLOR)
            elif app.settings.get('show_chatstate_in_roster'):
                chatstate = app.contacts.get_combined_chatstate(account, jid)
                if chatstate not in (None, 'active'):
                    color = app.css_config.get_value(
                        '.gajim-state-%s' % chatstate, StyleAttr.COLOR)
            else:
                color = app.css_config.get_value(
                    '.gajim-contact-row', StyleAttr.COLOR)
            renderer.set_property('foreground', color)

            self._set_contact_row_background_color(renderer, jid, account)
            desc = app.css_config.get_font('.gajim-contact-row')
            renderer.set_property('font-desc', desc)
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
        if model[titer][data] is None:
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
        if image is not None:
            surface = image.get_property('surface')
            renderer.set_property('surface', surface)
        # allocate space for the icon only if needed
        if model[titer][Column.AVATAR_IMG] or \
        app.settings.get('avatar_position_in_roster') == 'left':
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
        app.settings.get('avatar_position_in_roster') != 'left':
            renderer.set_property('visible', False)

        renderer.set_property('width', AvatarSize.ROSTER)
        renderer.set_property('xalign', 0.5)

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
        color = app.css_config.get_value('.gajim-account-row', StyleAttr.BACKGROUND)
        renderer.set_property('cell-background', color)

    def _set_contact_row_background_color(self, renderer, jid, account):
        if jid in app.newly_added[account]:
            renderer.set_property('cell-background', app.css_config.get_value(
                    '.gajim-roster-connected', StyleAttr.BACKGROUND))
        elif jid in app.to_be_removed[account]:
            renderer.set_property('cell-background', app.css_config.get_value(
                '.gajim-roster-disconnected', StyleAttr.BACKGROUND))
        else:
            color = app.css_config.get_value('.gajim-contact-row', StyleAttr.BACKGROUND)
            renderer.set_property('cell-background', color)

    def _set_group_row_background_color(self, renderer):
        color = app.css_config.get_value('.gajim-group-row', 'background')
        renderer.set_property('cell-background', color)

################################################################################
### Everything about building menus
### FIXME: We really need to make it simpler! 1465 lines are a few to much....
################################################################################

    def build_account_menu(self, account):
        # we have to create our own set of icons for the menu
        # using self.jabber_status_images is poopoo
        if not app.config.get_per('accounts', account, 'is_zeroconf'):
            xml = get_builder('account_context_menu.ui')
            account_context_menu = xml.get_object('account_context_menu')

            status_menuitem = xml.get_object('status_menuitem')
            add_contact_menuitem = xml.get_object('add_contact_menuitem')
            service_discovery_menuitem = xml.get_object(
                'service_discovery_menuitem')
            execute_command_menuitem = xml.get_object(
                'execute_command_menuitem')
            view_server_info_menuitem = xml.get_object(
                'view_server_info_menuitem')
            edit_account_menuitem = xml.get_object('edit_account_menuitem')
            sub_menu = Gtk.Menu()
            status_menuitem.set_submenu(sub_menu)

            for show in ('online', 'away', 'xa', 'dnd'):
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
            if not app.account_is_available(account):
                item.set_sensitive(False)

            item = Gtk.SeparatorMenuItem.new()
            sub_menu.append(item)

            uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
            item = Gtk.MenuItem.new_with_mnemonic(uf_show)
            sub_menu.append(item)
            item.connect('activate', self.change_status, account, 'offline')

            pep_menuitem = xml.get_object('pep_menuitem')
            if app.connections[account].get_module('PEP').supported:
                pep_submenu = Gtk.Menu()
                pep_menuitem.set_submenu(pep_submenu)

                item = Gtk.CheckMenuItem(label=_('Publish Tune'))
                pep_submenu.append(item)
                if sys.platform in ('win32', 'darwin'):
                    item.set_sensitive(False)
                else:
                    active = app.config.get_per('accounts', account,
                                                'publish_tune')
                    item.set_active(active)
                    item.connect('toggled', self.on_publish_tune_toggled,
                                 account)

                item = Gtk.CheckMenuItem(label=_('Publish Location'))
                pep_submenu.append(item)
                if not app.is_installed('GEOCLUE'):
                    item.set_sensitive(False)
                else:
                    active = app.config.get_per('accounts', account,
                                                'publish_location')
                    item.set_active(active)
                    item.connect('toggled', self.on_publish_location_toggled,
                                 account)

            else:
                pep_menuitem.set_sensitive(False)

            edit_account_menuitem.set_detailed_action_name(
                'app.accounts::%s' % account)
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
            view_server_info_menuitem.connect('activate',
                self.on_view_server_info, account)

            # make some items insensitive if account is offline
            if not app.account_is_available(account):
                for widget in (add_contact_menuitem, service_discovery_menuitem,
                execute_command_menuitem, view_server_info_menuitem,
                pep_menuitem):
                    widget.set_sensitive(False)
        else:
            xml = get_builder('zeroconf_context_menu.ui')
            account_context_menu = xml.get_object('zeroconf_context_menu')

            status_menuitem = xml.get_object('status_menuitem')
            zeroconf_properties_menuitem = xml.get_object(
                    'zeroconf_properties_menuitem')
            sub_menu = Gtk.Menu()
            status_menuitem.set_submenu(sub_menu)

            for show in ('online', 'away', 'dnd'):
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
            if not app.account_is_available(account):
                item.set_sensitive(False)

            uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
            item = Gtk.MenuItem.new_with_mnemonic(uf_show)
            sub_menu.append(item)
            item.connect('activate', self.change_status, account, 'offline')

            zeroconf_properties_menuitem.set_detailed_action_name(
                'app.accounts::%s' % account)

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
            accounts = [] # Put accounts in a list to sort them
            for account in app.connections:
                accounts.append(account)
            accounts.sort()
            for account in accounts:
                label = app.get_account_label(account)
                item = Gtk.MenuItem.new_with_label(label)
                account_menu = self.build_account_menu(account)
                item.set_submenu(account_menu)
                menu.append(item)

        event_button = gtkgui_helpers.get_possible_button_event(event)

        menu.attach_to_widget(self.tree, None)
        menu.connect('selection-done', gtkgui_helpers.destroy_widget)
        menu.show_all()
        menu.popup(None, None, None, None, event_button, event.time)

    def make_group_menu(self, event, iters):
        """
        Make group's popup menu
        """
        model = self.modelfilter
        groups = []
        accounts = []

        list_ = []  # list of (contact, account) tuples
        list_online = []  # list of (contact, account) tuples

        for titer in iters:
            groups.append(model[titer][Column.JID])
            accounts.append(model[titer][Column.ACCOUNT])
            # Don't show menu if groups of more than one account are selected
            if accounts[0] != model[titer][Column.ACCOUNT]:
                return
        account = accounts[0]

        show_bookmarked = True
        for jid in app.contacts.get_jid_list(account):
            contact = app.contacts.get_contact_with_highest_priority(account,
                jid)
            for group in groups:
                if group in contact.get_shown_groups():
                    if contact.show not in ('offline', 'error'):
                        list_online.append((contact, account))
                        # Check that all contacts support direct NUC invite
                        if not contact.supports(Namespace.CONFERENCE):
                            show_bookmarked = False
                    list_.append((contact, account))
        menu = Gtk.Menu()

        # Make special context menu if group is Groupchats
        if _('Group chats') in groups:
            if len(groups) == 1:
                maximize_menuitem = Gtk.MenuItem.new_with_mnemonic(
                    _('_Maximize All'))
                maximize_menuitem.connect('activate',
                    self.on_all_groupchat_maximized, list_)
                menu.append(maximize_menuitem)
            else:
                return
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
            invite_menuitem = Gtk.MenuItem.new_with_mnemonic(
                _('In_vite to'))
            if _('Transports') not in groups:
                gui_menu_builder.build_invite_submenu(invite_menuitem,
                    list_online, show_bookmarked=show_bookmarked)
                menu.append(invite_menuitem)

            # there is no singlemessage and custom status for zeroconf
            if app.config.get_per('accounts', account, 'is_zeroconf'):
                send_group_message_item.set_sensitive(False)

            if not app.account_is_available(account):
                send_group_message_item.set_sensitive(False)
                invite_menuitem.set_sensitive(False)

        special_group = False
        for group in groups:
            if group in helpers.special_groups:
                special_group = True
                break

        if not special_group and len(groups) == 1:
            group = groups[0]
            item = Gtk.SeparatorMenuItem.new() # separator
            menu.append(item)

            # Rename
            rename_item = Gtk.MenuItem.new_with_mnemonic(_('_Rename…'))
            menu.append(rename_item)
            rename_item.connect('activate', self.on_rename, 'group', group,
                account)

            # Remove group
            remove_item = Gtk.MenuItem.new_with_mnemonic(_('Remo_ve'))
            menu.append(remove_item)
            remove_item.connect('activate', self.on_remove_group_item_activated,
                group, account)

            # unsensitive if account is not connected
            if not app.account_is_available(account):
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
        blocking_supported = True
        for titer in iters:
            jid = model[titer][Column.JID]
            account = model[titer][Column.ACCOUNT]
            if not app.account_is_available(account):
                one_account_offline = True

            con = app.connections[account]
            if not con.get_module('Blocking').supported:
                blocking_supported = False
            contact = app.contacts.get_contact_with_highest_priority(
                account, jid)
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
            if not contact.supports(Namespace.CONFERENCE):
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
        if is_blocked and blocking_supported:
            unblock_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Unblock'))
            unblock_menuitem.connect('activate', self.on_unblock, list_)
            manage_contacts_submenu.append(unblock_menuitem)
        else:
            block_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Block'))
            block_menuitem.connect('activate', self.on_block, list_)
            manage_contacts_submenu.append(block_menuitem)

            if not blocking_supported:
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

            rename_menuitem = Gtk.MenuItem.new_with_mnemonic(_('Re_name'))
            rename_menuitem.connect('activate',
                                    self.on_groupchat_rename,
                                    jid,
                                    account)
            menu.append(rename_menuitem)

        disconnect_menuitem = Gtk.MenuItem.new_with_mnemonic(_(
            '_Leave'))
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
        history_menuitem.set_action_name('app.browse-history')
        dict_ = {'jid': GLib.Variant('s', contact.jid),
                 'account': GLib.Variant('s', account)}
        variant = GLib.Variant('a{sv}', dict_)
        history_menuitem.set_action_target_value(variant)

        menu.append(history_menuitem)

        event_button = gtkgui_helpers.get_possible_button_event(event)

        menu.attach_to_widget(self.tree, None)
        menu.connect('selection-done', gtkgui_helpers.destroy_widget)
        menu.show_all()
        menu.popup(None, None, None, None, event_button, event.time)

    def show_appropriate_context_menu(self, event, iters):
        # iters must be all of the same type
        model = self.modelfilter
        type_ = model[iters[0]][Column.TYPE]
        for titer in iters[1:]:
            if model[titer][Column.TYPE] != type_:
                return
        if type_ == 'group':
            self.make_group_menu(event, iters)
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
        if not list_of_paths:
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

    def fill_column(self, col):
        for rend in self.renderers_list:
            col.pack_start(rend[1], rend[2])
            if rend[0] != 'avatar':
                col.add_attribute(rend[1], rend[3], rend[4])
            col.set_cell_data_func(rend[1], rend[5], rend[6])
        # set renderers properties
        for renderer in self.renderers_propertys:
            renderer.set_property(self.renderers_propertys[renderer][0],
                self.renderers_propertys[renderer][1])

    def query_tooltip(self, widget, x_pos, y_pos, _keyboard_mode, tooltip):
        try:
            path = widget.get_path_at_pos(x_pos, y_pos)
            row = path[0]
            col = path[1]
        except TypeError:
            self._roster_tooltip.clear_tooltip()
            return False
        if not row:
            self._roster_tooltip.clear_tooltip()
            return False

        iter_ = None
        try:
            model = widget.get_model()
            iter_ = model.get_iter(row)
        except Exception:
            self._roster_tooltip.clear_tooltip()
            return False

        typ = model[iter_][Column.TYPE]
        account = model[iter_][Column.ACCOUNT]
        jid = model[iter_][Column.JID]
        connected_contacts = []

        if typ == 'group':
            if jid == _('Observers'):
                widget.set_tooltip_cell(tooltip, row, col, None)
                tooltip.set_text(
                    _('Observers can see your status, but you '
                      'are not allowed to see theirs'))
                return True
            return False

        if typ in ('contact', 'self_contact'):
            contacts = app.contacts.get_contacts(account, jid)

            for contact in contacts:
                if contact.show not in ('offline', 'error'):
                    connected_contacts.append(contact)
            if not connected_contacts:
                # no connected contacts, show the offline one
                connected_contacts = contacts
        elif typ == 'groupchat':
            connected_contacts = app.contacts.get_contacts(account, jid)
        elif typ != 'account':
            return False

        value, widget = self._roster_tooltip.get_tooltip(
            row, connected_contacts, account, typ)
        tooltip.set_custom(widget)
        return value

    def add_actions(self):

        actions = [
            ('show-roster',
             not self.xml.get_object('roster_vbox2').get_no_show_all(),
             self.on_show_roster_action),

            ('show-offline',
             app.settings.get('showoffline'),
             self.on_show_offline_contacts_action),

            ('show-active',
             app.settings.get('show_only_chat_and_online'),
             self.on_show_active_contacts_action),

            ('show-transports',
             app.settings.get('show_transports_group'),
             self.on_show_transports_action),
        ]

        for action in actions:
            action_name, variant, func = action
            act = Gio.SimpleAction.new_stateful(
                action_name, None, GLib.Variant.new_boolean(variant))
            act.connect('change-state', func)
            self.window.add_action(act)

################################################################################
###
################################################################################

    def __init__(self, application):
        self.application = application
        self.filtering = False
        self.starting = False
        self.starting_filtering = False
        # Number of renderers plugins added
        self.nb_ext_renderers = 0
        # When we quit, remember if we already saved config once
        self.save_done = False

        # [icon, name, type, jid, account, editable, mood_pixbuf,
        # activity_pixbuf, TUNE_ICON, LOCATION_ICON, avatar_img,
        # padlock_pixbuf, visible]
        self.columns = [str, str, str, str, str, str, str, str, str,
                        Gtk.Image, str, bool]

        self.xml = get_builder('roster_window.ui')
        self.window = self.xml.get_object('roster_window')
        application.add_window(self.window)
        self.add_actions()
        self.hpaned = self.xml.get_object('roster_hpaned')

        app.interface.msg_win_mgr = MessageWindowMgr(self.window, self.hpaned)
        app.interface.msg_win_mgr.connect('window-delete',
            self.on_message_window_delete)

        self.advanced_menus = [] # We keep them to destroy them
        if app.settings.get('roster_window_skip_taskbar'):
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
        self.regroup = app.settings.get('mergeaccounts')
        self.clicked_path = None # Used remember on which row we clicked
        if len(app.connections) < 2:
            # Do not merge accounts if only one exists
            self.regroup = False
        resize_window(self.window,
                      app.settings.get('roster_width'),
                      app.settings.get('roster_height'))
        restore_roster_position(self.window)

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

        # Status selector
        self._status_selector = StatusSelector()
        self.xml.roster_vbox2.add(self._status_selector)

        # Enable/Disable checkboxes at start
        if app.settings.get('showoffline'):
            self.window.lookup_action('show-active').set_enabled(False)

        if app.settings.get('show_only_chat_and_online'):
            self.window.lookup_action('show-offline').set_enabled(False)

        if self.hpaned.get_child2() is None:
            self.window.lookup_action('show-roster').set_enabled(False)

        # columns
        col = Gtk.TreeViewColumn()
        # list of renderers with attributes / properties in the form:
        # (name, renderer_object, expand?, attribute_name, attribute_value,
        # cell_data_func, func_arg)
        self.renderers_list = []
        self.renderers_propertys = {}

        renderer_text = Gtk.CellRendererText()
        self.renderers_propertys[renderer_text] = ('ellipsize',
            Pango.EllipsizeMode.END)

        def add_avatar_renderer():
            self.renderers_list.append(('avatar', Gtk.CellRendererPixbuf(),
                False, None, Column.AVATAR_IMG,
                self._fill_avatar_pixbuf_renderer, None))

        if app.settings.get('avatar_position_in_roster') == 'left':
            add_avatar_renderer()

        self.renderers_list += (
                ('icon', Gtk.CellRendererPixbuf(), False,
                'icon_name', Column.IMG, self._iconCellDataFunc, None),

                ('name', renderer_text, True,
                'markup', Column.NAME, self._nameCellDataFunc, None),

                ('mood', Gtk.CellRendererPixbuf(), False,
                'icon_name', Column.MOOD_PIXBUF,
                self._fill_pep_pixbuf_renderer, Column.MOOD_PIXBUF),

                ('activity', Gtk.CellRendererPixbuf(), False,
                'icon_name', Column.ACTIVITY_PIXBUF,
                self._fill_pep_pixbuf_renderer, Column.ACTIVITY_PIXBUF),

                ('tune', Gtk.CellRendererPixbuf(), False,
                'icon_name', Column.TUNE_ICON,
                self._fill_pep_pixbuf_renderer, Column.TUNE_ICON),

                ('geoloc', Gtk.CellRendererPixbuf(), False,
                'icon_name', Column.LOCATION_ICON,
                self._fill_pep_pixbuf_renderer, Column.LOCATION_ICON))

        if app.settings.get('avatar_position_in_roster') == 'right':
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

        # Signals
        # Drag
        self.tree.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK,
            [],
            Gdk.DragAction.DEFAULT |
            Gdk.DragAction.MOVE |
            Gdk.DragAction.COPY)
        self.tree.drag_source_add_text_targets()

        # Drop
        self.tree.enable_model_drag_dest([], Gdk.DragAction.DEFAULT)
        self.TARGET_TYPE_URI_LIST = 80
        uri_entry = Gtk.TargetEntry.new(
            'text/uri-list',
            Gtk.TargetFlags.OTHER_APP,
            self.TARGET_TYPE_URI_LIST)
        dst_targets = Gtk.TargetList.new([uri_entry])
        dst_targets.add_text_targets(0)
        self.tree.drag_dest_set_target_list(dst_targets)

        # Connect
        self.tree.connect('drag-begin', self.drag_begin)
        self.tree.connect('drag-end', self.drag_end)
        self.tree.connect('drag-drop', self.drag_drop)
        self.tree.connect('drag-data-get', self.drag_data_get_data)
        self.tree.connect('drag-data-received', self.drag_data_received_data)
        self.dragging = False
        self.xml.connect_signals(self)
        self.combobox_callback_active = True

        self.collapsed_rows = app.settings.get('collapsed_rows').split('\t')
        self.tree.set_has_tooltip(True)
        self._roster_tooltip = RosterTooltip()
        self.tree.connect('query-tooltip', self.query_tooltip)
        # Workaround: For strange reasons signal is behaving like row-changed
        self._toggeling_row = False
        self.setup_and_draw_roster()

        if app.settings.get('show_roster_on_startup') == 'always':
            self.window.show_all()
        elif app.settings.get('show_roster_on_startup') == 'never':
            if app.settings.get('trayicon') != 'always':
                # Without trayicon, user should see the roster!
                self.window.show_all()
                app.config.set('last_roster_visible', True)
        else:
            if app.settings.get('last_roster_visible') or \
            app.settings.get('trayicon') != 'always':
                self.window.show_all()

        self.scale_factor = self.window.get_scale_factor()

        if not app.config.get_per('accounts') or \
        app.config.get_per('accounts') == ['Local'] and not \
        app.config.get_per('accounts', 'Local', 'active'):
        # if we have no account configured or only Local account but not enabled
            def _open_wizard():
                open_window('AccountWizard')

            # Open wizard only after roster is created, so we can make it
            # transient for the roster window
            GLib.idle_add(_open_wizard)

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
        app.ged.register_event_handler('roster-received', ged.GUI1,
            self._nec_roster_received)
        app.ged.register_event_handler('anonymous-auth', ged.GUI1,
            self._nec_anonymous_auth)
        app.ged.register_event_handler('our-show', ged.GUI2,
            self._nec_our_show)
        app.ged.register_event_handler('connection-type', ged.GUI1,
            self._nec_connection_type)
        app.ged.register_event_handler('agent-removed', ged.GUI1,
            self._nec_agent_removed)
        app.ged.register_event_handler('nickname-received', ged.GUI1,
            self._on_nickname_received)
        app.ged.register_event_handler('mood-received', ged.GUI1,
            self._on_mood_received)
        app.ged.register_event_handler('activity-received', ged.GUI1,
            self._on_activity_received)
        app.ged.register_event_handler('tune-received', ged.GUI1,
            self._on_tune_received)
        app.ged.register_event_handler('location-received', ged.GUI1,
            self._on_location_received)
        app.ged.register_event_handler('update-roster-avatar', ged.GUI1,
            self._nec_update_avatar)
        app.ged.register_event_handler('update-room-avatar', ged.GUI1,
            self._nec_update_avatar)
        app.ged.register_event_handler('muc-subject', ged.GUI1,
            self._nec_muc_subject_received)
        app.ged.register_event_handler('metacontacts-received', ged.GUI2,
            self._nec_metacontacts_received)
        app.ged.register_event_handler('signed-in', ged.GUI1,
            self._nec_signed_in)
        app.ged.register_event_handler('decrypted-message-received', ged.GUI2,
            self._nec_decrypted_message_received)
        app.ged.register_event_handler('blocking', ged.GUI1,
            self._nec_blocking)
        app.ged.register_event_handler('style-changed', ged.GUI1,
            self._style_changed)
        app.ged.register_event_handler('chatstate-received', ged.GUI1,
                                       self._nec_chatstate_received)
        app.ged.register_event_handler('muc-disco-update', ged.GUI1,
                                       self._on_muc_disco_update)
        app.ged.register_event_handler('bookmarks-received', ged.GUI2,
                                       self._on_bookmarks_received)
