# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import overload

import itertools
import logging

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.modules import dataforms
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.structs import SearchFields
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import AssistantErrorPage
from gajim.gtk.assistant import AssistantPage
from gajim.gtk.assistant import AssistantProgressPage
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.dataform import FakeDataFormWidget
from gajim.gtk.dataform import MultipleDataForm
from gajim.gtk.menus import get_component_search_menu
from gajim.gtk.util.misc import ensure_not_destroyed
from gajim.gtk.widgets import GajimPopover

log = logging.getLogger("gajim.gtk.search")


class ComponentSearch(Assistant):
    def __init__(
        self, account: str, jid: str, transient_for: Gtk.Window | None = None
    ) -> None:
        Assistant.__init__(self, transient_for=transient_for, width=700, height=500)

        self._client = app.get_client(account)
        self.account = account
        self._jid = jid
        self._destroyed = False

        self.add_button("close", _("Close"))
        self.add_button("search", _("Search"), "suggested-action")
        self.add_button("new-search", _("New Search"))

        self.add_pages(
            {
                "prepare": RequestForm(),
                "form": SearchForm(),
                "result": Result(),
                "error": Error(),
            }
        )

        progress = self.add_default_page("progress")
        progress.set_title(_("Searching"))
        progress.set_text(_("Searching…"))

        self._connect(self, "button-clicked", self._on_button_clicked)

        self._client.get_module("Search").request_form(
            self._jid, callback=self._search_form_received
        )

    @overload
    def get_page(self, name: Literal["prepare"]) -> RequestForm: ...

    @overload
    def get_page(self, name: Literal["form"]) -> SearchForm: ...

    @overload
    def get_page(self, name: Literal["result"]) -> Result: ...

    @overload
    def get_page(self, name: Literal["error"]) -> Error: ...

    def get_page(self, name: str) -> AssistantPage:
        return self._pages[name]

    def _on_button_clicked(self, _assistant: Assistant, button_name: str) -> None:
        if button_name == "search":
            self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)
            form = self.get_page("form").get_submit_form()
            self._client.get_module("Search").send_form(
                self._jid, form, callback=self._on_search_result
            )
            return

        if button_name == "new-search":
            self.show_page("form", Gtk.StackTransitionType.SLIDE_RIGHT)
            return

        if button_name == "close":
            self.close()

    @ensure_not_destroyed
    def _search_form_received(self, task: Task) -> None:
        try:
            form = cast(SimpleDataForm | SearchFields, task.finish())
        except Exception as error:
            log.warning(error)
            self.get_page("error").set_text(_("Error while retrieving search form."))
            self.show_page("error")
            return

        self.get_page("form").process_search_form(form)
        self.show_page("form")

    @ensure_not_destroyed
    def _on_search_result(self, task: Task) -> None:
        try:
            form = cast(MultipleDataForm, task.finish())
        except Exception as error:
            log.warning(error)
            self.get_page("error").set_text(_("Error while receiving search results."))
            self.show_page("error")
            return

        self.get_page("result").process_result(form)
        self.show_page("result")

    def _cleanup(self) -> None:
        Assistant._cleanup(self)
        self._destroyed = True


class RequestForm(AssistantProgressPage):
    def __init__(self):
        AssistantProgressPage.__init__(self)
        self.set_title(_("Request Search Form"))
        self.set_text(_("Requesting search form from server"))

    def get_visible_buttons(self) -> list[str]:
        return ["close"]


class SearchForm(AssistantPage):
    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Search")

        self.complete = False

    def clear(self) -> None:
        self.remove(self._dataform_widget)

    def process_search_form(self, form: SimpleDataForm | SearchFields) -> None:
        self.clear()

        is_dataform = isinstance(form, SimpleDataForm)
        options = {"form-width": 350, "entry-activates-default": True}

        if is_dataform:
            self._dataform_widget = DataFormWidget(form, options=options)
        else:
            self._dataform_widget = FakeDataFormWidget(dict(form))

        self._dataform_widget.set_propagate_natural_height(True)
        self._connect(self._dataform_widget, "is-valid", self._on_is_valid)

        self._dataform_widget.validate()
        self.append(self._dataform_widget)

    def _on_is_valid(self, _widget: DataFormWidget, is_valid: bool) -> None:
        self.complete = is_valid
        self.update_page_complete()

    def get_submit_form(self) -> SimpleDataForm | SearchFields:
        assert self._dataform_widget is not None
        if isinstance(self._dataform_widget, DataFormWidget):
            return self._dataform_widget.get_submit_form()

        fields = self._dataform_widget.get_submit_form()
        return SearchFields(instructions="", **fields)

    def get_visible_buttons(self) -> list[str]:
        return ["close", "search"]

    def get_default_button(self) -> str:
        return "search"


class Result(AssistantPage):
    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Search Result")

        self._jid_col: int | None = None

        self._label = Gtk.Label(label=_("No results found"))
        self._label.add_css_class("title-3")
        self._label.set_visible(False)
        self._label.set_halign(Gtk.Align.CENTER)

        self._scrolled = Gtk.ScrolledWindow(
            propagate_natural_height=True,
            visible=False,
            has_frame=True,
        )

        self.append(self._label)
        self.append(self._scrolled)

        self._treeview: Gtk.TreeView | None = None

    def process_result(self, form: MultipleDataForm) -> None:
        if self._treeview is not None:
            self._scrolled.set_child(None)
            self._treeview = None
            self._label.set_visible(False)
            self._scrolled.set_visible(False)

        fieldtypes: list[type[bool] | type[str]] = []
        fieldvars: list[Any] = []
        index = 0
        for field in form.reported.iter_fields():
            if field.type_ == "boolean":
                fieldtypes.append(bool)
            elif field.type_ in ("jid-single", "text-single"):
                fieldtypes.append(str)
                if field.type_ == "jid-single" or field.var == "jid":
                    # Enable Start Chat context menu entry
                    self._jid_col = index
            else:
                log.warning("Not supported field received: %s", field.type_)
                continue
            fieldvars.append(field.var)
            index += 1

        liststore = Gtk.ListStore(*fieldtypes)

        for item in form.iter_records():
            iter_ = liststore.append()
            assert isinstance(item, dataforms.DataRecord)
            for field in item.iter_fields():
                if field.var in fieldvars:
                    liststore.set_value(iter_, fieldvars.index(field.var), field.value)

        self._treeview = Gtk.TreeView()
        self._treeview.set_hexpand(True)
        self._treeview.set_vexpand(True)
        self._treeview.add_css_class("gajim-treeview")

        gesture_secondary = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary, "pressed", self._on_button_press)
        self._treeview.add_controller(gesture_secondary)

        for field, counter in zip(
            form.reported.iter_fields(), itertools.count(), strict=False
        ):
            self._treeview.append_column(
                Gtk.TreeViewColumn(field.label, Gtk.CellRendererText(), text=counter)
            )

        self._treeview.set_model(liststore)
        self._treeview.set_visible(True)

        self._scrolled.set_visible(True)

        box = Gtk.Box()
        box.append(self._treeview)

        self._popover_menu = GajimPopover(None)
        box.append(self._popover_menu)
        self._scrolled.set_child(box)

    def _on_button_press(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        assert self._treeview is not None
        path = self._treeview.get_path_at_pos(int(x), int(y))
        if path is None:
            return

        gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)

        path, _column, _x, _y = path
        store = self._treeview.get_model()
        assert store is not None
        assert path is not None
        iter_ = store.get_iter(path)
        column_values = [str(item) for item in store[iter_]]
        text = " ".join(column_values)

        jid = None
        if self._jid_col is not None:
            jid = column_values[self._jid_col]
        menu = get_component_search_menu(jid, text)
        self._popover_menu.set_menu_model(menu)
        self._popover_menu.set_pointing_to_coord(x, y)
        self._popover_menu.popup()

    def get_visible_buttons(self) -> list[str]:
        return ["close", "new-search"]

    def get_default_button(self) -> str:
        return "close"


class Error(AssistantErrorPage):
    def __init__(self) -> None:
        AssistantErrorPage.__init__(self)
        self.set_title(_("Error"))
        self.set_heading(_("An error occurred"))

    def get_visible_buttons(self) -> list[str]:
        return ["close"]
