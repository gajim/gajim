# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging

from gi.repository import Gtk
from gi.repository import GtkSource
from nbxmpp.errors import StanzaError
from nbxmpp.modules import dataforms
from nbxmpp.simplexml import Node
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common.ged import EventHelper
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.builder import get_builder
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util.styling import get_source_view_style_scheme
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.pep_config")


class PEPConfig(GajimAppWindow, EventHelper):
    def __init__(self, account: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="PEPConfig",
            title=_("PEP Service Configuration (%s)") % account,
            default_width=700,
            default_height=800,
        )

        EventHelper.__init__(self)

        self._ui = get_builder("pep_config.ui")
        self.set_child(self._ui.stack)

        self.account = account
        self._client = app.get_client(account)

        self._result_node: Node | None = None
        self._dataform_widget: DataFormWidget | None = None

        source_manager = GtkSource.LanguageManager.get_default()
        lang = source_manager.get_language("xml")
        self._ui.items_view.get_buffer().set_language(lang)

        style_scheme = get_source_view_style_scheme()
        if style_scheme is not None:
            self._ui.items_view.get_buffer().set_style_scheme(style_scheme)

        self._init_services()

        selection = self._ui.services_treeview.get_selection()
        self._connect(selection, "changed", self._on_services_selection_changed)

        self._connect(
            self._ui.show_content_button, "clicked", self._on_show_content_clicked
        )
        self._connect(self._ui.delete_button, "clicked", self._on_delete_button_clicked)
        self._connect(
            self._ui.configure_button, "clicked", self._on_configure_button_clicked
        )
        self._connect(self._ui.items_back_button, "clicked", self._on_back_clicked)
        self._connect(self._ui.config_back_button, "clicked", self._on_back_clicked)
        self._connect(self._ui.save_button, "clicked", self._on_save_config_clicked)

        self.register_events([("style-changed", ged.GUI1, self._on_style_changed)])

    def _cleanup(self) -> None:
        self.unregister_events()
        app.check_finalize(self)

    def _on_style_changed(self, *args: Any) -> None:
        style_scheme = get_source_view_style_scheme()
        if style_scheme is not None:
            self._ui.items_view.get_buffer().set_style_scheme(style_scheme)

    def _on_services_selection_changed(self, _selection: Gtk.TreeSelection) -> None:

        self._ui.configure_button.set_sensitive(True)
        self._ui.show_content_button.set_sensitive(True)
        self._ui.delete_button.set_sensitive(True)

    def _init_services(self):
        # service, access_model, group
        self.treestore = Gtk.ListStore(str)
        self.treestore.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self._ui.services_treeview.set_model(self.treestore)

        col = Gtk.TreeViewColumn(title=_("Service"))
        col.set_sort_column_id(0)
        self._ui.services_treeview.append_column(col)

        cellrenderer_text = Gtk.CellRendererText()
        col.pack_start(cellrenderer_text, True)
        col.add_attribute(cellrenderer_text, "text", 0)

        jid = self._client.get_own_jid().bare
        self._client.get_module("Discovery").disco_items(
            jid, callback=self._items_received
        )

    def _items_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            InformationAlertDialog(_("Error"), to_user_string(error))
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

        def _on_response() -> None:
            self._client.get_module("PubSub").delete(
                node, callback=self._on_node_delete, user_data=node
            )

        ConfirmationAlertDialog(
            _("Delete Node?"),
            _("Do you want to delete this PEP node?"),
            confirm_label=_("_Delete"),
            appearance="destructive",
            callback=_on_response,
            parent=self.window,
        )

    def _on_node_delete(self, task: Task) -> None:
        node = task.get_user_data()

        try:
            task.finish()
        except StanzaError as error:
            InformationAlertDialog(
                _("PEP Node Not Removed"),
                _("PEP node %(node)s was not removed:\n%(message)s")
                % {"node": node, "message": error},
            )
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

        self._client.get_module("PubSub").get_node_configuration(
            node, callback=self._on_pep_config_received
        )

    def _on_pep_config_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except Exception:
            log.exception("Failed to retrieve config")
            return

        if self._dataform_widget is not None:
            self._ui.form_box.remove(self._dataform_widget)

        self._result_node = result.node

        form = dataforms.extend_form(node=result.form)
        self._dataform_widget = DataFormWidget(form)
        self._dataform_widget.set_propagate_natural_height(True)
        self._dataform_widget.set_visible(True)
        self._ui.form_box.append(self._dataform_widget)
        self._ui.form_label.set_text(result.node)

        self._ui.stack.set_visible_child_name("config")

    def _on_save_config_clicked(self, _button: Gtk.Button) -> None:
        assert self._dataform_widget is not None
        form = self._dataform_widget.get_submit_form()
        self._client.get_module("PubSub").set_node_configuration(
            self._result_node, form
        )

        self._ui.stack.set_visible_child_name("overview")

    def _on_back_clicked(self, _button: Gtk.Button) -> None:
        self._ui.stack.set_visible_child_name("overview")

    def _on_show_content_clicked(self, _button: Gtk.Button) -> None:
        selection = self._ui.services_treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        assert isinstance(model, Gtk.ListStore)
        assert iter_
        node = model[iter_][0]

        self._client.get_module("PubSub").request_items(
            node, callback=self._on_pep_items_received, user_data=node
        )

    def _on_pep_items_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except Exception:
            log.exception("Failed to retrieve items")
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

        self._ui.stack.set_visible_child_name("items")
