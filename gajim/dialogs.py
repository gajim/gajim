# Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2005-2008 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

from typing import Dict  # pylint: disable=unused-import
from typing import List  # pylint: disable=unused-import
from typing import Tuple  # pylint: disable=unused-import

import uuid
import logging

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common.i18n import _
from gajim.common.const import ACTIVITIES
from gajim.common.const import MOODS

from gajim.common import app
from gajim.common import helpers
from gajim.common.exceptions import GajimGeneralException

from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.dialogs import AspellDictError
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_builder
from gajim.gtk.util import get_activity_icon_name
from gajim.gtk.util import get_app_window
from gajim.gtk import gstreamer

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports


log = logging.getLogger('gajim.dialogs')


class EditGroupsDialog:
    """
    Class for the edit group dialog window
    """

    def __init__(self, list_):
        """
        list_ is a list of (contact, account) tuples
        """
        self.xml = get_builder('edit_groups_dialog.ui')
        self.dialog = self.xml.get_object('edit_groups_dialog')
        self.dialog.set_transient_for(app.interface.roster.window)
        self.list_ = list_
        self.changes_made = False
        self.treeview = self.xml.get_object('groups_treeview')
        if len(list_) == 1:
            contact = list_[0][0]
            self.xml.get_object('nickname_label').set_markup(
                    _('Contact name: <i>%s</i>') % contact.get_shown_name())
            self.xml.get_object('jid_label').set_markup(
                    _('XMPP Address: <i>%s</i>') % contact.jid)
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
                con = app.connections[account]
                con.get_module('Roster').update_contact(
                    contact.jid, contact.name, contact.groups)

    def on_edit_groups_dialog_response(self, widget, response_id):
        if response_id == Gtk.ResponseType.CLOSE:
            self.dialog.destroy()

    def remove_group(self, group):
        """
        Remove group group from all contacts and all their brothers
        """
        for (contact, account) in self.list_:
            app.interface.roster.remove_contact_from_groups(contact.jid,
                account, [group])

        # FIXME: Ugly workaround.
        # pylint: disable=undefined-loop-variable
        app.interface.roster.draw_group(_('General'), account)

    def add_group(self, group):
        """
        Add group group to all contacts and all their brothers
        """
        for (contact, account) in self.list_:
            app.interface.roster.add_contact_to_groups(contact.jid, account,
                [group])

        # FIXME: Ugly workaround.
        # Maybe we haven't been in any group (defaults to General)
        # pylint: disable=undefined-loop-variable
        app.interface.roster.draw_group(_('General'), account)

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
                for g in app.groups[account].keys():
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


class ChangeActivityDialog:
    PAGELIST = [
        'doing_chores', 'drinking', 'eating', 'exercising', 'grooming',
        'having_appointment', 'inactive', 'relaxing', 'talking', 'traveling',
        'working']

    def __init__(self, on_response, activity_=None, subactivity_=None, text=''):
        self.on_response = on_response
        self.activity = activity_
        self.subactivity = subactivity_
        self.text = text
        self.xml = get_builder('change_activity_dialog.ui')
        self.window = self.xml.get_object('change_activity_dialog')
        self.window.set_transient_for(app.interface.roster.window)

        self.checkbutton = self.xml.get_object('enable_checkbutton')
        self.notebook = self.xml.get_object('notebook')
        self.entry = self.xml.get_object('description_entry')

        rbtns = {}
        group = None

        for category in ACTIVITIES:
            icon_name = get_activity_icon_name(category)
            item = self.xml.get_object(category + '_image')
            item.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
            item.set_tooltip_text(ACTIVITIES[category]['category'])

            vbox = self.xml.get_object(category + '_vbox')
            vbox.set_border_width(5)

            # Other
            act = category + '_other'

            if group:
                rbtns[act] = Gtk.RadioButton()
                rbtns[act].join_group(group)
            else:
                rbtns[act] = group = Gtk.RadioButton()

            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            hbox = Gtk.HBox(homogeneous=False, spacing=5)
            hbox.pack_start(icon, False, False, 0)
            lbl = Gtk.Label(
                label='<b>%s</b>' % ACTIVITIES[category]['category'])
            lbl.set_use_markup(True)
            hbox.pack_start(lbl, False, False, 0)
            rbtns[act].add(hbox)
            rbtns[act].connect(
                'toggled', self.on_rbtn_toggled, [category, 'other'])
            vbox.pack_start(rbtns[act], False, False, 0)

            activities = list(ACTIVITIES[category].keys())
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

                icon_name = get_activity_icon_name(category, activity)
                icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
                label = Gtk.Label(label=ACTIVITIES[category][activity])
                hbox = Gtk.HBox(homogeneous=False, spacing=5)
                hbox.pack_start(icon, False, False, 0)
                hbox.pack_start(label, False, False, 0)
                rbtns[act].connect(
                    'toggled', self.on_rbtn_toggled, [category, activity])
                rbtns[act].add(hbox)
                vbox.pack_start(rbtns[act], False, False, 0)


        self.default_radio = rbtns['doing_chores_other']

        if self.activity in ACTIVITIES:
            if not self.subactivity in ACTIVITIES[self.activity]:
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
        Return activity and message (None if no activity selected)
        """
        if self.checkbutton.get_active():
            self.on_response(
                self.activity, self.subactivity, self.entry.get_text())
        else:
            self.on_response(None, None, '')
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

class ChangeMoodDialog:
    COLS = 11

    def __init__(self, on_response, mood_=None, text=''):
        self.on_response = on_response
        self.mood = mood_
        self.text = text
        self.xml = get_builder('change_mood_dialog.ui')

        self.window = self.xml.get_object('change_mood_dialog')
        self.window.set_transient_for(app.interface.roster.window)
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
        for mood in MOODS:
            self.MOODS.append(mood)
        self.MOODS.sort()

        for mood in self.MOODS:
            image = Gtk.Image.new_from_icon_name(
                'mood-%s' % mood, Gtk.IconSize.MENU)
            self.mood_buttons[mood] = Gtk.RadioButton()
            self.mood_buttons[mood].join_group(no_mood_button)
            self.mood_buttons[mood].set_mode(False)
            self.mood_buttons[mood].add(image)
            self.mood_buttons[mood].set_relief(Gtk.ReliefStyle.NONE)
            self.mood_buttons[mood].set_tooltip_text(MOODS[mood])
            self.mood_buttons[mood].connect('clicked',
                self.on_mood_button_clicked, mood)
            table.attach(self.mood_buttons[mood], x, y, 1, 1)

            # Calculate the next position
            x += 1
            if x >= self.COLS:
                x = 0
                y += 1

        if self.mood in MOODS:
            self.mood_buttons[self.mood].set_active(True)
            self.label.set_text(MOODS[self.mood])
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
            self.label.set_text(MOODS[data])
            self.entry.set_sensitive(True)
        else:
            self.label.set_text(_('None'))
            self.entry.set_text('')
            self.entry.set_sensitive(False)
        self.mood = data

    def on_ok_button_clicked(self, widget):
        '''Return mood and message (None if no mood selected)'''
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
    def __init__(self, timeout):
        self.countdown_left = timeout
        self.countdown_enabled = True
        self.title_text = ''

    def run_timeout(self):
        if self.countdown_left > 0:
            self.countdown()
            GLib.timeout_add_seconds(1, self.countdown)

    def on_timeout(self):
        """
        To be implemented in derivated classes
        """

    def countdown(self):
        if self.countdown_enabled:
            if self.countdown_left <= 0:
                self.on_timeout()
                return False
            self.dialog.set_title('%s [%s]' % (
                self.title_text, str(self.countdown_left)))
            self.countdown_left -= 1
            return True

        self.dialog.set_title(self.title_text)
        return False

class ChangeStatusMessageDialog(TimeoutDialog):
    def __init__(self, on_response, show=None, show_pep=True):
        countdown_time = app.config.get('change_status_window_timeout')
        TimeoutDialog.__init__(self, countdown_time)
        self.show = show
        self.pep_dict = {}
        self.show_pep = show_pep
        self.on_response = on_response
        self.xml = get_builder('change_status_message_dialog.ui')
        self.dialog = self.xml.get_object('change_status_message_dialog')
        self.dialog.set_transient_for(app.interface.roster.window)
        msg = None
        if show:
            uf_show = helpers.get_uf_show(show)
            self.title_text = _('%s Status Message') % uf_show
            msg = app.config.get_per('statusmsg', '_last_' + self.show,
                                                               'message')
            self.pep_dict['activity'] = app.config.get_per('statusmsg',
                '_last_' + self.show, 'activity')
            self.pep_dict['subactivity'] = app.config.get_per('statusmsg',
                '_last_' + self.show, 'subactivity')
            self.pep_dict['activity_text'] = app.config.get_per('statusmsg',
                '_last_' + self.show, 'activity_text')
            self.pep_dict['mood'] = app.config.get_per('statusmsg',
                '_last_' + self.show, 'mood')
            self.pep_dict['mood_text'] = app.config.get_per('statusmsg',
                '_last_' + self.show, 'mood_text')
        else:
            self.title_text = _('Status Message')
        self.dialog.set_title(self.title_text)

        message_textview = self.xml.get_object('message_textview')
        self.message_buffer = message_textview.get_buffer()

        if app.config.get('use_speller') and app.is_installed('GSPELL'):
            lang = app.config.get('speller_language')
            gspell_lang = Gspell.language_lookup(lang)
            if gspell_lang is None:
                AspellDictError(lang)
            else:
                spell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(
                    self.message_buffer)
                spell_buffer.set_spell_checker(Gspell.Checker.new(gspell_lang))
                spell_view = Gspell.TextView.get_from_gtk_text_view(
                    message_textview)
                spell_view.set_inline_spell_checking(True)
                spell_view.set_enable_language_menu(True)

        self.message_buffer.connect('changed', self.on_message_buffer_changed)
        if not msg:
            msg = ''
        msg = helpers.from_one_line(msg)
        self.message_buffer.set_text(msg)

        # have an empty string selectable, so user can clear msg
        self.preset_messages_dict = {'': ['', '', '', '', '', '']}
        for msg_name in app.config.get_per('statusmsg'):
            if msg_name.startswith('_last_'):
                continue
            opts = []
            for opt in ['message', 'activity', 'subactivity', 'activity_text',
                                    'mood', 'mood_text']:
                opts.append(app.config.get_per('statusmsg', msg_name, opt))
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
           ACTIVITIES:
            if 'subactivity' in self.pep_dict and self.pep_dict['subactivity'] \
            in ACTIVITIES[self.pep_dict['activity']]:
                icon_name = get_activity_icon_name(self.pep_dict['activity'],
                                                   self.pep_dict['subactivity'])
                img.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
            else:
                icon_name = get_activity_icon_name(self.pep_dict['activity'])
                img.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
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
        if 'mood' in self.pep_dict and self.pep_dict['mood'] in MOODS:
            img.set_from_icon_name('mood-%s' % self.pep_dict['mood'],
                                   Gtk.IconSize.MENU)
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
                app.config.set_per('statusmsg', '_last_' + self.show,
                    'message', msg)
                if self.show_pep:
                    app.config.set_per('statusmsg', '_last_' + self.show,
                        'activity', self.pep_dict['activity'])
                    app.config.set_per('statusmsg', '_last_' + self.show,
                        'subactivity', self.pep_dict['subactivity'])
                    app.config.set_per('statusmsg', '_last_' + self.show,
                        'activity_text', self.pep_dict['activity_text'])
                    app.config.set_per('statusmsg', '_last_' + self.show,
                        'mood', self.pep_dict['mood'])
                    app.config.set_per('statusmsg', '_last_' + self.show,
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
           event.keyval == Gdk.KEY_KP_Enter:  # catch CTRL+ENTER
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
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

        def _on_save_preset(msg_name):
            msg_text = status_message_to_save_as_preset
            msg_text_1l = helpers.to_one_line(msg_text)
            if not msg_name:  # msg_name was ''
                msg_name = msg_text_1l

            def _on_overwrite_preset():
                self.preset_messages_dict[msg_name] = [
                    msg_text, self.pep_dict.get('activity'),
                    self.pep_dict.get('subactivity'),
                    self.pep_dict.get('activity_text'),
                    self.pep_dict.get('mood'), self.pep_dict.get('mood_text')]
                app.config.set_per('statusmsg', msg_name, 'message',
                                   msg_text_1l)
                app.config.set_per('statusmsg', msg_name, 'activity',
                                   self.pep_dict.get('activity'))
                app.config.set_per('statusmsg', msg_name, 'subactivity',
                                   self.pep_dict.get('subactivity'))
                app.config.set_per('statusmsg', msg_name, 'activity_text',
                                   self.pep_dict.get('activity_text'))
                app.config.set_per('statusmsg', msg_name, 'mood',
                                   self.pep_dict.get('mood'))
                app.config.set_per('statusmsg', msg_name, 'mood_text',
                                   self.pep_dict.get('mood_text'))

            if msg_name in self.preset_messages_dict:
                NewConfirmationDialog(
                    _('Overwrite'),
                    _('Overwrite Status Message?'),
                    _('This name is already in use. Do you want to '
                      'overwrite this preset?'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       text=_('_Overwrite'),
                                       callback=_on_overwrite_preset)],
                    transient_for=self.dialog).show()
                return

            app.config.add_per('statusmsg', msg_name)
            _on_overwrite_preset()
            iter_ = self.message_liststore.append((msg_name,))
            # Select the one we just saved in combobox
            self.message_combobox.set_active_iter(iter_)

        InputDialog(
            _('Status Preset'),
            _('Save status as preset'),
            _('Please assign a name to this status message preset'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Save'),
                               callback=_on_save_preset)],
            input_str=_('New Status'),
            transient_for=self.dialog).show()

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


class SynchroniseSelectAccountDialog:
    def __init__(self, account):
        # 'account' can be None if we are about to create our first one
        if not app.account_is_available(account):
            ErrorDialog(_('You are not connected to the server'),
                _('Without a connection, you can not synchronise your contacts.'))
            raise GajimGeneralException('You are not connected to the server')
        self.account = account
        self.xml = get_builder('synchronise_select_account_dialog.ui')
        self.dialog = self.xml.get_object('synchronise_select_account_dialog')
        self.dialog.set_transient_for(get_app_window('AccountsWindow'))
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
        for remote_account in app.connections:
            if remote_account == self.account:
                # Do not show the account we're sync'ing
                continue
            iter_ = model.append()
            model.set(iter_, 0, remote_account, 1,
                app.get_hostname_from_account(remote_account))

    def on_cancel_button_clicked(self, widget):
        self.dialog.destroy()

    def on_ok_button_clicked(self, widget):
        sel = self.accounts_treeview.get_selection()
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        remote_account = model.get_value(iter_, 0)

        if not app.account_is_available(remote_account):
            ErrorDialog(_('This account is not connected to the server'),
                _('You cannot synchronize with an account unless it is connected.'))
            return

        try:
            SynchroniseSelectContactsDialog(self.account, remote_account)
        except GajimGeneralException:
            # if we showed ErrorDialog, there will not be dialog instance
            return
        self.dialog.destroy()

    @staticmethod
    def on_destroy(widget):
        del app.interface.instances['import_contacts']


class SynchroniseSelectContactsDialog:
    def __init__(self, account, remote_account):
        self.local_account = account
        self.remote_account = remote_account
        self.xml = get_builder('synchronise_select_contacts_dialog.ui')
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
        local_jid_list = app.contacts.get_contacts_jid_list(self.local_account)

        remote_jid_list = app.contacts.get_contacts_jid_list(
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
                    app.get_hostname_from_account(self.remote_account)
                remote_contact = app.contacts.get_first_contact_from_jid(
                        self.remote_account, remote_jid)
                # keep same groups and same nickname
                app.interface.roster.req_sub(self, remote_jid, message,
                    self.local_account, groups=remote_contact.groups,
                    nickname=remote_contact.name, auto_auth=True)
            iter_ = model.iter_next(iter_)
        self.dialog.destroy()


class TransformChatToMUC:
    # Keep a reference on windows so garbage collector don't restroy them
    instances = []  # type: List[TransformChatToMUC]
    def __init__(self, account, jids, preselected=None):
        """
        This window is used to trasform a one-to-one chat to a MUC. We do 2
        things: first select the server and then make a guests list
        """

        self.instances.append(self)
        self.account = account
        self.auto_jids = jids
        self.preselected_jids = preselected

        self.xml = get_builder('chat_to_muc_window.ui')
        self.window = self.xml.get_object('chat_to_muc_window')

        for widget_to_add in ('invite_button', 'cancel_button',
            'server_list_comboboxentry', 'guests_treeview', 'guests_store',
            'server_and_guests_hseparator', 'server_select_label'):
            self.__dict__[widget_to_add] = self.xml.get_object(widget_to_add)

        server_list = []
        self.servers = Gtk.ListStore(str)
        self.server_list_comboboxentry.set_model(self.servers)
        cell = Gtk.CellRendererText()
        self.server_list_comboboxentry.pack_start(cell, True)
        self.server_list_comboboxentry.add_attribute(cell, 'text', 0)

        # get the muc server of our server
        con = app.connections[account]
        service_jid = con.get_module('MUC').service_jid
        if service_jid is not None:
            server_list.append(str(service_jid))

        # add servers or recently joined groupchats
        recently_groupchat = app.config.get_per('accounts', account, 'recent_groupchats').split()
        for g in recently_groupchat:
            server = app.get_server_from_jid(g)
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

        self.guests_store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.guests_treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        # All contacts beside the following can be invited:
        #       transports, zeroconf contacts, minimized groupchats
        def invitable(contact, contact_transport=None):
            return (contact.jid not in self.auto_jids and
                contact.jid != app.get_jid_from_account(account) and
                contact.jid not in app.interface.minimized_controls[account] and
                not contact.is_transport() and
                contact_transport in ('jabber', None))

        # set jabber id and pseudos
        for account_ in app.contacts.get_accounts():
            if app.connections[account_].is_zeroconf:
                continue
            for jid in app.contacts.get_jid_list(account_):
                contact = app.contacts.get_contact_with_highest_priority(
                    account_, jid)
                contact_transport = app.get_transport_name_from_jid(jid)
                # Add contact if it can be invited
                if invitable(contact, contact_transport) and \
                contact.show not in ('offline', 'error'):
                    icon_name = get_icon_name(contact.show)
                    name = contact.name
                    if name == '':
                        name = jid.split('@')[0]
                    iter_ = self.guests_store.append([icon_name, name, jid])
                    # preselect treeview rows
                    if self.preselected_jids and jid in self.preselected_jids:
                        path = self.guests_store.get_path(iter_)
                        self.guests_treeview.get_selection().select_path(path)

        # show all
        self.window.show_all()

        self.xml.connect_signals(self)

    def on_chat_to_muc_window_destroy(self, widget):
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

        guest_list = []
        guests = self.guests_treeview.get_selection().get_selected_rows()
        for guest in guests[1]:
            iter_ = self.guests_store.get_iter(guest)
            guest_list.append(self.guests_store[iter_][2])
        for guest in self.auto_jids:
            guest_list.append(guest)
        room_jid = str(uuid.uuid4()) + '@' + server
        app.automatic_rooms[self.account][room_jid] = {}
        app.automatic_rooms[self.account][room_jid]['invities'] = guest_list
        app.automatic_rooms[self.account][room_jid]['continue_tag'] = True
        app.interface.create_groupchat(self.account, room_jid)
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()


class VoIPCallReceivedDialog:
    instances = {}   # type: Dict[Tuple[str, str], VoIPCallReceivedDialog]
    def __init__(self, account, contact_jid, sid, content_types):
        self.instances[(contact_jid, sid)] = self
        self.account = account
        self.fjid = contact_jid
        self.sid = sid
        self.content_types = content_types

        xml = get_builder('voip_call_received_dialog.ui')
        xml.connect_signals(self)

        jid = app.get_jid_without_resource(self.fjid)
        contact = app.contacts.get_first_contact_from_jid(account, jid)
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
            _('%(contact)s wants to start a %(type)s chat with you. Do you want '
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
        session = app.connections[self.account].get_module('Jingle').get_jingle_session(
            self.fjid, self.sid)
        if not session:
            dialog.destroy()
            return
        if response == Gtk.ResponseType.YES:
            #TODO: Ensure that ctrl.contact.resource == resource
            jid = app.get_jid_without_resource(self.fjid)
            ctrl = (app.interface.msg_win_mgr.get_control(self.fjid, self.account)
                or app.interface.msg_win_mgr.get_control(jid, self.account)
                or app.interface.new_chat_from_jid(self.account, jid))

            # Chat control opened, update content's status
            audio = session.get_content('audio')
            video = session.get_content('video')
            if audio and not audio.negotiated:
                ctrl.set_audio_state('connecting', self.sid)
            if video and not video.negotiated:
                video_hbox = ctrl.xml.get_object('video_hbox')
                video_hbox.set_no_show_all(False)
                if app.config.get('video_see_self'):
                    fixed = ctrl.xml.get_object('outgoing_fixed')
                    fixed.set_no_show_all(False)
                video_hbox.show_all()
                content = session.get_content('video')
                sink_other, widget_other, _ = gstreamer.create_gtk_widget()
                sink_self, widget_self, _ = gstreamer.create_gtk_widget()
                ctrl.xml.incoming_viewport.add(widget_other)
                ctrl.xml.outgoing_viewport.add(widget_self)
                content.do_setup(sink_self, sink_other)
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
