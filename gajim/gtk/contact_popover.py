# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime as dt

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.util.status import get_uf_show

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("contact_popover.ui"))
class ContactPopover(Gtk.Popover, EventHelper, SignalManager):
    __gtype_name__ = "ContactPopover"

    _avatar: Gtk.Image = Gtk.Template.Child()
    _name: Gtk.Label = Gtk.Template.Child()
    _role: Gtk.Label = Gtk.Template.Child()
    _org: Gtk.Label = Gtk.Template.Child()
    _info_listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self, contact: BareContact) -> None:
        Gtk.Popover.__init__(self)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._contact = contact

        self._update(contact)

    def _update(self, contact: BareContact) -> None:
        scale = self.get_scale_factor()

        texture = contact.get_avatar(AvatarSize.TOOLTIP, scale)
        self._avatar.set_pixel_size(AvatarSize.TOOLTIP)
        self._avatar.set_from_paintable(texture)

        self._name.set_markup(GLib.markup_escape_text(contact.name))

        # TODO: if role/org available
        self._role.set_label("Head of sales")
        self._role.set_visible(True)
        self._org.set_label("Big Corpo")
        self._org.set_visible(True)

        # Subscription
        if not contact.is_self and contact.subscription != "both":
            # "both" is properly subscribed. Show a warning otherwise.
            self._info_listbox.append(
                ContactPopoverInfoRow(self._contact, "subscription")
            )

        self._info_listbox.append(ContactPopoverInfoRow(self._contact, "status"))
        if self._contact.status:
            self._info_listbox.append(
                ContactPopoverInfoRow(self._contact, "status_message")
            )

        self._info_listbox.append(ContactPopoverInfoRow(self._contact, "jid"))

        # TODO: if email available
        self._info_listbox.append(ContactPopoverInfoRow(self._contact, "email"))

        # TODO: if telephone available
        self._info_listbox.append(ContactPopoverInfoRow(self._contact, "tel"))

        # TODO: if timezone available
        self._info_listbox.append(ContactPopoverInfoRow(self._contact, "time"))

        app.plugin_manager.extension_point("contact_tooltip_populate", self, contact)

    @Gtk.Template.Callback()
    def _on_contact_details_clicked(self, _button: Gtk.Button) -> None:
        account_jid_params = AccountJidParam(
            account=self._contact.account, jid=self._contact.jid
        )
        app.window.activate_action(
            "win.chat-contact-info", account_jid_params.to_variant()
        )


@Gtk.Template(string=get_ui_string("contact_popover_info_row.ui"))
class ContactPopoverInfoRow(Gtk.ListBoxRow):
    __gtype_name__ = "ContactPopoverInfoRow"

    _icon: Gtk.Image = Gtk.Template.Child()
    _label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, contact: BareContact, info_type: str) -> None:
        Gtk.ListBoxRow.__init__(self)

        self._contact = contact

        if info_type == "subscription":
            self._icon.set_from_icon_name("dialog-warning-symbolic")
            self._label.set_text(_("You are not sharing your status"))

        if info_type == "status":
            surface = get_show_circle(
                self._contact.show, AvatarSize.SHOW_CIRCLE, self.get_scale_factor()
            )
            self._icon.set_from_paintable(convert_surface_to_texture(surface))
            status_text = get_uf_show(self._contact.show.value)
            if idle_time_text := self._get_idle_time():
                status_text += f" ({idle_time_text})"
            self._label.set_text(status_text)

        if info_type == "status_message":
            self._icon.set_from_icon_name("feather-info-symbolic")
            self._label.set_text(self._contact.status)
            if len(self._contact.status) > 30:
                self._label.set_tooltip_text(self._contact.status)

        if info_type == "jid":
            self._icon.set_from_icon_name("lucide-message-circle-more-symbolic")
            self._label.set_use_markup(True)
            self._label.set_markup(
                f"<a href='xmpp:{self._contact.jid}'>{self._contact.jid}</a>"
            )
            self._label.set_selectable(True)

        if info_type == "email":
            self._icon.set_from_icon_name("mail-unread-symbolic")
            # TODO
            email = "sales@big-corpo.com"
            self._label.set_use_markup(True)
            self._label.set_markup(f"<a href='mailto:{email}'>{email}</a>")
            self._label.set_selectable(True)

        if info_type == "tel":
            self._icon.set_from_icon_name("call-start-symbolic")
            # TODO
            tel = "+0123456789"
            self._label.set_use_markup(True)
            self._label.set_markup(f"<a href='tel:{tel}'>{tel}</a>")
            self._label.set_selectable(True)

        if info_type == "time":
            self._icon.set_from_icon_name("feather-clock-symbolic")
            # TODO
            self._label.set_text("17:00 (your timezone)")

    def _get_idle_time(self) -> str | None:
        if self._contact.idle_datetime is None:
            return None

        current = dt.datetime.now()
        if self._contact.idle_datetime.date() == current.date():
            format_string = app.settings.get("time_format")
            formatted = self._contact.idle_datetime.strftime(format_string)
        else:
            format_string = app.settings.get("date_time_format")
            formatted = self._contact.idle_datetime.strftime(format_string)
        return _("last seen: %s") % formatted
