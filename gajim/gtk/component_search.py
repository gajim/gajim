# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload

import itertools
import logging

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.modules import dataforms
from nbxmpp.simplexml import Node

from gajim.common import app
from gajim.common import ged
from gajim.common.events import SearchFormReceivedEvent
from gajim.common.events import SearchResultReceivedEvent
from gajim.common.i18n import _

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.assistant import ProgressPage
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.menus import get_component_search_menu
from gajim.gtk.util import ensure_not_destroyed
from gajim.gtk.util import EventHelper
from gajim.gtk.util import GajimPopover

log = logging.getLogger('gajim.gtk.search')


class ComponentSearch(Assistant, EventHelper):
    def __init__(self,
                 account: str,
                 jid: str,
                 transient_for: Gtk.Window | None = None
                 ) -> None:
        Assistant.__init__(self,
                           transient_for=transient_for,
                           width=700,
                           height=500)
        EventHelper.__init__(self)

        self._client = app.get_client(account)
        self.account = account
        self._jid = jid
        self._destroyed = False

        self.add_button('search', _('Search'), 'suggested-action')
        self.add_button('new-search', _('New Search'))
        self.add_button('close', _('Close'))

        self.add_pages({
            'prepare': RequestForm(),
            'form': SearchForm(),
            'result': Result(),
            'error': Error()
        })

        progress = self.add_default_page('progress')
        progress.set_title(_('Searching'))
        progress.set_text(_('Searching…'))

        self.connect('button-clicked', self._on_button_clicked)
        self.connect('destroy', self._on_destroy)

        self.register_events([
            ('search-form-received', ged.GUI1, self._search_form_received),
            ('search-result-received', ged.GUI1, self._search_result_received),
        ])

        self._client.get_module('Search').request_search_fields(self._jid)

        self.show_all()

    @overload
    def get_page(self, name: Literal['prepare']) -> RequestForm: ...

    @overload
    def get_page(self, name: Literal['form']) -> SearchForm: ...

    @overload
    def get_page(self, name: Literal['result']) -> Result: ...

    @overload
    def get_page(self, name: Literal['error']) -> Error: ...

    def get_page(self, name: str) -> Page:
        return self._pages[name]

    def _on_button_clicked(self,
                           _assistant: Assistant,
                           button_name: str
                           ) -> None:
        if button_name == 'search':
            self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)
            form = self.get_page('form').get_submit_form()
            self._client.get_module('Search').send_search_form(
                self._jid, form, True)
            return

        if button_name == 'new-search':
            self.show_page('form', Gtk.StackTransitionType.SLIDE_RIGHT)
            return

        if button_name == 'close':
            self.destroy()

    @ensure_not_destroyed
    def _search_form_received(self, event: SearchFormReceivedEvent) -> None:
        if not event.is_dataform:
            self.get_page('error').set_text(
                _('Error while retrieving search form.'))
            self.show_page('error')
            return

        self.get_page('form').process_search_form(event.data)
        self.show_page('form')

    @ensure_not_destroyed
    def _search_result_received(self,
                                event: SearchResultReceivedEvent
                                ) -> None:
        if event.data is None:
            self.get_page('error').set_text(
                _('Error while receiving search results.'))
            self.show_page('error')
            return

        self.get_page('result').process_result(event.data)
        self.show_page('result')

    def _on_destroy(self, *args: Any) -> None:
        self._destroyed = True


class RequestForm(ProgressPage):
    def __init__(self):
        ProgressPage.__init__(self)
        self.set_title(_('Request Search Form'))
        self.set_text(_('Requesting search form from server'))

    def get_visible_buttons(self) -> list[str]:
        return ['close']


class SearchForm(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _('Search')

        self.complete = False

        self._dataform_widget = None

        self.show_all()

    @property
    def search_form(self) -> dataforms.SimpleDataForm:
        return self._dataform_widget.get_submit_form()

    def clear(self) -> None:
        self._show_form(None)

    def process_search_form(self, form: Node) -> None:
        self._show_form(form)

    def _show_form(self, form: Node | None) -> None:
        if self._dataform_widget is not None:
            self.remove(self._dataform_widget)
            self._dataform_widget.destroy()
        if form is None:
            return

        options = {
            'form-width': 350,
            'entry-activates-default': True
        }

        form = dataforms.extend_form(node=form)
        self._dataform_widget = DataFormWidget(form, options=options)
        self._dataform_widget.set_propagate_natural_height(True)
        self._dataform_widget.connect('is-valid', self._on_is_valid)
        self._dataform_widget.validate()
        self._dataform_widget.show_all()
        self.add(self._dataform_widget)

    def _on_is_valid(self, _widget: DataFormWidget, is_valid: bool) -> None:
        self.complete = is_valid
        self.update_page_complete()

    def get_submit_form(self) -> dataforms.SimpleDataForm:
        return self._dataform_widget.get_submit_form()

    def get_visible_buttons(self) -> list[str]:
        return ['close', 'search']

    def get_default_button(self) -> str:
        return 'search'


class Result(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _('Search Result')

        self._jid_col: int | None = None

        self._label = Gtk.Label(label=_('No results found'))
        self._label.get_style_context().add_class('bold16')
        self._label.set_no_show_all(True)
        self._label.set_halign(Gtk.Align.CENTER)

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_propagate_natural_height(True)
        self._scrolled.get_style_context().add_class('gajim-scrolled')
        self._scrolled.set_no_show_all(True)

        self.add(self._label)
        self.add(self._scrolled)

        self._treeview: Gtk.TreeView | None = None

        self.show_all()

    def process_result(self, form: Node | None) -> None:
        if self._treeview is not None:
            self._scrolled.remove(self._treeview)
            self._treeview.destroy()
            self._treeview = None
            self._label.hide()
            self._scrolled.hide()

        if not form:
            self._label.show()
            return

        form = dataforms.extend_form(node=form)

        fieldtypes: list[type[bool] | type[str]] = []
        fieldvars: list[Any] = []
        index = 0
        for field in form.reported.iter_fields():
            if field.type_ == 'boolean':
                fieldtypes.append(bool)
            elif field.type_ in ('jid-single', 'text-single'):
                fieldtypes.append(str)
                if field.type_ == 'jid-single' or field.var == 'jid':
                    # Enable Start Chat context menu entry
                    self._jid_col = index
            else:
                log.warning('Not supported field received: %s', field.type_)
                continue
            fieldvars.append(field.var)
            index += 1

        liststore = Gtk.ListStore(*fieldtypes)

        for item in form.iter_records():
            iter_ = liststore.append()
            for field in item.iter_fields():
                if field.var in fieldvars:
                    liststore.set_value(iter_,
                                        fieldvars.index(field.var),
                                        field.value)

        self._treeview = Gtk.TreeView()
        self._treeview.set_hexpand(True)
        self._treeview.set_vexpand(True)
        self._treeview.get_style_context().add_class('gajim-treeview')
        self._treeview.connect('button-press-event', self._on_button_press)

        for field, counter in zip(form.reported.iter_fields(),
                                  itertools.count(),
                                  strict=False):
            self._treeview.append_column(
                Gtk.TreeViewColumn(field.label,
                                   Gtk.CellRendererText(),
                                   text=counter))

        self._treeview.set_model(liststore)
        self._treeview.show()
        self._scrolled.add(self._treeview)
        self._scrolled.show()

    def _on_button_press(self,
                         treeview: Gtk.TreeView,
                         event: Gdk.EventButton
                         ) -> bool:

        if event.button != Gdk.BUTTON_SECONDARY:
            return False

        path = treeview.get_path_at_pos(int(event.x), int(event.y))
        if path is None:
            return False

        path, _column, _x, _y = path
        store = treeview.get_model()
        assert store is not None
        assert path is not None
        iter_ = store.get_iter(path)
        column_values = [str(item) for item in store[iter_]]
        text = ' '.join(column_values)

        jid = None
        if self._jid_col is not None:
            jid = column_values[self._jid_col]
        menu = get_component_search_menu(jid, text)

        popover = GajimPopover(menu, relative_to=self, event=event)
        popover.popup()
        return True

    def get_visible_buttons(self) -> list[str]:
        return ['close', 'new-search']

    def get_default_button(self) -> str:
        return 'close'


class Error(ErrorPage):
    def __init__(self) -> None:
        ErrorPage.__init__(self)
        self.set_title(_('Error'))
        self.set_heading(_('An error occurred'))

    def get_visible_buttons(self) -> list[str]:
        return ['close']
