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

import logging

from gi.repository import Gtk
from gi.repository import GObject

from nbxmpp.const import AdHocAction
from nbxmpp.modules import dataforms
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import to_user_string

from .dataform import DataFormWidget
from .util import MultiLineLabel

from .assistant import Assistant
from .assistant import Page
from .assistant import ErrorPage

log = logging.getLogger('gajim.gui.adhoc')


class AdHocCommand(Assistant):
    def __init__(self, account, jid=None):
        Assistant.__init__(self, width=600, height=500)

        self._destroyed = False

        self._client = app.get_client(account)
        self._account = account
        self._jid = jid

        self.add_button('complete', _('Complete'), complete=True,
                        css_class='suggested-action')
        self.add_button('next', _('Next'), complete=True,
                        css_class='suggested-action')
        self.add_button('prev', _('Previous'))
        self.add_button('cancel', _('Cancel'),
                        css_class='destructive-action')
        self.add_button('commands', _('Commands'),
                        css_class='suggested-action')
        self.add_button('execute', _('Execute'), css_class='suggested-action')

        self.add_pages({
            'commands': Commands(),
            'stage': Stage(),
            'completed': Completed(),
            'error': Error()
        })

        self._progress = self.add_default_page('progress')

        self.get_page('commands').connect('execute', self._on_execute)

        self.connect('button-clicked', self._on_button_clicked)
        self.connect('destroy', self._on_destroy)

        self._client.get_module('AdHocCommands').request_command_list(
            jid, callback=self._received_command_list)

        self.show_all()

    def _received_command_list(self, task):
        try:
            commands = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._set_error(to_user_string(error), False)
            return

        if not commands:
            self._set_error(_('No commands available'), False)
            return

        self.get_page('commands').add_commands(commands)
        self.show_page('commands')

    def _received_stage(self, task):
        try:
            stage = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._set_error(to_user_string(error), True)
            return

        page_name = 'stage'
        if stage.is_completed:
            page_name = 'completed'

        page = self.get_page(page_name)
        page.process_stage(stage)
        self.show_page(page_name)

    def _set_error(self, text, show_command_button):
        self.get_page('error').set_show_commands_button(show_command_button)
        self.get_page('error').set_text(text)
        self.show_page('error')

    def _on_destroy(self, *args):
        pass

    def _on_button_clicked(self, _assistant, button_name):
        if button_name == 'commands':
            self.show_page('commands')

        elif button_name == 'execute':
            self._on_execute()

        elif button_name in ('prev', 'next', 'complete'):
            self._on_stage_action(AdHocAction(button_name))

        elif button_name == 'cancel':
            self._on_cancel()

        else:
            raise ValueError('Invalid button name: %s' % button_name)

    def _on_stage_action(self, action):
        command, dataform = self.get_page('stage').stage_data
        if action == AdHocAction.PREV:
            dataform = None

        self._client.get_module('AdHocCommands').execute_command(
            command,
            action=action,
            dataform=dataform,
            callback=self._received_stage)

        self.show_page('progress')
        self.get_page('stage').clear()

    def _on_execute(self, *args):
        command = self.get_page('commands').get_selected_command()
        if command is None:
            return

        self._client.get_module('AdHocCommands').execute_command(
            command,
            action=AdHocAction.EXECUTE,
            callback=self._received_stage)

        self.show_page('progress')

    def _on_cancel(self):
        command, _ = self.get_page('stage').stage_data
        self._client.get_module('AdHocCommands').execute_command(
            command, AdHocAction.CANCEL)
        self.show_page('commands')


class Commands(Page):

    __gsignals__ = {
        'execute': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = True
        self.title = _('Command List')

        self._commands = {}
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.get_style_context().add_class('adhoc-scrolled')
        self._scrolled.set_max_content_height(400)
        self._scrolled.set_max_content_width(400)
        self._scrolled.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)
        self._treeview = Gtk.TreeView()
        self._treeview.get_style_context().add_class('adhoc-treeview')
        self._store = Gtk.ListStore(str, str)
        self._treeview.set_model(self._store)
        column = Gtk.TreeViewColumn(_('Commands'))
        column.set_expand(True)
        self._treeview.append_column(column)
        renderer = Gtk.CellRendererText()
        column.pack_start(renderer, True)
        column.add_attribute(renderer, 'text', 0)

        self._treeview.connect('row-activated', self._on_row_activate)
        self._treeview.set_search_equal_func(self._search_func)

        self._scrolled.add(self._treeview)
        self.pack_start(self._scrolled, True, True, 0)
        self.show_all()

    @staticmethod
    def _search_func(model, _column, search_text, iter_):
        return search_text.lower() not in model[iter_][0].lower()

    def _on_row_activate(self, _tree_view, _path, _column):
        self.emit('execute')

    def add_commands(self, commands):
        self._store.clear()
        self._commands = {}
        for command in commands:
            key = '%s:%s' % (command.jid, command.node)
            self._commands[key] = command
            self._store.append((command.name, key))

    def get_selected_command(self):
        model, treeiter = self._treeview.get_selection().get_selected()
        if treeiter is None:
            return None
        key = model[treeiter][1]
        return self._commands[key]

    def get_visible_buttons(self):
        return ['execute']


class Stage(Page):
    def __init__(self):
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = False
        self.title = _('Stage')

        self._dataform_widget = None
        self._notes = []
        self._last_stage_data = None
        self.default = None
        self.show_all()

    @property
    def stage_data(self):
        return self._last_stage_data, self._dataform_widget.get_submit_form()

    @property
    def actions(self):
        return self._last_stage_data.actions

    def clear(self):
        self._show_form(None)
        self._show_notes(None)
        self._last_stage_data = None

    def process_stage(self, stage_data):
        self._last_stage_data = stage_data
        self._show_notes(stage_data.notes)
        self._show_form(stage_data.data)
        self.default = stage_data.default

    def _show_form(self, form):
        if self._dataform_widget is not None:
            self.remove(self._dataform_widget)
            self._dataform_widget.destroy()
        if form is None:
            return
        form = dataforms.extend_form(node=form)
        options = {'entry-activates-default': True}
        self._dataform_widget = DataFormWidget(form, options)
        self._dataform_widget.connect('is-valid', self._on_is_valid)
        self._dataform_widget.validate()
        self._dataform_widget.show_all()
        self.add(self._dataform_widget)

    def _show_notes(self, notes):
        for note in self._notes:
            self.remove(note)
        self._notes = []

        if notes is None:
            return

        for note in notes:
            label = Gtk.Label(label=note.text)
            label.show()
            self._notes.append(label)
            self.add(label)

    def _on_is_valid(self, _widget, is_valid):
        self.complete = is_valid
        self.update_page_complete()

    def get_visible_buttons(self):
        actions = list(map(lambda action: action.value,
                           self._last_stage_data.actions))
        actions.append('cancel')
        return actions

    def get_default_button(self):
        if self._last_stage_data.default is None:
            return None
        return self._last_stage_data.default.value


class Completed(Page):
    def __init__(self):
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = True
        self.title = _('Completed')

        self._notes = []
        self._dataform_widget = None

        icon = Gtk.Image.new_from_icon_name('object-select-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('success-color')
        icon.show()

        label = Gtk.Label(label='Completed')
        label.show()

        self._icon_text = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._icon_text.set_spacing(12)
        self._icon_text.set_halign(Gtk.Align.CENTER)
        self._icon_text.add(icon)
        self._icon_text.add(label)
        self.add(self._icon_text)

        self.show_all()

    def process_stage(self, stage_data):
        self._show_notes(stage_data.notes)
        self._show_form(stage_data.data)
        self._show_icon_text(stage_data.data is None)

    def _show_icon_text(self, show):
        if show:
            self.set_valign(Gtk.Align.CENTER)
            self._icon_text.show_all()
        else:
            self.set_valign(Gtk.Align.FILL)
            self._icon_text.hide()

    def _show_form(self, form):
        if self._dataform_widget is not None:
            self.remove(self._dataform_widget)
            self._dataform_widget.destroy()
        if form is None:
            return

        form = dataforms.extend_form(node=form)

        self._dataform_widget = DataFormWidget(
            form, options={'read-only': True})
        self._dataform_widget.show_all()
        self.add(self._dataform_widget)

    def _show_notes(self, notes):
        for note in self._notes:
            self.remove(note)
        self._notes = []

        for note in notes:
            label = MultiLineLabel(label=note.text)
            label.set_justify(Gtk.Justification.CENTER)
            label.show()
            self._notes.append(label)
            self.add(label)

    def get_visible_buttons(self):
        return ['commands']


class Error(ErrorPage):
    def __init__(self):
        ErrorPage.__init__(self)

        self._show_commands_button = False
        self.set_heading(_('An error occurred'))

    def set_show_commands_button(self, value):
        self._show_commands_button = value

    def get_visible_buttons(self):
        if self._show_commands_button:
            return ['commands']
        return None
