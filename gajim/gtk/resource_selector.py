# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import locale
import logging

from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.structs import DiscoInfo

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import clear_listbox

log = logging.getLogger("gajim.gtk.resource_selector")


class ResourceSelector(Gtk.ScrolledWindow, SignalManager):

    __gsignals__ = {
        "selection-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(
        self, contact: BareContact, constraints: list[str] | None = None
    ) -> None:
        Gtk.ScrolledWindow.__init__(self, height_request=200)
        SignalManager.__init__(self)

        self.add_css_class("resource-selector")

        self._listbox = Gtk.ListBox()
        self._listbox.set_sort_func(self._sort_func)
        self._connect(self._listbox, "row-selected", self._on_row_selected)
        self.set_child(self._listbox)

        self._contact = contact
        self._contact.connect("presence-update", self._on_update)
        self._contact.connect("caps-update", self._on_update)

        # Constraints include nbxmpp Namespaces a resource has to support
        self._constraints = constraints or []

        self._set_placeholder()
        self._add_entries()

    def do_unroot(self) -> None:
        self._disconnect_all()
        self._contact.disconnect_all_from_obj(self)

        self._listbox.set_sort_func(None)
        Gtk.ScrolledWindow.do_unroot(self)
        app.check_finalize(self)

    @staticmethod
    def _sort_func(row1: ResourceRow, row2: ResourceRow) -> int:
        return locale.strcoll(row1.device_text.lower(), row2.device_text.lower())

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: ResourceRow | None) -> None:
        state = bool(row is not None)
        self.emit("selection-changed", state)

    def _set_placeholder(self) -> None:
        image = Gtk.Image.new_from_icon_name("lucide-circle-alert-symbolic")
        label = Gtk.Label(label=_("No devices online"))
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER
        )
        box.add_css_class("dimmed")
        box.append(image)
        box.append(label)
        self._listbox.set_placeholder(box)

    def _add_entries(self) -> None:
        for resource in self._contact.iter_resources():
            self._listbox.append(ResourceRow(resource, self._constraints))

    def _on_update(self, _contact: types.ResourceContact, _signal_name: str) -> None:
        clear_listbox(self._listbox)
        self._add_entries()

    def get_jid(self) -> JID:
        resource_row = cast(ResourceRow, self._listbox.get_selected_row())
        return resource_row.jid


class ResourceRow(Gtk.ListBoxRow):
    def __init__(
        self, resource_contact: ResourceContact, constraints: list[str]
    ) -> None:
        Gtk.ListBoxRow.__init__(self)

        self.jid = resource_contact.jid

        icon_name = "lucide-laptop-symbolic"
        tooltip_text = _("Computer")
        self.device_text = resource_contact.jid.resource or ""

        disco_info = app.storage.cache.get_last_disco_info(resource_contact.jid)
        if disco_info is not None:
            name, type_ = self._get_client_identity(disco_info)
            if name is not None:
                self.device_text = f"{name} ({resource_contact.jid.resource})"
            if type_ is not None:
                if type_ == "phone":
                    icon_name = "lucide-smartphone-symbolic"
                    tooltip_text = _("Phone")

        image = Gtk.Image(icon_name=icon_name, tooltip_text=tooltip_text, pixel_size=32)

        name_label = Gtk.Label()
        name_label.set_text(self.device_text)

        box = Gtk.Box(spacing=12)
        box.append(image)
        box.append(name_label)

        for constraint in constraints:
            if not resource_contact.supports(constraint):
                self.set_sensitive(False)
                self.set_tooltip_text(_("This device is not compatible."))

        self.set_child(box)

    @staticmethod
    def _get_client_identity(disco_info: DiscoInfo) -> tuple[str | None, str | None]:
        for identity in disco_info.identities:
            if identity.category == "client":
                return identity.name, identity.type
        return None, None
