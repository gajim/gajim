# Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
from datetime import datetime

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.util.status import get_uf_show
from gajim.common.util.text import format_location
from gajim.common.util.text import format_tune
from gajim.common.util.user_strings import get_uf_affiliation
from gajim.common.util.user_strings import get_uf_sub

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.builder import get_builder
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.util.misc import iterate_children

log = logging.getLogger("gajim.gtk.tooltips")


class GCTooltip:
    def __init__(self) -> None:
        self._contact: GroupchatParticipant | None = None

    def clear_tooltip(self) -> None:
        self._contact = None

    def get_tooltip(self, contact: GroupchatParticipant) -> tuple[bool, Gtk.Grid]:
        if not hasattr(self, "_ui"):
            self._ui = get_builder("groupchat_roster_tooltip.ui")

        if self._contact == contact:
            return True, self._ui.tooltip_grid

        self._populate_grid(contact)
        self._contact = contact
        return False, self._ui.tooltip_grid

    def _hide_grid_children(self) -> None:
        """
        Hide all Elements of the Tooltip Grid
        """
        for widget in iterate_children(self._ui.tooltip_grid):
            widget.set_visible(False)

    def _populate_grid(self, contact: GroupchatParticipant) -> None:
        """
        Populate the Tooltip Grid with data of from the contact
        """
        self._hide_grid_children()

        self._ui.nick.set_text(contact.name)
        self._ui.nick.set_visible(True)

        # Status Message
        if contact.status:
            status = contact.status.strip()
            if status != "":
                self._ui.status.set_text(status)
                self._ui.status.set_visible(True)

        # JID
        if contact.real_jid is not None:
            self._ui.jid.set_text(str(contact.real_jid.bare))
            self._ui.jid.set_visible(True)

        # Affiliation
        if not contact.affiliation.is_none:
            uf_affiliation = get_uf_affiliation(contact.affiliation)
            uf_affiliation = _("%(owner_or_admin_or_member)s of this group chat") % {
                "owner_or_admin_or_member": uf_affiliation
            }
            self._ui.affiliation.set_text(uf_affiliation)
            self._ui.affiliation.set_visible(True)

        if contact.hats is not None:

            container_remove_all(self._ui.hats_box)

            for hat in contact.hats.get_hats()[:5]:
                # Limit to 5 hats
                hat_badge = Gtk.Box(spacing=6, halign=Gtk.Align.START)
                hat_badge.add_css_class("badge")
                hat_badge.add_css_class("badge-hat")

                hat_badge_icon = Gtk.Image.new_from_icon_name("feather-tag-symbolic")
                hat_badge.append(hat_badge_icon)

                hat_badge_label = Gtk.Label(
                    label=GLib.markup_escape_text(hat.title),
                    ellipsize=Pango.EllipsizeMode.END,
                    max_width_chars=20,
                    halign=Gtk.Align.START,
                )
                hat_badge.append(hat_badge_label)

                self._ui.hats_box.append(hat_badge)
                self._ui.hats_box.set_visible(True)

        # Avatar
        scale = self._ui.tooltip_grid.get_scale_factor()
        texture = contact.get_avatar(AvatarSize.TOOLTIP, scale)
        self._ui.avatar.set_pixel_size(AvatarSize.TOOLTIP)
        self._ui.avatar.set_from_paintable(texture)
        self._ui.avatar.set_visible(True)
        self._ui.fillelement.set_visible(True)

        app.plugin_manager.extension_point(
            "gc_tooltip_populate", self, contact, self._ui.tooltip_grid
        )


class ContactTooltip:
    def __init__(self) -> None:
        self._contact = None

    def clear_tooltip(self) -> None:
        self._contact = None
        if not hasattr(self, "_ui"):
            return
        container_remove_all(self._ui.resources_box)
        for widget in iterate_children(self._ui.tooltip_grid):
            widget.set_visible(False)

    def get_tooltip(self, contact: types.BareContact) -> tuple[bool, Gtk.Grid]:
        if not hasattr(self, "_ui"):
            self._ui = get_builder("contact_tooltip.ui")

        if self._contact == contact:
            return True, self._ui.tooltip_grid

        self.clear_tooltip()
        self._populate_grid(contact)
        self._contact = contact
        return False, self._ui.tooltip_grid

    def _populate_grid(self, contact: types.BareContact) -> None:
        scale = self._ui.tooltip_grid.get_scale_factor()

        texture = contact.get_avatar(AvatarSize.TOOLTIP, scale)
        self._ui.avatar.set_pixel_size(AvatarSize.TOOLTIP)
        self._ui.avatar.set_from_paintable(texture)
        self._ui.avatar.set_visible(True)

        self._ui.name.set_markup(GLib.markup_escape_text(contact.name))
        self._ui.name.set_visible(True)

        self._ui.jid.set_text(str(contact.jid))
        self._ui.jid.set_visible(True)

        if contact.has_resources():
            for res in contact.iter_resources():
                self._add_resources(res)
        else:
            self._add_resources(contact)

        if contact.subscription and contact.subscription != "both":
            # 'both' is the normal subscription value, just omit it
            self._ui.sub.set_text(get_uf_sub(contact.subscription))
            self._ui.sub.set_visible(True)
            self._ui.sub_label.set_visible(True)

        self._append_pep_info(contact)

        app.plugin_manager.extension_point("contact_tooltip_populate", self, contact)

        # This sets the bottom-most widget to expand, in case the avatar
        # takes more space than the labels
        row_count = 1
        last_widget = self._ui.tooltip_grid.get_child_at(1, 1)
        assert last_widget is not None
        while row_count < 6:
            widget = self._ui.tooltip_grid.get_child_at(1, row_count)
            if widget and widget.get_visible():
                last_widget = widget
                row_count += 1
            else:
                break
        last_widget.set_vexpand(True)

    def _add_resources(
        self, contact: types.BareContact | types.ResourceContact
    ) -> None:

        resource_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        show_surface = get_show_circle(
            contact.show,
            AvatarSize.SHOW_CIRCLE,
            self._ui.tooltip_grid.get_scale_factor(),
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
            current = datetime.now()
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

        self._ui.resources_box.append(resource_box)
        self._ui.resources_box.set_visible(True)

    def _append_pep_info(self, contact: types.BareContact) -> None:
        tune = contact.get_tune()
        if tune is not None:
            tune_str = format_tune(tune)
            self._ui.tune.set_markup(tune_str)
            self._ui.tune.set_visible(True)
            self._ui.tune_label.set_visible(True)

        location = contact.get_location()
        if location is not None:
            location_str = format_location(location)
            self._ui.location.set_markup(location_str)
            self._ui.location.set_visible(True)
            self._ui.location_label.set_visible(True)
