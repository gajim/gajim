# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import datetime as dt

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.status import get_uf_show
from gajim.common.util.text import format_location
from gajim.common.util.text import format_tune
from gajim.common.util.user_strings import get_uf_sub

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("contact_popover.ui"))
class ContactPopover(Gtk.Popover, EventHelper, SignalManager):
    __gtype_name__ = "ContactPopover"

    _jid: Gtk.Label = Gtk.Template.Child()
    _tune_label: Gtk.Label = Gtk.Template.Child()
    _location_label: Gtk.Label = Gtk.Template.Child()
    _tune: Gtk.Label = Gtk.Template.Child()
    _location: Gtk.Label = Gtk.Template.Child()
    _name: Gtk.Label = Gtk.Template.Child()
    _avatar: Gtk.Image = Gtk.Template.Child()
    _sub_label: Gtk.Label = Gtk.Template.Child()
    _sub: Gtk.Label = Gtk.Template.Child()
    _resources_box: Gtk.Box = Gtk.Template.Child()

    def __init__(self, contact: BareContact) -> None:
        Gtk.Popover.__init__(self)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._contact = contact

        self._populate_grid(contact)
        # self._connect(self._copy_jid_button, "clicked", self._on_copy_jid_clicked)

    def _populate_grid(self, contact: BareContact) -> None:
        scale = self.get_scale_factor()

        texture = contact.get_avatar(AvatarSize.TOOLTIP, scale)
        self._avatar.set_pixel_size(AvatarSize.TOOLTIP)
        self._avatar.set_from_paintable(texture)
        self._avatar.set_visible(True)

        self._name.set_markup(GLib.markup_escape_text(contact.name))
        self._name.set_visible(True)

        self._jid.set_text(str(contact.jid))
        self._jid.set_visible(True)

        if contact.has_resources():
            for res in contact.iter_resources():
                self._add_resources(res)
        else:
            self._add_resources(contact)

        if contact.subscription and contact.subscription != "both":
            # 'both' is the normal subscription value, just omit it
            self._sub.set_text(get_uf_sub(contact.subscription))
            self._sub.set_visible(True)
            self._sub_label.set_visible(True)

        self._append_pep_info(contact)

        app.plugin_manager.extension_point("contact_tooltip_populate", self, contact)

        # This sets the bottom-most widget to expand, in case the avatar
        # takes more space than the labels
        row_count = 1
        grid = cast(Gtk.Grid, self.get_child())
        last_widget = grid.get_child_at(1, 1)
        assert last_widget is not None
        while row_count < 6:
            widget = grid.get_child_at(1, row_count)
            if widget and widget.get_visible():
                last_widget = widget
                row_count += 1
            else:
                break
        last_widget.set_vexpand(True)

    def _add_resources(self, contact: BareContact | ResourceContact) -> None:

        resource_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        show_surface = get_show_circle(
            contact.show,
            AvatarSize.SHOW_CIRCLE,
            self.get_scale_factor(),
        )
        show_image = Gtk.Image(
            paintable=convert_surface_to_texture(show_surface),
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
        )

        show_string = get_uf_show(contact.show.value)

        resource_string = ""
        if contact.jid.resource is not None:
            escaped_resource = GLib.markup_escape_text(contact.jid.resource)
            resource_string = f" ({escaped_resource})"

        resource_label = Gtk.Label(
            ellipsize=Pango.EllipsizeMode.END,
            halign=Gtk.Align.START,
            label=f"{show_string}{resource_string}",
            max_width_chars=30,
            xalign=0,
        )

        base_box = Gtk.Box(spacing=6)
        base_box.append(show_image)
        base_box.append(resource_label)
        resource_box.append(base_box)

        if contact.status:
            status_label = Gtk.Label(
                ellipsize=Pango.EllipsizeMode.END,
                halign=Gtk.Align.START,
                label=contact.status,
                max_width_chars=30,
                xalign=0,
            )
            resource_box.append(status_label)

        if idle_datetime := contact.idle_datetime:
            current = dt.datetime.now()
            if idle_datetime.date() == current.date():
                format_string = app.settings.get("time_format")
                formatted = idle_datetime.strftime(format_string)
            else:
                format_string = app.settings.get("date_time_format")
                formatted = idle_datetime.strftime(format_string)
            idle_text = _("Idle since: %s") % formatted
            idle_label = Gtk.Label(
                halign=Gtk.Align.START,
                label=idle_text,
                xalign=0,
            )
            resource_box.append(idle_label)

        app.plugin_manager.extension_point(
            "contact_tooltip_resource_populate", resource_box, contact
        )

        self._resources_box.append(resource_box)
        self._resources_box.set_visible(True)

    def _append_pep_info(self, contact: BareContact) -> None:
        tune = contact.get_tune()
        if tune is not None:
            tune_str = format_tune(tune)
            self._tune.set_markup(tune_str)
            self._tune.set_visible(True)
            self._tune_label.set_visible(True)

        location = contact.get_location()
        if location is not None:
            location_str = format_location(location)
            self._location.set_markup(location_str)
            self._location.set_visible(True)
            self._location_label.set_visible(True)
