# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize

from gajim.gtk.util.misc import get_ui_string

MAX_AVATARS = 5


@dataclass
class AvatarStackData:
    nickname: str | None
    timestamp: dt.datetime
    avatar_sha: str | None


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

        self._data: list[AvatarStackData] = []

    def set_data(self, data: list[AvatarStackData]) -> None:
        self._data = data

        for entry in self._data[:MAX_AVATARS]:
            self._avatar_box.append(self._get_avatar_image(entry))

        entries_count = len(self._data)
        if entries_count > MAX_AVATARS:
            self._more_label.set_label(f"+{entries_count - MAX_AVATARS}")
        else:
            self._more_label.set_label("")

    def _get_avatar_image(self, data: AvatarStackData) -> Gtk.Image:
        texture = None
        if data.avatar_sha is not None:
            texture = app.app.avatar_storage.get_avatar_by_sha(
                data.avatar_sha, AvatarSize.SMALL, self._scale_factor
            )

        if texture is None:
            # TODO: get default avatar
            pass

        image = Gtk.Image.new_from_paintable(texture)
        image.set_pixel_size(AvatarSize.SMALL)
        return image

    def _on_clicked(self, _widget: AvatarStack) -> None:
        self.set_popover(AvatarStackPopover(self._data))


@Gtk.Template.from_string(string=get_ui_string("conversation/avatar_stack_popover.ui"))
class AvatarStackPopover(Gtk.Popover):
    __gtype_name__ = "AvatarStackPopover"

    _listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self, data: list[AvatarStackData]) -> None:
        Gtk.Popover.__init__(self, autohide=False)
        self._scale_factor = self.get_scale_factor()

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

    def __init__(self, data: AvatarStackData) -> None:
        Gtk.ListBoxRow.__init__(self)
        scale_factor = self.get_scale_factor()
        self._avatar_image.set_pixel_size(AvatarSize.SMALL)

        texture = None
        if data.avatar_sha is not None:
            texture = app.app.avatar_storage.get_avatar_by_sha(
                data.avatar_sha, AvatarSize.SMALL, scale_factor
            )

        if texture is None:
            # TODO: get default avatar
            pass

        self._avatar_image.set_from_paintable(texture)

        self._contact_name_label.set_text(data.nickname)

        dt_format = app.settings.get("date_time_format")
        timestamp = data.timestamp.astimezone()
        self._timestamp_label.set_text(timestamp.strftime(dt_format))
