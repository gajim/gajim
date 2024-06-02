# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.const import AdHocAction
from nbxmpp.const import AdHocNoteType
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules import dataforms
from nbxmpp.modules.dataforms import MultipleDataForm
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.simplexml import Node
from nbxmpp.structs import AdHocCommand
from nbxmpp.structs import AdHocCommandNote
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.assistant import ProgressPage
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util import ensure_not_destroyed
from gajim.gtk.util import MultiLineLabel

log = logging.getLogger('gajim.gtk.adhoc')


class AdHocCommands(Assistant):
    def __init__(self, account: str, jids: list[str]) -> None:
        Assistant.__init__(self, width=600, height=500)
        self.account = account
        self.jids = jids
        self.jid = self.jids[0]  # TODO: Add resource chooser

        self._destroyed = False

        self._client = app.get_client(account)

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
            'request': RequestCommandList(),
            'commands': Commands(),
            'stage': Stage(),
            'completed': Completed(),
            'error': Error(),
            'executing': Executing(),
        })

        self.get_page('commands').connect('execute', self._on_execute)

        self.connect('button-clicked', self._on_button_clicked)
        self.connect('destroy', self._on_destroy)

        self._client.get_module('AdHocCommands').request_command_list(
            self.jid, callback=self._received_command_list)
        self.show_all()

    @ensure_not_destroyed
    def _received_command_list(self, task: Task) -> None:
        try:
            commands = cast(list[AdHocCommand] | None, task.finish())
        except (StanzaError, MalformedStanzaError) as error:
            self._set_error(to_user_string(error), False)
            return

        if not commands:
            self._set_error(_('No commands available'), False)
            return

        commands_page = cast(Commands, self.get_page('commands'))
        commands_page.add_commands(commands)
        self.show_page('commands')

    @ensure_not_destroyed
    def _received_stage(self, task: Task) -> None:
        try:
            stage = cast(AdHocCommand, task.finish())
        except (StanzaError, MalformedStanzaError) as error:
            self._set_error(to_user_string(error), True)
            return

        page_name = 'stage'
        if stage.is_completed:
            page_name = 'completed'

        page = cast(Stage | Completed, self.get_page(page_name))
        page.process_stage(stage)
        self.show_page(page_name)

    def _set_error(self, text: str, show_command_button: bool) -> None:
        error_page = cast(Error, self.get_page('error'))
        error_page.set_show_commands_button(show_command_button)
        error_page.set_text(text)
        self.show_page('error')

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._destroyed = True

    def _on_button_clicked(self,
                           _assistant: AdHocCommands,
                           button_name: str
                           ) -> None:
        if button_name == 'commands':
            self._client.get_module('AdHocCommands').request_command_list(
                self.jid, callback=self._received_command_list)

        elif button_name == 'execute':
            self._on_execute()

        elif button_name in ('prev', 'next', 'complete'):
            self._on_stage_action(AdHocAction(button_name))

        elif button_name == 'cancel':
            self._on_cancel()

        else:
            raise ValueError('Invalid button name: %s' % button_name)

    def _on_stage_action(self, action: AdHocAction) -> None:
        stage_page = cast(Stage, self.get_page('stage'))
        command, dataform = stage_page.stage_data
        if action == AdHocAction.PREV:
            dataform = None

        self._client.get_module('AdHocCommands').execute_command(
            command,
            action=action,
            dataform=dataform,
            callback=self._received_stage)

        self.show_page('executing')
        stage_page = cast(Stage, self.get_page('stage'))
        stage_page.clear()

    def _on_execute(self, *args: Any) -> None:
        commands_page = cast(Commands, self.get_page('commands'))
        command = commands_page.get_selected_command()
        if command is None:
            return

        self._client.get_module('AdHocCommands').execute_command(
            command,
            action=AdHocAction.EXECUTE,
            callback=self._received_stage)

        self.show_page('executing')

    def _on_cancel(self) -> None:
        stage_page = cast(Stage, self.get_page('stage'))
        command, _ = stage_page.stage_data
        self._client.get_module('AdHocCommands').execute_command(
            command, AdHocAction.CANCEL)
        self.show_page('commands')


class Commands(Page):

    __gsignals__ = {
        'execute': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = True
        self.title = _('Command List')

        self._commands: dict[str, AdHocCommand] = {}
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.get_style_context().add_class('gajim-scrolled')
        self._scrolled.set_max_content_height(400)
        self._scrolled.set_max_content_width(400)
        self._scrolled.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)
        self._treeview = Gtk.TreeView()
        self._treeview.get_style_context().add_class('gajim-treeview')
        self._store = Gtk.ListStore(str, str)
        self._treeview.set_model(self._store)
        column = Gtk.TreeViewColumn(
            _('Commands'),
            Gtk.CellRendererText(),
            text=0)
        column.set_expand(True)
        self._treeview.append_column(column)

        self._treeview.connect('row-activated', self._on_row_activate)
        self._treeview.set_search_equal_func(self._search_func)

        self._scrolled.add(self._treeview)
        self.pack_start(self._scrolled, True, True, 0)
        self.show_all()

    @staticmethod
    def _search_func(model: Gtk.TreeModel,
                     _column: int,
                     search_text: str,
                     iter_: Gtk.TreeIter
                     ) -> bool:
        return search_text.lower() not in model[iter_][0].lower()

    def _on_row_activate(self,
                         _tree_view: Gtk.TreeView,
                         _path: Gtk.TreePath,
                         _column: Gtk.TreeViewColumn
                         ) -> None:
        self.emit('execute')

    def add_commands(self, commands: list[AdHocCommand]) -> None:
        self._store.clear()
        self._commands = {}
        for command in commands:
            key = f'{command.jid}:{command.node}'
            self._commands[key] = command
            self._store.append((command.name, key))

    def get_selected_command(self) -> AdHocCommand | None:
        model, treeiter = self._treeview.get_selection().get_selected()
        if treeiter is None:
            return None
        key = model[treeiter][1]
        return self._commands[key]

    def get_visible_buttons(self) -> list[str]:
        return ['execute']


class Stage(Page):
    def __init__(self) -> None:
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = False
        self.title = _('Stage')

        self._dataform_widget = None
        self._notes: list[Gtk.Label] = []
        self._last_stage_data: AdHocCommand | None = None
        self.default = None
        self.show_all()

    @property
    def stage_data(self) -> tuple[AdHocCommand,
                                  SimpleDataForm | MultipleDataForm]:
        assert self._last_stage_data is not None
        assert self._dataform_widget is not None
        return self._last_stage_data, self._dataform_widget.get_submit_form()

    @property
    def actions(self) -> set[AdHocAction] | None:
        assert self._last_stage_data is not None
        return self._last_stage_data.actions

    def clear(self) -> None:
        self._show_form(None)
        self._show_notes(None)
        self._last_stage_data = None

    def process_stage(self, stage_data: AdHocCommand) -> None:
        self._last_stage_data = stage_data
        self._show_notes(stage_data.notes)
        self._show_form(stage_data.data)
        self.default = stage_data.default

    def _show_form(self, form: Node | None) -> None:
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

    def _show_notes(self, notes: list[AdHocCommandNote] | None):
        for note in self._notes:
            self.remove(note)
        self._notes = []

        if notes is None:
            return

        for note in notes:
            label = Gtk.Label(
                label=note.text,
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR)
            label.show()
            self._notes.append(label)
            self.add(label)

    def _on_is_valid(self, _widget: DataFormWidget, is_valid: bool) -> None:
        self.complete = is_valid
        self.update_page_complete()

    def get_visible_buttons(self) -> list[str]:
        return [action.value for action in self._last_stage_data.actions]

    def get_default_button(self) -> str:
        return self._last_stage_data.default.value


class Completed(Page):
    def __init__(self) -> None:
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = True
        self.title = _('Completed')
        self._severity = AdHocNoteType.INFO

        self._dataform_widget = None

        self._icon = SeverityIcon(self._severity)
        self._icon.show()

        self._label = Gtk.Label(label=_('Completed'))
        self._label.show()

        self._icon_text = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._icon_text.set_spacing(12)
        self._icon_text.set_halign(Gtk.Align.CENTER)
        self._icon_text.add(self._icon)
        self._icon_text.add(self._label)
        self.add(self._icon_text)

        self._notes = Gtk.Grid(row_spacing=6, column_spacing=12)
        self._notes.insert_column(0)
        self._notes.insert_column(1)
        self._notes.set_vexpand(False)
        self._notes.set_hexpand(True)
        notes_box = Gtk.Box()
        notes_box.set_halign(Gtk.Align.CENTER)
        notes_box.set_vexpand(False)
        notes_box.add(self._notes)
        self.add(notes_box)

        self.show_all()

    def process_stage(self, stage_data: AdHocCommand) -> None:
        self._reset_severity()
        self._show_notes(stage_data.notes)
        self._show_form(stage_data.data)
        self._show_icon_text(stage_data.data is None)
        self._show_icon(len(stage_data.notes) <= 1)

    def _set_status(self, status: str):
        self.title = status
        self._label.set_label(status)

    def _show_icon_text(self, show: bool) -> None:
        if show:
            self.set_valign(Gtk.Align.CENTER)
            self._icon_text.show_all()
        else:
            self.set_valign(Gtk.Align.FILL)
            self._icon_text.hide()

        if self._severity == AdHocNoteType.INFO:
            self._set_status(_('Completed'))
        elif self._severity == AdHocNoteType.WARN:
            self._set_status(_('Warning'))
        elif self._severity == AdHocNoteType.ERROR:
            self._set_status(_('Error'))

    def _show_form(self, form: Node | None) -> None:
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

    def _show_notes(self, notes: list[AdHocCommandNote]):
        self._notes.foreach(self._remove_note_cell)

        for i, note in enumerate(notes):
            if len(notes) > 1:
                icon = SeverityIcon(note.type)
                icon.show()
                self._notes.attach(icon, 0, i, 1, 1)

            label = MultiLineLabel(label=note.text)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_vexpand(False)
            label.show()
            self._notes.attach(label, 1, i, 1, 1)

            self._bump_severity(note.type)

    def _show_icon(self, show: bool):
        if show:
            self._icon.set_severity(self._severity)
        else:
            self._icon.hide()

    def _reset_severity(self):
        self._severity = AdHocNoteType.INFO

    def _bump_severity(self, severity: AdHocNoteType):
        if ((severity == AdHocNoteType.WARN and
                self._severity != AdHocNoteType.ERROR) or
                severity == AdHocNoteType.ERROR):
            self._severity = severity

    def _remove_note_cell(self, cell: Gtk.Widget) -> None:
        self._notes.remove(cell)
        cell.destroy()

    def get_visible_buttons(self) -> list[str]:
        return ['commands']


class Error(ErrorPage):
    def __init__(self) -> None:
        ErrorPage.__init__(self)

        self._show_commands_button = False
        self.set_heading(_('An error occurred'))

    def set_show_commands_button(self, value: bool) -> None:
        self._show_commands_button = value

    def get_visible_buttons(self) -> list[str]:
        if self._show_commands_button:
            return ['commands']
        return []


class Executing(ProgressPage):
    def __init__(self) -> None:
        ProgressPage.__init__(self)
        self.set_title(_('Executing…'))
        self.set_text(_('Executing…'))


class RequestCommandList(ProgressPage):
    def __init__(self) -> None:
        ProgressPage.__init__(self)
        self.set_title(_('Requesting Command List'))
        self.set_text(_('Requesting Command List'))


class SeverityIcon(Gtk.Image):
    def __init__(self, severity: AdHocNoteType) -> None:
        Gtk.Image.__init__(self)
        self.set_severity(severity)

    def set_severity(self, severity: AdHocNoteType) -> None:
        ctx = self.get_style_context()
        ctx.remove_class('success-color')
        ctx.remove_class('warning-color')
        ctx.remove_class('error-color')
        if severity == AdHocNoteType.INFO:
            self.set_from_icon_name('object-select-symbolic',
                    Gtk.IconSize.DIALOG)
            ctx.add_class('success-color')
        elif severity == AdHocNoteType.WARN:
            self.set_from_icon_name('dialog-warning-symbolic',
                    Gtk.IconSize.DIALOG)
            ctx.add_class('warning-color')
        elif severity == AdHocNoteType.ERROR:
            self.set_from_icon_name('dialog-error-symbolic',
                    Gtk.IconSize.DIALOG)
            ctx.add_class('error-color')
