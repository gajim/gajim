# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import overload

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
from gajim.common.util.text import process_non_spacing_marks

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import DefaultPage
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.assistant import ProgressPage
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import ensure_not_destroyed
from gajim.gtk.widgets import MultiLineLabel

log = logging.getLogger("gajim.gtk.adhoc")


class AdHocCommands(Assistant):
    def __init__(self, account: str, jids: list[str]) -> None:
        Assistant.__init__(self, width=600, height=500)
        self.account = account
        self.jid = str(jids[0])  # TODO: Add resource chooser

        self._destroyed = False

        self._client = app.get_client(account)

        self.add_button("cancel", _("Cancel"))
        self.add_button("prev", _("Previous"))
        self.add_button("next", _("Next"), complete=True, css_class="suggested-action")
        self.add_button(
            "complete", _("Complete"), complete=True, css_class="suggested-action"
        )
        self.add_button("commands", _("Commands"), css_class="suggested-action")
        self.add_button("execute", _("Execute"), css_class="suggested-action")

        self.add_pages(
            {
                "request": RequestCommandList(),
                "commands": Commands(),
                "stage": Stage(),
                "completed": Completed(),
                "error": Error(),
                "end": End(),
                "executing": Executing(),
            }
        )

        commands_page = self.get_page("commands")
        self._connect(commands_page, "execute", self._on_execute)

        self._connect(self, "button-clicked", self._on_button_clicked)

        self._client.get_module("AdHocCommands").request_command_list(
            self.jid, callback=self._received_command_list
        )
        self.show_all()

    @overload
    def get_page(self, name: Literal["request"]) -> RequestCommandList: ...

    @overload
    def get_page(self, name: Literal["commands"]) -> Commands: ...

    @overload
    def get_page(self, name: Literal["stage"]) -> Stage: ...

    @overload
    def get_page(self, name: Literal["completed"]) -> Completed: ...

    @overload
    def get_page(self, name: Literal["error"]) -> Error: ...

    @overload
    def get_page(self, name: Literal["end"]) -> End: ...

    @overload
    def get_page(self, name: Literal["executing"]) -> Executing: ...

    def get_page(self, name: str) -> Page:
        return self._pages[name]

    @ensure_not_destroyed
    def _received_command_list(self, task: Task) -> None:
        try:
            commands = cast(list[AdHocCommand] | None, task.finish())
        except StanzaError as error:
            if error.condition == "feature-not-implemented":
                commands = []
            else:
                self._set_error(to_user_string(error), False)
                return

        except MalformedStanzaError:
            self._set_error(_("Invalid server response"), False)
            return

        if not commands:
            self._set_end(_("No commands available"))
            return

        commands_page = self.get_page("commands")
        commands_page.add_commands(commands)
        self.show_page("commands")

    @ensure_not_destroyed
    def _received_stage(self, task: Task) -> None:
        try:
            stage = cast(AdHocCommand, task.finish())
        except StanzaError as error:
            self._set_error(to_user_string(error), True)
            return

        except MalformedStanzaError:
            self._set_error(_("Invalid server response"), False)
            return

        page_name = "stage"
        if stage.is_completed:
            page_name = "completed"

        page = self.get_page(page_name)
        page.process_stage(stage)
        self.show_page(page_name)

    def _set_error(self, text: str, show_command_button: bool) -> None:
        error_page = self.get_page("error")
        error_page.set_show_commands_button(show_command_button)
        error_page.set_text(text)
        self.show_page("error")

    def _set_end(self, text: str = "") -> None:
        end = self.get_page("end")
        end.set_text(text)
        self.show_page("end")

    def _cleanup(self) -> None:
        self._destroyed = True

    def _on_button_clicked(self, _assistant: AdHocCommands, button_name: str) -> None:
        if button_name == "commands":
            self._client.get_module("AdHocCommands").request_command_list(
                self.jid, callback=self._received_command_list
            )

        elif button_name == "execute":
            self._on_execute()

        elif button_name in ("prev", "next", "complete"):
            self._on_stage_action(AdHocAction(button_name))

        elif button_name == "cancel":
            self._on_cancel()

        else:
            raise ValueError("Invalid button name: %s" % button_name)

    def _on_stage_action(self, action: AdHocAction) -> None:
        stage_page = self.get_page("stage")
        command, dataform = stage_page.stage_data
        if action == AdHocAction.PREV:
            dataform = None

        self._client.get_module("AdHocCommands").execute_command(
            command, action=action, dataform=dataform, callback=self._received_stage
        )

        self.show_page("executing")
        stage_page = self.get_page("stage")
        stage_page.clear()

    def _on_execute(self, *args: Any) -> None:
        commands_page = self.get_page("commands")
        command = commands_page.get_selected_command()
        if command is None:
            return

        self._client.get_module("AdHocCommands").execute_command(
            command, action=AdHocAction.EXECUTE, callback=self._received_stage
        )

        self.show_page("executing")

    def _on_cancel(self) -> None:
        stage_page = self.get_page("stage")
        command, _ = stage_page.stage_data
        self._client.get_module("AdHocCommands").execute_command(
            command, AdHocAction.CANCEL
        )
        self.show_page("commands")


class Commands(Page):
    __gsignals__ = {
        "execute": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = True
        self.title = _("Command List")

        self._commands: dict[str, AdHocCommand] = {}
        self._scrolled = Gtk.ScrolledWindow(
            max_content_width=400,
            max_content_height=400,
            propagate_natural_height=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
            has_frame=True,
        )

        self._treeview = Gtk.TreeView()
        self._treeview.add_css_class("gajim-treeview")
        self._store = Gtk.ListStore(str, str)
        self._treeview.set_model(self._store)
        column = Gtk.TreeViewColumn(_("Commands"), Gtk.CellRendererText(), text=0)
        column.set_expand(True)
        self._treeview.append_column(column)

        self._connect(self._treeview, "row-activated", self._on_row_activate)
        self._treeview.set_search_equal_func(self._search_func)

        self._scrolled.set_child(self._treeview)
        self.append(self._scrolled)

    @staticmethod
    def _search_func(
        model: Gtk.TreeModel, _column: int, search_text: str, iter_: Gtk.TreeIter
    ) -> bool:
        return search_text.lower() not in model[iter_][0].lower()

    def _on_row_activate(
        self, _tree_view: Gtk.TreeView, _path: Gtk.TreePath, _column: Gtk.TreeViewColumn
    ) -> None:
        self.emit("execute")

    def add_commands(self, commands: list[AdHocCommand]) -> None:
        self._store.clear()
        self._commands = {}
        for command in commands:
            key = f"{command.jid}:{command.node}"
            self._commands[key] = command
            self._store.append((command.name, key))

    def get_selected_command(self) -> AdHocCommand | None:
        model, treeiter = self._treeview.get_selection().get_selected()
        if treeiter is None:
            return None
        key = model[treeiter][1]
        return self._commands[key]

    def get_visible_buttons(self) -> list[str]:
        return ["execute"]


class Stage(Page):
    def __init__(self) -> None:
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = False
        self.title = _("Stage")

        self._dataform_widget = None
        self._notes: list[Gtk.Label] = []
        self._last_stage_data: AdHocCommand | None = None
        self.default = None

    @property
    def stage_data(
        self,
    ) -> tuple[AdHocCommand, SimpleDataForm | MultipleDataForm | None]:
        assert self._last_stage_data is not None
        form = None
        if self._dataform_widget is not None:
            form = self._dataform_widget.get_submit_form()
        assert self._dataform_widget is not None
        return self._last_stage_data, form

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
        if form is None:
            return
        form = dataforms.extend_form(node=form)
        options = {"entry-activates-default": True}
        self._dataform_widget = DataFormWidget(form, options)
        self._connect(self._dataform_widget, "is-valid", self._on_is_valid)
        self._dataform_widget.validate()
        self.append(self._dataform_widget)

    def _show_notes(self, notes: list[AdHocCommandNote] | None) -> None:
        for note in self._notes:
            self.remove(note)
        self._notes = []

        if notes is None:
            return

        for note in notes:
            label = Gtk.Label(
                label=process_non_spacing_marks(note.text),
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
            )
            label.set_visible(True)
            self._notes.append(label)
            self.append(label)

    def _on_is_valid(self, _widget: DataFormWidget, is_valid: bool) -> None:
        self.complete = is_valid
        self.update_page_complete()

    def get_visible_buttons(self) -> list[str]:
        assert self._last_stage_data is not None
        assert self._last_stage_data.actions is not None
        return [action.value for action in self._last_stage_data.actions]

    def get_default_button(self) -> str:
        assert self._last_stage_data is not None
        assert self._last_stage_data.default is not None
        return self._last_stage_data.default.value


class Completed(Page):
    def __init__(self) -> None:
        Page.__init__(self)

        self.set_valign(Gtk.Align.FILL)
        self.complete = True
        self.title = _("Completed")
        self._severity = AdHocNoteType.INFO

        self._dataform_widget = None

        self._icon = SeverityIcon(self._severity)
        self._icon.set_visible(True)

        self._label = Gtk.Label(label=_("Completed"))
        self._label.set_visible(True)

        self._icon_text = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._icon_text.set_spacing(12)
        self._icon_text.set_halign(Gtk.Align.CENTER)
        self._icon_text.append(self._icon)
        self._icon_text.append(self._label)
        self.append(self._icon_text)

        self._notes = Gtk.Grid(row_spacing=6, column_spacing=12)
        self._notes.insert_column(0)
        self._notes.insert_column(1)
        self._notes.set_vexpand(False)
        self._notes.set_hexpand(True)
        notes_box = Gtk.Box()
        notes_box.set_halign(Gtk.Align.CENTER)
        notes_box.set_vexpand(False)
        notes_box.append(self._notes)
        self.append(notes_box)

    def process_stage(self, stage_data: AdHocCommand) -> None:
        self._reset_severity()
        self._show_notes(stage_data.notes)
        self._show_form(stage_data.data)
        self._show_icon_text(stage_data.data is None)
        self._show_icon(len(stage_data.notes or []) <= 1)

    def _set_status(self, status: str):
        self.title = status
        self._label.set_label(status)

    def _show_icon_text(self, show: bool) -> None:
        if show:
            self.set_valign(Gtk.Align.CENTER)
            self._icon_text.set_visible(True)
        else:
            self.set_valign(Gtk.Align.FILL)
            self._icon_text.set_visible(False)

        if self._severity == AdHocNoteType.INFO:
            self._set_status(_("Completed"))
        elif self._severity == AdHocNoteType.WARN:
            self._set_status(_("Warning"))
        elif self._severity == AdHocNoteType.ERROR:
            self._set_status(_("Error"))

    def _show_form(self, form: Node | None) -> None:
        if self._dataform_widget is not None:
            self.remove(self._dataform_widget)
        if form is None:
            return

        form = dataforms.extend_form(node=form)

        self._dataform_widget = DataFormWidget(form, options={"read-only": True})
        self.append(self._dataform_widget)

    def _show_notes(self, notes: list[AdHocCommandNote] | None) -> None:
        container_remove_all(self._notes)

        if notes is None:
            return

        for i, note in enumerate(notes):
            if len(notes) > 1:
                icon = SeverityIcon(note.type)
                icon.set_visible(True)
                self._notes.attach(icon, 0, i, 1, 1)

            label = MultiLineLabel(label=process_non_spacing_marks(note.text))
            label.set_justify(Gtk.Justification.CENTER)
            label.set_vexpand(False)
            label.set_visible(True)
            self._notes.attach(label, 1, i, 1, 1)

            self._bump_severity(note.type)

    def _show_icon(self, show: bool):
        if show:
            self._icon.set_severity(self._severity)
        else:
            self._icon.set_visible(False)

    def _reset_severity(self):
        self._severity = AdHocNoteType.INFO

    def _bump_severity(self, severity: AdHocNoteType):
        if (
            severity == AdHocNoteType.WARN and self._severity != AdHocNoteType.ERROR
        ) or severity == AdHocNoteType.ERROR:
            self._severity = severity

    def get_visible_buttons(self) -> list[str]:
        return ["commands"]


class Error(ErrorPage):
    def __init__(self) -> None:
        ErrorPage.__init__(self)

        self._show_commands_button = False
        self.set_heading(_("An error occurred"))

    def set_show_commands_button(self, value: bool) -> None:
        self._show_commands_button = value

    def get_visible_buttons(self) -> list[str]:
        if self._show_commands_button:
            return ["commands"]
        return []


class End(DefaultPage):
    def __init__(self) -> None:
        DefaultPage.__init__(self)
        self.title = _("Completed")


class Executing(ProgressPage):
    def __init__(self) -> None:
        ProgressPage.__init__(self)
        self.set_title(_("Executing…"))
        self.set_text(_("Executing…"))


class RequestCommandList(ProgressPage):
    def __init__(self) -> None:
        ProgressPage.__init__(self)
        self.set_title(_("Requesting Command List"))
        self.set_text(_("Requesting Command List"))


class SeverityIcon(Gtk.Image):
    def __init__(self, severity: AdHocNoteType) -> None:
        Gtk.Image.__init__(self)
        self.set_severity(severity)

    def set_severity(self, severity: AdHocNoteType) -> None:
        self.remove_css_class("success")
        self.remove_css_class("warning")
        self.remove_css_class("error")
        if severity == AdHocNoteType.INFO:
            self.set_from_icon_name("lucide-check-symbolic")
            self.add_css_class("success")
        elif severity == AdHocNoteType.WARN:
            self.set_from_icon_name("lucide-circle-alert-symbolic")
            self.add_css_class("warning")
        elif severity == AdHocNoteType.ERROR:
            self.set_from_icon_name("lucide-circle-x-symbolic")
            self.add_css_class("error")
