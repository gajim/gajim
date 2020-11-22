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
from enum import IntEnum

from gi.repository import Gtk

from nbxmpp.const import AdHocAction
from nbxmpp.modules import dataforms
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import to_user_string

from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util import find_widget
from gajim.gtk.util import MultiLineLabel

log = logging.getLogger('gajim.gtk.adhoc')


class Page(IntEnum):
    REQUEST = 0
    EXECUTE = 1
    COMMANDS = 2
    STAGE = 3
    COMPLETED = 4
    ERROR = 5


class AdHocCommand(Gtk.Assistant):
    def __init__(self, account, jid=None):
        Gtk.Assistant.__init__(self)

        self._con = app.connections[account]
        self._account = account
        self._destroyed = False

        self.set_application(app.app)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.set_default_size(600, 400)
        self.get_style_context().add_class('dialog-margin')

        self._add_page(Request())
        self._add_page(ExecuteCommand())
        self._add_page(Commands())
        self._add_page(Stage())
        self._add_page(Completed())
        self._add_page(Error())

        self.connect('prepare', self._on_page_change)
        self.connect('cancel', self._on_cancel)
        self.connect('close', self._on_cancel)
        self.connect('destroy', self._on_destroy)

        self._remove_sidebar()

        self._buttons = {}
        self._add_custom_buttons()

        self.show()
        self._con.get_module('AdHocCommands').request_command_list(
            jid, callback=self._received_command_list)

    def _add_custom_buttons(self):
        action_area = find_widget('action_area', self)
        for button in list(action_area.get_children()):
            self.remove_action_widget(button)

        cancel = ActionButton(_('Cancel'), AdHocAction.CANCEL)
        cancel.connect('clicked', self._abort)
        self._buttons['cancel'] = cancel
        self.add_action_widget(cancel)

        complete = ActionButton(_('Finish'), AdHocAction.COMPLETE)
        complete.connect('clicked', self._execute_action)
        self._buttons['complete'] = complete
        self.add_action_widget(complete)

        commands = Gtk.Button(label=_('Commands'))
        commands.connect('clicked',
                         lambda *args: self.set_current_page(Page.COMMANDS))
        self._buttons['commands'] = commands
        self.add_action_widget(commands)

        next_ = ActionButton(_('Next'), AdHocAction.NEXT)
        next_.connect('clicked', self._execute_action)
        self._buttons['next'] = next_
        self.add_action_widget(next_)

        prev = ActionButton(_('Previous'), AdHocAction.PREV)
        prev.connect('clicked', self._execute_action)
        self._buttons['prev'] = prev
        self.add_action_widget(prev)

        execute = ActionButton(_('Execute'), AdHocAction.EXECUTE)
        execute.connect('clicked', self._execute_action)
        self._buttons['execute'] = execute
        self.add_action_widget(execute)

    def _set_button_visibility(self, page):
        for action, button in self._buttons.items():
            button.hide()
            if action in ('next', 'prev', 'complete'):
                button.remove_default()

        if page == Page.COMMANDS:
            self._buttons['execute'].show()

        elif page == Page.STAGE:
            self._buttons['cancel'].show()
            stage_page = self.get_nth_page(page)
            if not stage_page.actions:
                self._buttons['complete'].show()
                self._buttons['complete'].make_default()
            else:
                for action in stage_page.actions:
                    button = self._buttons.get(action.value)
                    if button is not None:
                        if button.action == stage_page.default:
                            button.make_default()
                        button.show()

        elif page == Page.ERROR:
            error_page = self.get_nth_page(page)
            if error_page.show_command_button:
                self._buttons['commands'].show()

        elif page == Page.COMPLETED:
            self._buttons['commands'].show()

    def _add_page(self, page):
        self.append_page(page)
        self.set_page_type(page, page.type_)
        self.set_page_title(page, page.title)
        self.set_page_complete(page, page.complete)

    def execute_action(self):
        self._execute_action(self._buttons['execute'])

    def _execute_action(self, button):
        action = button.action
        current_page = self.get_current_page()
        dataform = None
        if action == AdHocAction.EXECUTE:
            command = self.get_nth_page(current_page).get_selected_command()
            if command is None:
                # The commands page should not show if there are no commands,
                # but if for some reason it does don’t fail horribly
                return
        else:
            command, dataform = self.get_nth_page(current_page).stage_data
            if action == AdHocAction.PREV:
                dataform = None

        self.set_current_page(Page.EXECUTE)
        if current_page == Page.STAGE:
            self.get_nth_page(current_page).clear()
        self._con.get_module('AdHocCommands').execute_command(
            command,
            action=action,
            dataform=dataform,
            callback=self._received_stage)

    def _abort(self, *args):
        if self.get_current_page() == Page.STAGE:
            command = self.get_nth_page(Page.STAGE).stage_data[0]
            self._con.get_module('AdHocCommands').execute_command(
                command, AdHocAction.CANCEL)
            self.set_current_page(Page.COMMANDS)

    def _received_command_list(self, task):
        try:
            commands = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._set_error(to_user_string(error), False)
            return

        if not commands:
            self._set_error(_('No commands available'), False)
            return

        self.get_nth_page(Page.COMMANDS).add_commands(commands)
        self.set_current_page(Page.COMMANDS)

    def _received_stage(self, task):
        try:
            stage = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._set_error(to_user_string(error), True)
            return

        page = Page.STAGE
        if stage.is_completed:
            page = Page.COMPLETED

        stage_page = self.get_nth_page(page)
        stage_page.process_stage(stage)
        self.set_current_page(page)

    def _set_error(self, text, show_command_button):
        self.get_nth_page(Page.ERROR).set_text(text)
        self.get_nth_page(Page.ERROR).show_command_button = show_command_button
        self.set_current_page(Page.ERROR)

    def set_stage_complete(self, is_valid):
        self._buttons['next'].set_sensitive(is_valid)
        self._buttons['complete'].set_sensitive(is_valid)

    def _remove_sidebar(self):
        main_box = self.get_children()[0]
        sidebar = main_box.get_children()[0]
        main_box.remove(sidebar)

    def _on_page_change(self, _assistant, _page):
        self._set_button_visibility(self.get_current_page())

    def _on_cancel(self, _widget):
        self.destroy()

    def _on_destroy(self, *args):
        self._destroyed = True


class Request(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Request Command List')
    complete = False

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        spinner = Gtk.Spinner()
        self.pack_start(spinner, True, True, 0)
        spinner.start()
        self.show_all()


class ExecuteCommand(Request):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Executing…')
    complete = False


class Commands(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Command List')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
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
        self.get_toplevel().execute_action()

    def add_commands(self, commands):
        self._store.clear()
        self._commands = {}
        for command in commands:
            key = '%s:%s' % (command.jid, command.node)
            self._commands[key] = command
            self._store.append((command.name, key))

    def get_selected_command(self):
        model, treeiter = self._treeview.get_selection().get_selected()
        key = model[treeiter][1]
        return self._commands[key]


class Stage(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Settings')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
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
        self._dataform_widget = DataFormWidget(form)
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
        self.get_toplevel().set_stage_complete(is_valid)


class Completed(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Finished')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self._notes = []
        self._dataform_widget = None

        icon = Gtk.Image.new_from_icon_name('object-select-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('success-color')
        icon.show()

        label = Gtk.Label(label='Finished')
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


class Error(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Execution failed')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_homogeneous(True)
        self._show_command_button = False

        icon = Gtk.Image.new_from_icon_name('dialog-error-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('error-color')
        icon.set_valign(Gtk.Align.END)
        self._label = Gtk.Label()
        self._label.get_style_context().add_class('bold16')
        self._label.set_valign(Gtk.Align.START)

        self.add(icon)
        self.add(self._label)
        self.show_all()

    def set_text(self, text):
        self._label.set_text(text)

    @property
    def show_command_button(self):
        return self._show_command_button

    @show_command_button.setter
    def show_command_button(self, value):
        self._show_command_button = value


class ActionButton(Gtk.Button):
    def __init__(self, label, action):
        Gtk.Button.__init__(self, label=label)
        self.action = action

        if action == AdHocAction.CANCEL:
            self.get_style_context().add_class('destructive-action')
        if action == AdHocAction.EXECUTE:
            self.get_style_context().add_class('suggested-action')

    def make_default(self):
        self.get_style_context().add_class('suggested-action')

    def remove_default(self):
        self.get_style_context().remove_class('suggested-action')
