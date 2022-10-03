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

from __future__ import annotations

from typing import Optional

import logging

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GtkSource

from nbxmpp.errors import StanzaError
from nbxmpp.modules import dataforms
from nbxmpp.simplexml import Node
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import to_user_string

from .dialogs import ErrorDialog
from .dialogs import WarningDialog
from .dataform import DataFormWidget
from .builder import get_builder

log = logging.getLogger('gajim.gui.pep_config')


class PEPConfig(Gtk.ApplicationWindow):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('PEPConfig')
        self.set_default_size(700, 800)
        self.set_resizable(True)
        self.set_transient_for(app.window)

        self._ui = get_builder('pep_config.ui')
        self.add(self._ui.stack)

        self.account = account
        self.set_title(_('PEP Service Configuration (%s)') % self.account)
        self._client = app.get_client(account)

        self._result_node: Optional[Node] = None
        self._dataform_widget: Optional[DataFormWidget] = None

        source_manager = GtkSource.LanguageManager.get_default()
        lang = source_manager.get_language('xml')
        self._ui.items_view.get_buffer().set_language(lang)

        self._style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
        style_scheme = self._get_style_scheme()
        if style_scheme is not None:
            self._ui.items_view.get_buffer().set_style_scheme(style_scheme)

        self._init_services()
        self._ui.services_treeview.get_selection().connect(
            'changed', self._on_services_selection_changed)

        self.show_all()
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

    def _get_style_scheme(self) -> Optional[GtkSource.StyleScheme]:
        if app.css_config.prefer_dark:
            style_scheme = self._style_scheme_manager.get_scheme(
                'solarized-dark')
        else:
            style_scheme = self._style_scheme_manager.get_scheme(
                'solarized-light')
        return style_scheme

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_services_selection_changed(self,
                                       _selection: Gtk.TreeSelection
                                       ) -> None:

        self._ui.configure_button.set_sensitive(True)
        self._ui.show_content_button.set_sensitive(True)
        self._ui.delete_button.set_sensitive(True)

    def _init_services(self):
        # service, access_model, group
        self.treestore = Gtk.ListStore(str)
        self.treestore.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self._ui.services_treeview.set_model(self.treestore)

        col = Gtk.TreeViewColumn(_('Service'))
        col.set_sort_column_id(0)
        self._ui.services_treeview.append_column(col)

        cellrenderer_text = Gtk.CellRendererText()
        col.pack_start(cellrenderer_text, True)
        col.add_attribute(cellrenderer_text, 'text', 0)

        jid = self._client.get_own_jid().bare
        self._client.get_module('Discovery').disco_items(
            jid, callback=self._items_received)

    def _items_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            ErrorDialog('Error', to_user_string(error))
            return

        jid = result.jid.bare
        for item in result.items:
            if item.jid == jid and item.node is not None:
                self.treestore.append([item.node])

    def _on_delete_button_clicked(self, _widget: Gtk.Button) -> None:
        selection = self._ui.services_treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        assert isinstance(model, Gtk.ListStore)
        assert iter_
        node = model[iter_][0]

        self._client.get_module('PubSub').delete(
            node,
            callback=self._on_node_delete,
            user_data=node)

    def _on_node_delete(self, task: Task) -> None:
        node = task.get_user_data()

        try:
            task.finish()
        except StanzaError as error:
            WarningDialog(
                _('PEP node was not removed'),
                _('PEP node %(node)s was not removed:\n%(message)s') % {
                    'node': node,
                    'message': error})
            return

        model = self._ui.services_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        iter_ = model.get_iter_first()
        while iter_:
            if model[iter_][0] == node:
                model.remove(iter_)
                break
            iter_ = model.iter_next(iter_)

    def _on_configure_button_clicked(self, _button: Gtk.Button) -> None:
        selection = self._ui.services_treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        assert isinstance(model, Gtk.ListStore)
        assert iter_
        node = model[iter_][0]

        self._client.get_module('PubSub').get_node_configuration(
            node,
            callback=self._on_pep_config_received)

    def _on_pep_config_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except Exception:
            log.exception('Failed to retrieve config')
            return

        if self._dataform_widget is not None:
            self._ui.form_box.remove(self._dataform_widget)
            self._dataform_widget.destroy()

        self._result_node = result.node

        form = dataforms.extend_form(node=result.form)
        self._dataform_widget = DataFormWidget(form)
        self._dataform_widget.set_propagate_natural_height(True)
        self._dataform_widget.show_all()
        self._ui.form_box.add(self._dataform_widget)
        self._ui.form_label.set_text(result.node)

        self._ui.stack.set_visible_child_name('config')

    def _on_save_config_clicked(self, _button: Gtk.Button) -> None:
        assert self._dataform_widget is not None
        form = self._dataform_widget.get_submit_form()
        self._client.get_module('PubSub').set_node_configuration(
            self._result_node, form)

        self._ui.stack.set_visible_child_name('overview')

    def _on_back_clicked(self, _button: Gtk.Button) -> None:
        self._ui.stack.set_visible_child_name('overview')

    def _on_show_content_clicked(self, _button: Gtk.Button) -> None:
        selection = self._ui.services_treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        assert isinstance(model, Gtk.ListStore)
        assert iter_
        node = model[iter_][0]

        self._client.get_module('PubSub').request_items(
            node,
            callback=self._on_pep_items_received,
            user_data=node)

    def _on_pep_items_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except Exception:
            log.exception('Failed to retrieve items')
            return

        parent_node = task.get_user_data()
        self._ui.items_label.set_text(str(parent_node))

        buf = self._ui.items_view.get_buffer()
        start, end = buf.get_bounds()
        buf.delete(start, end)

        for node in result:
            # pylint: disable=unnecessary-dunder-call
            node = node.__str__(fancy=True)

            buf = self._ui.items_view.get_buffer()
            buf.insert_at_cursor(str(node))

        self._ui.stack.set_visible_child_name('items')
