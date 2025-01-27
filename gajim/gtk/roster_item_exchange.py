# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import i18n
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import SimpleDialog
from gajim.gtk.widgets import GajimAppWindow


class RosterItemExchange(GajimAppWindow):
    """
    Used when someone sends a Roster Item Exchange suggestion (XEP-0144)
    """

    def __init__(
        self,
        account: str,
        action: str,
        exchange_list: dict[str, list[str]],
        jid_from: JID,
        message_body: str | None = None,
    ) -> None:
        GajimAppWindow.__init__(
            self,
            name="RosterItemExchange",
            title=_("Contact List Exchange"),
        )

        self.account = account
        self._client = app.get_client(account)

        self._action = action
        self._exchange_list = exchange_list
        self._jid_from = jid_from

        self._ui = get_builder("roster_item_exchange.ui")
        self.set_child(self._ui.roster_item_exchange)

        self._connect(self._ui.cancel_button, "clicked", self._on_cancel_button_clicked)
        self._connect(self._ui.accept_button, "clicked", self._on_accept_button_clicked)

        contact = self._client.get_module("Contacts").get_contact(jid_from.bare)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant
        )

        # Set label depending on action
        type_label = ""
        if action == "add":
            type_label = _(
                "%(name)s (%(jid)s) would like to add some "
                "contacts to your contact list."
            ) % {"name": contact.name, "jid": self._jid_from.bare}
        elif action == "modify":
            type_label = _(
                "%(name)s (%(jid)s) would like to modify some "
                "contacts in your contact list."
            ) % {"name": contact.name, "jid": self._jid_from.bare}
        elif action == "delete":
            type_label = _(
                "%(name)s (%(jid)s) would like to delete some "
                "contacts from your contact list."
            ) % {"name": contact.name, "jid": self._jid_from.bare}
        self._ui.type_label.set_text(type_label)

        if message_body:
            buffer_ = self._ui.body_textview.get_buffer()
            buffer_.set_text(message_body)
        else:
            self._ui.body_scrolledwindow.hide()

        # Treeview
        self._model = Gtk.ListStore(bool, str, str, str, str)
        self._ui.items_list_treeview.set_model(self._model)
        # Columns
        renderer1 = Gtk.CellRendererToggle()
        renderer1.set_property("activatable", True)
        self._connect(renderer1, "toggled", self._on_toggled)
        title = ""
        if self._action == "add":
            title = _("Add")
        elif self._action == "modify":
            title = _("Modify")
        elif self._action == "delete":
            title = _("Delete")
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, title, renderer1, active=0
        )
        renderer2 = Gtk.CellRendererText()
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, _("JID"), renderer2, text=1
        )
        renderer3 = Gtk.CellRendererText()
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, _("Name"), renderer3, text=2
        )
        renderer4 = Gtk.CellRendererText()
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, _("Groups"), renderer4, text=3
        )

        if action == "add":
            self._add()
        elif action == "modify":
            self._modify()
        elif action == "delete":
            self._delete()

    def _cleanup(self) -> None:
        pass

    def _on_toggled(self, cell: Gtk.CellRendererToggle, path: str) -> None:
        iter_ = self._model.get_iter(path)
        self._model[iter_][0] = not cell.get_active()

    def _add(self) -> None:
        for jid in self._exchange_list:
            contact = self._client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            name = self._exchange_list[jid][0]
            groups = ", ".join(self._exchange_list[jid][1])
            if not contact.is_in_roster:
                iter_ = self._model.append()
                self._model.set(iter_, {0: True, 1: jid, 2: name, 3: groups})

        self._ui.accept_button.set_label(_("Add"))

    def _modify(self) -> None:
        for jid in self._exchange_list:
            is_right = True
            contact = self._client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            name = self._exchange_list[jid][0]
            groups = ", ".join(self._exchange_list[jid][1])

            if name != contact.name:
                is_right = False
            for group in self._exchange_list[jid][1]:
                if group not in contact.groups:
                    is_right = False
            if not is_right and contact.is_in_roster:
                iter_ = self._model.append()
                self._model.set(iter_, {0: True, 1: jid, 2: name, 3: groups})

        self._ui.accept_button.set_label(_("Modify"))

    def _delete(self) -> None:
        for jid in self._exchange_list:
            contact = self._client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            name = self._exchange_list[jid][0]
            groups = ", ".join(self._exchange_list[jid][1])
            if contact.is_in_roster:
                iter_ = self._model.append()
                self._model.set(iter_, {0: True, 1: jid, 2: name, 3: groups})

        self._ui.accept_button.set_label(_("Delete"))

    def _on_accept_button_clicked(self, _button: Gtk.Button) -> None:
        iter_ = self._model.get_iter_first()
        if self._action == "add":
            count = 0
            while iter_:
                if self._model[iter_][0]:
                    count += 1
                    # It is selected
                    contact = self._client.get_module("Contacts").get_contact(
                        self._jid_from.bare
                    )
                    assert isinstance(
                        contact, BareContact | GroupchatContact | GroupchatParticipant
                    )
                    message = _(
                        "%(name)s %(jid)s suggested me to add you to "
                        "my contact list."
                    ) % {"name": contact.name, "jid": self._jid_from.bare}
                    # Keep same groups and same nickname
                    groups: list[str] = []
                    groups = self._model[iter_][3].split(", ")
                    if groups == [""]:
                        groups = []
                    jid = self._model[iter_][1]
                    if app.jid_is_transport(str(self._jid_from)):
                        self._client.get_module("Presence").automatically_added.append(
                            jid
                        )

                    self._client.get_module("Presence").subscribe(
                        jid,
                        msg=message,
                        name=self._model[iter_][2],
                        groups=groups,
                        auto_auth=True,
                    )
                iter_ = self._model.iter_next(iter_)
            SimpleDialog(
                _("Successfully Added Contacts"),
                i18n.ngettext(
                    "Added %(count)s contact", "Added %(count)s contacts", count
                )
                % {"count": count},
            )
        elif self._action == "modify":
            count = 0
            while iter_:
                if self._model[iter_][0]:
                    count += 1
                    # It is selected
                    jid = self._model[iter_][1]
                    # Keep same groups and same nickname
                    groups = self._model[iter_][3].split(", ")
                    if groups == [""]:
                        groups = []
                    self._client.get_module("Roster").set_item(
                        jid, self._model[iter_][2], groups
                    )

                iter_ = self._model.iter_next(iter_)
        elif self._action == "delete":
            count = 0
            while iter_:
                if self._model[iter_][0]:
                    count += 1
                    # It is selected
                    jid = self._model[iter_][1]
                    self._client.get_module("Presence").unsubscribe(jid)
                    self._client.get_module("Roster").delete_item(jid)
                iter_ = self._model.iter_next(iter_)
            SimpleDialog(
                _("Successfully Removed Contacts"),
                i18n.ngettext(
                    "Removed %(count)s contact", "Removed %(count)s contacts", count
                )
                % {"count": count},
            )
        self.close()

    def _on_cancel_button_clicked(self, _button: Gtk.Button) -> None:
        self.close()
