# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.client import BareContact
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.modules.chat_markers import DisplayedMarkerData
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.types import ChatContactT
from gajim.common.util.user_strings import get_uf_relative_time

from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import get_ui_string

MAX_AVATARS = 5


@Gtk.Template.from_string(string=get_ui_string("conversation/avatar_stack.ui"))
class AvatarStack(Gtk.MenuButton):
    __gtype_name__ = "AvatarStack"

    _avatar_box: Gtk.Box = Gtk.Template.Child()
    _more_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, account: str) -> None:
        Gtk.MenuButton.__init__(self)

        self._account = account
        self._client = app.get_client(self._account)

        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        self.set_create_popup_func(self._on_clicked)

        self._scale_factor = self.get_scale_factor()

        self._markers: list[DisplayedMarkerData] = []
        self._avatar_contacts: set[ChatContactT] = set()

    def do_unroot(self) -> None:
        self._disconnect_avatar_contacts()
        self.set_create_popup_func(None)
        Gtk.MenuButton.do_unroot(self)

    def set_data(self, markers: list[DisplayedMarkerData]) -> None:
        self._disconnect_avatar_contacts()
        self._markers = markers.copy()
        self._connect_avatar_contacts()
        container_remove_all(self._avatar_box)

        if not markers:
            return

        for entry in self._markers[:MAX_AVATARS]:
            self._avatar_box.append(self._get_avatar_image(entry))

        entries_count = len(self._markers)
        if entries_count > MAX_AVATARS:
            self._more_label.set_visible(True)
            self._more_label.set_label(f"+{entries_count - MAX_AVATARS}")
        else:
            self._more_label.set_visible(False)
            self._more_label.set_label("")

        marker_count = len(self._markers)
        if marker_count == 1:
            marker = markers[0]

            if marker.occupant is None:
                contact = self._client.get_module("Contacts").get_contact_if_exists(
                    marker.jid
                )
                assert contact is not None
                assert not isinstance(contact, ResourceContact)
                nickname = contact.name
            else:
                nickname = marker.occupant.nickname

            self.set_tooltip_text(_("Seen by %s") % nickname)
        else:
            self.set_tooltip_text(_("Seen by %s participants") % marker_count)

    def _connect_avatar_contacts(self) -> None:
        contacts = self._client.get_module("Contacts")
        for marker in self._markers:
            contact = contacts.get_contact_if_exists(marker.jid)
            if contact is None or isinstance(contact, ResourceContact):
                continue

            if marker.occupant is None:
                if isinstance(contact, BareContact):
                    contact.connect("avatar-update", self._on_avatar_update)
                    self._avatar_contacts.add(contact)
                continue

            if isinstance(contact, GroupchatContact):
                contact.connect("user-avatar-update", self._on_muc_avatar_update)
                self._avatar_contacts.add(contact)

    def _disconnect_avatar_contacts(self) -> None:
        for contact in self._avatar_contacts:
            contact.disconnect_all_from_obj(self)
        self._avatar_contacts.clear()

    def _on_avatar_update(self, *args: object) -> None:
        self.set_data(self._markers)

    def _on_muc_avatar_update(
        self,
        _room: GroupchatContact,
        _signal_name: str,
        contact: GroupchatParticipant,
        _avatar_sha: str | None,
        *args: object,
    ) -> None:
        updated = False
        for marker in self._markers:
            occupant = marker.occupant
            if occupant is None:
                continue

            matches_occupant = (
                contact.occupant_id is not None and occupant.id == contact.occupant_id
            )
            matches_nickname = occupant.nickname == contact.name
            if not matches_occupant and not matches_nickname:
                continue

            app.storage.archive.refresh(occupant, ["avatar_sha"])
            updated = True

        if updated:
            self.set_data(self._markers)

    def _get_avatar_image(self, marker: DisplayedMarkerData) -> Gtk.Image:
        texture = None
        if marker.occupant is None:
            contact = self._client.get_module("Contacts").get_contact_if_exists(
                marker.jid
            )
            assert contact is not None
            if isinstance(contact, BareContact):
                texture = contact.get_avatar(
                    size=AvatarSize.SMALL, scale=self._scale_factor, add_show=False
                )

        else:
            texture = app.app.avatar_storage.get_occupant_texture(
                marker.jid,
                marker.occupant,
                size=AvatarSize.SMALL,
                scale=self._scale_factor,
            )

        image = Gtk.Image.new_from_paintable(texture)
        image.set_pixel_size(AvatarSize.SMALL)
        return image

    def _on_clicked(self, _widget: AvatarStack) -> None:
        self.set_popover(AvatarStackPopover(self._account, self._markers))


@Gtk.Template.from_string(string=get_ui_string("conversation/avatar_stack_popover.ui"))
class AvatarStackPopover(Gtk.Popover):
    __gtype_name__ = "AvatarStackPopover"

    _listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self, account: str, data: list[DisplayedMarkerData]) -> None:
        Gtk.Popover.__init__(self)

        for entry in data:
            self._listbox.append(AvatarStackPopoverRow(account, entry))


@Gtk.Template.from_string(
    string=get_ui_string("conversation/avatar_stack_popover_row.ui")
)
class AvatarStackPopoverRow(Gtk.ListBoxRow):
    __gtype_name__ = "AvatarStackPopoverRow"

    _avatar_image: Gtk.Image = Gtk.Template.Child()
    _contact_name_label: Gtk.Label = Gtk.Template.Child()
    _timestamp_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, account: str, marker: DisplayedMarkerData) -> None:
        Gtk.ListBoxRow.__init__(self)

        nickname = ""
        texture = None

        if marker.occupant is None:
            client = app.get_client(account)
            contact = client.get_module("Contacts").get_contact_if_exists(marker.jid)
            assert contact is not None
            if isinstance(contact, BareContact):
                texture = contact.get_avatar(
                    size=AvatarSize.SMALL, scale=self.get_scale_factor(), add_show=False
                )
                nickname = contact.name

        else:
            texture = app.app.avatar_storage.get_occupant_texture(
                marker.jid,
                marker.occupant,
                size=AvatarSize.ROSTER,
                scale=self.get_scale_factor(),
            )
            nickname = marker.occupant.nickname or ""

        self._avatar_image.set_from_paintable(texture)
        self._avatar_image.set_pixel_size(AvatarSize.ROSTER)

        self._contact_name_label.set_text(nickname)

        self._timestamp_label.set_text(get_uf_relative_time(marker.timestamp))
