# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import Gtk

import gajim.common.storage.archive.models as mod
from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import get_ui_string

MAX_AVATARS = 5


@Gtk.Template.from_string(string=get_ui_string("conversation/avatar_stack.ui"))
class AvatarStack(Gtk.MenuButton):
    __gtype_name__ = "AvatarStack"

    _avatar_box: Gtk.Box = Gtk.Template.Child()
    _more_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.MenuButton.__init__(self)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        self.set_create_popup_func(self._on_clicked)

        self._scale_factor = self.get_scale_factor()

        self._markers: list[mod.DisplayedMarker] = []

    def set_data(self, markers: list[mod.DisplayedMarker]) -> None:
        self._markers = markers.copy()
        container_remove_all(self._avatar_box)

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
            assert marker.occupant is not None
            self.set_tooltip_text(_("Seen by %s") % marker.occupant.nickname)
        else:
            self.set_tooltip_text(_("Seen by %s participants") % marker_count)

    def _get_avatar_image(self, marker: mod.DisplayedMarker) -> Gtk.Image:
        assert marker.occupant is not None
        texture = app.app.avatar_storage.get_occupant_texture(
            marker.remote.jid,
            marker.occupant,
            size=AvatarSize.SMALL,
            scale=self._scale_factor,
        )

        image = Gtk.Image.new_from_paintable(texture)
        image.set_pixel_size(AvatarSize.SMALL)
        return image

    def _on_clicked(self, _widget: AvatarStack) -> None:
        self.set_popover(AvatarStackPopover(self._markers))


@Gtk.Template.from_string(string=get_ui_string("conversation/avatar_stack_popover.ui"))
class AvatarStackPopover(Gtk.Popover):
    __gtype_name__ = "AvatarStackPopover"

    _listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self, data: list[mod.DisplayedMarker]) -> None:
        Gtk.Popover.__init__(self)

        for entry in data:
            self._listbox.append(AvatarStackPopoverRow(entry))


@Gtk.Template.from_string(
    string=get_ui_string("conversation/avatar_stack_popover_row.ui")
)
class AvatarStackPopoverRow(Gtk.ListBoxRow):
    __gtype_name__ = "AvatarStackPopoverRow"

    _avatar_image: Gtk.Image = Gtk.Template.Child()
    _contact_name_label: Gtk.Label = Gtk.Template.Child()
    _timestamp_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, marker: mod.DisplayedMarker) -> None:
        Gtk.ListBoxRow.__init__(self)

        assert marker.occupant is not None
        texture = app.app.avatar_storage.get_occupant_texture(
            marker.remote.jid,
            marker.occupant,
            size=AvatarSize.ROSTER,
            scale=self.get_scale_factor(),
        )

        self._avatar_image.set_from_paintable(texture)
        self._avatar_image.set_pixel_size(AvatarSize.ROSTER)

        self._contact_name_label.set_text(marker.occupant.nickname or "")

        dt_format = app.settings.get("date_time_format")
        timestamp = marker.timestamp.astimezone()
        self._timestamp_label.set_text(timestamp.strftime(dt_format))
