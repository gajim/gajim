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

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import ACTIVITIES
from gajim.common.const import MOODS
from gajim.common.const import PEPEventType
from gajim.common.helpers import from_one_line
from gajim.common.helpers import to_one_line
from gajim.common.helpers import remove_invalid_xml_chars
from gajim.common.i18n import _

from gajim.gtk.dialogs import TimeoutWindow
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.util import get_builder
from gajim.gtk.util import get_activity_icon_name

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

ACTIVITY_PAGELIST = [
    'doing_chores',
    'drinking',
    'eating',
    'exercising',
    'grooming',
    'having_appointment',
    'inactive',
    'relaxing',
    'talking',
    'traveling',
    'working',
]


class StatusChange(Gtk.ApplicationWindow, TimeoutWindow):
    def __init__(self, callback, account=None, show=None, show_pep=True):
        Gtk.ApplicationWindow.__init__(self)
        countdown_time = app.config.get('change_status_window_timeout')
        TimeoutWindow.__init__(self, countdown_time)
        self.set_name('StatusChange')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(400, 350)
        self.set_show_menubar(False)
        self.set_transient_for(app.interface.roster.window)
        self.title_text = _('Status Message')  # TimeoutWindow

        self.account = account
        self._callback = callback
        self._show = show
        self._show_pep = show_pep

        self._ui = get_builder('status_change_window.ui')
        self.add(self._ui.status_stack)

        self._status_message = ''
        self._pep_dict = {
            'activity': '',
            'subactivity': '',
            'mood': '',
        }
        self._get_current_status_data()
        self._preset_messages_dict = {}
        self._get_presets()

        if self._show:
            self._ui.activity_switch.set_active(self._pep_dict['activity'])
            self._ui.activity_page_button.set_sensitive(
                self._pep_dict['activity'])
            self._ui.mood_switch.set_active(self._pep_dict['mood'])
            self._ui.mood_page_button.set_sensitive(self._pep_dict['mood'])

        self._message_buffer = self._ui.message_textview.get_buffer()
        self._apply_speller()
        self._message_buffer.set_text(from_one_line(self._status_message))

        if show_pep:
            self._draw_activity()
            self._init_activities()
            self._draw_mood()
            self._init_moods()
        else:
            self._ui.pep_grid.set_no_show_all(True)
            self._ui.pep_grid.hide()

        self._message_buffer.connect('changed', self._stop_timeout)
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.show_all()
        self.run_timeout()

    def on_timeout(self):
        self._change_status()

    def _stop_timeout(self, *args):
        self.countdown_enabled = False

    def _on_key_press(self, _widget, event):
        self.countdown_enabled = False
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
                self._change_status()
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _apply_speller(self):
        if app.config.get('use_speller') and app.is_installed('GSPELL'):
            lang = app.config.get('speller_language')
            gspell_lang = Gspell.language_lookup(lang)
            if gspell_lang is None:
                gspell_lang = Gspell.language_get_default()
            spell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(
                self._message_buffer)
            spell_buffer.set_spell_checker(Gspell.Checker.new(gspell_lang))
            spell_view = Gspell.TextView.get_from_gtk_text_view(
                self._ui.message_textview)
            spell_view.set_inline_spell_checking(True)
            spell_view.set_enable_language_menu(True)

    def _get_current_status_data(self):
        '''
        Gathers status/pep data for a given account or checks if all accounts
        are synchronized. If not, no status message/pep data will be displayed.
        '''
        if self.account:
            self._status_message = app.connections[self.account].status_message
            activity_data = app.connections[self.account].pep.get(
                PEPEventType.ACTIVITY)
            mood_data = app.connections[self.account].pep.get(
                PEPEventType.MOOD)
            if activity_data:
                self._pep_dict['activity'] = activity_data.activity
                self._pep_dict['subactivity'] = activity_data.subactivity
            if mood_data:
                self._pep_dict['mood'] = mood_data.mood
        else:
            status_messages = []
            activities = []
            subactivities = []
            moods = []
            for account in app.connections:
                status_messages.append(app.connections[account].status_message)
                activity_data = app.connections[account].pep.get(
                    PEPEventType.ACTIVITY)
                mood_data = app.connections[account].pep.get(PEPEventType.MOOD)
                if activity_data:
                    activities.append(activity_data.activity)
                    subactivities.append(activity_data.subactivity)
                if mood_data:
                    moods.append(mood_data.mood)
            equal_messages = all(x == status_messages[0] for x in
                                 status_messages)
            equal_activities = all(x == activities[0] for x in activities)
            equal_subactivities = all(x == subactivities[0] for x in
                                      subactivities)
            equal_moods = all(x == moods[0] for x in moods)
            if equal_messages:
                self._status_message = status_messages[0]
            if activities and equal_activities:
                self._pep_dict['activity'] = activities[0]
            if subactivities and equal_subactivities:
                self._pep_dict['subactivity'] = subactivities[0]
            if moods and equal_moods:
                self._pep_dict['mood'] = moods[0]

    def _get_presets(self):
        self._preset_messages_dict = {}
        for msg_name in app.config.get_per('statusmsg'):
            if msg_name.startswith('_last_'):
                continue
            opts = []
            for opt in ['message', 'activity', 'subactivity', 'mood']:
                opts.append(app.config.get_per('statusmsg', msg_name, opt))
            opts[0] = from_one_line(opts[0])
            self._preset_messages_dict[msg_name] = opts
        self._build_preset_popover()

    def _build_preset_popover(self):
        child = self._ui.preset_popover.get_children()
        if child:
            self._ui.preset_popover.remove(child[0])

        preset_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        preset_box.get_style_context().add_class('margin-3')
        self._ui.preset_popover.add(preset_box)

        for preset in self._preset_messages_dict:
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

            preset_button = Gtk.Button()
            preset_button.set_name(preset)
            preset_button.set_relief(Gtk.ReliefStyle.NONE)
            preset_button.set_hexpand(True)
            preset_button.add(Gtk.Label(label=preset, halign=Gtk.Align.START))
            preset_button.connect('clicked', self._on_preset_select)
            button_box.add(preset_button)

            remove_button = Gtk.Button()
            remove_button.set_name(preset)
            remove_button.set_relief(Gtk.ReliefStyle.NONE)
            remove_button.set_halign(Gtk.Align.END)
            remove_button.add(Gtk.Image.new_from_icon_name(
                'edit-delete-symbolic', Gtk.IconSize.MENU))
            remove_button.connect('clicked', self._on_preset_remove)
            button_box.add(remove_button)
            preset_box.add(button_box)
            preset_box.show_all()

    def _init_activities(self):
        radio_btns = {}
        group = None

        for category in ACTIVITIES:
            icon_name = get_activity_icon_name(category)
            item = self._ui.get_object(category + '_image')
            item.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
            item.set_tooltip_text(ACTIVITIES[category]['category'])

            category_box = self._ui.get_object(category + '_box')

            # Other
            act = category + '_other'
            if group:
                radio_btns[act] = Gtk.RadioButton()
                radio_btns[act].join_group(group)
            else:
                radio_btns[act] = group = Gtk.RadioButton()

            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                               spacing=6)
            icon_box.pack_start(icon, False, False, 0)
            label = Gtk.Label(
                label='<b>%s</b>' % ACTIVITIES[category]['category'])
            label.set_use_markup(True)
            icon_box.pack_start(label, False, False, 0)
            radio_btns[act].add(icon_box)
            radio_btns[act].join_group(self._ui.no_activity_button)
            radio_btns[act].connect(
                'toggled', self._on_activity_toggled, [category, 'other'])
            category_box.pack_start(radio_btns[act], False, False, 0)

            activities = list(ACTIVITIES[category].keys())
            activities.sort()
            for activity in activities:
                if activity == 'category':
                    continue

                act = category + '_' + activity

                if group:
                    radio_btns[act] = Gtk.RadioButton()
                    radio_btns[act].join_group(group)
                else:
                    radio_btns[act] = group = Gtk.RadioButton()

                icon_name = get_activity_icon_name(category, activity)
                icon = Gtk.Image.new_from_icon_name(
                    icon_name, Gtk.IconSize.MENU)
                label = Gtk.Label(label=ACTIVITIES[category][activity])
                icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                   spacing=6)
                icon_box.pack_start(icon, False, False, 0)
                icon_box.pack_start(label, False, False, 0)
                radio_btns[act].join_group(self._ui.no_activity_button)
                radio_btns[act].connect('toggled', self._on_activity_toggled,
                                        [category, activity])
                radio_btns[act].add(icon_box)
                category_box.pack_start(radio_btns[act], False, False, 0)

        if not self._pep_dict['activity']:
            self._ui.no_activity_button.set_active(True)

        if self._pep_dict['activity'] in ACTIVITIES:
            if self._pep_dict['subactivity'] not in ACTIVITIES[
                    self._pep_dict['activity']]:
                self._pep_dict['subactivity'] = 'other'

            radio_btns[self._pep_dict['activity'] + '_' + self._pep_dict[
                'subactivity']].set_active(True)

            self._ui.activity_notebook.set_current_page(
                ACTIVITY_PAGELIST.index(self._pep_dict['activity']))

    def _draw_activity(self):
        if self._pep_dict['activity'] in ACTIVITIES:
            if (self._pep_dict['subactivity'] in
                    ACTIVITIES[self._pep_dict['activity']]):
                icon_name = get_activity_icon_name(
                    self._pep_dict['activity'],
                    self._pep_dict['subactivity'])
                self._ui.activity_image.set_from_icon_name(
                    icon_name, Gtk.IconSize.MENU)
                self._ui.activity_button_label.set_text(
                    ACTIVITIES[self._pep_dict['activity']][
                        self._pep_dict['subactivity']])
            else:
                icon_name = get_activity_icon_name(self._pep_dict['activity'])
                self._ui.activity_image.set_from_icon_name(
                    icon_name, Gtk.IconSize.MENU)
                self._ui.activity_button_label.set_text(
                    ACTIVITIES[self._pep_dict['activity']]['category'])
        else:
            self._ui.activity_image.set_from_pixbuf(None)
            self._ui.activity_button_label.set_text(_('No activity'))

    def _init_moods(self):
        self._ui.no_mood_button.set_mode(False)
        self._ui.no_mood_button.connect(
            'clicked', self._on_mood_button_clicked, None)

        x_position = 1
        y_position = 0
        mood_buttons = {}

        # Order them first
        moods = []
        for mood in MOODS:
            moods.append(mood)
        moods.sort()

        for mood in moods:
            image = Gtk.Image.new_from_icon_name(
                'mood-%s' % mood, Gtk.IconSize.MENU)
            mood_buttons[mood] = Gtk.RadioButton()
            mood_buttons[mood].join_group(self._ui.no_mood_button)
            mood_buttons[mood].set_mode(False)
            mood_buttons[mood].add(image)
            mood_buttons[mood].set_relief(Gtk.ReliefStyle.NONE)
            mood_buttons[mood].set_tooltip_text(MOODS[mood])
            mood_buttons[mood].connect(
                'clicked', self._on_mood_button_clicked, mood)
            self._ui.moods_grid.attach(
                mood_buttons[mood], x_position, y_position, 1, 1)

            # Calculate the next position
            x_position += 1
            if x_position >= 11:
                x_position = 0
                y_position += 1

        if self._pep_dict['mood'] in MOODS:
            mood_buttons[self._pep_dict['mood']].set_active(True)
            self._ui.mood_label.set_text(MOODS[self._pep_dict['mood']])
        else:
            self._ui.mood_label.set_text(_('No mood selected'))

    def _draw_mood(self):
        if self._pep_dict['mood'] in MOODS:
            self._ui.mood_image.set_from_icon_name(
                'mood-%s' % self._pep_dict['mood'], Gtk.IconSize.MENU)
            self._ui.mood_button_label.set_text(
                MOODS[self._pep_dict['mood']])
        else:
            self._ui.mood_image.set_from_pixbuf(None)
            self._ui.mood_button_label.set_text(_('No mood'))

    def _on_preset_select(self, widget):
        self.countdown_enabled = False
        self._ui.preset_popover.popdown()
        name = widget.get_name()
        self._message_buffer.set_text(self._preset_messages_dict[name][0])
        self._pep_dict['activity'] = self._preset_messages_dict[name][1]
        self._pep_dict['subactivity'] = self._preset_messages_dict[name][2]
        self._pep_dict['mood'] = self._preset_messages_dict[name][3]
        self._draw_activity()
        self._draw_mood()

        self._ui.activity_switch.set_active(self._pep_dict['activity'])
        self._ui.activity_page_button.set_sensitive(self._pep_dict['activity'])
        self._ui.mood_switch.set_active(self._pep_dict['mood'])
        self._ui.mood_page_button.set_sensitive(self._pep_dict['mood'])

    def _on_preset_remove(self, widget):
        self.countdown_enabled = False
        name = widget.get_name()
        app.config.del_per('statusmsg', name)
        self._get_presets()

    def _on_save_as_preset_clicked(self, _widget):
        self.countdown_enabled = False
        start_iter, finish_iter = self._message_buffer.get_bounds()
        message_text = self._message_buffer.get_text(
            start_iter, finish_iter, True)

        def _on_save_preset(preset_name):
            msg_text_one_line = to_one_line(message_text)
            if not preset_name:
                preset_name = msg_text_one_line

            def _on_set_config():
                activity = ''
                subactivity = ''
                mood = ''
                if self._ui.activity_switch.get_active():
                    activity = self._pep_dict['activity']
                    subactivity = self._pep_dict['subactivity']
                if self._ui.mood_switch.get_active():
                    mood = self._pep_dict['mood']
                app.config.set_per('statusmsg', preset_name, 'message',
                                   msg_text_one_line)
                app.config.set_per('statusmsg', preset_name, 'activity',
                                   activity)
                app.config.set_per('statusmsg', preset_name, 'subactivity',
                                   subactivity)
                app.config.set_per('statusmsg', preset_name, 'mood', mood)
                self._get_presets()

            if preset_name in self._preset_messages_dict:
                NewConfirmationDialog(
                    _('Overwrite'),
                    _('Overwrite Status Message?'),
                    _('This name is already in use. Do you want to '
                      'overwrite this preset?'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       text=_('_Overwrite'),
                                       callback=_on_set_config)],
                    transient_for=self).show()
                return

            app.config.add_per('statusmsg', preset_name)
            _on_set_config()

        InputDialog(
            _('Status Preset'),
            _('Save status as preset'),
            _('Please assign a name to this status message preset'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Save'),
                               callback=_on_save_preset)],
            input_str=_('New Status'),
            transient_for=self).show()

    def _on_activity_page_clicked(self, _widget):
        self.countdown_enabled = False
        self._ui.status_stack.set_visible_child_full(
            'activity-page',
            Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_activity_toggled(self, widget, data):
        if widget.get_active():
            self._pep_dict['activity'] = data[0]
            self._pep_dict['subactivity'] = data[1]

    def _on_no_activity_toggled(self, _widget):
        self._pep_dict['activity'] = ''
        self._pep_dict['subactivity'] = ''

    def _on_mood_page_clicked(self, _widget):
        self.countdown_enabled = False
        self._ui.status_stack.set_visible_child_full(
            'mood-page',
            Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_mood_button_clicked(self, _widget, data):
        if data:
            self._ui.mood_label.set_text(MOODS[data])
        else:
            self._ui.mood_label.set_text(_('No mood selected'))
        self._pep_dict['mood'] = data

    def _on_back_clicked(self, _widget):
        self._ui.status_stack.set_visible_child_full(
            'status-page',
            Gtk.StackTransitionType.SLIDE_RIGHT)
        self._draw_activity()
        self._draw_mood()

    def _on_activity_switch(self, switch, *args):
        self.countdown_enabled = False
        self._ui.activity_page_button.set_sensitive(switch.get_active())

    def _on_mood_switch(self, switch, *args):
        self.countdown_enabled = False
        self._ui.mood_page_button.set_sensitive(switch.get_active())

    def _send_user_mood(self):
        mood = None
        if self._ui.mood_switch.get_active():
            mood = self._pep_dict['mood']

        for client in app.get_available_clients(self.account):
            client.set_user_mood(mood)

    def _send_user_activity(self):
        activity = None
        if self._ui.activity_switch.get_active():
            activity = (self._pep_dict['activity'],
                        self._pep_dict['subactivity'])

        for client in app.get_available_clients(self.account):
            client.set_user_activity(activity)

    def _change_status(self, *args):
        beg, end = self._message_buffer.get_bounds()
        message = self._message_buffer.get_text(beg, end, True).strip()
        message = remove_invalid_xml_chars(message)

        self._send_user_activity()
        self._send_user_mood()

        self._callback(message)
        self.destroy()
