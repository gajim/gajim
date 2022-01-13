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

log = logging.getLogger('gajim.gui.resource_selector')


class ResourceSelector(Gtk.ScrolledWindow):

    __gsignals__ = {
        'selection-changed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            (bool, )),
    }

    def __init__(self,
                 contact: BareContact,
                 constraints: Optional[list[str]] = None) -> None:
        Gtk.ScrolledWindow.__init__(self)
        self.set_shadow_type(Gtk.ShadowType.IN)
        self.set_size_request(-1, 200)
        self.get_style_context().add_class('resource-selector')

        self._listbox = Gtk.ListBox()
        self._listbox.set_sort_func(self._sort_func)
        self._listbox.connect('row-selected', self._on_row_selected)
        self.add(self._listbox)

        self._contact = contact
        self._contact.connect('presence-update', self._on_update)
        self._contact.connect('caps-update', self._on_update)

        # Constraints include nbxmpp Namespaces a resource has to support
        self._constraints = constraints or []

        self._set_placeholder()
        self._add_entries()

        self.show_all()

    @staticmethod
    def _sort_func(row1: ResourceRow, row2: ResourceRow) -> int:
        return locale.strcoll(
            row1.device_text.lower(), row2.device_text.lower())

    def _on_row_selected(self,
                         _listbox: Gtk.ListBox,
                         row: ResourceRow
                         ) -> None:
        state = bool(row is not None)
        self.emit('selection-changed', state)

    def _set_placeholder(self) -> None:
        image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.DND)
        label = Gtk.Label(label=_('No devices online'))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        box.get_style_context().add_class('dim-label')
        box.add(image)
        box.add(label)
        box.show_all()
        self._listbox.set_placeholder(box)

    def _add_entries(self) -> None:
        for resource in self._contact.iter_resources():
            self._listbox.add(ResourceRow(resource, self._constraints))

    def _on_update(self,
                   _contact: types.ResourceContact,
                   _signal_name: str
                   ) -> None:
        for child in self._listbox.get_children():
            self._listbox.remove(child)
        self._add_entries()

    def get_jid(self) -> JID:
        resource_row = cast(ResourceRow, self._listbox.get_selected_row())
        return resource_row.jid


class ResourceRow(Gtk.ListBoxRow):
    def __init__(self,
                 resource_contact: ResourceContact,
                 constraints: list[str]
                 ) -> None:
        Gtk.ListBoxRow.__init__(self)

        self.jid = resource_contact.jid

        icon_name = 'computer-symbolic'
        tooltip_text = _('Computer')
        self.device_text = resource_contact.jid.resource or ''

        disco_info = app.storage.cache.get_last_disco_info(
            resource_contact.jid)
        if disco_info is not None:
            name, type_ = self._get_client_identity(disco_info)
            if name is not None:
                self.device_text = f'{name} ({resource_contact.jid.resource})'
            if type_ is not None:
                if type_ == 'phone':
                    icon_name = 'phone-symbolic'
                    tooltip_text = _('Phone')

        image = Gtk.Image()
        image.set_from_icon_name(icon_name, Gtk.IconSize.DND)
        image.set_tooltip_text(tooltip_text)

        name_label = Gtk.Label()
        name_label.set_text(self.device_text)

        box = Gtk.Box(spacing=12)
        box.add(image)
        box.add(name_label)

        for constraint in constraints:
            if not resource_contact.supports(constraint):
                self.set_sensitive(False)
                self.set_tooltip_text(_('This devices is not compatible.'))

        self.add(box)
        self.show_all()

    @staticmethod
    def _get_client_identity(disco_info: DiscoInfo
                             ) -> tuple[Optional[str], Optional[str]]:
        for identity in disco_info.identities:
            if identity.category == 'client':
                return identity.name, identity.type
        return None, None
