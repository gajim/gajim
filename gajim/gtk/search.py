# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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

import logging
import itertools
from enum import IntEnum

from gi.repository import Gtk

from nbxmpp.modules import dataforms

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _

from .menus import SearchMenu
from .dataform import DataFormWidget
from .util import ensure_not_destroyed
from .util import find_widget
from .util import EventHelper

log = logging.getLogger('gajim.gui.search')


class Page(IntEnum):
    REQUEST_FORM = 0
    FORM = 1
    REQUEST_RESULT = 2
    COMPLETED = 3
    ERROR = 4


class Search(Gtk.Assistant, EventHelper):
    def __init__(self, account, jid, transient_for=None):
        Gtk.Assistant.__init__(self)
        EventHelper.__init__(self)

        self._con = app.connections[account]
        self._account = account
        self._jid = jid
        self._destroyed = False

        self.set_application(app.app)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        if transient_for is not None:
            self.set_transient_for(transient_for)

        self.set_size_request(500, 400)
        self.get_style_context().add_class('dialog-margin')

        self._add_page(RequestForm())
        self._add_page(Form())
        self._add_page(RequestResult())
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
        self.register_events([
            ('search-form-received', ged.GUI1, self._search_form_received),
            ('search-result-received', ged.GUI1, self._search_result_received),
        ])

        self._request_search_fields()

    def _add_custom_buttons(self):
        action_area = find_widget('action_area', self)
        for button in list(action_area.get_children()):
            self.remove_action_widget(button)

        search = Gtk.Button(label=_('Search'))
        search.connect('clicked', self._execute_search)
        search.get_style_context().add_class('suggested-action')
        self._buttons['search'] = search
        self.add_action_widget(search)

        new_search = Gtk.Button(label=_('New Search'))
        new_search.get_style_context().add_class('suggested-action')
        new_search.connect('clicked',
                           lambda *args: self.set_current_page(Page.FORM))
        self._buttons['new-search'] = new_search
        self.add_action_widget(new_search)

    def _set_button_visibility(self, page):
        for button in self._buttons.values():
            button.hide()

        if page == Page.FORM:
            self._buttons['search'].show()

        elif page in (Page.ERROR, Page.COMPLETED):
            self._buttons['new-search'].show()

    def _add_page(self, page):
        self.append_page(page)
        self.set_page_type(page, page.type_)
        self.set_page_title(page, page.title)
        self.set_page_complete(page, page.complete)

    def set_stage_complete(self, is_valid):
        self._buttons['search'].set_sensitive(is_valid)

    def _request_search_fields(self):
        self._con.get_module('Search').request_search_fields(self._jid)

    def _execute_search(self, *args):
        self.set_current_page(Page.REQUEST_RESULT)
        form = self.get_nth_page(Page.FORM).get_submit_form()
        self._con.get_module('Search').send_search_form(self._jid, form, True)

    @ensure_not_destroyed
    def _search_form_received(self, event):
        if not event.is_dataform:
            self.set_current_page(Page.ERROR)
            return

        self.get_nth_page(Page.FORM).process_search_form(event.data)
        self.set_current_page(Page.FORM)

    @ensure_not_destroyed
    def _search_result_received(self, event):
        if event.data is None:
            self._on_error('')
            return
        self.get_nth_page(Page.COMPLETED).process_result(event.data)
        self.set_current_page(Page.COMPLETED)

    def _remove_sidebar(self):
        main_box = self.get_children()[0]
        sidebar = main_box.get_children()[0]
        main_box.remove(sidebar)

    def _on_page_change(self, _assistant, _page):
        self._set_button_visibility(self.get_current_page())

    def _on_error(self, error_text):
        log.info('Show Error page')
        page = self.get_nth_page(Page.ERROR)
        page.set_text(error_text)
        self.set_current_page(Page.ERROR)

    def _on_cancel(self, _widget):
        self.destroy()

    def _on_destroy(self, *args):
        self._destroyed = True


class RequestForm(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Request Search Form')
    complete = False

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        spinner = Gtk.Spinner()
        self.pack_start(spinner, True, True, 0)
        spinner.start()
        self.show_all()


class Form(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Search')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self._dataform_widget = None
        self.show_all()

    @property
    def search_form(self):
        return self._dataform_widget.get_submit_form()

    def clear(self):
        self._show_form(None)

    def process_search_form(self, form):
        self._show_form(form)

    def _show_form(self, form):
        if self._dataform_widget is not None:
            self.remove(self._dataform_widget)
            self._dataform_widget.destroy()
        if form is None:
            return

        options = {'form-width': 350}

        form = dataforms.extend_form(node=form)
        self._dataform_widget = DataFormWidget(form, options=options)
        self._dataform_widget.connect('is-valid', self._on_is_valid)
        self._dataform_widget.validate()
        self._dataform_widget.show_all()
        self.add(self._dataform_widget)

    def _on_is_valid(self, _widget, is_valid):
        self.get_toplevel().set_stage_complete(is_valid)

    def get_submit_form(self):
        return self._dataform_widget.get_submit_form()


class RequestResult(RequestForm):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Search…')
    complete = False


class Completed(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Search Result')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.show_all()
        self._label = Gtk.Label(label=_('No results found'))
        self._label.get_style_context().add_class('bold16')
        self._label.set_no_show_all(True)
        self._label.set_halign(Gtk.Align.CENTER)
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.get_style_context().add_class('search-scrolled')
        self._scrolled.set_no_show_all(True)
        self._treeview = None
        self._menu = None
        self.add(self._label)
        self.add(self._scrolled)
        self.show_all()

    def process_result(self, form):
        if self._treeview is not None:
            self._scrolled.remove(self._treeview)
            self._treeview.destroy()
            self._treeview = None
            self._menu = None
            self._label.hide()
            self._scrolled.hide()

        if not form:
            self._label.show()
            return

        form = dataforms.extend_form(node=form)

        fieldtypes = []
        fieldvars = []
        for field in form.reported.iter_fields():
            if field.type_ == 'boolean':
                fieldtypes.append(bool)
            elif field.type_ in ('jid-single', 'text-single'):
                fieldtypes.append(str)
            else:
                log.warning('Not supported field received: %s', field.type_)
                continue
            fieldvars.append(field.var)

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
        self._treeview.get_style_context().add_class('search-treeview')
        self._treeview.connect('button-press-event', self._on_button_press)
        self._menu = SearchMenu(self._treeview)

        for field, counter in zip(form.reported.iter_fields(),
                                  itertools.count()):
            self._treeview.append_column(
                Gtk.TreeViewColumn(field.label,
                                   Gtk.CellRendererText(),
                                   text=counter))

        self._treeview.set_model(liststore)
        self._treeview.show()
        self._scrolled.add(self._treeview)
        self._scrolled.show()

    def _on_button_press(self, treeview, event):
        if event.button != 3:
            return
        path, _column, _x, _y = treeview.get_path_at_pos(event.x, event.y)
        if path is None:
            return
        store = treeview.get_model()
        iter_ = store.get_iter(path)
        column_values = store[iter_]
        text = ' '.join(column_values)
        self._menu.set_copy_text(text)
        self._menu.popup_at_pointer()


class Error(Gtk.Box):

    type_ = Gtk.AssistantPageType.CUSTOM
    title = _('Error')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_homogeneous(True)

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
