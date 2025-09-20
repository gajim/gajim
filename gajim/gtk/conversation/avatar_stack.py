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
from gajim.common.modules.contacts import ResourceContact
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

    def do_unroot(self) -> None:
        self.set_create_popup_func(None)
        Gtk.MenuButton.do_unroot(self)
        app.check_finalize(self)

    def set_data(self, markers: list[DisplayedMarkerData]) -> None:
        self._markers = markers.copy()
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
