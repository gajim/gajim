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

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatOfflineParticipant
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.util.user_strings import get_uf_affiliation

from gajim.gtk.builder import get_builder
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import iterate_children

log = logging.getLogger("gajim.gtk.tooltips")


class GCTooltip:
    def __init__(self) -> None:
        self._contact: GroupchatParticipant | GroupchatOfflineParticipant | None = None

    def clear_tooltip(self) -> None:
        self._contact = None

    def get_tooltip(
        self, contact: GroupchatParticipant | GroupchatOfflineParticipant
    ) -> tuple[bool, Gtk.Grid]:
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

    def _populate_grid(
        self, contact: GroupchatParticipant | GroupchatOfflineParticipant
    ) -> None:
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
                if hat.hue is not None:
                    css_provider = Gtk.CssProvider()
                    css_provider.load_from_string(
                        f".badge-hat {{background-color: hsl({hat.hue}, 100%, 25%);}}"
                    )
                    context = hat_badge.get_style_context()
                    context.add_provider(
                        css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )

                hat_badge_icon = Gtk.Image.new_from_icon_name("lucide-tag-symbolic")
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
