# -*- coding: utf-8 -*-
## src/dialogs.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2005-2008 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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
from gi.repository import GObject
from gi.repository import GLib
import cairo
import os
import nbxmpp
import time

import gtkgui_helpers
import vcard
import conversation_textview
import message_control
import dataforms_widget

from random import randrange
from common import pep
from common import ged

try:
    import gtkspell
    HAS_GTK_SPELL = True
except ImportError:
    HAS_GTK_SPELL = False

# those imports are not used in this file, but in files that 'import dialogs'
# so they can do dialog.GajimThemesWindow() for example
from filetransfers_window import FileTransfersWindow
from gajim_themes_window import GajimThemesWindow
from advanced_configuration_window import AdvancedConfigurationWindow

from common import gajim
from common import helpers
from common import i18n
from common import dataforms
from common.exceptions import GajimGeneralException
from common.connection_handlers_events import MessageOutgoingEvent

class EditGroupsDialog:
    """
    Class for the edit group dialog window
    """

    def __init__(self, list_):
        """
        list_ is a list of (contact, account) tuples
        """
        self.xml = gtkgui_helpers.get_gtk_builder('edit_groups_dialog.ui')
        self.dialog = self.xml.get_object('edit_groups_dialog')
        self.dialog.set_transient_for(gajim.interface.roster.window)
        self.list_ = list_
        self.changes_made = False
        self.treeview = self.xml.get_object('groups_treeview')
        if len(list_) == 1:
            contact = list_[0][0]
            self.xml.get_object('nickname_label').set_markup(
                    _('Contact name: <i>%s</i>') % contact.get_shown_name())
            self.xml.get_object('jid_label').set_markup(
                    _('Jabber ID: <i>%s</i>') % contact.jid)
        else:
            self.xml.get_object('nickname_label').set_no_show_all(True)
            self.xml.get_object('nickname_label').hide()
            self.xml.get_object('jid_label').set_no_show_all(True)
            self.xml.get_object('jid_label').hide()

        self.xml.connect_signals(self)
        self.init_list()

        self.dialog.show_all()
        if self.changes_made:
            for (contact, account) in self.list_:
                gajim.connections[account].update_contact(contact.jid,
                    contact.name, contact.groups)

    def on_edit_groups_dialog_response(self, widget, response_id):
        if response_id == Gtk.ResponseType.CLOSE:
            self.dialog.destroy()

    def remove_group(self, group):
        """
        Remove group group from all contacts and all their brothers
        """
        for (contact, account) in self.list_:
            gajim.interface.roster.remove_contact_from_groups(contact.jid,
                account, [group])

        # FIXME: Ugly workaround.
        gajim.interface.roster.draw_group(_('General'), account)

    def add_group(self, group):
        """
        Add group group to all contacts and all their brothers
        """
        for (contact, account) in self.list_:
            gajim.interface.roster.add_contact_to_groups(contact.jid, account,
                [group])

        # FIXME: Ugly workaround.
        # Maybe we haven't been in any group (defaults to General)
        gajim.interface.roster.draw_group(_('General'), account)

    def on_add_button_clicked(self, widget):
        group = self.xml.get_object('group_entry').get_text()
        if not group:
            return
        # Do not allow special groups
        if group in helpers.special_groups:
            return
        # check if it already exists
        model = self.treeview.get_model()
        iter_ = model.get_iter_first()
        while iter_:
            if model.get_value(iter_, 0) == group:
                return
            iter_ = model.iter_next(iter_)
        self.changes_made = True
        model.append((group, True, False))
        self.add_group(group)
        self.init_list() # Re-draw list to sort new item

    def group_toggled_cb(self, cell, path):
        self.changes_made = True
        model = self.treeview.get_model()
        if model[path][2]:
            model[path][2] = False
            model[path][1] = True
        else:
            model[path][1] = not model[path][1]
        group = model[path][0]
        if model[path][1]:
            self.add_group(group)
        else:
            self.remove_group(group)

    def init_list(self):
        store = Gtk.ListStore(str, bool, bool)
        self.treeview.set_model(store)
        for column in self.treeview.get_columns():
            # Clear treeview when re-drawing
            self.treeview.remove_column(column)
        accounts = []
        # Store groups in a list so we can sort them and the number of contacts in
        # it
        groups = {}
        for (contact, account) in self.list_:
            if account not in accounts:
                accounts.append(account)
                for g in gajim.groups[account].keys():
                    if g in groups:
                        continue
                    groups[g] = 0
            c_groups = contact.groups
            for g in c_groups:
                groups[g] += 1
        group_list = []
        # Remove special groups if they are empty
        for group in groups:
            if group not in helpers.special_groups or groups[group] > 0:
                group_list.append(group)
        group_list.sort()
        for group in group_list:
            iter_ = store.append()
            store.set(iter_, 0, group) # Group name
            if groups[group] == 0:
                store.set(iter_, 1, False)
            else:
                store.set(iter_, 1, True)
                if groups[group] == len(self.list_):
                    # all contacts are in this group
                    store.set(iter_, 2, False)
                else:
                    store.set(iter_, 2, True)
        column = Gtk.TreeViewColumn(_('Group'))
        column.set_expand(True)
        self.treeview.append_column(column)
        renderer = Gtk.CellRendererText()
        column.pack_start(renderer, True)
        column.add_attribute(renderer, 'text', 0)

        column = Gtk.TreeViewColumn(_('In the group'))
        column.set_expand(False)
        self.treeview.append_column(column)
        renderer = Gtk.CellRendererToggle()
        column.pack_start(renderer, True)
        renderer.set_property('activatable', True)
        renderer.connect('toggled', self.group_toggled_cb)
        column.add_attribute(renderer, 'active', 1)
        column.add_attribute(renderer, 'inconsistent', 2)

class PassphraseDialog:
    """
    Class for Passphrase dialog
    """
    def __init__(self, titletext, labeltext, checkbuttontext=None,
    ok_handler=None, cancel_handler=None):
        self.xml = gtkgui_helpers.get_gtk_builder('passphrase_dialog.ui')
        self.window = self.xml.get_object('passphrase_dialog')
        self.passphrase_entry = self.xml.get_object('passphrase_entry')
        self.passphrase = -1
        self.window.set_title(titletext)
        self.xml.get_object('message_label').set_text(labeltext)

        self.ok = False

        self.cancel_handler = cancel_handler
        self.ok_handler = ok_handler
        okbutton = self.xml.get_object('ok_button')
        okbutton.connect('clicked', self.on_okbutton_clicked)
        cancelbutton = self.xml.get_object('cancel_button')
        cancelbutton.connect('clicked', self.on_cancelbutton_clicked)

        self.xml.connect_signals(self)
        self.window.set_transient_for(gajim.interface.roster.window)
        self.window.show_all()

        self.check = bool(checkbuttontext)
        checkbutton =   self.xml.get_object('save_passphrase_checkbutton')
        if self.check:
            checkbutton.set_label(checkbuttontext)
        else:
            checkbutton.hide()

    def on_okbutton_clicked(self, widget):
        if not self.ok_handler:
            return

        passph = self.passphrase_entry.get_text()

        if self.check:
            checked = self.xml.get_object('save_passphrase_checkbutton').\
                    get_active()
        else:
            checked = False

        self.ok = True

        self.window.destroy()

        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](passph, checked, *self.ok_handler[1:])
        else:
            self.ok_handler(passph, checked)

    def on_cancelbutton_clicked(self, widget):
        self.window.destroy()

    def on_passphrase_dialog_destroy(self, widget):
        if self.cancel_handler and not self.ok:
            self.cancel_handler()

class ChooseGPGKeyDialog:
    """
    Class for GPG key dialog
    """

    def __init__(self, title_text, prompt_text, secret_keys, on_response,
            selected=None, transient_for=None):
        '''secret_keys : {keyID: userName, ...}'''
        self.on_response = on_response
        xml = gtkgui_helpers.get_gtk_builder('choose_gpg_key_dialog.ui')
        self.window = xml.get_object('choose_gpg_key_dialog')
        self.window.set_title(title_text)
        self.window.set_transient_for(transient_for)
        self.keys_treeview = xml.get_object('keys_treeview')
        prompt_label = xml.get_object('prompt_label')
        prompt_label.set_text(prompt_text)
        model = Gtk.ListStore(str, str)
        model.set_sort_func(1, self.sort_keys)
        model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.keys_treeview.set_model(model)
        #columns
        renderer = Gtk.CellRendererText()
        col = self.keys_treeview.insert_column_with_attributes(-1, _('KeyID'),
                renderer, text=0)
        col.set_sort_column_id(0)
        renderer = Gtk.CellRendererText()
        col = self.keys_treeview.insert_column_with_attributes(-1,
                _('Contact name'), renderer, text=1)
        col.set_sort_column_id(1)
        self.keys_treeview.set_search_column(1)
        self.fill_tree(secret_keys, selected)
        self.window.connect('response', self.on_dialog_response)
        self.window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.window.show_all()

    def sort_keys(self, model, iter1, iter2, data=None):
        value1 = model[iter1][1]
        value2 = model[iter2][1]
        if value1 == _('None'):
            return -1
        elif value2 == _('None'):
            return 1
        elif value1 < value2:
            return -1
        return 1

    def on_dialog_response(self, dialog, response):
        selection = self.keys_treeview.get_selection()
        (model, iter_) = selection.get_selected()
        if iter_ and response == Gtk.ResponseType.OK:
            keyID = [ model[iter_][0], model[iter_][1] ]
        else:
            keyID = None
        self.on_response(keyID)
        self.window.destroy()

    def fill_tree(self, list_, selected):
        model = self.keys_treeview.get_model()
        for keyID in list_.keys():
            iter_ = model.append((keyID, list_[keyID]))
            if keyID == selected:
                path = model.get_path(iter_)
                self.keys_treeview.set_cursor(path)


class ChangeActivityDialog:
    PAGELIST = ['doing_chores', 'drinking', 'eating', 'exercising', 'grooming',
            'having_appointment', 'inactive', 'relaxing', 'talking', 'traveling',
            'working']

    def __init__(self, on_response, activity=None, subactivity=None, text=''):
        self.on_response = on_response
        self.activity = activity
        self.subactivity = subactivity
        self.text = text
        self.xml = gtkgui_helpers.get_gtk_builder('change_activity_dialog.ui')
        self.window = self.xml.get_object('change_activity_dialog')
        self.window.set_transient_for(gajim.interface.roster.window)

        self.checkbutton = self.xml.get_object('enable_checkbutton')
        self.notebook = self.xml.get_object('notebook')
        self.entry = self.xml.get_object('description_entry')

        rbtns = {}
        group = None

        for category in pep.ACTIVITIES:
            item = self.xml.get_object(category + '_image')
            item.set_from_pixbuf(
                    gtkgui_helpers.load_activity_icon(category).get_pixbuf())
            item.set_tooltip_text(pep.ACTIVITIES[category]['category'])

            vbox = self.xml.get_object(category + '_vbox')
            vbox.set_border_width(5)

            # Other
            act = category + '_other'

            if group:
                rbtns[act] = Gtk.RadioButton()
                rbtns[act].join_group(group)
            else:
                rbtns[act] = group = Gtk.RadioButton()

            hbox = Gtk.HBox(False, 5)
            hbox.pack_start(gtkgui_helpers.load_activity_icon(category,
                activity), False, False, 0)
            lbl = Gtk.Label(label='<b>' + pep.ACTIVITIES[category]['category'] \
                + '</b>')
            lbl.set_use_markup(True)
            hbox.pack_start(lbl, False, False, 0)
            rbtns[act].add(hbox)
            rbtns[act].connect('toggled', self.on_rbtn_toggled,
                    [category, 'other'])
            vbox.pack_start(rbtns[act], False, False, 0)

            activities = []
            for activity in pep.ACTIVITIES[category]:
                activities.append(activity)
            activities.sort()
            for activity in activities:
                if activity == 'category':
                    continue

                act = category + '_' + activity

                if group:
                    rbtns[act] = Gtk.RadioButton()
                    rbtns[act].join_group(group)
                else:
                    rbtns[act] = group = Gtk.RadioButton()

                hbox = Gtk.HBox(False, 5)
                hbox.pack_start(gtkgui_helpers.load_activity_icon(category,
                        activity), False, False, 0)
                hbox.pack_start(Gtk.Label(pep.ACTIVITIES[category][activity]),
                        False, False, 0)
                rbtns[act].connect('toggled', self.on_rbtn_toggled,
                        [category, activity])
                rbtns[act].add(hbox)
                vbox.pack_start(rbtns[act], False, False, 0)


        self.default_radio = rbtns['doing_chores_other']

        if self.activity in pep.ACTIVITIES:
            if not self.subactivity in pep.ACTIVITIES[self.activity]:
                self.subactivity = 'other'

            rbtns[self.activity + '_' + self.subactivity].set_active(True)

            self.checkbutton.set_active(True)
            self.notebook.set_sensitive(True)
            self.entry.set_sensitive(True)

            self.notebook.set_current_page(
                    self.PAGELIST.index(self.activity))

            self.entry.set_text(text)

        else:
            self.checkbutton.set_active(False)

        self.xml.connect_signals(self)
        self.window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.window.show_all()

    def on_enable_checkbutton_toggled(self, widget):
        self.notebook.set_sensitive(widget.get_active())
        self.entry.set_sensitive(widget.get_active())
        if not self.activity:
            self.default_radio.set_active(True)

    def on_rbtn_toggled(self, widget, data):
        if widget.get_active():
            self.activity = data[0]
            self.subactivity = data[1]

    def on_ok_button_clicked(self, widget):
        """
        Return activity and messsage (None if no activity selected)
        """
        if self.checkbutton.get_active():
            self.on_response(self.activity, self.subactivity,
                    self.entry.get_text())
        else:
            self.on_response(None, None, '')
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

class ChangeMoodDialog:
    COLS = 11

    def __init__(self, on_response, mood=None, text=''):
        self.on_response = on_response
        self.mood = mood
        self.text = text
        self.xml = gtkgui_helpers.get_gtk_builder('change_mood_dialog.ui')

        self.window = self.xml.get_object('change_mood_dialog')
        self.window.set_transient_for(gajim.interface.roster.window)
        self.window.set_title(_('Set Mood'))

        table = self.xml.get_object('mood_icons_table')
        self.label = self.xml.get_object('mood_label')
        self.entry = self.xml.get_object('description_entry')

        no_mood_button = self.xml.get_object('no_mood_button')
        no_mood_button.set_mode(False)
        no_mood_button.connect('clicked',
                self.on_mood_button_clicked, None)

        x = 1
        y = 0
        self.mood_buttons = {}

        # Order them first
        self.MOODS = []
        for mood in pep.MOODS:
            self.MOODS.append(mood)
        self.MOODS.sort()

        for mood in self.MOODS:
            self.mood_buttons[mood] = Gtk.RadioButton()
            self.mood_buttons[mood].join_group(no_mood_button)
            self.mood_buttons[mood].set_mode(False)
            self.mood_buttons[mood].add(gtkgui_helpers.load_mood_icon(mood))
            self.mood_buttons[mood].set_relief(Gtk.ReliefStyle.NONE)
            self.mood_buttons[mood].set_tooltip_text(pep.MOODS[mood])
            self.mood_buttons[mood].connect('clicked',
                    self.on_mood_button_clicked, mood)
            table.attach(self.mood_buttons[mood], x, x + 1, y, y + 1)

            # Calculate the next position
            x += 1
            if x >= self.COLS:
                x = 0
                y += 1

        if self.mood in pep.MOODS:
            self.mood_buttons[self.mood].set_active(True)
            self.label.set_text(pep.MOODS[self.mood])
            self.entry.set_sensitive(True)
            if self.text:
                self.entry.set_text(self.text)
        else:
            self.label.set_text(_('None'))
            self.entry.set_text('')
            self.entry.set_sensitive(False)

        self.xml.connect_signals(self)
        self.window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.window.show_all()

    def on_mood_button_clicked(self, widget, data):
        if data:
            self.label.set_text(pep.MOODS[data])
            self.entry.set_sensitive(True)
        else:
            self.label.set_text(_('None'))
            self.entry.set_text('')
            self.entry.set_sensitive(False)
        self.mood = data

    def on_ok_button_clicked(self, widget):
        '''Return mood and messsage (None if no mood selected)'''
        message = self.entry.get_text()
        self.on_response(self.mood, message)
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

class TimeoutDialog:
    """
    Class designed to be derivated to create timeout'd dialogs (dialogs that
    closes automatically after a timeout)
    """
    def __init__(self, timeout, on_timeout):
        self.countdown_left = timeout
        self.countdown_enabled = True
        self.title_text = ''
        self.on_timeout = on_timeout

    def run_timeout(self):
        if self.countdown_left > 0:
            self.countdown()
            GLib.timeout_add_seconds(1, self.countdown)

    def on_timeout():
        """
        To be implemented in derivated classes
        """
        pass

    def countdown(self):
        if self.countdown_enabled:
            if self.countdown_left <= 0:
                self.on_timeout()
                return False
            self.dialog.set_title('%s [%s]' % (self.title_text,
                    str(self.countdown_left)))
            self.countdown_left -= 1
            return True
        else:
            self.dialog.set_title(self.title_text)
            return False

class ChangeStatusMessageDialog(TimeoutDialog):
    def __init__(self, on_response, show=None, show_pep=True):
        countdown_time = gajim.config.get('change_status_window_timeout')
        TimeoutDialog.__init__(self, countdown_time, self.on_timeout)
        self.show = show
        self.pep_dict = {}
        self.show_pep = show_pep
        self.on_response = on_response
        self.xml = gtkgui_helpers.get_gtk_builder('change_status_message_dialog.ui')
        self.dialog = self.xml.get_object('change_status_message_dialog')
        self.dialog.set_transient_for(gajim.interface.roster.window)
        msg = None
        if show:
            uf_show = helpers.get_uf_show(show)
            self.title_text = _('%s Status Message') % uf_show
            msg = gajim.config.get_per('statusmsg', '_last_' + self.show,
                                                               'message')
            self.pep_dict['activity'] = gajim.config.get_per('statusmsg',
                '_last_' + self.show, 'activity')
            self.pep_dict['subactivity'] = gajim.config.get_per('statusmsg',
                '_last_' + self.show, 'subactivity')
            self.pep_dict['activity_text'] = gajim.config.get_per('statusmsg',
                '_last_' + self.show, 'activity_text')
            self.pep_dict['mood'] = gajim.config.get_per('statusmsg',
                '_last_' + self.show, 'mood')
            self.pep_dict['mood_text'] = gajim.config.get_per('statusmsg',
                '_last_' + self.show, 'mood_text')
        else:
            self.title_text = _('Status Message')
        self.dialog.set_title(self.title_text)

        message_textview = self.xml.get_object('message_textview')
        self.message_buffer = message_textview.get_buffer()
        self.message_buffer.connect('changed', self.on_message_buffer_changed)
        if not msg:
            msg = ''
        msg = helpers.from_one_line(msg)
        self.message_buffer.set_text(msg)

        # have an empty string selectable, so user can clear msg
        self.preset_messages_dict = {'': ['', '', '', '', '', '']}
        for msg_name in gajim.config.get_per('statusmsg'):
            if msg_name.startswith('_last_'):
                continue
            opts = []
            for opt in ['message', 'activity', 'subactivity', 'activity_text',
                                    'mood', 'mood_text']:
                opts.append(gajim.config.get_per('statusmsg', msg_name, opt))
            opts[0] = helpers.from_one_line(opts[0])
            self.preset_messages_dict[msg_name] = opts
        sorted_keys_list = helpers.get_sorted_keys(self.preset_messages_dict)

        self.message_liststore = Gtk.ListStore(str) # msg_name
        self.message_combobox = self.xml.get_object('message_combobox')
        self.message_combobox.set_model(self.message_liststore)
        cellrenderertext = Gtk.CellRendererText()
        self.message_combobox.pack_start(cellrenderertext, True)
        self.message_combobox.add_attribute(cellrenderertext, 'text', 0)
        for msg_name in sorted_keys_list:
            self.message_liststore.append((msg_name,))

        if show_pep:
            self.draw_activity()
            self.draw_mood()
        else:
            # remove acvtivity / mood lines
            self.xml.get_object('activity_label').set_no_show_all(True)
            self.xml.get_object('activity_button').set_no_show_all(True)
            self.xml.get_object('mood_label').set_no_show_all(True)
            self.xml.get_object('mood_button').set_no_show_all(True)
            self.xml.get_object('activity_label').hide()
            self.xml.get_object('activity_button').hide()
            self.xml.get_object('mood_label').hide()
            self.xml.get_object('mood_button').hide()

        self.xml.connect_signals(self)
        self.run_timeout()
        self.dialog.connect('response', self.on_dialog_response)
        self.dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.dialog.show_all()

    def draw_activity(self):
        """
        Set activity button
        """
        img = self.xml.get_object('activity_image')
        label = self.xml.get_object('activity_button_label')
        if 'activity' in self.pep_dict and self.pep_dict['activity'] in \
           pep.ACTIVITIES:
            if 'subactivity' in self.pep_dict and self.pep_dict['subactivity'] \
            in pep.ACTIVITIES[self.pep_dict['activity']]:
                img.set_from_pixbuf(gtkgui_helpers.load_activity_icon(
                    self.pep_dict['activity'], self.pep_dict['subactivity']).\
                        get_pixbuf())
            else:
                img.set_from_pixbuf(gtkgui_helpers.load_activity_icon(
                    self.pep_dict['activity']).get_pixbuf())
            if self.pep_dict['activity_text']:
                label.set_text(self.pep_dict['activity_text'])
            else:
                label.set_text('')
        else:
            img.set_from_pixbuf(None)
            label.set_text('')

    def draw_mood(self):
        """
        Set mood button
        """
        img = self.xml.get_object('mood_image')
        label = self.xml.get_object('mood_button_label')
        if 'mood' in self.pep_dict and self.pep_dict['mood'] in pep.MOODS:
            img.set_from_pixbuf(gtkgui_helpers.load_mood_icon(
                self.pep_dict['mood']).get_pixbuf())
            if self.pep_dict['mood_text']:
                label.set_text(self.pep_dict['mood_text'])
            else:
                label.set_text('')
        else:
            img.set_from_pixbuf(None)
            label.set_text('')

    def on_timeout(self):
        # Prevent GUI freeze when the combobox menu is opened on close
        self.message_combobox.popdown()
        self.dialog.response(Gtk.ResponseType.OK)

    def on_dialog_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            beg, end = self.message_buffer.get_bounds()
            message = self.message_buffer.get_text(beg, end, True).strip()
            message = helpers.remove_invalid_xml_chars(message)
            msg = helpers.to_one_line(message)
            if self.show:
                gajim.config.set_per('statusmsg', '_last_' + self.show,
                    'message', msg)
                if self.show_pep:
                    gajim.config.set_per('statusmsg', '_last_' + self.show,
                        'activity', self.pep_dict['activity'])
                    gajim.config.set_per('statusmsg', '_last_' + self.show,
                        'subactivity', self.pep_dict['subactivity'])
                    gajim.config.set_per('statusmsg', '_last_' + self.show,
                        'activity_text', self.pep_dict['activity_text'])
                    gajim.config.set_per('statusmsg', '_last_' + self.show,
                        'mood', self.pep_dict['mood'])
                    gajim.config.set_per('statusmsg', '_last_' + self.show,
                        'mood_text', self.pep_dict['mood_text'])
        else:
            message = None # user pressed Cancel button or X wm button
        self.dialog.destroy()
        self.on_response(message, self.pep_dict)

    def on_message_combobox_changed(self, widget):
        self.countdown_enabled = False
        model = widget.get_model()
        active = widget.get_active()
        if active < 0:
            return None
        name = model[active][0]
        self.message_buffer.set_text(self.preset_messages_dict[name][0])
        self.pep_dict['activity'] = self.preset_messages_dict[name][1]
        self.pep_dict['subactivity'] = self.preset_messages_dict[name][2]
        self.pep_dict['activity_text'] = self.preset_messages_dict[name][3]
        self.pep_dict['mood'] = self.preset_messages_dict[name][4]
        self.pep_dict['mood_text'] = self.preset_messages_dict[name][5]
        self.draw_activity()
        self.draw_mood()

    def on_change_status_message_dialog_key_press_event(self, widget, event):
        self.countdown_enabled = False
        if event.keyval == Gdk.KEY_Return or \
           event.keyval == Gdk.KEY_KP_Enter: # catch CTRL+ENTER
            if (event.get_state() & Gdk.ModifierType.CONTROL_MASK):
                self.dialog.response(Gtk.ResponseType.OK)
                # Stop the event
                return True

    def on_message_buffer_changed(self, widget):
        self.countdown_enabled = False
        self.toggle_sensitiviy_of_save_as_preset()

    def toggle_sensitiviy_of_save_as_preset(self):
        btn = self.xml.get_object('save_as_preset_button')
        if self.message_buffer.get_char_count() == 0:
            btn.set_sensitive(False)
        else:
            btn.set_sensitive(True)

    def on_save_as_preset_button_clicked(self, widget):
        self.countdown_enabled = False
        start_iter, finish_iter = self.message_buffer.get_bounds()
        status_message_to_save_as_preset = self.message_buffer.get_text(
                start_iter, finish_iter, True)
        def on_ok(msg_name):
            msg_text = status_message_to_save_as_preset
            msg_text_1l = helpers.to_one_line(msg_text)
            if not msg_name: # msg_name was ''
                msg_name = msg_text_1l

            def on_ok2():
                self.preset_messages_dict[msg_name] = [
                    msg_text, self.pep_dict.get('activity'),
                    self.pep_dict.get('subactivity'),
                    self.pep_dict.get('activity_text'),
                    self.pep_dict.get('mood'), self.pep_dict.get('mood_text')]
                gajim.config.set_per('statusmsg', msg_name, 'message',
                    msg_text_1l)
                gajim.config.set_per('statusmsg', msg_name, 'activity',
                    self.pep_dict.get('activity'))
                gajim.config.set_per('statusmsg', msg_name, 'subactivity',
                    self.pep_dict.get('subactivity'))
                gajim.config.set_per('statusmsg', msg_name, 'activity_text',
                    self.pep_dict.get('activity_text'))
                gajim.config.set_per('statusmsg', msg_name, 'mood',
                    self.pep_dict.get('mood'))
                gajim.config.set_per('statusmsg', msg_name, 'mood_text',
                    self.pep_dict.get('mood_text'))
            if msg_name in self.preset_messages_dict:
                ConfirmationDialog(_('Overwrite Status Message?'),
                    _('This name is already used. Do you want to overwrite this '
                    'status message?'), on_response_ok=on_ok2)
                return
            gajim.config.add_per('statusmsg', msg_name)
            on_ok2()
            iter_ = self.message_liststore.append((msg_name,))
            # select in combobox the one we just saved
            self.message_combobox.set_active_iter(iter_)
        InputDialog(_('Save as Preset Status Message'),
            _('Please type a name for this status message'), is_modal=False,
            ok_handler=on_ok)

    def on_activity_button_clicked(self, widget):
        self.countdown_enabled = False
        def on_response(activity, subactivity, text):
            self.pep_dict['activity'] = activity or ''
            self.pep_dict['subactivity'] = subactivity or ''
            self.pep_dict['activity_text'] = text
            self.draw_activity()
        ChangeActivityDialog(on_response, self.pep_dict['activity'],
            self.pep_dict['subactivity'], self.pep_dict['activity_text'])

    def on_mood_button_clicked(self, widget):
        self.countdown_enabled = False
        def on_response(mood, text):
            self.pep_dict['mood'] = mood or ''
            self.pep_dict['mood_text'] = text
            self.draw_mood()
        ChangeMoodDialog(on_response, self.pep_dict['mood'],
                                         self.pep_dict['mood_text'])

class AddNewContactWindow:
    """
    Class for AddNewContactWindow
    """

    uid_labels = {'jabber': _('Jabber ID:'),
        'aim': _('AIM Address:'),
        'gadu-gadu': _('GG Number:'),
        'icq': _('ICQ Number:'),
        'msn': _('MSN Address:'),
        'yahoo': _('Yahoo! Address:')}

    def __init__(self, account=None, jid=None, user_nick=None, group=None):
        self.account = account
        self.adding_jid = False
        if account is None:
            # fill accounts with active accounts
            accounts = []
            for account in gajim.connections.keys():
                if gajim.connections[account].connected > 1:
                    accounts.append(account)
            if not accounts:
                return
            if len(accounts) == 1:
                self.account = account
        else:
            accounts = [self.account]
        if self.account:
            location = gajim.interface.instances[self.account]
        else:
            location = gajim.interface.instances
        if 'add_contact' in location:
            location['add_contact'].window.present()
            # An instance is already opened
            return
        location['add_contact'] = self
        self.xml = gtkgui_helpers.get_gtk_builder('add_new_contact_window.ui')
        self.xml.connect_signals(self)
        self.window = self.xml.get_object('add_new_contact_window')
        for w in ('account_combobox', 'account_hbox', 'account_label',
        'uid_label', 'uid_entry', 'protocol_combobox', 'protocol_jid_combobox',
        'protocol_hbox', 'nickname_entry', 'message_scrolledwindow',
        'save_message_checkbutton', 'register_hbox', 'subscription_table',
        'add_button', 'message_textview', 'connected_label',
        'group_comboboxentry', 'auto_authorize_checkbutton'):
            self.__dict__[w] = self.xml.get_object(w)
        if account and len(gajim.connections) >= 2:
            self.default_desc = _('Please fill in the data of the contact you '
                'want to add in account %s') % account
        else:
            self.default_desc = _('Please fill in the data of the contact you '
                'want to add')
        self.xml.get_object('prompt_label').set_text(self.default_desc)
        self.agents = {'jabber': []}
        self.gateway_prompt = {}
        # types to which we are not subscribed but account has an agent for it
        self.available_types = []
        for acct in accounts:
            for j in gajim.contacts.get_jid_list(acct):
                if gajim.jid_is_transport(j):
                    type_ = gajim.get_transport_name_from_jid(j, False)
                    if not type_:
                        continue
                    if type_ in self.agents:
                        self.agents[type_].append(j)
                    else:
                        self.agents[type_] = [j]
                    self.gateway_prompt[j] = {'desc': None, 'prompt': None}
        # Now add the one to which we can register
        for acct in accounts:
            for type_ in gajim.connections[acct].available_transports:
                if type_ in self.agents:
                    continue
                self.agents[type_] = []
                for jid_ in gajim.connections[acct].available_transports[type_]:
                    if not jid_ in self.agents[type_]:
                        self.agents[type_].append(jid_)
                        self.gateway_prompt[jid_] = {'desc': None,
                            'prompt': None}
                self.available_types.append(type_)
        # Combobox with transport/jabber icons
        liststore = Gtk.ListStore(str, GdkPixbuf.Pixbuf, str)
        cell = Gtk.CellRendererPixbuf()
        self.protocol_combobox.pack_start(cell, False)
        self.protocol_combobox.add_attribute(cell, 'pixbuf', 1)
        cell = Gtk.CellRendererText()
        cell.set_property('xpad', 5)
        self.protocol_combobox.pack_start(cell, True)
        self.protocol_combobox.add_attribute(cell, 'text', 0)
        self.protocol_combobox.set_model(liststore)
        uf_type = {'jabber': 'Jabber', 'aim': 'AIM', 'gadu-gadu': 'Gadu Gadu',
            'icq': 'ICQ', 'msn': 'MSN', 'yahoo': 'Yahoo'}
        # Jabber as first
        img = gajim.interface.jabber_state_images['16']['online']
        liststore.append(['Jabber', img.get_pixbuf(), 'jabber'])
        for type_ in self.agents:
            if type_ == 'jabber':
                continue
            imgs = gajim.interface.roster.transports_state_images
            img = None
            if type_ in imgs['16'] and 'online' in imgs['16'][type_]:
                img = imgs['16'][type_]['online']
                if type_ in uf_type:
                    liststore.append([uf_type[type_], img.get_pixbuf(), type_])
                else:
                    liststore.append([type_, img.get_pixbuf(), type_])
            else:
                liststore.append([type_, img, type_])
            if account:
                for service in self.agents[type_]:
                    gajim.connections[account].request_gateway_prompt(service)
        self.protocol_combobox.set_active(0)
        self.auto_authorize_checkbutton.show()
        liststore = Gtk.ListStore(str)
        self.protocol_jid_combobox.set_model(liststore)
        if jid:
            self.jid_escaped = True
            type_ = gajim.get_transport_name_from_jid(jid)
            if not type_:
                type_ = 'jabber'
            if type_ == 'jabber':
                self.uid_entry.set_text(jid)
            else:
                uid, transport = gajim.get_name_and_server_from_jid(jid)
                self.uid_entry.set_text(uid.replace('%', '@', 1))
            # set protocol_combobox
            model = self.protocol_combobox.get_model()
            iter_ = model.get_iter_first()
            i = 0
            while iter_:
                if model[iter_][2] == type_:
                    self.protocol_combobox.set_active(i)
                    break
                iter_ = model.iter_next(iter_)
                i += 1

            # set protocol_jid_combobox
            self.protocol_jid_combobox.set_active(0)
            model = self.protocol_jid_combobox.get_model()
            iter_ = model.get_iter_first()
            i = 0
            while iter_:
                if model[iter_][0] == transport:
                    self.protocol_jid_combobox.set_active(i)
                    break
                iter_ = model.iter_next(iter_)
                i += 1
            if user_nick:
                self.nickname_entry.set_text(user_nick)
            self.nickname_entry.grab_focus()
        else:
            self.jid_escaped = False
            self.uid_entry.grab_focus()
        group_names = []
        for acct in accounts:
            for g in gajim.groups[acct].keys():
                if g not in helpers.special_groups and g not in group_names:
                    group_names.append(g)
        group_names.sort()
        i = 0
        for g in group_names:
            self.group_comboboxentry.append_text(g)
            if group == g:
                self.group_comboboxentry.set_active(i)
            i += 1

        self.window.set_transient_for(gajim.interface.roster.window)
        self.window.show_all()

        if self.account:
            self.account_label.hide()
            self.account_hbox.hide()
        else:
            liststore = Gtk.ListStore(str, str)
            for acct in accounts:
                liststore.append([acct, acct])
            self.account_combobox.set_model(liststore)
            self.account_combobox.set_active(0)

        if self.account:
            message_buffer = self.message_textview.get_buffer()
            msg = helpers.from_one_line(helpers.get_subscription_request_msg(
                self.account))
            message_buffer.set_text(msg)

        gajim.ged.register_event_handler('gateway-prompt-received', ged.GUI1,
            self._nec_gateway_prompt_received)
        gajim.ged.register_event_handler('presence-received', ged.GUI1,
            self._nec_presence_received)

    def on_add_new_contact_window_destroy(self, widget):
        if self.account:
            location = gajim.interface.instances[self.account]
        else:
            location = gajim.interface.instances
        del location['add_contact']
        gajim.ged.remove_event_handler('presence-received', ged.GUI1,
            self._nec_presence_received)
        gajim.ged.remove_event_handler('gateway-prompt-received', ged.GUI1,
            self._nec_gateway_prompt_received)

    def on_register_button_clicked(self, widget):
        model = self.protocol_jid_combobox.get_model()
        row = self.protocol_jid_combobox.get_active()
        jid = model[row][0]
        gajim.connections[self.account].request_register_agent_info(jid)

    def on_add_new_contact_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape: # ESCAPE
            self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        """
        When Cancel button is clicked
        """
        self.window.destroy()

    def on_add_button_clicked(self, widget):
        """
        When Subscribe button is clicked
        """
        jid = self.uid_entry.get_text().strip()
        if not jid:
            return

        model = self.protocol_combobox.get_model()
        row = self.protocol_combobox.get_active_iter()
        type_ = model[row][2]
        if type_ != 'jabber':
            model = self.protocol_jid_combobox.get_model()
            row = self.protocol_jid_combobox.get_active()
            transport = model[row][0]
            if self.account and not self.jid_escaped:
                self.adding_jid = (jid, transport, type_)
                gajim.connections[self.account].request_gateway_prompt(
                    transport, jid)
            else:
                jid = jid.replace('@', '%') + '@' + transport
                self._add_jid(jid, type_)
        else:
            self._add_jid(jid, type_)

    def _add_jid(self, jid, type_):
        # check if jid is conform to RFC and stringprep it
        try:
            jid = helpers.parse_jid(jid)
        except helpers.InvalidFormat as s:
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, str(s))
            return

        # No resource in jid
        if jid.find('/') >= 0:
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, _('The user ID must not contain a resource.'))
            return

        if jid == gajim.get_jid_from_account(self.account):
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, _('You cannot add yourself to your roster.'))
            return

        nickname = self.nickname_entry.get_text() or ''
        # get value of account combobox, if account was not specified
        if not self.account:
            model = self.account_combobox.get_model()
            index = self.account_combobox.get_active()
            self.account = model[index][1]

        # Check if jid is already in roster
        if jid in gajim.contacts.get_jid_list(self.account):
            c = gajim.contacts.get_first_contact_from_jid(self.account, jid)
            if _('Not in Roster') not in c.groups and c.sub in ('both', 'to'):
                ErrorDialog(_('Contact already in roster'),
                    _('This contact is already listed in your roster.'))
                return

        if type_ == 'jabber':
            message_buffer = self.message_textview.get_buffer()
            start_iter = message_buffer.get_start_iter()
            end_iter = message_buffer.get_end_iter()
            message = message_buffer.get_text(start_iter, end_iter, True)
            if self.save_message_checkbutton.get_active():
                msg = helpers.to_one_line(message)
                gajim.config.set_per('accounts', self.account,
                    'subscription_request_msg', msg)
        else:
            message= ''
        group = self.group_comboboxentry.get_child().get_text()
        groups = []
        if group:
            groups = [group]
        auto_auth = self.auto_authorize_checkbutton.get_active()
        gajim.interface.roster.req_sub(self, jid, message, self.account,
            groups=groups, nickname=nickname, auto_auth=auto_auth)
        self.window.destroy()

    def on_account_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        account = model[iter_][0]
        message_buffer = self.message_textview.get_buffer()
        message_buffer.set_text(helpers.get_subscription_request_msg(account))

    def on_protocol_jid_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        if not iter_:
            return
        jid_ = model[iter_][0]
        model = self.protocol_combobox.get_model()
        iter_ = self.protocol_combobox.get_active_iter()
        type_ = model[iter_][2]
        desc = None
        if self.agents[type_] and jid_ in self.gateway_prompt:
            desc = self.gateway_prompt[jid_]['desc']
        if not desc:
            desc = self.default_desc
        self.xml.get_object('prompt_label').set_text(desc)

        prompt = None
        if self.agents[type_] and jid_ in self.gateway_prompt:
            prompt = self.gateway_prompt[jid_]['prompt']
        if not prompt:
            if type_ in self.uid_labels:
                prompt = self.uid_labels[type_]
            else:
                prompt = _('User ID:')
        self.uid_label.set_text(prompt)

    def on_protocol_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        type_ = model[iter_][2]
        model = self.protocol_jid_combobox.get_model()
        model.clear()
        if len(self.agents[type_]):
            for jid_ in self.agents[type_]:
                model.append([jid_])
            self.protocol_jid_combobox.set_active(0)
        desc = None
        if self.agents[type_]:
            jid_ = self.agents[type_][0]
            if jid_ in self.gateway_prompt:
                desc = self.gateway_prompt[jid_]['desc']
        if not desc:
            desc = self.default_desc
        self.xml.get_object('prompt_label').set_text(desc)
        if len(self.agents[type_]) > 1:
            self.protocol_jid_combobox.show()
        else:
            self.protocol_jid_combobox.hide()
        prompt = None
        if self.agents[type_]:
            jid_ = self.agents[type_][0]
            if jid_ in self.gateway_prompt:
                prompt = self.gateway_prompt[jid_]['prompt']
        if not prompt:
            if type_ in self.uid_labels:
                prompt = self.uid_labels[type_]
            else:
                prompt = _('User ID:')
        self.uid_label.set_text(prompt)

        if type_ == 'jabber':
            self.message_scrolledwindow.show()
            self.save_message_checkbutton.show()
        else:
            self.message_scrolledwindow.hide()
            self.save_message_checkbutton.hide()
        if type_ in self.available_types:
            self.register_hbox.show()
            self.auto_authorize_checkbutton.hide()
            self.connected_label.hide()
            self.subscription_table.hide()
            self.add_button.set_sensitive(False)
        else:
            self.register_hbox.hide()
            if type_ != 'jabber':
                model = self.protocol_jid_combobox.get_model()
                row = self.protocol_jid_combobox.get_active()
                jid = model[row][0]
                contact = gajim.contacts.get_first_contact_from_jid(
                    self.account, jid)
                if contact.show in ('offline', 'error'):
                    self.subscription_table.hide()
                    self.connected_label.show()
                    self.add_button.set_sensitive(False)
                    self.auto_authorize_checkbutton.hide()
                    return
            self.subscription_table.show()
            self.auto_authorize_checkbutton.show()
            self.connected_label.hide()
            self.add_button.set_sensitive(True)

    def transport_signed_in(self, jid):
        model = self.protocol_jid_combobox.get_model()
        row = self.protocol_jid_combobox.get_active()
        _jid = model[row][0]
        if _jid == jid:
            self.register_hbox.hide()
            self.connected_label.hide()
            self.subscription_table.show()
            self.auto_authorize_checkbutton.show()
            self.add_button.set_sensitive(True)

    def transport_signed_out(self, jid):
        model = self.protocol_jid_combobox.get_model()
        row = self.protocol_jid_combobox.get_active()
        _jid = model[row][0]
        if _jid == jid:
            self.subscription_table.hide()
            self.auto_authorize_checkbutton.hide()
            self.connected_label.show()
            self.add_button.set_sensitive(False)

    def _nec_presence_received(self, obj):
        if gajim.jid_is_transport(obj.jid):
            if obj.old_show == 0 and obj.new_show > 1:
                self.transport_signed_in(obj.jid)
            elif obj.old_show > 1 and obj.new_show == 0:
                self.transport_signed_out(obj.jid)

    def _nec_gateway_prompt_received(self, obj):
        if self.adding_jid:
            jid, transport, type_ = self.adding_jid
            if obj.prompt_jid:
                self._add_jid(obj.prompt_jid, type_)
            else:
                jid = jid.replace('@', '%') + '@' + transport
                self._add_jid(jid, type_)
        elif obj.jid in self.gateway_prompt:
            if obj.desc:
                self.gateway_prompt[obj.jid]['desc'] = obj.desc
            if obj.prompt:
                self.gateway_prompt[obj.jid]['prompt'] = obj.prompt

class AboutDialog:
    """
    Class for about dialog
    """

    def __init__(self):
        dlg = Gtk.AboutDialog()
        dlg.set_transient_for(gajim.interface.roster.window)
        dlg.set_name('Gajim')
        dlg.set_version(gajim.version)
        s = 'Copyright © 2003-2014 Gajim Team'
        dlg.set_copyright(s)
        copying_file_path = self.get_path('COPYING')
        if copying_file_path:
            with open(copying_file_path) as a_file:
                text = a_file.read()
            dlg.set_license(text)

        gtk_ver = '%i.%i.%i' % (Gtk.get_major_version(),
            Gtk.get_minor_version(), Gtk.get_micro_version())
        gobject_ver = self.tuple2str(GObject.pygobject_version)
        dlg.set_comments('%s\n%s %s\n%s %s' % (_('A GTK+ Jabber/XMPP client'),
            _('GTK+ Version:'), gtk_ver, _('PyGobject Version:'), gobject_ver))
        dlg.set_website('http://gajim.org/')

        authors_file_path = self.get_path('AUTHORS')
        if authors_file_path:
            authors = []
            with open(authors_file_path) as a_file:
                authors_file = a_file.read()
            authors_file = authors_file.split('\n')
            for author in authors_file:
                if author == 'CURRENT DEVELOPERS:':
                    authors.append(_('Current Developers:'))
                elif author == 'PAST DEVELOPERS:':
                    authors.append('\n' + _('Past Developers:'))
                elif author != '': # Real author line
                    authors.append(author)

            thanks_file_path = self.get_path('THANKS')
            if thanks_file_path:
                authors.append('\n' + _('THANKS:'))
                with open(thanks_file_path) as a_file:
                    text = a_file.read()
                text_splitted = text.split('\n')
                text = '\n'.join(text_splitted[:-2]) # remove one english sentence
                # and add it manually as translatable
                text += '\n%s\n' % _('Last but not least, we would like to '
                    'thank all the package maintainers.')
                authors.append(text)

            dlg.set_authors(authors)

        dlg.props.wrap_license = True

        pixbuf = gtkgui_helpers.get_icon_pixmap('gajim', 128)

        dlg.set_logo(pixbuf)
        #here you write your name in the form Name FamilyName <someone@somewhere>
        dlg.set_translator_credits(_('translator-credits'))

        thanks_artists_file_path = self.get_path('THANKS.artists')
        if thanks_artists_file_path:
            with open(thanks_artists_file_path) as a_file:
                artists_text = a_file.read()
            artists = artists_text.split('\n')
            dlg.set_artists(artists)

        dlg.connect('response', self.on_response)
        dlg.show_all()

    def on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.CANCEL:
            dialog.destroy()

    def tuple2str(self, tuple_):
        str_ = ''
        for num in tuple_:
            str_ += str(num) + '.'
        return str_[0:-1] # remove latest .

    def get_path(self, filename):
        """
        Where can we find this Credits file?
        """
        if os.path.isfile(os.path.join(gajim.defs.docdir, filename)):
            return os.path.join(gajim.defs.docdir, filename)
        elif os.path.isfile('../' + filename):
            return ('../' + filename)
        else:
            return None

class Dialog(Gtk.Dialog):
    def __init__(self, parent, title, buttons, default=None,
    on_response_ok=None, on_response_cancel=None):
        GObject.GObject.__init__(self, title, parent,
            Gtk.DialogFlags.DESTROY_WITH_PARENT | Gtk.DialogFlags.NO_SEPARATOR)

        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel
        self.set_border_width(6)
        self.vbox.set_spacing(12)
        self.set_resizable(False)

        for stock, response in buttons:
            b = self.add_button(stock, response)

        if default is not None:
            self.set_default_response(default)
        else:
            self.set_default_response(buttons[-1][1])

        self.connect('response', self.on_response)

    def on_response(self, widget, response_id):
        if response_id == Gtk.ResponseType.OK:
            if self.user_response_ok:
                if isinstance(self.user_response_ok, tuple):
                    self.user_response_ok[0](*self.user_response_ok[1:])
                else:
                    self.user_response_ok()
            self.destroy()
        elif response_id == Gtk.ResponseType.CANCEL:
            if self.user_response_cancel:
                if isinstance(self.user_response_cancel, tuple):
                    self.user_response_cancel[0](*self.user_response_ok[1:])
                else:
                    self.user_response_cancel()
            self.destroy()

    def just_destroy(self, widget):
        self.destroy()

    def get_button(self, index):
        buttons = self.action_area.get_children()
        return index < len(buttons) and buttons[index] or None


class HigDialog(Gtk.MessageDialog):
    def __init__(self, parent, type_, buttons, pritext, sectext,
    on_response_ok=None, on_response_cancel=None, on_response_yes=None,
    on_response_no=None):
        self.call_cancel_on_destroy = True
        Gtk.MessageDialog.__init__(self, parent,
           Gtk.DialogFlags.DESTROY_WITH_PARENT | Gtk.DialogFlags.MODAL,
           type_, buttons, message_format = pritext)

        self.format_secondary_markup(sectext)

        buttons = self.action_area.get_children()
        self.possible_responses = {Gtk.ResponseType.OK: on_response_ok,
            Gtk.ResponseType.CANCEL: on_response_cancel,
            Gtk.ResponseType.YES: on_response_yes,
            Gtk.ResponseType.NO: on_response_no}

        self.connect('response', self.on_response)
        self.connect('destroy', self.on_dialog_destroy)

    def on_response(self, dialog, response_id):
        if not response_id in self.possible_responses:
            return
        if not self.possible_responses[response_id]:
            self.destroy()
        elif isinstance(self.possible_responses[response_id], tuple):
            if len(self.possible_responses[response_id]) == 1:
                self.possible_responses[response_id][0](dialog)
            else:
                self.possible_responses[response_id][0](dialog,
                    *self.possible_responses[response_id][1:])
        else:
            self.possible_responses[response_id](dialog)


    def on_dialog_destroy(self, widget):
        if not self.call_cancel_on_destroy:
            return
        cancel_handler = self.possible_responses[Gtk.ResponseType.CANCEL]
        if not cancel_handler:
            return False
        if isinstance(cancel_handler, tuple):
            cancel_handler[0](None, *cancel_handler[1:])
        else:
            cancel_handler(None)

    def popup(self):
        """
        Show dialog
        """
        vb = self.get_children()[0].get_children()[0] # Give focus to top vbox
#        vb.set_flags(Gtk.CAN_FOCUS)
        vb.grab_focus()
        self.show_all()

class FileChooserDialog(Gtk.FileChooserDialog):
    """
    Non-blocking FileChooser Dialog around Gtk.FileChooserDialog
    """
    def __init__(self, title_text, action, buttons, default_response,
    select_multiple=False, current_folder=None, on_response_ok=None,
    on_response_cancel=None, transient_for=None):

        GObject.GObject.__init__(self, title=title_text, parent=transient_for,
            action=action)
        self.add_button(buttons[0],buttons[1])
        if len(buttons) ==4:
            self.add_button(buttons[2],buttons[3])
        self.set_default_response(default_response)
        self.set_select_multiple(select_multiple)
        if current_folder and os.path.isdir(current_folder):
            self.set_current_folder(current_folder)
        else:
            self.set_current_folder(helpers.get_documents_path())
        self.response_ok, self.response_cancel = \
                on_response_ok, on_response_cancel
        # in gtk+-2.10 clicked signal on some of the buttons in a dialog
        # is emitted twice, so we cannot rely on 'clicked' signal
        self.connect('response', self.on_dialog_response)
        self.show_all()

    def on_dialog_response(self, dialog, response):
        if response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.CLOSE):
            if self.response_cancel:
                if isinstance(self.response_cancel, tuple):
                    self.response_cancel[0](dialog, *self.response_cancel[1:])
                else:
                    self.response_cancel(dialog)
            else:
                self.just_destroy(dialog)
        elif response == Gtk.ResponseType.OK:
            if self.response_ok:
                if isinstance(self.response_ok, tuple):
                    self.response_ok[0](dialog, *self.response_ok[1:])
                else:
                    self.response_ok(dialog)
            else:
                self.just_destroy(dialog)

    def just_destroy(self, widget):
        self.destroy()

class AspellDictError:
    def __init__(self, lang):
        ErrorDialog(
            _('Dictionary for lang %s not available') % lang,
            _('You have to install %s dictionary to use spellchecking, or '
            'choose another language by setting the speller_language option.'
            '\n\nHighlighting misspelled words feature will not be used') % lang)
        gajim.config.set('use_speller', False)

class ConfirmationDialog(HigDialog):
    """
    HIG compliant confirmation dialog
    """

    def __init__(self, pritext, sectext='', on_response_ok=None,
    on_response_cancel=None, transient_for=None):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel
        HigDialog.__init__(self, transient_for,
           Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, pritext, sectext,
           self.on_response_ok, self.on_response_cancel)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](*self.user_response_ok[1:])
            else:
                self.user_response_ok()
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_ok[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()

class NonModalConfirmationDialog(HigDialog):
    """
    HIG compliant non modal confirmation dialog
    """

    def __init__(self, pritext, sectext='', on_response_ok=None,
    on_response_cancel=None):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel
        if hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
            self.on_response_cancel)
        self.set_modal(False)

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](*self.user_response_ok[1:])
            else:
                self.user_response_ok()
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_cancel[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()

class WarningDialog(HigDialog):
    """
    HIG compliant warning dialog
    """

    def __init__(self, pritext, sectext='', transient_for=None):
        if not transient_for and hasattr(gajim.interface, 'roster') and \
        gajim.interface.roster:
            transient_for = gajim.interface.roster.window
        HigDialog.__init__(self, transient_for, Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK, pritext, sectext)
        self.set_modal(False)
        self.popup()

class InformationDialog(HigDialog):
    """
    HIG compliant info dialog
    """

    def __init__(self, pritext, sectext='', transient_for=None):
        if transient_for:
            parent = transient_for
        elif hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
            pritext, sectext)
        self.set_modal(False)
        self.popup()

class ErrorDialog(HigDialog):
    """
    HIG compliant error dialog
    """

    def __init__(self, pritext, sectext='', on_response_ok=None,
    on_response_cancel=None, transient_for=None):
        if transient_for:
            parent = transient_for
        elif hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK,
            pritext, sectext, on_response_ok=on_response_ok,
            on_response_cancel=on_response_cancel)
        self.popup()

class YesNoDialog(HigDialog):
    """
    HIG compliant YesNo dialog
    """

    def __init__(self, pritext, sectext='', checktext='', text_label=None,
    on_response_yes=None, on_response_no=None, type_=Gtk.MessageType.QUESTION,
    transient_for=None):
        self.user_response_yes = on_response_yes
        self.user_response_no = on_response_no
        if transient_for:
            parent = transient_for
        elif hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, type_, Gtk.ButtonsType.YES_NO, pritext,
            sectext, on_response_yes=self.on_response_yes,
            on_response_no=self.on_response_no)

        if checktext:
            self.checkbutton = Gtk.CheckButton(checktext)
            self.vbox.pack_start(self.checkbutton, False, True, 0)
        else:
            self.checkbutton = None
        if text_label:
            label = Gtk.Label(label=text_label)
            self.vbox.pack_start(label, False, True, 0)
            buff = Gtk.TextBuffer()
            self.textview = Gtk.TextView.new_with_buffer(buff)
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.IN)
            frame.add(self.textview)
            self.vbox.pack_start(frame, False, True, 0)
        else:
            self.textview = None
        self.set_modal(False)
        self.popup()

    def on_response_yes(self, widget):
        if self.user_response_yes:
            if self.textview:
                buff = self.textview.get_buffer()
                start, end = buff.get_bounds()
                txt = self.textview.get_buffer().get_text(start, end, True)

            if isinstance(self.user_response_yes, tuple):
                if self.textview:
                    self.user_response_yes[0](self.is_checked(), txt,
                        *self.user_response_yes[1:])
                else:
                    self.user_response_yes[0](self.is_checked(),
                        *self.user_response_yes[1:])
            else:
                if self.textview:
                    self.user_response_yes(self.is_checked(), txt)
                else:
                    self.user_response_yes(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_no(self, widget):
        if self.user_response_no:
            if self.textview:
                buff = self.textview.get_buffer()
                start, end = buff.get_bounds()
                txt = self.textview.get_buffer().get_text(start, end, True)

            if isinstance(self.user_response_no, tuple):
                if self.textview:
                    self.user_response_no[0](txt, *self.user_response_no[1:])
                else:
                    self.user_response_no[0](*self.user_response_no[1:])
            else:
                if self.textview:
                    self.user_response_no(txt)
                else:
                    self.user_response_no()
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        """
        Get active state of the checkbutton
        """
        if not self.checkbutton:
            return False
        return self.checkbutton.get_active()

class ConfirmationDialogCheck(ConfirmationDialog):
    """
    HIG compliant confirmation dialog with checkbutton
    """

    def __init__(self, pritext, sectext='', checktext='', on_response_ok=None,
    on_response_cancel=None, is_modal=True, transient_for=None):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel

        if transient_for:
            parent = transient_for
        elif hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, Gtk.MessageType.QUESTION,
           Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
           self.on_response_cancel)

        self.set_default_response(Gtk.ResponseType.OK)

        ok_button = self.action_area.get_children()[0] # right to left
        ok_button.grab_focus()

        self.checkbutton = Gtk.CheckButton(checktext)
        self.vbox.pack_start(self.checkbutton, False, True, 0)
        self.set_modal(is_modal)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](self.is_checked(),
                    *self.user_response_ok[1:])
            else:
                self.user_response_ok(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](self.is_checked(),
                    *self.user_response_cancel[1:])
            else:
                self.user_response_cancel(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        """
        Get active state of the checkbutton
        """
        return self.checkbutton.get_active()

class ConfirmationDialogDoubleCheck(ConfirmationDialog):
    """
    HIG compliant confirmation dialog with 2 checkbuttons
    """

    def __init__(self, pritext, sectext='', checktext1='', checktext2='',
    tooltip1='', tooltip2='', on_response_ok=None, on_response_cancel=None,
    is_modal=True):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel

        if hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, Gtk.MessageType.QUESTION,
           Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
           self.on_response_cancel)

        self.set_default_response(Gtk.ResponseType.OK)

        ok_button = self.action_area.get_children()[0] # right to left
        ok_button.grab_focus()

        if checktext1:
            self.checkbutton1 = Gtk.CheckButton(checktext1)
            if tooltip1:
                self.checkbutton1.set_tooltip_text(tooltip1)
            self.vbox.pack_start(self.checkbutton1, False, True, 0)
        else:
            self.checkbutton1 = None
        if checktext2:
            self.checkbutton2 = Gtk.CheckButton(checktext2)
            if tooltip2:
                self.checkbutton2.set_tooltip_text(tooltip2)
            self.vbox.pack_start(self.checkbutton2, False, True, 0)
        else:
            self.checkbutton2 = None

        self.set_modal(is_modal)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](self.is_checked(),
                    *self.user_response_ok[1:])
            else:
                self.user_response_ok(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_cancel[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        ''' Get active state of the checkbutton '''
        if self.checkbutton1:
            is_checked_1 = self.checkbutton1.get_active()
        else:
            is_checked_1 = False
        if self.checkbutton2:
            is_checked_2 = self.checkbutton2.get_active()
        else:
            is_checked_2 = False
        return [is_checked_1, is_checked_2]

class PlainConnectionDialog(ConfirmationDialogDoubleCheck):
    """
    Dialog that is shown when using an insecure connection
    """
    def __init__(self, account, on_ok, on_cancel):
        pritext = _('Insecure connection')
        sectext = _('You are about to connect to the account %(account)s '
            '(%(server)s) with an insecure connection. This means all your '
            'conversations will be exchanged unencrypted. This type of '
            'connection is really discouraged.\nAre you sure you want to do '
            'that?') % {'account': account,
            'server': gajim.get_hostname_from_account(account)}
        checktext1 = _('Yes, I really want to connect insecurely')
        tooltip1 = _('Gajim will NOT connect unless you check this box')
        checktext2 = _('_Do not ask me again')
        ConfirmationDialogDoubleCheck.__init__(self, pritext, sectext,
            checktext1, checktext2, tooltip1=tooltip1, on_response_ok=on_ok,
            on_response_cancel=on_cancel, is_modal=False)
        self.ok_button = self.action_area.get_children()[0] # right to left
        self.ok_button.set_sensitive(False)
        self.checkbutton1.connect('clicked', self.on_checkbutton_clicked)
        self.set_title(_('Insecure connection'))

    def on_checkbutton_clicked(self, widget):
        self.ok_button.set_sensitive(widget.get_active())

class ConfirmationDialogDoubleRadio(ConfirmationDialog):
    """
    HIG compliant confirmation dialog with 2 radios
    """

    def __init__(self, pritext, sectext='', radiotext1='', radiotext2='',
    on_response_ok=None, on_response_cancel=None, is_modal=True):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel

        if hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, Gtk.MessageType.QUESTION,
                Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
                self.on_response_cancel)

        self.set_default_response(Gtk.ResponseType.OK)

        ok_button = self.action_area.get_children()[0] # right to left
        ok_button.grab_focus()

        self.radiobutton1 = Gtk.RadioButton(label=radiotext1)
        self.vbox.pack_start(self.radiobutton1, False, True, 0)

        self.radiobutton2 = Gtk.RadioButton(group=self.radiobutton1,
                label=radiotext2)
        self.vbox.pack_start(self.radiobutton2, False, True, 0)

        self.set_modal(is_modal)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](self.is_checked(),
                        *self.user_response_ok[1:])
            else:
                self.user_response_ok(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_cancel[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        ''' Get active state of the checkbutton '''
        if self.radiobutton1:
            is_checked_1 = self.radiobutton1.get_active()
        else:
            is_checked_1 = False
        if self.radiobutton2:
            is_checked_2 = self.radiobutton2.get_active()
        else:
            is_checked_2 = False
        return [is_checked_1, is_checked_2]

class FTOverwriteConfirmationDialog(ConfirmationDialog):
    """
    HIG compliant confirmation dialog to overwrite or resume a file transfert
    """

    def __init__(self, pritext, sectext='', propose_resume=True,
    on_response=None, transient_for=None):
        if transient_for:
            parent = transient_for
        elif hasattr(gajim.interface, 'roster') and gajim.interface.roster:
            parent = gajim.interface.roster.window
        else:
            parent = None
        HigDialog.__init__(self, parent, Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.CANCEL, pritext, sectext)

        self.on_response = on_response

        if propose_resume:
            b = Gtk.Button('', Gtk.STOCK_REFRESH)
            align = b.get_children()[0]
            hbox = align.get_children()[0]
            label = hbox.get_children()[1]
            label.set_text(_('_Resume'))
            label.set_use_underline(True)
            self.add_action_widget(b, 100)

        b = Gtk.Button('', Gtk.STOCK_SAVE_AS)
        align = b.get_children()[0]
        hbox = align.get_children()[0]
        label = hbox.get_children()[1]
        label.set_text(_('Re_place'))
        label.set_use_underline(True)
        self.add_action_widget(b, 200)

        self.connect('response', self.on_dialog_response)
        self.show_all()

    def on_dialog_response(self, dialog, response):
        if self.on_response:
            if isinstance(self.on_response, tuple):
                self.on_response[0](response, *self.on_response[1:])
            else:
                self.on_response(response)
        self.call_cancel_on_destroy = False
        self.destroy()

class CommonInputDialog:
    """
    Common Class for Input dialogs
    """

    def __init__(self, title, label_str, is_modal, ok_handler, cancel_handler,
    transient_for=None):
        self.dialog = self.xml.get_object('input_dialog')
        label = self.xml.get_object('label')
        self.dialog.set_title(title)
        label.set_markup(label_str)
        self.cancel_handler = cancel_handler
        self.vbox = self.xml.get_object('vbox')
        if transient_for:
            self.dialog.set_transient_for(transient_for)

        self.ok_handler = ok_handler
        okbutton = self.xml.get_object('okbutton')
        okbutton.connect('clicked', self.on_okbutton_clicked)
        cancelbutton = self.xml.get_object('cancelbutton')
        cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
        self.xml.connect_signals(self)
        self.dialog.show_all()

    def on_input_dialog_destroy(self, widget):
        if self.cancel_handler:
            self.cancel_handler()

    def on_okbutton_clicked(self, widget):
        user_input = self.get_text()
        if user_input:
            user_input = user_input
        self.cancel_handler = None
        self.dialog.destroy()
        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](user_input, *self.ok_handler[1:])
        else:
            self.ok_handler(user_input)

    def on_cancelbutton_clicked(self, widget):
        self.dialog.destroy()

    def destroy(self):
        self.dialog.destroy()

class InputDialog(CommonInputDialog):
    """
    Class for Input dialog
    """

    def __init__(self, title, label_str, input_str=None, is_modal=True,
    ok_handler=None, cancel_handler=None, transient_for=None):
        self.xml = gtkgui_helpers.get_gtk_builder('input_dialog.ui')
        CommonInputDialog.__init__(self, title, label_str, is_modal, ok_handler,
            cancel_handler, transient_for=transient_for)
        self.input_entry = self.xml.get_object('input_entry')
        if input_str:
            self.set_entry(input_str)

    def on_input_dialog_delete_event(self, widget, event):
        '''
        may be implemented by subclasses
        '''
        pass

    def set_entry(self, value):
        self.input_entry.set_text(value)
        self.input_entry.select_region(0, -1) # select all

    def get_text(self):
        return self.input_entry.get_text()

class InputDialogCheck(InputDialog):
    """
    Class for Input dialog
    """

    def __init__(self, title, label_str, checktext='', input_str=None,
                    is_modal=True, ok_handler=None, cancel_handler=None):
        self.xml = gtkgui_helpers.get_gtk_builder('input_dialog.ui')
        InputDialog.__init__(self, title, label_str, input_str=input_str,
                is_modal=is_modal, ok_handler=ok_handler,
                cancel_handler=cancel_handler)
        self.input_entry = self.xml.get_object('input_entry')
        if input_str:
            self.input_entry.set_text(input_str)
            self.input_entry.select_region(0, -1) # select all

        if checktext:
            self.checkbutton = Gtk.CheckButton(checktext)
            self.vbox.pack_start(self.checkbutton, False, True, 0)
            self.checkbutton.show()

    def on_okbutton_clicked(self, widget):
        user_input = self.get_text()
        if user_input:
            user_input = user_input
        self.cancel_handler = None
        self.dialog.destroy()
        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](user_input, self.is_checked(), *self.ok_handler[1:])
        else:
            self.ok_handler(user_input, self.is_checked())

    def get_text(self):
        return self.input_entry.get_text()

    def is_checked(self):
        """
        Get active state of the checkbutton
        """
        try:
            return self.checkbutton.get_active()
        except Exception:
            # There is no checkbutton
            return False

class ChangeNickDialog(InputDialogCheck):
    """
    Class for changing room nickname in case of conflict
    """

    def __init__(self, account, room_jid, title, prompt, check_text=None,
    change_nick=False):
        """
        change_nick must be set to True when we are already occupant of the room
        and we are changing our nick
        """
        InputDialogCheck.__init__(self, title, '', checktext=check_text,
            input_str='', is_modal=True, ok_handler=None, cancel_handler=None)
        self.room_queue = [(account, room_jid, prompt, change_nick)]
        self.check_next()

    def on_input_dialog_delete_event(self, widget, event):
        self.on_cancelbutton_clicked(widget)
        return True

    def setup_dialog(self):
        self.gc_control = gajim.interface.msg_win_mgr.get_gc_control(
                self.room_jid, self.account)
        if not self.gc_control and \
        self.room_jid in gajim.interface.minimized_controls[self.account]:
            self.gc_control = \
                gajim.interface.minimized_controls[self.account][self.room_jid]
        if not self.gc_control:
            self.check_next()
            return
        label = self.xml.get_object('label')
        label.set_markup(self.prompt)
        self.set_entry(self.gc_control.nick + \
                gajim.config.get('gc_proposed_nick_char'))

    def check_next(self):
        if len(self.room_queue) == 0:
            self.cancel_handler = None
            self.dialog.destroy()
            if 'change_nick_dialog' in gajim.interface.instances:
                del gajim.interface.instances['change_nick_dialog']
            return
        self.account, self.room_jid, self.prompt, self.change_nick = \
            self.room_queue.pop(0)
        self.setup_dialog()

        if gajim.new_room_nick is not None and not gajim.gc_connected[
        self.account][self.room_jid] and self.gc_control.nick != \
        gajim.new_room_nick:
            self.dialog.hide()
            self.on_ok(gajim.new_room_nick, True)
        else:
            self.dialog.show()

    def on_okbutton_clicked(self, widget):
        nick = self.get_text()
        if nick:
            nick = nick
        # send presence to room
        try:
            nick = helpers.parse_resource(nick)
        except Exception:
            # invalid char
            ErrorDialog(_('Invalid nickname'),
                    _('The nickname contains invalid characters.'))
            return
        self.on_ok(nick, self.is_checked())

    def on_ok(self, nick, is_checked):
        if is_checked:
            gajim.new_room_nick = nick
        gajim.connections[self.account].join_gc(nick, self.room_jid, None,
            change_nick=self.change_nick)
        if gajim.gc_connected[self.account][self.room_jid]:
            # We are changing nick, we will change self.nick when we receive
            # presence that inform that it works
            self.gc_control.new_nick = nick
        else:
            # We are connecting, we will not get a changed nick presence so
            # change it NOW. We don't already have a nick so it's harmless
            self.gc_control.nick = nick
        self.check_next()

    def on_cancelbutton_clicked(self, widget):
        self.gc_control.new_nick = ''
        self.check_next()

    def add_room(self, account, room_jid, prompt, change_nick=False):
        if (account, room_jid, prompt, change_nick) not in self.room_queue:
            self.room_queue.append((account, room_jid, prompt, change_nick))

class InputTextDialog(CommonInputDialog):
    """
    Class for multilines Input dialog (more place than InputDialog)
    """

    def __init__(self, title, label_str, input_str=None, is_modal=True,
                             ok_handler=None, cancel_handler=None):
        self.xml = gtkgui_helpers.get_gtk_builder('input_text_dialog.ui')
        CommonInputDialog.__init__(self, title, label_str, is_modal, ok_handler,
                                                           cancel_handler)
        self.input_buffer = self.xml.get_object('input_textview').get_buffer()
        if input_str:
            self.input_buffer.set_text(input_str)
            start_iter, end_iter = self.input_buffer.get_bounds()
            self.input_buffer.select_range(start_iter, end_iter) # select all

    def get_text(self):
        start_iter, end_iter = self.input_buffer.get_bounds()
        return self.input_buffer.get_text(start_iter, end_iter, True)

class DoubleInputDialog:
    """
    Class for Double Input dialog
    """

    def __init__(self, title, label_str1, label_str2, input_str1=None,
    input_str2=None, is_modal=True, ok_handler=None, cancel_handler=None,
    transient_for=None):
        self.xml = gtkgui_helpers.get_gtk_builder('dubbleinput_dialog.ui')
        self.dialog = self.xml.get_object('dubbleinput_dialog')
        label1 = self.xml.get_object('label1')
        self.input_entry1 = self.xml.get_object('input_entry1')
        label2 = self.xml.get_object('label2')
        self.input_entry2 = self.xml.get_object('input_entry2')
        self.dialog.set_title(title)
        label1.set_markup(label_str1)
        label2.set_markup(label_str2)
        self.cancel_handler = cancel_handler
        if input_str1:
            self.input_entry1.set_text(input_str1)
            self.input_entry1.select_region(0, -1) # select all
        if input_str2:
            self.input_entry2.set_text(input_str2)
            self.input_entry2.select_region(0, -1) # select all
        if transient_for:
            self.dialog.set_transient_for(transient_for)

        self.dialog.set_modal(is_modal)

        self.ok_handler = ok_handler
        okbutton = self.xml.get_object('okbutton')
        okbutton.connect('clicked', self.on_okbutton_clicked)
        cancelbutton = self.xml.get_object('cancelbutton')
        cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
        self.xml.connect_signals(self)
        self.dialog.show_all()

    def on_dubbleinput_dialog_destroy(self, widget):
        if not self.cancel_handler:
            return False
        if isinstance(self.cancel_handler, tuple):
            self.cancel_handler[0](*self.cancel_handler[1:])
        else:
            self.cancel_handler()

    def on_okbutton_clicked(self, widget):
        user_input1 = self.input_entry1.get_text()
        user_input2 = self.input_entry2.get_text()
        self.cancel_handler = None
        self.dialog.destroy()
        if not self.ok_handler:
            return
        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](user_input1, user_input2, *self.ok_handler[1:])
        else:
            self.ok_handler(user_input1, user_input2)

    def on_cancelbutton_clicked(self, widget):
        self.dialog.destroy()
        if not self.cancel_handler:
            return
        if isinstance(self.cancel_handler, tuple):
            self.cancel_handler[0](*self.cancel_handler[1:])
        else:
            self.cancel_handler()

class SubscriptionRequestWindow:
    def __init__(self, jid, text, account, user_nick=None):
        xml = gtkgui_helpers.get_gtk_builder('subscription_request_window.ui')
        self.window = xml.get_object('subscription_request_window')
        self.jid = jid
        self.account = account
        self.user_nick = user_nick
        if len(gajim.connections) >= 2:
            prompt_text = \
                _('Subscription request for account %(account)s from %(jid)s')\
                % {'account': account, 'jid': self.jid}
        else:
            prompt_text = _('Subscription request from %s') % self.jid
        xml.get_object('from_label').set_text(prompt_text)
        xml.get_object('message_textview').get_buffer().set_text(text)
        xml.connect_signals(self)
        self.window.show_all()

    def on_subscription_request_window_destroy(self, widget):
        """
        Close window
        """
        if self.jid in gajim.interface.instances[self.account]['sub_request']:
            # remove us from open windows
            del gajim.interface.instances[self.account]['sub_request'][self.jid]

    def prepare_popup_menu(self):
        xml = gtkgui_helpers.get_gtk_builder('subscription_request_popup_menu.ui')
        menu = xml.get_object('subscription_request_popup_menu')
        xml.connect_signals(self)
        return menu

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_authorize_button_clicked(self, widget):
        """
        Accept the request
        """
        gajim.connections[self.account].send_authorization(self.jid)
        self.window.destroy()
        contact = gajim.contacts.get_contact(self.account, self.jid)
        if not contact or _('Not in Roster') in contact.groups:
            AddNewContactWindow(self.account, self.jid, self.user_nick)

    def on_contact_info_activate(self, widget):
        """
        Ask vcard
        """
        if self.jid in gajim.interface.instances[self.account]['infos']:
            gajim.interface.instances[self.account]['infos'][self.jid].window.present()
        else:
            contact = gajim.contacts.create_contact(jid=self.jid, account=self.account)
            gajim.interface.instances[self.account]['infos'][self.jid] = \
                     vcard.VcardWindow(contact, self.account)
            # Remove jabber page
            gajim.interface.instances[self.account]['infos'][self.jid].xml.\
                     get_object('information_notebook').remove_page(0)

    def on_start_chat_activate(self, widget):
        """
        Open chat
        """
        gajim.interface.new_chat_from_jid(self.account, self.jid)

    def on_deny_button_clicked(self, widget):
        """
        Refuse the request
        """
        gajim.connections[self.account].refuse_authorization(self.jid)
        contact = gajim.contacts.get_contact(self.account, self.jid)
        if contact and _('Not in Roster') in contact.get_shown_groups():
            gajim.interface.roster.remove_contact(self.jid, self.account)
        self.window.destroy()

    def on_actions_button_clicked(self, widget):
        """
        Popup action menu
        """
        menu = self.prepare_popup_menu()
        menu.show_all()
        gtkgui_helpers.popup_emoticons_under_button(menu, widget,
            self.window.get_window())


class JoinGroupchatWindow:
    def __init__(self, account=None, room_jid='', nick='', password='',
    automatic=False):
        """
        Automatic is a dict like {'invities': []}. If automatic is not empty,
        this means room must be automaticaly configured and when done, invities
        must be automatically invited
        """
        if account:
            if room_jid != '' and room_jid in gajim.gc_connected[account] and \
            gajim.gc_connected[account][room_jid]:
                ErrorDialog(_('You are already in group chat %s') % room_jid)
                raise GajimGeneralException('You are already in this group chat')
            if nick == '':
                nick = gajim.nicks[account]
            if gajim.connections[account].connected < 2:
                ErrorDialog(_('You are not connected to the server'),
                    _('You can not join a group chat unless you are connected.'))
                raise GajimGeneralException('You must be connected to join a groupchat')

        self.xml = gtkgui_helpers.get_gtk_builder('join_groupchat_window.ui')

        account_label = self.xml.get_object('account_label')
        account_combobox = self.xml.get_object('account_combobox')
        account_label.set_no_show_all(False)
        account_combobox.set_no_show_all(False)
        liststore = Gtk.ListStore(str)
        account_combobox.set_model(liststore)
        cell = Gtk.CellRendererText()
        account_combobox.pack_start(cell, True)
        account_combobox.add_attribute(cell, 'text', 0)
        account_combobox.set_active(-1)

        # Add accounts, set current as active if it matches 'account'
        for acct in [a for a in gajim.connections if \
        gajim.account_is_connected(a)]:
            if gajim.connections[acct].is_zeroconf:
                continue
            liststore.append([acct])
            if account and account == acct:
                account_combobox.set_active(liststore.iter_n_children(None)-1)

        self.account = account
        self.automatic = automatic
        self._empty_required_widgets = []

        self.window = self.xml.get_object('join_groupchat_window')
        self.window.set_transient_for(gajim.interface.roster.window)
        self._room_jid_entry = self.xml.get_object('room_jid_entry')
        self._nickname_entry = self.xml.get_object('nickname_entry')
        self._password_entry = self.xml.get_object('password_entry')

        self._nickname_entry.set_text(nick)
        if password:
            self._password_entry.set_text(password)
        self.xml.connect_signals(self)
        title = None
        if account:
            # now add us to open windows
            gajim.interface.instances[account]['join_gc'] = self
            if len(gajim.connections) > 1:
                title = _('Join Group Chat with account %s') % account
        if title is None:
            title = _('Join Group Chat')
        self.window.set_title(title)


        self.server_model = Gtk.ListStore(str)
        self.server_comboboxentry = Gtk.ComboBox.new_with_model_and_entry(
            self.server_model)
        self.server_comboboxentry.set_entry_text_column(0)
        hbox1 = self.xml.get_object('hbox1')
        hbox1.pack_start(self.server_comboboxentry, False, False, 0)

        entry = self.server_comboboxentry.child
        entry.connect('changed', self.on_server_entry_changed)
        self.browse_button = self.xml.get_object('browse_rooms_button')
        self.browse_button.set_sensitive(False)

        self.recently_combobox = self.xml.get_object('recently_combobox')
        liststore = Gtk.ListStore(str, str)
        self.recently_combobox.set_model(liststore)
        cell = Gtk.CellRendererText()
        self.recently_combobox.pack_start(cell, True)
        self.recently_combobox.add_attribute(cell, 'text', 0)
        self.recently_groupchat = gajim.config.get('recently_groupchat').split()

        server_list = []
        # get the muc server of our server
        if 'jabber' in gajim.connections[account].muc_jid:
            server_list.append(gajim.connections[account].muc_jid['jabber'])
        for g in self.recently_groupchat:
            r_jid = gajim.get_jid_without_resource(g)
            nick = gajim.get_resource_from_jid(g)
            if nick:
                show = '%(nick)s on %(room_jid)s' % {'nick': nick,
                    'room_jid': r_jid}
            else:
                show = r_jid
            liststore.append([show, g])
            server = gajim.get_server_from_jid(r_jid)
            if server not in server_list and not server.startswith('irc'):
                server_list.append(server)

        for s in server_list:
            self.server_model.append([s])


        self._set_room_jid(room_jid)

        if len(self.recently_groupchat) == 0:
            self.recently_combobox.set_sensitive(False)
        elif room_jid == '':
            self.recently_combobox.set_active(0)
            self._room_jid_entry.select_region(0, -1)
        elif room_jid != '':
            self.xml.get_object('join_button').grab_focus()

        if not self._room_jid_entry.get_text():
            self._empty_required_widgets.append(self._room_jid_entry)
        if not self._nickname_entry.get_text():
            self._empty_required_widgets.append(self._nickname_entry)
        if len(self._empty_required_widgets):
            self.xml.get_object('join_button').set_sensitive(False)

        if account and not gajim.connections[account].private_storage_supported:
            self.xml.get_object('bookmark_checkbutton').set_sensitive(False)

        self.requested_jid = None
        gajim.ged.register_event_handler('agent-info-received', ged.GUI1,
            self._nec_agent_info_received)
        gajim.ged.register_event_handler('agent-info-error-received', ged.GUI1,
            self._nec_agent_info_error_received)

        self.window.show_all()

    def on_join_groupchat_window_destroy(self, widget):
        """
        Close window
        """
        gajim.ged.remove_event_handler('agent-info-received', ged.GUI1,
            self._nec_agent_info_received)
        gajim.ged.register_event_handler('agent-info-error-received', ged.GUI1,
            self._nec_agent_info_error_received)
        if self.account and 'join_gc' in gajim.interface.instances[self.account]:
            # remove us from open windows
            del gajim.interface.instances[self.account]['join_gc']

    def on_join_groupchat_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape: # ESCAPE
            widget.destroy()

    def on_required_entry_changed(self, widget):
        if not widget.get_text():
            self._empty_required_widgets.append(widget)
            self.xml.get_object('join_button').set_sensitive(False)
        else:
            if widget in self._empty_required_widgets:
                self._empty_required_widgets.remove(widget)
            if not self._empty_required_widgets and self.account:
                self.xml.get_object('join_button').set_sensitive(True)
            text = self._room_jid_entry.get_text()
            if widget == self._room_jid_entry and '@' in text:
                # Don't allow @ char in room entry
                room_jid, server = text.split('@', 1)
                self._room_jid_entry.set_text(room_jid)
                if server:
                    self.server_comboboxentry.get_child().set_text(server)
                self.server_comboboxentry.grab_focus()

    def on_account_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        self.account = model[iter_][0]
        self.on_required_entry_changed(self._nickname_entry)

    def _set_room_jid(self, full_jid):
        room_jid, nick = gajim.get_room_and_nick_from_fjid(full_jid)
        room, server = gajim.get_name_and_server_from_jid(room_jid)
        self._room_jid_entry.set_text(room)
        model = self.server_comboboxentry.get_model()
        self.server_comboboxentry.get_child().set_text(server)
        if nick:
            self._nickname_entry.set_text(nick)

    def on_recently_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        full_jid = model[iter_][1]
        self._set_room_jid(full_jid)

    def on_browse_rooms_button_clicked(self, widget):
        server = self.server_comboboxentry.get_child().get_text()
        self.requested_jid = server
        gajim.connections[self.account].discoverInfo(server)

    def _nec_agent_info_error_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.jid != self.requested_jid:
            return
        self.requested_jid = None
        window = gajim.interface.instances[self.account]['join_gc'].window
        ErrorDialog(_('Wrong server'), _('%s is not a groupchat server') % \
            obj.jid, transient_for=window)

    def _nec_agent_info_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.jid != self.requested_jid:
            return
        self.requested_jid = None
        if nbxmpp.NS_MUC not in obj.features:
            window = gajim.interface.instances[self.account]['join_gc'].window
            ErrorDialog(_('Wrong server'), _('%s is not a groupchat server') % \
                obj.jid, transient_for=window)
            return
        if obj.jid in gajim.interface.instances[self.account]['disco']:
            gajim.interface.instances[self.account]['disco'][obj.jid].window.\
                present()
        else:
            try:
                # Object will add itself to the window dict
                import disco
                disco.ServiceDiscoveryWindow(self.account, obj.jid,
                    initial_identities=[{'category': 'conference',
                    'type': 'text'}])
            except GajimGeneralException:
                pass

    def on_server_entry_changed(self, widget):
        if not widget.get_text():
            self.browse_button.set_sensitive(False)
        else:
            self.browse_button.set_sensitive(True)

    def on_cancel_button_clicked(self, widget):
        """
        When Cancel button is clicked
        """
        self.window.destroy()

    def on_bookmark_checkbutton_toggled(self, widget):
        auto_join_checkbutton = self.xml.get_object('auto_join_checkbutton')
        if widget.get_active():
            auto_join_checkbutton.set_sensitive(True)
        else:
            auto_join_checkbutton.set_sensitive(False)

    def on_join_button_clicked(self, widget):
        """
        When Join button is clicked
        """
        if not self.account:
            ErrorDialog(_('Invalid Account'),
                _('You have to choose an account from which you want to join the '
                'groupchat.'))
            return
        nickname = self._nickname_entry.get_text()
        server = self.server_comboboxentry.get_child().get_text()
        room = self._room_jid_entry.get_text().strip()
        room_jid = room + '@' + server
        password = self._password_entry.get_text()
        try:
            nickname = helpers.parse_resource(nickname)
        except Exception:
            ErrorDialog(_('Invalid Nickname'),
                    _('The nickname contains invalid characters.'))
            return
        user, server, resource = helpers.decompose_jid(room_jid)
        if not user or not server or resource:
            ErrorDialog(_('Invalid group chat Jabber ID'),
                    _('Please enter the group chat Jabber ID as room@server.'))
            return
        try:
            room_jid = helpers.parse_jid(room_jid)
        except Exception:
            ErrorDialog(_('Invalid group chat Jabber ID'),
                    _('The group chat Jabber ID contains invalid characters.'))
            return

        if gajim.contacts.get_contact(self.account, room_jid) and \
        not gajim.contacts.get_contact(self.account, room_jid).is_groupchat():
            ErrorDialog(_('This is not a group chat'),
                _('%s is not the name of a group chat.') % room_jid)
            return

        full_jid = room_jid + '/' + nickname
        if full_jid in self.recently_groupchat:
            self.recently_groupchat.remove(full_jid)
        self.recently_groupchat.insert(0, full_jid)
        if len(self.recently_groupchat) > 10:
            self.recently_groupchat = self.recently_groupchat[0:10]
        gajim.config.set('recently_groupchat',
            ' '.join(self.recently_groupchat))

        if self.xml.get_object('bookmark_checkbutton').get_active():
            if self.xml.get_object('auto_join_checkbutton').get_active():
                autojoin = '1'
            else:
                autojoin = '0'
            # Add as bookmark, with autojoin and not minimized
            name = gajim.get_nick_from_jid(room_jid)
            gajim.interface.add_gc_bookmark(self.account, name, room_jid,
                autojoin, '0', password, nickname)

        if self.automatic:
            gajim.automatic_rooms[self.account][room_jid] = self.automatic

        gajim.interface.join_gc_room(self.account, room_jid, nickname, password)

        self.window.destroy()

class SynchroniseSelectAccountDialog:
    def __init__(self, account):
        # 'account' can be None if we are about to create our first one
        if not account or gajim.connections[account].connected < 2:
            ErrorDialog(_('You are not connected to the server'),
                _('Without a connection, you can not synchronise your contacts.'))
            raise GajimGeneralException('You are not connected to the server')
        self.account = account
        self.xml = gtkgui_helpers.get_gtk_builder('synchronise_select_account_dialog.ui')
        self.dialog = self.xml.get_object('synchronise_select_account_dialog')
        self.dialog.set_transient_for(gajim.interface.instances['accounts'].window)
        self.accounts_treeview = self.xml.get_object('accounts_treeview')
        model = Gtk.ListStore(str, str, bool)
        self.accounts_treeview.set_model(model)
        # columns
        renderer = Gtk.CellRendererText()
        self.accounts_treeview.insert_column_with_attributes(-1, _('Name'),
            renderer, text=0)
        renderer = Gtk.CellRendererText()
        self.accounts_treeview.insert_column_with_attributes(-1, _('Server'),
            renderer, text=1)

        self.xml.connect_signals(self)
        self.init_accounts()
        self.dialog.show_all()

    def on_accounts_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def init_accounts(self):
        """
        Initialize listStore with existing accounts
        """
        model = self.accounts_treeview.get_model()
        model.clear()
        for remote_account in gajim.connections:
            if remote_account == self.account:
                # Do not show the account we're sync'ing
                continue
            iter_ = model.append()
            model.set(iter_, 0, remote_account, 1,
                gajim.get_hostname_from_account(remote_account))

    def on_cancel_button_clicked(self, widget):
        self.dialog.destroy()

    def on_ok_button_clicked(self, widget):
        sel = self.accounts_treeview.get_selection()
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        remote_account = model.get_value(iter_, 0)

        if gajim.connections[remote_account].connected < 2:
            ErrorDialog(_('This account is not connected to the server'),
                _('You cannot synchronize with an account unless it is connected.'))
            return
        else:
            try:
                SynchroniseSelectContactsDialog(self.account, remote_account)
            except GajimGeneralException:
                # if we showed ErrorDialog, there will not be dialog instance
                return
        self.dialog.destroy()

class SynchroniseSelectContactsDialog:
    def __init__(self, account, remote_account):
        self.local_account = account
        self.remote_account = remote_account
        self.xml = gtkgui_helpers.get_gtk_builder(
            'synchronise_select_contacts_dialog.ui')
        self.dialog = self.xml.get_object('synchronise_select_contacts_dialog')
        self.contacts_treeview = self.xml.get_object('contacts_treeview')
        model = Gtk.ListStore(bool, str)
        self.contacts_treeview.set_model(model)
        # columns
        renderer1 = Gtk.CellRendererToggle()
        renderer1.set_property('activatable', True)
        renderer1.connect('toggled', self.toggled_callback)
        self.contacts_treeview.insert_column_with_attributes(-1,
            _('Synchronise'), renderer1, active=0)
        renderer2 = Gtk.CellRendererText()
        self.contacts_treeview.insert_column_with_attributes(-1, _('Name'),
            renderer2, text=1)

        self.xml.connect_signals(self)
        self.init_contacts()
        self.dialog.show_all()

    def toggled_callback(self, cell, path):
        model = self.contacts_treeview.get_model()
        iter_ = model.get_iter(path)
        model[iter_][0] = not cell.get_active()

    def on_contacts_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def init_contacts(self):
        """
        Initialize listStore with existing accounts
        """
        model = self.contacts_treeview.get_model()
        model.clear()

        # recover local contacts
        local_jid_list = gajim.contacts.get_contacts_jid_list(self.local_account)

        remote_jid_list = gajim.contacts.get_contacts_jid_list(
                self.remote_account)
        for remote_jid in remote_jid_list:
            if remote_jid not in local_jid_list:
                iter_ = model.append()
                model.set(iter_, 0, True, 1, remote_jid)

    def on_cancel_button_clicked(self, widget):
        self.dialog.destroy()

    def on_ok_button_clicked(self, widget):
        model = self.contacts_treeview.get_model()
        iter_ = model.get_iter_first()
        while iter_:
            if model[iter_][0]:
                # it is selected
                remote_jid = model[iter_][1]
                message = 'I\'m synchronizing my contacts from my %s account, could you please add this address to your contact list?' % \
                    gajim.get_hostname_from_account(self.remote_account)
                remote_contact = gajim.contacts.get_first_contact_from_jid(
                        self.remote_account, remote_jid)
                # keep same groups and same nickname
                gajim.interface.roster.req_sub(self, remote_jid, message,
                    self.local_account, groups = remote_contact.groups,
                    nickname = remote_contact.name, auto_auth = True)
            iter_ = model.iter_next(iter_)
        self.dialog.destroy()

class NewChatDialog(InputDialog):
    def __init__(self, account):
        self.account = account

        if len(gajim.connections) > 1:
            title = _('Start Chat with account %s') % account
        else:
            title = _('Start Chat')
        prompt_text = _('Fill in the nickname or the Jabber ID of the contact you would like\nto send a chat message to:')
        InputDialog.__init__(self, title, prompt_text, is_modal=False)
        self.input_entry.set_placeholder_text(_('Nickname / Jabber ID'))

        self.completion_dict = {}
        liststore = gtkgui_helpers.get_completion_liststore(self.input_entry)
        self.completion_dict = helpers.get_contact_dict_for_account(account)
        # add all contacts to the model
        keys = sorted(self.completion_dict.keys())
        for jid in keys:
            contact = self.completion_dict[jid]
            img = gajim.interface.jabber_state_images['16'][contact.show]
            liststore.append((img.get_pixbuf(), jid))

        self.ok_handler = self.new_chat_response
        okbutton = self.xml.get_object('okbutton')
        okbutton.connect('clicked', self.on_okbutton_clicked)
        cancelbutton = self.xml.get_object('cancelbutton')
        cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
        self.dialog.set_transient_for(gajim.interface.roster.window)
        self.dialog.show_all()

    def new_chat_response(self, jid):
        """
        Called when ok button is clicked
        """
        if gajim.connections[self.account].connected <= 1:
            #if offline or connecting
            ErrorDialog(_('Connection not available'),
                _('Please make sure you are connected with "%s".') % self.account)
            return

        if jid in self.completion_dict:
            jid = self.completion_dict[jid].jid
        else:
            try:
                jid = helpers.parse_jid(jid)
            except helpers.InvalidFormat as e:
                ErrorDialog(_('Invalid JID'), str(e))
                return
            except:
                ErrorDialog(_('Invalid JID'), _('Unable to parse "%s".') % jid)
                return
        gajim.interface.new_chat_from_jid(self.account, jid)

class ChangePasswordDialog:
    def __init__(self, account, on_response, transient_for=None):
        # 'account' can be None if we are about to create our first one
        if not account or gajim.connections[account].connected < 2:
            ErrorDialog(_('You are not connected to the server'),
                _('Without a connection, you can not change your password.'))
            raise GajimGeneralException('You are not connected to the server')
        self.account = account
        self.on_response = on_response
        self.xml = gtkgui_helpers.get_gtk_builder('change_password_dialog.ui')
        self.dialog = self.xml.get_object('change_password_dialog')
        self.dialog.set_transient_for(transient_for)
        self.password1_entry = self.xml.get_object('password1_entry')
        self.password2_entry = self.xml.get_object('password2_entry')
        self.dialog.connect('response', self.on_dialog_response)

        self.dialog.show_all()

    def on_dialog_response(self, dialog, response):
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            self.on_response(None)
            return
        password1 = self.password1_entry.get_text()
        if not password1:
            ErrorDialog(_('Invalid password'), _('You must enter a password.'))
            return
        password2 = self.password2_entry.get_text()
        if password1 != password2:
            ErrorDialog(_('Passwords do not match'),
                _('The passwords typed in both fields must be identical.'))
            return
        dialog.destroy()
        self.on_response(password1)

class PopupNotificationWindow:
    def __init__(self, event_type, jid, account, msg_type='',
    path_to_image=None, title=None, text=None, timeout=-1):
        self.account = account
        self.jid = jid
        self.msg_type = msg_type
        self.index = len(gajim.interface.roster.popup_notification_windows)

        xml = gtkgui_helpers.get_gtk_builder('popup_notification_window.ui')
        self.window = xml.get_object('popup_notification_window')
        self.window.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)
        close_button = xml.get_object('close_button')
        event_type_label = xml.get_object('event_type_label')
        event_description_label = xml.get_object('event_description_label')
        eventbox = xml.get_object('eventbox')
        image = xml.get_object('notification_image')

        if not text:
            text = gajim.get_name_from_jid(account, jid) # default value of text
        if not title:
            title = ''

        event_type_label.set_markup(
            '<span foreground="black" weight="bold">%s</span>' %
            GLib.markup_escape_text(title))

        # set colors [ http://www.pitt.edu/~nisg/cis/web/cgi/rgb.html ]
        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, 'black')
        self.window.override_background_color(Gtk.StateType.NORMAL, color)

        # default image
        if not path_to_image:
            path_to_image = gtkgui_helpers.get_icon_path('gajim-chat_msg_recv', 48)

        if event_type == _('Contact Signed In'):
            bg_color = gajim.config.get('notif_signin_color')
        elif event_type == _('Contact Signed Out'):
            bg_color = gajim.config.get('notif_signout_color')
        elif event_type in (_('New Message'), _('New Single Message'),
            _('New Private Message'), _('New E-mail')):
            bg_color = gajim.config.get('notif_message_color')
        elif event_type == _('File Transfer Request'):
            bg_color = gajim.config.get('notif_ftrequest_color')
        elif event_type == _('File Transfer Error'):
            bg_color = gajim.config.get('notif_fterror_color')
        elif event_type in (_('File Transfer Completed'),
        _('File Transfer Stopped')):
            bg_color = gajim.config.get('notif_ftcomplete_color')
        elif event_type == _('Groupchat Invitation'):
            bg_color = gajim.config.get('notif_invite_color')
        elif event_type == _('Contact Changed Status'):
            bg_color = gajim.config.get('notif_status_color')
        else: # Unknown event! Shouldn't happen but deal with it
            bg_color = gajim.config.get('notif_other_color')
        popup_bg_color = Gdk.RGBA()
        Gdk.RGBA.parse(popup_bg_color, bg_color)
        close_button.override_background_color(Gtk.StateType.NORMAL,
            popup_bg_color)
        eventbox.override_background_color(Gtk.StateType.NORMAL, popup_bg_color)
        event_description_label.set_markup('<span foreground="black">%s</span>' %
            GLib.markup_escape_text(text))

        # set the image
        image.set_from_file(path_to_image)

        # position the window to bottom-right of screen
        window_width, self.window_height = self.window.get_size()
        gajim.interface.roster.popups_notification_height += self.window_height
        pos_x = gajim.config.get('notification_position_x')
        if pos_x < 0:
            pos_x = Gdk.Screen.width() - window_width + pos_x + 1
        pos_y = gajim.config.get('notification_position_y')
        if pos_y < 0:
            pos_y = Gdk.Screen.height() - \
                gajim.interface.roster.popups_notification_height + pos_y + 1
        self.window.move(pos_x, pos_y)

        xml.connect_signals(self)
        self.window.show_all()
        if timeout > 0:
            GLib.timeout_add_seconds(timeout, self.on_timeout)

    def on_close_button_clicked(self, widget):
        self.adjust_height_and_move_popup_notification_windows()

    def on_timeout(self):
        self.adjust_height_and_move_popup_notification_windows()

    def adjust_height_and_move_popup_notification_windows(self):
        #remove
        gajim.interface.roster.popups_notification_height -= self.window_height
        self.window.destroy()

        if len(gajim.interface.roster.popup_notification_windows) > self.index:
            # we want to remove the destroyed window from the list
            gajim.interface.roster.popup_notification_windows.pop(self.index)

        # move the rest of popup windows
        gajim.interface.roster.popups_notification_height = 0
        current_index = 0
        for window_instance in gajim.interface.roster.popup_notification_windows:
            window_instance.index = current_index
            current_index += 1
            window_width, window_height = window_instance.window.get_size()
            gajim.interface.roster.popups_notification_height += window_height
            window_instance.window.move(Gdk.Screen.width() - window_width,
                Gdk.Screen.height() - \
                gajim.interface.roster.popups_notification_height)

    def on_popup_notification_window_button_press_event(self, widget, event):
        if event.button != 1:
            self.window.destroy()
            return
        gajim.interface.handle_event(self.account, self.jid, self.msg_type)
        self.adjust_height_and_move_popup_notification_windows()

class SingleMessageWindow:
    """
    SingleMessageWindow can send or show a received singled message depending on
    action argument which can be 'send' or 'receive'
    """
    # Keep a reference on windows so garbage collector don't restroy them
    instances = []
    def __init__(self, account, to='', action='', from_whom='', subject='',
            message='', resource='', session=None, form_node=None):
        self.instances.append(self)
        self.account = account
        self.action = action

        self.subject = subject
        self.message = message
        self.to = to
        self.from_whom = from_whom
        self.resource = resource
        self.session = session

        self.xml = gtkgui_helpers.get_gtk_builder('single_message_window.ui')
        self.window = self.xml.get_object('single_message_window')
        self.count_chars_label = self.xml.get_object('count_chars_label')
        self.from_label = self.xml.get_object('from_label')
        self.from_entry = self.xml.get_object('from_entry')
        self.to_label = self.xml.get_object('to_label')
        self.to_entry = self.xml.get_object('to_entry')
        self.subject_entry = self.xml.get_object('subject_entry')
        self.message_scrolledwindow = self.xml.get_object(
                'message_scrolledwindow')
        self.message_textview = self.xml.get_object('message_textview')
        self.message_tv_buffer = self.message_textview.get_buffer()
        self.conversation_scrolledwindow = self.xml.get_object(
                'conversation_scrolledwindow')
        self.conversation_textview = conversation_textview.ConversationTextview(
            account, used_in_history_window=True)
        self.conversation_textview.tv.show()
        self.conversation_tv_buffer = self.conversation_textview.tv.get_buffer()
        self.xml.get_object('conversation_scrolledwindow').add(
                self.conversation_textview.tv)

        self.form_widget = None
        parent_box = self.xml.get_object('conversation_scrolledwindow').\
                           get_parent()
        if form_node:
            dataform = dataforms.ExtendForm(node=form_node)
            self.form_widget = dataforms_widget.DataFormWidget(dataform)
            self.form_widget.show_all()
            parent_box.add(self.form_widget)
            parent_box.child_set_property(self.form_widget, 'position',
                parent_box.child_get_property(self.xml.get_object(
                'conversation_scrolledwindow'), 'position'))
            self.action = 'form'

        self.send_button = self.xml.get_object('send_button')
        self.reply_button = self.xml.get_object('reply_button')
        self.send_and_close_button = self.xml.get_object('send_and_close_button')
        self.cancel_button = self.xml.get_object('cancel_button')
        self.close_button = self.xml.get_object('close_button')
        self.message_tv_buffer.connect('changed', self.update_char_counter)
        if isinstance(to, list):
            jid = ', '.join( [i[0].get_full_jid() for i in to])
            self.to_entry.set_text(jid)
            self.to_entry.set_sensitive(False)
        else:
            self.to_entry.set_text(to)

        if gajim.config.get('use_speller') and HAS_GTK_SPELL and action == 'send':
            try:
                lang = gajim.config.get('speller_language')
                if not lang:
                    lang = gajim.LANG
                gtkspell.Spell(self.conversation_textview.tv, lang)
                gtkspell.Spell(self.message_textview, lang)
            except (GObject.GError, TypeError, RuntimeError, OSError):
                AspellDictError(lang)

        self.prepare_widgets_for(self.action)

        # set_text(None) raises TypeError exception
        if self.subject is None:
            self.subject = ''
        self.subject_entry.set_text(self.subject)


        if to == '':
            liststore = gtkgui_helpers.get_completion_liststore(self.to_entry)
            self.completion_dict = helpers.get_contact_dict_for_account(account)
            keys = sorted(self.completion_dict.keys())
            for jid in keys:
                contact = self.completion_dict[jid]
                img = gajim.interface.jabber_state_images['16'][contact.show]
                liststore.append((img.get_pixbuf(), jid))
        else:
            self.completion_dict = {}
        self.xml.connect_signals(self)

        # get window position and size from config
        gtkgui_helpers.resize_window(self.window,
            gajim.config.get('single-msg-width'),
            gajim.config.get('single-msg-height'))
        gtkgui_helpers.move_window(self.window,
            gajim.config.get('single-msg-x-position'),
            gajim.config.get('single-msg-y-position'))

        self.window.show_all()

    def on_single_message_window_destroy(self, widget):
        self.instances.remove(self)
        c = gajim.contacts.get_contact_with_highest_priority(self.account,
                self.from_whom)
        if not c:
            # Groupchat is maybe already destroyed
            return
        if c.is_groupchat() and not self.from_whom in \
        gajim.interface.minimized_controls[self.account] and self.action == \
        'receive' and gajim.events.get_nb_roster_events(self.account,
        self.from_whom, types=['chat', 'normal']) == 0:
            gajim.interface.roster.remove_groupchat(self.from_whom, self.account)

    def set_cursor_to_end(self):
        end_iter = self.message_tv_buffer.get_end_iter()
        self.message_tv_buffer.place_cursor(end_iter)

    def save_pos(self):
        # save the window size and position
        x, y = self.window.get_position()
        gajim.config.set('single-msg-x-position', x)
        gajim.config.set('single-msg-y-position', y)
        width, height = self.window.get_size()
        gajim.config.set('single-msg-width', width)
        gajim.config.set('single-msg-height', height)

    def on_single_message_window_delete_event(self, window, ev):
        self.save_pos()

    def prepare_widgets_for(self, action):
        if len(gajim.connections) > 1:
            if action == 'send':
                title = _('Single Message using account %s') % self.account
            else:
                title = _('Single Message in account %s') % self.account
        else:
            title = _('Single Message')

        if action == 'send': # prepare UI for Sending
            title = _('Send %s') % title
            self.send_button.show()
            self.send_and_close_button.show()
            self.to_label.show()
            self.to_entry.show()
            self.reply_button.hide()
            self.from_label.hide()
            self.from_entry.hide()
            self.conversation_scrolledwindow.hide()
            self.message_scrolledwindow.show()

            if self.message: # we come from a reply?
                self.message_textview.grab_focus()
                self.cancel_button.hide()
                self.close_button.show()
                self.message_tv_buffer.set_text(self.message)
                GLib.idle_add(self.set_cursor_to_end)
            else: # we write a new message (not from reply)
                self.close_button.hide()
                if self.to: # do we already have jid?
                    self.subject_entry.grab_focus()

        elif action == 'receive': # prepare UI for Receiving
            title = _('Received %s') % title
            self.reply_button.show()
            self.from_label.show()
            self.from_entry.show()
            self.send_button.hide()
            self.send_and_close_button.hide()
            self.to_label.hide()
            self.to_entry.hide()
            self.conversation_scrolledwindow.show()
            self.message_scrolledwindow.hide()

            if self.message:
                self.conversation_textview.print_real_text(self.message)
            fjid = self.from_whom
            if self.resource:
                fjid += '/' + self.resource # Full jid of sender (with resource)
            self.from_entry.set_text(fjid)
            self.from_entry.set_property('editable', False)
            self.subject_entry.set_property('editable', False)
            self.reply_button.grab_focus()
            self.cancel_button.hide()
            self.close_button.show()
        elif action == 'form': # prepare UI for Receiving
            title = _('Form %s') % title
            self.send_button.show()
            self.send_and_close_button.show()
            self.to_label.show()
            self.to_entry.show()
            self.reply_button.hide()
            self.from_label.hide()
            self.from_entry.hide()
            self.conversation_scrolledwindow.hide()
            self.message_scrolledwindow.hide()

        self.window.set_title(title)

    def on_cancel_button_clicked(self, widget):
        self.save_pos()
        self.window.destroy()

    def on_close_button_clicked(self, widget):
        self.save_pos()
        self.window.destroy()

    def update_char_counter(self, widget):
        characters_no = self.message_tv_buffer.get_char_count()
        self.count_chars_label.set_text(str(characters_no))

    def send_single_message(self):
        if gajim.connections[self.account].connected <= 1:
            # if offline or connecting
            ErrorDialog(_('Connection not available'),
                _('Please make sure you are connected with "%s".') % self.account)
            return True
        if isinstance(self.to, list):
            sender_list = []
            for i in self.to:
                if i[0].resource:
                    sender_list.append(i[0].jid + '/' + i[0].resource)
                else:
                    sender_list.append(i[0].jid)
        else:
            sender_list = [j.strip() for j in self.to_entry.get_text().split(
                ',')]

        subject = self.subject_entry.get_text()
        begin, end = self.message_tv_buffer.get_bounds()
        message = self.message_tv_buffer.get_text(begin, end, True)

        if self.form_widget:
            form_node = self.form_widget.data_form
        else:
            form_node = None

        recipient_list = []

        for to_whom_jid in sender_list:
            if to_whom_jid in self.completion_dict:
                to_whom_jid = self.completion_dict[to_whom_jid].jid
            try:
                to_whom_jid = helpers.parse_jid(to_whom_jid)
            except helpers.InvalidFormat:
                ErrorDialog(_('Invalid Jabber ID'),
                    _('It is not possible to send a message to %s, this JID is not '
                    'valid.') % to_whom_jid)
                return True

            if '/announce/' in to_whom_jid:
                gajim.connections[self.account].send_motd(to_whom_jid, subject,
                    message)
                continue

            recipient_list.append(to_whom_jid)

        gajim.nec.push_outgoing_event(MessageOutgoingEvent(None,
            account=self.account, jid=recipient_list, message=message,
            type_='normal', subject=subject, form_node=form_node))

        self.subject_entry.set_text('') # we sent ok, clear the subject
        self.message_tv_buffer.set_text('') # we sent ok, clear the textview

    def on_send_button_clicked(self, widget):
        self.send_single_message()

    def on_reply_button_clicked(self, widget):
        # we create a new blank window to send and we preset RE: and to jid
        self.subject = _('RE: %s') % self.subject
        self.message = _('%s wrote:\n') % self.from_whom + self.message
        # add > at the begining of each line
        self.message = self.message.replace('\n', '\n> ') + '\n\n'
        self.window.destroy()
        SingleMessageWindow(self.account, to=self.from_whom, action='send',
            from_whom=self.from_whom, subject=self.subject, message=self.message,
            session=self.session)

    def on_send_and_close_button_clicked(self, widget):
        if self.send_single_message():
            return
        self.save_pos()
        self.window.destroy()

    def on_single_message_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape: # ESCAPE
            self.save_pos()
            self.window.destroy()

class XMLConsoleWindow:
    def __init__(self, account):
        self.account = account

        self.xml = gtkgui_helpers.get_gtk_builder('xml_console_window.ui')
        self.window = self.xml.get_object('xml_console_window')
        self.input_textview = self.xml.get_object('input_textview')
        self.stanzas_log_textview = self.xml.get_object('stanzas_log_textview')
        self.input_tv_buffer = self.input_textview.get_buffer()
        buffer_ = self.stanzas_log_textview.get_buffer()
        end_iter = buffer_.get_end_iter()
        buffer_.create_mark('end', end_iter, False)

        self.tagIn = buffer_.create_tag('incoming')
        color = gajim.config.get('inmsgcolor')
        self.tagIn.set_property('foreground', color)
        self.tagInPresence = buffer_.create_tag('incoming_presence')
        self.tagInPresence.set_property('foreground', color)
        self.tagInMessage = buffer_.create_tag('incoming_message')
        self.tagInMessage.set_property('foreground', color)
        self.tagInIq = buffer_.create_tag('incoming_iq')
        self.tagInIq.set_property('foreground', color)

        self.tagOut = buffer_.create_tag('outgoing')
        color = gajim.config.get('outmsgcolor')
        self.tagOut.set_property('foreground', color)
        self.tagOutPresence = buffer_.create_tag('outgoing_presence')
        self.tagOutPresence.set_property('foreground', color)
        self.tagOutMessage = buffer_.create_tag('outgoing_message')
        self.tagOutMessage.set_property('foreground', color)
        self.tagOutIq = buffer_.create_tag('outgoing_iq')
        self.tagOutIq.set_property('foreground', color)
        buffer_.create_tag('') # Default tag

        self.enabled = True
        self.xml.get_object('enable_checkbutton').set_active(True)

        col = Gdk.RGBA()
        Gdk.RGBA.parse(col, color)
        self.input_textview.override_color(Gtk.StateType.NORMAL, col)

        if len(gajim.connections) > 1:
            title = _('XML Console for %s') % self.account
        else:
            title = _('XML Console')

        self.window.set_title(title)
        self.window.show_all()
        gajim.ged.register_event_handler('stanza-received', ged.GUI1,
            self._nec_stanza_received)
        gajim.ged.register_event_handler('stanza-sent', ged.GUI1,
            self._nec_stanza_sent)

        self.xml.connect_signals(self)

    def on_xml_console_window_destroy(self, widget):
        del gajim.interface.instances[self.account]['xml_console']
        gajim.ged.remove_event_handler('stanza-received', ged.GUI1,
            self._nec_stanza_received)
        gajim.ged.remove_event_handler('stanza-sent', ged.GUI1,
            self._nec_stanza_sent)

    def on_clear_button_clicked(self, widget):
        buffer_ = self.stanzas_log_textview.get_buffer()
        buffer_.set_text('')

    def on_enable_checkbutton_toggled(self, widget):
        self.enabled = widget.get_active()

    def on_in_stanza_checkbutton_toggled(self, widget):
        active = widget.get_active()
        self.tagIn.set_property('invisible', active)
        self.tagInPresence.set_property('invisible', active)
        self.tagInMessage.set_property('invisible', active)
        self.tagInIq.set_property('invisible', active)

    def on_presence_stanza_checkbutton_toggled(self, widget):
        active = widget.get_active()
        self.tagInPresence.set_property('invisible', active)
        self.tagOutPresence.set_property('invisible', active)

    def on_out_stanza_checkbutton_toggled(self, widget):
        active = widget.get_active()
        self.tagOut.set_property('invisible', active)
        self.tagOutPresence.set_property('invisible', active)
        self.tagOutMessage.set_property('invisible', active)
        self.tagOutIq.set_property('invisible', active)

    def on_message_stanza_checkbutton_toggled(self, widget):
        active = widget.get_active()
        self.tagInMessage.set_property('invisible', active)
        self.tagOutMessage.set_property('invisible', active)

    def on_iq_stanza_checkbutton_toggled(self, widget):
        active = widget.get_active()
        self.tagInIq.set_property('invisible', active)
        self.tagOutIq.set_property('invisible', active)

    def scroll_to_end(self, ):
        parent = self.stanzas_log_textview.get_parent()
        buffer_ = self.stanzas_log_textview.get_buffer()
        end_mark = buffer_.get_mark('end')
        if not end_mark:
            return False
        self.stanzas_log_textview.scroll_to_mark(end_mark, 0, True,     0, 1)
        adjustment = parent.get_hadjustment()
        adjustment.set_value(0)
        return False

    def print_stanza(self, stanza, kind):
        # kind must be 'incoming' or 'outgoing'
        if not self.enabled:
            return
        if not stanza:
            return

        buffer = self.stanzas_log_textview.get_buffer()
        at_the_end = False
        end_iter = buffer.get_end_iter()
        end_rect = self.stanzas_log_textview.get_iter_location(end_iter)
        visible_rect = self.stanzas_log_textview.get_visible_rect()
        if end_rect.y <= (visible_rect.y + visible_rect.height):
            at_the_end = True
        end_iter = buffer.get_end_iter()

        type_ = ''
        if stanza[1:9] == 'presence':
            type_ = 'presence'
        elif stanza[1:8] == 'message':
            type_ = 'message'
        elif stanza[1:3] == 'iq':
            type_ = 'iq'

        if type_:
            type_ = kind + '_'  + type_
        else:
            type_ = kind # 'incoming' or 'outgoing'

        if kind == 'incoming':
            buffer.insert_with_tags_by_name(end_iter, '<!-- In %s -->\n' % \
                time.strftime('%c'), type_)
        elif kind == 'outgoing':
            buffer.insert_with_tags_by_name(end_iter, '<!-- Out %s -->\n' % \
                time.strftime('%c'), type_)
        end_iter = buffer.get_end_iter()
        buffer.insert_with_tags_by_name(end_iter, stanza.replace('><', '>\n<') \
            + '\n\n', type_)
        if at_the_end:
            GLib.idle_add(self.scroll_to_end)

    def _nec_stanza_received(self, obj):
        if obj.conn.name != self.account:
            return
        self.print_stanza(obj.stanza_str, 'incoming')

    def _nec_stanza_sent(self, obj):
        if obj.conn.name != self.account:
            return
        self.print_stanza(obj.stanza_str, 'outgoing')

    def on_send_button_clicked(self, widget):
        if gajim.connections[self.account].connected <= 1:
            # if offline or connecting
            ErrorDialog(_('Connection not available'),
                _('Please make sure you are connected with "%s".') % \
                self.account)
            return
        begin_iter, end_iter = self.input_tv_buffer.get_bounds()
        stanza = self.input_tv_buffer.get_text(begin_iter, end_iter, True)
        if stanza:
            gajim.connections[self.account].send_stanza(stanza)
            self.input_tv_buffer.set_text('') # we sent ok, clear the textview

    def on_presence_button_clicked(self, widget):
        self.input_tv_buffer.set_text(
            '<presence><show></show><status></status><priority></priority>'
            '</presence>')

    def on_iq_button_clicked(self, widget):
        self.input_tv_buffer.set_text(
            '<iq to="" type=""><query xmlns=""></query></iq>')

    def on_message_button_clicked(self, widget):
        self.input_tv_buffer.set_text(
            '<message to="" type=""><body></body></message>')

    def on_expander_activate(self, widget):
        if not widget.get_expanded(): # it's the opposite!
            # it's expanded!!
            self.input_textview.grab_focus()

#Action that can be done with an incoming list of contacts
TRANSLATED_ACTION = {'add': _('add'), 'modify': _('modify'),
    'remove': _('remove')}
class RosterItemExchangeWindow:
    """
    Windows used when someone send you a exchange contact suggestion
    """

    def __init__(self, account, action, exchange_list, jid_from,
                    message_body=None):
        self.account = account
        self.action = action
        self.exchange_list = exchange_list
        self.message_body = message_body
        self.jid_from = jid_from

        show_dialog = False

        # Connect to gtk builder
        self.xml = gtkgui_helpers.get_gtk_builder(
            'roster_item_exchange_window.ui')
        self.window = self.xml.get_object('roster_item_exchange_window')

        # Add Widgets.
        for widget_to_add in ['accept_button_label', 'type_label',
        'body_scrolledwindow', 'body_textview', 'items_list_treeview']:
            self.__dict__[widget_to_add] = self.xml.get_object(widget_to_add)

        # Set labels
        # self.action can be 'add', 'modify' or 'remove'
        self.type_label.set_label(
            _('<b>%(jid)s</b> would like you to <b>%(action)s</b> some contacts '
            'in your roster.') % {'jid': jid_from,
            'action': TRANSLATED_ACTION[self.action]})
        if message_body:
            buffer_ = self.body_textview.get_buffer()
            buffer_.set_text(self.message_body)
        else:
            self.body_scrolledwindow.hide()
        # Treeview
        model = Gtk.ListStore(bool, str, str, str, str)
        self.items_list_treeview.set_model(model)
        # columns
        renderer1 = Gtk.CellRendererToggle()
        renderer1.set_property('activatable', True)
        renderer1.connect('toggled', self.toggled_callback)
        if self.action == 'add':
            title = _('Add')
        elif self.action == 'modify':
            title = _('Modify')
        elif self.action == 'delete':
            title = _('Delete')
        self.items_list_treeview.insert_column_with_attributes(-1, title,
            renderer1, active=0)
        renderer2 = Gtk.CellRendererText()
        self.items_list_treeview.insert_column_with_attributes(-1, _('Jabber ID'),
            renderer2, text=1)
        renderer3 = Gtk.CellRendererText()
        self.items_list_treeview.insert_column_with_attributes(-1, _('Name'),
            renderer3, text=2)
        renderer4 = Gtk.CellRendererText()
        self.items_list_treeview.insert_column_with_attributes(-1, _('Groups'),
            renderer4, text=3)

        # Init contacts
        model = self.items_list_treeview.get_model()
        model.clear()

        if action == 'add':
            for jid in self.exchange_list:
                groups = ''
                is_in_roster = True
                contact = gajim.contacts.get_contact_with_highest_priority(
                    self.account, jid)
                if not contact or _('Not in Roster') in contact.groups:
                    is_in_roster = False
                name = self.exchange_list[jid][0]
                num_list = len(self.exchange_list[jid][1])
                current = 0
                for group in self.exchange_list[jid][1]:
                    current += 1
                    if contact and not group in contact.groups:
                        is_in_roster = False
                    if current == num_list:
                        groups = groups + group
                    else:
                        groups = groups + group + ', '
                if not is_in_roster:
                    show_dialog = True
                    iter_ = model.append()
                    model.set(iter_, 0, True, 1, jid, 2, name, 3, groups)

            # Change label for accept_button to action name instead of 'OK'.
            self.accept_button_label.set_label(_('Add'))
        elif action == 'modify':
            for jid in self.exchange_list:
                groups = ''
                is_in_roster = True
                is_right = True
                contact = gajim.contacts.get_contact_with_highest_priority(
                    self.account, jid)
                name = self.exchange_list[jid][0]
                if not contact:
                    is_in_roster = False
                    is_right = False
                else:
                    if name != contact.name:
                        is_right = False
                num_list = len(self.exchange_list[jid][1])
                current = 0
                for group in self.exchange_list[jid][1]:
                    current += 1
                    if contact and not group in contact.groups:
                        is_right = False
                    if current == num_list:
                        groups = groups + group
                    else:
                        groups = groups + group + ', '
                if not is_right and is_in_roster:
                    show_dialog = True
                    iter_ = model.append()
                    model.set(iter_, 0, True, 1, jid, 2, name, 3, groups)

            # Change label for accept_button to action name instead of 'OK'.
            self.accept_button_label.set_label(_('Modify'))
        elif action == 'delete':
            for jid in self.exchange_list:
                groups = ''
                is_in_roster = True
                contact = gajim.contacts.get_contact_with_highest_priority(
                        self.account, jid)
                name = self.exchange_list[jid][0]
                if not contact:
                    is_in_roster = False
                num_list = len(self.exchange_list[jid][1])
                current = 0
                for group in self.exchange_list[jid][1]:
                    current += 1
                    if current == num_list:
                        groups = groups + group
                    else:
                        groups = groups + group + ', '
                if is_in_roster:
                    show_dialog = True
                    iter_ = model.append()
                    model.set(iter_, 0, True, 1, jid, 2, name, 3, groups)

            # Change label for accept_button to action name instead of 'OK'.
            self.accept_button_label.set_label(_('Delete'))

        if show_dialog:
            self.window.show_all()
            self.xml.connect_signals(self)

    def toggled_callback(self, cell, path):
        model = self.items_list_treeview.get_model()
        iter_ = model.get_iter(path)
        model[iter_][0] = not cell.get_active()

    def on_accept_button_clicked(self, widget):
        model = self.items_list_treeview.get_model()
        iter_ = model.get_iter_first()
        if self.action == 'add':
            a = 0
            while iter_:
                if model[iter_][0]:
                    a+=1
                    # it is selected
                    #remote_jid = model[iter_][1]
                    message = _('%s suggested me to add you in my roster.'
                            % self.jid_from)
                    # keep same groups and same nickname
                    groups = model[iter_][3].split(', ')
                    if groups == ['']:
                        groups = []
                    jid = model[iter_][1]
                    if gajim.jid_is_transport(self.jid_from):
                        gajim.connections[self.account].automatically_added.append(
                                jid)
                    gajim.interface.roster.req_sub(self, jid, message,
                            self.account, groups=groups, nickname=model[iter_][2],
                            auto_auth=True)
                iter_ = model.iter_next(iter_)
            InformationDialog(i18n.ngettext('Added %d contact',
                'Added %d contacts', a, a, a))
        elif self.action == 'modify':
            a = 0
            while iter_:
                if model[iter_][0]:
                    a+=1
                    # it is selected
                    jid = model[iter_][1]
                    # keep same groups and same nickname
                    groups = model[iter_][3].split(', ')
                    if groups == ['']:
                        groups = []
                    for u in gajim.contacts.get_contact(self.account, jid):
                        u.name = model[iter_][2]
                    gajim.connections[self.account].update_contact(jid,
                            model[iter_][2], groups)
                    self.draw_contact(jid, self.account)
                    # Update opened chat
                    ctrl = gajim.interface.msg_win_mgr.get_control(jid, self.account)
                    if ctrl:
                        ctrl.update_ui()
                        win = gajim.interface.msg_win_mgr.get_window(jid,
                                self.account)
                        win.redraw_tab(ctrl)
                        win.show_title()
                iter_ = model.iter_next(iter_)
        elif self.action == 'delete':
            a = 0
            while iter_:
                if model[iter_][0]:
                    a+=1
                    # it is selected
                    jid = model[iter_][1]
                    gajim.connections[self.account].unsubscribe(jid)
                    gajim.interface.roster.remove_contact(jid, self.account)
                    gajim.contacts.remove_jid(self.account, jid)
                iter_ = model.iter_next(iter_)
            InformationDialog(i18n.ngettext('Removed %d contact',
                'Removed %d contacts', a, a, a))
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()


class ItemArchivingPreferencesWindow:
    otr_name = ('approve', 'concede', 'forbid', 'oppose', 'prefer', 'require')
    otr_index = dict([(j, i) for i, j in enumerate(otr_name)])
    save_name = ('body', 'false', 'message', 'stream')
    save_index = dict([(j, i) for i, j in enumerate(save_name)])

    def __init__(self, account, item):
        self.account = account
        self.item = item
        if self.item and self.item != 'Default':
            self.item_config = gajim.connections[self.account].items[self.item]
        else:
            self.item_config = gajim.connections[self.account].default
        self.waiting = None

        # Connect to gtk builder
        self.xml = gtkgui_helpers.get_gtk_builder(
                'item_archiving_preferences_window.ui')
        self.window = self.xml.get_object('item_archiving_preferences_window')

        # Add Widgets
        for widget_to_add in ('jid_entry', 'expire_entry', 'otr_combobox',
        'save_combobox', 'cancel_button', 'ok_button', 'progressbar'):
            self.__dict__[widget_to_add] = self.xml.get_object(widget_to_add)

        if self.item:
            self.jid_entry.set_text(self.item)
        expire_value = self.item_config['expire'] or ''
        self.otr_combobox.set_active(self.otr_index[self.item_config['otr']])
        self.save_combobox.set_active(
                self.save_index[self.item_config['save']])
        self.expire_entry.set_text(expire_value)

        self.window.set_title(_('Archiving Preferences for %s') % self.account)

        self.window.show_all()
        self.progressbar.hide()
        self.xml.connect_signals(self)

    def update_progressbar(self):
        if self.waiting:
            self.progressbar.pulse()
            return True
        return False

    def on_otr_combobox_changed(self, widget):
        otr = self.otr_name[self.otr_combobox.get_active()]
        if otr == 'require':
            self.save_combobox.set_active(self.save_index['false'])

    def on_ok_button_clicked(self, widget):
        # Return directly if operation in progress
        if self.waiting:
            return

        item = self.jid_entry.get_text()
        otr = self.otr_name[self.otr_combobox.get_active()]
        save = self.save_name[self.save_combobox.get_active()]
        expire = self.expire_entry.get_text()

        if self.item != 'Default':
            try:
                item = helpers.parse_jid(item)
            except helpers.InvalidFormat as s:
                pritext = _('Invalid User ID')
                ErrorDialog(pritext, str(s))
                return

        if expire:
            try:
                if int(expire) < 0 or str(int(expire)) != expire:
                    raise ValueError
            except ValueError:
                pritext = _('Invalid expire value')
                sectext = _('Expire must be a valid positive integer.')
                ErrorDialog(pritext, sectext)
                return

        if not (item == self.item and expire == self.item_config['expire'] and
        otr == self.item_config['otr'] and save == self.item_config['save']):
            if not self.item or self.item == item:
                if self.item == 'Default':
                    self.waiting = 'default'
                    gajim.connections[self.account].set_default(
                        otr, save, expire)
                else:
                    self.waiting = 'item'
                    gajim.connections[self.account].append_or_update_item(
                        item, otr, save, expire)
            else:
                self.waiting = 'item'
                gajim.connections[self.account].append_or_update_item(
                    item, otr, save, expire)
                gajim.connections[self.account].remove_item(self.item)
            self.launch_progressbar()
        #self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def on_item_archiving_preferences_window_destroy(self, widget):
        if self.item:
            key_name = 'edit_item_archiving_preferences_%s' % self.item
        else:
            key_name = 'new_item_archiving_preferences'
        if key_name in gajim.interface.instances[self.account]:
            del gajim.interface.instances[self.account][key_name]

    def launch_progressbar(self):
        self.progressbar.show()
        self.update_progressbar_timeout_id = GLib.timeout_add(100,
            self.update_progressbar)

    def response_arrived(self, data):
        if self.waiting:
            self.window.destroy()

    def error_arrived(self, error):
        if self.waiting:
            self.waiting = None
            self.progressbar.hide()
            pritext = _('There is an error with the form')
            sectext = error
            ErrorDialog(pritext, sectext)


class ArchivingPreferencesWindow:
    auto_name = ('false', 'true')
    auto_index = dict([(j, i) for i, j in enumerate(auto_name)])
    method_foo_name = ('prefer', 'concede', 'forbid')
    method_foo_index = dict([(j, i) for i, j in enumerate(method_foo_name)])

    def __init__(self, account):
        self.account = account
        self.waiting = []

        # Connect to glade
        self.xml = gtkgui_helpers.get_gtk_builder(
            'archiving_preferences_window.ui')
        self.window = self.xml.get_object('archiving_preferences_window')

        # Add Widgets
        for widget_to_add in ('auto_combobox', 'method_auto_combobox',
        'method_local_combobox', 'method_manual_combobox', 'close_button',
        'item_treeview', 'item_notebook', 'otr_combobox', 'save_combobox',
        'expire_entry', 'remove_button', 'edit_button'):
            self.__dict__[widget_to_add] = self.xml.get_object(widget_to_add)

        self.auto_combobox.set_active(
            self.auto_index[gajim.connections[self.account].auto])
        self.method_auto_combobox.set_active(
            self.method_foo_index[gajim.connections[self.account].method_auto])
        self.method_local_combobox.set_active(
            self.method_foo_index[gajim.connections[self.account].method_local])
        self.method_manual_combobox.set_active(
            self.method_foo_index[gajim.connections[self.account].\
                method_manual])

        model = Gtk.ListStore(str, str, str, str)
        self.item_treeview.set_model(model)
        col = Gtk.TreeViewColumn('jid')
        self.item_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True, True, 0)
        col.set_attributes(renderer, text=0)

        col = Gtk.TreeViewColumn('expire')
        col.pack_start(renderer, True, True, 0)
        col.set_attributes(renderer, text=1)
        self.item_treeview.append_column(col)

        col = Gtk.TreeViewColumn('otr')
        col.pack_start(renderer, True, True, 0)
        col.set_attributes(renderer, text=2)
        self.item_treeview.append_column(col)

        col = Gtk.TreeViewColumn('save')
        col.pack_start(renderer, True, True, 0)
        col.set_attributes(renderer, text=3)
        self.item_treeview.append_column(col)

        self.fill_items()

        self.current_item = None

        def sort_items(model, iter1, iter2, data=None):
            item1 = model.get_value(iter1, 0)
            item2 = model.get_value(iter2, 0)
            if item1 == 'Default':
                return -1
            if item2 == 'Default':
                return 1
            if '@' in item1:
                if '@' not in item2:
                    return 1
            elif '@' in item2:
                return -1
            if item1 < item2:
                return -1
            if item1 > item2:
                return 1
            # item1 == item2 ? WTF?
            return 0

        model.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        model.set_sort_func(0, sort_items)

        self.remove_button.set_sensitive(False)
        self.edit_button.set_sensitive(False)

        self.window.set_title(_('Archiving Preferences for %s') % self.account)

        gajim.ged.register_event_handler(
            'archiving-preferences-changed-received', ged.GUI1,
            self._nec_archiving_changed_received)
        gajim.ged.register_event_handler('archiving-error-received', ged.GUI1,
            self._nec_archiving_error)

        self.window.show_all()

        self.xml.connect_signals(self)

    def on_add_item_button_clicked(self, widget):
        key_name = 'new_item_archiving_preferences'
        if key_name in gajim.interface.instances[self.account]:
            gajim.interface.instances[self.account][key_name].window.present()
        else:
            gajim.interface.instances[self.account][key_name] = \
                ItemArchivingPreferencesWindow(self.account, '')

    def on_remove_item_button_clicked(self, widget):
        if not self.current_item:
            return

        self.waiting.append('itemremove')
        sel = self.item_treeview.get_selection()
        (model, iter_) = sel.get_selected()
        gajim.connections[self.account].remove_item(model[iter_][0])
        model.remove(iter_)
        self.remove_button.set_sensitive(False)
        self.edit_button.set_sensitive(False)

    def on_edit_item_button_clicked(self, widget):
        if not self.current_item:
            return

        key_name = 'edit_item_archiving_preferences_%s' % self.current_item
        if key_name in gajim.interface.instances[self.account]:
            gajim.interface.instances[self.account][key_name].window.present()
        else:
            gajim.interface.instances[self.account][key_name] = \
                ItemArchivingPreferencesWindow(self.account, self.current_item)

    def on_item_treeview_cursor_changed(self, widget):
        sel = self.item_treeview.get_selection()
        (model, iter_) = sel.get_selected()
        item = None
        if iter_:
            item = model[iter_][0]
        if self.current_item and self.current_item == item:
            return

        self.current_item = item
        if self.current_item == 'Default':
            self.remove_button.set_sensitive(False)
            self.edit_button.set_sensitive(True)
        elif self.current_item:
            self.remove_button.set_sensitive(True)
            self.edit_button.set_sensitive(True)
        else:
            self.remove_button.set_sensitive(False)
            self.edit_button.set_sensitive(False)

    def on_auto_combobox_changed(self, widget):
        save = self.auto_name[widget.get_active()]
        gajim.connections[self.account].set_auto(save)

    def on_method_foo_combobox_changed(self, widget):
        # We retrieve method type from widget name
        # ('foo' in 'method_foo_combobox')
        method_type = widget.name.split('_')[1]
        use = self.method_foo_name[widget.get_active()]
        self.waiting.append('method_%s' % method_type)
        gajim.connections[self.account].set_method(method_type, use)

    def get_child_window(self):
        edit_key_name = 'edit_item_archiving_preferences_%s' % self.current_item
        new_key_name = 'new_item_archiving_preferences'

        if edit_key_name in gajim.interface.instances[self.account]:
            return gajim.interface.instances[self.account][edit_key_name]

        if new_key_name in gajim.interface.instances[self.account]:
            return gajim.interface.instances[self.account][new_key_name]

    def _nec_archiving_changed_received(self, obj):
        if obj.conn.name != self.account:
            return
        for key in ('auto', 'method_auto', 'method_local', 'method_manual'):
            if key in obj.conf and key in self.waiting:
                self.waiting.remove(key)
        if 'default' in obj.conf:
            key_name = 'edit_item_archiving_preferences_%s' % \
                self.current_item
            if key_name in gajim.interface.instances[self.account]:
                gajim.interface.instances[self.account][key_name].\
                    response_arrived(obj.conf['default'])
            self.fill_items(True)
        for jid, pref in obj.new_items.items():
            child = self.get_child_window()
            if child:
                is_new = not child.item
                child.response_arrived(pref)
                if is_new:
                    model = self.item_treeview.get_model()
                    model.append((jid, pref['expire'], pref['otr'],
                        pref['save']))
                    continue
            self.fill_items(True)
        if 'itemremove' in self.waiting and obj.removed_items:
            self.waiting.remove('itemremove')
            self.fill_items(True)

    def fill_items(self, clear=False):
        model = self.item_treeview.get_model()
        if clear:
            model.clear()
        default_config = gajim.connections[self.account].default
        expire_value = default_config['expire'] or ''
        model.append(('Default', expire_value,
            default_config['otr'], default_config['save']))
        for item, item_config in \
        gajim.connections[self.account].items.items():
            expire_value = item_config['expire'] or ''
            model.append((item, expire_value, item_config['otr'],
                item_config['save']))

    def _nec_archiving_error(self, obj):
        if obj.conn.name != self.account:
            return
        if self.waiting:
            pritext = _('There is an error')
            sectext = obj.error_msg
            ErrorDialog(pritext, sectext)
            self.waiting.pop()
        else:
            child = self.get_child_window()
            if child:
                child.error_arrived(obj.error_msg)

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_archiving_preferences_window_destroy(self, widget):
        gajim.ged.remove_event_handler(
            'archiving-preferences-changed-received', ged.GUI1,
            self._nec_archiving_changed_received)
        gajim.ged.remove_event_handler('archiving-error-received', ged.GUI1,
            self._nec_archiving_error)
        if 'archiving_preferences' in gajim.interface.instances[self.account]:
            del gajim.interface.instances[self.account]['archiving_preferences']


class PrivacyListWindow:
    """
    Window that is used for creating NEW or EDITING already there privacy lists
    """

    def __init__(self, account, privacy_list_name, action):
        '''action is 'EDIT' or 'NEW' depending on if we create a new priv list
        or edit an already existing one'''
        self.account = account
        self.privacy_list_name = privacy_list_name

        # Dicts and Default Values
        self.active_rule = ''
        self.global_rules = {}
        self.list_of_groups = {}

        self.max_order = 0

        # Default Edit Values
        self.edit_rule_type = 'jid'
        self.allow_deny = 'allow'

        # Connect to gtk builder
        self.xml = gtkgui_helpers.get_gtk_builder('privacy_list_window.ui')
        self.window = self.xml.get_object('privacy_list_edit_window')

        # Add Widgets

        for widget_to_add in ('title_hbox', 'privacy_lists_title_label',
        'list_of_rules_label', 'add_edit_rule_label', 'delete_open_buttons_hbox',
        'privacy_list_active_checkbutton', 'privacy_list_default_checkbutton',
        'list_of_rules_combobox', 'delete_open_buttons_hbox',
        'delete_rule_button', 'open_rule_button', 'edit_allow_radiobutton',
        'edit_deny_radiobutton', 'edit_type_jabberid_radiobutton',
        'edit_type_jabberid_entry', 'edit_type_group_radiobutton',
        'edit_type_group_combobox', 'edit_type_subscription_radiobutton',
        'edit_type_subscription_combobox', 'edit_type_select_all_radiobutton',
        'edit_queries_send_checkbutton', 'edit_send_messages_checkbutton',
        'edit_view_status_checkbutton', 'edit_all_checkbutton',
        'edit_order_spinbutton', 'new_rule_button', 'save_rule_button',
        'privacy_list_refresh_button', 'privacy_list_close_button',
        'edit_send_status_checkbutton', 'add_edit_vbox',
        'privacy_list_active_checkbutton', 'privacy_list_default_checkbutton'):
            self.__dict__[widget_to_add] = self.xml.get_object(widget_to_add)

        self.privacy_lists_title_label.set_label(
                _('Privacy List <b><i>%s</i></b>') % \
                GLib.markup_escape_text(self.privacy_list_name))

        if len(gajim.connections) > 1:
            title = _('Privacy List for %s') % self.account
        else:
            title = _('Privacy List')

        self.delete_rule_button.set_sensitive(False)
        self.open_rule_button.set_sensitive(False)
        self.privacy_list_active_checkbutton.set_sensitive(False)
        self.privacy_list_default_checkbutton.set_sensitive(False)
        self.list_of_rules_combobox.set_sensitive(False)

        # set jabber id completion
        jids_list_store = Gtk.ListStore(GObject.TYPE_STRING)
        for jid in gajim.contacts.get_jid_list(self.account):
            jids_list_store.append([jid])
        jid_entry_completion = Gtk.EntryCompletion()
        jid_entry_completion.set_text_column(0)
        jid_entry_completion.set_model(jids_list_store)
        jid_entry_completion.set_popup_completion(True)
        self.edit_type_jabberid_entry.set_completion(jid_entry_completion)
        if action == 'EDIT':
            self.refresh_rules()

        model = self.edit_type_group_combobox.get_model()
        count = 0
        for group in gajim.groups[self.account]:
            self.list_of_groups[group] = count
            count += 1
            model.append([group])
        self.edit_type_group_combobox.set_active(0)

        self.window.set_title(title)

        gajim.ged.register_event_handler('privacy-list-received', ged.GUI1,
            self._nec_privacy_list_received)
        gajim.ged.register_event_handler('privacy-list-active-default',
            ged.GUI1, self._nec_privacy_list_active_default)

        self.window.show_all()
        self.add_edit_vbox.hide()

        self.xml.connect_signals(self)

    def on_privacy_list_edit_window_destroy(self, widget):
        key_name = 'privacy_list_%s' % self.privacy_list_name
        if key_name in gajim.interface.instances[self.account]:
            del gajim.interface.instances[self.account][key_name]
        gajim.ged.remove_event_handler('privacy-list-received', ged.GUI1,
            self._nec_privacy_list_received)
        gajim.ged.remove_event_handler('privacy-list-active-default',
            ged.GUI1, self._nec_privacy_list_active_default)

    def _nec_privacy_list_active_default(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.active_list == self.privacy_list_name:
            self.privacy_list_active_checkbutton.set_active(True)
        else:
            self.privacy_list_active_checkbutton.set_active(False)
        if obj.default_list == self.privacy_list_name:
            self.privacy_list_default_checkbutton.set_active(True)
        else:
            self.privacy_list_default_checkbutton.set_active(False)

    def privacy_list_received(self, rules):
        model = self.list_of_rules_combobox.get_model()
        model.clear()
        self.global_rules = {}
        for rule in rules:
            if 'type' in rule:
                text_item = _('Order: %(order)s, action: %(action)s, type: %(type)s'
                        ', value: %(value)s') % {'order': rule['order'],
                        'action': rule['action'], 'type': rule['type'],
                        'value': rule['value']}
            else:
                text_item = _('Order: %(order)s, action: %(action)s') % \
                        {'order': rule['order'], 'action': rule['action']}
            if int(rule['order']) > self.max_order:
                self.max_order = int(rule['order'])
            self.global_rules[text_item] = rule
            model.append([text_item])
        if len(rules) == 0:
            self.title_hbox.set_sensitive(False)
            self.list_of_rules_combobox.set_sensitive(False)
            self.delete_rule_button.set_sensitive(False)
            self.open_rule_button.set_sensitive(False)
            self.privacy_list_active_checkbutton.set_sensitive(False)
            self.privacy_list_default_checkbutton.set_sensitive(False)
        else:
            self.list_of_rules_combobox.set_active(0)
            self.title_hbox.set_sensitive(True)
            self.list_of_rules_combobox.set_sensitive(True)
            self.delete_rule_button.set_sensitive(True)
            self.open_rule_button.set_sensitive(True)
            self.privacy_list_active_checkbutton.set_sensitive(True)
            self.privacy_list_default_checkbutton.set_sensitive(True)
        self.reset_fields()
        gajim.connections[self.account].get_active_default_lists()

    def _nec_privacy_list_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.list_name != self.privacy_list_name:
            return
        self.privacy_list_received(obj.rules)

    def refresh_rules(self):
        gajim.connections[self.account].get_privacy_list(self.privacy_list_name)

    def on_delete_rule_button_clicked(self, widget):
        model = self.list_of_rules_combobox.get_model()
        iter_ = self.list_of_rules_combobox.get_active_iter()
        _rule = model[iter_][0]
        tags = []
        for rule in self.global_rules:
            if rule != _rule:
                tags.append(self.global_rules[rule])
        gajim.connections[self.account].set_privacy_list(
                self.privacy_list_name, tags)
        self.privacy_list_received(tags)
        self.add_edit_vbox.hide()
        if not tags: # we removed latest rule
            if 'privacy_lists' in gajim.interface.instances[self.account]:
                win = gajim.interface.instances[self.account]['privacy_lists']
                win.remove_privacy_list_from_combobox(self.privacy_list_name)
                win.draw_widgets()

    def on_open_rule_button_clicked(self, widget):
        self.add_edit_rule_label.set_label(
                _('<b>Edit a rule</b>'))
        active_num = self.list_of_rules_combobox.get_active()
        if active_num == -1:
            self.active_rule = ''
        else:
            model = self.list_of_rules_combobox.get_model()
            iter_ = self.list_of_rules_combobox.get_active_iter()
            self.active_rule = model[iter_][0]
        if self.active_rule != '':
            rule_info = self.global_rules[self.active_rule]
            self.edit_order_spinbutton.set_value(int(rule_info['order']))
            if 'type' in rule_info:
                if rule_info['type'] == 'jid':
                    self.edit_type_jabberid_radiobutton.set_active(True)
                    self.edit_type_jabberid_entry.set_text(rule_info['value'])
                elif rule_info['type'] == 'group':
                    self.edit_type_group_radiobutton.set_active(True)
                    if rule_info['value'] in self.list_of_groups:
                        self.edit_type_group_combobox.set_active(
                                self.list_of_groups[rule_info['value']])
                    else:
                        self.edit_type_group_combobox.set_active(0)
                elif rule_info['type'] == 'subscription':
                    self.edit_type_subscription_radiobutton.set_active(True)
                    sub_value = rule_info['value']
                    if sub_value == 'none':
                        self.edit_type_subscription_combobox.set_active(0)
                    elif sub_value == 'both':
                        self.edit_type_subscription_combobox.set_active(1)
                    elif sub_value == 'from':
                        self.edit_type_subscription_combobox.set_active(2)
                    elif sub_value == 'to':
                        self.edit_type_subscription_combobox.set_active(3)
                else:
                    self.edit_type_select_all_radiobutton.set_active(True)
            else:
                self.edit_type_select_all_radiobutton.set_active(True)
            self.edit_send_messages_checkbutton.set_active(False)
            self.edit_queries_send_checkbutton.set_active(False)
            self.edit_view_status_checkbutton.set_active(False)
            self.edit_send_status_checkbutton.set_active(False)
            self.edit_all_checkbutton.set_active(False)
            if not rule_info['child']:
                self.edit_all_checkbutton.set_active(True)
            else:
                if 'presence-out' in rule_info['child']:
                    self.edit_send_status_checkbutton.set_active(True)
                if 'presence-in' in rule_info['child']:
                    self.edit_view_status_checkbutton.set_active(True)
                if 'iq' in rule_info['child']:
                    self.edit_queries_send_checkbutton.set_active(True)
                if 'message' in rule_info['child']:
                    self.edit_send_messages_checkbutton.set_active(True)

            if rule_info['action'] == 'allow':
                self.edit_allow_radiobutton.set_active(True)
            else:
                self.edit_deny_radiobutton.set_active(True)
        self.add_edit_vbox.show()

    def on_edit_all_checkbutton_toggled(self, widget):
        if widget.get_active():
            self.edit_send_messages_checkbutton.set_active(True)
            self.edit_queries_send_checkbutton.set_active(True)
            self.edit_view_status_checkbutton.set_active(True)
            self.edit_send_status_checkbutton.set_active(True)
            self.edit_send_messages_checkbutton.set_sensitive(False)
            self.edit_queries_send_checkbutton.set_sensitive(False)
            self.edit_view_status_checkbutton.set_sensitive(False)
            self.edit_send_status_checkbutton.set_sensitive(False)
        else:
            self.edit_send_messages_checkbutton.set_active(False)
            self.edit_queries_send_checkbutton.set_active(False)
            self.edit_view_status_checkbutton.set_active(False)
            self.edit_send_status_checkbutton.set_active(False)
            self.edit_send_messages_checkbutton.set_sensitive(True)
            self.edit_queries_send_checkbutton.set_sensitive(True)
            self.edit_view_status_checkbutton.set_sensitive(True)
            self.edit_send_status_checkbutton.set_sensitive(True)

    def on_privacy_list_active_checkbutton_toggled(self, widget):
        if widget.get_active():
            gajim.connections[self.account].set_active_list(
                    self.privacy_list_name)
        else:
            gajim.connections[self.account].set_active_list(None)

    def on_privacy_list_default_checkbutton_toggled(self, widget):
        if widget.get_active():
            gajim.connections[self.account].set_default_list(
                    self.privacy_list_name)
        else:
            gajim.connections[self.account].set_default_list(None)

    def on_new_rule_button_clicked(self, widget):
        self.reset_fields()
        self.add_edit_vbox.show()

    def reset_fields(self):
        self.edit_type_jabberid_entry.set_text('')
        self.edit_allow_radiobutton.set_active(True)
        self.edit_type_jabberid_radiobutton.set_active(True)
        self.active_rule = ''
        self.edit_send_messages_checkbutton.set_active(False)
        self.edit_queries_send_checkbutton.set_active(False)
        self.edit_view_status_checkbutton.set_active(False)
        self.edit_send_status_checkbutton.set_active(False)
        self.edit_all_checkbutton.set_active(False)
        self.edit_order_spinbutton.set_value(self.max_order + 1)
        self.edit_type_group_combobox.set_active(0)
        self.edit_type_subscription_combobox.set_active(0)
        self.add_edit_rule_label.set_label(
                _('<b>Add a rule</b>'))

    def get_current_tags(self):
        if self.edit_type_jabberid_radiobutton.get_active():
            edit_type = 'jid'
            edit_value = self.edit_type_jabberid_entry.get_text()
        elif self.edit_type_group_radiobutton.get_active():
            edit_type = 'group'
            model = self.edit_type_group_combobox.get_model()
            iter_ = self.edit_type_group_combobox.get_active_iter()
            edit_value = model[iter_][0]
        elif self.edit_type_subscription_radiobutton.get_active():
            edit_type = 'subscription'
            subs = ['none', 'both', 'from', 'to']
            edit_value = subs[self.edit_type_subscription_combobox.get_active()]
        elif self.edit_type_select_all_radiobutton.get_active():
            edit_type = ''
            edit_value = ''
        edit_order = str(self.edit_order_spinbutton.get_value_as_int())
        if self.edit_allow_radiobutton.get_active():
            edit_deny = 'allow'
        else:
            edit_deny = 'deny'
        child = []
        if not self.edit_all_checkbutton.get_active():
            if self.edit_send_messages_checkbutton.get_active():
                child.append('message')
            if self.edit_queries_send_checkbutton.get_active():
                child.append('iq')
            if self.edit_send_status_checkbutton.get_active():
                child.append('presence-out')
            if self.edit_view_status_checkbutton.get_active():
                child.append('presence-in')
        if edit_type != '':
            return {'order': edit_order, 'action': edit_deny,
                'type': edit_type, 'value': edit_value, 'child': child}
        return {'order': edit_order, 'action': edit_deny, 'child': child}

    def on_save_rule_button_clicked(self, widget):
        tags=[]
        current_tags = self.get_current_tags()
        if int(current_tags['order']) > self.max_order:
            self.max_order = int(current_tags['order'])
        if self.active_rule == '':
            tags.append(current_tags)

        for rule in self.global_rules:
            if rule != self.active_rule:
                tags.append(self.global_rules[rule])
            else:
                tags.append(current_tags)

        gajim.connections[self.account].set_privacy_list(
                self.privacy_list_name, tags)
        self.refresh_rules()
        self.add_edit_vbox.hide()
        if 'privacy_lists' in gajim.interface.instances[self.account]:
            win = gajim.interface.instances[self.account]['privacy_lists']
            win.add_privacy_list_to_combobox(self.privacy_list_name)
            win.draw_widgets()

    def on_list_of_rules_combobox_changed(self, widget):
        self.add_edit_vbox.hide()

    def on_edit_type_radiobutton_changed(self, widget, radiobutton):
        active_bool = widget.get_active()
        if active_bool:
            self.edit_rule_type = radiobutton

    def on_edit_allow_radiobutton_changed(self, widget, radiobutton):
        active_bool = widget.get_active()
        if active_bool:
            self.allow_deny = radiobutton

    def on_close_button_clicked(self, widget):
        self.window.destroy()

class PrivacyListsWindow:
    """
    Window that is the main window for Privacy Lists; we can list there the
    privacy lists and ask to create a new one or edit an already there one
    """
    def __init__(self, account):
        self.account = account
        self.privacy_lists_save = []

        self.xml = gtkgui_helpers.get_gtk_builder('privacy_lists_window.ui')

        self.window = self.xml.get_object('privacy_lists_first_window')
        for widget_to_add in ('list_of_privacy_lists_combobox',
            'delete_privacy_list_button', 'open_privacy_list_button',
            'new_privacy_list_button', 'new_privacy_list_entry',
            'privacy_lists_refresh_button', 'close_privacy_lists_window_button'):
            self.__dict__[widget_to_add] = self.xml.get_object(widget_to_add)

        self.draw_privacy_lists_in_combobox([])
        self.privacy_lists_refresh()

        self.enabled = True

        if len(gajim.connections) > 1:
            title = _('Privacy Lists for %s') % self.account
        else:
            title = _('Privacy Lists')

        self.window.set_title(title)

        gajim.ged.register_event_handler('privacy-lists-received', ged.GUI1,
            self._nec_privacy_lists_received)
        gajim.ged.register_event_handler('privacy-lists-removed', ged.GUI1,
            self._nec_privacy_lists_removed)

        self.window.show_all()

        self.xml.connect_signals(self)

    def on_privacy_lists_first_window_destroy(self, widget):
        if 'privacy_lists' in gajim.interface.instances[self.account]:
            del gajim.interface.instances[self.account]['privacy_lists']
        gajim.ged.remove_event_handler('privacy-lists-received', ged.GUI1,
            self._nec_privacy_lists_received)
        gajim.ged.remove_event_handler('privacy-lists-removed', ged.GUI1,
            self._nec_privacy_lists_removed)

    def remove_privacy_list_from_combobox(self, privacy_list):
        if privacy_list not in self.privacy_lists_save:
            return
        privacy_list_index = self.privacy_lists_save.index(privacy_list)
        self.list_of_privacy_lists_combobox.remove_text(privacy_list_index)
        self.privacy_lists_save.remove(privacy_list)

    def add_privacy_list_to_combobox(self, privacy_list):
        if privacy_list in self.privacy_lists_save:
            return
        model = self.list_of_privacy_lists_combobox.get_model()
        model.append([privacy_list])
        self.privacy_lists_save.append(privacy_list)

    def draw_privacy_lists_in_combobox(self, privacy_lists):
        self.list_of_privacy_lists_combobox.set_active(-1)
        self.list_of_privacy_lists_combobox.get_model().clear()
        self.privacy_lists_save = []
        for add_item in privacy_lists:
            self.add_privacy_list_to_combobox(add_item)
        self.draw_widgets()

    def draw_widgets(self):
        if len(self.privacy_lists_save) == 0:
            self.list_of_privacy_lists_combobox.set_sensitive(False)
            self.open_privacy_list_button.set_sensitive(False)
            self.delete_privacy_list_button.set_sensitive(False)
        else:
            self.list_of_privacy_lists_combobox.set_sensitive(True)
            self.list_of_privacy_lists_combobox.set_active(0)
            self.open_privacy_list_button.set_sensitive(True)
            self.delete_privacy_list_button.set_sensitive(True)

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_delete_privacy_list_button_clicked(self, widget):
        active_list = self.privacy_lists_save[
            self.list_of_privacy_lists_combobox.get_active()]
        gajim.connections[self.account].del_privacy_list(active_list)

    def privacy_list_removed(self, active_list):
        self.privacy_lists_save.remove(active_list)
        self.privacy_lists_received({'lists': self.privacy_lists_save})

    def _nec_privacy_lists_removed(self, obj):
        if obj.conn.name != self.account:
            return
        self.privacy_list_removed(obj.lists_list)

    def privacy_lists_received(self, lists):
        if not lists:
            return
        privacy_lists = []
        for privacy_list in lists['lists']:
            privacy_lists.append(privacy_list)
        self.draw_privacy_lists_in_combobox(privacy_lists)

    def _nec_privacy_lists_received(self, obj):
        if obj.conn.name != self.account:
            return
        self.privacy_lists_received(obj.lists_list)

    def privacy_lists_refresh(self):
        gajim.connections[self.account].get_privacy_lists()

    def on_new_privacy_list_button_clicked(self, widget):
        name = self.new_privacy_list_entry.get_text()
        if not name:
            ErrorDialog(_('Invalid List Name'),
                _('You must enter a name to create a privacy list.'),
                transient_for=self.window)
            return
        key_name = 'privacy_list_%s' % name
        if key_name in gajim.interface.instances[self.account]:
            gajim.interface.instances[self.account][key_name].window.present()
        else:
            gajim.interface.instances[self.account][key_name] = \
                PrivacyListWindow(self.account, name, 'NEW')
        self.new_privacy_list_entry.set_text('')

    def on_privacy_lists_refresh_button_clicked(self, widget):
        self.privacy_lists_refresh()

    def on_open_privacy_list_button_clicked(self, widget):
        name = self.privacy_lists_save[
                self.list_of_privacy_lists_combobox.get_active()]
        key_name = 'privacy_list_%s' % name
        if key_name in gajim.interface.instances[self.account]:
            gajim.interface.instances[self.account][key_name].window.present()
        else:
            gajim.interface.instances[self.account][key_name] = \
                     PrivacyListWindow(self.account, name, 'EDIT')

class InvitationReceivedDialog:
    def __init__(self, account, room_jid, contact_fjid, password=None,
    comment=None, is_continued=False):

        self.room_jid = room_jid
        self.account = account
        self.password = password
        self.is_continued = is_continued
        self.contact_fjid = contact_fjid

        jid = gajim.get_jid_without_resource(contact_fjid)

        pritext = _('''You are invited to a groupchat''')
        #Don't translate $Contact
        if is_continued:
            sectext = _('$Contact has invited you to join a discussion')
        else:
            sectext = _('$Contact has invited you to group chat %(room_jid)s')\
                % {'room_jid': room_jid}
        contact = gajim.contacts.get_first_contact_from_jid(account, jid)
        contact_text = contact and contact.name or jid
        sectext = i18n.direction_mark + sectext.replace('$Contact',
            contact_text)

        if comment: # only if not None and not ''
            comment = GLib.markup_escape_text(comment)
            comment = _('Comment: %s') % comment
            sectext += '\n\n%s' % comment
        sectext += '\n\n' + _('Do you want to accept the invitation?')

        def on_yes(checked, text):
            try:
                if self.is_continued:
                    gajim.interface.join_gc_room(self.account, self.room_jid,
                        gajim.nicks[self.account], None, is_continued=True)
                else:
                    JoinGroupchatWindow(self.account, self.room_jid)
            except GajimGeneralException:
                pass

        def on_no(text):
            gajim.connections[account].decline_invitation(self.room_jid,
                self.contact_fjid, text)

        dlg = YesNoDialog(pritext, sectext,
            text_label=_('Reason (if you decline):'), on_response_yes=on_yes,
            on_response_no=on_no)
        dlg.set_title(_('Groupchat Invitation'))

class ProgressDialog:
    def __init__(self, title_text, during_text, messages_queue):
        """
        During text is what to show during the procedure, messages_queue has the
        message to show in the textview
        """
        self.xml = gtkgui_helpers.get_gtk_builder('progress_dialog.ui')
        self.dialog = self.xml.get_object('progress_dialog')
        self.label = self.xml.get_object('label')
        self.label.set_markup('<big>' + during_text + '</big>')
        self.progressbar = self.xml.get_object('progressbar')
        self.dialog.set_title(title_text)
        self.dialog.set_default_size(450, 250)
        self.window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.dialog.show_all()
        self.xml.connect_signals(self)

        self.update_progressbar_timeout_id = GLib.timeout_add(100,
            self.update_progressbar)

    def update_progressbar(self):
        if self.dialog:
            self.progressbar.pulse()
            return True # loop forever
        return False

    def on_progress_dialog_delete_event(self, widget, event):
        return True # WM's X button or Escape key should not destroy the window


class ClientCertChooserDialog(FileChooserDialog):
    def __init__(self, path_to_clientcert_file='', on_response_ok=None,
    on_response_cancel=None):
        '''
        optionally accepts path_to_clientcert_file so it has that as selected
        '''
        def on_ok(widget, callback):
            '''
            check if file exists and call callback
            '''
            path_to_clientcert_file = self.get_filename()
            path_to_clientcert_file = \
                gtkgui_helpers.decode_filechooser_file_paths(
                (path_to_clientcert_file,))[0]
            if os.path.exists(path_to_clientcert_file):
                callback(widget, path_to_clientcert_file)

        FileChooserDialog.__init__(self,
            title_text=_('Choose Client Cert #PCKS12'),
            transient_for=gajim.interface.instances['accounts'].window,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK),
            current_folder='',
            default_response=Gtk.ResponseType.OK,
            on_response_ok=(on_ok, on_response_ok),
            on_response_cancel=on_response_cancel)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self.add_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('PKCS12 Files'))
        filter_.add_pattern('*.p12')
        self.add_filter(filter_)
        self.set_filter(filter_)

        if path_to_clientcert_file:
            # set_filename accept only absolute path
            path_to_clientcert_file = os.path.abspath(path_to_clientcert_file)
            self.set_filename(path_to_clientcert_file)


class SoundChooserDialog(FileChooserDialog):
    def __init__(self, path_to_snd_file='', on_response_ok=None,
                    on_response_cancel=None):
        """
        Optionally accepts path_to_snd_file so it has that as selected
        """
        def on_ok(widget, callback):
            """
            Check if file exists and call callback
            """
            path_to_snd_file = self.get_filename()
            path_to_snd_file = gtkgui_helpers.decode_filechooser_file_paths(
                    (path_to_snd_file,))[0]
            if os.path.exists(path_to_snd_file):
                callback(widget, path_to_snd_file)

        FileChooserDialog.__init__(self, title_text = _('Choose Sound'),
           action = Gtk.FileChooserAction.OPEN,
           buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                  Gtk.STOCK_OPEN, Gtk.ResponseType.OK),
           default_response = Gtk.ResponseType.OK,
           current_folder = gajim.config.get('last_sounds_dir'),
           on_response_ok = (on_ok, on_response_ok),
           on_response_cancel = on_response_cancel)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self.add_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('Wav Sounds'))
        filter_.add_pattern('*.wav')
        self.add_filter(filter_)
        self.set_filter(filter_)

        path_to_snd_file = helpers.check_soundfile_path(path_to_snd_file)
        if path_to_snd_file:
            # set_filename accept only absolute path
            path_to_snd_file = os.path.abspath(path_to_snd_file)
            self.set_filename(path_to_snd_file)

class ImageChooserDialog(FileChooserDialog):
    def __init__(self, path_to_file='', on_response_ok=None,
                    on_response_cancel=None):
        """
        Optionally accepts path_to_snd_file so it has that as selected
        """
        def on_ok(widget, callback):
            '''check if file exists and call callback'''
            path_to_file = self.get_filename()
            if not path_to_file:
                return
            path_to_file = gtkgui_helpers.decode_filechooser_file_paths(
                    (path_to_file,))[0]
            if os.path.exists(path_to_file):
                if isinstance(callback, tuple):
                    callback[0](widget, path_to_file, *callback[1:])
                else:
                    callback(widget, path_to_file)

        try:
            if os.name == 'nt':
                path = helpers.get_my_pictures_path()
            else:
                path = os.environ['HOME']
        except Exception:
            path = ''
        FileChooserDialog.__init__(self,
           title_text = _('Choose Image'),
           action = Gtk.FileChooserAction.OPEN,
           buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                  Gtk.STOCK_OPEN, Gtk.ResponseType.OK),
           default_response = Gtk.ResponseType.OK,
           current_folder = path,
           on_response_ok = (on_ok, on_response_ok),
           on_response_cancel = on_response_cancel)

        if on_response_cancel:
            self.connect('destroy', on_response_cancel)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self.add_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('Images'))
        filter_.add_mime_type('image/png')
        filter_.add_mime_type('image/jpeg')
        filter_.add_mime_type('image/gif')
        filter_.add_mime_type('image/tiff')
        filter_.add_mime_type('image/svg+xml')
        filter_.add_mime_type('image/x-xpixmap') # xpm
        self.add_filter(filter_)
        self.set_filter(filter_)

        if path_to_file:
            self.set_filename(path_to_file)

        self.set_use_preview_label(False)
        self.set_preview_widget(Gtk.Image())
        self.connect('selection-changed', self.update_preview)

    def update_preview(self, widget):
        path_to_file = widget.get_preview_filename()
        if path_to_file is None or os.path.isdir(path_to_file):
            # nothing to preview or directory
            # make sure you clean image do show nothing
            preview = widget.get_preview_widget()
            preview.clear()
            return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path_to_file, 100, 100)
        except GObject.GError:
            return
        widget.get_preview_widget().set_from_pixbuf(pixbuf)

class AvatarChooserDialog(ImageChooserDialog):
    def __init__(self, path_to_file='', on_response_ok=None,
            on_response_cancel=None, on_response_clear=None):
        ImageChooserDialog.__init__(self, path_to_file, on_response_ok,
            on_response_cancel)
        button = Gtk.Button(None, Gtk.STOCK_CLEAR)
        self.response_clear = on_response_clear
        if on_response_clear:
            button.connect('clicked', self.on_clear)
        button.show_all()
        self.action_area.pack_start(button, True, True, 0)
        self.action_area.reorder_child(button, 0)

    def on_clear(self, widget):
        if isinstance(self.response_clear, tuple):
            self.response_clear[0](widget, *self.response_clear[1:])
        else:
            self.response_clear(widget)


class ArchiveChooserDialog(FileChooserDialog):
    def __init__(self, on_response_ok=None, on_response_cancel=None):

        def on_ok(widget, callback):
            '''check if file exists and call callback'''
            path_to_file = self.get_filename()
            if not path_to_file:
                return
            path_to_file = gtkgui_helpers.decode_filechooser_file_paths(
                (path_to_file,))[0]
            if os.path.exists(path_to_file):
                if isinstance(callback, tuple):
                    callback[0](path_to_file, *callback[1:])
                else:
                    callback(path_to_file)
            self.destroy()

        path = helpers.get_documents_path()

        FileChooserDialog.__init__(self,
            title_text=_('Choose Archive'),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK),
            default_response=Gtk.ResponseType.OK,
            current_folder=path,
            on_response_ok=(on_ok, on_response_ok),
            on_response_cancel=on_response_cancel)

        if on_response_cancel:
            self.connect('destroy', on_response_cancel)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self.add_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('Zip files'))
        filter_.add_pattern('*.zip')

        self.add_filter(filter_)
        self.set_filter(filter_)


class AddSpecialNotificationDialog:
    def __init__(self, jid):
        """
        jid is the jid for which we want to add special notification (sound and
        notification popups)
        """
        self.xml = gtkgui_helpers.get_gtk_builder(
            'add_special_notification_window.ui')
        self.window = self.xml.get_object('add_special_notification_window')
        self.condition_combobox = self.xml.get_object('condition_combobox')
        self.condition_combobox.set_active(0)
        self.notification_popup_yes_no_combobox = self.xml.get_object(
                'notification_popup_yes_no_combobox')
        self.notification_popup_yes_no_combobox.set_active(0)
        self.listen_sound_combobox = self.xml.get_object('listen_sound_combobox')
        self.listen_sound_combobox.set_active(0)

        self.jid = jid
        self.xml.get_object('when_foo_becomes_label').set_text(
                _('When %s becomes:') % self.jid)

        self.window.set_title(_('Adding Special Notification for %s') % jid)
        self.window.show_all()
        self.xml.connect_signals(self)

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def on_add_special_notification_window_delete_event(self, widget, event):
        self.window.destroy()

    def on_listen_sound_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 1: # user selected 'choose sound'
            def on_ok(widget, path_to_snd_file):
                pass

            def on_cancel(widget):
                widget.set_active(0) # go back to No Sound

            self.dialog = SoundChooserDialog(on_response_ok=on_ok,
                on_response_cancel=on_cancel)

    def on_ok_button_clicked(self, widget):
        conditions = ('online', 'chat', 'online_and_chat',
            'away', 'xa', 'away_and_xa', 'dnd', 'xa_and_dnd', 'offline')
        active = self.condition_combobox.get_active()

        active_iter = self.listen_sound_combobox.get_active_iter()
        listen_sound_model = self.listen_sound_combobox.get_model()

class TransformChatToMUC:
    # Keep a reference on windows so garbage collector don't restroy them
    instances = []
    def __init__(self, account, jids, preselected=None):
        """
        This window is used to trasform a one-to-one chat to a MUC. We do 2
        things: first select the server and then make a guests list
        """

        self.instances.append(self)
        self.account = account
        self.auto_jids = jids
        self.preselected_jids = preselected

        self.xml = gtkgui_helpers.get_gtk_builder('chat_to_muc_window.ui')
        self.window = self.xml.get_object('chat_to_muc_window')

        for widget_to_add in ('invite_button', 'cancel_button',
            'server_list_comboboxentry', 'guests_treeview',
            'server_and_guests_hseparator', 'server_select_label'):
            self.__dict__[widget_to_add] = self.xml.get_object(widget_to_add)

        server_list = []
        self.servers = Gtk.ListStore(str)
        self.server_list_comboboxentry.set_model(self.servers)
        cell = Gtk.CellRendererText()
        self.server_list_comboboxentry.pack_start(cell, True)
        self.server_list_comboboxentry.add_attribute(cell, 'text', 0)

        # get the muc server of our server
        if 'jabber' in gajim.connections[account].muc_jid:
            server_list.append(gajim.connections[account].muc_jid['jabber'])
        # add servers or recently joined groupchats
        recently_groupchat = gajim.config.get('recently_groupchat').split()
        for g in recently_groupchat:
            server = gajim.get_server_from_jid(g)
            if server not in server_list and not server.startswith('irc'):
                server_list.append(server)
        # add a default server
        if not server_list:
            server_list.append('conference.jabber.org')

        for s in server_list:
            self.servers.append([s])

        self.server_list_comboboxentry.set_active(0)

        # set treeview
        # name, jid
        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        self.store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.guests_treeview.set_model(self.store)

        renderer1 = Gtk.CellRendererText()
        renderer2 = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn('Status', renderer2, pixbuf=0)
        self.guests_treeview.append_column(column)
        column = Gtk.TreeViewColumn('Name', renderer1, text=1)
        self.guests_treeview.append_column(column)

        self.guests_treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        # All contacts beside the following can be invited:
        #       transports, zeroconf contacts, minimized groupchats
        def invitable(contact, contact_transport=None):
            return (contact.jid not in self.auto_jids and
                contact.jid != gajim.get_jid_from_account(self.account) and
                contact.jid not in gajim.interface.minimized_controls[account] and
                not contact.is_transport() and
                contact_transport in ('jabber', None))

        # set jabber id and pseudos
        for account in gajim.contacts.get_accounts():
            if gajim.connections[account].is_zeroconf:
                continue
            for jid in gajim.contacts.get_jid_list(account):
                contact = gajim.contacts.get_contact_with_highest_priority(
                    account, jid)
                contact_transport = gajim.get_transport_name_from_jid(jid)
                # Add contact if it can be invited
                if invitable(contact, contact_transport) and \
                contact.show not in ('offline', 'error'):
                    img = gajim.interface.jabber_state_images['16'][contact.show]
                    name = contact.name
                    if name == '':
                        name = jid.split('@')[0]
                    iter_ = self.store.append([img.get_pixbuf(), name, jid])
                    # preselect treeview rows
                    if self.preselected_jids and jid in self.preselected_jids:
                        path = self.store.get_path(iter_)
                        self.guests_treeview.get_selection().select_path(path)

        gajim.ged.register_event_handler('unique-room-id-supported', ged.GUI1,
            self._nec_unique_room_id_supported)
        gajim.ged.register_event_handler('unique-room-id-not-supported',
            ged.GUI1, self._nec_unique_room_id_not_supported)

        # show all
        self.window.show_all()

        self.xml.connect_signals(self)

    def on_chat_to_muc_window_destroy(self, widget):
        gajim.ged.remove_event_handler('unique-room-id-supported', ged.GUI1,
            self._nec_unique_room_id_supported)
        gajim.ged.remove_event_handler('unique-room-id-not-supported', ged.GUI1,
            self._nec_unique_room_id_not_supported)
        self.instances.remove(self)

    def on_chat_to_muc_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape: # ESCAPE
            self.window.destroy()

    def on_invite_button_clicked(self, widget):
        row = self.server_list_comboboxentry.get_child().get_displayed_row()
        model = self.server_list_comboboxentry.get_model()
        server = model[row][0].strip()
        if server == '':
            return
        gajim.connections[self.account].check_unique_room_id_support(server, self)

    def _nec_unique_room_id_supported(self, obj):
        if obj.instance != self:
            return
        guest_list = []
        guests = self.guests_treeview.get_selection().get_selected_rows()
        for guest in guests[1]:
            iter_ = self.store.get_iter(guest)
            guest_list.append(self.store[iter_][2])
        for guest in self.auto_jids:
            guest_list.append(guest)
        room_jid = obj.room_id + '@' + obj.server
        gajim.automatic_rooms[self.account][room_jid] = {}
        gajim.automatic_rooms[self.account][room_jid]['invities'] = guest_list
        gajim.automatic_rooms[self.account][room_jid]['continue_tag'] = True
        gajim.interface.join_gc_room(self.account, room_jid,
            gajim.nicks[self.account], None, is_continued=True)
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def _nec_unique_room_id_not_supported(self, obj):
        if obj.instance != self:
            return
        obj.room_id = gajim.nicks[self.account].lower().replace(' ', '') + \
            str(randrange(9999999))
        self._nec_unique_room_id_supported(obj)

class DataFormWindow(Dialog):
    def __init__(self, form, on_response_ok):
        self.df_response_ok = on_response_ok
        Dialog.__init__(self, None, 'test', [(Gtk.STOCK_CANCEL,
            Gtk.ResponseType.REJECT), (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT)],
            on_response_ok=self.on_ok)
        self.set_resizable(True)
        gtkgui_helpers.resize_window(self, 600, 400)
        self.dataform_widget =  dataforms_widget.DataFormWidget()
        self.dataform = dataforms.ExtendForm(node=form)
        self.dataform_widget.set_sensitive(True)
        self.dataform_widget.data_form = self.dataform
        self.dataform_widget.show_all()
        self.vbox.pack_start(self.dataform_widget, True, True, 0)

    def on_ok(self):
        form = self.dataform_widget.data_form
        if isinstance(self.df_response_ok, tuple):
            self.df_response_ok[0](form, *self.df_response_ok[1:])
        else:
            self.df_response_ok(form)
        self.destroy()

class ESessionInfoWindow:
    """
    Class for displaying information about a XEP-0116 encrypted session
    """
    def __init__(self, session, transient_for=None):
        self.session = session

        self.xml = gtkgui_helpers.get_gtk_builder('esession_info_window.ui')
        self.xml.connect_signals(self)

        self.security_image = self.xml.get_object('security_image')
        self.verify_now_button = self.xml.get_object('verify_now_button')
        self.button_label = self.xml.get_object('verification_status_label')
        self.window = self.xml.get_object('esession_info_window')
        self.update_info()
        self.window.set_transient_for(transient_for)

        self.window.show_all()

    def update_info(self):
        labeltext = _('''Your chat session with <b>%(jid)s</b> is encrypted.\n\nThis session's Short Authentication String is <b>%(sas)s</b>.''') % {'jid': self.session.jid, 'sas': self.session.sas}

        if self.session.verified_identity:
            labeltext += '\n\n' + _('''You have already verified this contact's identity.''')
            security_image = 'security-high'
            if self.session.control:
                self.session.control._show_lock_image(True, 'E2E', True,
                    self.session.is_loggable(), True)

            verification_status = _('''Contact's identity verified''')
            self.window.set_title(verification_status)
            self.xml.get_object('verification_status_label').set_markup(
                    '<b><span size="x-large">%s</span></b>' % verification_status)

            self.xml.get_object('dialog-action_area1').set_no_show_all(True)
            self.button_label.set_text(_('Verify again...'))
        else:
            if self.session.control:
                self.session.control._show_lock_image(True, 'E2E', True,
                     self.session.is_loggable(), False)
            labeltext += '\n\n' + _('''To be certain that <b>only</b> the expected person can read your messages or send you messages, you need to verify their identity by clicking the button below.''')
            security_image = 'security-low'

            verification_status = _('''Contact's identity NOT verified''')
            self.window.set_title(verification_status)
            self.xml.get_object('verification_status_label').set_markup(
                '<b><span size="x-large">%s</span></b>' % verification_status)

            self.button_label.set_text(_('Verify...'))

        path = gtkgui_helpers.get_icon_path(security_image, 32)
        self.security_image.set_from_file(path)

        self.xml.get_object('info_display').set_markup(labeltext)

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_verify_now_button_clicked(self, widget):
        pritext = _('''Have you verified the contact's identity?''')
        sectext = _('''To prevent talking to an unknown person, you should speak to <b>%(jid)s</b> directly (in person or on the phone) and verify that they see the same Short Authentication String (SAS) as you.\n\nThis session's Short Authentication String is <b>%(sas)s</b>.''') % {'jid': self.session.jid, 'sas': self.session.sas}
        sectext += '\n\n' + _('Did you talk to the remote contact and verify the SAS?')

        def on_yes(checked):
            self.session._verified_srs_cb()
            self.session.verified_identity = True
            self.update_info()

        def on_no():
            self.session._unverified_srs_cb()
            self.session.verified_identity = False
            self.update_info()

        YesNoDialog(pritext, sectext, on_response_yes=on_yes,
            on_response_no=on_no, transient_for=self.window)

class GPGInfoWindow:
    """
    Class for displaying information about a XEP-0116 encrypted session
    """
    def __init__(self, control, transient_for=None):
        xml = gtkgui_helpers.get_gtk_builder('esession_info_window.ui')
        security_image = xml.get_object('security_image')
        status_label = xml.get_object('verification_status_label')
        info_label = xml.get_object('info_display')
        verify_now_button = xml.get_object('verify_now_button')
        self.window = xml.get_object('esession_info_window')
        account = control.account
        keyID = control.contact.keyID
        error = None

        verify_now_button.set_no_show_all(True)
        verify_now_button.hide()

        if keyID.endswith('MISMATCH'):
            verification_status = _('''Contact's identity NOT verified''')
            info = _('The contact\'s key (%s) <b>does not match</b> the key '
                'assigned in Gajim.') % keyID[:8]
            image = 'security-low'
        elif not keyID:
            # No key assigned nor a key is used by remote contact
            verification_status = _('No OpenPGP key assigned')
            info = _('No OpenPGP key is assigned to this contact. So you cannot'
                ' encrypt messages.')
            image = 'security-low'
        else:
            error = gajim.connections[account].gpg.encrypt('test', [keyID])[1]
            if error:
                verification_status = _('''Contact's identity NOT verified''')
                info = _('OpenPGP key is assigned to this contact, but <b>you '
                    'do not trust his key</b>, so message <b>cannot</b> be '
                    'encrypted. Use your OpenPGP client to trust this key.')
                image = 'security-low'
            else:
                verification_status = _('''Contact's identity verified''')
                info = _('OpenPGP Key is assigned to this contact, and you '
                    'trust his key, so messages will be encrypted.')
                image = 'security-high'

        status_label.set_markup('<b><span size="x-large">%s</span></b>' % \
            verification_status)
        info_label.set_markup(info)

        path = gtkgui_helpers.get_icon_path(image, 32)
        security_image.set_from_file(path)

        self.window.set_transient_for(transient_for)
        xml.connect_signals(self)
        self.window.show_all()

    def on_close_button_clicked(self, widget):
        self.window.destroy()



class ResourceConflictDialog(TimeoutDialog, InputDialog):
    def __init__(self, title, text, resource, ok_handler):
        TimeoutDialog.__init__(self, 15, self.on_timeout)
        InputDialog.__init__(self, title, text, input_str=resource,
                is_modal=False, ok_handler=ok_handler)
        self.title_text = title
        self.run_timeout()

    def on_timeout(self):
        self.on_okbutton_clicked(None)



class VoIPCallReceivedDialog(object):
    instances = {}
    def __init__(self, account, contact_jid, sid, content_types):
        self.instances[(contact_jid, sid)] = self
        self.account = account
        self.fjid = contact_jid
        self.sid = sid
        self.content_types = content_types

        xml = gtkgui_helpers.get_gtk_builder('voip_call_received_dialog.ui')
        xml.connect_signals(self)

        jid = gajim.get_jid_without_resource(self.fjid)
        contact = gajim.contacts.get_first_contact_from_jid(account, jid)
        if contact and contact.name:
            self.contact_text = '%s (%s)' % (contact.name, jid)
        else:
            self.contact_text = contact_jid

        self.dialog = xml.get_object('voip_call_received_messagedialog')
        self.set_secondary_text()

        self.dialog.show_all()

    @classmethod
    def get_dialog(cls, jid, sid):
        if (jid, sid) in cls.instances:
            return cls.instances[(jid, sid)]
        else:
            return None

    def set_secondary_text(self):
        if 'audio' in self.content_types and 'video' in self.content_types:
            types_text = _('an audio and video')
        elif 'audio' in self.content_types:
            types_text = _('an audio')
        elif 'video' in self.content_types:
            types_text = _('a video')

        # do the substitution
        self.dialog.set_property('secondary-text',
            _('%(contact)s wants to start %(type)s session with you. Do you want '
            'to answer the call?') % {'contact': self.contact_text,
            'type': types_text})

    def add_contents(self, content_types):
        for type_ in content_types:
            if type_ not in self.content_types:
                self.content_types.add(type_)
        self.set_secondary_text()

    def remove_contents(self, content_types):
        for type_ in content_types:
            if type_ in self.content_types:
                self.content_types.remove(type_)
        if not self.content_types:
            self.dialog.destroy()
        else:
            self.set_secondary_text()

    def on_voip_call_received_messagedialog_destroy(self, dialog):
        if (self.fjid, self.sid) in self.instances:
            del self.instances[(self.fjid, self.sid)]

    def on_voip_call_received_messagedialog_close(self, dialog):
        return self.on_voip_call_received_messagedialog_response(dialog,
                Gtk.ResponseType.NO)

    def on_voip_call_received_messagedialog_response(self, dialog, response):
        # we've got response from user, either stop connecting or accept the call
        session = gajim.connections[self.account].get_jingle_session(self.fjid,
            self.sid)
        if not session:
            dialog.destroy()
            return
        if response == Gtk.ResponseType.YES:
            #TODO: Ensure that ctrl.contact.resource == resource
            jid = gajim.get_jid_without_resource(self.fjid)
            resource = gajim.get_resource_from_jid(self.fjid)
            ctrl = (gajim.interface.msg_win_mgr.get_control(self.fjid, self.account)
                or gajim.interface.msg_win_mgr.get_control(jid, self.account)
                or gajim.interface.new_chat_from_jid(self.account, jid))

            # Chat control opened, update content's status
            audio = session.get_content('audio')
            video = session.get_content('video')
            if audio and not audio.negotiated:
                ctrl.set_audio_state('connecting', self.sid)
            if video and not video.negotiated:
                video_hbox = ctrl.xml.get_object('video_hbox')
                video_hbox.set_no_show_all(False)
                if gajim.config.get('video_see_self'):
                    fixed = ctrl.xml.get_object('outgoing_fixed')
                    fixed.set_no_show_all(False)
                video_hbox.show_all()
                if os.name == 'nt':
                    in_xid = ctrl.xml.get_object('incoming_drawingarea').\
                        get_window().handle
                else:
                    in_xid = ctrl.xml.get_object('incoming_drawingarea').\
                        get_window().xid
                content = session.get_content('video')
                # move outgoing stream to chat window
                if gajim.config.get('video_see_self'):
                    if os.name == 'nt':
                        out_xid = ctrl.xml.get_object('outgoing_drawingarea').\
                            get_window().handle
                    else:
                        out_xid = ctrl.xml.get_object('outgoing_drawingarea').\
                            get_window().xid
                    b = content.src_bin
                    found = False
                    for e in b.elements():
                        if e.get_name().startswith('autovideosink'):
                            found = True
                            break
                    if found:
                        found = False
                        for f in e.elements():
                            if f.get_name().startswith('autovideosink'):
                                f.set_xwindow_id(out_xid)
                                content.out_xid = out_xid
                content.in_xid = in_xid
                ctrl.set_video_state('connecting', self.sid)
            # Now, accept the content/sessions.
            # This should be done after the chat control is running
            if not session.accepted:
                session.approve_session()
            for content in self.content_types:
                session.approve_content(content)
        else: # response==Gtk.ResponseType.NO
            if not session.accepted:
                session.decline_session()
            else:
                for content in self.content_types:
                    session.reject_content(content)

        dialog.destroy()

class CertificatDialog(InformationDialog):
    def __init__(self, parent, account, cert):
        issuer = cert.get_issuer()
        subject = cert.get_subject()
        InformationDialog.__init__(self,
            _('Certificate for account %s') % account, _('''<b>Issued to:</b>
Common Name (CN): %(scn)s
Organization (O): %(sorg)s
Organizationl Unit (OU): %(sou)s
Serial Number: %(sn)s

<b>Issued by:</b>
Common Name (CN): %(icn)s
Organization (O): %(iorg)s
Organizationl Unit (OU): %(iou)s

<b>Validity:</b>
Issued on: %(io)s
Expires on: %(eo)s

<b>Fingerprint</b>
SHA1 Fingerprint: %(sha1)s

SHA256 Fingerprint: %(sha256)s
''') % {
            'scn': subject.commonName, 'sorg': subject.organizationName,
            'sou': subject.organizationalUnitName,
            'sn': cert.get_serial_number(), 'icn': issuer.commonName,
            'iorg': issuer.organizationName,
            'iou': issuer.organizationalUnitName,
            'io': cert.get_notBefore(), 'eo': cert.get_notAfter(),
            'sha1': cert.digest('sha1'),
            'sha256': cert.digest('sha256')})
        pix = gtkgui_helpers.get_icon_pixmap('application-certificate', size=32,
            quiet=True)
        if pix:
            img =  Gtk.Image.new_from_pixbuf(pix)
            img.show_all()
            self.set_image(img)
        self.set_transient_for(parent)
        self.set_title(_('Certificate for account %s') % account)


class CheckFingerprintDialog(YesNoDialog):
    def __init__(self, pritext='', sectext='', checktext='',
    on_response_yes=None, on_response_no=None, account=None, certificate=None):
        self.account = account
        self.cert = certificate
        YesNoDialog.__init__(self, pritext, sectext=sectext,
            checktext=checktext, on_response_yes=on_response_yes,
            on_response_no=on_response_no)
        self.set_title(_('SSL Certificate Verification for %s') % account)
        b = Gtk.Button(_('View cert...'))
        b.connect('clicked', self.on_cert_clicked)
        b.show_all()
        area = self.get_action_area()
        area.pack_start(b, True, True, 0)

    def on_cert_clicked(self, button):
        CertificatDialog(self, self.account, self.cert)

class SSLErrorDialog(ConfirmationDialogDoubleCheck):
    def __init__(self, account, certificate, pritext, sectext, checktext1,
    checktext2, on_response_ok=None, on_response_cancel=None):
        self.account = account
        self.cert = certificate
        ConfirmationDialogDoubleCheck.__init__(self, pritext, sectext,
            checktext1, checktext2, on_response_ok=on_response_ok,
            on_response_cancel=on_response_cancel, is_modal=False)
        b = Gtk.Button(_('View cert...'))
        b.connect('clicked', self.on_cert_clicked)
        b.show_all()
        area = self.get_action_area()
        area.pack_start(b, True, True, 0)

    def on_cert_clicked(self, button):
        d = CertificatDialog(self, self.account, self.cert)


class BigAvatarWindow(Gtk.Window):
    def __init__(self, avatar, pos_x, pos_y, width, height, callback):
        super(BigAvatarWindow, self).__init__(type=Gtk.WindowType.POPUP)
        self.set_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.avatar = avatar
        self.callback = callback
        self.screen = self.get_screen()
        self.visual = self.screen.get_rgba_visual()
        if self.visual != None and self.screen.is_composited():
            self.set_visual(self.visual)
        self.set_app_paintable(True)
        self.set_size_request(width, height)
        self.move(pos_x, pos_y)
        self.connect("draw", self.area_draw)
        # we should hide the window
        self.connect('leave_notify_event', self._on_window_avatar_leave_notify)
        self.connect('motion-notify-event', self._on_window_motion_notify)
        self.realize()
        # make the cursor invisible so we can see the image
        invisible_cursor = gtkgui_helpers.get_invisible_cursor()
        self.get_window().set_cursor(invisible_cursor)
        self.show_all()

    def area_draw(self, widget, cr):
        cr.set_source_rgba(.2, .2, .2, 0.0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        Gdk.cairo_set_source_pixbuf(cr, self.avatar, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

    def _on_window_avatar_leave_notify(self, widget, event):
        """
        Just left the popup window that holds avatar
        """
        self.destroy()
        self.bigger_avatar_window = None
        # Re-show the small avatar
        self.callback()

    def _on_window_motion_notify(self, widget, event):
        """
        Just moved the mouse so show the cursor
        """
        cursor = Gdk.Cursor.new(Gdk.CursorType.LEFT_PTR)
        self.get_window().set_cursor(cursor)
